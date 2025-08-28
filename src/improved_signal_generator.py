"""
Improved Signal Generator for IQ 720 Trading Bot
This module addresses key issues in the original signal generator:
1. Reduces overconfidence in signals
2. Improves market regime detection
3. Adds proper uncertainty handling
4. Implements adaptive parameter selection
5. Enhances integration of technical and ML signals
"""
import numpy as np
import pandas as pd
import talib
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging
from enum import Enum

# Import existing components
from .utils.improved_ml_predictor import ImprovedMLPredictor
from .utils.market_analyzer import MarketAnalyzer
from .utils.news.forex_news import ForexNewsFilter

class MarketRegime(Enum):
    """Enum representing different market regimes"""
    STRONG_TREND_UP = "STRONG_TREND_UP"
    TREND_UP = "TREND_UP"
    STRONG_TREND_DOWN = "STRONG_TREND_DOWN"
    TREND_DOWN = "TREND_DOWN"
    CHOPPY = "CHOPPY"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"

class TradingSession(Enum):
    """Enum representing different trading sessions"""
    LONDON_NY_OVERLAP = "london_ny_overlap"
    LONDON_OPEN = "london_open"
    NY_SESSION = "ny_session"
    ASIAN_SESSION = "asian_session"
    WEEKEND = "weekend"
    UNKNOWN = "unknown"

@dataclass
class Signal:
    timestamp: datetime
    direction: str  # "BUY" or "SELL"
    asset: str
    expiry_minutes: int
    confidence: float
    indicators: dict
    uncertainty: float = 0.0  # Added uncertainty metric

class ImprovedSignalGenerator:
    def __init__(self, config: dict = None):
        """
        Initialize the improved signal generator with better defaults
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Initialize data containers
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.timestamp_history: List[datetime] = []
        self.open_price_history: List[float] = []
        self.high_price_history: List[float] = []
        self.low_price_history: List[float] = []
        
        # Trading state
        self.consecutive_losses = 0
        self.trades_today = 0
        self.last_signal_time: Optional[datetime] = None
        self.asset_name: Optional[str] = None
        
        # Initialize components
        self.news_filter = ForexNewsFilter()
        self.market_analyzer = MarketAnalyzer()
        
        # Use improved ML predictor
        self.ml_predictor = ImprovedMLPredictor(lookback_periods=100, sequence_length=20)
        
        # Configuration parameters with better defaults
        self.news_buffer_minutes = self.config.get('news_buffer_minutes', 15)
        self.min_market_confidence = self.config.get('min_market_confidence', 0.6)
        self.use_ml_predictions = self.config.get('use_ml_predictions', True)
        self.ml_confidence_threshold = self.config.get('ml_confidence_threshold', 0.6)  # Reduced from 0.65
        self.ml_weight = self.config.get('ml_weight', 0.5)  # Increased from 0.4
        self.max_daily_trades = self.config.get('max_daily_trades', 5)
        self.min_signal_interval_minutes = self.config.get('min_signal_interval_minutes', 30)
        
        # Adaptive parameters
        self.rsi_overbought = self.config.get('rsi_overbought', 70)
        self.rsi_oversold = self.config.get('rsi_oversold', 30)
        
        # State variables
        self.current_regime: MarketRegime = MarketRegime.UNKNOWN
        self.regime_confidence: float = 0.0
        self.current_session: TradingSession = TradingSession.UNKNOWN
        self.historical_data = None  # DataFrame to store historical data for ML
        self.last_news_check = None
    
    def add_candle(self, candle_data: dict, asset_name: str = "UNKNOWN") -> Optional[Signal]:
        """
        Process new candle data and potentially generate a signal
        
        Args:
            candle_data: Dictionary with OHLCV data
            asset_name: Name of the trading asset
            
        Returns:
            Optional Signal object if a trading signal is generated
        """
        try:
            # Extract candle data
            open_price = float(candle_data['open'])
            high_price = float(candle_data['high'])
            low_price = float(candle_data['low'])
            close_price = float(candle_data['close'])
            volume = float(candle_data['volume'])
            timestamp = datetime.fromtimestamp(candle_data['timestamp'])
            
            # Store asset name
            self.asset_name = asset_name

            # Add to history
            self.open_price_history.append(open_price)
            self.high_price_history.append(high_price)
            self.low_price_history.append(low_price)
            self.price_history.append(close_price)
            self.volume_history.append(volume)
            self.timestamp_history.append(timestamp)

            # Keep last 200 candles for analysis
            max_history = 200
            if len(self.price_history) > max_history:
                self.open_price_history = self.open_price_history[-max_history:]
                self.high_price_history = self.high_price_history[-max_history:]
                self.low_price_history = self.low_price_history[-max_history:]
                self.price_history = self.price_history[-max_history:]
                self.volume_history = self.volume_history[-max_history:]
                self.timestamp_history = self.timestamp_history[-max_history:]

            # Update historical data for ML
            self._update_historical_dataframe()
            
            # Only generate signals if we have enough data
            if len(self.price_history) < 50:
                self.logger.info(f"Not enough data for analysis yet. Have {len(self.price_history)} candles, need 50.")
                return None
                
            # Detect market regime
            self._detect_market_regime()
            
            # Detect trading session
            self._detect_trading_session()
            
            # Check trading conditions
            if not self._check_trading_conditions():
                return None

            return self._analyze_indicators()

        except Exception as e:
            self.logger.error(f"Error processing candle data: {e}")
            return None
            
    def _update_historical_dataframe(self):
        """Create/update pandas DataFrame for ML processing"""
        if len(self.timestamp_history) < 10:
            return
            
        # Create DataFrame with OHLCV data
        data = {
            'timestamp': self.timestamp_history,
            'open': self.open_price_history,
            'high': self.high_price_history,
            'low': self.low_price_history,
            'close': self.price_history,
            'volume': self.volume_history
        }
        
        self.historical_data = pd.DataFrame(data)
        self.historical_data.set_index('timestamp', inplace=True)
        
        # Train ML model if we have enough data and it's not trained yet
        if len(self.historical_data) >= 100 and not self.ml_predictor.is_trained:
            try:
                self.logger.info("Training ML predictor with historical data...")
                self.ml_predictor.train(self.historical_data)
                self.logger.info("ML predictor training complete")
            except Exception as e:
                self.logger.error(f"Error training ML predictor: {e}")
                # Try loading a pre-trained model if available
                try:
                    self.ml_predictor.load_models()
                except Exception as load_error:
                    self.logger.error(f"Error loading ML models: {load_error}")

    def _detect_market_regime(self):
        """
        Detect market regime using advanced methods
        Returns regime type and confidence score
        """
        if len(self.price_history) < 50:
            self.current_regime = MarketRegime.UNKNOWN
            self.regime_confidence = 0.0
            return
        
        prices = np.array(self.price_history)
        
        # Calculate key metrics
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns[-20:]) * np.sqrt(252)  # Annualized
        
        # Calculate trend metrics
        sma20 = talib.SMA(prices, timeperiod=20)[-1]
        sma50 = talib.SMA(prices, timeperiod=50)[-1]
        sma_ratio = sma20 / sma50 if sma50 > 0 else 1.0
        
        # Direction of last N periods
        n_periods = 10
        if len(prices) >= n_periods:
            up_periods = sum(prices[-n_periods:] > np.roll(prices[-n_periods:], 1)[1:])
            trend_strength = abs(up_periods - (n_periods-1) / 2) / ((n_periods-1) / 2)
        else:
            trend_strength = 0.0
        
        # Detect regime
        if volatility > 0.2:  # High volatility threshold
            self.current_regime = MarketRegime.HIGH_VOLATILITY
            self.regime_confidence = min(volatility / 0.2, 1.0)
        elif volatility < 0.05:  # Low volatility threshold
            self.current_regime = MarketRegime.LOW_VOLATILITY
            self.regime_confidence = 1.0 - min(volatility / 0.05, 1.0)
        elif trend_strength > 0.6:  # Strong trend
            if sma_ratio > 1.01:  # Uptrend
                self.current_regime = MarketRegime.STRONG_TREND_UP
                self.regime_confidence = min((sma_ratio - 1.0) * 50, 1.0)
            elif sma_ratio < 0.99:  # Downtrend
                self.current_regime = MarketRegime.STRONG_TREND_DOWN
                self.regime_confidence = min((1.0 - sma_ratio) * 50, 1.0)
            else:  # Not clear enough
                self.current_regime = MarketRegime.RANGING
                self.regime_confidence = 0.5
        elif trend_strength > 0.3:  # Moderate trend
            if sma_ratio > 1.005:  # Uptrend
                self.current_regime = MarketRegime.TREND_UP
                self.regime_confidence = min((sma_ratio - 1.0) * 100, 1.0)
            elif sma_ratio < 0.995:  # Downtrend
                self.current_regime = MarketRegime.TREND_DOWN
                self.regime_confidence = min((1.0 - sma_ratio) * 100, 1.0)
            else:  # Not clear enough
                self.current_regime = MarketRegime.RANGING
                self.regime_confidence = 0.5
        elif np.std(returns[-10:]) > np.std(returns[-30:]):  # Increasing volatility - choppy
            self.current_regime = MarketRegime.CHOPPY
            self.regime_confidence = 0.7
        else:  # Default to ranging
            self.current_regime = MarketRegime.RANGING
            self.regime_confidence = 0.6
            
        self.logger.debug(f"Detected market regime: {self.current_regime.value} with {self.regime_confidence:.2f} confidence")
    
    def _detect_trading_session(self):
        """
        Detect current trading session based on timestamp
        """
        if not self.timestamp_history:
            self.current_session = TradingSession.UNKNOWN
            return
            
        current_time = self.timestamp_history[-1]
        
        # Check if weekend
        if current_time.weekday() >= 5:  # 5=Saturday, 6=Sunday
            self.current_session = TradingSession.WEEKEND
            return
            
        # Get hour in UTC
        hour_utc = current_time.hour
        
        # Define sessions (in UTC)
        # Asian session: 22:00-07:00 UTC
        # London session: 07:00-16:00 UTC
        # NY session: 12:00-20:00 UTC
        # London-NY overlap: 12:00-16:00 UTC
        
        if 12 <= hour_utc < 16:
            self.current_session = TradingSession.LONDON_NY_OVERLAP
        elif 7 <= hour_utc < 12:
            self.current_session = TradingSession.LONDON_OPEN
        elif 16 <= hour_utc < 20:
            self.current_session = TradingSession.NY_SESSION
        elif 22 <= hour_utc or hour_utc < 7:
            self.current_session = TradingSession.ASIAN_SESSION
        else:
            self.current_session = TradingSession.UNKNOWN
            
    def _check_trading_conditions(self) -> bool:
        """Check if trading conditions are met"""
        current_time = datetime.now()
        
        # Don't trade too frequently
        if self.last_signal_time:
            minutes_since_last_signal = (current_time - self.last_signal_time).total_seconds() / 60
            if minutes_since_last_signal < self.min_signal_interval_minutes:
                self.logger.debug(f"Skipping analysis: {minutes_since_last_signal:.1f} minutes since last signal (minimum {self.min_signal_interval_minutes})")
                return False
        
        # Limit daily trades
        if self.trades_today >= self.max_daily_trades:
            self.logger.debug(f"Reached maximum daily trades: {self.trades_today}")
            return False
            
        # Check for important news events
        if self.news_filter and self.asset_name:
            if self._check_news_events():
                self.logger.info(f"Skipping analysis: Important news event for {self.asset_name}")
                return False
        
        # Don't trade during weekend
        if self.current_session == TradingSession.WEEKEND:
            self.logger.debug("Skipping analysis: Weekend session")
            return False
            
        # Don't trade in very uncertain markets
        if self.current_regime == MarketRegime.HIGH_VOLATILITY and self.regime_confidence > 0.8:
            self.logger.debug("Skipping analysis: High volatility market")
            return False
            
        # Don't trade in very choppy markets
        if self.current_regime == MarketRegime.CHOPPY and self.regime_confidence > 0.8:
            self.logger.debug("Skipping analysis: Choppy market")
            return False
            
        # Adapt RSI parameters based on market regime
        self._adapt_parameters()
        
        return True
        
    def _check_news_events(self) -> bool:
        """Check for important news events"""
        if not self.news_filter:
            return False
            
        current_time = datetime.now()
        
        # Only check news every 10 minutes to avoid API rate limits
        if self.last_news_check and (current_time - self.last_news_check).total_seconds() < 600:
            return False
            
        # Update last check time
        self.last_news_check = current_time
        
        # Check for important news in the next buffer period
        important_news = self.news_filter.get_important_events(
            self.asset_name, 
            current_time, 
            current_time + timedelta(minutes=self.news_buffer_minutes)
        )
        
        return len(important_news) > 0
        
    def _adapt_parameters(self):
        """Adapt technical indicator parameters based on market regime"""
        # Adapt RSI thresholds based on market regime
        if self.current_regime in [MarketRegime.STRONG_TREND_UP, MarketRegime.TREND_UP]:
            # In uptrends, RSI can stay higher for longer
            self.rsi_overbought = 75
            self.rsi_oversold = 35
        elif self.current_regime in [MarketRegime.STRONG_TREND_DOWN, MarketRegime.TREND_DOWN]:
            # In downtrends, RSI can stay lower for longer
            self.rsi_overbought = 65
            self.rsi_oversold = 25
        elif self.current_regime == MarketRegime.RANGING:
            # In ranging markets, standard thresholds work well
            self.rsi_overbought = 70
            self.rsi_oversold = 30
        elif self.current_regime == MarketRegime.CHOPPY:
            # In choppy markets, use tighter thresholds
            self.rsi_overbought = 65
            self.rsi_oversold = 35
        else:
            # Default values
            self.rsi_overbought = 70
            self.rsi_oversold = 30

    def _analyze_indicators(self) -> Optional[Signal]:
        """
        Analyze technical indicators and ML predictions to generate trading signals
        
        Returns:
            Optional Signal object if a trading signal is generated
        """
        # Calculate traditional indicators with numpy arrays
        prices = np.array(self.price_history)
        volumes = np.array(self.volume_history)
        
        # Calculate RSI
        rsi = talib.RSI(prices, timeperiod=14)[-1]
        
        # Calculate MACD
        macd, signal, hist = talib.MACD(prices, fastperiod=12, slowperiod=26, signalperiod=9)
        macd_value = macd[-1]
        signal_value = signal[-1]
        hist_value = hist[-1]
        
        # Volume analysis
        volume_sma = talib.SMA(volumes, timeperiod=10)[-1]
        current_volume = volumes[-1]
        volume_ratio = current_volume / volume_sma if volume_sma > 0 else 1.0

        # Initialize indicator results
        indicators = {
            'rsi': rsi,
            'macd': macd_value,
            'macd_signal': signal_value,
            'macd_hist': hist_value,
            'volume_ratio': volume_ratio,
            'regime': self.current_regime.value,
            'regime_confidence': self.regime_confidence,
            'session': self.current_session.value
        }
        
        # Traditional signal detection with more conservative thresholds
        traditional_signal = None
        traditional_confidence = 0.0
        
        # Check for buy conditions - more stringent criteria
        if (rsi < self.rsi_oversold and  # Oversold
            macd_value > signal_value and  # Bullish MACD crossover
            hist_value > 0 and  # Positive histogram
            volume_ratio > 1.1 and  # Volume spike
            self._check_consecutive_candles("bullish", 2)):  # Price action confirmation
            
            traditional_signal = "BUY"
            # More conservative confidence calculation
            traditional_confidence = 0.65 + min((self.rsi_oversold - rsi) / 30, 0.15) + min((volume_ratio - 1) / 5, 0.1)
            traditional_confidence = min(traditional_confidence, 0.9)  # Cap confidence

        # Check for sell conditions - more stringent criteria
        elif (rsi > self.rsi_overbought and  # Overbought
              macd_value < signal_value and  # Bearish MACD crossover
              hist_value < 0 and  # Negative histogram
              volume_ratio > 1.1 and  # Volume spike
              self._check_consecutive_candles("bearish", 2)):  # Price action confirmation
            
            traditional_signal = "SELL"
            # More conservative confidence calculation
            traditional_confidence = 0.65 + min((rsi - self.rsi_overbought) / 30, 0.15) + min((volume_ratio - 1) / 5, 0.1)
            traditional_confidence = min(traditional_confidence, 0.9)  # Cap confidence
        
        # ML-based signal detection
        ml_signal = None
        ml_confidence = 0.0
        ml_uncertainty = 0.5  # Default uncertainty
        ml_details = {}
        
        if self.use_ml_predictions and self.historical_data is not None and len(self.historical_data) >= 100:
            try:
                # Get ML prediction with improved ML predictor
                prediction, confidence, details = self.ml_predictor.predict(self.historical_data)
                
                # Extract uncertainty from ML prediction
                ml_uncertainty = details.get('uncertainty', 0.5)
                is_anomaly = details.get('is_anomaly', False)
                
                # Validate prediction against market conditions
                is_valid, adjusted_confidence, validation_details = self.ml_predictor.validate_prediction(
                    prediction, 
                    confidence,
                    self.current_regime.value,
                    self.current_session.value,
                    is_anomaly
                )
                
                if is_valid and adjusted_confidence >= self.ml_confidence_threshold:
                    ml_signal = "BUY" if prediction else "SELL"
                    ml_confidence = adjusted_confidence
                    
                    # Store detailed ML info
                    ml_details = {
                        'raw_confidence': confidence,
                        'adjusted_confidence': adjusted_confidence,
                        'uncertainty': ml_uncertainty,
                        'top_features': details.get('top_features', {}),
                        'is_anomaly': is_anomaly
                    }
                    
                # Add ML indicators to the result
                indicators['ml_prediction'] = "BUY" if prediction else "SELL"
                indicators['ml_confidence'] = confidence
                indicators['ml_adjusted_confidence'] = adjusted_confidence
                indicators['ml_uncertainty'] = ml_uncertainty
                indicators['ml_top_features'] = list(details.get('top_features', {}).keys())[:3]
                
            except Exception as e:
                self.logger.error(f"Error getting ML prediction: {e}")
        
        # Make final decision combining traditional and ML signals
        # with uncertainty-aware combination
        final_signal = None
        final_confidence = 0.0
        final_uncertainty = 0.5  # Default uncertainty
        
        # If both signals agree, boost confidence while accounting for uncertainty
        if traditional_signal and ml_signal and traditional_signal == ml_signal:
            final_signal = traditional_signal
            
            # Weight by inverse of uncertainty
            trad_weight = self.ml_weight
            ml_weight = 1 - self.ml_weight
            
            # Combine confidences with uncertainty weighting
            final_confidence = (traditional_confidence * trad_weight) + (ml_confidence * ml_weight)
            
            # Adjust final confidence by overall uncertainty
            final_uncertainty = (ml_uncertainty * ml_weight) + (0.3 * trad_weight)  # Assume traditional has 0.3 uncertainty
            final_confidence = final_confidence * (1 - final_uncertainty * 0.5)
            
            self.logger.info(f"Traditional and ML signals agree on {final_signal}")
            
        # If only traditional signal is available or strong enough
        elif traditional_signal and (not ml_signal or traditional_confidence > 0.8):
            final_signal = traditional_signal
            final_confidence = traditional_confidence * 0.9  # Slightly reduce confidence
            final_uncertainty = 0.4  # Higher uncertainty without ML confirmation
            self.logger.info(f"Using traditional signal: {final_signal}")
            
        # If only ML signal is available and strong with low uncertainty
        elif ml_signal and ml_confidence > 0.75 and ml_uncertainty < 0.3:
            final_signal = ml_signal
            final_confidence = ml_confidence * 0.95  # Slightly reduce confidence
            final_uncertainty = ml_uncertainty
            self.logger.info(f"Using ML signal: {final_signal}")
        
        # If signals disagree, use the one with higher confidence adjusted for uncertainty
        elif traditional_signal and ml_signal:
            # Adjust confidences by uncertainty
            trad_adj = traditional_confidence * (1 - 0.3)  # Assume 0.3 uncertainty for traditional
            ml_adj = ml_confidence * (1 - ml_uncertainty)
            
            if trad_adj > ml_adj:
                final_signal = traditional_signal
                final_confidence = trad_adj * 0.8  # Reduce confidence due to disagreement
                final_uncertainty = 0.4
                self.logger.info(f"Signals disagree, using traditional signal with reduced confidence")
            else:
                final_signal = ml_signal
                final_confidence = ml_adj * 0.8  # Reduce confidence due to disagreement
                final_uncertainty = ml_uncertainty + 0.1  # Increase uncertainty due to disagreement
                self.logger.info(f"Signals disagree, using ML signal with reduced confidence")
                
        # No signal case
        if not final_signal:
            return None
        
        # Cap confidence at 0.9 to avoid overconfidence
        final_confidence = min(final_confidence, 0.9)
        
        # Only proceed if confidence is sufficient
        if final_confidence < self.ml_confidence_threshold:
            self.logger.debug(f"Signal confidence {final_confidence:.2f} below threshold {self.ml_confidence_threshold}")
            return None
            
        # Add ML details to indicators if available
        if ml_details:
            indicators['ml_details'] = ml_details
        
        # Generate final signal
        expiry_minutes = self._determine_optimal_expiry()
        
        signal = Signal(
            timestamp=datetime.now(),
            direction=final_signal,
            asset=self.asset_name or "UNKNOWN",
            expiry_minutes=expiry_minutes,
            confidence=final_confidence,
            indicators=indicators,
            uncertainty=final_uncertainty
        )
        
        # Update state
        self.last_signal_time = datetime.now()
        self.trades_today += 1
        
        return signal
    
    def _determine_optimal_expiry(self) -> int:
        """Determine optimal expiry time based on market conditions"""
        # Default expiry
        expiry = 15  # minutes
        
        # Adjust based on volatility
        if self.current_regime == MarketRegime.HIGH_VOLATILITY:
            expiry = 10  # Shorter expiry in volatile markets
        elif self.current_regime == MarketRegime.LOW_VOLATILITY:
            expiry = 20  # Longer expiry in low volatility
        
        # Adjust based on session
        if self.current_session == TradingSession.ASIAN_SESSION:
            expiry = max(expiry, 20)  # Longer expiry in less active session
        elif self.current_session == TradingSession.LONDON_NY_OVERLAP:
            expiry = min(expiry, 15)  # Shorter expiry in active session
            
        return expiry
            
    def _check_consecutive_candles(self, pattern: str, count: int) -> bool:
        """Check for consecutive bullish/bearish candles"""
        if len(self.price_history) < count + 1:
            return False

        prices = self.price_history[-(count + 1):]
        if pattern == "bullish":
            return all(prices[i] < prices[i + 1] for i in range(count))
        else:  # bearish
            return all(prices[i] > prices[i + 1] for i in range(count))

    def reset_daily_counter(self):
        """Reset the daily trade counter"""
        self.trades_today = 0
