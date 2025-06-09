"""
Scheduler for daily Agoda scraping
"""
import schedule
import time
import threading
import signal
import sys
from datetime import datetime, time as dt_time
from typing import List, Callable, Optional
import json
import os

from agoda_scraper import AgodaScraper
from utils import setup_logging
from config import DATA_DIR

class ScrapingScheduler:
    """Scheduler for automated daily scraping"""
    
    def __init__(self, hotel_urls: List[str], schedule_time: str = "09:00"):
        """
        Initialize scheduler
        
        Args:
            hotel_urls: List of Agoda hotel URLs to scrape
            schedule_time: Time to run daily scraping (HH:MM format)
        """
        self.hotel_urls = hotel_urls
        self.schedule_time = schedule_time
        self.logger = setup_logging("scheduler")
        self.running = False
        self.thread = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"Scheduler initialized with {len(hotel_urls)} hotels")
        self.logger.info(f"Daily scraping scheduled for {schedule_time}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def scrape_job(self):
        """Job function to run scraping"""
        try:
            self.logger.info("Starting scheduled scraping job")
            
            with AgodaScraper() as scraper:
                session = scraper.run_daily_scrape(self.hotel_urls)
                
                self.logger.info(f"Scraping job completed. Session ID: {session.session_id}")
                self.logger.info(f"Hotels scraped: {session.success_count}")
                self.logger.info(f"Errors: {session.error_count}")
                
                if session.error_count > 0:
                    self.logger.warning(f"Errors occurred during scraping: {session.errors}")
                
                return session
                
        except Exception as e:
            self.logger.error(f"Error in scraping job: {e}")
            raise
    
    def schedule_daily_scraping(self):
        """Schedule daily scraping at specified time"""
        schedule.clear()  # Clear any existing schedules
        
        schedule.every().day.at(self.schedule_time).do(self.scrape_job)
        
        self.logger.info(f"Daily scraping scheduled for {self.schedule_time}")
    
    def run_once(self):
        """Run scraping once immediately"""
        self.logger.info("Running scraping job once")
        return self.scrape_job()
    
    def start(self):
        """Start the scheduler in a separate thread"""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.schedule_daily_scraping()
        self.running = True
        
        def run_scheduler():
            self.logger.info("Scheduler thread started")
            while self.running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    self.logger.error(f"Error in scheduler thread: {e}")
                    time.sleep(60)
            
            self.logger.info("Scheduler thread stopped")
        
        self.thread = threading.Thread(target=run_scheduler, daemon=True)
        self.thread.start()
        
        self.logger.info("Scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            self.logger.warning("Scheduler is not running")
            return
        
        self.running = False
        schedule.clear()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.logger.info("Scheduler stopped")
    
    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time"""
        jobs = schedule.get_jobs()
        if jobs:
            return jobs[0].next_run
        return None
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.running
    
    def add_hotel_url(self, url: str):
        """Add a new hotel URL to scraping list"""
        if url not in self.hotel_urls:
            self.hotel_urls.append(url)
            self.logger.info(f"Added hotel URL: {url}")
            self.save_config()
    
    def remove_hotel_url(self, url: str):
        """Remove a hotel URL from scraping list"""
        if url in self.hotel_urls:
            self.hotel_urls.remove(url)
            self.logger.info(f"Removed hotel URL: {url}")
            self.save_config()
    
    def update_schedule_time(self, new_time: str):
        """Update the scheduled time"""
        try:
            # Validate time format
            dt_time.fromisoformat(new_time)
            
            self.schedule_time = new_time
            self.logger.info(f"Updated schedule time to: {new_time}")
            
            # Reschedule if running
            if self.running:
                self.schedule_daily_scraping()
            
            self.save_config()
            
        except ValueError:
            self.logger.error(f"Invalid time format: {new_time}. Use HH:MM format.")
            raise
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            config = {
                "hotel_urls": self.hotel_urls,
                "schedule_time": self.schedule_time,
                "last_updated": datetime.now().isoformat()
            }
            
            config_path = os.path.join(DATA_DIR, "scheduler_config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Configuration saved to {config_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
    
    @classmethod
    def load_config(cls, config_path: str = None) -> 'ScrapingScheduler':
        """Load scheduler configuration from file"""
        if config_path is None:
            config_path = os.path.join(DATA_DIR, "scheduler_config.json")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            scheduler = cls(
                hotel_urls=config.get("hotel_urls", []),
                schedule_time=config.get("schedule_time", "09:00")
            )
            
            scheduler.logger.info(f"Configuration loaded from {config_path}")
            return scheduler
            
        except FileNotFoundError:
            scheduler = cls(hotel_urls=[], schedule_time="09:00")
            scheduler.logger.info("No existing configuration found, created new scheduler")
            return scheduler
        
        except Exception as e:
            logger = setup_logging("scheduler")
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def get_status(self) -> dict:
        """Get current scheduler status"""
        return {
            "running": self.running,
            "schedule_time": self.schedule_time,
            "hotel_count": len(self.hotel_urls),
            "next_run": self.get_next_run_time().isoformat() if self.get_next_run_time() else None,
            "hotel_urls": self.hotel_urls
        }

def main():
    """Main function for running scheduler as standalone script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agoda Scraping Scheduler")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--time", help="Schedule time (HH:MM format)", default="09:00")
    parser.add_argument("--run-once", action="store_true", help="Run scraping once and exit")
    parser.add_argument("--add-url", help="Add hotel URL to configuration")
    parser.add_argument("--remove-url", help="Remove hotel URL from configuration")
    parser.add_argument("--list-urls", action="store_true", help="List configured hotel URLs")
    
    args = parser.parse_args()
    
    # Load or create scheduler
    if args.config:
        scheduler = ScrapingScheduler.load_config(args.config)
    else:
        scheduler = ScrapingScheduler.load_config()
    
    # Handle URL management
    if args.add_url:
        scheduler.add_hotel_url(args.add_url)
        print(f"Added URL: {args.add_url}")
        return
    
    if args.remove_url:
        scheduler.remove_hotel_url(args.remove_url)
        print(f"Removed URL: {args.remove_url}")
        return
    
    if args.list_urls:
        print("Configured hotel URLs:")
        for i, url in enumerate(scheduler.hotel_urls, 1):
            print(f"{i}. {url}")
        return
    
    # Update schedule time if provided
    if args.time != "09:00":
        scheduler.update_schedule_time(args.time)
    
    # Run scraping
    if args.run_once:
        print("Running scraping job once...")
        session = scheduler.run_once()
        print(f"Scraping completed. Session ID: {session.session_id}")
    else:
        print(f"Starting scheduler with {len(scheduler.hotel_urls)} hotels...")
        print(f"Daily scraping scheduled for {scheduler.schedule_time}")
        print("Press Ctrl+C to stop")
        
        scheduler.start()
        
        try:
            while scheduler.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            scheduler.stop()

if __name__ == "__main__":
    main()
