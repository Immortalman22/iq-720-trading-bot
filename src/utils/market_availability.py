"""
Market Availability Manager for IQ Option Trading Bot

This module checks whether markets are currently available for trading on IQ Option platform,
differentiates between regular and OTC markets, and ensures signals are only generated
for available markets.
"""

import logging
from datetime import datetime, time, timedelta
import os
import pytz

try:
    import yaml
except ImportError:
    import subprocess
    import sys
    print("Installing pyyaml...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyyaml'])
    import yaml

logger = logging.getLogger("MarketAvailabilityManager")

class MarketAvailabilityManager:
    """
    Manages market availability for IQ Option platform
    
    This class helps determine:
    1. Whether a market is currently available for trading
    2. If a market is regular or OTC (Over-The-Counter)
    3. Trading hours for different market types
    """
    
    def __init__(self, config_file=None):
        """
        Initialize the market availability manager
        
        Args:
            config_file: Path to market schedule configuration file
        """
        # Set default config file path if not provided
        self.config_file = config_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'market_schedule.yaml'
        )
        
        # Initialize market availability information
        self.initialize_market_info()
        
    def initialize_market_info(self):
        """
        Initialize market trading hours and availability from config file
        """
        # Default trading hours in case config file is not available
        self.forex_trading_hours = {
            'regular': {
                'weekday_open': time(0, 0),  # 00:00 UTC Monday
                'weekday_close': time(23, 59),  # 23:59 UTC Friday
                'weekend_open': None,  # Closed on weekends
                'weekend_close': None,  # Closed on weekends
            },
            'otc': {
                'weekday_open': time(0, 0),  # 00:00 UTC
                'weekday_close': time(23, 59),  # 23:59 UTC
                'weekend_open': time(0, 0),  # 00:00 UTC
                'weekend_close': time(23, 59),  # 23:59 UTC
            }
        }
        
        # Default OTC availability
        self.otc_pairs = [
            'EUR/USD', 'GBP/USD', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD', 
            'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'USD/JPY'
        ]
        
        # Try to load configuration from file
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as file:
                    config = yaml.safe_load(file)
                    
                # Parse trading hours
                if 'forex' in config:
                    forex_config = config['forex']
                    
                    # Parse regular market hours
                    if 'regular' in forex_config:
                        reg_config = forex_config['regular']
                        
                        # Parse Sunday open time (forex week start)
                        if 'sunday_open' in reg_config:
                            hours, minutes = map(int, reg_config['sunday_open'].split(':'))
                            self.forex_trading_hours['regular']['weekday_open'] = time(hours, minutes)
                            
                        # Parse Friday close time (forex week end)
                        if 'friday_close' in reg_config:
                            hours, minutes = map(int, reg_config['friday_close'].split(':'))
                            self.forex_trading_hours['regular']['weekday_close'] = time(hours, minutes)
                            
                        # Weekend availability
                        if 'weekend' in reg_config and reg_config['weekend']:
                            if 'weekend_open' in reg_config and 'weekend_close' in reg_config:
                                open_hours, open_minutes = map(int, reg_config['weekend_open'].split(':'))
                                close_hours, close_minutes = map(int, reg_config['weekend_close'].split(':'))
                                self.forex_trading_hours['regular']['weekend_open'] = time(open_hours, open_minutes)
                                self.forex_trading_hours['regular']['weekend_close'] = time(close_hours, close_minutes)
                    
                    # Parse OTC market hours
                    if 'otc' in forex_config:
                        otc_config = forex_config['otc']
                        
                        # Parse weekday times
                        if 'sunday_open' in otc_config:
                            hours, minutes = map(int, otc_config['sunday_open'].split(':'))
                            self.forex_trading_hours['otc']['weekday_open'] = time(hours, minutes)
                            
                        if 'friday_close' in otc_config:
                            hours, minutes = map(int, otc_config['friday_close'].split(':'))
                            self.forex_trading_hours['otc']['weekday_close'] = time(hours, minutes)
                            
                        # Weekend availability
                        if 'weekend' in otc_config and otc_config['weekend']:
                            if 'weekend_open' in otc_config and 'weekend_close' in otc_config:
                                open_hours, open_minutes = map(int, otc_config['weekend_open'].split(':'))
                                close_hours, close_minutes = map(int, otc_config['weekend_close'].split(':'))
                                self.forex_trading_hours['otc']['weekend_open'] = time(open_hours, open_minutes)
                                self.forex_trading_hours['otc']['weekend_close'] = time(close_hours, close_minutes)
                
                # Parse pair availability
                if 'pairs' in config:
                    pairs_config = config['pairs']
                    
                    # Build list of OTC pairs from configuration
                    self.otc_pairs = [
                        pair for pair, settings in pairs_config.items()
                        if 'otc' in settings and settings['otc']
                    ]
                    
                    # Build full pair availability dictionary
                    self.pair_availability = {}
                    for pair, settings in pairs_config.items():
                        self.pair_availability[pair] = {
                            'regular': settings.get('regular', False),
                            'otc': settings.get('otc', False)
                        }
                        
                logger.info(f"Market schedule loaded from {self.config_file}")
                logger.info(f"OTC pairs available: {len(self.otc_pairs)}")
                
        except Exception as e:
            logger.error(f"Error loading market schedule: {e}")
            logger.warning("Using default market schedule configuration")
        
        # Market open/close status caching (to avoid excessive checking)
        self.last_check_time = {}
        self.market_status_cache = {}
        
        logger.info("Market availability manager initialized")
        
    def is_weekend(self, dt=None):
        """
        Check if the given datetime is on a weekend
        
        Args:
            dt: Datetime object to check, defaults to current time
            
        Returns:
            bool: True if weekend, False otherwise
        """
        if dt is None:
            dt = datetime.now(pytz.UTC)
            
        # Saturday = 5, Sunday = 6
        return dt.weekday() >= 5
    
    def is_market_open(self, pair, market_type=None):
        """
        Check if a market is currently open for trading
        
        Args:
            pair: Trading pair to check
            market_type: 'regular' or 'otc', if None will check both
            
        Returns:
            tuple: (is_open, market_type, message)
        """
        # Use cached result if checked recently (within 5 minutes)
        cache_key = f"{pair}_{market_type}"
        now = datetime.now(pytz.UTC)
        
        if (cache_key in self.last_check_time and 
                (now - self.last_check_time[cache_key]).total_seconds() < 300):
            return self.market_status_cache[cache_key]
        
        # Check pair availability from configuration
        if hasattr(self, 'pair_availability') and pair in self.pair_availability:
            pair_config = self.pair_availability[pair]
            regular_available = pair_config.get('regular', False)
            otc_available = pair_config.get('otc', False)
        else:
            # Fall back to simple list check
            regular_available = True  # Assume regular markets are available for all pairs
            otc_available = pair in self.otc_pairs
        
        # Get current day and time
        current_time = now.time()
        is_weekend = self.is_weekend(now)
        
        # If market type is not specified, determine based on time and availability
        if market_type is None:
            if is_weekend:
                # On weekends, only OTC is available if supported
                market_type = 'otc' if otc_available else None
            else:
                # During weekdays, prefer regular market if available, otherwise OTC
                if regular_available:
                    market_type = 'regular'
                elif otc_available:
                    market_type = 'otc'
                else:
                    market_type = None
        
        # If we couldn't determine a market type or the specified one is invalid
        if market_type not in ['regular', 'otc']:
            return (False, None, f"No valid market type available for {pair}")
        
        # Check if the specified market type is available for this pair
        if market_type == 'regular' and not regular_available:
            return (False, None, f"Regular market not available for {pair}")
        elif market_type == 'otc' and not otc_available:
            return (False, None, f"OTC market not available for {pair}")
            
        # Get trading hours for the market type
        trading_hours = self.forex_trading_hours[market_type]
        
        # Check if market is open based on day and time
        if is_weekend:
            # Weekend logic
            if trading_hours['weekend_open'] is None:
                is_open = False
                message = f"{pair} {market_type} market is closed on weekends"
            else:
                is_open = (trading_hours['weekend_open'] <= current_time <= trading_hours['weekend_close'])
                message = f"{pair} {market_type} market is {'open' if is_open else 'closed'} on weekends"
        else:
            # Weekday logic
            if trading_hours['weekday_open'] is None:
                is_open = False
                message = f"{pair} {market_type} market is not available on weekdays"
            else:
                # For most forex markets, if open_time < close_time, it's straightforward
                if trading_hours['weekday_open'] < trading_hours['weekday_close']:
                    is_open = (trading_hours['weekday_open'] <= current_time <= trading_hours['weekday_close'])
                else:
                    # Handle markets that span across midnight
                    is_open = (trading_hours['weekday_open'] <= current_time or 
                               current_time <= trading_hours['weekday_close'])
                
                message = f"{pair} {market_type} market is {'open' if is_open else 'closed'}"
        
        # Cache the result
        self.last_check_time[cache_key] = now
        self.market_status_cache[cache_key] = (is_open, market_type, message)
        
        return (is_open, market_type, message)
    
    def get_best_available_market(self, pair):
        """
        Get the best available market type for a pair
        
        Args:
            pair: Trading pair to check
            
        Returns:
            tuple: (is_available, market_type, message)
        """
        # First check if the regular market is open
        regular_status = self.is_market_open(pair, 'regular')
        if regular_status[0]:
            return regular_status
            
        # If regular market is closed, try OTC
        otc_status = self.is_market_open(pair, 'otc')
        if otc_status[0]:
            return otc_status
            
        # No markets available
        return (False, None, f"No markets available for {pair} at this time")
    
    def get_market_status_summary(self):
        """
        Get a summary of all market availability
        
        Returns:
            dict: Summary of market availability
        """
        summary = {
            'regular_open': [],
            'otc_open': [],
            'all_closed': [],
            'timestamp': datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        # Check standard forex pairs
        for pair in self.otc_pairs:
            status = self.get_best_available_market(pair)
            if status[0]:
                if status[1] == 'regular':
                    summary['regular_open'].append(pair)
                else:
                    summary['otc_open'].append(pair)
            else:
                summary['all_closed'].append(pair)
        
        return summary
