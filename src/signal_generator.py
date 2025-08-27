import numpy as np
import pandas as pd
import talib
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
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
from .utils.ml_predictor import MLPredictor

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
        self.open_price_history: List[float] = []
        self.high_price_history: List[float] = []
        self.low_price_history: List[float] = []
        self.consecutive_losses = 0
        self.trades_today = 0
        self.last_signal_time: Optional[datetime] = None
        
        # Initialize components
        self.news_filter = ForexNewsFilter()
        self.market_analyzer = MarketAnalyzer()
        self.market_regime_detector = MarketRegimeDetector()
        self.pattern_recognition = PatternRecognition()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.real_time_optimizer = RealTimeOptimizer()
        self.ml_predictor = MLPredictor(lookback_periods=100, sequence_length=20)
        
        # Configuration parameters
        self.last_news_check = None
        self.news_buffer_minutes = 15
        self.min_market_confidence = 0.6  # Minimum market condition confidence
        self.use_ml_predictions = True  # Flag to toggle ML usage
        self.ml_confidence_threshold = 0.65  # Minimum ML confidence to consider
        self.ml_weight = 0.4  # Weight of ML prediction in final decision
        
        # State variables
        self.current_regime: Optional[MarketRegime] = None
        self.regime_confidence: float = 0.0
        self.pattern_memory = []  # Store recent pattern signals
        self.ml_predictions_history = []  # Store recent ML predictions
        self.last_calculation_time = datetime.now()
        self.execution_times = []  # Track signal generation speed
        self.historical_data = None  # DataFrame to store historical data for ML

    def add_candle(self, candle_data: dict) -> Optional[Signal]:
        """
        Process new candle data and potentially generate a signal
        
        Args:
            candle_data: Dictionary with OHLCV data
            
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

            # Add to history
            self.open_price_history.append(open_price)
            self.high_price_history.append(high_price)
            self.low_price_history.append(low_price)
            self.price_history.append(close_price)
            self.volume_history.append(volume)
            self.timestamp_history.append(timestamp)

            # Update market analyzer
            self.market_analyzer.add_candle(candle_data)

            # Keep last 200 candles for analysis (increased for ML models)
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
            if len(self.price_history) < 50:  # Increased minimum required for ML features
                self.logger.info(f"Not enough data for analysis yet. Have {len(self.price_history)} candles, need 50.")
                return None

            return self._analyze_indicators()

        except Exception as e:
            self.logger.error(f"Error processing candle data: {e}")
            return None
            
    def _update_historical_dataframe(self):
        """Create/update pandas DataFrame for ML processing"""
        import pandas as pd
        
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
                except:
                    pass

    def _analyze_indicators(self) -> Optional[Signal]:
        """
        Analyze technical indicators and ML predictions to generate trading signals
        
        Returns:
            Optional Signal object if a trading signal is generated
        """
        if not self._check_trading_conditions():
            return None

        prices = np.array(self.price_history)
        volumes = np.array(self.volume_history)
        
        start_time = datetime.now()

        # Calculate traditional indicators
        rsi = talib.RSI(prices, timeperiod=14)[-1]
        macd, signal, hist = talib.MACD(prices, fastperiod=12, slowperiod=26, signalperiod=9)
        volume_sma = talib.SMA(volumes, timeperiod=10)[-1]
        current_volume = volumes[-1]
        
        # Detect market regime
        if len(prices) >= 50:
            self.current_regime, self.regime_confidence = self.market_regime_detector.detect_regime(prices)
            self.logger.debug(f"Current market regime: {self.current_regime.name}, confidence: {self.regime_confidence:.2f}")
        
        # Get current session
        current_time = self.timestamp_history[-1]
        session_manager = SessionManager()
        current_session = session_manager.get_current_session(current_time)

        # Initialize indicator results
        indicators = {
            'rsi': rsi,
            'macd': macd[-1],
            'macd_signal': signal[-1],
            'macd_hist': hist[-1],
            'volume_ratio': current_volume / volume_sma if volume_sma > 0 else 0,
            'regime': self.current_regime.name if self.current_regime else "UNKNOWN",
            'session': current_session
        }
        
        # Traditional signal detection
        traditional_signal = None
        traditional_confidence = 0.0
        
        # Check for buy conditions
        if (rsi < 30 and  # Oversold
            macd[-1] > signal[-1] and  # Bullish MACD crossover
            current_volume > volume_sma * 1.2 and  # Volume spike
            self._check_consecutive_candles("bullish", 2)):  # Price action confirmation
            
            traditional_signal = "BUY"
            traditional_confidence = 0.7 + min((30 - rsi) / 30, 0.2) + min((current_volume / volume_sma - 1) / 2, 0.1)

        # Check for sell conditions
        elif (rsi > 70 and  # Overbought
            macd[-1] < signal[-1] and  # Bearish MACD crossover
            current_volume > volume_sma * 1.2 and  # Volume spike
            self._check_consecutive_candles("bearish", 2)):  # Price action confirmation
            
            traditional_signal = "SELL"
            traditional_confidence = 0.7 + min((rsi - 70) / 30, 0.2) + min((current_volume / volume_sma - 1) / 2, 0.1)
        
        # Get pattern recognition signals
        if len(self.open_price_history) >= 10:
            pattern_signals = self._analyze_patterns()
            if pattern_signals:
                indicators.update({"patterns": pattern_signals})
                
                # Incorporate pattern confidence if available and no traditional signal yet
                if not traditional_signal and pattern_signals.get('direction') in ['BULLISH', 'BEARISH']:
                    pattern_confidence = pattern_signals.get('confidence', 0)
                    if pattern_confidence > 0.75:
                        traditional_signal = "BUY" if pattern_signals['direction'] == 'BULLISH' else "SELL"
                        traditional_confidence = pattern_confidence
        
        # ML-based signal detection
        ml_signal = None
        ml_confidence = 0.0
        ml_details = {}
        
        if self.use_ml_predictions and self.historical_data is not None and len(self.historical_data) >= 100:
            try:
                # Get ML prediction
                prediction, confidence, details = self.ml_predictor.predict(self.historical_data)
                
                # Validate ML prediction based on market conditions
                is_anomaly = details.get('is_anomaly', False)
                is_valid, adjusted_confidence, validation_details = self.ml_predictor.validate_prediction(
                    prediction, 
                    confidence,
                    self.current_regime.name if self.current_regime else "UNKNOWN",
                    current_session,
                    is_anomaly
                )
                
                if is_valid and adjusted_confidence >= self.ml_confidence_threshold:
                    ml_signal = "BUY" if prediction else "SELL"
                    ml_confidence = adjusted_confidence
                    
                    # Store more detailed ML info
                    ml_details = {
                        'raw_confidence': confidence,
                        'adjusted_confidence': adjusted_confidence,
                        'top_features': details.get('top_features', {}),
                        'is_anomaly': is_anomaly,
                        'price_prediction': details.get('price_prediction'),
                        'validation': validation_details
                    }
                    
                    # Store prediction history
                    self.ml_predictions_history.append({
                        'timestamp': current_time,
                        'prediction': ml_signal,
                        'confidence': ml_confidence,
                        'details': ml_details
                    })
                    if len(self.ml_predictions_history) > 100:
                        self.ml_predictions_history = self.ml_predictions_history[-100:]
                        
                # Add ML indicators to the result
                indicators['ml_prediction'] = "BUY" if prediction else "SELL"
                indicators['ml_confidence'] = confidence
                indicators['ml_adjusted_confidence'] = adjusted_confidence
                indicators['ml_top_features'] = list(details.get('top_features', {}).keys())[:3]
                
            except Exception as e:
                self.logger.error(f"Error getting ML prediction: {e}")
        
        # Make final decision combining traditional and ML signals
        final_signal = None
        final_confidence = 0.0
        
        # If both signals agree, boost confidence
        if traditional_signal and ml_signal and traditional_signal == ml_signal:
            final_signal = traditional_signal
            final_confidence = (traditional_confidence * (1 - self.ml_weight)) + (ml_confidence * self.ml_weight) + 0.05
            self.logger.info(f"Traditional and ML signals agree on {final_signal}")
            
        # If only traditional signal is available or strong enough
        elif traditional_signal and (not ml_signal or traditional_confidence > 0.8):
            final_signal = traditional_signal
            final_confidence = traditional_confidence
            self.logger.info(f"Using traditional signal: {final_signal}")
            
        # If only ML signal is available and strong
        elif ml_signal and ml_confidence > 0.75:
            final_signal = ml_signal
            final_confidence = ml_confidence
            self.logger.info(f"Using ML signal: {final_signal}")
        
        # If signals disagree, use the one with higher confidence
        elif traditional_signal and ml_signal:
            if traditional_confidence > ml_confidence:
                final_signal = traditional_signal
                final_confidence = traditional_confidence * 0.9  # Reduce confidence due to disagreement
                self.logger.info(f"Signals disagree, using traditional signal with reduced confidence")
            else:
                final_signal = ml_signal
                final_confidence = ml_confidence * 0.9  # Reduce confidence due to disagreement
                self.logger.info(f"Signals disagree, using ML signal with reduced confidence")
                
        # No signal case
        if not final_signal:
            return None
            
        # Generate final signal
        if final_signal:
            # Add ML details to indicators if available
            if ml_details:
                indicators['ml_details'] = ml_details
            
            # Track execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            self.execution_times.append(execution_time)
            if len(self.execution_times) > 100:
                self.execution_times = self.execution_times[-100:]
                
            self.logger.info(f"Signal generation took {execution_time:.3f} seconds")
            
            return self._generate_signal(final_signal, indicators, final_confidence)
            
        return None
        
    def _analyze_patterns(self) -> Dict[str, Any]:
        """Analyze candlestick patterns"""
        if len(self.open_price_history) < 10:
            return {}
            
        # Get arrays for pattern recognition
        open_prices = np.array(self.open_price_history)
        high_prices = np.array(self.high_price_history)
        low_prices = np.array(self.low_price_history)
        close_prices = np.array(self.price_history)
        
        # Identify patterns
        patterns = self.pattern_recognition.identify_patterns(
            high_prices, low_prices, open_prices, close_prices
        )
        
        if not patterns:
            return {}
            
        # Find strongest pattern
        strongest_pattern = None
        highest_confidence = 0.0
        
        for pattern_name, (pattern_type, strength, confidence) in patterns.items():
            if confidence > highest_confidence:
                highest_confidence = confidence
                strongest_pattern = {
                    'name': pattern_name,
                    'type': pattern_type.value,
                    'strength': strength.value,
                    'confidence': confidence,
                    'direction': 'BULLISH' if pattern_type in [PatternType.BULLISH, PatternType.REVERSAL] else 'BEARISH'
                }
                
        if strongest_pattern:
            # Add to pattern memory
            self.pattern_memory.append({
                'timestamp': self.timestamp_history[-1],
                'pattern': strongest_pattern
            })
            if len(self.pattern_memory) > 20:
                self.pattern_memory = self.pattern_memory[-20:]
                
            return strongest_pattern
                
        return {}

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

    def _generate_signal(self, direction: str, indicators: dict, confidence_override: float = None) -> Signal:
        """
        Generate a trading signal with computed confidence
        
        Args:
            direction: "BUY" or "SELL"
            indicators: Dictionary of technical indicators and their values
            confidence_override: Optional pre-calculated confidence value
            
        Returns:
            Signal object with trade details
        """
        # Use provided confidence if available
        if confidence_override is not None:
            confidence = confidence_override
        else:
            # Calculate confidence based on indicator strength
            rsi_strength = abs(50 - indicators['rsi']) / 50
            macd_strength = abs(indicators['macd'] - indicators['macd_signal'])
            volume_strength = indicators['volume_ratio'] - 1

            # Combine indicators with weights
            confidence = (0.4 * rsi_strength + 
                        0.4 * macd_strength + 
                        0.2 * volume_strength)
        
        # Adjust expiry based on confidence
        expiry_minutes = 1  # Default
        if confidence > 0.8:
            expiry_minutes = 5  # More confident signals get longer expiry
        elif confidence > 0.7:
            expiry_minutes = 3
            
        # Ensure confidence is normalized
        confidence = min(max(confidence, 0), 1)  # Normalize to 0-1

        # Create signal object
        signal = Signal(
            timestamp=self.timestamp_history[-1],
            direction=direction,
            asset="EUR/USD",
            expiry_minutes=expiry_minutes,
            confidence=confidence,
            indicators=indicators
        )

        # Log signal details
        pattern_info = ""
        if 'patterns' in indicators:
            pattern = indicators['patterns']
            pattern_info = f", Pattern: {pattern.get('name', 'Unknown')} ({pattern.get('confidence', 0):.2f})"
            
        ml_info = ""
        if 'ml_confidence' in indicators:
            ml_info = f", ML: {indicators.get('ml_prediction', 'Unknown')} ({indicators.get('ml_adjusted_confidence', 0):.2f})"
            
        self.logger.info(
            f"Signal generated: {direction} {signal.asset} with {confidence:.2f} confidence, "
            f"expiry: {expiry_minutes}m{pattern_info}{ml_info}"
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
