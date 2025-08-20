"""
Market Regime Detection Module
Identifies different market conditions and adapts trading strategy accordingly.
"""
import numpy as np
from enum import Enum
from typing import Tuple, List
import talib

class MarketRegime(Enum):
    STRONG_TREND_UP = "STRONG_TREND_UP"
    WEAK_TREND_UP = "WEAK_TREND_UP"
    CHOPPY = "CHOPPY"
    WEAK_TREND_DOWN = "WEAK_TREND_DOWN"
    STRONG_TREND_DOWN = "STRONG_TREND_DOWN"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"

class MarketRegimeDetector:
    def __init__(self, lookback_period: int = 100):
        self.lookback_period = lookback_period
        self.min_data_points = 20
        
    def detect_regime(self, prices: List[float], volumes: List[float]) -> Tuple[MarketRegime, float]:
        if len(prices) < self.min_data_points:
            return MarketRegime.CHOPPY, 0.5

        prices_np = np.array(prices)
        volumes_np = np.array(volumes)
        
        # Trend Strength Analysis
        atr = talib.ATR(
            high=prices_np,
            low=prices_np,
            close=prices_np,
            timeperiod=14
        )[-1]
        
        adx = talib.ADX(
            high=prices_np,
            low=prices_np,
            close=prices_np,
            timeperiod=14
        )[-1]
        
        # Volatility Analysis
        bollinger_upper, _, bollinger_lower = talib.BBANDS(
            prices_np,
            timeperiod=20,
            nbdevup=2,
            nbdevdn=2
        )
        bb_width = (bollinger_upper[-1] - bollinger_lower[-1]) / prices_np[-1]
        
        # Volume Analysis
        volume_sma = talib.SMA(volumes_np, timeperiod=20)[-1]
        volume_ratio = volumes_np[-1] / volume_sma if volume_sma > 0 else 1.0
        
        # Trend Direction
        ema_fast = talib.EMA(prices_np, timeperiod=10)[-1]
        ema_slow = talib.EMA(prices_np, timeperiod=30)[-1]
        trend_strength = abs(ema_fast - ema_slow) / prices_np[-1]
        
        # Determine Regime
        if adx > 25:  # Strong trend
            if ema_fast > ema_slow:
                regime = MarketRegime.STRONG_TREND_UP
                confidence = min(adx / 100, 0.95)
            else:
                regime = MarketRegime.STRONG_TREND_DOWN
                confidence = min(adx / 100, 0.95)
                
        elif adx > 15:  # Weak trend
            if ema_fast > ema_slow:
                regime = MarketRegime.WEAK_TREND_UP
                confidence = 0.6
            else:
                regime = MarketRegime.WEAK_TREND_DOWN
                confidence = 0.6
                
        else:  # No clear trend
            if bb_width > 0.02:  # High volatility
                regime = MarketRegime.HIGH_VOLATILITY
                confidence = min(bb_width * 20, 0.9)
            elif bb_width < 0.01:  # Low volatility
                regime = MarketRegime.LOW_VOLATILITY
                confidence = min(1 - bb_width * 50, 0.9)
            else:
                regime = MarketRegime.CHOPPY
                confidence = 0.5
        
        # Adjust confidence based on volume
        confidence *= min(volume_ratio, 1.2)
        
        return regime, confidence

    def get_regime_parameters(self, regime: MarketRegime) -> dict:
        """Get optimal trading parameters for the current market regime."""
        params = {
            MarketRegime.STRONG_TREND_UP: {
                'momentum_threshold': 0.4,
                'stop_loss_multiplier': 1.5,
                'take_profit_multiplier': 2.0,
                'entry_aggressiveness': 0.8
            },
            MarketRegime.WEAK_TREND_UP: {
                'momentum_threshold': 0.5,
                'stop_loss_multiplier': 1.2,
                'take_profit_multiplier': 1.5,
                'entry_aggressiveness': 0.6
            },
            MarketRegime.CHOPPY: {
                'momentum_threshold': 0.7,
                'stop_loss_multiplier': 1.0,
                'take_profit_multiplier': 1.2,
                'entry_aggressiveness': 0.4
            },
            MarketRegime.WEAK_TREND_DOWN: {
                'momentum_threshold': 0.5,
                'stop_loss_multiplier': 1.2,
                'take_profit_multiplier': 1.5,
                'entry_aggressiveness': 0.6
            },
            MarketRegime.STRONG_TREND_DOWN: {
                'momentum_threshold': 0.4,
                'stop_loss_multiplier': 1.5,
                'take_profit_multiplier': 2.0,
                'entry_aggressiveness': 0.8
            },
            MarketRegime.HIGH_VOLATILITY: {
                'momentum_threshold': 0.6,
                'stop_loss_multiplier': 2.0,
                'take_profit_multiplier': 2.5,
                'entry_aggressiveness': 0.5
            },
            MarketRegime.LOW_VOLATILITY: {
                'momentum_threshold': 0.8,
                'stop_loss_multiplier': 1.0,
                'take_profit_multiplier': 1.2,
                'entry_aggressiveness': 0.3
            }
        }
        return params[regime]
