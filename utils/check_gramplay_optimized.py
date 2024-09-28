import asyncio
import logging

import httpx
import uvloop

from utils.fetch_util import fetch_with_retries
from utils.logging_util import create_logger

# Set uvloop as the event loop policy for better performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Configure logging
logger = create_logger()

async def check_gramplay(
        client: httpx.AsyncClient,
        url: str,
        semaphore: asyncio.Semaphore,
        matched_urls: list,
        lock: asyncio.Lock,
        failed_urls: set,
        fail_lock: asyncio.Lock,
        completed_urls: set,
        completed_lock: asyncio.Lock,
        retries: int,
        backoff_factor: float
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
        content = await fetch_with_retries(client, url, retries, backoff_factor)
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


