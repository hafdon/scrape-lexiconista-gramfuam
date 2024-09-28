import asyncio
import logging

from config.config import MATCHED_FILE

async def write_batches(
        file_handle,
        matched_urls: list,
        lock: asyncio.Lock,
        batch_write_interval: int
):
    """
    Periodically writes matched URLs to the output file in batches.

    Args:
        file_handle (aiofiles.AsyncBufferedWriter): The file handle for writing.
        matched_urls (list): Shared list containing matched URLs.
        lock (asyncio.Lock): Lock to manage access to matched_urls.
    """
    while True:
        await asyncio.sleep(batch_write_interval)
        async with lock:
            if matched_urls:
                batch = matched_urls.copy()
                matched_urls.clear()
                await file_handle.write('\n'.join(batch) + '\n')
                logging.debug(f"Wrote a batch of {len(batch)} URLs to {MATCHED_FILE}")
