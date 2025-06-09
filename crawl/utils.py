"""
Utility functions for Agoda scraper
"""
import time
import random
import logging
import os
import re
from datetime import datetime, date
from typing import List, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import DELAY_BETWEEN_REQUESTS, USER_AGENTS, LOGS_DIR, LOG_LEVEL, LOG_FORMAT

def setup_logging(name: str = "agoda_scraper") -> logging.Logger:
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Create file handler
    log_filename = os.path.join(LOGS_DIR, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

def get_random_user_agent() -> str:
    """Get a random user agent string"""
    return random.choice(USER_AGENTS)

def wait_with_jitter(base_delay: float = DELAY_BETWEEN_REQUESTS):
    """Wait with random jitter to avoid detection"""
    jitter = random.uniform(0.5, 1.5)
    delay = base_delay * jitter
    time.sleep(delay)

def safe_find_element(driver, by, value, timeout=10, multiple=False):
    """Safely find element(s) with timeout"""
    try:
        if multiple:
            wait = WebDriverWait(driver, timeout)
            return wait.until(EC.presence_of_all_elements_located((by, value)))
        else:
            wait = WebDriverWait(driver, timeout)
            return wait.until(EC.presence_of_element_located((by, value)))
    except TimeoutException:
        return [] if multiple else None

def safe_get_text(element, default="") -> str:
    """Safely get text from element"""
    try:
        return element.text.strip() if element else default
    except:
        return default

def safe_get_attribute(element, attribute, default="") -> str:
    """Safely get attribute from element"""
    try:
        return element.get_attribute(attribute) if element else default
    except:
        return default

def extract_price_from_text(text: str) -> tuple[float, str]:
    """Extract price and currency from text"""
    if not text:
        return 0.0, ""

    # Common currency symbols and codes
    currency_patterns = {
        'VND': r'[₫]|VND|VNĐ|đ\s*$|^\s*đ',  # Enhanced VND detection
        'USD': r'[\$]|USD',
        'EUR': r'[€]|EUR',
        'GBP': r'[£]|GBP',
        'THB': r'[฿]|THB',
        'SGD': r'SGD',
        'MYR': r'MYR',
        'JPY': r'[¥]|JPY',
        'KRW': r'[₩]|KRW',
        'CNY': r'[¥]|CNY|RMB'
    }

    # Clean text but preserve currency symbols
    original_text = text
    clean_text = re.sub(r'[,\s]+', '', text)

    # Try to find currency and extract price
    for currency, pattern in currency_patterns.items():
        if re.search(pattern, original_text, re.IGNORECASE):
            # Extract numbers - handle Vietnamese number format
            price_matches = re.findall(r'[\d,\.]+', clean_text)
            for price_match in price_matches:
                try:
                    # Handle different number formats
                    price_str = price_match.replace(',', '')

                    # For VND, numbers are often large (millions)
                    if '.' in price_str and currency == 'VND':
                        # In Vietnamese format, . might be thousands separator
                        parts = price_str.split('.')
                        if len(parts) == 2 and len(parts[1]) == 3:
                            # Likely thousands separator
                            price_str = parts[0] + parts[1]

                    price = float(price_str)
                    if price > 0:
                        return price, currency
                except ValueError:
                    continue

    # Fallback: try to extract any number
    price_matches = re.findall(r'[\d,\.]+', clean_text)
    for price_match in price_matches:
        try:
            price_str = price_match.replace(',', '')
            if '.' in price_str:
                parts = price_str.split('.')
                if len(parts) == 2 and len(parts[1]) == 3:
                    # Likely thousands separator
                    price_str = parts[0] + parts[1]

            price = float(price_str)
            if price > 0:
                # Guess currency based on price range
                if price > 10000:  # Likely VND
                    return price, "VND"
                else:
                    return price, "UNKNOWN"
        except ValueError:
            continue

    return 0.0, ""

def build_agoda_search_url(hotel_url: str, check_in: date, check_out: date, 
                          adults: int = 2, children: int = 0, rooms: int = 1) -> str:
    """Build Agoda search URL with specific dates"""
    try:
        # Parse the original URL
        parsed = urlparse(hotel_url)
        
        # Extract hotel ID from URL if possible
        hotel_id_match = re.search(r'/hotel/([^/]+)', parsed.path)
        if not hotel_id_match:
            # Try alternative patterns
            hotel_id_match = re.search(r'hotelid=(\d+)', parsed.query)
        
        # Build new query parameters
        query_params = {
            'checkIn': check_in.strftime('%Y-%m-%d'),
            'checkOut': check_out.strftime('%Y-%m-%d'),
            'adults': str(adults),
            'children': str(children),
            'rooms': str(rooms),
            'cid': '1844104',  # Common Agoda tracking ID
            'tag': 'f19c4b9c-5d0b-4b8a-9c1a-7b8f9e0d1c2a'  # Sample tracking tag
        }
        
        # Merge with existing query parameters
        existing_params = parse_qs(parsed.query)
        for key, value in existing_params.items():
            if key not in query_params and value:
                query_params[key] = value[0]
        
        # Rebuild URL
        new_query = urlencode(query_params)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        
        return new_url
    
    except Exception as e:
        logging.error(f"Error building Agoda URL: {e}")
        return hotel_url

def validate_url(url: str) -> bool:
    """Validate if URL is a valid Agoda URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.endswith('agoda.com') and parsed.scheme in ['http', 'https']
    except:
        return False

def clean_hotel_name(name: str) -> str:
    """Clean hotel name for filename usage"""
    if not name:
        return "unknown_hotel"
    
    # Remove special characters and replace spaces
    cleaned = re.sub(r'[^\w\s-]', '', name)
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    return cleaned.lower()

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying functions on failure"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        time.sleep(wait_time)
                        continue
                    else:
                        break
            raise last_exception
        return wrapper
    return decorator
