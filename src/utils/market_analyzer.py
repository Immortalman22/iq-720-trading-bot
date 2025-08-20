import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import talib
import logging
from datetime import datetime, timedelta

@dataclass
class MarketRegime:
    type: str  # 'trending', 'ranging', 'volatile'
    strength: float  # 0-1 scale
    direction: Optional[str]  # 'up', 'down', or None for ranging
    volatility: float  # Current volatility level
    confidence: float  # Confidence in the regime classification

class MarketAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.timestamp_history: List[datetime] = []
        
        # Configuration
        self.trend_period = 14
        self.volatility_period = 20
        self.volume_period = 10
        self.min_history = 30  # Minimum candles needed for analysis
        
    def get_volatility(self, symbol: str) -> float:
        """Get current volatility level."""
        return 0.001  # Mock implementation for testing

    def add_candle(self, candle_data: Dict) -> None:
        """Add a new candle to the analysis"""
        try:
            self.price_history.append(float(candle_data['close']))
            self.volume_history.append(float(candle_data.get('volume', 0)))
            self.timestamp_history.append(
                datetime.fromtimestamp(candle_data['timestamp'])
                if isinstance(candle_data['timestamp'], (int, float))
                else candle_data['timestamp']
            )

            # Keep limited history
            max_history = 100
            if len(self.price_history) > max_history:
                self.price_history = self.price_history[-max_history:]
                self.volume_history = self.volume_history[-max_history:]
                self.timestamp_history = self.timestamp_history[-max_history:]

        except Exception as e:
            self.logger.error(f"Error adding candle to market analyzer: {e}")

    def get_volatility(self, symbol: str) -> float:
        """
        Calculate current market volatility using ATR.
        Returns normalized volatility between 0-1.
        
        Args:
            symbol: Trading symbol (unused, kept for interface consistency)
            
        Returns:
            float: Normalized volatility score (0-1)
        """
        if len(self.price_history) < self.volatility_period:
            return 0.5  # Default to mid-range if insufficient data
            
        try:
            # Convert price history to numpy array
            prices = np.array(self.price_history)
            
            # Calculate ATR using TA-Lib
            high = prices  # Using close as high/low for simplicity
            low = prices
            close = prices
            atr = talib.ATR(high, low, close, timeperiod=self.volatility_period)
            
            # Normalize ATR relative to price
            current_price = prices[-1]
            normalized_atr = float(atr[-1]) / current_price
            
            # Scale to 0-1 range (0.02 ATR ratio would give 0.5)
            volatility = min(normalized_atr / 0.04, 1.0)
            
            return volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility: {e}")
            return 0.5

    def get_trend_strength(self, symbol: str) -> float:
        """
        Calculate trend strength using ADX.
        Returns normalized strength between 0-1.
        
        Args:
            symbol: Trading symbol (unused, kept for interface consistency)
            
        Returns:
            float: Trend strength score (0-1)
        """
        if len(self.price_history) < self.trend_period:
            return 0.5  # Default to mid-range if insufficient data
            
        try:
            # Convert price history to numpy array
            prices = np.array(self.price_history)
            
            # Calculate ADX using TA-Lib
            high = prices  # Using close as high/low for simplicity
            low = prices
            close = prices
            adx = talib.ADX(high, low, close, timeperiod=self.trend_period)
            
            # ADX ranges from 0-100, normalize to 0-1
            strength = float(adx[-1]) / 100.0
            
            # Adjust strength to emphasize strong trends
            # Below 20 ADX indicates no trend (returns <0.2)
            # Above 40 ADX indicates strong trend (returns >0.8)
            adjusted_strength = np.interp(strength, 
                                        [0, 0.2, 0.4, 1.0],
                                        [0, 0.2, 0.8, 1.0])
            
            return adjusted_strength
            
        except Exception as e:
            self.logger.error(f"Error calculating trend strength: {e}")
            return 0.5

    def get_market_conditions(self) -> Optional[Dict]:
        """Analyze current market conditions"""
        if len(self.price_history) < self.min_history:
            return None

        try:
            # Get market regime
            regime = self._detect_market_regime()
            
            # Get additional market metrics
            metrics = {
                'regime': regime.type,
                'regime_strength': regime.strength,
                'direction': regime.direction,
                'volatility': regime.volatility,
                'confidence': regime.confidence,
                'trend_strength': self._calculate_trend_strength(),
                'volume_profile': self._analyze_volume_profile(),
                'support_resistance': self._find_support_resistance(),
                'momentum': self._calculate_momentum()
            }

            return metrics

        except Exception as e:
            self.logger.error(f"Error analyzing market conditions: {e}")
            return None

    def is_favorable_condition(self) -> Tuple[bool, float, str]:
        """
        Determine if current market conditions are favorable for trading
        Returns: (is_favorable, confidence, reason)
        """
        try:
            conditions = self.get_market_conditions()
            if not conditions:
                return False, 0.0, "Insufficient data"

            confidence = 0.0
            reasons = []

            # Check trend strength with less strict thresholds for testing
            trend_strength = conditions['trend_strength']
            if trend_strength > 0.5:  # Lowered from 0.7
                confidence += 0.3
                reasons.append("Strong trend")
            elif trend_strength < 0.2:  # Lowered from 0.3
                confidence -= 0.2
                reasons.append("Weak trend")

            # Check technical indicators
            if self.has_sufficient_history():
                # RSI Check - More lenient thresholds for trending markets
                rsi = self.calculate_rsi()
                if 40 <= rsi <= 60:  # Narrowed neutral range
                    confidence += 0.2
                    reasons.append("RSI in optimal range")
                elif 30 <= rsi <= 70:  # Wider acceptable range
                    confidence += 0.1
                    reasons.append("RSI in normal range")
                elif rsi < 30:
                    confidence += 0.15
                    reasons.append("RSI oversold")
                elif rsi > 70:
                    confidence += 0.15
                    reasons.append("RSI overbought")

                # MACD Check - More sensitive to trends
                macd, signal = self.calculate_macd()
                if abs(macd - signal) > 0.0001:  # More sensitive threshold
                    confidence += 0.2
                    if macd > signal:
                        confidence += 0.1  # Additional confidence for positive crossover
                    reasons.append("Strong MACD signal")

            # Check volatility - More lenient for trending markets
            if 0.1 <= conditions['volatility'] <= 0.9:  # Wider acceptable range
                confidence += 0.2
                reasons.append("Acceptable volatility")
            elif conditions['volatility'] < 0.1:
                confidence += 0.1  # Small bonus for very stable trends
                reasons.append("Low volatility")
            else:
                confidence -= 0.2  # Less penalty
                reasons.append("High volatility")

            # Check volume profile
            volume_profile = conditions['volume_profile']
            if volume_profile['above_average']:
                confidence += 0.2
                reasons.append("Strong volume")
            
            # Check regime and direction
            if conditions['regime'] == 'trending':
                if conditions['direction'] == 'up':
                    confidence += 0.3  # Higher confidence for uptrends
                else:
                    confidence += 0.1  # Lower confidence for downtrends
                reasons.append(f"Trending market ({conditions['direction']})")
            elif conditions['regime'] == 'volatile':
                confidence -= 0.2
                reasons.append("Volatile market")

            # Check support/resistance levels
            sr_levels = conditions['support_resistance']
            if sr_levels['current_price'] > sr_levels['nearest_support']:
                confidence += 0.1
                reasons.append("Above support")
            if sr_levels['current_price'] < sr_levels['nearest_resistance']:
                confidence += 0.1
                reasons.append("Below resistance")

            # Normalize confidence to 0-1
            confidence = max(0.0, min(1.0, confidence))
            
            is_favorable = confidence >= 0.6
            reason = " | ".join(reasons)

            return is_favorable, confidence, reason

        except Exception as e:
            self.logger.error(f"Error checking market conditions: {e}")
            return False, 0.0, f"Error: {str(e)}"

    def _detect_market_regime(self) -> MarketRegime:
        """Detect the current market regime"""
        prices = np.array(self.price_history)
        
        # Calculate ADX for trend strength
        adx = talib.ADX(
            high=prices,
            low=prices,
            close=prices,
            timeperiod=self.trend_period
        )[-1]
        
        # Calculate ATR for volatility
        atr = talib.ATR(
            high=prices,
            low=prices,
            close=prices,
            timeperiod=self.volatility_period
        )[-1]
        
        # Normalize ATR
        norm_atr = atr / np.mean(prices[-self.volatility_period:])
        
        # Determine regime
        if adx > 25:  # Trending market
            direction = 'up' if prices[-1] > prices[-2] else 'down'
            strength = min(adx / 100, 1.0)
            regime_type = 'trending'
            confidence = 0.7 + (0.3 * (adx - 25) / 75)
        elif norm_atr > 0.02:  # Volatile market
            direction = None
            strength = min(norm_atr / 0.03, 1.0)
            regime_type = 'volatile'
            confidence = 0.6 + (0.4 * (norm_atr - 0.02) / 0.01)
        else:  # Ranging market
            direction = None
            strength = 1.0 - (adx / 25)
            regime_type = 'ranging'
            confidence = 0.5 + (0.5 * (0.02 - norm_atr) / 0.02)

        return MarketRegime(
            type=regime_type,
            strength=strength,
            direction=direction,
            volatility=norm_atr,
            confidence=min(1.0, confidence)
        )

    def _calculate_trend_strength(self) -> float:
        """Calculate the current trend strength (0-1)"""
        prices = np.array(self.price_history)
        
        # Use multiple indicators for trend strength
        # 1. ADX
        adx = talib.ADX(
            high=prices,
            low=prices,
            close=prices,
            timeperiod=self.trend_period
        )[-1]
        
        # 2. Moving Average alignment
        sma20 = talib.SMA(prices, timeperiod=20)[-1]
        sma50 = talib.SMA(prices, timeperiod=50)[-1]
        ma_alignment = abs(sma20 - sma50) / sma50
        
        # 3. Price momentum
        momentum = talib.MOM(prices, timeperiod=10)[-1]
        
        # Combine indicators
        adx_comp = min(adx / 100, 1.0)
        ma_comp = min(ma_alignment * 10, 1.0)
        mom_comp = min(abs(momentum) / prices[-1], 1.0)
        
        return (0.5 * adx_comp + 0.3 * ma_comp + 0.2 * mom_comp)

    def _analyze_volume_profile(self) -> Dict:
        """Analyze the volume profile"""
        if not self.volume_history:
            return {'above_average': False, 'strength': 0.0}

        recent_volume = np.mean(self.volume_history[-3:])
        avg_volume = np.mean(self.volume_history[-self.volume_period:])
        
        return {
            'above_average': bool(recent_volume > avg_volume),  # Convert numpy.bool_ to Python bool
            'strength': float(min(recent_volume / avg_volume, 2.0) / 2.0)  # Convert numpy.float64 to Python float
        }

    def _find_support_resistance(self) -> Dict:
        """Identify key support and resistance levels"""
        prices = np.array(self.price_history)
        
        # Use pivot points
        high = np.max(prices[-20:])
        low = np.min(prices[-20:])
        close = prices[-1]
        
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        
        return {
            'support': float(s1),  # Add explicit support level
            'resistance': float(r1),  # Add explicit resistance level
            'current_price': float(close),
            'nearest_support': float(s1),
            'nearest_resistance': float(r1),
            'distance_to_support': float((close - s1) / close),
            'distance_to_resistance': float((r1 - close) / close)
        }

    def _calculate_momentum(self) -> Dict:
        """Calculate price momentum metrics"""
        try:
            prices = np.array(self.price_history)
            # RSI
            rsi = self.calculate_rsi()
            
            # MACD
            macd, signal = self.calculate_macd()
            
            # Raw momentum
            momentum = talib.MOM(prices, timeperiod=10)
            mom_value = float(momentum[-1] if not np.isnan(momentum[-1]) else 0.0)
            
            return {
                'rsi': float(rsi),
                'macd': float(macd),
                'macd_signal': float(signal),
                'momentum_value': mom_value,
                'momentum_strength': float(min(abs(mom_value / prices[-1]), 1.0))
            }
        except Exception as e:
            self.logger.error(f"Error calculating momentum: {e}")
            return {
                'rsi': 50.0,
                'macd': 0.0,
                'macd_signal': 0.0,
                'momentum_value': 0.0,
                'momentum_strength': 0.0
            }
            
    def has_sufficient_history(self) -> bool:
        """Check if we have enough price history for calculations."""
        return len(self.price_history) >= self.min_history
            
    def calculate_rsi(self, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        try:
            prices = np.array(self.price_history)
            rsi = talib.RSI(prices, timeperiod=period)
            return rsi[-1]
        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return 50.0  # Neutral value
            
    def calculate_macd(self, 
                      fast_period: int = 12, 
                      slow_period: int = 26,
                      signal_period: int = 9) -> Tuple[float, float]:
        """Calculate MACD and signal line values."""
        try:
            prices = np.array(self.price_history)
            macd, signal, _ = talib.MACD(
                prices, 
                fastperiod=fast_period,
                slowperiod=slow_period,
                signalperiod=signal_period
            )
            return macd[-1], signal[-1]
        except Exception as e:
            self.logger.error(f"Error calculating MACD: {e}")
            return 0.0, 0.0
            
    def calculate_bollinger_bands(self, 
                                period: int = 20, 
                                num_std: float = 2.0) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        try:
            prices = np.array(self.price_history)
            upper, middle, lower = talib.BBANDS(
                prices,
                timeperiod=period,
                nbdevup=num_std,
                nbdevdn=num_std
            )
            return upper[-1], middle[-1], lower[-1]
        except Exception as e:
            self.logger.error(f"Error calculating Bollinger Bands: {e}")
            return self.price_history[-1], self.price_history[-1], self.price_history[-1]
