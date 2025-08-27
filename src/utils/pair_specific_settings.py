"""
Pair-specific settings for different currency pairs.
This module contains customized technical indicator settings for different currency pairs.
"""
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

# Define volatility categories
HIGH_VOLATILITY_PAIRS = ['GBP/JPY', 'AUD/JPY', 'NZD/JPY', 'CAD/JPY', 'GBP/AUD', 'GBP/NZD']
MEDIUM_VOLATILITY_PAIRS = ['EUR/USD', 'GBP/USD', 'USD/CAD', 'AUD/USD', 'EUR/JPY', 'EUR/GBP']
LOW_VOLATILITY_PAIRS = ['USD/CHF', 'EUR/CHF', 'USD/JPY', 'NZD/USD']

class PairSettings:
    """Manage pair-specific technical indicator settings."""
    
    def __init__(self):
        # Default settings
        self.default_settings = {
            'rsi': {'timeperiod': 14},
            'macd': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},
            'stoch': {'fastk_period': 14, 'slowk_period': 3, 'slowd_period': 3},
            'bollinger': {'timeperiod': 20, 'nbdevup': 2, 'nbdevdn': 2},
            'atr': {'timeperiod': 14},
            'volume_timeperiod': 10,
            'price_action_lookback': 3,
            'trend_timeperiod': 50,
        }
        
        # Initialize pair-specific settings
        self.pair_settings = {}
        self._initialize_pair_settings()
        
    def _initialize_pair_settings(self):
        """Set up customized settings for each currency pair."""
        
        # High volatility pairs - use shorter periods, quicker response
        for pair in HIGH_VOLATILITY_PAIRS:
            self.pair_settings[pair] = {
                'rsi': {'timeperiod': 10},  # Shorter RSI for faster response
                'macd': {'fastperiod': 8, 'slowperiod': 17, 'signalperiod': 9},  # More sensitive MACD
                'stoch': {'fastk_period': 10, 'slowk_period': 3, 'slowd_period': 3},
                'bollinger': {'timeperiod': 14, 'nbdevup': 2.2, 'nbdevdn': 2.2},  # Tighter bands
                'atr': {'timeperiod': 10},  # More responsive ATR
                'volume_timeperiod': 8,
                'price_action_lookback': 2,  # Need fewer confirming candles
                'trend_timeperiod': 35,  # Shorter trend assessment period
                'signal_threshold': 0.75,  # Higher threshold for volatile pairs
                'correlation_threshold': 0.85,
                'min_volatility_percentile': 65,  # Only trade when volatility is high enough
            }
            
        # Medium volatility pairs - balanced settings
        for pair in MEDIUM_VOLATILITY_PAIRS:
            self.pair_settings[pair] = {
                'rsi': {'timeperiod': 14},  # Standard RSI
                'macd': {'fastperiod': 12, 'slowperiod': 26, 'signalperiod': 9},  # Standard MACD
                'stoch': {'fastk_period': 14, 'slowk_period': 3, 'slowd_period': 3},
                'bollinger': {'timeperiod': 20, 'nbdevup': 2, 'nbdevdn': 2},
                'atr': {'timeperiod': 14},
                'volume_timeperiod': 10,
                'price_action_lookback': 3,
                'trend_timeperiod': 50,
                'signal_threshold': 0.7,
                'correlation_threshold': 0.8,
                'min_volatility_percentile': 50,
            }
            
        # Low volatility pairs - use longer periods, less noise
        for pair in LOW_VOLATILITY_PAIRS:
            self.pair_settings[pair] = {
                'rsi': {'timeperiod': 21},  # Longer RSI to filter noise
                'macd': {'fastperiod': 16, 'slowperiod': 32, 'signalperiod': 9},  # Less sensitive MACD
                'stoch': {'fastk_period': 18, 'slowk_period': 3, 'slowd_period': 3},
                'bollinger': {'timeperiod': 26, 'nbdevup': 1.8, 'nbdevdn': 1.8},  # Wider bands for noise
                'atr': {'timeperiod': 21},  # Smoother ATR
                'volume_timeperiod': 15,
                'price_action_lookback': 4,  # Need more confirming candles
                'trend_timeperiod': 75,  # Longer trend assessment period
                'signal_threshold': 0.65,  # Lower threshold acceptable for stable pairs
                'correlation_threshold': 0.75,
                'min_volatility_percentile': 40,  # Can trade in lower volatility
            }
    
    def get_settings(self, pair: str) -> Dict[str, Any]:
        """Get settings for a specific currency pair."""
        # Return specific settings if they exist, otherwise default settings
        if pair in self.pair_settings:
            return self.pair_settings[pair]
        
        # For pairs not explicitly defined, check if we can categorize by components
        # For example, if we have a new pair like EUR/NZD, we can check for volatility
        if pair.split('/')[0] in ['GBP', 'AUD', 'NZD'] or pair.split('/')[1] == 'JPY':
            # Higher volatility category for pairs with these currencies
            return self._get_nearest_settings(pair, HIGH_VOLATILITY_PAIRS)
        elif pair.split('/')[0] in ['CHF', 'USD'] or pair.split('/')[1] == 'CHF':
            # Lower volatility for CHF pairs
            return self._get_nearest_settings(pair, LOW_VOLATILITY_PAIRS)
        else:
            # Default to medium volatility
            return self._get_nearest_settings(pair, MEDIUM_VOLATILITY_PAIRS)
    
    def _get_nearest_settings(self, pair: str, category_pairs: List[str]) -> Dict[str, Any]:
        """Find the most similar pair in a category and return its settings."""
        if not category_pairs:
            return self.default_settings
            
        # Just use the first pair in the category as a simple approach
        return self.pair_settings[category_pairs[0]]
        
    def update_settings(self, pair: str, settings: Dict[str, Any]) -> None:
        """Update settings for a specific pair based on performance or other factors."""
        if pair in self.pair_settings:
            self.pair_settings[pair].update(settings)
        else:
            self.pair_settings[pair] = {**self.default_settings, **settings}

# Initialize pair settings
pair_settings = PairSettings()
