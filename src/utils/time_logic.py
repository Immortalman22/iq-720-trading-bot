"""
Time-based logic handler for different market types and sessions.
"""
from datetime import datetime, time, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging
import pytz

class TimeLogic:
    """
    Manages time-based logic for different market types and trading sessions.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Market types
        self.market_types = {
            'forex': {
                'description': 'Foreign Exchange',
                'hours': '24/5',
                'timezone': 'UTC'
            },
            'digital': {
                'description': 'Digital Options',
                'hours': '24/7',
                'timezone': 'UTC'
            },
            'otc': {
                'description': 'Over-The-Counter',
                'hours': 'Weekend',
                'timezone': 'UTC'
            },
            'stocks': {
                'description': 'Stock Markets',
                'hours': 'Exchange-dependent',
                'timezone': 'Variable'
            }
        }
        
        # Trading sessions (all times in UTC)
        self.sessions = {
            'sydney': {
                'start': time(22, 0),  # 22:00 UTC
                'end': time(7, 0),     # 07:00 UTC
                'spans_midnight': True,
                'description': 'Sydney/Wellington Session',
                'best_pairs': ['AUD/USD', 'AUD/JPY', 'NZD/USD', 'AUD/NZD']
            },
            'tokyo': {
                'start': time(0, 0),   # 00:00 UTC
                'end': time(9, 0),     # 09:00 UTC
                'spans_midnight': False,
                'description': 'Tokyo Session',
                'best_pairs': ['USD/JPY', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY']
            },
            'london': {
                'start': time(8, 0),   # 08:00 UTC
                'end': time(17, 0),    # 17:00 UTC
                'spans_midnight': False,
                'description': 'London/European Session',
                'best_pairs': ['EUR/USD', 'GBP/USD', 'EUR/GBP', 'EUR/CHF']
            },
            'new_york': {
                'start': time(13, 0),  # 13:00 UTC
                'end': time(22, 0),    # 22:00 UTC
                'spans_midnight': False,
                'description': 'New York/US Session',
                'best_pairs': ['EUR/USD', 'USD/CAD', 'USD/CHF', 'GBP/USD']
            },
            'overlap_london_ny': {
                'start': time(13, 0),  # 13:00 UTC
                'end': time(17, 0),    # 17:00 UTC
                'spans_midnight': False,
                'description': 'London-New York Overlap',
                'best_pairs': ['EUR/USD', 'GBP/USD', 'USD/CHF', 'USD/JPY']
            },
            'overlap_tokyo_london': {
                'start': time(8, 0),   # 08:00 UTC
                'end': time(9, 0),     # 09:00 UTC
                'spans_midnight': False,
                'description': 'Tokyo-London Overlap',
                'best_pairs': ['EUR/JPY', 'GBP/JPY']
            }
        }
        
        # Weekend OTC market times
        self.otc_times = {
            'start': [
                (time(0, 0), 'Saturday'),  # Saturday 00:00 UTC
            ],
            'end': [
                (time(23, 59, 59), 'Sunday')  # Sunday 23:59:59 UTC
            ]
        }
        
        # Forex market open/close times
        self.forex_times = {
            'open': [
                (time(22, 0), 'Sunday')   # Sunday 22:00 UTC
            ],
            'close': [
                (time(22, 0), 'Friday')   # Friday 22:00 UTC
            ]
        }
        
        # Initialize timezone
        self.timezone = pytz.timezone('UTC')
        
    def get_current_market_type(self, timestamp: Optional[datetime] = None) -> str:
        """
        Determine the current market type based on time.
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            Market type ('forex', 'digital', 'otc', or 'stocks')
        """
        timestamp = timestamp or datetime.now(self.timezone)
        
        # Check if it's weekend (OTC trading)
        if timestamp.weekday() >= 5:  # Saturday (5) or Sunday (6)
            # Sunday after 22:00 is regular forex
            if timestamp.weekday() == 6 and timestamp.time() >= time(22, 0):
                return 'forex'
            return 'otc'
            
        # Check if it's outside forex trading hours (Friday after 22:00)
        if timestamp.weekday() == 4 and timestamp.time() >= time(22, 0):
            return 'digital'
            
        # Default to forex during weekdays
        return 'forex'
        
    def get_current_session(self, timestamp: Optional[datetime] = None) -> List[str]:
        """
        Get current trading session(s).
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            List of active sessions
        """
        timestamp = timestamp or datetime.now(self.timezone)
        current_time = timestamp.time()
        
        active_sessions = []
        
        for session_name, session_info in self.sessions.items():
            start_time = session_info['start']
            end_time = session_info['end']
            spans_midnight = session_info['spans_midnight']
            
            # Check if current time is within session
            in_session = False
            
            if spans_midnight:
                # Session spans across midnight
                if current_time >= start_time or current_time <= end_time:
                    in_session = True
            else:
                # Regular session within same day
                if start_time <= current_time <= end_time:
                    in_session = True
                    
            if in_session:
                active_sessions.append(session_name)
                
        return active_sessions
        
    def get_market_description(self, timestamp: Optional[datetime] = None) -> str:
        """
        Get a description of the current market conditions.
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            String description of current market type and session
        """
        timestamp = timestamp or datetime.now(self.timezone)
        
        market_type = self.get_current_market_type(timestamp)
        sessions = self.get_current_session(timestamp)
        
        market_desc = self.market_types[market_type]['description']
        
        if not sessions:
            return f"{market_desc} (No active major session)"
            
        session_descs = [self.sessions[s]['description'] for s in sessions]
        return f"{market_desc} ({', '.join(session_descs)})"
        
    def get_optimal_pairs_for_time(self, timestamp: Optional[datetime] = None) -> List[str]:
        """
        Get the optimal currency pairs to trade at the current time.
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            List of optimal currency pairs for current session
        """
        timestamp = timestamp or datetime.now(self.timezone)
        sessions = self.get_current_session(timestamp)
        
        # No active sessions
        if not sessions:
            return []
            
        # Collect pairs from all active sessions
        optimal_pairs = set()
        for session in sessions:
            optimal_pairs.update(self.sessions[session]['best_pairs'])
            
        return list(optimal_pairs)
        
    def is_forex_market_open(self, timestamp: Optional[datetime] = None) -> bool:
        """
        Check if the forex market is currently open.
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            True if forex market is open
        """
        timestamp = timestamp or datetime.now(self.timezone)
        market_type = self.get_current_market_type(timestamp)
        
        return market_type == 'forex'
        
    def get_time_to_next_session(self, timestamp: Optional[datetime] = None) -> Tuple[str, timedelta]:
        """
        Get the time until the next trading session starts.
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            Tuple of (session_name, time_until_session)
        """
        timestamp = timestamp or datetime.now(self.timezone)
        current_time = timestamp.time()
        
        # Check if we're already in a session
        current_sessions = self.get_current_session(timestamp)
        if current_sessions:
            return (current_sessions[0], timedelta(0))
            
        # Find the next session
        next_session = None
        min_time_delta = timedelta(days=1)
        
        for session_name, session_info in self.sessions.items():
            start_time = session_info['start']
            
            # Calculate time until session starts
            if start_time > current_time:
                # Later today
                session_datetime = datetime.combine(timestamp.date(), start_time)
                delta = session_datetime - timestamp
            else:
                # Tomorrow
                tomorrow = timestamp + timedelta(days=1)
                session_datetime = datetime.combine(tomorrow.date(), start_time)
                delta = session_datetime - timestamp
                
            if delta < min_time_delta:
                min_time_delta = delta
                next_session = session_name
                
        return (next_session, min_time_delta)
        
    def get_session_volatility_factor(self, timestamp: Optional[datetime] = None) -> float:
        """
        Get a volatility factor based on the current session.
        Higher values indicate typically more volatile sessions.
        
        Args:
            timestamp: Optional datetime to check (defaults to current time)
            
        Returns:
            Volatility factor (0.5-1.5)
        """
        timestamp = timestamp or datetime.now(self.timezone)
        sessions = self.get_current_session(timestamp)
        
        # Base volatility
        volatility = 1.0
        
        # No active sessions - lower volatility
        if not sessions:
            return 0.5
            
        # Session-specific adjustments
        for session in sessions:
            if session == 'london':
                volatility *= 1.2
            elif session == 'new_york':
                volatility *= 1.1
            elif session == 'overlap_london_ny':
                volatility *= 1.5  # Highest volatility during overlap
                
        return min(1.5, volatility)  # Cap at 1.5
        
    def format_trading_signal_time_context(self, signal_data: Dict) -> str:
        """
        Format time context information for a trading signal.
        
        Args:
            signal_data: Signal data dictionary
            
        Returns:
            String with formatted time context information
        """
        timestamp = signal_data.get('timestamp') or datetime.now(self.timezone)
        
        market_type = self.get_current_market_type(timestamp)
        sessions = self.get_current_session(timestamp)
        
        # Format market type
        market_info = self.market_types[market_type]['description']
        
        # Format session information
        session_info = "No active major session"
        if sessions:
            session_info = ", ".join([self.sessions[s]['description'] for s in sessions])
            
        # Format time
        time_str = timestamp.strftime("%H:%M:%S %Z")
        
        return f"Market: {market_info} | Session: {session_info} | Time: {time_str}"
