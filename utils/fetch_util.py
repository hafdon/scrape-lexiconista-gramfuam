import asyncio
import logging

import httpx


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
