"""
Configuration settings for Agoda scraper
"""
import os
from datetime import datetime, timedelta

# Base configuration
BASE_URL = "https://www.agoda.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]

# Scraping settings
DELAY_BETWEEN_REQUESTS = 3  # seconds
MAX_RETRIES = 3
TIMEOUT = 30  # seconds
IMPLICIT_WAIT = 10  # seconds

# Date settings
TARGET_DATES_OFFSET = [0, 7, 15]  # D, D+7, D+15

# Data storage settings
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
OUTPUT_FORMAT = "json"  # json, csv, both

# Selenium settings
HEADLESS = True
WINDOW_SIZE = (1920, 1080)

# Chrome options
CHROME_OPTIONS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-extensions",
    "--disable-plugins",
    "--disable-images",  # Speed up loading
    "--disable-javascript",  # Only if site works without JS
]

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Rate limiting
REQUESTS_PER_MINUTE = 10
CONCURRENT_REQUESTS = 1

def get_target_dates():
    """Get target dates for scraping (D, D+7, D+15)"""
    today = datetime.now().date()
    return [today + timedelta(days=offset) for offset in TARGET_DATES_OFFSET]

def get_output_filename(hotel_name="", timestamp=None):
    """Generate output filename with timestamp"""
    if timestamp is None:
        timestamp = datetime.now()
    
    date_str = timestamp.strftime("%Y%m%d_%H%M%S")
    hotel_part = f"_{hotel_name.replace(' ', '_').lower()}" if hotel_name else ""
    
    return f"agoda_pricing{hotel_part}_{date_str}"
