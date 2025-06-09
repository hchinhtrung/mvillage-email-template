#!/usr/bin/env python3
"""
Test script for Agoda scraper
"""
import sys
import os
from datetime import date, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all modules can be imported"""
    print("Testing imports...")
    
    try:
        from agoda_scraper import AgodaScraper
        print("✓ AgodaScraper imported successfully")
        
        from scheduler import ScrapingScheduler
        print("✓ ScrapingScheduler imported successfully")
        
        from data_models import HotelPricing, RoomInfo, ScrapingSession
        print("✓ Data models imported successfully")
        
        from utils import setup_logging, validate_url, extract_price_from_text
        print("✓ Utils imported successfully")
        
        import config
        print("✓ Config imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_config():
    """Test configuration settings"""
    print("\nTesting configuration...")
    
    try:
        from config import get_target_dates, get_output_filename, DATA_DIR
        
        # Test target dates
        dates = get_target_dates()
        print(f"✓ Target dates: {[d.isoformat() for d in dates]}")
        
        # Test filename generation
        filename = get_output_filename("test_hotel")
        print(f"✓ Generated filename: {filename}")
        
        # Test data directory
        print(f"✓ Data directory: {DATA_DIR}")
        
        return True
        
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False

def test_utils():
    """Test utility functions"""
    print("\nTesting utilities...")
    
    try:
        from utils import validate_url, extract_price_from_text, setup_logging
        
        # Test URL validation
        valid_url = "https://www.agoda.com/hotel/example"
        invalid_url = "https://booking.com/hotel/example"
        
        assert validate_url(valid_url) == True
        assert validate_url(invalid_url) == False
        print("✓ URL validation working")
        
        # Test price extraction
        price_texts = [
            "THB 1,500",
            "$150.00",
            "€120.50",
            "1,200 VND"
        ]
        
        for text in price_texts:
            price, currency = extract_price_from_text(text)
            print(f"✓ Price extraction: '{text}' -> {price} {currency}")
        
        # Test logging setup
        logger = setup_logging("test")
        logger.info("Test log message")
        print("✓ Logging setup working")
        
        return True
        
    except Exception as e:
        print(f"✗ Utils error: {e}")
        return False

def test_data_models():
    """Test data models"""
    print("\nTesting data models...")
    
    try:
        from data_models import RoomInfo, HotelPricing, ScrapingSession
        from datetime import datetime
        
        # Test RoomInfo
        room = RoomInfo(
            room_type="Deluxe Room",
            price=1500.0,
            currency="THB",
            availability=True,
            max_guests=2
        )
        print(f"✓ RoomInfo created: {room.room_type}")
        
        # Test HotelPricing
        hotel = HotelPricing(
            hotel_name="Test Hotel",
            hotel_id="12345",
            location="Bangkok, Thailand",
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=1),
            rooms=[room]
        )
        print(f"✓ HotelPricing created: {hotel.hotel_name}")
        
        # Test JSON serialization
        json_data = hotel.to_json()
        print("✓ JSON serialization working")
        
        # Test ScrapingSession
        session = ScrapingSession(
            session_id="test-session",
            start_time=datetime.now(),
            end_time=None,
            hotels_scraped=[hotel],
            target_dates=[date.today()]
        )
        print(f"✓ ScrapingSession created: {session.session_id}")
        
        return True
        
    except Exception as e:
        print(f"✗ Data models error: {e}")
        return False

def test_webdriver_setup():
    """Test WebDriver setup"""
    print("\nTesting WebDriver setup...")
    
    try:
        from agoda_scraper import AgodaScraper
        
        scraper = AgodaScraper(headless=True)
        scraper.setup_driver()
        
        if scraper.driver:
            print("✓ WebDriver setup successful")
            
            # Test basic navigation
            scraper.driver.get("https://www.google.com")
            title = scraper.driver.title
            print(f"✓ Navigation test: {title}")
            
            scraper.close_driver()
            print("✓ WebDriver closed successfully")
            
            return True
        else:
            print("✗ WebDriver setup failed")
            return False
            
    except Exception as e:
        print(f"✗ WebDriver error: {e}")
        return False

def test_scheduler():
    """Test scheduler functionality"""
    print("\nTesting scheduler...")
    
    try:
        from scheduler import ScrapingScheduler
        
        # Test scheduler creation
        test_urls = ["https://www.agoda.com/hotel/test"]
        scheduler = ScrapingScheduler(test_urls, "10:00")
        print(f"✓ Scheduler created with {len(scheduler.hotel_urls)} URLs")
        
        # Test configuration save/load
        scheduler.save_config()
        print("✓ Configuration saved")
        
        loaded_scheduler = ScrapingScheduler.load_config()
        print("✓ Configuration loaded")
        
        # Test status
        status = scheduler.get_status()
        print(f"✓ Status retrieved: {status['hotel_count']} hotels")
        
        return True
        
    except Exception as e:
        print(f"✗ Scheduler error: {e}")
        return False

def test_directory_structure():
    """Test directory structure"""
    print("\nTesting directory structure...")
    
    try:
        import os
        from config import DATA_DIR, LOGS_DIR
        
        # Check if directories exist or can be created
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        print(f"✓ Data directory: {DATA_DIR}")
        print(f"✓ Logs directory: {LOGS_DIR}")
        
        # Check write permissions
        test_file = os.path.join(DATA_DIR, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("✓ Write permissions OK")
        
        return True
        
    except Exception as e:
        print(f"✗ Directory structure error: {e}")
        return False

def main():
    """Run all tests"""
    print("Agoda Scraper Test Suite")
    print("=" * 40)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Utilities", test_utils),
        ("Data Models", test_data_models),
        ("Directory Structure", test_directory_structure),
        ("Scheduler", test_scheduler),
        ("WebDriver Setup", test_webdriver_setup),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The scraper is ready to use.")
        print("\nNext steps:")
        print("1. Add your competitor hotel URLs using: python main.py --add-url 'URL'")
        print("2. Test with a single hotel: python main.py --url 'URL'")
        print("3. Set up daily scheduling: python main.py --schedule")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the errors above.")
        
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
