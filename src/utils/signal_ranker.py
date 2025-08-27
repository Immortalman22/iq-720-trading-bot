"""
Signal strength ranking system.
This module calculates and ranks signals based on multiple factors.
"""
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging

@dataclass
class RankedSignal:
    """A signal with strength ranking metrics"""
    timestamp: datetime
    direction: str  # "BUY" or "SELL"
    asset: str
    expiry_minutes: int
    confidence: float
    indicators: dict
    strength_score: float  # Overall strength score 0-100
    strength_factors: Dict[str, float]  # Individual component scores
    market_context: Dict[str, Any]  # Additional market context

class SignalRanker:
    """Ranks trading signals by their strength and quality."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Weights for different components in the strength calculation
        self.weights = {
            'indicator_alignment': 0.25,  # How well indicators agree
            'signal_strength': 0.25,      # Strength of individual indicators
            'trend_alignment': 0.20,      # Alignment with overall trend
            'volume_confirmation': 0.15,  # Volume confirmation
            'historical_performance': 0.10,  # How well signals worked in the past
            'volatility': 0.05,           # Current volatility conditions
        }
        self.recent_signals = []  # Keep track of recent signals
        
    def calculate_signal_strength(self, signal_data: Dict) -> Tuple[float, Dict[str, float]]:
        """
        Calculate the strength score of a potential signal
        
        Args:
            signal_data: Dictionary containing indicator values and other signal info
            
        Returns:
            Tuple containing (overall_score, component_scores)
        """
        direction = signal_data['direction']
        indicators = signal_data['indicators']
        asset = signal_data['asset']
        
        # Initialize component scores
        component_scores = {}
        
        # 1. Indicator Alignment Score (how well multiple indicators agree)
        indicator_alignment = self._calculate_indicator_alignment(direction, indicators)
        component_scores['indicator_alignment'] = indicator_alignment
        
        # 2. Signal Strength (how strong each indicator is)
        signal_strength = self._calculate_signal_strength(direction, indicators)
        component_scores['signal_strength'] = signal_strength
        
        # 3. Trend Alignment (how well signal aligns with overall trend)
        trend_alignment = self._calculate_trend_alignment(direction, indicators)
        component_scores['trend_alignment'] = trend_alignment
        
        # 4. Volume Confirmation
        volume_score = self._calculate_volume_score(indicators)
        component_scores['volume_confirmation'] = volume_score
        
        # 5. Historical Performance (based on similar past signals)
        historical_score = self._calculate_historical_score(asset, direction, indicators)
        component_scores['historical_performance'] = historical_score
        
        # 6. Volatility Score
        volatility_score = self._calculate_volatility_score(indicators)
        component_scores['volatility'] = volatility_score
        
        # Calculate weighted overall score
        overall_score = 0
        for component, score in component_scores.items():
            overall_score += score * self.weights[component]
            
        # Scale to 0-100 range
        overall_score = min(max(overall_score * 100, 0), 100)
        
        return overall_score, component_scores
        
    def _calculate_indicator_alignment(self, direction: str, indicators: Dict) -> float:
        """
        Calculate how well different indicators align.
        1.0 = perfect alignment, 0.0 = complete disagreement
        """
        # Initialize counter for agreeing indicators
        agreeing = 0
        total_indicators = 0
        
        # RSI alignment
        if 'rsi' in indicators:
            total_indicators += 1
            rsi = indicators['rsi']
            if (direction == 'BUY' and rsi < 40) or (direction == 'SELL' and rsi > 60):
                agreeing += 1
                
        # MACD alignment
        if 'macd' in indicators and 'macd_signal' in indicators:
            total_indicators += 1
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            if (direction == 'BUY' and macd > macd_signal) or (direction == 'SELL' and macd < macd_signal):
                agreeing += 1
                
        # Stochastic alignment if available
        if 'stoch_k' in indicators and 'stoch_d' in indicators:
            total_indicators += 1
            stoch_k = indicators['stoch_k']
            stoch_d = indicators['stoch_d']
            if (direction == 'BUY' and stoch_k > stoch_d and stoch_k < 30) or \
               (direction == 'SELL' and stoch_k < stoch_d and stoch_k > 70):
                agreeing += 1
                
        # Bollinger band alignment if available
        if 'bb_upper' in indicators and 'bb_lower' in indicators and 'close' in indicators:
            total_indicators += 1
            close = indicators['close']
            upper = indicators['bb_upper']
            lower = indicators['bb_lower']
            if (direction == 'BUY' and close <= lower * 1.02) or \
               (direction == 'SELL' and close >= upper * 0.98):
                agreeing += 1
        
        # Calculate alignment ratio
        if total_indicators == 0:
            return 0.5  # Default to neutral if no indicators
            
        alignment_score = agreeing / total_indicators
        return alignment_score
        
    def _calculate_signal_strength(self, direction: str, indicators: Dict) -> float:
        """
        Calculate the strength of the signal based on how far indicators are from thresholds.
        1.0 = very strong, 0.0 = very weak
        """
        # Initialize strength accumulator
        strength_sum = 0
        count = 0
        
        # RSI strength
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if direction == 'BUY':
                # Lower RSI = stronger buy signal
                strength = max(0, min(1, (40 - rsi) / 20)) if rsi < 40 else 0
            else:  # SELL
                # Higher RSI = stronger sell signal
                strength = max(0, min(1, (rsi - 60) / 20)) if rsi > 60 else 0
            strength_sum += strength
            count += 1
            
        # MACD strength
        if 'macd' in indicators and 'macd_signal' in indicators:
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            # Strength based on distance between MACD and signal line
            if (direction == 'BUY' and macd > macd_signal) or (direction == 'SELL' and macd < macd_signal):
                # Normalize the difference
                diff = abs(macd - macd_signal)
                strength = min(1, diff / 0.001)  # Cap at 1.0
                strength_sum += strength
            else:
                strength_sum += 0
            count += 1
            
        # Volume strength
        if 'volume_ratio' in indicators:
            volume_ratio = indicators['volume_ratio']
            # Higher volume = stronger signal, if above average
            if volume_ratio > 1:
                # Cap at volume 3x average
                volume_strength = min(1, (volume_ratio - 1) / 2)
                strength_sum += volume_strength
            else:
                strength_sum += 0
            count += 1
            
        # Calculate average strength
        if count == 0:
            return 0.5  # Default to neutral if no indicators
            
        return strength_sum / count
        
    def _calculate_trend_alignment(self, direction: str, indicators: Dict) -> float:
        """
        Calculate how well the signal aligns with the overall trend.
        1.0 = perfectly aligned with trend, 0.0 = against trend
        """
        # Initialize with neutral score if we don't have trend data
        if 'trend_direction' not in indicators:
            return 0.5
            
        trend_direction = indicators['trend_direction']
        
        # If trend aligns with signal direction
        if (trend_direction == 'up' and direction == 'BUY') or \
           (trend_direction == 'down' and direction == 'SELL'):
            return 1.0
            
        # If trend is against signal direction
        elif (trend_direction == 'up' and direction == 'SELL') or \
             (trend_direction == 'down' and direction == 'BUY'):
            return 0.0
            
        # If trend is neutral
        else:
            return 0.5
            
    def _calculate_volume_score(self, indicators: Dict) -> float:
        """Calculate score based on volume confirmation."""
        if 'volume_ratio' not in indicators:
            return 0.5
            
        volume_ratio = indicators['volume_ratio']
        
        # Low volume is less reliable
        if volume_ratio < 0.8:
            return 0.3
            
        # Average volume is neutral
        elif volume_ratio < 1.2:
            return 0.5
            
        # Above average volume is good
        elif volume_ratio < 2.0:
            return 0.75
            
        # High volume is very good
        else:
            return min(1.0, volume_ratio / 3)  # Cap at 1.0
            
    def _calculate_historical_score(self, asset: str, direction: str, indicators: Dict) -> float:
        """Calculate score based on historical performance of similar signals."""
        # In a real implementation, this would query historical performance data
        # For now, we'll return a neutral score
        return 0.5
        
    def _calculate_volatility_score(self, indicators: Dict) -> float:
        """Calculate score based on volatility conditions."""
        if 'atr_ratio' not in indicators:
            return 0.5
            
        # ATR ratio = current ATR / average ATR
        atr_ratio = indicators['atr_ratio']
        
        # Very low volatility is bad for signals
        if atr_ratio < 0.7:
            return 0.3
            
        # Low volatility is suboptimal
        elif atr_ratio < 0.9:
            return 0.4
            
        # Normal volatility is good
        elif atr_ratio < 1.3:
            return 0.7
            
        # High volatility can be good but also more risky
        elif atr_ratio < 2.0:
            return 0.8
            
        # Very high volatility might indicate abnormal conditions
        else:
            return 0.5
            
    def rank_signals(self, signals: List[Dict]) -> List[RankedSignal]:
        """
        Rank multiple signals by their strength
        
        Args:
            signals: List of signal dictionaries
            
        Returns:
            List of RankedSignal objects sorted by strength (highest first)
        """
        if not signals:
            return []
            
        ranked_signals = []
        
        for signal_data in signals:
            # Calculate signal strength
            strength_score, strength_factors = self.calculate_signal_strength(signal_data)
            
            # Create a RankedSignal object
            ranked_signal = RankedSignal(
                timestamp=signal_data['timestamp'],
                direction=signal_data['direction'],
                asset=signal_data['asset'],
                expiry_minutes=signal_data['expiry_minutes'],
                confidence=signal_data['confidence'],
                indicators=signal_data['indicators'],
                strength_score=strength_score,
                strength_factors=strength_factors,
                market_context={
                    'time_of_day': signal_data['timestamp'].hour,
                    'day_of_week': signal_data['timestamp'].weekday(),
                }
            )
            
            ranked_signals.append(ranked_signal)
            
        # Sort by strength score (descending)
        ranked_signals.sort(key=lambda s: s.strength_score, reverse=True)
        
        # Store recent signals for reference
        self.recent_signals = ranked_signals[:10]  # Keep top 10
        
        return ranked_signals
        
    def get_top_signals(self, signals: List[Dict], limit: int = 3) -> List[RankedSignal]:
        """Get the top N strongest signals."""
        ranked = self.rank_signals(signals)
        return ranked[:limit]
        
    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """Update the weighting factors for signal ranking."""
        # Validate weights
        if sum(new_weights.values()) != 1.0:
            self.logger.warning("Weights don't sum to 1.0, normalizing...")
            total = sum(new_weights.values())
            new_weights = {k: v/total for k, v in new_weights.items()}
            
        self.weights.update(new_weights)
