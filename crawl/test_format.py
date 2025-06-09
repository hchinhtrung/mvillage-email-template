#!/usr/bin/env python3
"""
Test script to verify the expected output format
"""
import sys
import os
from datetime import date, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agoda_scraper import AgodaScraper
from utils import format_vnd_price

def test_pullman_format():
    """Test Pullman hotel with expected format output"""
    
    # URL pattern bạn cung cấp
    hotel_url = "https://www.agoda.com/vi-vn/pullman-saigon-centre-hotel/hotel/ho-chi-minh-city-vn.html?countryId=38&finalPriceView=1&isShowMobileAppPrice=false&cid=1844104&numberOfBedrooms=&familyMode=false&adults=2&children=0&rooms=1&maxRooms=0&isCalendarCallout=false&childAges=&numberOfGuest=0&missingChildAges=false&travellerType=1&showReviewSubmissionEntry=false&currencyCode=VND&isFreeOccSearch=false&los=1&searchrequestid=616107f0-75f0-4319-923d-cc9a79de71df&checkin=2025-07-10"
    
    # Test date
    test_date = date(2025, 7, 10)
    
    print("🏨 Testing Pullman Saigon Centre Hotel")
    print(f"📅 Date: {test_date}")
    print("=" * 60)
    
    try:
        with AgodaScraper(headless=True) as scraper:
            results = scraper.scrape_hotel_for_dates(hotel_url, [test_date])
            
            if results:
                hotel = results[0]
                print(f"✅ Hotel: {hotel.hotel_name}")
                print(f"📍 Location: {hotel.location}")
                print(f"📅 Check-in: {hotel.check_in_date}")
                print(f"📅 Check-out: {hotel.check_out_date}")
                print(f"🏠 Rooms found: {len(hotel.rooms)}")
                print()
                
                print("💰 PRICING DATA (Expected Format):")
                print("-" * 60)
                
                for i, room in enumerate(hotel.rooms, 1):
                    # Format theo yêu cầu: Room Name - Price VND
                    formatted_display = room.get_formatted_display()
                    print(f"{i:2d}. {formatted_display}")
                
                print()
                print("📊 SUMMARY:")
                print(f"   Total rooms: {len(hotel.rooms)}")
                
                if hotel.rooms:
                    prices = [room.price for room in hotel.rooms if room.price > 0]
                    if prices:
                        min_price = min(prices)
                        max_price = max(prices)
                        avg_price = sum(prices) / len(prices)
                        
                        print(f"   Price range: {format_vnd_price(min_price)} - {format_vnd_price(max_price)}")
                        print(f"   Average price: {format_vnd_price(avg_price)}")
                
                print()
                print("✅ SUCCESS: Data extracted in expected format!")
                
            else:
                print("❌ No data extracted")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_price_formatting():
    """Test price formatting function"""
    print("\n🧪 Testing Price Formatting:")
    print("-" * 40)
    
    test_prices = [
        2896188,
        6044815,
        439000,
        8273602,
        1500000
    ]
    
    for price in test_prices:
        formatted = format_vnd_price(price)
        print(f"{price:>10,} -> {formatted}")

def main():
    """Main test function"""
    print("🔧 AGODA SCRAPER FORMAT TEST")
    print("=" * 60)
    
    # Test price formatting first
    test_price_formatting()
    
    # Test actual scraping
    test_pullman_format()
    
    print("\n" + "=" * 60)
    print("✅ Format test completed!")
    print("\nExpected output format:")
    print("Superior 2 Giường Đơn (Superior 2 Single Beds) - 2.896.188 ₫")

if __name__ == "__main__":
    main()
