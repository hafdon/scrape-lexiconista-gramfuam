import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import logging
import random
import sys

class AsyncScraper:
    def __init__(self, start_url, output_file='alpha_urls.txt'):
        self.start_url = start_url
        self.output_file = output_file
        uri = aiohttp.helpers.URL(start_url)
        self.base_url = f"{uri.scheme}://{uri.host}"
        if uri.port:
            self.base_url += f":{uri.port}"

        # Sets to keep track of URLs
        self.visited_pages = set()
        self.extracted_urls = set()

        # Asyncio Queue for pages to visit
        self.page_queue = asyncio.Queue()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        # Progress tracking
        self.total_pages_discovered = 0
        self.total_pages_processed = 0
        self.lock = asyncio.Lock()  # To protect shared resources

        # Setup logging
        logging.basicConfig(
            filename='scraper.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    async def load_processed_urls(self):
        # Load matched URLs if the file exists
        if os.path.exists(self.output_file):
            async with aiofiles.open(self.output_file, 'r', encoding='utf-8') as f:
                async for line in f:
                    url = line.strip()
                    if url:
                        self.extracted_urls.add(url)
            logging.info(f"Loaded {len(self.extracted_urls)} URLs from {self.output_file}")

    async def save_url(self, url):
        """Writes a URL to the output file."""
        async with aiofiles.open(self.output_file, 'a', encoding='utf-8') as f:
            await f.write(url + '\n')

    async def process_url(self, session, url):
        logging.info(f"Processing URL: {url}")
        max_retries = 3
        backoff_factor = 2
        for attempt in range(1, max_retries + 1):
            try:
                async with self.semaphore:
                    async with session.get(url, timeout=30) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')

                            # Extract hrefs from <span class="abcItem"> <a href="..."> tags
                            abc_items = soup.find_all('span', class_='abcItem')
                            new_urls = []
                            for item in abc_items:
                                a_tag = item.find('a', href=True)
                                if a_tag:
                                    href = a_tag['href']
                                    full_url = urljoin(self.base_url, href)
                                    new_urls.append(full_url)

                            async with self.lock:
                                for new_url in new_urls:
                                    if new_url not in self.extracted_urls:
                                        self.extracted_urls.add(new_url)
                                        await self.save_url(new_url)
                                        logging.debug(f"Extracted URL: {new_url}")
                                        # Optionally, add to queue if you want to process these pages as well
                                        # await self.page_queue.put(new_url)
                                        # self.total_pages_discovered += 1

                            # Discover pagination links (if any) and add to queue
                            # Modify this part based on actual pagination structure
                            pagination_div = soup.find('div', class_='pagination')
                            if pagination_div:
                                next_link = pagination_div.find('a', text='Next')
                                if next_link and 'href' in next_link.attrs:
                                    next_url = urljoin(self.base_url, next_link['href'])
                                    async with self.lock:
                                        if next_url not in self.visited_pages:
                                            self.visited_pages.add(next_url)
                                            await self.page_queue.put(next_url)
                                            self.total_pages_discovered += 1
                                            logging.debug(f"Discovered pagination URL: {next_url}")

                            # Random delay between requests to be polite
                            await asyncio.sleep(random.uniform(0.5, 1.5))

                            # Update progress
                            async with self.lock:
                                self.total_pages_processed += 1
                                if self.total_pages_processed % 100 == 0:
                                    print(f"Processed {self.total_pages_processed} pages. Discovered {self.total_pages_discovered} pages.")

                            break  # Success, exit the retry loop

                        elif response.status == 429:
                            # Too Many Requests
                            logging.warning(f"Received 429 Too Many Requests for {url}. Attempt {attempt}/{max_retries}.")
                            await asyncio.sleep(backoff_factor ** attempt)
                        elif 500 <= response.status < 600:
                            # Server errors
                            logging.warning(f"Server error {response.status} for {url}. Attempt {attempt}/{max_retries}.")
                            await asyncio.sleep(backoff_factor ** attempt)
                        else:
                            # Other HTTP errors
                            logging.error(f"HTTP error {response.status} for {url}. Skipping.")
                            break  # Skip this URL

            except asyncio.TimeoutError:
                logging.warning(f"Timeout while fetching {url}. Attempt {attempt}/{max_retries}.")
                if attempt == max_retries:
                    logging.error(f"Failed to fetch {url} after {max_retries} attempts due to timeout.")
            except aiohttp.ClientError as e:
                logging.error(f"Client error while fetching {url}: {e}. Attempt {attempt}/{max_retries}.")
                if attempt == max_retries:
                    logging.error(f"Failed to fetch {url} after {max_retries} attempts due to client error.")
            except Exception as e:
                logging.error(f"Unexpected error while fetching {url}: {e}. Attempt {attempt}/{max_retries}.")
                if attempt == max_retries:
                    logging.error(f"Failed to fetch {url} after {max_retries} attempts due to unexpected error.")

    async def worker(self, session):
        """Worker that processes pages from the queue."""
        while True:
            try:
                current_url = await self.page_queue.get()
                logging.info(f"Worker started processing: {current_url}")
                await self.process_url(session, current_url)
                self.page_queue.task_done()
            except Exception as e:
                logging.error(f"Unexpected error in worker: {e}", exc_info=True)
                self.page_queue.task_done()

    async def scrape(self):
        """Main method to start scraping."""
        # Load already processed URLs to avoid duplication
        await self.load_processed_urls()

        # Start with the initial URL
        if self.start_url not in self.visited_pages:
            self.visited_pages.add(self.start_url)
            await self.page_queue.put(self.start_url)
            self.total_pages_discovered += 1

        # Create an aiohttp session with a connector that limits the number of connections
        connector = aiohttp.TCPConnector(limit=20)  # Adjust based on your system and server capacity
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Start worker tasks
            tasks = []
            num_workers = 10  # Number of concurrent workers
            for _ in range(num_workers):
                task = asyncio.create_task(self.worker(session))
                tasks.append(task)

            # Wait until the queue is fully processed
            await self.page_queue.join()

            # Cancel worker tasks
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        print(f"Scraping completed. Processed {self.total_pages_processed} pages.")
        print(f"Total URLs extracted: {len(self.extracted_urls)}")
        logging.info("Scraping completed successfully.")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 alpha_scraper.py <start_url>")
        sys.exit(1)
    start_url = sys.argv[1]
    scraper = AsyncScraper(start_url=start_url)
    asyncio.run(scraper.scrape())

if __name__ == "__main__":
    main()
