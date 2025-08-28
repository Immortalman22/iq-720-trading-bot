#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dynamic Pair Correlation Analyzer for IQ 720 Trading Bot

This module analyzes correlations between trading pairs to:
1. Identify redundant trades (highly correlated pairs)
2. Find confirmation signals across correlated assets
3. Help diversify trading decisions

The correlation analyzer runs in the background and updates the correlation
matrix periodically to adapt to changing market conditions.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger("PairCorrelationAnalyzer")

class PairCorrelationAnalyzer:
    """Analyzes correlations between trading pairs dynamically"""
    
    def __init__(self, data_fetcher, config=None):
        """
        Initialize the correlation analyzer
        
        Args:
            data_fetcher: Object used to fetch market data
            config: Configuration dictionary for the correlation analyzer
        """
        self.data_fetcher = data_fetcher
        self.config = config or {}
        
        # Default configuration values
        self.lookback_days = self.config.get('correlation_lookback_days', 30)
        self.update_interval = self.config.get('correlation_update_interval', 6)  # hours
        self.high_correlation_threshold = self.config.get('high_correlation_threshold', 0.85)
        self.pairs = self.config.get('trading_pairs', [])
        
        # Correlation matrices
        self.correlation_matrix = None  # Full correlation matrix
        self.short_term_matrix = None   # Short term (1 day) correlations
        self.medium_term_matrix = None  # Medium term (1 week) correlations
        self.long_term_matrix = None    # Long term (1 month) correlations
        
        # Last update time
        self.last_update = None
        
        # Pair groups (pairs that are highly correlated)
        self.correlation_groups = []
        
        # Flag for correlation matrix validity
        self.is_initialized = False
        
        # Start the background update thread
        if self.pairs:
            self._start_background_updates()
        else:
            logger.warning("No trading pairs provided, correlation analysis disabled")

    def _start_background_updates(self):
        """Start background thread for updating correlation matrices"""
        self.running = True
        self.update_thread = threading.Thread(
            target=self._update_loop, 
            daemon=True,
            name="CorrelationUpdaterThread"
        )
        self.update_thread.start()
        logger.info("Started correlation analyzer background thread")
        
    def _update_loop(self):
        """Background loop for periodic correlation matrix updates"""
        while self.running:
            try:
                # Update correlation matrices
                self.update_correlation_matrices()
                
                # Log status
                logger.info("Correlation matrices updated successfully")
                
                # Sleep until next update interval
                for _ in range(self.update_interval * 3600 // 30):  # Convert hours to 30-second intervals
                    if not self.running:
                        break
                    time.sleep(30)
                    
            except Exception as e:
                logger.error(f"Error updating correlation matrices: {e}")
                time.sleep(300)  # Sleep for 5 minutes on error
    
    def stop(self):
        """Stop the background update thread"""
        self.running = False
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
            logger.info("Correlation analyzer background thread stopped")
    
    def update_correlation_matrices(self):
        """Update all correlation matrices with latest data"""
        # Skip if no pairs are available
        if not self.pairs:
            return False
        
        try:
            # Get price data for all pairs
            prices = {}
            valid_pairs = []
            
            for pair in self.pairs:
                try:
                    # Get daily candle data
                    candles = self.data_fetcher.get_candles(pair, interval='1d', limit=self.lookback_days + 5)
                    if candles is None or len(candles) < self.lookback_days:
                        logger.warning(f"Not enough data for {pair}, skipping in correlation calculation")
                        continue
                    
                    # Extract close prices
                    close_prices = [candle['close'] for candle in candles[-self.lookback_days:]]
                    prices[pair] = close_prices
                    valid_pairs.append(pair)
                except Exception as e:
                    logger.error(f"Error fetching data for {pair}: {e}")
            
            if len(valid_pairs) < 2:
                logger.warning("Not enough valid pairs for correlation analysis")
                return False
            
            # Convert to DataFrame
            price_df = pd.DataFrame(prices)
            
            # Calculate correlation matrices for different timeframes
            self.correlation_matrix = price_df.corr()  # Full period
            
            # Short-term (1 day)
            if len(price_df) >= 2:
                self.short_term_matrix = price_df.iloc[-2:].corr()
            
            # Medium-term (1 week)
            if len(price_df) >= 7:
                self.medium_term_matrix = price_df.iloc[-7:].corr()
            
            # Long-term (30 days - full period)
            self.long_term_matrix = self.correlation_matrix
            
            # Update correlation groups
            self._update_correlation_groups()
            
            # Update last update time
            self.last_update = datetime.now()
            
            # Set initialized flag
            self.is_initialized = True
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating correlation matrices: {e}")
            return False
    
    def _update_correlation_groups(self):
        """Group pairs that are highly correlated with each other"""
        if self.correlation_matrix is None:
            return
        
        # Get pairs that are in the correlation matrix
        pairs = list(self.correlation_matrix.columns)
        
        # Create correlation groups
        visited = set()
        groups = []
        
        for pair in pairs:
            if pair in visited:
                continue
                
            # Start a new group
            group = {pair}
            visited.add(pair)
            
            # Find highly correlated pairs
            for other_pair in pairs:
                if other_pair == pair or other_pair in visited:
                    continue
                
                # Check if correlation exceeds threshold
                if abs(self.correlation_matrix.loc[pair, other_pair]) >= self.high_correlation_threshold:
                    group.add(other_pair)
                    visited.add(other_pair)
            
            # Add group if it has more than one pair
            if len(group) > 1:
                groups.append(sorted(list(group)))
        
        self.correlation_groups = groups
        logger.debug(f"Updated correlation groups: {len(groups)} groups identified")
    
    def get_correlation(self, pair1, pair2, timeframe='medium'):
        """
        Get correlation between two pairs
        
        Args:
            pair1: First trading pair
            pair2: Second trading pair
            timeframe: 'short', 'medium', or 'long'
            
        Returns:
            Correlation coefficient or None if not available
        """
        if not self.is_initialized:
            return None
            
        # Select appropriate correlation matrix
        if timeframe == 'short':
            matrix = self.short_term_matrix
        elif timeframe == 'medium':
            matrix = self.medium_term_matrix
        elif timeframe == 'long':
            matrix = self.long_term_matrix
        else:
            matrix = self.correlation_matrix
            
        # Return correlation if available
        if matrix is not None and pair1 in matrix.columns and pair2 in matrix.columns:
            return matrix.loc[pair1, pair2]
        
        return None
    
    def get_correlations_for_pair(self, pair, threshold=0.5, timeframe='medium'):
        """
        Get all pairs correlated with the given pair above threshold
        
        Args:
            pair: Trading pair to check
            threshold: Minimum absolute correlation
            timeframe: 'short', 'medium', or 'long'
            
        Returns:
            Dictionary of {pair: correlation} for correlated pairs
        """
        if not self.is_initialized:
            return {}
            
        # Select appropriate correlation matrix
        if timeframe == 'short':
            matrix = self.short_term_matrix
        elif timeframe == 'medium':
            matrix = self.medium_term_matrix
        elif timeframe == 'long':
            matrix = self.long_term_matrix
        else:
            matrix = self.correlation_matrix
            
        if matrix is None or pair not in matrix.columns:
            return {}
            
        # Get correlations for the pair
        correlations = matrix[pair].to_dict()
        
        # Filter by threshold
        filtered = {p: corr for p, corr in correlations.items() 
                   if p != pair and abs(corr) >= threshold}
        
        return filtered
    
    def get_correlation_group(self, pair):
        """
        Get the correlation group containing the given pair
        
        Args:
            pair: Trading pair to check
            
        Returns:
            List of pairs in the same correlation group, or None if not found
        """
        if not self.is_initialized:
            return None
            
        for group in self.correlation_groups:
            if pair in group:
                return group
                
        return None
        
    def evaluate_signal_confirmation(self, signal):
        """
        Check if the signal is confirmed by correlated pairs
        
        Args:
            signal: Trading signal with asset and direction
            
        Returns:
            Confirmation score between -1 and 1, where:
            - 1 = strong confirmation
            - 0 = no confirmation
            - -1 = strong contradiction
        """
        if not self.is_initialized or not hasattr(signal, 'asset') or not hasattr(signal, 'direction'):
            return 0
        
        # Get correlations for the pair
        correlations = self.get_correlations_for_pair(signal.asset, threshold=0.7)
        if not correlations:
            return 0
            
        # Fetch most recent signals for correlated pairs
        confirmation_score = 0
        confirmation_count = 0
        
        for pair, correlation in correlations.items():
            # Check if we have a recent signal for this pair
            other_signal = self.get_recent_signal(pair)
            if other_signal is None:
                continue
                
            # Determine if the signal is confirmatory or contradictory
            same_direction = (signal.direction == other_signal.direction)
            
            # For negatively correlated pairs, opposite direction is confirmatory
            if correlation < 0:
                same_direction = not same_direction
                
            # Update confirmation score
            if same_direction:
                confirmation_score += abs(correlation)
            else:
                confirmation_score -= abs(correlation)
                
            confirmation_count += 1
            
        # Normalize score between -1 and 1
        if confirmation_count > 0:
            return confirmation_score / confirmation_count
            
        return 0
    
    def get_recent_signal(self, pair):
        """
        Get the most recent signal for a pair
        Note: This is a stub method - implement actual logic in the main bot
        
        Args:
            pair: Trading pair
            
        Returns:
            Most recent signal for the pair or None
        """
        # This method should be overridden with actual implementation
        # that retrieves recent signals from the signal generator
        return None
    
    def are_highly_correlated(self, pair1, pair2, threshold=None):
        """
        Check if two pairs are highly correlated
        
        Args:
            pair1: First trading pair
            pair2: Second trading pair
            threshold: Custom correlation threshold (default: use high_correlation_threshold)
            
        Returns:
            True if pairs are highly correlated, False otherwise
        """
        threshold = threshold or self.high_correlation_threshold
        correlation = self.get_correlation(pair1, pair2)
        
        if correlation is None:
            return False
            
        return abs(correlation) >= threshold
        
    def get_status_summary(self):
        """
        Get a summary of the correlation analyzer status
        
        Returns:
            Dictionary with status information
        """
        return {
            'initialized': self.is_initialized,
            'last_update': self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else None,
            'pairs_analyzed': len(self.correlation_matrix.columns) if self.correlation_matrix is not None else 0,
            'correlation_groups': len(self.correlation_groups),
            'update_interval_hours': self.update_interval
        }
