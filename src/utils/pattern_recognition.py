"""
Advanced Pattern Recognition Module
Identifies technical patterns and calculates their reliability based on market context.
"""
from enum import Enum
from typing import List, Dict, Tuple, Optional
import numpy as np
import talib

class PatternType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    CONTINUATION = "CONTINUATION"
    REVERSAL = "REVERSAL"
    NEUTRAL = "NEUTRAL"

class PatternStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

class PatternRecognition:
    def __init__(self):
        # Dictionary mapping pattern names to their functions in TA-Lib
        self.candlestick_patterns = {
            # Reversal Patterns
            'ENGULFING': talib.CDLENGULFING,
            'HAMMER': talib.CDLHAMMER,
            'SHOOTING_STAR': talib.CDLSHOOTINGSTAR,
            'MORNING_STAR': talib.CDLMORNINGSTAR,
            'EVENING_STAR': talib.CDLEVENINGSTAR,
            
            # Continuation Patterns
            'HARAMI': talib.CDLHARAMI,
            'DOJI': talib.CDLDOJI,
            'SPINNING_TOP': talib.CDLSPINNINGTOP,
            
            # Strong Momentum Patterns
            'THREE_WHITE_SOLDIERS': talib.CDL3WHITESOLDIERS,
            'THREE_BLACK_CROWS': talib.CDL3BLACKCROWS,
            'MARUBOZU': talib.CDLMARUBOZU
        }

    def identify_patterns(self, high: np.ndarray, low: np.ndarray, 
                         open_prices: np.ndarray, close: np.ndarray) -> Dict[str, Tuple[PatternType, PatternStrength, float]]:
        """
        Identify candlestick patterns and their reliability.
        Returns dict of pattern name -> (type, strength, confidence)
        """
        patterns = {}
        
        # Check each pattern
        for pattern_name, pattern_func in self.candlestick_patterns.items():
            result = pattern_func(open_prices, high, low, close)
            
            # If pattern detected in the last candle
            if result[-1] != 0:
                pattern_type = self._get_pattern_type(pattern_name, result[-1])
                strength = self._calculate_pattern_strength(
                    pattern_name, 
                    high, low, open_prices, close,
                    result[-1]
                )
                confidence = self._calculate_pattern_confidence(
                    pattern_name,
                    high, low, open_prices, close,
                    strength
                )
                
                patterns[pattern_name] = (pattern_type, strength, confidence)
        
        return patterns

    def _get_pattern_type(self, pattern_name: str, signal: int) -> PatternType:
        """Determine pattern type based on signal and pattern name."""
        if signal > 0:
            if pattern_name in ['HAMMER', 'MORNING_STAR', 'ENGULFING']:
                return PatternType.REVERSAL
            return PatternType.BULLISH
        elif signal < 0:
            if pattern_name in ['SHOOTING_STAR', 'EVENING_STAR', 'ENGULFING']:
                return PatternType.REVERSAL
            return PatternType.BEARISH
        return PatternType.NEUTRAL

    def _calculate_pattern_strength(self, pattern_name: str, 
                                  high: np.ndarray, low: np.ndarray,
                                  open_prices: np.ndarray, close: np.ndarray,
                                  signal: int) -> PatternStrength:
        """Calculate pattern strength based on various factors."""
        # Get recent price action
        recent_high = high[-5:]
        recent_low = low[-5:]
        recent_close = close[-5:]
        recent_open = open_prices[-5:]
        
        # Calculate volatility
        atr = talib.ATR(high, low, close, timeperiod=14)[-1]
        body_size = abs(close[-1] - open_prices[-1])
        
        # Strong patterns criteria
        if pattern_name in ['THREE_WHITE_SOLDIERS', 'THREE_BLACK_CROWS', 'MARUBOZU']:
            return PatternStrength.VERY_STRONG if body_size > atr else PatternStrength.STRONG
            
        # Reversal patterns strength
        if pattern_name in ['HAMMER', 'SHOOTING_STAR', 'MORNING_STAR', 'EVENING_STAR']:
            trend_strength = self._calculate_trend_strength(close)
            if trend_strength > 0.8:
                return PatternStrength.VERY_STRONG
            elif trend_strength > 0.5:
                return PatternStrength.STRONG
                
        # Continuation patterns
        if pattern_name in ['HARAMI', 'DOJI', 'SPINNING_TOP']:
            if body_size < 0.3 * atr:
                return PatternStrength.MODERATE
            return PatternStrength.WEAK
            
        return PatternStrength.MODERATE

    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate the strength of the current trend."""
        ema20 = talib.EMA(prices, timeperiod=20)
        ema50 = talib.EMA(prices, timeperiod=50)
        
        trend_angle = abs(ema20[-1] - ema20[-5]) / prices[-1]
        trend_consistency = abs(ema20[-1] - ema50[-1]) / prices[-1]
        
        return min(1.0, (trend_angle + trend_consistency) / 2)

    def _calculate_pattern_confidence(self, pattern_name: str,
                                    high: np.ndarray, low: np.ndarray,
                                    open_prices: np.ndarray, close: np.ndarray,
                                    strength: PatternStrength) -> float:
        """Calculate confidence score for the pattern."""
        # Base confidence from strength
        base_confidence = {
            PatternStrength.WEAK: 0.3,
            PatternStrength.MODERATE: 0.5,
            PatternStrength.STRONG: 0.7,
            PatternStrength.VERY_STRONG: 0.9
        }[strength]
        
        # Volume confirmation (if available)
        volume_confirmation = 1.0  # Default if no volume data
        
        # Trend confirmation
        trend_strength = self._calculate_trend_strength(close)
        
        # Pattern completion quality
        completion_quality = self._calculate_completion_quality(
            pattern_name, high, low, open_prices, close
        )
        
        # Final confidence calculation
        confidence = (base_confidence * 0.4 +
                     volume_confirmation * 0.2 +
                     trend_strength * 0.2 +
                     completion_quality * 0.2)
        
        return min(0.95, confidence)  # Cap at 0.95 to account for uncertainty

    def _calculate_completion_quality(self, pattern_name: str,
                                    high: np.ndarray, low: np.ndarray,
                                    open_prices: np.ndarray, close: np.ndarray) -> float:
        """Calculate how well-formed the pattern is."""
        # Get recent candles
        recent_high = high[-3:]
        recent_low = low[-3:]
        recent_close = close[-3:]
        recent_open = open_prices[-3:]
        
        # Calculate average trading range
        atr = talib.ATR(high, low, close, timeperiod=14)[-1]
        
        # Pattern-specific quality checks
        if pattern_name in ['ENGULFING', 'MARUBOZU']:
            body_size = abs(close[-1] - open_prices[-1])
            quality = min(1.0, body_size / atr)
        
        elif pattern_name in ['HAMMER', 'SHOOTING_STAR']:
            shadow_size = max(high[-1] - max(open_prices[-1], close[-1]),
                            min(open_prices[-1], close[-1]) - low[-1])
            quality = min(1.0, shadow_size / atr)
        
        elif pattern_name in ['MORNING_STAR', 'EVENING_STAR']:
            quality = min(1.0, abs(close[-1] - close[-3]) / atr)
        
        else:
            quality = 0.7  # Default quality for other patterns
        
        return quality
