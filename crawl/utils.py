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
    """Extract price and currency from text - optimized for Vietnamese VND format"""
    if not text:
        return 0.0, ""

    # Enhanced VND patterns for Vietnamese Agoda pages
    vnd_patterns = [
        r'([\d,\.]+)\s*₫',  # 2.896.188 ₫
        r'([\d,\.]+)\s*VND',  # 2896188 VND
        r'₫\s*([\d,\.]+)',  # ₫ 2.896.188
        r'VND\s*([\d,\.]+)',  # VND 2896188
        r'([\d,\.]+)\s*đ',  # 2.896.188 đ
        r'đ\s*([\d,\.]+)',  # đ 2.896.188
    ]

    # First try VND patterns specifically
    for pattern in vnd_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                # Handle Vietnamese number format: 2.896.188
                price_str = match.strip()

                # Remove commas first
                price_str = price_str.replace(',', '')

                # Handle dots as thousands separators in Vietnamese format
                if '.' in price_str:
                    # Count dots to determine if they're thousands separators
                    dot_count = price_str.count('.')
                    if dot_count >= 1:
                        # Check if last part after dot has 3 digits (thousands separator)
                        parts = price_str.split('.')
                        if len(parts[-1]) == 3 and all(len(part) <= 3 for part in parts[1:]):
                            # This is thousands separator format: 2.896.188
                            price_str = ''.join(parts)
                        else:
                            # This might be decimal: 2896.50
                            price_str = price_str  # Keep as is

                price = float(price_str)
                if price > 1000:  # Reasonable VND price
                    return price, "VND"
            except ValueError:
                continue

    # Fallback to other currencies
    currency_patterns = {
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

    for currency, pattern in currency_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            price_matches = re.findall(r'[\d,\.]+', text)
            for price_match in price_matches:
                try:
                    price_str = price_match.replace(',', '')
                    price = float(price_str)
                    if price > 0:
                        return price, currency
                except ValueError:
                    continue

    # Final fallback: extract any number and guess currency
    price_matches = re.findall(r'[\d,\.]+', text)
    for price_match in price_matches:
        try:
            price_str = price_match.replace(',', '')

            # Handle Vietnamese dot format
            if '.' in price_str:
                parts = price_str.split('.')
                if len(parts) >= 2 and all(len(part) <= 3 for part in parts[1:]):
                    price_str = ''.join(parts)

            price = float(price_str)
            if price > 10000:  # Likely VND
                return price, "VND"
            elif price > 0:
                return price, "UNKNOWN"
        except ValueError:
            continue

    return 0.0, ""

def format_vnd_price(price: float) -> str:
    """Format price in Vietnamese VND format with dots as thousands separators"""
    if price <= 0:
        return "0 ₫"

    # Convert to integer for VND
    price_int = int(price)

    # Format with dots as thousands separators
    price_str = f"{price_int:,}".replace(',', '.')

    return f"{price_str} ₫"

def build_agoda_search_url(hotel_url: str, check_in: date, check_out: date,
                          adults: int = 2, children: int = 0, rooms: int = 1) -> str:
    """Build Agoda search URL with specific dates using the provided URL pattern"""
    try:
        # Parse the original URL
        parsed = urlparse(hotel_url)

        # Parse existing query parameters
        existing_params = parse_qs(parsed.query)

        # Convert to single values (parse_qs returns lists)
        query_params = {}
        for key, value_list in existing_params.items():
            if value_list:
                query_params[key] = value_list[0]

        # Update/add the date parameters
        query_params['checkIn'] = check_in.strftime('%Y-%m-%d')
        query_params['checkOut'] = check_out.strftime('%Y-%m-%d')

        # Update the checkin parameter if it exists (for the specific format you provided)
        if 'checkin' in query_params:
            query_params['checkin'] = check_in.strftime('%Y-%m-%d')

        # Ensure other important parameters
        query_params.update({
            'adults': str(adults),
            'children': str(children),
            'rooms': str(rooms),
            'currencyCode': 'VND',  # Force VND currency
            'finalPriceView': '1',
            'isShowMobileAppPrice': 'false'
        })

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
