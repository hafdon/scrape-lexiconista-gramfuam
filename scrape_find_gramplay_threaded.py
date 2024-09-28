import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import threading
from queue import Queue
import os

def collect_urls(start_url):
    """
    Collects all URLs from the starting URL by navigating through the pages.

    Args:
        start_url (str): The starting URL to begin the collection.

    Returns:
        list: A list of all collected URLs.
    """
    all_urls = []
    visited_urls = set()
    current_url = start_url

    while current_url:
        if current_url in visited_urls:
            break
        visited_urls.add(current_url)
        print(f"Collecting URL: {current_url}")
        response = requests.get(current_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        all_urls.append(current_url)

        # Find the current page link
        abc_div = soup.find('div', class_='abc')
        if not abc_div:
            print("No navigation found, stopping.")
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
                print(f"Next URL: {current_url}")
            else:
                print("Next link has no href, stopping.")
                break
        else:
            print("No next page, stopping.")
            break
    return all_urls

def process_url(url, matched_urls, matched_urls_lock, processed_urls, processed_urls_lock, matched_urls_file, processed_urls_file):
    with processed_urls_lock:
        if url in processed_urls:
            return
    print(f"Processing URL: {url}")
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Check for 'gramPlay' instances
        gramplay_elements = soup.find_all(onclick=lambda x: x and 'gramPlay' in x)
        if gramplay_elements:
            with matched_urls_lock:
                if url not in matched_urls:
                    print(f"Found gramPlay on {url}")
                    matched_urls.add(url)
                    with open(matched_urls_file, 'a', encoding='utf-8') as f:
                        f.write(url + '\n')
        # Mark the URL as processed
        with processed_urls_lock:
            processed_urls.add(url)
            with open(processed_urls_file, 'a', encoding='utf-8') as f:
                f.write(url + '\n')
    except Exception as e:
        print(f"Error processing URL {url}: {e}")

def scrape_urls(start_url, matched_urls_file='matched_urls.txt', processed_urls_file='processed_urls.txt'):
    # Load matched URLs if the file exists to avoid duplicates
    matched_urls = set()
    if os.path.exists(matched_urls_file):
        with open(matched_urls_file, 'r', encoding='utf-8') as f:
            matched_urls = set(line.strip() for line in f if line.strip())

    # Load processed URLs to avoid reprocessing
    processed_urls = set()
    if os.path.exists(processed_urls_file):
        with open(processed_urls_file, 'r', encoding='utf-8') as f:
            processed_urls = set(line.strip() for line in f if line.strip())

    # Collect all URLs
    if os.path.exists('all_urls.txt'):
        with open('all_urls.txt', 'r', encoding='utf-8') as f:
            all_urls = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(all_urls)} URLs from all_urls.txt")
    else:
        all_urls = collect_urls(start_url)
        with open('all_urls.txt', 'w', encoding='utf-8') as f:
            for url in all_urls:
                f.write(url + '\n')
        print(f"Collected {len(all_urls)} URLs")

    # Use threading to process URLs
    matched_urls_lock = threading.Lock()
    processed_urls_lock = threading.Lock()
    threads = []
    num_threads = 10  # Adjust the number of threads as needed

    def worker():
        while True:
            try:
                url = url_queue.get_nowait()
            except:
                break
            process_url(url, matched_urls, matched_urls_lock, processed_urls, processed_urls_lock, matched_urls_file, processed_urls_file)
            url_queue.task_done()

    url_queue = Queue()
    for url in all_urls:
        url_queue.put(url)

    for i in range(num_threads):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Block until all tasks are done
    url_queue.join()

    # Stop workers
    for t in threads:
        t.join()

    print("\nURLs that matched the criteria:")
    for url in matched_urls:
        print(url)

if __name__ == "__main__":
    start_url = "http://breistest.lexiconista.com/en/gram/bí"
    scrape_urls(start_url)
