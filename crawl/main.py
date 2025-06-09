#!/usr/bin/env python3
"""
Main entry point for Agoda scraper
"""
import argparse
import sys
import os
from datetime import datetime, date
from typing import List

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agoda_scraper import AgodaScraper
from scheduler import ScrapingScheduler
from utils import setup_logging, validate_url
from config import get_target_dates, DATA_DIR

def scrape_single_hotel(url: str, dates: List[date] = None) -> None:
    """Scrape a single hotel for specified dates"""
    logger = setup_logging("main")
    
    if not validate_url(url):
        logger.error(f"Invalid Agoda URL: {url}")
        return
    
    if dates is None:
        dates = get_target_dates()
    
    logger.info(f"Scraping hotel: {url}")
    logger.info(f"Target dates: {[d.isoformat() for d in dates]}")
    
    try:
        with AgodaScraper() as scraper:
            results = scraper.scrape_hotel_for_dates(url, dates)
            
            if results:
                logger.info(f"Successfully scraped {len(results)} date combinations")
                for result in results:
                    logger.info(f"  - {result.hotel_name}: {result.check_in_date} to {result.check_out_date}")
                    logger.info(f"    Rooms found: {len(result.rooms)}")
            else:
                logger.warning("No data was scraped")
                
    except Exception as e:
        logger.error(f"Error scraping hotel: {e}")

def scrape_multiple_hotels(urls: List[str], dates: List[date] = None) -> None:
    """Scrape multiple hotels"""
    logger = setup_logging("main")
    
    if dates is None:
        dates = get_target_dates()
    
    logger.info(f"Scraping {len(urls)} hotels")
    logger.info(f"Target dates: {[d.isoformat() for d in dates]}")
    
    try:
        with AgodaScraper() as scraper:
            session = scraper.scrape_multiple_hotels(urls, dates)
            
            logger.info(f"Scraping session completed")
            logger.info(f"Session ID: {session.session_id}")
            logger.info(f"Hotels successfully scraped: {session.success_count}")
            logger.info(f"Errors encountered: {session.error_count}")
            
            if session.error_count > 0:
                logger.warning("Errors occurred:")
                for error in session.errors:
                    logger.warning(f"  - {error}")
                    
    except Exception as e:
        logger.error(f"Error in scraping session: {e}")

def start_scheduler(schedule_time: str = "09:00", config_file: str = None) -> None:
    """Start the daily scheduler"""
    logger = setup_logging("main")
    
    try:
        if config_file:
            scheduler = ScrapingScheduler.load_config(config_file)
        else:
            scheduler = ScrapingScheduler.load_config()
        
        if not scheduler.hotel_urls:
            logger.error("No hotel URLs configured. Add URLs using --add-url option first.")
            return
        
        if schedule_time != "09:00":
            scheduler.update_schedule_time(schedule_time)
        
        logger.info(f"Starting scheduler with {len(scheduler.hotel_urls)} hotels")
        logger.info(f"Daily scraping scheduled for {scheduler.schedule_time}")
        logger.info("Press Ctrl+C to stop")
        
        scheduler.start()
        
        try:
            while scheduler.is_running():
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down scheduler...")
            scheduler.stop()
            
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")

def manage_urls(action: str, url: str = None, config_file: str = None) -> None:
    """Manage hotel URLs in configuration"""
    logger = setup_logging("main")
    
    try:
        if config_file:
            scheduler = ScrapingScheduler.load_config(config_file)
        else:
            scheduler = ScrapingScheduler.load_config()
        
        if action == "add" and url:
            if not validate_url(url):
                logger.error(f"Invalid Agoda URL: {url}")
                return
            scheduler.add_hotel_url(url)
            print(f"Added URL: {url}")
            
        elif action == "remove" and url:
            scheduler.remove_hotel_url(url)
            print(f"Removed URL: {url}")
            
        elif action == "list":
            print(f"Configured hotel URLs ({len(scheduler.hotel_urls)}):")
            for i, hotel_url in enumerate(scheduler.hotel_urls, 1):
                print(f"{i}. {hotel_url}")
                
        elif action == "clear":
            scheduler.hotel_urls.clear()
            scheduler.save_config()
            print("Cleared all hotel URLs")
            
        else:
            logger.error(f"Invalid action or missing URL: {action}")
            
    except Exception as e:
        logger.error(f"Error managing URLs: {e}")

def show_status(config_file: str = None) -> None:
    """Show current scheduler status"""
    try:
        if config_file:
            scheduler = ScrapingScheduler.load_config(config_file)
        else:
            scheduler = ScrapingScheduler.load_config()
        
        status = scheduler.get_status()
        
        print("Scheduler Status:")
        print(f"  Running: {status['running']}")
        print(f"  Schedule Time: {status['schedule_time']}")
        print(f"  Hotel Count: {status['hotel_count']}")
        print(f"  Next Run: {status['next_run'] or 'Not scheduled'}")
        
        if status['hotel_urls']:
            print("\nConfigured Hotels:")
            for i, url in enumerate(status['hotel_urls'], 1):
                print(f"  {i}. {url}")
        else:
            print("\nNo hotels configured")
            
    except Exception as e:
        print(f"Error getting status: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Agoda Hotel Pricing Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape a single hotel
  python main.py --url "https://www.agoda.com/hotel/example"
  
  # Start daily scheduler
  python main.py --schedule
  
  # Add hotel to configuration
  python main.py --add-url "https://www.agoda.com/hotel/example"
  
  # List configured hotels
  python main.py --list-urls
  
  # Run scraping once for all configured hotels
  python main.py --run-once
        """
    )
    
    # Main actions
    parser.add_argument("--url", help="Single hotel URL to scrape")
    parser.add_argument("--urls-file", help="File containing hotel URLs (one per line)")
    parser.add_argument("--schedule", action="store_true", help="Start daily scheduler")
    parser.add_argument("--run-once", action="store_true", help="Run scraping once for all configured hotels")
    
    # URL management
    parser.add_argument("--add-url", help="Add hotel URL to configuration")
    parser.add_argument("--remove-url", help="Remove hotel URL from configuration")
    parser.add_argument("--list-urls", action="store_true", help="List configured hotel URLs")
    parser.add_argument("--clear-urls", action="store_true", help="Clear all configured hotel URLs")
    
    # Configuration
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--schedule-time", default="09:00", help="Daily schedule time (HH:MM format)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--status", action="store_true", help="Show scheduler status")
    
    # Date options
    parser.add_argument("--dates", nargs="+", help="Specific dates to scrape (YYYY-MM-DD format)")
    
    args = parser.parse_args()
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Parse dates if provided
    target_dates = None
    if args.dates:
        try:
            target_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in args.dates]
        except ValueError as e:
            print(f"Error parsing dates: {e}")
            return
    
    # Handle different actions
    if args.status:
        show_status(args.config)
        
    elif args.add_url:
        manage_urls("add", args.add_url, args.config)
        
    elif args.remove_url:
        manage_urls("remove", args.remove_url, args.config)
        
    elif args.list_urls:
        manage_urls("list", config_file=args.config)
        
    elif args.clear_urls:
        manage_urls("clear", config_file=args.config)
        
    elif args.url:
        scrape_single_hotel(args.url, target_dates)
        
    elif args.urls_file:
        try:
            with open(args.urls_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            scrape_multiple_hotels(urls, target_dates)
        except FileNotFoundError:
            print(f"File not found: {args.urls_file}")
        except Exception as e:
            print(f"Error reading URLs file: {e}")
            
    elif args.run_once:
        try:
            scheduler = ScrapingScheduler.load_config(args.config)
            if not scheduler.hotel_urls:
                print("No hotel URLs configured. Add URLs using --add-url option first.")
                return
            session = scheduler.run_once()
            print(f"Scraping completed. Session ID: {session.session_id}")
        except Exception as e:
            print(f"Error running scraping: {e}")
            
    elif args.schedule:
        start_scheduler(args.schedule_time, args.config)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
