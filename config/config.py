# config.py

import os

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
INPUT_DIR = os.path.join(DATA_DIR, 'input')
OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# File paths
INPUT_FILE = os.path.join(INPUT_DIR, 'output_urls.txt')
FAILED_FILE = os.path.join(OUTPUT_DIR, 'failed_urls.txt')
MATCHED_FILE = os.path.join(OUTPUT_DIR, 'matched_urls.txt')
INVALID_FILE = os.path.join(OUTPUT_DIR, 'invalid_urls.txt')
LOG_FILE = os.path.join(LOG_DIR, 'process.log')
