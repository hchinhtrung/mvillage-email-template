#!/usr/bin/env python3
"""
Example usage of Agoda scraper
"""
import sys
import os
from datetime import datetime, date, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agoda_scraper import AgodaScraper
from scheduler import ScrapingScheduler
from utils import setup_logging

def example_single_hotel():
    """Example: Scrape a single hotel"""
    print("=== Example: Single Hotel Scraping ===")
    
    # Example Agoda hotel URL (replace with actual competitor URL)
    hotel_url = "https://www.agoda.com/centara-grand-beach-resort-samui/hotel/koh-samui-th.html"
    
    logger = setup_logging("example")
    logger.info("Starting single hotel scraping example")
    
    try:
        with AgodaScraper(headless=False) as scraper:  # Set headless=False to see browser
            # Get default target dates (D, D+7, D+15)
            target_dates = [
                date.today(),
                date.today() + timedelta(days=7),
                date.today() + timedelta(days=15)
            ]
            
            print(f"Scraping hotel: {hotel_url}")
            print(f"Target dates: {[d.isoformat() for d in target_dates]}")
            
            results = scraper.scrape_hotel_for_dates(hotel_url, target_dates)
            
            if results:
                print(f"\nSuccessfully scraped {len(results)} date combinations:")
                for result in results:
                    print(f"\n--- {result.hotel_name} ---")
                    print(f"Check-in: {result.check_in_date}")
                    print(f"Check-out: {result.check_out_date}")
                    print(f"Location: {result.location}")
                    print(f"Rating: {result.rating}")
                    print(f"Rooms found: {len(result.rooms)}")
                    
                    for i, room in enumerate(result.rooms[:3], 1):  # Show first 3 rooms
                        print(f"  Room {i}: {room.room_type}")
                        print(f"    Price: {room.price} {room.currency}")
                        print(f"    Available: {room.availability}")
            else:
                print("No data was scraped. Check the URL and try again.")
                
    except Exception as e:
        print(f"Error in example: {e}")

def example_multiple_hotels():
    """Example: Scrape multiple hotels"""
    print("\n=== Example: Multiple Hotels Scraping ===")
    
    # Example hotel URLs (replace with actual competitor URLs)
    hotel_urls = [
        "https://www.agoda.com/centara-grand-beach-resort-samui/hotel/koh-samui-th.html",
        "https://www.agoda.com/four-seasons-resort-koh-samui/hotel/koh-samui-th.html"
    ]
    
    logger = setup_logging("example")
    logger.info("Starting multiple hotels scraping example")
    
    try:
        with AgodaScraper(headless=True) as scraper:  # Use headless for multiple hotels
            print(f"Scraping {len(hotel_urls)} hotels...")
            
            session = scraper.scrape_multiple_hotels(hotel_urls)
            
            print(f"\nScraping session completed!")
            print(f"Session ID: {session.session_id}")
            print(f"Hotels successfully scraped: {session.success_count}")
            print(f"Errors encountered: {session.error_count}")
            print(f"Duration: {session.get_duration():.2f} seconds")
            
            if session.hotels_scraped:
                print(f"\nScraped hotels:")
                for hotel in session.hotels_scraped:
                    print(f"- {hotel.hotel_name} ({hotel.check_in_date}): {len(hotel.rooms)} rooms")
            
            if session.errors:
                print(f"\nErrors:")
                for error in session.errors:
                    print(f"- {error}")
                    
    except Exception as e:
        print(f"Error in example: {e}")

def example_scheduler_setup():
    """Example: Set up daily scheduler"""
    print("\n=== Example: Scheduler Setup ===")
    
    # Example hotel URLs
    hotel_urls = [
        "https://www.agoda.com/centara-grand-beach-resort-samui/hotel/koh-samui-th.html",
        "https://www.agoda.com/four-seasons-resort-koh-samui/hotel/koh-samui-th.html"
    ]
    
    try:
        # Create scheduler
        scheduler = ScrapingScheduler(hotel_urls, schedule_time="09:00")
        
        print(f"Scheduler created with {len(scheduler.hotel_urls)} hotels")
        print(f"Daily scraping scheduled for {scheduler.schedule_time}")
        
        # Save configuration
        scheduler.save_config()
        print("Configuration saved")
        
        # Show status
        status = scheduler.get_status()
        print(f"\nScheduler Status:")
        print(f"- Running: {status['running']}")
        print(f"- Schedule Time: {status['schedule_time']}")
        print(f"- Hotel Count: {status['hotel_count']}")
        
        # Run once as example
        print("\nRunning scraping once as example...")
        session = scheduler.run_once()
        print(f"Example run completed. Session ID: {session.session_id}")
        
    except Exception as e:
        print(f"Error in scheduler example: {e}")

def example_data_analysis():
    """Example: Analyze scraped data"""
    print("\n=== Example: Data Analysis ===")
    
    import pandas as pd
    import glob
    import json
    
    try:
        # Find latest data files
        data_dir = "data"
        json_files = glob.glob(f"{data_dir}/agoda_pricing_session_*.json")
        
        if not json_files:
            print("No data files found. Run scraping first.")
            return
        
        # Load latest session data
        latest_file = max(json_files)
        print(f"Analyzing data from: {latest_file}")
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # Basic statistics
        hotels_count = len(session_data['hotels_scraped'])
        total_rooms = sum(len(hotel['rooms']) for hotel in session_data['hotels_scraped'])
        
        print(f"\nSession Statistics:")
        print(f"- Hotels scraped: {hotels_count}")
        print(f"- Total rooms found: {total_rooms}")
        print(f"- Success rate: {session_data['success_count']}/{session_data['success_count'] + session_data['error_count']}")
        
        # Price analysis
        if session_data['hotels_scraped']:
            all_prices = []
            for hotel in session_data['hotels_scraped']:
                for room in hotel['rooms']:
                    if room['price'] > 0:
                        all_prices.append(room['price'])
            
            if all_prices:
                print(f"\nPrice Analysis:")
                print(f"- Average price: {sum(all_prices)/len(all_prices):.2f}")
                print(f"- Min price: {min(all_prices):.2f}")
                print(f"- Max price: {max(all_prices):.2f}")
                
                # Hotel breakdown
                print(f"\nHotel Breakdown:")
                for hotel in session_data['hotels_scraped']:
                    hotel_prices = [room['price'] for room in hotel['rooms'] if room['price'] > 0]
                    if hotel_prices:
                        avg_price = sum(hotel_prices) / len(hotel_prices)
                        print(f"- {hotel['hotel_name']}: {len(hotel_prices)} rooms, avg {avg_price:.2f}")
        
    except Exception as e:
        print(f"Error in data analysis: {e}")

def main():
    """Run all examples"""
    print("Agoda Scraper Examples")
    print("=" * 50)
    
    # Check if we have example URLs
    print("Note: This example uses sample Agoda URLs.")
    print("Replace with actual competitor hotel URLs for real scraping.")
    print()
    
    try:
        # Example 1: Single hotel
        example_single_hotel()
        
        # Example 2: Multiple hotels
        example_multiple_hotels()
        
        # Example 3: Scheduler setup
        example_scheduler_setup()
        
        # Example 4: Data analysis
        example_data_analysis()
        
        print("\n" + "=" * 50)
        print("Examples completed!")
        print("\nNext steps:")
        print("1. Replace example URLs with actual competitor hotel URLs")
        print("2. Configure the scheduler with your target hotels")
        print("3. Set up daily automated scraping")
        print("4. Analyze the collected pricing data")
        
    except KeyboardInterrupt:
        print("\nExamples interrupted by user")
    except Exception as e:
        print(f"\nError running examples: {e}")

if __name__ == "__main__":
    main()
