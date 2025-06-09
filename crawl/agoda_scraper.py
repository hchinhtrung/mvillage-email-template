"""
Main Agoda scraper class
"""
import os
import time
import uuid
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from data_models import HotelPricing, RoomInfo, ScrapingSession, DataExporter
from utils import (
    setup_logging, get_random_user_agent, wait_with_jitter, 
    safe_find_element, safe_get_text, safe_get_attribute,
    extract_price_from_text, build_agoda_search_url, validate_url,
    clean_hotel_name, retry_on_failure
)
from config import (
    HEADLESS, WINDOW_SIZE, CHROME_OPTIONS, TIMEOUT, IMPLICIT_WAIT,
    MAX_RETRIES, get_target_dates, get_output_filename, DATA_DIR, OUTPUT_FORMAT
)

class AgodaScraper:
    """Main scraper class for Agoda hotel pricing data"""
    
    def __init__(self, headless: bool = HEADLESS):
        self.logger = setup_logging("agoda_scraper")
        self.headless = headless
        self.driver = None
        self.session = None
        
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
    
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Add all configured options
            for option in CHROME_OPTIONS:
                chrome_options.add_argument(option)
            
            # Set window size
            chrome_options.add_argument(f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}")
            
            # Set user agent
            user_agent = get_random_user_agent()
            chrome_options.add_argument(f"--user-agent={user_agent}")
            
            # Additional anti-detection measures
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Setup driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set timeouts
            self.driver.implicitly_wait(IMPLICIT_WAIT)
            self.driver.set_page_load_timeout(TIMEOUT)
            
            self.logger.info("WebDriver setup completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to setup WebDriver: {e}")
            raise
    
    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("WebDriver closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing WebDriver: {e}")
    
    @retry_on_failure(max_retries=MAX_RETRIES)
    def load_page(self, url: str) -> bool:
        """Load a page with retry logic"""
        try:
            self.logger.info(f"Loading page: {url}")
            self.driver.get(url)

            # Wait for page to load
            WebDriverWait(self.driver, TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Additional wait for dynamic content
            time.sleep(8)  # Increased wait time

            # Log page title for debugging
            self.logger.info(f"Page title: {self.driver.title}")
            self.logger.info(f"Current URL: {self.driver.current_url}")

            # Check if we're on the right page
            if "agoda" not in self.driver.current_url.lower():
                self.logger.warning(f"Unexpected URL: {self.driver.current_url}")

            # Check for robot detection
            page_source = self.driver.page_source.lower()
            if "robot" in page_source or "captcha" in page_source:
                self.logger.warning("Robot/CAPTCHA detection found, but continuing...")

            self.logger.info("Page loaded successfully")
            return True

        except TimeoutException:
            self.logger.error(f"Timeout loading page: {url}")
            return False
        except WebDriverException as e:
            self.logger.error(f"WebDriver error loading page: {e}")
            return False
    
    def extract_hotel_info(self, url: str, check_in: date, check_out: date) -> Optional[HotelPricing]:
        """Extract hotel pricing information from Agoda page"""
        try:
            # Build search URL with specific dates
            self.logger.info("Building search URL...")
            search_url = build_agoda_search_url(url, check_in, check_out)
            self.logger.info(f"Built search URL: {search_url}")

            self.logger.info("Loading page...")
            if not self.load_page(search_url):
                self.logger.error("Failed to load page")
                return None

            # Wait for pricing information to load
            self.logger.info("Waiting for content to load...")
            wait_with_jitter(2)

            # Extract hotel name
            self.logger.info("Extracting hotel name...")
            hotel_name = self._extract_hotel_name()
            if not hotel_name:
                self.logger.warning("Could not extract hotel name")
                hotel_name = "Unknown Hotel"

            # Extract hotel location
            self.logger.info("Extracting location...")
            location = self._extract_location()

            # Extract hotel rating and reviews
            self.logger.info("Extracting rating...")
            rating = self._extract_rating()
            self.logger.info("Extracting review count...")
            review_count = self._extract_review_count()

            # Extract room information
            self.logger.info("Extracting room information...")
            rooms = self._extract_room_info()

            if not rooms:
                self.logger.warning("No room information found")
                return None

            # Create hotel pricing object
            self.logger.info("Creating hotel pricing object...")
            hotel_pricing = HotelPricing(
                hotel_name=hotel_name,
                hotel_id=self._extract_hotel_id(),
                location=location,
                check_in_date=check_in,
                check_out_date=check_out,
                rooms=rooms,
                rating=rating,
                review_count=review_count,
                hotel_url=url
            )

            self.logger.info(f"Successfully extracted data for {hotel_name}")
            return hotel_pricing

        except Exception as e:
            self.logger.error(f"Error extracting hotel info: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _extract_hotel_name(self) -> str:
        """Extract hotel name from page"""
        selectors = [
            "h1[data-selenium='hotel-header-name']",
            "h1.HeaderCerebrum__Name",
            "h1.hotel-name",
            "[data-testid='hotel-name']",
            ".hotel-header-name",
            "h1[data-element-name='hotel-header-name']",
            "h1.PropertyHeaderName",
            ".PropertyHeaderName h1",
            "h1",
            ".hotel-name",
            "[data-selenium='hotel-name']"
        ]

        for selector in selectors:
            element = safe_find_element(self.driver, By.CSS_SELECTOR, selector)
            if element:
                name = safe_get_text(element)
                if name and len(name.strip()) > 3:  # Ensure we get a meaningful name
                    self.logger.info(f"Found hotel name with selector '{selector}': {name}")
                    return name

        # Try to extract from page title as fallback
        try:
            title = self.driver.title
            if title and "agoda" in title.lower():
                # Extract hotel name from title (usually before " - Agoda")
                parts = title.split(" - ")
                if len(parts) > 1:
                    potential_name = parts[0].strip()
                    if len(potential_name) > 3:
                        self.logger.info(f"Extracted hotel name from title: {potential_name}")
                        return potential_name
        except:
            pass

        self.logger.warning("Could not extract hotel name")
        return ""
    
    def _extract_location(self) -> str:
        """Extract hotel location"""
        selectors = [
            "[data-selenium='hotel-address-map']",
            ".hotel-address",
            ".HeaderCerebrum__Address",
            "[data-testid='hotel-address']"
        ]
        
        for selector in selectors:
            element = safe_find_element(self.driver, By.CSS_SELECTOR, selector)
            if element:
                location = safe_get_text(element)
                if location:
                    return location
        
        return ""
    
    def _extract_rating(self) -> Optional[float]:
        """Extract hotel rating"""
        selectors = [
            "[data-selenium='hotel-header-review-score']",
            ".ReviewScore__Number",
            ".hotel-rating",
            "[data-testid='review-score']"
        ]
        
        for selector in selectors:
            element = safe_find_element(self.driver, By.CSS_SELECTOR, selector)
            if element:
                rating_text = safe_get_text(element)
                try:
                    return float(rating_text.split()[0])
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_review_count(self) -> Optional[int]:
        """Extract review count"""
        selectors = [
            "[data-selenium='hotel-header-review-count']",
            ".ReviewScore__Text",
            ".review-count",
            "[data-testid='review-count']"
        ]
        
        for selector in selectors:
            element = safe_find_element(self.driver, By.CSS_SELECTOR, selector)
            if element:
                count_text = safe_get_text(element)
                # Extract number from text like "1,234 reviews"
                import re
                match = re.search(r'([\d,]+)', count_text)
                if match:
                    try:
                        return int(match.group(1).replace(',', ''))
                    except ValueError:
                        continue
        
        return None
    
    def _extract_hotel_id(self) -> Optional[str]:
        """Extract hotel ID from URL or page"""
        try:
            current_url = self.driver.current_url
            import re
            match = re.search(r'hotelid=(\d+)', current_url)
            if match:
                return match.group(1)
            
            match = re.search(r'/hotel/([^/]+)', current_url)
            if match:
                return match.group(1)
        except:
            pass
        
        return None

    def _extract_room_info(self) -> List[RoomInfo]:
        """Extract room information and pricing"""
        rooms = []

        # Wait for room data to load
        time.sleep(3)

        # Common selectors for room containers
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

        room_elements = []
        for selector in room_selectors:
            room_elements = safe_find_element(self.driver, By.CSS_SELECTOR, selector, multiple=True)
            if room_elements:
                self.logger.info(f"Found {len(room_elements)} room elements with selector: {selector}")
                break

        if not room_elements:
            self.logger.warning("No room elements found, trying alternative approach")
            # Try to find any pricing elements as a fallback
            price_selectors = [
                "[data-testid*='price']",
                "[data-selenium*='price']",
                ".price",
                ".Price"
            ]

            price_elements = []
            for selector in price_selectors:
                price_elements = safe_find_element(self.driver, By.CSS_SELECTOR, selector, multiple=True)
                if price_elements:
                    self.logger.info(f"Found {len(price_elements)} price elements with selector: {selector}")
                    break

            if price_elements:
                # Create basic room info from price elements
                for i, price_element in enumerate(price_elements[:10]):  # Limit to 10 rooms
                    try:
                        price_text = safe_get_text(price_element)
                        if price_text and price_text.strip():
                            price, currency = extract_price_from_text(price_text)
                            if price > 0:
                                room_info = RoomInfo(
                                    room_type=f"Room Type {i+1}",
                                    price=price,
                                    currency=currency,
                                    availability=True
                                )
                                rooms.append(room_info)
                                self.logger.info(f"Extracted price room {i+1}: {price} {currency}")
                    except Exception as e:
                        self.logger.error(f"Error extracting fallback room info: {e}")
                        continue

            if rooms:
                self.logger.info(f"Successfully extracted {len(rooms)} rooms using price fallback")
            return rooms

        for i, room_element in enumerate(room_elements):
            try:
                room_info = self._extract_single_room_info(room_element)
                if room_info:
                    rooms.append(room_info)
                    self.logger.info(f"Successfully extracted room {i+1}: {room_info.room_type}")
            except Exception as e:
                self.logger.error(f"Error extracting room info for element {i}: {e}")
                continue

        self.logger.info(f"Total rooms extracted: {len(rooms)}")
        return rooms

    def _extract_single_room_info(self, room_element) -> Optional[RoomInfo]:
        """Extract information for a single room"""
        try:
            # Extract room type/name
            room_type = self._extract_room_type(room_element)
            if not room_type:
                return None

            # Extract price
            price, currency = self._extract_room_price(room_element)

            # Extract availability
            availability = self._extract_room_availability(room_element)

            # Extract additional room details
            max_guests = self._extract_max_guests(room_element)
            bed_type = self._extract_bed_type(room_element)
            room_size = self._extract_room_size(room_element)
            amenities = self._extract_amenities(room_element)
            cancellation_policy = self._extract_cancellation_policy(room_element)

            return RoomInfo(
                room_type=room_type,
                price=price,
                currency=currency,
                availability=availability,
                max_guests=max_guests,
                bed_type=bed_type,
                room_size=room_size,
                amenities=amenities,
                cancellation_policy=cancellation_policy
            )

        except Exception as e:
            self.logger.error(f"Error extracting single room info: {e}")
            return None

    def _extract_room_type(self, room_element) -> str:
        """Extract room type from room element"""
        selectors = [
            ".room-type-name",
            ".MasterRoom__Name",
            "[data-selenium='room-name']",
            "h3",
            ".room-title",
            "[data-testid='room-name']"
        ]

        for selector in selectors:
            element = room_element.find_element(By.CSS_SELECTOR, selector) if room_element else None
            if element:
                room_type = safe_get_text(element)
                if room_type:
                    return room_type

        return "Unknown Room Type"

    def _extract_room_price(self, room_element) -> tuple[float, str]:
        """Extract room price and currency"""
        price_selectors = [
            ".room-price",
            ".MasterRoom__Price",
            "[data-selenium='display-price']",
            ".price-display",
            "[data-testid='price']",
            ".price"
        ]

        for selector in price_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    price_text = safe_get_text(element)
                    if price_text:
                        return extract_price_from_text(price_text)
            except:
                continue

        return 0.0, ""

    def _extract_room_availability(self, room_element) -> bool:
        """Extract room availability"""
        # Check for sold out or unavailable indicators
        unavailable_selectors = [
            ".sold-out",
            ".unavailable",
            "[data-selenium='sold-out']",
            ".no-availability"
        ]

        for selector in unavailable_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    return False
            except:
                continue

        # Check for booking button or price presence
        available_selectors = [
            ".book-button",
            ".select-room",
            "[data-selenium='select-room-btn']",
            ".price"
        ]

        for selector in available_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    return True
            except:
                continue

        return True  # Default to available if no clear indicators

    def _extract_max_guests(self, room_element) -> Optional[int]:
        """Extract maximum guests for room"""
        guest_selectors = [
            ".max-guests",
            ".guest-capacity",
            "[data-selenium='guest-count']"
        ]

        for selector in guest_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    text = safe_get_text(element)
                    import re
                    match = re.search(r'(\d+)', text)
                    if match:
                        return int(match.group(1))
            except:
                continue

        return None

    def _extract_bed_type(self, room_element) -> Optional[str]:
        """Extract bed type information"""
        bed_selectors = [
            ".bed-type",
            ".bed-info",
            "[data-selenium='bed-type']"
        ]

        for selector in bed_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    bed_type = safe_get_text(element)
                    if bed_type:
                        return bed_type
            except:
                continue

        return None

    def _extract_room_size(self, room_element) -> Optional[str]:
        """Extract room size information"""
        size_selectors = [
            ".room-size",
            ".size-info",
            "[data-selenium='room-size']"
        ]

        for selector in size_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    size = safe_get_text(element)
                    if size:
                        return size
            except:
                continue

        return None

    def _extract_amenities(self, room_element) -> Optional[List[str]]:
        """Extract room amenities"""
        amenity_selectors = [
            ".amenities li",
            ".room-amenities .amenity",
            "[data-selenium='amenity']"
        ]

        amenities = []
        for selector in amenity_selectors:
            try:
                elements = room_element.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    amenity = safe_get_text(element)
                    if amenity and amenity not in amenities:
                        amenities.append(amenity)
            except:
                continue

        return amenities if amenities else None

    def _extract_cancellation_policy(self, room_element) -> Optional[str]:
        """Extract cancellation policy"""
        policy_selectors = [
            ".cancellation-policy",
            ".policy-info",
            "[data-selenium='cancellation']"
        ]

        for selector in policy_selectors:
            try:
                element = room_element.find_element(By.CSS_SELECTOR, selector)
                if element:
                    policy = safe_get_text(element)
                    if policy:
                        return policy
            except:
                continue

        return None

    def scrape_hotel_for_dates(self, hotel_url: str, target_dates: List[date] = None) -> List[HotelPricing]:
        """Scrape hotel pricing for multiple target dates"""
        if target_dates is None:
            target_dates = get_target_dates()

        if not validate_url(hotel_url):
            self.logger.error(f"Invalid Agoda URL: {hotel_url}")
            return []

        # Setup driver if not already done
        if not self.driver:
            self.logger.info("Setting up WebDriver...")
            self.setup_driver()

        results = []

        for target_date in target_dates:
            try:
                # Check-out date is the next day
                check_out_date = target_date + timedelta(days=1)

                self.logger.info(f"Scraping for dates: {target_date} to {check_out_date}")

                hotel_pricing = self.extract_hotel_info(hotel_url, target_date, check_out_date)

                if hotel_pricing:
                    results.append(hotel_pricing)
                    if self.session:
                        self.session.add_hotel(hotel_pricing)
                else:
                    error_msg = f"Failed to extract data for {target_date}"
                    self.logger.error(error_msg)
                    if self.session:
                        self.session.add_error(error_msg)

                # Wait between requests
                wait_with_jitter()

            except Exception as e:
                error_msg = f"Error scraping for date {target_date}: {e}"
                self.logger.error(error_msg)
                if self.session:
                    self.session.add_error(error_msg)

        return results

    def scrape_multiple_hotels(self, hotel_urls: List[str], target_dates: List[date] = None) -> ScrapingSession:
        """Scrape multiple hotels for target dates"""
        if target_dates is None:
            target_dates = get_target_dates()

        # Create new scraping session
        session_id = str(uuid.uuid4())
        self.session = ScrapingSession(
            session_id=session_id,
            start_time=datetime.now(),
            end_time=None,
            hotels_scraped=[],
            target_dates=target_dates
        )

        self.logger.info(f"Starting scraping session {session_id} for {len(hotel_urls)} hotels")

        try:
            # Setup driver
            self.setup_driver()

            for i, hotel_url in enumerate(hotel_urls, 1):
                self.logger.info(f"Processing hotel {i}/{len(hotel_urls)}: {hotel_url}")

                try:
                    results = self.scrape_hotel_for_dates(hotel_url, target_dates)
                    self.logger.info(f"Successfully scraped {len(results)} date combinations for hotel {i}")

                except Exception as e:
                    error_msg = f"Failed to scrape hotel {hotel_url}: {e}"
                    self.logger.error(error_msg)
                    self.session.add_error(error_msg)

                # Wait between hotels
                wait_with_jitter(5)

        except Exception as e:
            error_msg = f"Critical error during scraping session: {e}"
            self.logger.error(error_msg)
            self.session.add_error(error_msg)

        finally:
            # Close driver and finish session
            self.close_driver()
            self.session.finish_session()

            # Save session data
            self.save_session_data(self.session)

        self.logger.info(f"Scraping session completed. Success: {self.session.success_count}, Errors: {self.session.error_count}")
        return self.session

    def save_session_data(self, session: ScrapingSession):
        """Save scraping session data to files"""
        try:
            timestamp = session.start_time
            base_filename = get_output_filename("session", timestamp)

            if OUTPUT_FORMAT in ["json", "both"]:
                json_filepath = os.path.join(DATA_DIR, f"{base_filename}.json")
                DataExporter.export_to_json(session, json_filepath)
                self.logger.info(f"Session data saved to JSON: {json_filepath}")

            if OUTPUT_FORMAT in ["csv", "both"]:
                csv_filepath = os.path.join(DATA_DIR, f"{base_filename}.csv")
                DataExporter.export_to_csv(session, csv_filepath)
                self.logger.info(f"Session data saved to CSV: {csv_filepath}")

        except Exception as e:
            self.logger.error(f"Error saving session data: {e}")

    def run_daily_scrape(self, hotel_urls: List[str]) -> ScrapingSession:
        """Run daily scraping for configured hotels"""
        self.logger.info("Starting daily scraping run")

        target_dates = get_target_dates()
        self.logger.info(f"Target dates: {[d.isoformat() for d in target_dates]}")

        return self.scrape_multiple_hotels(hotel_urls, target_dates)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close_driver()
