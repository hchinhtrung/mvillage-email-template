#!/usr/bin/env python3
"""
Debug script for Agoda scraper
"""
import sys
import os
import time
from datetime import date, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def debug_agoda_page():
    """Debug Agoda page loading and element detection"""
    
    # Pullman Saigon Centre Hotel URL
    hotel_url = "https://www.agoda.com/vi-vn/pullman-saigon-centre-hotel/hotel/ho-chi-minh-city-vn.html"
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Don't run headless for debugging
    # chrome_options.add_argument("--headless")
    
    print("Setting up WebDriver...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"Loading page: {hotel_url}")
        driver.get(hotel_url)
        
        # Wait for page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # Wait for dynamic content
        time.sleep(10)
        
        # Try to find hotel name
        print("\n=== Looking for hotel name ===")
        name_selectors = [
            "h1[data-selenium='hotel-header-name']",
            "h1.HeaderCerebrum__Name", 
            "h1.hotel-name",
            "[data-testid='hotel-name']",
            ".hotel-header-name",
            "h1[data-element-name='hotel-header-name']",
            "h1.PropertyHeaderName",
            ".PropertyHeaderName h1",
            "h1"
        ]
        
        for selector in name_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for i, element in enumerate(elements):
                        text = element.text.strip()
                        if text:
                            print(f"Found with '{selector}' [{i}]: {text}")
                            break
            except Exception as e:
                print(f"Error with selector '{selector}': {e}")
        
        # Try to find room elements
        print("\n=== Looking for room elements ===")
        room_selectors = [
            "[data-selenium='masterroom']",
            ".MasterRoom",
            ".room-container",
            ".room-item",
            "[data-testid='room-item']",
            ".PropertyRoomsList .Room",
            ".RoomGridItem",
            ".room-card",
            "[data-element-name='room-card']"
        ]
        
        for selector in room_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"Found {len(elements)} room elements with '{selector}'")
                    for i, element in enumerate(elements[:3]):  # Show first 3
                        try:
                            text = element.text.strip()[:100]  # First 100 chars
                            print(f"  Room {i+1}: {text}...")
                        except:
                            print(f"  Room {i+1}: [Could not get text]")
                    break
            except Exception as e:
                print(f"Error with room selector '{selector}': {e}")
        
        # Try to find price elements
        print("\n=== Looking for price elements ===")
        price_selectors = [
            "[data-selenium*='price']",
            ".price",
            ".Price",
            "[data-testid*='price']",
            ".room-price",
            ".MasterRoom__Price"
        ]
        
        for selector in price_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"Found {len(elements)} price elements with '{selector}'")
                    for i, element in enumerate(elements[:5]):  # Show first 5
                        try:
                            text = element.text.strip()
                            if text:
                                print(f"  Price {i+1}: {text}")
                        except:
                            print(f"  Price {i+1}: [Could not get text]")
                    break
            except Exception as e:
                print(f"Error with price selector '{selector}': {e}")
        
        # Check page source for debugging
        print("\n=== Page source analysis ===")
        page_source = driver.page_source
        print(f"Page source length: {len(page_source)} characters")
        
        # Look for common Agoda elements in source
        agoda_indicators = [
            "agoda",
            "hotel-header",
            "room",
            "price",
            "PropertyHeader",
            "MasterRoom"
        ]
        
        for indicator in agoda_indicators:
            count = page_source.lower().count(indicator.lower())
            print(f"'{indicator}' appears {count} times in page source")
        
        # Check if we're being redirected or blocked
        if "captcha" in page_source.lower():
            print("⚠️  CAPTCHA detected in page")
        
        if "blocked" in page_source.lower():
            print("⚠️  Blocking detected in page")
        
        if "robot" in page_source.lower():
            print("⚠️  Robot detection in page")
        
        # Save page source for analysis
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("\n📄 Page source saved to debug_page_source.html")
        
        # Take a screenshot
        driver.save_screenshot("debug_screenshot.png")
        print("📸 Screenshot saved to debug_screenshot.png")
        
        print("\n=== Debug complete ===")
        print("Check the saved files for more details.")
        print("Press Enter to close browser...")
        input()
        
    except Exception as e:
        print(f"Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_agoda_page()
