import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import threading
from queue import Queue
import os
import time
import random
import logging

def collect_urls(start_url):
    all_urls = []
    visited_urls = set()
    current_url = start_url

    while current_url:
        if current_url in visited_urls:
            break
        visited_urls.add(current_url)
        logging.info(f"Collecting URL: {current_url}")
        try:
            response = requests.get(current_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            all_urls.append(current_url)

            # Find the current page link
            abc_div = soup.find('div', class_='abc')
            if not abc_div:
                logging.warning("No navigation found, stopping.")
                break

            links = abc_div.find_all('a')
            current_index = None

            # Find the index of the current page
            for i, link in enumerate(links):
                if 'class' in link.attrs and 'current' in link['class']:
                    current_index = i
                    break

            # Get the next link
            if current_index is not None and current_index + 1 < len(links):
                next_link = links[current_index + 1]
                next_href = next_link.get('href')
                if next_href:
                    current_url = urljoin(current_url, next_href)
                else:
                    logging.warning("Next link has no href, stopping.")
                    break
            else:
                logging.info("No next page, stopping.")
                break
        except requests.exceptions.RequestException as e:
            logging.error(f"Error collecting URL {current_url}: {e}")
            break  # Decide whether to continue or break
        # Politeness policy: Delay between requests
        time.sleep(random.uniform(1, 2))  # Random delay between 1 and 2 seconds
    return all_urls

def process_url(url, matched_urls, matched_urls_lock, processed_urls, processed_urls_lock, matched_urls_file, processed_urls_file, thread_control):
    with processed_urls_lock:
        if url in processed_urls:
            return
    logging.info(f"Processing URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Check for 'gramPlay' instances
        gramplay_elements = soup.find_all(onclick=lambda x: x and 'gramPlay' in x)
        if gramplay_elements:
            with matched_urls_lock:
                if url not in matched_urls:
                    logging.info(f"Found gramPlay on {url}")
                    matched_urls.add(url)
                    with open(matched_urls_file, 'a', encoding='utf-8') as f:
                        f.write(url + '\n')
        # Mark the URL as processed
        with processed_urls_lock:
            processed_urls.add(url)
            with open(processed_urls_file, 'a', encoding='utf-8') as f:
                f.write(url + '\n')

        # Update thread control
        with thread_control['lock']:
            thread_control['successes'] += 1

    except requests.exceptions.RequestException as e:
        logging.error(f"Error processing URL {url}: {e}")
        # Update thread control
        with thread_control['lock']:
            thread_control['errors'] += 1
    finally:
        # Politeness policy: Delay between requests
        time.sleep(random.uniform(1, 2))  # Random delay between 1 and 2 seconds

def adjust_thread_count(thread_control):
    # Adjust threads based on error rate
    with thread_control['lock']:
        total = thread_control['successes'] + thread_control['errors']
        if total == 0:
            return  # Not enough data to adjust
        error_rate = thread_control['errors'] / total

    # Adjust thread count based on error rate thresholds
    if error_rate > 0.5 and thread_control['num_threads'] > 1:
        # High error rate, reduce threads
        with thread_control['lock']:
            thread_control['num_threads'] -= 1
            logging.info(f"Reducing thread count to {thread_control['num_threads']} due to high error rate.")
    elif error_rate < 0.1 and thread_control['num_threads'] < thread_control['max_threads']:
        # Low error rate, increase threads
        with thread_control['lock']:
            thread_control['num_threads'] += 1
            logging.info(f"Increasing thread count to {thread_control['num_threads']} due to low error rate.")

def scrape_urls(start_url, matched_urls_file='matched_urls.txt', processed_urls_file='processed_urls.txt'):
    # Setup logging
    logging.basicConfig(filename='scrape.log', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    # Load matched URLs if the file exists to avoid duplicates
    matched_urls = set()
    if os.path.exists(matched_urls_file):
        with open(matched_urls_file, 'r', encoding='utf-8') as f:
            matched_urls = set(line.strip() for line in f if line.strip())
        logging.info(f"Loaded {len(matched_urls)} matched URLs from {matched_urls_file}")

    # Load processed URLs to avoid reprocessing
    processed_urls = set()
    if os.path.exists(processed_urls_file):
        with open(processed_urls_file, 'r', encoding='utf-8') as f:
            processed_urls = set(line.strip() for line in f if line.strip())
        logging.info(f"Loaded {len(processed_urls)} processed URLs from {processed_urls_file}")

    # Collect all URLs
    if os.path.exists('all_urls.txt'):
        with open('all_urls.txt', 'r', encoding='utf-8') as f:
            all_urls = [line.strip() for line in f if line.strip()]
        logging.info(f"Loaded {len(all_urls)} URLs from all_urls.txt")
    else:
        all_urls = collect_urls(start_url)
        with open('all_urls.txt', 'w', encoding='utf-8') as f:
            for url in all_urls:
                f.write(url + '\n')
        logging.info(f"Collected {len(all_urls)} URLs")

    # Use threading to process URLs
    matched_urls_lock = threading.Lock()
    processed_urls_lock = threading.Lock()
    thread_control = {
        'num_threads': 5,  # Starting number of threads
        'max_threads': 10,  # Maximum number of threads
        'successes': 0,
        'errors': 0,
        'lock': threading.Lock()
    }
    threads = []

    url_queue = Queue()

    for url in all_urls:
        if url not in processed_urls:
            url_queue.put(url)
            logging.debug(f"Added URL to queue: {url}")
        else:
            logging.debug(f"URL already processed: {url}")

    def worker():
        while True:
            try:
                url = url_queue.get_nowait()
                logging.debug(f"Thread {threading.current_thread().name} processing URL: {url}")
            except:
                logging.debug(f"Thread {threading.current_thread().name} found queue empty.")
                break
            process_url(url, matched_urls, matched_urls_lock, processed_urls, processed_urls_lock,
                        matched_urls_file, processed_urls_file, thread_control)
            url_queue.task_done()
            adjust_thread_count(thread_control)

    for i in range(thread_control['num_threads']):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Block until all tasks are done
    url_queue.join()

    # Stop workers
    for t in threads:
        t.join()

    logging.info("Scraping completed.")

    print("\nURLs that matched the criteria:")
    for url in matched_urls:
        print(url)

if __name__ == "__main__":
    start_url = "http://breistest.lexiconista.com/en/gram/bia"
    scrape_urls(start_url)
