import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import threading
import queue  # Import the queue module
import os
import time
import random
import logging

class Scraper:
    def __init__(self, start_url, matched_urls_file='matched_urls.txt', processed_urls_file='processed_urls.txt'):
        self.start_url = start_url
        self.matched_urls_file = matched_urls_file
        self.processed_urls_file = processed_urls_file
        self.visited_urls = set()
        self.matched_urls = set()
        self.processed_urls = set()
        self.url_queue = queue.Queue()  # Use queue.Queue()
        self.lock = threading.Lock() # Protect shared data
        self.thread_control = {
            'num_threads': 5,  # Starting number of threads
            'max_threads': 10,  # Maximum number of threads
            'successes': 0,
            'errors': 0,
            'lock': threading.Lock()
        }
        # Setup logging
        logging.basicConfig(filename='scrape.log', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def load_processed_urls(self):
        # Load matched URLs if the file exists to avoid duplicates
        if os.path.exists(self.matched_urls_file):
            with open(self.matched_urls_file, 'r', encoding='utf-8') as f:
                self.matched_urls = set(line.strip() for line in f if line.strip())
            logging.info(f"Loaded {len(self.matched_urls)} matched URLs from {self.matched_urls_file}")

        # Load processed URLs to avoid reprocessing
        if os.path.exists(self.processed_urls_file):
            with open(self.processed_urls_file, 'r', encoding='utf-8') as f:
                self.processed_urls = set(line.strip() for line in f if line.strip())
            # This log could get very long:
            # logging.info(f"Loaded {len(self.processed_urls)} processed URLs from {self.processed_urls_file}")

    def save_processed_url(self, url):
        with self.lock:
            self.processed_urls.add(url)
            with open(self.processed_urls_file, 'a', encoding='utf-8') as f:
                f.write(url + '\n')

    def save_matched_url(self, url):
        with self.lock:
            self.matched_urls.add(url)
            with open(self.matched_urls_file, 'a', encoding='utf-8') as f:
                f.write(url + '\n')

    def process_url(self, url):
        logging.info(f"Processing URL: {url}")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Check for 'gramPlay' instances
            gramplay_elements = soup.find_all(onclick=lambda x: x and 'gramPlay' in x)
            if gramplay_elements:
                if url not in self.matched_urls:
                    logging.info(f"Found gramPlay on {url}")
                    self.save_matched_url(url)

            # Mark the URL as processed
            self.save_processed_url(url)

            # Update thread control
            with self.thread_control['lock']:
                self.thread_control['successes'] += 1

            # Discover new URLs from the navigation and add them to the queue
            self.discover_urls(soup, url)

        except requests.exceptions.RequestException as e:
            logging.error(f"Error processing URL {url}: {e}")
            # Update thread control
            with self.thread_control['lock']:
                self.thread_control['errors'] += 1
        finally:
            # Politeness policy: Delay between requests
            time.sleep(random.uniform(1, 2))  # Random delay between 1 and 2 seconds

    def worker(self):
        while True:
            try:
                url = self.url_queue.get_nowait()
                if url in self.processed_urls:
                    self.url_queue.task_done()
                    continue
                self.process_url(url)
                self.url_queue.task_done()
                self.adjust_thread_count()
            except queue.Empty:
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}", exc_info=True)
                self.url_queue.task_done()

    def adjust_thread_count(self):
        # Adjust threads based on error rate
        with self.thread_control['lock']:
            total = self.thread_control['successes'] + self.thread_control['errors']
            if total == 0:
                return  # Not enough data to adjust
            error_rate = self.thread_control['errors'] / total

        # Adjust thread count based on error rate thresholds
        if error_rate > 0.5 and self.thread_control['num_threads'] > 1:
            # High error rate, reduce threads
            with self.thread_control['lock']:
                self.thread_control['num_threads'] -= 1
                logging.info(f"Reducing thread count to {self.thread_control['num_threads']} due to high error rate.")
        elif error_rate < 0.1 and self.thread_control['num_threads'] < self.thread_control['max_threads']:
            # Low error rate, increase threads
            with self.thread_control['lock']:
                self.thread_control['num_threads'] += 1
                logging.info(f"Increasing thread count to {self.thread_control['num_threads']} due to low error rate.")

    def discover_urls(self, soup, base_url):
        abc_div = soup.find('div', class_='abc')
        if not abc_div:
            logging.warning(f"No navigation found on {base_url}.")
            return

        links = abc_div.find_all('a')
        for link in links:
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                with self.lock:
                    if full_url not in self.visited_urls and full_url not in self.processed_urls:
                        self.visited_urls.add(full_url)
                        self.url_queue.put(full_url)
                        logging.debug(f"Discovered and queued URL: {full_url}")
            else:
                logging.debug("Found a link without href attribute.")

    def scrape(self):
        self.load_processed_urls()
        # Start with the initial URL
        self.visited_urls.add(self.start_url)
        self.url_queue.put(self.start_url)

        threads = []

        for i in range(self.thread_control['num_threads']):
            t = threading.Thread(target=self.worker, name=f"Thread-{i+1}")
            t.start()
            threads.append(t)

        # Wait until all tasks are done
        self.url_queue.join()

        # Stop workers
        for t in threads:
            t.join()

        logging.info("Scraping completed.")

        print("\nURLs that matched the criteria:")
        for url in self.matched_urls:
            print(url)

if __name__ == "__main__":
    start_url = "http://breistest.lexiconista.com/en/gram/bia"
    scraper = Scraper(start_url)
    scraper.scrape()
