import numpy as np
import pandas as pd
import talib
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import logging
from .utils.news.forex_news import ForexNewsFilter
from .utils.market_analyzer import MarketAnalyzer
from .utils.session_manager import SessionManager
from .utils.market_regime import MarketRegimeDetector, MarketRegime
from .utils.pattern_recognition import PatternRecognition, PatternType, PatternStrength
from .utils.correlation_analyzer import CorrelationAnalyzer
from .utils.historical_analyzer import HistoricalAnalyzer, MarketPhase
from .utils.real_time_optimizer import RealTimeOptimizer

@dataclass
class Signal:
    timestamp: datetime
    direction: str  # "BUY" or "SELL"
    asset: str
    expiry_minutes: int
    confidence: float
    indicators: dict

class SignalGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.timestamp_history: List[datetime] = []
        self.consecutive_losses = 0
        self.trades_today = 0
        self.last_signal_time: Optional[datetime] = None
        self.news_filter = ForexNewsFilter()
        self.market_analyzer = MarketAnalyzer()
        self.market_regime_detector = MarketRegimeDetector()
        self.pattern_recognition = PatternRecognition()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.real_time_optimizer = RealTimeOptimizer()
        self.last_news_check = None
        self.news_buffer_minutes = 15
        self.min_market_confidence = 0.6  # Minimum market condition confidence
        self.current_regime: Optional[MarketRegime] = None
        self.regime_confidence: float = 0.0
        self.pattern_memory = []  # Store recent pattern signals
        self.last_calculation_time = datetime.now()
        self.execution_times = []  # Track signal generation speed

    def add_candle(self, candle_data: dict) -> Optional[Signal]:
        """Process new candle data and potentially generate a signal"""
        try:
            # Extract candle data
            close_price = float(candle_data['close'])
            volume = float(candle_data['volume'])
            timestamp = datetime.fromtimestamp(candle_data['timestamp'])

            # Add to history
            self.price_history.append(close_price)
            self.volume_history.append(volume)
            self.timestamp_history.append(timestamp)

            # Update market analyzer
            self.market_analyzer.add_candle(candle_data)

            # Keep last 100 candles for analysis
            max_history = 100
            if len(self.price_history) > max_history:
                self.price_history = self.price_history[-max_history:]
                self.volume_history = self.volume_history[-max_history:]
                self.timestamp_history = self.timestamp_history[-max_history:]

            # Only generate signals if we have enough data
            if len(self.price_history) < 26:  # Minimum required for MACD
                return None

            return self._analyze_indicators()

        except Exception as e:
            self.logger.error(f"Error processing candle data: {e}")
            return None

    def _analyze_indicators(self) -> Optional[Signal]:
        """Analyze technical indicators and generate trading signal"""
        if not self._check_trading_conditions():
            return None

        prices = np.array(self.price_history)
        volumes = np.array(self.volume_history)

        # Calculate indicators
        rsi = talib.RSI(prices, timeperiod=14)[-1]
        macd, signal, _ = talib.MACD(prices, fastperiod=12, slowperiod=26, signalperiod=9)
        volume_sma = talib.SMA(volumes, timeperiod=10)[-1]
        current_volume = volumes[-1]

        # Initialize indicator results
        indicators = {
            'rsi': rsi,
            'macd': macd[-1],
            'macd_signal': signal[-1],
            'volume_ratio': current_volume / volume_sma if volume_sma > 0 else 0
        }

        # Check for buy conditions
        if (rsi < 30 and  # Oversold
            macd[-1] > signal[-1] and  # Bullish MACD crossover
            current_volume > volume_sma * 1.2 and  # Volume spike
            self._check_consecutive_candles("bullish", 2)):  # Price action confirmation
            
            return self._generate_signal("BUY", indicators)

        # Check for sell conditions
        if (rsi > 70 and  # Overbought
            macd[-1] < signal[-1] and  # Bearish MACD crossover
            current_volume > volume_sma * 1.2 and  # Volume spike
            self._check_consecutive_candles("bearish", 2)):  # Price action confirmation
            
            return self._generate_signal("SELL", indicators)

        return None

    def _check_consecutive_candles(self, pattern: str, count: int) -> bool:
        """Check for consecutive bullish/bearish candles"""
        if len(self.price_history) < count + 1:
            return False

        prices = self.price_history[-(count + 1):]
        if pattern == "bullish":
            return all(prices[i] < prices[i + 1] for i in range(count))
        else:  # bearish
            return all(prices[i] > prices[i + 1] for i in range(count))

    def _check_trading_conditions(self) -> bool:
        """Check if trading conditions are met"""
        current_time = datetime.now()

        # Check maximum trades per day
        if self.trades_today >= 15:
            self.logger.info("Maximum daily trades reached")
            return False

        # Check consecutive losses
        if self.consecutive_losses >= 3:
            self.logger.info("Maximum consecutive losses reached")
            return False

        # Ensure minimum time between signals (5 minutes)
        if (self.last_signal_time and 
            (current_time - self.last_signal_time).total_seconds() < 300):
            return False

        # Check for news events
        if self.news_filter.is_news_time(current_time, self.news_buffer_minutes):
            next_event = self.news_filter.get_next_event()
            if next_event:
                self.logger.info(f"Trading blocked due to upcoming news: {next_event['title']} at {next_event['time']}")
            return False

        # Cache upcoming events if needed
        if (not self.last_news_check or 
            (current_time - self.last_news_check).total_seconds() > 3600):  # Check every hour
            upcoming = self.news_filter.get_upcoming_events(24)
            if upcoming:
                self.logger.info(f"Upcoming news events in next 24h: {len(upcoming)}")
            self.last_news_check = current_time

        # Check market conditions
        is_favorable, confidence, reason = self.market_analyzer.is_favorable_condition()
        if not is_favorable or confidence < self.min_market_confidence:
            self.logger.info(f"Unfavorable market conditions: {reason} (confidence: {confidence:.2f})")
            return False

        # Get detailed market conditions for logging
        market_conditions = self.market_analyzer.get_market_conditions()
        if market_conditions:
            self.logger.debug(f"Market conditions: {market_conditions}")

        return True

    def _generate_signal(self, direction: str, indicators: dict) -> Signal:
        """Generate a trading signal with computed confidence"""
        # Calculate confidence based on indicator strength
        rsi_strength = abs(50 - indicators['rsi']) / 50
        macd_strength = abs(indicators['macd'] - indicators['macd_signal'])
        volume_strength = indicators['volume_ratio'] - 1

        # Combine indicators with weights
        confidence = (0.4 * rsi_strength + 
                     0.4 * macd_strength + 
                     0.2 * volume_strength)
        confidence = min(max(confidence, 0), 1)  # Normalize to 0-1

        signal = Signal(
            timestamp=self.timestamp_history[-1],
            direction=direction,
            asset="EUR/USD",
            expiry_minutes=1,  # Default to 1-minute expiry
            confidence=confidence,
            indicators=indicators
        )

        # Update tracking variables
        self.last_signal_time = signal.timestamp
        self.trades_today += 1

        return signal

    def record_trade_result(self, won: bool):
        """Record the result of a trade for risk management"""
        if won:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
