import argparse
import asyncio
import httpx
import aiofiles
import os
import logging
from tqdm.asyncio import tqdm

from utils.check_gramplay_optimized import is_valid_url, write_batches, check_gramplay
from config import INPUT_FILE, FAILED_FILE, OUTPUT_FILE, COMPLETED_FILE


# Argument parser to handle optional command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description="Process URLs with optional configuration.")

    parser.add_argument(
        '--concurrent-requests', type=int, default=CONCURRENT_REQUESTS,
        help=f"Number of concurrent requests (default: {CONCURRENT_REQUESTS})"
    )
    parser.add_argument(
        '--batch-write-interval', type=int, default=BATCH_WRITE_INTERVAL,
        help=f"Seconds between batch writes (default: {BATCH_WRITE_INTERVAL})"
    )
    parser.add_argument(
        '--retries', type=int, default=RETRIES,
        help=f"Number of retry attempts for failed requests (default: {RETRIES})"
    )
    parser.add_argument(
        '--backoff-factor', type=float, default=BACKOFF_FACTOR,
        help=f"Factor for exponential backoff (default: {BACKOFF_FACTOR})"
    )

    return parser.parse_args()


async def process_urls():
    """
    Process URLs from output_urls.txt and failed_urls.txt until no more failed URLs remain.
    """
    # Loop until there are no more failed URLs
    while True:
        # Check if failed_urls.txt exists and has contents
        if os.path.isfile(FAILED_FILE):
            async with aiofiles.open(FAILED_FILE, 'r', encoding='utf-8') as f:
                failed_urls = [line.strip() for line in await f.readlines() if line.strip()]
        else:
            failed_urls = []

        if not failed_urls:
            logging.info("No failed URLs left to process. Exiting.")
            print("No failed URLs left to process. Exiting.")
            break

        # Move failed URLs to output_urls.txt
        async with aiofiles.open(INPUT_FILE, 'w', encoding='utf-8') as out_f:
            await out_f.write('\n'.join(failed_urls) + '\n')

        # Clear failed_urls.txt
        async with aiofiles.open(FAILED_FILE, 'w', encoding='utf-8') as f:
            await f.write('')

        # Now run the processing logic for these URLs
        await main()

        # Check again for failed URLs and continue the loop if they exist


async def main():
    """
    The main coroutine that orchestrates reading URLs, checking them,
    and writing matched URLs to the output file.
    """

    # Parse command-line arguments
    args = parse_arguments()

    # Overwrite the configuration constants with the values from the arguments
    global CONCURRENT_REQUESTS, BATCH_WRITE_INTERVAL, RETRIES, BACKOFF_FACTOR
    CONCURRENT_REQUESTS = args.concurrent_requests
    BATCH_WRITE_INTERVAL = args.batch_write_interval
    RETRIES = args.retries
    BACKOFF_FACTOR = args.backoff_factor

    # Log the values being used
    print(f"CONCURRENT_REQUESTS: {CONCURRENT_REQUESTS}")
    print(f"BATCH_WRITE_INTERVAL: {BATCH_WRITE_INTERVAL}")
    print(f"RETRIES: {RETRIES}")
    print(f"BACKOFF_FACTOR: {BACKOFF_FACTOR}")

    # Check if the input file exists
    if not os.path.isfile(INPUT_FILE):
        logging.error(f"Input file '{INPUT_FILE}' does not exist.")
        print(f"Input file '{INPUT_FILE}' does not exist.")
        return

    # Read and validate URLs from the input file
    async with aiofiles.open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw_urls = [line.strip() for line in await f.readlines() if line.strip()]

    # Validate URLs
    urls = [url for url in raw_urls if is_valid_url(url)]
    invalid_urls = set(raw_urls) - set(urls)
    if invalid_urls:
        logging.warning(f"Found {len(invalid_urls)} invalid URLs. They will be skipped.")
        # Optionally, write invalid URLs to a separate file
        async with aiofiles.open("invalid_urls.txt", "w", encoding='utf-8') as invalid_file:
            await invalid_file.write('\n'.join(invalid_urls) + '\n')

    if not urls:
        logging.error(f"No valid URLs found in '{INPUT_FILE}'. Exiting.")
        return

    logging.info(f"Total URLs to process: {len(urls)}")

    # Initialize concurrency controls
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    lock = asyncio.Lock()
    fail_lock = asyncio.Lock()
    completed_lock = asyncio.Lock()
    matched_urls = []

    # Read existing failed URLs from 'FAILED_FILE' if it exists
    failed_urls = set()
    if os.path.isfile(FAILED_FILE):
        async with aiofiles.open(FAILED_FILE, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
            failed_urls.update(line.strip() for line in lines if line.strip())

    failed_urls_start_len = len(failed_urls)

    completed_urls = set()
    if os.path.isfile(COMPLETED_FILE):
        async with aiofiles.open(COMPLETED_FILE, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
            completed_urls.update(line.strip() for line in lines if line.strip())

    # Open the output file in write mode (append)
    async with aiofiles.open(OUTPUT_FILE, 'a', encoding='utf-8') as file_handle:
        # Start the batch writer task
        writer_task = asyncio.create_task(write_batches(file_handle, matched_urls, lock))

        # Initialize the HTTP client with HTTP/2 support and high connection limits
        async with httpx.AsyncClient(http2=True, limits=httpx.Limits(max_connections=CONCURRENT_REQUESTS)) as client:
            # Create tasks for checking each URL
            tasks = [
                asyncio.create_task(
                    check_gramplay(client, url, semaphore,
                                   matched_urls, lock,
                                   failed_urls, fail_lock,
                                   completed_urls, completed_lock))
                for url in urls
            ]

            # Use tqdm for progress tracking
            for f_task in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing URLs"):
                await f_task

        # Allow some time for the last batch to be written
        await asyncio.sleep(BATCH_WRITE_INTERVAL + 1)
        # Cancel the writer task as it's an infinite loop
        writer_task.cancel()
        try:
            await writer_task
        except asyncio.CancelledError:
            pass

    # Verification
    total_urls = len(urls)
    failed_urls_end_len = len(failed_urls)
    failed_urls_difference = failed_urls_start_len - failed_urls_end_len
    processed_urls = total_urls - failed_urls_difference
    logging.info(f"Total URLs: {total_urls}")
    logging.info(f"Successfully processed URLs: {processed_urls}")
    logging.info(f"Failed URLs: {len(failed_urls)}")

    if failed_urls:
        # Write failed URLs to a separate file for later retry
        async with aiofiles.open(FAILED_FILE, "w", encoding='utf-8') as fail_file:
            await fail_file.write('\n'.join(sorted(failed_urls)) + '\n')
        logging.info(f"Failed URLs have been written to '{FAILED_FILE}'.")

    if completed_urls:
        # Write completed URLs to a separate file
        async with aiofiles.open(COMPLETED_FILE, 'w', encoding='utf-8') as completed_file:
            await completed_file.write('\n'.join(sorted(completed_urls)) + '\n')
        logging.info(f"Completed URLs have been written to '{COMPLETED_FILE}'.")

    print(f"\nProcessing complete. Matched URLs have been written to '{OUTPUT_FILE}'.")
    print(f"Check 'process.log' for detailed logs.")


if __name__ == '__main__':
    try:
        asyncio.run(process_urls())
    except KeyboardInterrupt:
        logging.info("Process interrupted by user.")
