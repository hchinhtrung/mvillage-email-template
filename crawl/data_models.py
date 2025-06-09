"""
Data models for Agoda scraper
"""
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import json

@dataclass
class RoomInfo:
    """Data model for room information"""
    room_type: str
    price: float
    currency: str
    availability: bool
    max_guests: Optional[int] = None
    bed_type: Optional[str] = None
    room_size: Optional[str] = None
    amenities: Optional[List[str]] = None
    cancellation_policy: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class HotelPricing:
    """Data model for hotel pricing information"""
    hotel_name: str
    hotel_id: Optional[str]
    location: str
    check_in_date: date
    check_out_date: date
    rooms: List[RoomInfo]
    rating: Optional[float] = None
    review_count: Optional[int] = None
    hotel_url: Optional[str] = None
    scraped_at: datetime = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert date objects to strings for JSON serialization
        data['check_in_date'] = self.check_in_date.isoformat()
        data['check_out_date'] = self.check_out_date.isoformat()
        data['scraped_at'] = self.scraped_at.isoformat()
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

@dataclass
class ScrapingSession:
    """Data model for a complete scraping session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    hotels_scraped: List[HotelPricing]
    target_dates: List[date]
    success_count: int = 0
    error_count: int = 0
    errors: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def add_hotel(self, hotel: HotelPricing):
        """Add a hotel to the session"""
        self.hotels_scraped.append(hotel)
        self.success_count += 1
    
    def add_error(self, error: str):
        """Add an error to the session"""
        self.errors.append(error)
        self.error_count += 1
    
    def finish_session(self):
        """Mark the session as finished"""
        self.end_time = datetime.now()
    
    def get_duration(self) -> Optional[float]:
        """Get session duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert datetime and date objects to strings
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        data['target_dates'] = [d.isoformat() for d in self.target_dates]
        data['hotels_scraped'] = [hotel.to_dict() for hotel in self.hotels_scraped]
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

class DataExporter:
    """Utility class for exporting scraped data"""
    
    @staticmethod
    def export_to_json(data: ScrapingSession, filepath: str):
        """Export scraping session to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(data.to_json())
    
    @staticmethod
    def export_to_csv(data: ScrapingSession, filepath: str):
        """Export scraping session to CSV file"""
        import pandas as pd
        
        # Flatten the data for CSV export
        rows = []
        for hotel in data.hotels_scraped:
            base_data = {
                'session_id': data.session_id,
                'scraped_at': hotel.scraped_at.isoformat(),
                'hotel_name': hotel.hotel_name,
                'hotel_id': hotel.hotel_id,
                'location': hotel.location,
                'check_in_date': hotel.check_in_date.isoformat(),
                'check_out_date': hotel.check_out_date.isoformat(),
                'rating': hotel.rating,
                'review_count': hotel.review_count,
                'hotel_url': hotel.hotel_url
            }
            
            for room in hotel.rooms:
                row = base_data.copy()
                row.update({
                    'room_type': room.room_type,
                    'price': room.price,
                    'currency': room.currency,
                    'availability': room.availability,
                    'max_guests': room.max_guests,
                    'bed_type': room.bed_type,
                    'room_size': room.room_size,
                    'amenities': ', '.join(room.amenities) if room.amenities else None,
                    'cancellation_policy': room.cancellation_policy
                })
                rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding='utf-8')
        return df
