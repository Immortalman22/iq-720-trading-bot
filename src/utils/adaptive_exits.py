#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Adaptive Exit Strategies for IQ-720 Trading Bot

This module provides dynamic exit strategies that adapt to market conditions,
volatility, and prediction confidence to optimize trade exits.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
import math
from enum import Enum

logger = logging.getLogger("AdaptiveExitStrategies")

class ExitType(Enum):
    """Types of exit strategies"""
    FIXED = "fixed"
    VOLATILITY_BASED = "volatility_based"
    PREDICTION_BASED = "prediction_based"
    TIME_BASED = "time_based"
    TRAILING = "trailing"
    COMBINED = "combined"

class AdaptiveExitStrategies:
    """
    Provides dynamic exit strategies that adapt to market conditions.
    
    Features:
    - Volatility-based stop loss and take profit
    - Time-based exits adjusted for volatility
    - Trailing stops that adapt to price movement
    - Exit strategies based on prediction confidence
    """
    
    def __init__(self, config=None):
        """
        Initialize the adaptive exit strategies manager.
        
        Args:
            config: Configuration dictionary for exit strategies
        """
        self.config = config or {}
        
        # Default settings
        self.default_stop_loss = self.config.get('default_stop_loss', 0.02)  # 2%
        self.default_take_profit = self.config.get('default_take_profit', 0.04)  # 4%
        self.volatility_multiplier = self.config.get('volatility_multiplier', 2.0)
        self.trailing_activation = self.config.get('trailing_activation', 0.5)  # Activate trailing at 50% of take profit
        self.trailing_step = self.config.get('trailing_step', 0.2)  # Move stop by 20% of price movement
        
    def calculate_atr(self, data, periods=14):
        """
        Calculate Average True Range (ATR) for volatility measurement.
        
        Args:
            data: DataFrame with OHLCV data
            periods: Number of periods for ATR calculation
            
        Returns:
            ATR value (float)
        """
        if len(data) < periods + 1:
            return None
            
        # Calculate True Range
        high = data['high'].values
        low = data['low'].values
        close = np.concatenate([[data['close'].values[0]], data['close'].values[:-1]])
        
        tr1 = np.abs(high - low)
        tr2 = np.abs(high - close)
        tr3 = np.abs(low - close)
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # Calculate ATR
        atr = np.mean(tr[-periods:])
        
        return atr
        
    def get_volatility_factor(self, data, timeframe_minutes=5, use_atr=True):
        """
        Calculate volatility factor for scaling exit levels.
        
        Args:
            data: DataFrame with OHLCV data
            timeframe_minutes: Timeframe in minutes
            use_atr: Whether to use ATR instead of standard deviation
            
        Returns:
            Volatility factor (float)
        """
        if len(data) < 20:
            return 1.0
            
        if use_atr:
            atr = self.calculate_atr(data)
            if atr is None:
                return 1.0
                
            # Normalize ATR by current price for percentage
            current_price = data['close'].iloc[-1]
            volatility = atr / current_price
        else:
            # Use standard deviation of returns
            returns = data['close'].pct_change().dropna()
            if len(returns) < 5:
                return 1.0
                
            volatility = returns.std()
            
        # Adjust for timeframe
        # Assuming volatility scales with square root of time
        # 5 minutes is our base timeframe
        time_factor = math.sqrt(timeframe_minutes / 5)
        
        # Normalize volatility relative to "normal" volatility
        # 0.01 (1%) is considered "normal" for a 5-min timeframe
        normalized_volatility = volatility * time_factor / 0.01
        
        return normalized_volatility
        
    def calculate_exits(self, data, direction, confidence=None, 
                        target_return=None, expiry_minutes=5,
                        exit_type=ExitType.COMBINED):
        """
        Calculate adaptive exit levels based on market conditions.
        
        Args:
            data: DataFrame with OHLCV data
            direction: 'BUY' or 'SELL'
            confidence: Prediction confidence (0-1)
            target_return: Expected return if available
            expiry_minutes: Trade expiry in minutes
            exit_type: Type of exit strategy to use
            
        Returns:
            Dictionary with exit levels
        """
        if len(data) < 20:
            logger.warning("Insufficient data for calculating exits, using defaults")
            return {
                'stop_loss': self.default_stop_loss,
                'take_profit': self.default_take_profit,
                'time_exit': expiry_minutes,
                'exit_type': ExitType.FIXED.value
            }
            
        current_price = data['close'].iloc[-1]
        
        # Calculate volatility factor
        volatility_factor = self.get_volatility_factor(data, expiry_minutes)
        
        # Base levels
        base_stop = self.default_stop_loss
        base_tp = self.default_take_profit
        
        # Adjust for exit strategy type
        if exit_type == ExitType.VOLATILITY_BASED:
            # Scale exits based on current volatility
            stop_loss = base_stop * volatility_factor
            take_profit = base_tp * volatility_factor
            
            # Apply reasonable limits
            stop_loss = min(max(stop_loss, 0.01), 0.05)
            take_profit = min(max(take_profit, 0.02), 0.1)
            
        elif exit_type == ExitType.PREDICTION_BASED and target_return is not None:
            # Use predicted return to set take profit
            take_profit = abs(target_return) * 1.2  # Slight buffer
            
            # Scale stop loss based on confidence
            if confidence is not None:
                # Higher confidence = tighter stop
                confidence_factor = 1.5 - confidence * 0.5  # Range: 1.0 to 1.5
                stop_loss = base_stop * confidence_factor * volatility_factor
            else:
                stop_loss = base_stop * volatility_factor
                
            # Apply reasonable limits
            stop_loss = min(max(stop_loss, 0.01), 0.05)
            take_profit = min(max(take_profit, 0.02), 0.1)
            
        elif exit_type == ExitType.TIME_BASED:
            # Use default exits but calculate optimal time exit
            stop_loss = base_stop * volatility_factor
            take_profit = base_tp * volatility_factor
            
            # Scale time exit by volatility
            time_exit = int(expiry_minutes / volatility_factor)
            time_exit = min(max(time_exit, expiry_minutes // 2), expiry_minutes * 2)
            
            # Apply reasonable limits
            stop_loss = min(max(stop_loss, 0.01), 0.05)
            take_profit = min(max(take_profit, 0.02), 0.1)
            
        elif exit_type == ExitType.COMBINED:
            # Combine volatility and prediction-based approaches
            
            # Scale based on volatility
            vol_stop = base_stop * volatility_factor
            vol_tp = base_tp * volatility_factor
            
            # Adjust based on prediction if available
            if target_return is not None:
                pred_tp = abs(target_return) * 1.2
                # Weighted average
                take_profit = (vol_tp + pred_tp) / 2
            else:
                take_profit = vol_tp
                
            # Adjust stop loss based on confidence
            if confidence is not None:
                # Higher confidence = tighter stop
                confidence_factor = 1.5 - confidence * 0.5  # Range: 1.0 to 1.5
                stop_loss = vol_stop * confidence_factor
            else:
                stop_loss = vol_stop
                
            # Ensure reasonable risk:reward
            if take_profit < stop_loss * 1.5:
                take_profit = stop_loss * 1.5
                
            # Apply reasonable limits
            stop_loss = min(max(stop_loss, 0.01), 0.05)
            take_profit = min(max(take_profit, 0.02), 0.1)
            
        else:  # FIXED or fallback
            stop_loss = self.default_stop_loss
            take_profit = self.default_take_profit
            
        # Calculate price levels based on direction
        if direction == 'BUY':
            stop_price = current_price * (1 - stop_loss)
            take_profit_price = current_price * (1 + take_profit)
        else:  # SELL
            stop_price = current_price * (1 + stop_loss)
            take_profit_price = current_price * (1 - take_profit)
            
        # Prepare result
        result = {
            'entry_price': current_price,
            'stop_loss_price': stop_price,
            'take_profit_price': take_profit_price,
            'stop_loss_pct': stop_loss,
            'take_profit_pct': take_profit,
            'time_exit': expiry_minutes,
            'exit_type': exit_type.value,
            'volatility_factor': volatility_factor
        }
        
        # Add trailing stop parameters if applicable
        if exit_type in [ExitType.TRAILING, ExitType.COMBINED]:
            trailing_activation_price = current_price * (
                1 + take_profit * self.trailing_activation if direction == 'BUY'
                else 1 - take_profit * self.trailing_activation
            )
            
            result['trailing'] = {
                'activation_price': trailing_activation_price,
                'activation_pct': take_profit * self.trailing_activation,
                'step_pct': self.trailing_step
            }
            
        return result
        
    def update_trailing_stop(self, trade_info, current_price):
        """
        Update trailing stop price based on current price.
        
        Args:
            trade_info: Dictionary with trade information
            current_price: Current price of the asset
            
        Returns:
            Updated trade_info dictionary
        """
        if 'trailing' not in trade_info:
            return trade_info
            
        direction = trade_info.get('direction')
        if not direction:
            return trade_info
            
        trailing = trade_info['trailing']
        
        # Check if trailing stop is activated
        if not trailing.get('activated', False):
            # Check if price has reached activation level
            if direction == 'BUY':
                activated = current_price >= trailing['activation_price']
            else:  # SELL
                activated = current_price <= trailing['activation_price']
                
            if activated:
                trailing['activated'] = True
                logger.info(f"Trailing stop activated at price {current_price}")
        
        # Update trailing stop if activated
        if trailing.get('activated', False):
            current_stop = trade_info['stop_loss_price']
            
            if direction == 'BUY':
                # For long positions, trailing stop moves up
                step = (current_price - trade_info['entry_price']) * trailing['step_pct']
                new_stop = trade_info['entry_price'] + step
                
                # Only move stop up, never down
                if new_stop > current_stop:
                    trade_info['stop_loss_price'] = new_stop
                    trade_info['stop_loss_pct'] = (trade_info['entry_price'] - new_stop) / trade_info['entry_price']
                    logger.info(f"Updated trailing stop to {new_stop}")
                    
            else:  # SELL
                # For short positions, trailing stop moves down
                step = (trade_info['entry_price'] - current_price) * trailing['step_pct']
                new_stop = trade_info['entry_price'] - step
                
                # Only move stop down, never up
                if new_stop < current_stop:
                    trade_info['stop_loss_price'] = new_stop
                    trade_info['stop_loss_pct'] = (new_stop - trade_info['entry_price']) / trade_info['entry_price']
                    logger.info(f"Updated trailing stop to {new_stop}")
                    
        return trade_info
        
    def check_exit_conditions(self, trade_info, current_price, current_time=None):
        """
        Check if any exit conditions are met.
        
        Args:
            trade_info: Dictionary with trade information
            current_price: Current price of the asset
            current_time: Current time (datetime object)
            
        Returns:
            Tuple of (exit_triggered, exit_reason, exit_price)
        """
        if not trade_info:
            return False, "Invalid trade info", None
            
        direction = trade_info.get('direction')
        if not direction:
            return False, "No trade direction specified", None
            
        # Default values if not provided
        if current_time is None:
            current_time = datetime.now()
            
        entry_time = trade_info.get('entry_time')
        if entry_time and isinstance(entry_time, str):
            try:
                entry_time = datetime.fromisoformat(entry_time)
            except ValueError:
                entry_time = None
                
        # Check stop loss
        stop_loss_price = trade_info.get('stop_loss_price')
        if stop_loss_price:
            if direction == 'BUY' and current_price <= stop_loss_price:
                return True, "Stop Loss", current_price
            elif direction == 'SELL' and current_price >= stop_loss_price:
                return True, "Stop Loss", current_price
                
        # Check take profit
        take_profit_price = trade_info.get('take_profit_price')
        if take_profit_price:
            if direction == 'BUY' and current_price >= take_profit_price:
                return True, "Take Profit", current_price
            elif direction == 'SELL' and current_price <= take_profit_price:
                return True, "Take Profit", current_price
                
        # Check time-based exit
        if entry_time and 'time_exit' in trade_info:
            time_exit_minutes = trade_info['time_exit']
            exit_time = entry_time + timedelta(minutes=time_exit_minutes)
            
            if current_time >= exit_time:
                return True, "Time Exit", current_price
                
        return False, None, None
        
    def get_exit_summary(self, trade_info):
        """
        Get a human-readable summary of exit strategies for a trade.
        
        Args:
            trade_info: Dictionary with trade information
            
        Returns:
            String with exit strategy summary
        """
        if not trade_info:
            return "No exit strategy information available"
            
        direction = trade_info.get('direction', 'UNKNOWN')
        entry_price = trade_info.get('entry_price', 0)
        
        # Calculate absolute and percentage differences
        stop_loss_price = trade_info.get('stop_loss_price')
        take_profit_price = trade_info.get('take_profit_price')
        
        if stop_loss_price and entry_price:
            sl_diff = abs(stop_loss_price - entry_price)
            sl_pct = sl_diff / entry_price * 100
        else:
            sl_pct = trade_info.get('stop_loss_pct', 0) * 100
            
        if take_profit_price and entry_price:
            tp_diff = abs(take_profit_price - entry_price)
            tp_pct = tp_diff / entry_price * 100
        else:
            tp_pct = trade_info.get('take_profit_pct', 0) * 100
            
        # Format summary
        summary = (
            f"{direction} trade at {entry_price:.5f}\n"
            f"Stop Loss: {stop_loss_price:.5f} ({sl_pct:.2f}%)\n"
            f"Take Profit: {take_profit_price:.5f} ({tp_pct:.2f}%)\n"
        )
        
        # Add time exit if available
        if 'time_exit' in trade_info:
            summary += f"Time Exit: {trade_info['time_exit']} minutes\n"
            
        # Add trailing stop info if available
        if 'trailing' in trade_info:
            trailing = trade_info['trailing']
            activation_pct = trailing.get('activation_pct', 0) * 100
            step_pct = trailing.get('step_pct', 0) * 100
            
            summary += (
                f"Trailing Stop: Activates at {activation_pct:.1f}% of TP, "
                f"Step: {step_pct:.1f}% of move\n"
            )
            
        # Add exit type
        exit_type = trade_info.get('exit_type', 'fixed')
        summary += f"Strategy: {exit_type.capitalize()}"
        
        return summary
