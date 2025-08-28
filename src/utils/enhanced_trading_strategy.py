#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Trading Strategy Integration Module for IQ-720 Trading Bot

This module integrates all enhanced trading strategy components:
- Return prediction
- Adaptive exit strategies
- Position sizing
- Market availability checks
- Correlation analysis
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from enum import Enum
import json
import os

# Import our enhanced modules
from utils.return_prediction import ReturnPredictor
from utils.adaptive_exits import AdaptiveExitStrategies, ExitType
from utils.position_sizing import PositionSizing, SizingMethod
from utils.market_availability import MarketAvailability
from utils.pair_correlation_analyzer import PairCorrelationAnalyzer
from utils.market_regime import MarketRegimeDetector
from utils.signal_ranker import SignalRanker

logger = logging.getLogger("EnhancedTradingStrategy")

class TradingMode(Enum):
    """Trading modes for the enhanced strategy"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    ADAPTIVE = "adaptive"


class EnhancedTradingStrategy:
    """
    Enhanced Trading Strategy that integrates multiple advanced components
    for improved trading decisions, risk management, and performance.
    """
    
    def __init__(self, config=None, account_balance=1000):
        """
        Initialize the enhanced trading strategy.
        
        Args:
            config: Configuration dictionary
            account_balance: Initial account balance
        """
        self.config = config or {}
        self.account_balance = account_balance
        
        # Default settings
        self.trading_mode = TradingMode(self.config.get('trading_mode', 'balanced'))
        self.min_confidence = self.config.get('min_confidence', 0.65)
        self.min_correlation_confirmation = self.config.get('min_correlation_confirmation', 0.6)
        self.use_market_regime = self.config.get('use_market_regime', True)
        self.check_market_availability = self.config.get('check_market_availability', True)
        self.position_sizing_method = SizingMethod(self.config.get('position_sizing_method', 'fractional_kelly'))
        self.exit_strategy_type = ExitType(self.config.get('exit_strategy_type', 'combined'))
        self.max_active_trades = self.config.get('max_active_trades', 3)
        self.required_correlation_pairs = self.config.get('required_correlation_pairs', 2)
        
        # Initialize sub-components
        self._init_components()
        
        # Track active trades
        self.active_trades = {}
        
        logger.info(f"Enhanced Trading Strategy initialized in {self.trading_mode.value} mode")
        
    def _init_components(self):
        """Initialize trading strategy components"""
        
        # Initialize return predictor
        predictor_config = self.config.get('return_predictor', {})
        self.return_predictor = ReturnPredictor(predictor_config)
        
        # Initialize exit strategies
        exit_config = self.config.get('exit_strategies', {})
        self.exit_strategies = AdaptiveExitStrategies(exit_config)
        
        # Initialize position sizing
        sizing_config = self.config.get('position_sizing', {})
        self.position_sizing = PositionSizing(sizing_config, self.account_balance)
        
        # Initialize market availability checker
        availability_config = self.config.get('market_availability', {})
        self.market_checker = MarketAvailability(availability_config)
        
        # Initialize correlation analyzer
        correlation_config = self.config.get('correlation', {})
        self.correlation_analyzer = PairCorrelationAnalyzer(correlation_config)
        
        # Initialize market regime detector
        regime_config = self.config.get('market_regime', {})
        self.regime_detector = MarketRegimeDetector(regime_config)
        
        # Initialize signal ranker
        ranker_config = self.config.get('signal_ranker', {})
        self.signal_ranker = SignalRanker(ranker_config)
    
    def update_account_balance(self, new_balance):
        """
        Update account balance and related components.
        
        Args:
            new_balance: New account balance
        """
        self.account_balance = new_balance
        self.position_sizing.update_account_balance(new_balance)
    
    def add_trade_result(self, trade_id, win, profit_pct=None):
        """
        Record trade result and update components.
        
        Args:
            trade_id: ID of the trade
            win: Whether trade was profitable
            profit_pct: Percentage profit/loss
        """
        # Update position sizing with trade result
        self.position_sizing.add_trade_result(win, profit_pct)
        
        # If trade was in active trades, remove it
        if trade_id in self.active_trades:
            del self.active_trades[trade_id]
            logger.info(f"Trade {trade_id} removed from active trades")
    
    def adjust_min_confidence(self, market_regime=None):
        """
        Adjust minimum confidence threshold based on market regime.
        
        Args:
            market_regime: Current market regime
            
        Returns:
            Adjusted confidence threshold
        """
        base_confidence = self.min_confidence
        
        # No adjustment if no regime provided or regime adaptation disabled
        if market_regime is None or not self.use_market_regime:
            return base_confidence
            
        # Adjust threshold based on market regime
        if market_regime == 'trending_up':
            # Lower threshold in strong uptrends
            return base_confidence * 0.9
        elif market_regime == 'trending_down':
            # Lower threshold in strong downtrends
            return base_confidence * 0.9
        elif market_regime == 'ranging_low_volatility':
            # Standard threshold in low volatility ranges
            return base_confidence
        elif market_regime == 'ranging_high_volatility':
            # Higher threshold in volatile ranges
            return base_confidence * 1.1
        elif market_regime == 'reversal':
            # Higher threshold during reversals
            return base_confidence * 1.15
            
        return base_confidence
    
    def evaluate_trading_signals(self, signals, market_data, current_time=None):
        """
        Evaluate trading signals using enhanced criteria.
        
        Args:
            signals: Dictionary of trading signals by pair
            market_data: Dictionary of market data by pair
            current_time: Current time
            
        Returns:
            Ranked and filtered trading signals
        """
        if not signals or not market_data:
            return []
            
        if current_time is None:
            current_time = datetime.now()
            
        evaluated_signals = []
        
        # Process each signal
        for pair, signal in signals.items():
            if not signal or 'direction' not in signal:
                continue
                
            # Skip if pair data not available
            if pair not in market_data:
                continue
                
            pair_data = market_data[pair]
            
            # Check market availability if enabled
            if self.check_market_availability:
                is_available, market_type = self.market_checker.check_availability(pair, current_time)
                if not is_available:
                    logger.info(f"Market {pair} is not available, skipping signal")
                    continue
                    
                # Add market type to signal
                signal['market_type'] = market_type
            
            # Determine market regime if enabled
            market_regime = None
            if self.use_market_regime and len(pair_data) >= 20:
                market_regime = self.regime_detector.detect_regime(pair_data)
                signal['market_regime'] = market_regime
            
            # Adjust confidence threshold based on regime
            adjusted_confidence = self.adjust_min_confidence(market_regime)
            
            # Skip if confidence below threshold
            if signal.get('confidence', 0) < adjusted_confidence:
                logger.info(f"Signal for {pair} confidence {signal.get('confidence', 0):.2f} "
                           f"below threshold {adjusted_confidence:.2f}, skipping")
                continue
            
            # Predict expected returns
            if 'expected_return' not in signal:
                expected_return = self.return_predictor.predict_expected_return(pair_data)
                signal['expected_return'] = expected_return
                
                # Skip if expected return doesn't match direction
                if (signal['direction'] == 'BUY' and expected_return <= 0) or \
                   (signal['direction'] == 'SELL' and expected_return >= 0):
                    logger.info(f"Signal direction {signal['direction']} doesn't match "
                               f"expected return {expected_return:.4f}, skipping")
                    continue
            
            # Get correlation confirmation
            correlated_pairs = self.correlation_analyzer.get_correlated_pairs(pair)
            confirming_signals = self.correlation_analyzer.check_signal_confirmation(
                pair, signal['direction'], signals
            )
            
            # Add correlation data to signal
            signal['correlation_confirmation'] = len(confirming_signals) / max(1, len(correlated_pairs))
            signal['confirming_pairs'] = confirming_signals
            
            # Skip if insufficient correlation confirmation
            if signal['correlation_confirmation'] < self.min_correlation_confirmation or \
               len(confirming_signals) < self.required_correlation_pairs:
                logger.info(f"Signal for {pair} has insufficient correlation confirmation "
                           f"{signal['correlation_confirmation']:.2f}, skipping")
                continue
            
            # Calculate exit strategies
            exit_info = self.exit_strategies.calculate_exits(
                pair_data,
                signal['direction'],
                signal.get('confidence'),
                signal.get('expected_return'),
                exit_type=self.exit_strategy_type
            )
            
            # Add exit info to signal
            signal['exit_info'] = exit_info
            
            # Calculate position size
            position_info = self.position_sizing.calculate_position_size(
                method=self.position_sizing_method,
                win_probability=signal.get('confidence', 0.5),
                expected_return=signal.get('expected_return'),
                stop_loss_pct=exit_info.get('stop_loss_pct'),
                confidence=signal.get('confidence'),
                volatility_factor=exit_info.get('volatility_factor')
            )
            
            # Add position info to signal
            signal['position_info'] = position_info
            
            # Add to evaluated signals
            evaluated_signals.append({
                'pair': pair,
                'signal': signal,
                'timestamp': current_time,
            })
        
        # If we have more signals than max_active_trades, rank and filter
        if len(evaluated_signals) > self.max_active_trades:
            ranked_signals = self.signal_ranker.rank_signals(evaluated_signals)
            return ranked_signals[:self.max_active_trades]
        
        return evaluated_signals
    
    def check_exit_conditions(self, current_prices, current_time=None):
        """
        Check exit conditions for active trades.
        
        Args:
            current_prices: Dictionary of current prices by pair
            current_time: Current time
            
        Returns:
            Dictionary of trades to exit with reasons
        """
        if not self.active_trades:
            return {}
            
        if current_time is None:
            current_time = datetime.now()
            
        trades_to_exit = {}
        
        # Check each active trade
        for trade_id, trade_info in list(self.active_trades.items()):
            pair = trade_info.get('pair')
            
            # Skip if no price data for pair
            if pair not in current_prices:
                continue
                
            current_price = current_prices[pair]
            
            # Check exit conditions
            exit_triggered, exit_reason, exit_price = self.exit_strategies.check_exit_conditions(
                trade_info, current_price, current_time
            )
            
            if exit_triggered:
                trades_to_exit[trade_id] = {
                    'trade_info': trade_info,
                    'exit_reason': exit_reason,
                    'exit_price': exit_price,
                    'exit_time': current_time
                }
                
                # Remove from active trades
                del self.active_trades[trade_id]
                logger.info(f"Trade {trade_id} marked for exit: {exit_reason} at {exit_price}")
                
        return trades_to_exit
    
    def update_trailing_stops(self, current_prices):
        """
        Update trailing stops for active trades.
        
        Args:
            current_prices: Dictionary of current prices by pair
        """
        if not self.active_trades:
            return
            
        # Update trailing stops for each trade
        for trade_id, trade_info in self.active_trades.items():
            pair = trade_info.get('pair')
            
            # Skip if no price data for pair
            if pair not in current_prices:
                continue
                
            current_price = current_prices[pair]
            
            # Update trailing stop if applicable
            if 'exit_info' in trade_info and 'trailing' in trade_info['exit_info']:
                updated_info = self.exit_strategies.update_trailing_stop(
                    trade_info['exit_info'], current_price
                )
                
                # Update trade info
                trade_info['exit_info'] = updated_info
    
    def execute_trade(self, evaluated_signal):
        """
        Execute a trade based on evaluated signal.
        
        Args:
            evaluated_signal: Evaluated signal dictionary
            
        Returns:
            Trade info dictionary or None if trade not executed
        """
        if not evaluated_signal:
            return None
            
        # Check if we have too many active trades
        if len(self.active_trades) >= self.max_active_trades:
            logger.info("Maximum active trades reached, skipping execution")
            return None
            
        pair = evaluated_signal.get('pair')
        signal = evaluated_signal.get('signal')
        
        if not pair or not signal:
            return None
            
        # Generate trade ID
        trade_id = f"{pair}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Build trade info
        trade_info = {
            'id': trade_id,
            'pair': pair,
            'direction': signal.get('direction'),
            'entry_time': datetime.now(),
            'entry_price': signal.get('current_price'),
            'confidence': signal.get('confidence'),
            'expected_return': signal.get('expected_return'),
            'market_regime': signal.get('market_regime'),
            'market_type': signal.get('market_type'),
            'exit_info': signal.get('exit_info'),
            'position_info': signal.get('position_info'),
            'correlation_confirmation': signal.get('correlation_confirmation'),
            'confirming_pairs': signal.get('confirming_pairs')
        }
        
        # Add to active trades
        self.active_trades[trade_id] = trade_info
        
        logger.info(f"Executed trade {trade_id} for {pair} {signal.get('direction')} "
                   f"with size {signal.get('position_info', {}).get('position_size', 0):.2f}")
        
        return trade_info
    
    def get_trade_summary(self, trade_info):
        """
        Generate human-readable trade summary.
        
        Args:
            trade_info: Trade information dictionary
            
        Returns:
            String with trade summary
        """
        if not trade_info:
            return "No trade information available"
            
        pair = trade_info.get('pair', 'UNKNOWN')
        direction = trade_info.get('direction', 'UNKNOWN')
        entry_price = trade_info.get('entry_price', 0)
        entry_time = trade_info.get('entry_time', datetime.now())
        confidence = trade_info.get('confidence', 0)
        expected_return = trade_info.get('expected_return', 0)
        
        # Format summary
        summary = (
            f"Trade {trade_info.get('id', 'UNKNOWN')}\n"
            f"Pair: {pair} | Direction: {direction}\n"
            f"Entry: {entry_price:.5f} at {entry_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Confidence: {confidence:.2%} | Expected Return: {expected_return:.2%}\n"
        )
        
        # Add exit strategy info if available
        if 'exit_info' in trade_info:
            exit_info = trade_info['exit_info']
            stop_loss = exit_info.get('stop_loss_price', 0)
            take_profit = exit_info.get('take_profit_price', 0)
            
            summary += (
                f"Stop Loss: {stop_loss:.5f} ({exit_info.get('stop_loss_pct', 0):.2%})\n"
                f"Take Profit: {take_profit:.5f} ({exit_info.get('take_profit_pct', 0):.2%})\n"
            )
            
            # Add trailing stop info if available
            if 'trailing' in exit_info:
                trailing = exit_info['trailing']
                activation_pct = trailing.get('activation_pct', 0) * 100
                summary += f"Trailing Stop: Activates at {activation_pct:.1f}% of TP\n"
        
        # Add position info if available
        if 'position_info' in trade_info:
            position_info = trade_info['position_info']
            position_size = position_info.get('position_size', 0)
            method = position_info.get('method', 'unknown')
            
            summary += (
                f"Position Size: {position_size:.2f} ({position_info.get('position_fraction', 0):.2%} of account)\n"
                f"Sizing Method: {method.capitalize()}\n"
            )
        
        # Add market context if available
        if 'market_regime' in trade_info:
            summary += f"Market Regime: {trade_info['market_regime']}\n"
            
        if 'market_type' in trade_info:
            summary += f"Market Type: {trade_info['market_type']}\n"
        
        # Add correlation info
        confirmation = trade_info.get('correlation_confirmation', 0)
        confirming_pairs = trade_info.get('confirming_pairs', [])
        
        summary += (
            f"Correlation Confirmation: {confirmation:.2%}\n"
            f"Confirming Pairs: {', '.join(confirming_pairs) if confirming_pairs else 'None'}"
        )
        
        return summary
    
    def save_trade_history(self, filepath):
        """
        Save trade history to JSON file.
        
        Args:
            filepath: Path to save trade history
            
        Returns:
            Boolean indicating success
        """
        try:
            # Convert trade history to serializable format
            trade_history = []
            for trade in self.position_sizing.trade_history:
                trade_dict = {
                    'timestamp': trade['timestamp'].isoformat(),
                    'win': trade['win'],
                }
                if 'profit_pct' in trade:
                    trade_dict['profit_pct'] = trade['profit_pct']
                    
                trade_history.append(trade_dict)
                
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(trade_history, f, indent=2)
                
            logger.info(f"Trade history saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
            return False
    
    def load_trade_history(self, filepath):
        """
        Load trade history from JSON file.
        
        Args:
            filepath: Path to load trade history from
            
        Returns:
            Boolean indicating success
        """
        if not os.path.exists(filepath):
            logger.warning(f"Trade history file {filepath} not found")
            return False
            
        try:
            # Load from file
            with open(filepath, 'r') as f:
                trade_history = json.load(f)
                
            # Convert to trade history format
            for trade in trade_history:
                trade_dict = {
                    'timestamp': datetime.fromisoformat(trade['timestamp']),
                    'win': trade['win'],
                }
                if 'profit_pct' in trade:
                    trade_dict['profit_pct'] = trade['profit_pct']
                    
                self.position_sizing.trade_history.append(trade_dict)
                
            logger.info(f"Loaded {len(trade_history)} trades from history file")
            return True
            
        except Exception as e:
            logger.error(f"Error loading trade history: {e}")
            return False
