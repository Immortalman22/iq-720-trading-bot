import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import logging
from typing import List, Dict, Optional
import json
from pathlib import Path
import os

class ForexNewsFilter:
    def __init__(self, cache_dir: str = None):
        self.logger = logging.getLogger(__name__)
        self.cache_dir = cache_dir or Path(__file__).parent / "cache"
        self.cache_file = self.cache_dir / "news_cache.json"
        self.cached_news = {}
        self._load_cache()

    def _load_cache(self):
        """Load cached news events"""
        try:
            if not self.cache_dir.exists():
                os.makedirs(self.cache_dir)

            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.cached_news = json.load(f)
                
                # Clean old entries
                today = datetime.now().date().isoformat()
                self.cached_news = {
                    date: events for date, events in self.cached_news.items()
                    if date >= today
                }
                self._save_cache()
        except Exception as e:
            self.logger.error(f"Error loading news cache: {e}")
            self.cached_news = {}

    def _save_cache(self):
        """Save news events to cache"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cached_news, f)
        except Exception as e:
            self.logger.error(f"Error saving news cache: {e}")

    def fetch_economic_calendar(self, days: int = 1) -> List[Dict]:
        """Fetch economic news events affecting EUR/USD"""
        try:
            # First check cache
            date_key = datetime.now().date().isoformat()
            if date_key in self.cached_news:
                return self.cached_news[date_key]

            # If not in cache, fetch from API
            # Note: In production, replace with your preferred forex news API
            # Example using ForexFactory API (you'll need to sign up for API access)
            url = "https://api.forexfactory.com/v1/calendar"
            params = {
                "currency": "EUR,USD",
                "importance": "high",
                "days": days
            }
            
            # Simulated response for development
            # In production, use: response = requests.get(url, params=params)
            events = self._get_sample_events()
            
            # Cache the results
            self.cached_news[date_key] = events
            self._save_cache()
            
            return events

        except Exception as e:
            self.logger.error(f"Error fetching economic calendar: {e}")
            return []

    def is_news_time(self, timestamp: datetime, buffer_minutes: int = 15) -> bool:
        """Check if given time is within news event buffer"""
        try:
            # Convert timestamp to UTC if it's not
            if timestamp.tzinfo is None:
                timestamp = pytz.utc.localize(timestamp)
            
            # Get today's events
            events = self.fetch_economic_calendar()
            
            # Check each event
            for event in events:
                event_time = datetime.fromisoformat(event['time'])
                if event_time.tzinfo is None:
                    event_time = pytz.utc.localize(event_time)
                
                time_diff = abs((timestamp - event_time).total_seconds() / 60)
                
                # If within buffer period of any event
                if time_diff <= buffer_minutes:
                    self.logger.info(f"News event detected: {event['title']} at {event_time}")
                    return True
            
            return False

        except Exception as e:
            self.logger.error(f"Error checking news time: {e}")
            # If there's an error, better to assume it's news time to be safe
            return True

    def _get_sample_events(self) -> List[Dict]:
        """Generate sample news events for testing"""
        now = datetime.now(pytz.utc)
        
        return [
            {
                'title': 'ECB Interest Rate Decision',
                'currency': 'EUR',
                'importance': 'high',
                'time': (now + timedelta(minutes=30)).isoformat(),
                'forecast': '4.50%',
                'previous': '4.50%'
            },
            {
                'title': 'US Non-Farm Payrolls',
                'currency': 'USD',
                'importance': 'high',
                'time': (now + timedelta(hours=2)).isoformat(),
                'forecast': '180K',
                'previous': '175K'
            }
        ]

    def get_upcoming_events(self, hours: int = 24) -> List[Dict]:
        """Get list of upcoming high-impact news events"""
        events = self.fetch_economic_calendar()
        now = datetime.now(pytz.utc)
        
        # Filter events within specified hours
        upcoming = []
        for event in events:
            event_time = datetime.fromisoformat(event['time'])
            if event_time > now and event_time <= now + timedelta(hours=hours):
                upcoming.append({
                    'title': event['title'],
                    'currency': event['currency'],
                    'time': event_time.strftime('%Y-%m-%d %H:%M UTC'),
                    'importance': event['importance']
                })
        
        return upcoming

    def get_next_event(self) -> Optional[Dict]:
        """Get the next upcoming news event"""
        upcoming = self.get_upcoming_events()
        return upcoming[0] if upcoming else None
