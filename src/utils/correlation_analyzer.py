"""
Currency Pair Correlation Analysis
Analyzes correlations between different currency pairs to improve trading decisions.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

class CorrelationAnalyzer:
    def __init__(self, lookback_periods: int = 100):
        self.lookback_periods = lookback_periods
        self.pair_data = {}
        self.correlations = {}
        self.last_update = None
        
        # Major pairs to track for EUR/USD correlation
        self.related_pairs = [
            'GBP/USD',  # Strong positive correlation
            'USD/CHF',  # Strong negative correlation
            'USD/JPY',  # Moderate correlation
            'AUD/USD',  # Risk sentiment correlation
            'USD/CAD',  # Oil-related correlation
        ]
        
        # Initialize correlation thresholds
        self.correlation_thresholds = {
            'strong_positive': 0.7,
            'strong_negative': -0.7,
            'moderate_positive': 0.5,
            'moderate_negative': -0.5
        }

    def add_pair_data(self, pair: str, price: float, timestamp: datetime):
        """Add new price data for a currency pair."""
        if pair not in self.pair_data:
            self.pair_data[pair] = {'prices': [], 'timestamps': []}
            
        self.pair_data[pair]['prices'].append(price)
        self.pair_data[pair]['timestamps'].append(timestamp)
        
        # Keep only lookback period worth of data
        if len(self.pair_data[pair]['prices']) > self.lookback_periods:
            self.pair_data[pair]['prices'].pop(0)
            self.pair_data[pair]['timestamps'].pop(0)

    def calculate_correlations(self) -> Dict[str, float]:
        """Calculate correlations between EUR/USD and other pairs."""
        if 'EUR/USD' not in self.pair_data:
            return {}
            
        eur_usd_prices = np.array(self.pair_data['EUR/USD']['prices'])
        correlations = {}
        
        for pair in self.related_pairs:
            if pair in self.pair_data:
                pair_prices = np.array(self.pair_data[pair]['prices'])
                if len(pair_prices) == len(eur_usd_prices):
                    correlation = np.corrcoef(eur_usd_prices, pair_prices)[0, 1]
                    correlations[pair] = correlation
                    
        self.correlations = correlations
        self.last_update = datetime.now()
        return correlations

    def get_correlation_signals(self) -> Dict[str, Dict[str, float]]:
        """Get trading signals based on correlations."""
        if not self.correlations or self.last_update is None:
            return {}
            
        # Check if correlations need updating (every 5 minutes)
        if datetime.now() - self.last_update > timedelta(minutes=5):
            self.calculate_correlations()
            
        signals = {}
        for pair, correlation in self.correlations.items():
            if abs(correlation) >= self.correlation_thresholds['strong_positive']:
                signals[pair] = {
                    'correlation': correlation,
                    'strength': 'strong',
                    'confidence': min(abs(correlation), 0.95)
                }
            elif abs(correlation) >= self.correlation_thresholds['moderate_positive']:
                signals[pair] = {
                    'correlation': correlation,
                    'strength': 'moderate',
                    'confidence': abs(correlation)
                }
                
        return signals

    def validate_trade_direction(self, direction: str, confidence_threshold: float = 0.7) -> Tuple[bool, float]:
        """
        Validate a potential trade direction using correlation data.
        Returns (is_valid, confidence_score)
        """
        if not self.correlations:
            return True, 0.5  # Neutral if no correlation data
            
        supporting_pairs = 0
        opposing_pairs = 0
        total_confidence = 0
        
        for pair, correlation in self.correlations.items():
            if abs(correlation) >= self.correlation_thresholds['moderate_positive']:
                if direction == "BUY":
                    if correlation > 0:
                        supporting_pairs += 1
                        total_confidence += abs(correlation)
                    else:
                        opposing_pairs += 1
                else:  # SELL
                    if correlation < 0:
                        supporting_pairs += 1
                        total_confidence += abs(correlation)
                    else:
                        opposing_pairs += 1
                        
        if supporting_pairs + opposing_pairs == 0:
            return True, 0.5
            
        support_ratio = supporting_pairs / (supporting_pairs + opposing_pairs)
        avg_confidence = total_confidence / (supporting_pairs + opposing_pairs)
        
        is_valid = support_ratio >= 0.6  # At least 60% of correlated pairs support the direction
        confidence = support_ratio * avg_confidence
        
        return is_valid, confidence

    def get_market_sentiment(self) -> Tuple[str, float]:
        """
        Analyze overall market sentiment using correlations.
        Returns (sentiment, confidence)
        """
        if not self.correlations:
            return "NEUTRAL", 0.5
            
        risk_on_score = 0
        risk_off_score = 0
        total_weight = 0
        
        # Weight pairs by correlation strength
        for pair, correlation in self.correlations.items():
            weight = abs(correlation)
            if pair in ['AUD/USD', 'GBP/USD']:  # Risk sentiment pairs
                if correlation > 0:
                    risk_on_score += weight
                else:
                    risk_off_score += weight
                total_weight += weight
                
        if total_weight == 0:
            return "NEUTRAL", 0.5
            
        sentiment_score = (risk_on_score - risk_off_score) / total_weight
        
        if sentiment_score > 0.3:
            return "RISK_ON", min(abs(sentiment_score), 0.95)
        elif sentiment_score < -0.3:
            return "RISK_OFF", min(abs(sentiment_score), 0.95)
        else:
            return "NEUTRAL", 0.5
