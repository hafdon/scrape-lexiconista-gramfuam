from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import requests
import os

# Specify the path to your ChromeDriver
service = Service('/Users/starkat/chromedriver')

# Set up the Selenium WebDriver with the Service object
driver = webdriver.Chrome(service=service)

# Load the webpage
url = "http://breistest.lexiconista.com/CanC-verb/"
driver.get(url)

# Get the page source after dynamic content loads
page_source = driver.page_source

# Parse the loaded page
soup = BeautifulSoup(page_source, "html.parser")

# Close the Selenium driver
driver.quit()

# Find all the audio file links
audio_links = []
for link in soup.find_all('a', href=True):
    if link['href'].endswith('.mp3'):
        audio_links.append(url + link['href'])

# Create a folder to save audio files
os.makedirs('../audio_files', exist_ok=True)

# Download and save the audio files
for audio_link in audio_links:
    audio_data = requests.get(audio_link).content
    file_name = audio_link.split('/')[-1]
    with open(f'audio_files/{file_name}', 'wb') as audio_file:
        audio_file.write(audio_data)
        print(f"Downloaded: {file_name}")

print("All audio files downloaded.")
