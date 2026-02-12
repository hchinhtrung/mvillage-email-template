"""
🔄 SMART RETRY FOR NA CELLS - AGODA PRICE CRAWLER
Best practices implementation for OTA crawling
"""

import pandas as pd
import random
import time
import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ============================================================
# 📁 CONFIG - RETRY STRATEGY
# ============================================================

# Get script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(SCRIPT_DIR, "hotel_prices_20260212.csv")  # File cần retry
INPUT_CSV = os.path.join(SCRIPT_DIR, "raw.csv")                      # File gốc có URLs
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "hotel_prices_RETRY_" + datetime.now().strftime("%Y%m%d_%H%M") + ".csv")

# AGGRESSIVE STEALTH SETTINGS for retry
NUM_WORKERS = 2              # ⬇️ Giảm workers (ít hơn = stealth hơn)
MAX_RETRIES = 5              # ⬆️ Tăng retries
DELAY_RANGE = (3, 7)         # ⬆️ Tăng delay (3-7s thay vì 1.5-3.5s)
PAGE_TIMEOUT = 30            # ⬆️ Tăng timeout (30s thay vì 20s)
ELEMENT_WAIT = 20            # ⬆️ Wait for elements
RETRY_BACKOFF = 2.0          # Exponential backoff multiplier

# TESTING OPTIONS
TEST_MODE = True             # ✅ Set True để chỉ retry 50 cells đầu (test)
AUTO_START = True            # ✅ Set True để skip confirmation prompt

# ENHANCED STEALTH
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# ============================================================
# 🔧 ENHANCED STEALTH DRIVER
# ============================================================

def create_stealth_driver():
    """Enhanced stealth driver với more anti-detection measures"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    # Random window size
    width = random.randint(1366, 1920)
    height = random.randint(768, 1080)
    options.add_argument(f"--window-size={width},{height}")

    driver = webdriver.Chrome(options=options)

    # Inject stealth scripts
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": random.choice(USER_AGENTS)
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
    driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")

    return driver

# ============================================================
# 🎯 SMART WAIT FOR PRICE ELEMENT
# ============================================================

def wait_for_price_element(driver, wait_time=ELEMENT_WAIT):
    """Wait cho price element với multiple strategies"""
    try:
        # Strategy 1: Wait for specific price element
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-selenium='hotel-rooms-availability-prices']"))
        )
        time.sleep(random.uniform(1, 2))  # Extra wait for JS render
        return True
    except:
        try:
            # Strategy 2: Wait for any price-like element
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'PropertyCardPrice')]"))
            )
            time.sleep(random.uniform(1, 2))
            return True
        except:
            return False

# ============================================================
# 🔄 ENHANCED CRAWL FUNCTION
# ============================================================

def crawl_single_cell_retry(driver, hotel_name, room_type, hotel_url, week_num, retry_attempt=0):
    """Enhanced crawl với smart waiting và verification"""
    try:
        check_in_date = datetime.now() + timedelta(weeks=week_num)
        check_out_date = check_in_date + timedelta(days=1)

        check_in_str = check_in_date.strftime("%Y-%m-%d")
        check_out_str = check_out_date.strftime("%Y-%m-%d")

        # Build URL with explicit dates
        if "checkIn=" not in hotel_url:
            separator = "&" if "?" in hotel_url else "?"
            full_url = f"{hotel_url}{separator}checkIn={check_in_str}&checkOut={check_out_str}&adults=2"
        else:
            import re
            full_url = re.sub(r'checkIn=[\d-]+', f'checkIn={check_in_str}', hotel_url)
            full_url = re.sub(r'checkOut=[\d-]+', f'checkOut={check_out_str}', full_url)

        # Navigate with timeout
        driver.set_page_load_timeout(PAGE_TIMEOUT)
        driver.get(full_url)

        # Random human-like behavior
        time.sleep(random.uniform(2, 4))

        # Scroll slowly like human
        driver.execute_script("window.scrollTo({top: document.body.scrollHeight/3, behavior: 'smooth'})")
        time.sleep(random.uniform(1, 2))

        # Smart wait for price elements
        if not wait_for_price_element(driver):
            print(f"      ⏳ W{week_num}: Price element not loaded within {ELEMENT_WAIT}s")
            return "NA"

        # Try multiple selectors
        selectors = [
            "span[data-selenium='hotel-rooms-availability-prices']",
            "span.PropertyCardPrice__Value",
            "span[data-ppapi='room-price']",
            "div.PriceDisplay span"
        ]

        price_text = None
        for selector in selectors:
            try:
                price_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if price_elements:
                    # Filter room type
                    for elem in price_elements:
                        parent_text = elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MasterRoom') or contains(@class, 'Room')]").text
                        if room_type.lower() in parent_text.lower():
                            price_text = elem.text.strip()
                            break
                    if price_text:
                        break
            except:
                continue

        if price_text and price_text not in ['', 'NA', '--']:
            print(f"      ✅ W{week_num}: {price_text} (retry #{retry_attempt})")
            return price_text
        else:
            print(f"      ❌ W{week_num}: No price found (retry #{retry_attempt})")
            return "NA"

    except Exception as e:
        print(f"      ⚠️  W{week_num}: Error - {str(e)[:50]}")
        return "NA"

# ============================================================
# 📊 IDENTIFY NA CELLS
# ============================================================

def identify_na_cells(result_df, raw_df):
    """Identify all (hotel, week) combinations that need retry"""
    na_cells = []

    for idx, row in result_df.iterrows():
        hotel_name = row['hotel_name']
        room_type = row['room_type']

        # Get URL from raw file
        raw_match = raw_df[
            (raw_df['hotel_name'] == hotel_name) &
            (raw_df['room_type'] == room_type)
        ]

        if raw_match.empty:
            continue

        hotel_url = raw_match.iloc[0]['hotel_url']

        # Check each week
        for week_num in range(1, 7):
            price = row[f'price_w{week_num}']
            if pd.isna(price) or price == 'NA' or price == '':
                na_cells.append({
                    'hotel_name': hotel_name,
                    'room_type': room_type,
                    'hotel_url': hotel_url,
                    'week_num': week_num
                })

    return na_cells

# ============================================================
# 🔄 RETRY WORKER
# ============================================================

def retry_worker(cell_batch, worker_id, results_dict, lock):
    """Worker to retry a batch of NA cells"""
    driver = create_stealth_driver()

    try:
        for cell in cell_batch:
            hotel_name = cell['hotel_name']
            room_type = cell['room_type']
            hotel_url = cell['hotel_url']
            week_num = cell['week_num']

            print(f"  🔄 Worker {worker_id}: {hotel_name[:30]}... W{week_num}")

            # Retry with exponential backoff
            price = "NA"
            for retry in range(MAX_RETRIES):
                if retry > 0:
                    backoff = DELAY_RANGE[0] * (RETRY_BACKOFF ** retry)
                    print(f"      💤 Retry {retry}/{MAX_RETRIES} after {backoff:.1f}s")
                    time.sleep(backoff)

                price = crawl_single_cell_retry(
                    driver, hotel_name, room_type, hotel_url, week_num, retry
                )

                if price != "NA":
                    break

            # Store result
            key = (hotel_name, room_type, week_num)
            with lock:
                results_dict[key] = price

            # Random delay between cells
            time.sleep(random.uniform(*DELAY_RANGE))

    finally:
        driver.quit()

# ============================================================
# 🚀 MAIN RETRY FUNCTION
# ============================================================

def main_retry():
    print("\n" + "="*60)
    print("🔄 SMART RETRY FOR NA CELLS - AGODA CRAWLER")
    print("="*60)

    # Load files
    print(f"\n📂 Loading {INPUT_FILE}...")
    result_df = pd.read_csv(INPUT_FILE)

    print(f"📂 Loading {INPUT_CSV} for URLs...")
    raw_df = pd.read_csv(INPUT_CSV)

    # Normalize column names in raw_df
    raw_df.columns = ['hotel_name', 'hotel_url', 'room_type']
    print(f"✅ Loaded {len(raw_df)} hotels from raw CSV")

    # Identify NA cells
    print("\n🔍 Identifying NA cells...")
    na_cells = identify_na_cells(result_df, raw_df)

    # Test mode - limit cells
    if TEST_MODE:
        na_cells = na_cells[:50]
        print(f"\n⚠️  TEST MODE: Only retrying first 50 cells")

    print(f"\n📊 Found {len(na_cells)} cells to retry")
    print(f"   Using {NUM_WORKERS} workers")
    print(f"   Delay range: {DELAY_RANGE[0]}-{DELAY_RANGE[1]}s")
    print(f"   Max retries per cell: {MAX_RETRIES}")

    if len(na_cells) == 0:
        print("✅ No NA cells found! All done.")
        return

    # Estimate time
    avg_time_per_cell = (DELAY_RANGE[0] + DELAY_RANGE[1]) / 2 * MAX_RETRIES
    estimated_time = (len(na_cells) * avg_time_per_cell) / NUM_WORKERS / 60
    print(f"   ⏱️  Estimated time: ~{estimated_time:.0f} minutes")

    if not AUTO_START:
        try:
            input("\n⏸️  Press Enter to start retry...")
        except EOFError:
            print("\n⚠️  No interactive terminal. Set AUTO_START=True to skip prompt.")
            return

    # Split work among workers
    batch_size = len(na_cells) // NUM_WORKERS + 1
    batches = [na_cells[i:i+batch_size] for i in range(0, len(na_cells), batch_size)]

    # Retry with threading
    results_dict = {}
    lock = threading.Lock()

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = []
        for worker_id, batch in enumerate(batches, 1):
            future = executor.submit(retry_worker, batch, worker_id, results_dict, lock)
            futures.append(future)

        # Wait for completion
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Worker error: {e}")

    elapsed = time.time() - start_time

    # Update dataframe with retry results
    print(f"\n💾 Updating results...")
    updated_count = 0

    for (hotel_name, room_type, week_num), price in results_dict.items():
        if price != "NA":
            mask = (result_df['hotel_name'] == hotel_name) & (result_df['room_type'] == room_type)
            result_df.loc[mask, f'price_w{week_num}'] = price
            updated_count += 1

    # Save result
    result_df.to_csv(OUTPUT_FILE, index=False)

    # Final statistics
    print("\n" + "="*60)
    print("✅ RETRY COMPLETED")
    print("="*60)
    print(f"Total cells retried: {len(na_cells)}")
    print(f"Successfully updated: {updated_count} ({updated_count/len(na_cells)*100:.1f}%)")
    print(f"Still NA: {len(na_cells) - updated_count}")
    print(f"Time elapsed: {elapsed/60:.1f} minutes")
    print(f"Output saved to: {OUTPUT_FILE}")
    print("="*60)

if __name__ == "__main__":
    main_retry()
