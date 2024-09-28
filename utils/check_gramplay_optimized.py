import asyncio
import logging
from urllib.parse import urlparse

import httpx
import uvloop

from utils.logging_util import create_logger

# Set uvloop as the event loop policy for better performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from config import OUTPUT_FILE

# Configuration Constants
CONCURRENT_REQUESTS = 400  # Adjust based on your system and target servers
BATCH_WRITE_INTERVAL = 5  # Seconds between batch writes
RETRIES = 3  # Number of retry attempts for failed requests
BACKOFF_FACTOR = 12  # Factor for exponential backoff

# Configure logging
logger = create_logger()


def is_valid_url(url: str) -> bool:
    """
    Validates the URL format.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


async def fetch_with_retries(client: httpx.AsyncClient, url: str, retries: int = 3, backoff_factor: float = 0.5) -> str:
    """
    Fetches the content of a URL with retry logic.

    Args:
        client (httpx.AsyncClient): The HTTP client to use for fetching.
        url (str): The URL to fetch.
        retries (int): Number of retry attempts.
        backoff_factor (float): Factor for exponential backoff.

    Returns:
        str: The text content of the response if successful; otherwise, None.
    """
    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.text
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logging.warning(f"Attempt {attempt} - Error fetching {url}: {e}")
            if attempt < retries:
                wait_time = backoff_factor * (2 ** (attempt - 1))
                logging.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
    logging.error(f"Failed to fetch {url} after {retries} attempts.")
    return None


async def check_gramplay(
        client: httpx.AsyncClient,
        url: str,
        semaphore: asyncio.Semaphore,
        matched_urls: list,
        lock: asyncio.Lock,
        failed_urls: set,
        fail_lock: asyncio.Lock,
        completed_urls: set,
        completed_lock: asyncio.Lock
):
    """
    Checks if the string 'gramPlay' exists in the content of the URL.
    If found, appends the URL to the matched_urls list.
    If fetching fails after retries, adds the URL to the failed_urls set.
    If fetching succeeds, adds the URL to the completed_urls set

    Args:
        client (httpx.AsyncClient): The HTTP client to use for fetching.
        url (str): The URL to check.
        semaphore (asyncio.Semaphore): Semaphore to limit concurrency.
        matched_urls (list): Shared list to store matched URLs.
        lock (asyncio.Lock): Lock to manage access to matched_urls.
        failed_urls (set): Shared set to store failed URLs.
        fail_lock (asyncio.Lock): Lock to manage access to failed_urls.
    """
    async with semaphore:
        content = await fetch_with_retries(client, url, retries=RETRIES, backoff_factor=BACKOFF_FACTOR)
        async with completed_lock:
            completed_urls.add(url)
        if content:
            if "gramPlay" in content:
                logging.info(f"'gramPlay' found in {url}")
                async with lock:
                    matched_urls.append(url)
            else:
                logging.debug(f"'gramPlay' not found in {url}")
        else:
            logging.error(f"Failed to process {url}")
            async with fail_lock:
                failed_urls.add(url)
            async with completed_lock:
                # remove failed url from list of completed urls
                completed_urls.remove(url)


async def write_batches(
        file_handle,
        matched_urls: list,
        lock: asyncio.Lock
):
    """
    Periodically writes matched URLs to the output file in batches.

    Args:
        file_handle (aiofiles.AsyncBufferedWriter): The file handle for writing.
        matched_urls (list): Shared list containing matched URLs.
        lock (asyncio.Lock): Lock to manage access to matched_urls.
    """
    while True:
        await asyncio.sleep(BATCH_WRITE_INTERVAL)
        async with lock:
            if matched_urls:
                batch = matched_urls.copy()
                matched_urls.clear()
                await file_handle.write('\n'.join(batch) + '\n')
                logging.debug(f"Wrote a batch of {len(batch)} URLs to {OUTPUT_FILE}")
