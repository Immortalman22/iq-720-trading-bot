"""
Enhanced signal generator with pair-specific logic, signal ranking, and time-based trading.
"""
import numpy as np
import pandas as pd
import talib
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import datetime
import logging

# Import base classes
from ..signal_generator import SignalGenerator, Signal

# Import utility modules
from .pair_specific_settings import pair_settings
from .signal_ranker import SignalRanker, RankedSignal
from .correlation_manager import CorrelationManager
from .pair_performance_tracker import PairPerformanceTracker
from .dynamic_asset_selector import DynamicAssetSelector
from .time_logic import TimeLogic
from .improved_indicators import improved_indicators

@dataclass
class EnhancedSignal(Signal):
    """Enhanced trading signal with additional attributes"""
    strength_score: float = 0.0
    strength_factors: Dict[str, float] = None
    time_context: str = ""
    is_tradable: bool = True
    market_session: str = ""
    rank: int = 0

class EnhancedSignalGenerator(SignalGenerator):
    """
    Enhanced signal generator with additional features:
    - Pair-specific indicator settings
    - Signal strength ranking
    - Correlation management
    - Performance tracking
    - Dynamic asset selection
    - Time-based trading logic
    - Improved indicator calculations
    """
    
    def __init__(self):
        # Initialize base class
        super().__init__()
        
        # Initialize enhanced components
        self.pair_settings = pair_settings
        self.signal_ranker = SignalRanker()
        self.correlation_manager = CorrelationManager()
        self.performance_tracker = PairPerformanceTracker()
        self.asset_selector = DynamicAssetSelector()
        self.time_logic = TimeLogic()
        
        # Track pair-specific data
        self.pair_price_history = {}
        self.pair_volume_history = {}
        self.pair_timestamp_history = {}
        
        # Tracking generated signals
        self.recent_signals = []
        self.max_recent_signals = 50
        self.active_signals = {}  # Currently active signals
        
        self.logger.info("Enhanced signal generator initialized")
        
    def add_candle(self, candle_data: dict) -> Optional[EnhancedSignal]:
        """Process new candle data and potentially generate an enhanced signal"""
        try:
            # Extract candle data
            close_price = float(candle_data['close'])
            open_price = float(candle_data.get('open', close_price))
            high_price = float(candle_data.get('high', close_price))
            low_price = float(candle_data.get('low', close_price))
            volume = float(candle_data.get('volume', 0))
            timestamp = datetime.fromtimestamp(candle_data['timestamp'])
            pair = candle_data.get('asset', "EUR/USD")  # Default to EUR/USD if not specified
            
            # Initialize pair data structures if needed
            if pair not in self.pair_price_history:
                self.pair_price_history[pair] = []
                self.pair_volume_history[pair] = []
                self.pair_timestamp_history[pair] = []
                
            # Add to history
            self.pair_price_history[pair].append(close_price)
            self.pair_volume_history[pair].append(volume)
            self.pair_timestamp_history[pair].append(timestamp)
            
            # Update correlation manager
            self.correlation_manager.update_price_data(pair, close_price, timestamp)
            
            # Update asset selector with OHLC data
            ohlc = {'open': open_price, 'high': high_price, 'low': low_price, 'close': close_price}
            self.asset_selector.update_price_data(pair, ohlc, timestamp)
            
            # Keep last 100 candles for analysis
            max_history = 100
            if len(self.pair_price_history[pair]) > max_history:
                self.pair_price_history[pair] = self.pair_price_history[pair][-max_history:]
                self.pair_volume_history[pair] = self.pair_volume_history[pair][-max_history:]
                self.pair_timestamp_history[pair] = self.pair_timestamp_history[pair][-max_history:]
                
            # Only generate signals if we have enough data
            min_required = 50  # Increased for more reliable signals
            if len(self.pair_price_history[pair]) < min_required:
                return None
                
            # Generate signal if conditions are met
            signal = self._analyze_pair(pair, timestamp)
            
            if signal:
                # Add to recent signals
                self.recent_signals.append(signal)
                if len(self.recent_signals) > self.max_recent_signals:
                    self.recent_signals = self.recent_signals[-self.max_recent_signals:]
                
            return signal
                
        except Exception as e:
            self.logger.error(f"Error processing candle data: {e}")
            return None
            
    def _analyze_pair(self, pair: str, timestamp: datetime) -> Optional[EnhancedSignal]:
        """
        Analyze a specific currency pair and generate a signal if conditions are met.
        
        Args:
            pair: Currency pair to analyze
            timestamp: Current timestamp
            
        Returns:
            EnhancedSignal if conditions are met, otherwise None
        """
        # Check if trading conditions are met
        if not self._check_enhanced_trading_conditions(pair, timestamp):
            return None
            
        # Get pair-specific settings
        settings = self.pair_settings.get_settings(pair)
        
        # Get price and volume data
        prices = np.array(self.pair_price_history[pair])
        volumes = np.array(self.pair_volume_history[pair])
        
        # Calculate indicators with improved methods and pair-specific settings
        indicators = improved_indicators.calculate_all_indicators(prices, volumes, settings)
        
        if not indicators:
            return None
            
        # Check for buy conditions with pair-specific thresholds
        signal_threshold = settings.get('signal_threshold', 0.7)
        
        # Check for buy signal
        buy_signal = self._check_buy_signal(pair, indicators, settings)
        
        # Check for sell signal
        sell_signal = self._check_sell_signal(pair, indicators, settings)
        
        # Generate signal if conditions are met
        if buy_signal and buy_signal >= signal_threshold:
            return self._generate_enhanced_signal(pair, "BUY", indicators, timestamp, buy_signal)
        elif sell_signal and sell_signal >= signal_threshold:
            return self._generate_enhanced_signal(pair, "SELL", indicators, timestamp, sell_signal)
            
        return None
        
    def _check_buy_signal(self, pair: str, indicators: Dict, settings: Dict) -> float:
        """
        Check if conditions for a buy signal are met.
        
        Args:
            pair: Currency pair
            indicators: Calculated indicators
            settings: Pair-specific settings
            
        Returns:
            Signal strength if conditions are met, otherwise 0
        """
        # Initialize signal components
        signal_components = []
        weights = []
        
        # RSI oversold condition
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 40:
                # Stronger signal the lower the RSI
                rsi_strength = (40 - rsi) / 40  # 0 to 1 scale
                signal_components.append(rsi_strength)
                weights.append(0.3)
        
        # MACD bullish crossover or positive histogram
        if 'macd' in indicators and 'macd_signal' in indicators:
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            
            # Check crossover
            macd_crossover = improved_indicators.detect_indicator_crossover(
                np.array([indicators.get('macd_prev', macd), macd]),
                np.array([indicators.get('macd_signal_prev', macd_signal), macd_signal])
            )
            
            if macd_crossover == 'bullish' or (macd > macd_signal and indicators.get('macd_hist_slope', 0) > 0):
                macd_strength = min(1, abs(macd - macd_signal) * 1000)  # Scale appropriately
                signal_components.append(macd_strength)
                weights.append(0.3)
                
        # Stochastic oversold or bullish crossover
        if 'stoch_k' in indicators and 'stoch_d' in indicators:
            stoch_k = indicators['stoch_k']
            stoch_d = indicators['stoch_d']
            
            if stoch_k < 30 and stoch_k > stoch_d:
                stoch_strength = (30 - stoch_k) / 30
                signal_components.append(stoch_strength)
                weights.append(0.2)
                
        # Bollinger Band bounce from lower band
        if 'bb_lower' in indicators and 'bb_position' in indicators:
            bb_position = indicators['bb_position']
            
            if bb_position < 0.2:  # Close to lower band
                bb_strength = 1 - bb_position
                signal_components.append(bb_strength)
                weights.append(0.2)
                
        # Price action confirmation (consecutive bullish candles)
        lookback = settings.get('price_action_lookback', 3)
        if self._check_consecutive_candles(self.pair_price_history[pair], "bullish", lookback):
            signal_components.append(1.0)
            weights.append(0.1)
            
        # Volume confirmation
        if 'volume_ratio' in indicators and indicators['volume_ratio'] > 1.2:
            volume_strength = min(1.0, (indicators['volume_ratio'] - 1) / 2)
            signal_components.append(volume_strength)
            weights.append(0.1)
            
        # Trend alignment
        if 'trend_direction' in indicators and indicators['trend_direction'] == 'UP':
            signal_components.append(1.0)
            weights.append(0.2)
            
        # Bullish divergence in RSI
        prices = np.array(self.pair_price_history[pair])
        if 'rsi' in indicators and len(prices) >= 14:
            rsi_values = talib.RSI(prices, timeperiod=14)
            divergence = improved_indicators.check_divergence(prices[-14:], rsi_values[-14:])
            if divergence == 'bullish':
                signal_components.append(1.0)
                weights.append(0.3)
        
        # Calculate overall signal strength if we have components
        if signal_components and weights:
            # Normalize weights
            weights = np.array(weights) / sum(weights)
            # Weighted average
            return float(np.sum(np.array(signal_components) * weights))
            
        return 0.0
        
    def _check_sell_signal(self, pair: str, indicators: Dict, settings: Dict) -> float:
        """
        Check if conditions for a sell signal are met.
        
        Args:
            pair: Currency pair
            indicators: Calculated indicators
            settings: Pair-specific settings
            
        Returns:
            Signal strength if conditions are met, otherwise 0
        """
        # Initialize signal components
        signal_components = []
        weights = []
        
        # RSI overbought condition
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi > 60:
                # Stronger signal the higher the RSI
                rsi_strength = (rsi - 60) / 40  # 0 to 1 scale
                signal_components.append(rsi_strength)
                weights.append(0.3)
        
        # MACD bearish crossover or negative histogram
        if 'macd' in indicators and 'macd_signal' in indicators:
            macd = indicators['macd']
            macd_signal = indicators['macd_signal']
            
            # Check crossover
            macd_crossover = improved_indicators.detect_indicator_crossover(
                np.array([indicators.get('macd_prev', macd), macd]),
                np.array([indicators.get('macd_signal_prev', macd_signal), macd_signal])
            )
            
            if macd_crossover == 'bearish' or (macd < macd_signal and indicators.get('macd_hist_slope', 0) < 0):
                macd_strength = min(1, abs(macd - macd_signal) * 1000)  # Scale appropriately
                signal_components.append(macd_strength)
                weights.append(0.3)
                
        # Stochastic overbought or bearish crossover
        if 'stoch_k' in indicators and 'stoch_d' in indicators:
            stoch_k = indicators['stoch_k']
            stoch_d = indicators['stoch_d']
            
            if stoch_k > 70 and stoch_k < stoch_d:
                stoch_strength = (stoch_k - 70) / 30
                signal_components.append(stoch_strength)
                weights.append(0.2)
                
        # Bollinger Band bounce from upper band
        if 'bb_upper' in indicators and 'bb_position' in indicators:
            bb_position = indicators['bb_position']
            
            if bb_position > 0.8:  # Close to upper band
                bb_strength = bb_position
                signal_components.append(bb_strength)
                weights.append(0.2)
                
        # Price action confirmation (consecutive bearish candles)
        lookback = settings.get('price_action_lookback', 3)
        if self._check_consecutive_candles(self.pair_price_history[pair], "bearish", lookback):
            signal_components.append(1.0)
            weights.append(0.1)
            
        # Volume confirmation
        if 'volume_ratio' in indicators and indicators['volume_ratio'] > 1.2:
            volume_strength = min(1.0, (indicators['volume_ratio'] - 1) / 2)
            signal_components.append(volume_strength)
            weights.append(0.1)
            
        # Trend alignment
        if 'trend_direction' in indicators and indicators['trend_direction'] == 'DOWN':
            signal_components.append(1.0)
            weights.append(0.2)
            
        # Bearish divergence in RSI
        prices = np.array(self.pair_price_history[pair])
        if 'rsi' in indicators and len(prices) >= 14:
            rsi_values = talib.RSI(prices, timeperiod=14)
            divergence = improved_indicators.check_divergence(prices[-14:], rsi_values[-14:])
            if divergence == 'bearish':
                signal_components.append(1.0)
                weights.append(0.3)
        
        # Calculate overall signal strength if we have components
        if signal_components and weights:
            # Normalize weights
            weights = np.array(weights) / sum(weights)
            # Weighted average
            return float(np.sum(np.array(signal_components) * weights))
            
        return 0.0
        
    def _check_enhanced_trading_conditions(self, pair: str, timestamp: datetime) -> bool:
        """
        Check if trading conditions are met with enhanced checks.
        
        Args:
            pair: Currency pair to check
            timestamp: Current timestamp
            
        Returns:
            True if trading conditions are met
        """
        # First check base conditions
        if not self._check_trading_conditions():
            return False
            
        # Check if forex market is open based on time
        if not self.time_logic.is_forex_market_open(timestamp):
            self.logger.info(f"Forex market closed for {pair} at {timestamp}")
            return False
            
        # Check if pair is in tradable pairs from asset selector
        if not pair in self.asset_selector.tradable_pairs and len(self.asset_selector.tradable_pairs) > 0:
            # Allow exceptions for particularly strong signals or if performance is good
            pair_stats = self.performance_tracker.pair_stats.get(pair, {})
            win_rate = pair_stats.get('win_rate', 0)
            
            # Skip check if we have good past performance with this pair
            if win_rate < 0.6:  # Require 60% win rate to trade non-selected pair
                self.logger.info(f"Pair {pair} not in selected tradable pairs")
                return False
                
        # Check if there's a recent signal for this pair to avoid multiple entries
        for signal in self.recent_signals[-10:]:  # Check last 10 signals
            if signal.asset == pair and (timestamp - signal.timestamp).total_seconds() < 900:  # 15 min
                self.logger.info(f"Skipping {pair} - recent signal exists")
                return False
                
        # Check if current session is suitable for this pair
        current_sessions = self.time_logic.get_current_session(timestamp)
        optimal_pairs = self.time_logic.get_optimal_pairs_for_time(timestamp)
        
        if optimal_pairs and pair not in optimal_pairs:
            # Check if performance justifies trading anyway
            pair_stats = self.performance_tracker.pair_stats.get(pair, {})
            win_rate = pair_stats.get('win_rate', 0)
            
            if win_rate < 0.65:  # Require higher win rate for off-session pairs
                self.logger.info(f"Pair {pair} not optimal for current session {current_sessions}")
                return False
                
        return True
        
    def _generate_enhanced_signal(self, pair: str, direction: str, indicators: Dict,
                                 timestamp: datetime, confidence: float) -> EnhancedSignal:
        """
        Generate an enhanced signal with additional metrics.
        
        Args:
            pair: Currency pair
            direction: "BUY" or "SELL"
            indicators: Calculated indicators
            timestamp: Signal timestamp
            confidence: Signal confidence
            
        Returns:
            Enhanced signal with additional information
        """
        # Calculate signal strength score using the ranker
        signal_data = {
            'direction': direction,
            'asset': pair,
            'indicators': indicators,
            'timestamp': timestamp
        }
        
        strength_score, strength_factors = self.signal_ranker.calculate_signal_strength(signal_data)
        
        # Get time context information
        time_context = self.time_logic.format_trading_signal_time_context(signal_data)
        
        # Get current trading session
        current_sessions = self.time_logic.get_current_session(timestamp)
        session_str = ', '.join(current_sessions) if current_sessions else "No major session"
        
        # Adjust expiry time based on volatility
        # Higher volatility pairs and higher volatility times get shorter expiry
        base_expiry = 1
        volatility_factor = self.time_logic.get_session_volatility_factor(timestamp)
        pair_settings = self.pair_settings.get_settings(pair)
        
        if pair in self.pair_settings.HIGH_VOLATILITY_PAIRS:
            expiry = max(1, round(base_expiry * 0.8 * volatility_factor))
        elif pair in self.pair_settings.LOW_VOLATILITY_PAIRS:
            expiry = max(1, round(base_expiry * 1.2 * volatility_factor))
        else:
            expiry = max(1, round(base_expiry * volatility_factor))
            
        # Create enhanced signal
        signal = EnhancedSignal(
            timestamp=timestamp,
            direction=direction,
            asset=pair,
            expiry_minutes=expiry,
            confidence=confidence,
            indicators=indicators,
            strength_score=strength_score,
            strength_factors=strength_factors,
            time_context=time_context,
            is_tradable=True,
            market_session=session_str
        )
        
        # Update last signal time
        self.last_signal_time = timestamp
        self.trades_today += 1
        
        return signal
        
    def record_trade_result(self, pair: str, direction: str, entry_time: datetime, 
                           exit_time: datetime, profit_pips: float, win: bool) -> None:
        """
        Record the result of a trade for performance tracking.
        
        Args:
            pair: Currency pair
            direction: "BUY" or "SELL"
            entry_time: Trade entry time
            exit_time: Trade exit time
            profit_pips: Profit/loss in pips
            win: Whether the trade was a win
        """
        # Update base class tracking
        super().record_trade_result(win)
        
        # Record in performance tracker
        self.performance_tracker.add_trade_result(
            pair=pair,
            direction=direction,
            entry_time=entry_time,
            exit_time=exit_time,
            profit_pips=profit_pips,
            win=win
        )
        
    def get_ranked_signals(self, signals: List[EnhancedSignal], max_signals: int = 5) -> List[EnhancedSignal]:
        """
        Rank signals by strength and filter correlated pairs.
        
        Args:
            signals: List of signals to rank
            max_signals: Maximum number of signals to return
            
        Returns:
            List of ranked signals (strongest first), with correlated pairs removed
        """
        if not signals:
            return []
            
        # Sort signals by strength score (descending)
        sorted_signals = sorted(signals, key=lambda s: s.strength_score, reverse=True)
        
        # Apply correlation filter
        filtered_signals = []
        used_pairs = set()
        
        for signal in sorted_signals:
            pair = signal.asset
            
            # Skip if we already have a correlated pair
            correlated = False
            for used_pair in used_pairs:
                if self.correlation_manager.are_correlated(pair, used_pair):
                    correlated = True
                    break
                    
            if not correlated:
                # Add rank to signal
                signal.rank = len(filtered_signals) + 1
                filtered_signals.append(signal)
                used_pairs.add(pair)
                
            # Stop once we have enough signals
            if len(filtered_signals) >= max_signals:
                break
                
        return filtered_signals
        
    def _check_consecutive_candles(self, prices: List[float], pattern: str, count: int) -> bool:
        """
        Check for consecutive bullish/bearish candles.
        
        Args:
            prices: List of prices
            pattern: "bullish" or "bearish"
            count: Number of consecutive candles to check
            
        Returns:
            True if pattern is found
        """
        if len(prices) < count + 1:
            return False
            
        price_array = prices[-(count + 1):]
        
        if pattern == "bullish":
            return all(price_array[i] < price_array[i + 1] for i in range(count))
        else:  # bearish
            return all(price_array[i] > price_array[i + 1] for i in range(count))
            
    def generate_daily_report(self) -> Dict:
        """
        Generate a daily performance report.
        
        Returns:
            Dictionary with report data
        """
        # Get performance data from tracker
        return self.performance_tracker.generate_daily_report()

# Create an instance of the enhanced signal generator
enhanced_signal_generator = EnhancedSignalGenerator()
