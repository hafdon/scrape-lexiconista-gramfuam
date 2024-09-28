import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import logging
import random

class AsyncScraper:
    def __init__(self, start_url, matched_urls_file='matched_urls.txt', processed_urls_file='processed_urls.txt'):
        self.start_url = start_url
        self.matched_urls_file = matched_urls_file
        self.processed_urls_file = processed_urls_file

        # Sets to keep track of URLs
        self.visited_urls = set()
        self.matched_urls = set()
        self.processed_urls = set()

        # Asyncio Queue
        self.url_queue = asyncio.Queue()

        # Locks for thread-safe operations
        self.visited_lock = asyncio.Lock()
        self.matched_lock = asyncio.Lock()
        self.processed_lock = asyncio.Lock()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(10)  # Reduced from 100 to 10

        # Progress tracking
        self.total_urls_discovered = 0
        self.total_urls_processed = 0

        # Setup logging
        logging.basicConfig(filename='scrape.log', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    async def load_processed_urls(self):
        # Load matched URLs if the file exists
        if os.path.exists(self.matched_urls_file):
            async with aiofiles.open(self.matched_urls_file, 'r', encoding='utf-8') as f:
                async for line in f:
                    url = line.strip()
                    if url:
                        self.matched_urls.add(url)
            logging.info(f"Loaded {len(self.matched_urls)} matched URLs from {self.matched_urls_file}")

        # Load processed URLs if the file exists
        if os.path.exists(self.processed_urls_file):
            async with aiofiles.open(self.processed_urls_file, 'r', encoding='utf-8') as f:
                async for line in f:
                    url = line.strip()
                    if url:
                        self.processed_urls.add(url)
            # logging.info(f"Loaded {len(self.processed_urls)} processed URLs from {self.processed_urls_file}")

    async def save_processed_url(self, url):
        async with self.processed_lock:
            if url not in self.processed_urls:
                self.processed_urls.add(url)
                async with aiofiles.open(self.processed_urls_file, 'a', encoding='utf-8') as f:
                    await f.write(url + '\n')
                self.total_urls_processed += 1

    async def save_matched_url(self, url):
        async with self.matched_lock:
            if url not in self.matched_urls:
                self.matched_urls.add(url)
                async with aiofiles.open(self.matched_urls_file, 'a', encoding='utf-8') as f:
                    await f.write(url + '\n')

    async def process_url(self, session, url):
        logging.info(f"Processing URL: {url}")
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                async with self.semaphore:
                    async with session.get(url, timeout=30) as response:
                        response.raise_for_status()
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        # Check for 'gramPlay' instances
                        gramplay_elements = soup.find_all(onclick=lambda x: x and 'gramPlay' in x)
                        if gramplay_elements:
                            await self.save_matched_url(url)
                            logging.info(f"Found gramPlay on {url}")

                        # Mark the URL as processed
                        await self.save_processed_url(url)

                        # Discover new URLs from the navigation and add them to the queue
                        await self.discover_urls(soup, url)

                        # Random delay between requests
                        await asyncio.sleep(random.uniform(0.5, 1.5))

                        break  # Success, exit the retry loop

            except asyncio.TimeoutError:
                logging.warning(f"TimeoutError on {url} (Attempt {attempt}/{max_retries})")
                if attempt == max_retries:
                    logging.error(f"Failed to process {url} after {max_retries} attempts due to timeout.")
                    await self.save_processed_url(url)  # Mark as processed to avoid reprocessing
            except Exception as e:
                logging.error(f"Error processing URL {url} (Attempt {attempt}/{max_retries}): {e}", exc_info=True)
                if attempt == max_retries:
                    await self.save_processed_url(url)  # Mark as processed to avoid reprocessing
            else:
                # No exceptions, break the retry loop
                break

    async def worker(self, session):
        while True:
            try:
                url = await self.url_queue.get()
                if url in self.processed_urls:
                    self.url_queue.task_done()
                    continue
                await self.process_url(session, url)
                self.url_queue.task_done()

                # Report progress every 100 URLs
                if self.total_urls_processed % 100 == 0 and self.total_urls_processed > 0:
                    print(f"Processed {self.total_urls_processed} URLs. Discovered {self.total_urls_discovered} URLs.")

            except Exception as e:
                logging.error(f"Unexpected error: {e}", exc_info=True)
                self.url_queue.task_done()

    async def discover_urls(self, soup, base_url):
        abc_div = soup.find('div', class_='abc')
        if not abc_div:
            logging.warning(f"No navigation found on {base_url}.")
            return

        links = abc_div.find_all('a')
        for link in links:
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                async with self.visited_lock:
                    if full_url not in self.visited_urls and full_url not in self.processed_urls:
                        self.visited_urls.add(full_url)
                        self.total_urls_discovered += 1
                        await self.url_queue.put(full_url)
                        logging.debug(f"Discovered and queued URL: {full_url}")
            else:
                logging.debug("Found a link without href attribute.")

    async def scrape(self):
        # Load processed and matched URLs
        await self.load_processed_urls()

        # Start with the initial URL
        async with self.visited_lock:
            if self.start_url not in self.visited_urls and self.start_url not in self.processed_urls:
                self.visited_urls.add(self.start_url)
                self.total_urls_discovered += 1
                await self.url_queue.put(self.start_url)

        connector = aiohttp.TCPConnector(limit=20)  # Limit the number of connections
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            num_workers = 20  # Reduced from 100 to 20
            for _ in range(num_workers):
                task = asyncio.create_task(self.worker(session))
                tasks.append(task)

            # Wait until the queue is fully processed
            await self.url_queue.join()

            # Cancel all worker tasks
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        logging.info("Scraping completed.")

        print(f"\nScraping completed. Processed {self.total_urls_processed} URLs.")
        print("\nURLs that matched the criteria:")
        for url in self.matched_urls:
            print(url)

if __name__ == "__main__":
    scraper = AsyncScraper(start_url="http://breistest.lexiconista.com/en/gram/ab")
    asyncio.run(scraper.scrape())
