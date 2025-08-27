"""
Correlation analysis module to prevent overtrading correlated assets.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import logging

class CorrelationManager:
    """
    Manages correlations between currency pairs to prevent overtrading.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Predefined correlation groups (from historical analysis)
        self.correlated_groups = [
            # Major USD pairs tend to be correlated
            {'EUR/USD', 'GBP/USD', 'AUD/USD', 'NZD/USD'},
            # JPY pairs often move together
            {'USD/JPY', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'NZD/JPY'},
            # European pairs correlation
            {'EUR/GBP', 'EUR/CHF', 'GBP/CHF'},
            # Commodity currencies
            {'AUD/USD', 'NZD/USD', 'USD/CAD'},
            # CHF pairs
            {'USD/CHF', 'EUR/CHF', 'GBP/CHF'}
        ]
        # Dynamic correlation matrix (will be updated with live data)
        self.correlation_matrix = pd.DataFrame()
        self.price_history = {}  # Store recent price data for pairs
        self.history_length = 100  # Store last 100 price points
        self.correlation_threshold = 0.7  # Default correlation threshold
        self.active_trades = set()  # Currently active trades
        
    def update_price_data(self, pair: str, price: float, timestamp: datetime) -> None:
        """
        Update price history for correlation calculations.
        
        Args:
            pair: Currency pair
            price: Latest price
            timestamp: Timestamp of the price
        """
        if pair not in self.price_history:
            self.price_history[pair] = []
            
        self.price_history[pair].append((timestamp, price))
        
        # Trim history to specified length
        if len(self.price_history[pair]) > self.history_length:
            self.price_history[pair] = self.price_history[pair][-self.history_length:]
            
        # Recalculate correlation matrix periodically
        # (not on every update to save computational resources)
        if len(self.price_history[pair]) % 10 == 0:
            self._update_correlation_matrix()
            
    def _update_correlation_matrix(self) -> None:
        """Update the correlation matrix based on recent price data."""
        # Need at least 2 pairs with enough data points
        valid_pairs = [pair for pair, history in self.price_history.items() 
                      if len(history) >= 30]
        
        if len(valid_pairs) < 2:
            return
            
        # Create a DataFrame from price histories
        data = {}
        for pair in valid_pairs:
            # Extract just prices in order
            data[pair] = [price for _, price in self.price_history[pair][-30:]]
            
        df = pd.DataFrame(data)
        
        # Calculate correlation matrix
        self.correlation_matrix = df.corr()
        self.logger.debug(f"Updated correlation matrix with {len(valid_pairs)} pairs")
        
    def are_correlated(self, pair1: str, pair2: str) -> bool:
        """
        Check if two pairs are correlated.
        
        Args:
            pair1: First currency pair
            pair2: Second currency pair
            
        Returns:
            True if pairs are correlated above threshold
        """
        # Check predefined groups first
        for group in self.correlated_groups:
            if pair1 in group and pair2 in group:
                return True
                
        # Check dynamic correlation if available
        if not self.correlation_matrix.empty:
            if pair1 in self.correlation_matrix.index and pair2 in self.correlation_matrix.columns:
                correlation = abs(self.correlation_matrix.loc[pair1, pair2])
                return correlation >= self.correlation_threshold
                
        # Default to analyzing the currency components
        # If pairs share currencies, they're often correlated
        currencies1 = set(pair1.split('/'))
        currencies2 = set(pair2.split('/'))
        
        # If they share currencies, consider them potentially correlated
        return len(currencies1.intersection(currencies2)) > 0
        
    def register_active_trade(self, pair: str) -> None:
        """Register an active trade on a pair."""
        self.active_trades.add(pair)
        
    def remove_active_trade(self, pair: str) -> None:
        """Remove a pair from active trades."""
        if pair in self.active_trades:
            self.active_trades.remove(pair)
            
    def get_correlated_active_trades(self, pair: str) -> List[str]:
        """
        Get active trades correlated with the given pair.
        
        Args:
            pair: Currency pair to check
            
        Returns:
            List of active trades correlated with the pair
        """
        correlated = []
        for active_pair in self.active_trades:
            if self.are_correlated(pair, active_pair):
                correlated.append(active_pair)
                
        return correlated
        
    def can_trade_pair(self, pair: str) -> Tuple[bool, List[str]]:
        """
        Check if a pair can be traded based on correlation rules.
        
        Args:
            pair: Currency pair to check
            
        Returns:
            Tuple of (can_trade, list_of_correlated_active_trades)
        """
        # Get correlated active trades
        correlated_trades = self.get_correlated_active_trades(pair)
        
        # Can trade if there are no correlated active trades
        can_trade = len(correlated_trades) == 0
        
        return can_trade, correlated_trades
        
    def select_strongest_signal(self, signals: List[Dict]) -> Optional[Dict]:
        """
        From a list of correlated signals, select the strongest one.
        
        Args:
            signals: List of signal dictionaries
            
        Returns:
            The strongest signal, or None if list is empty
        """
        if not signals:
            return None
            
        # Use confidence as the default strength measure
        return max(signals, key=lambda s: s['confidence'])
        
    def filter_correlated_signals(self, signals: List[Dict]) -> List[Dict]:
        """
        Filter out correlated signals, keeping only the strongest in each group.
        
        Args:
            signals: List of signal dictionaries
            
        Returns:
            Filtered list of signals
        """
        if not signals:
            return []
            
        # Sort signals by confidence/strength (assuming higher is stronger)
        sorted_signals = sorted(signals, key=lambda s: s['confidence'], reverse=True)
        
        # Initialize with the strongest signal
        filtered_signals = [sorted_signals[0]]
        processed_pairs = {sorted_signals[0]['asset']}
        
        # Check each remaining signal
        for signal in sorted_signals[1:]:
            pair = signal['asset']
            
            # Skip if already processed a correlated pair
            is_correlated = False
            for processed_pair in processed_pairs:
                if self.are_correlated(pair, processed_pair):
                    is_correlated = True
                    break
                    
            if not is_correlated:
                filtered_signals.append(signal)
                processed_pairs.add(pair)
                
        return filtered_signals
