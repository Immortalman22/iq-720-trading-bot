"""
Dynamic asset selection based on volatility and market conditions.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime, time, timedelta
import logging
import talib

class DynamicAssetSelector:
    """
    Selects the best assets to trade based on volatility and market conditions.
    """
    
    def __init__(self, max_active_pairs: int = 5):
        self.logger = logging.getLogger(__name__)
        self.max_active_pairs = max_active_pairs
        self.price_history = {}  # Store recent price data for volatility calculation
        self.volatility_metrics = {}  # Store volatility metrics for each pair
        self.tradable_pairs = set()  # Currently tradable pairs
        self.last_selection_time = None
        self.selection_interval = timedelta(hours=4)  # Update selection every 4 hours
        
        # Market session times (UTC)
        self.sessions = {
            'sydney': (time(22, 0), time(7, 0)),   # 22:00-07:00 UTC
            'tokyo': (time(0, 0), time(9, 0)),     # 00:00-09:00 UTC
            'london': (time(8, 0), time(17, 0)),   # 08:00-17:00 UTC
            'new_york': (time(13, 0), time(22, 0)) # 13:00-22:00 UTC
        }
        
        # All supported pairs
        self.all_pairs = [
            # Major pairs
            'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'USD/CAD', 'NZD/USD',
            # Minor pairs
            'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'EUR/CHF', 'EUR/CAD', 'EUR/AUD', 'GBP/CHF',
            'GBP/AUD', 'AUD/JPY', 'AUD/CAD', 'AUD/NZD', 'AUD/CHF', 'CAD/JPY', 'NZD/JPY'
        ]
        
    def update_price_data(self, pair: str, ohlc: Dict, timestamp: datetime) -> None:
        """
        Update price history for volatility calculations.
        
        Args:
            pair: Currency pair
            ohlc: Open, High, Low, Close prices
            timestamp: Timestamp of the candle
        """
        if pair not in self.price_history:
            self.price_history[pair] = []
            
        # Add OHLC data
        self.price_history[pair].append({
            'timestamp': timestamp,
            'open': ohlc['open'],
            'high': ohlc['high'],
            'low': ohlc['low'],
            'close': ohlc['close']
        })
        
        # Keep last 100 candles for calculations
        if len(self.price_history[pair]) > 100:
            self.price_history[pair] = self.price_history[pair][-100:]
            
        # Check if it's time to update pair selection
        current_time = datetime.now()
        if (self.last_selection_time is None or 
            current_time - self.last_selection_time > self.selection_interval):
            self._update_volatility_metrics()
            self._select_tradable_pairs()
            self.last_selection_time = current_time
            
    def _update_volatility_metrics(self) -> None:
        """Calculate volatility metrics for all pairs with enough data."""
        for pair, candles in self.price_history.items():
            if len(candles) < 20:  # Need at least 20 candles
                continue
                
            # Extract high/low prices for ATR calculation
            highs = np.array([c['high'] for c in candles])
            lows = np.array([c['low'] for c in candles])
            closes = np.array([c['close'] for c in candles])
            
            # Calculate ATR (Average True Range)
            atr = talib.ATR(highs, lows, closes, timeperiod=14)
            
            # Calculate percentage volatility (ATR / Price * 100)
            current_price = closes[-1]
            percentage_volatility = (atr[-1] / current_price) * 100
            
            # Calculate price range as percentage
            price_range = (np.max(highs[-20:]) - np.min(lows[-20:])) / current_price * 100
            
            # Calculate standard deviation of returns
            returns = np.diff(closes) / closes[:-1] * 100
            std_dev = np.std(returns)
            
            # Store metrics
            self.volatility_metrics[pair] = {
                'atr': atr[-1],
                'percentage_volatility': percentage_volatility,
                'price_range': price_range,
                'std_dev': std_dev,
                'composite_score': 0.5 * percentage_volatility + 0.3 * std_dev + 0.2 * price_range,
                'last_updated': datetime.now()
            }
            
        self.logger.debug(f"Updated volatility metrics for {len(self.volatility_metrics)} pairs")
            
    def _select_tradable_pairs(self) -> None:
        """Select the best pairs to trade based on volatility and market session."""
        if not self.volatility_metrics:
            self.logger.warning("No volatility metrics available for pair selection")
            return
            
        current_time = datetime.now().time()
        current_session = self._get_current_session(current_time)
        
        # Get pairs sorted by volatility
        sorted_pairs = sorted(
            self.volatility_metrics.keys(),
            key=lambda p: self.volatility_metrics[p]['composite_score'],
            reverse=True
        )
        
        # Add session-specific pairs
        session_pairs = set()
        if current_session:
            session_pairs = self._get_session_specific_pairs(current_session)
            
        # Combine high volatility pairs with session-specific pairs
        high_vol_pairs = set(sorted_pairs[:self.max_active_pairs])
        
        # Final selection: prioritize session pairs but ensure we have max_active_pairs in total
        selected_pairs = session_pairs.copy()
        
        # Add high volatility pairs until we reach max_active_pairs
        remaining_slots = self.max_active_pairs - len(selected_pairs)
        if remaining_slots > 0:
            for pair in sorted_pairs:
                if pair not in selected_pairs:
                    selected_pairs.add(pair)
                    remaining_slots -= 1
                    if remaining_slots == 0:
                        break
                        
        # Update tradable pairs
        self.tradable_pairs = selected_pairs
        
        self.logger.info(f"Selected {len(self.tradable_pairs)} pairs for trading: {self.tradable_pairs}")
            
    def _get_current_session(self, current_time: time) -> Optional[str]:
        """Determine the current trading session."""
        for session, (start, end) in self.sessions.items():
            # Handle sessions that cross midnight
            if start > end:
                if current_time >= start or current_time <= end:
                    return session
            else:
                if start <= current_time <= end:
                    return session
        return None
        
    def _get_session_specific_pairs(self, session: str) -> Set[str]:
        """Get pairs that perform well in the specified session."""
        # These would ideally be based on historical performance data
        session_pairs = {
            'sydney': {'AUD/USD', 'AUD/JPY', 'NZD/USD', 'AUD/NZD'},
            'tokyo': {'USD/JPY', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY'},
            'london': {'EUR/USD', 'GBP/USD', 'EUR/GBP', 'EUR/CHF'},
            'new_york': {'EUR/USD', 'USD/CAD', 'USD/CHF', 'GBP/USD'}
        }
        return session_pairs.get(session, set())
        
    def is_pair_tradable(self, pair: str) -> bool:
        """Check if a pair is currently tradable."""
        return pair in self.tradable_pairs
        
    def get_tradable_pairs(self) -> List[str]:
        """Get the list of currently tradable pairs."""
        return list(self.tradable_pairs)
        
    def get_volatility_metrics(self, pair: str) -> Optional[Dict]:
        """Get volatility metrics for a specific pair."""
        return self.volatility_metrics.get(pair)
        
    def get_all_volatility_metrics(self) -> Dict[str, Dict]:
        """Get volatility metrics for all pairs."""
        return self.volatility_metrics
        
    def get_top_volatile_pairs(self, n: int = 5) -> List[str]:
        """Get the top N most volatile pairs."""
        if not self.volatility_metrics:
            return []
            
        sorted_pairs = sorted(
            self.volatility_metrics.keys(),
            key=lambda p: self.volatility_metrics[p]['composite_score'],
            reverse=True
        )
        return sorted_pairs[:n]
        
    def add_custom_tradable_pair(self, pair: str) -> None:
        """
        Add a custom pair to the tradable list even if it's not in the top by volatility.
        Useful when analysis suggests a good opportunity in a pair that's not in the top volatility list.
        """
        if pair in self.all_pairs:
            self.tradable_pairs.add(pair)
            self.logger.info(f"Added {pair} to tradable pairs based on custom analysis")
            
    def remove_tradable_pair(self, pair: str) -> None:
        """Remove a pair from the tradable list."""
        if pair in self.tradable_pairs:
            self.tradable_pairs.remove(pair)
            self.logger.info(f"Removed {pair} from tradable pairs")
