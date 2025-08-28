#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Position Sizing Module for IQ-720 Trading Bot

This module implements intelligent position sizing strategies including:
- Kelly Criterion
- Fixed Fraction
- Risk of Ruin protection
- Drawdown-based sizing adjustments
- Win rate and expected return based adjustments
"""

import numpy as np
import pandas as pd
import logging
import math
from enum import Enum
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger("PositionSizing")

class SizingMethod(Enum):
    """Position sizing methods"""
    FIXED = "fixed"
    FIXED_RISK = "fixed_risk"
    KELLY = "kelly"
    FRACTIONAL_KELLY = "fractional_kelly"
    DYNAMIC = "dynamic"
    DRAWDOWN_ADJUSTED = "drawdown_adjusted"
    CONFIDENCE_BASED = "confidence_based"
    VOLATILITY_SCALED = "volatility_scaled"


class PositionSizing:
    """
    Intelligent position sizing for optimal trade management.
    
    Features:
    - Kelly Criterion implementation
    - Fractional Kelly for more conservative sizing
    - Dynamic adjustment based on recent performance
    - Risk of ruin protection
    - Drawdown-based position adjustment
    """
    
    def __init__(self, config=None, account_balance=None):
        """
        Initialize the position sizing module.
        
        Args:
            config: Configuration dictionary
            account_balance: Current account balance
        """
        self.config = config or {}
        self.account_balance = account_balance or 1000.0  # Default if not provided
        
        # Default settings
        self.default_risk_per_trade = self.config.get('default_risk_per_trade', 0.02)  # 2% risk per trade
        self.max_risk_per_trade = self.config.get('max_risk_per_trade', 0.05)  # 5% max risk per trade
        self.min_trade_size = self.config.get('min_trade_size', 1.0)  # Minimum trade size
        self.kelly_fraction = self.config.get('kelly_fraction', 0.5)  # Half-Kelly for conservatism
        self.max_exposure = self.config.get('max_exposure', 0.25)  # Maximum 25% account exposure
        self.drawdown_scaling_enabled = self.config.get('drawdown_scaling_enabled', True)
        self.max_consecutive_losses = self.config.get('max_consecutive_losses', 3)
        
        # Track trade history for win rate calculation
        self.trade_history = deque(maxlen=100)  # Store last 100 trades
        self.current_drawdown = 0.0
        self.peak_balance = self.account_balance
        self.consecutive_losses = 0
        
    def update_account_balance(self, new_balance):
        """
        Update the account balance and related metrics.
        
        Args:
            new_balance: New account balance
        """
        old_balance = self.account_balance
        self.account_balance = new_balance
        
        # Update peak balance if we have a new peak
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
            self.current_drawdown = 0.0
        else:
            # Calculate current drawdown
            self.current_drawdown = (self.peak_balance - new_balance) / self.peak_balance
        
        # Check if we had a losing trade
        if new_balance < old_balance:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            
        logger.info(f"Account balance updated: {new_balance}, "
                   f"Drawdown: {self.current_drawdown:.2%}, "
                   f"Consecutive losses: {self.consecutive_losses}")
    
    def add_trade_result(self, win, profit_pct=None):
        """
        Add a trade result to history for win rate calculation.
        
        Args:
            win: Boolean indicating if trade was profitable
            profit_pct: Percentage profit/loss (optional)
        """
        timestamp = datetime.now()
        trade = {
            'timestamp': timestamp,
            'win': win,
            'profit_pct': profit_pct
        }
        self.trade_history.append(trade)
        
        # Update consecutive losses
        if not win:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            
        logger.debug(f"Trade added to history: win={win}, profit_pct={profit_pct}")
    
    def get_win_rate(self, lookback=None):
        """
        Calculate win rate from trade history.
        
        Args:
            lookback: Number of recent trades to consider (None = all)
            
        Returns:
            Win rate as decimal (0-1)
        """
        if not self.trade_history:
            return 0.5  # Default win rate if no history
            
        trades = list(self.trade_history)
        if lookback and lookback < len(trades):
            trades = trades[-lookback:]
            
        wins = sum(1 for t in trades if t['win'])
        win_rate = wins / len(trades) if trades else 0.5
        
        return win_rate
    
    def get_avg_win_loss_ratio(self, lookback=None):
        """
        Calculate average win/loss ratio from trade history.
        
        Args:
            lookback: Number of recent trades to consider (None = all)
            
        Returns:
            Average win/loss ratio
        """
        if not self.trade_history:
            return 1.0  # Default ratio if no history
            
        trades = list(self.trade_history)
        if lookback and lookback < len(trades):
            trades = trades[-lookback:]
            
        win_trades = [t for t in trades if t['win'] and t.get('profit_pct')]
        loss_trades = [t for t in trades if not t['win'] and t.get('profit_pct')]
        
        if not win_trades or not loss_trades:
            return 1.0
            
        avg_win = sum(t['profit_pct'] for t in win_trades) / len(win_trades)
        avg_loss = abs(sum(t['profit_pct'] for t in loss_trades)) / len(loss_trades)
        
        return avg_win / avg_loss if avg_loss > 0 else 1.0
    
    def get_expected_return(self, win_probability, win_loss_ratio=None):
        """
        Calculate expected return per trade.
        
        Args:
            win_probability: Probability of winning (0-1)
            win_loss_ratio: Ratio of average win to average loss
            
        Returns:
            Expected return as decimal
        """
        if win_loss_ratio is None:
            win_loss_ratio = self.get_avg_win_loss_ratio()
            
        # Expected return formula: (win_rate * avg_win) - ((1-win_rate) * avg_loss)
        # If we assume avg_win = win_loss_ratio * avg_loss, then:
        # expected_return = (win_rate * win_loss_ratio) - (1-win_rate)
        expected_return = (win_probability * win_loss_ratio) - (1 - win_probability)
        
        return expected_return
    
    def calculate_kelly_criterion(self, win_probability, win_loss_ratio=None):
        """
        Calculate Kelly Criterion for optimal position sizing.
        
        Args:
            win_probability: Probability of winning (0-1)
            win_loss_ratio: Ratio of average win to average loss
            
        Returns:
            Kelly fraction as decimal (0-1)
        """
        if win_probability <= 0:
            return 0.0
            
        if win_loss_ratio is None:
            win_loss_ratio = self.get_avg_win_loss_ratio()
        
        # Kelly formula: f* = (p*b - q)/b
        # where p = win probability, q = loss probability, b = win/loss ratio
        loss_probability = 1 - win_probability
        
        # Avoid division by zero
        if win_loss_ratio <= 0:
            return 0.0
            
        kelly = (win_probability * win_loss_ratio - loss_probability) / win_loss_ratio
        
        # Bound Kelly to reasonable limits [0, 1]
        kelly = max(0.0, min(1.0, kelly))
        
        return kelly
    
    def get_drawdown_adjustment(self):
        """
        Calculate adjustment factor based on current drawdown.
        
        Returns:
            Adjustment factor (0-1) to scale position size
        """
        if not self.drawdown_scaling_enabled:
            return 1.0
            
        # Linear scaling: 100% at 0% drawdown, 25% at 20% drawdown
        if self.current_drawdown >= 0.2:
            return 0.25
            
        # Linear scaling between 0% and 20% drawdown
        adjustment = 1.0 - (self.current_drawdown * 3.75)
        return max(0.25, adjustment)
    
    def get_consecutive_loss_adjustment(self):
        """
        Calculate adjustment factor based on consecutive losses.
        
        Returns:
            Adjustment factor (0-1) to scale position size
        """
        if self.consecutive_losses <= 1:
            return 1.0
            
        # Reduce by 20% for each consecutive loss after the first
        factor = 1.0 - (0.2 * (self.consecutive_losses - 1))
        return max(0.2, factor)
    
    def calculate_position_size(self, 
                               method=SizingMethod.FRACTIONAL_KELLY,
                               win_probability=None, 
                               expected_return=None,
                               risk_reward_ratio=None,
                               stop_loss_pct=None,
                               confidence=None,
                               volatility_factor=None):
        """
        Calculate position size based on specified method.
        
        Args:
            method: SizingMethod enum value
            win_probability: Probability of winning (0-1)
            expected_return: Expected return of trade
            risk_reward_ratio: Risk/reward ratio
            stop_loss_pct: Stop loss percentage
            confidence: Model confidence (0-1)
            volatility_factor: Market volatility factor
            
        Returns:
            Dictionary with position size information
        """
        # Default to 50% win probability if not provided
        if win_probability is None:
            win_probability = self.get_win_rate()
            
        # If stop loss not provided, use default
        if stop_loss_pct is None:
            stop_loss_pct = self.default_risk_per_trade
            
        # Calculate risk reward ratio if not provided
        if risk_reward_ratio is None and expected_return is not None:
            # Approximate risk reward from expected return
            # This is a simplified estimation
            risk_reward_ratio = (1 + expected_return) / (1 - win_probability) if win_probability < 1 else 2.0
        
        # Default risk reward
        if risk_reward_ratio is None:
            risk_reward_ratio = 2.0  # Default 2:1 reward:risk
            
        # Get base position size based on method
        if method == SizingMethod.FIXED:
            # Fixed amount per trade
            position_fraction = self.default_risk_per_trade
            
        elif method == SizingMethod.FIXED_RISK:
            # Fixed percentage risk
            if stop_loss_pct > 0:
                # Calculate position size to risk x% of account on stop loss
                position_fraction = self.default_risk_per_trade / stop_loss_pct
            else:
                position_fraction = self.default_risk_per_trade
                
        elif method == SizingMethod.KELLY:
            # Full Kelly Criterion
            kelly = self.calculate_kelly_criterion(win_probability, risk_reward_ratio)
            position_fraction = kelly
            
        elif method == SizingMethod.FRACTIONAL_KELLY:
            # Fractional Kelly (conservative)
            kelly = self.calculate_kelly_criterion(win_probability, risk_reward_ratio)
            position_fraction = kelly * self.kelly_fraction
            
        elif method == SizingMethod.CONFIDENCE_BASED:
            # Scale by prediction confidence
            base_fraction = self.default_risk_per_trade
            if confidence is not None:
                # Scale from 50% to 100% of base size based on confidence
                position_fraction = base_fraction * (0.5 + 0.5 * confidence)
            else:
                position_fraction = base_fraction
                
        elif method == SizingMethod.VOLATILITY_SCALED:
            # Scale by inverse of volatility
            base_fraction = self.default_risk_per_trade
            if volatility_factor is not None and volatility_factor > 0:
                # Higher volatility = smaller position
                position_fraction = base_fraction / volatility_factor
            else:
                position_fraction = base_fraction
                
        elif method == SizingMethod.DRAWDOWN_ADJUSTED:
            # Base size adjusted by drawdown
            base_fraction = self.default_risk_per_trade
            drawdown_factor = self.get_drawdown_adjustment()
            position_fraction = base_fraction * drawdown_factor
            
        elif method == SizingMethod.DYNAMIC:
            # Comprehensive dynamic sizing
            kelly = self.calculate_kelly_criterion(win_probability, risk_reward_ratio)
            
            # Start with fractional Kelly
            position_fraction = kelly * self.kelly_fraction
            
            # Apply drawdown adjustment
            drawdown_factor = self.get_drawdown_adjustment()
            position_fraction *= drawdown_factor
            
            # Apply consecutive loss adjustment
            loss_factor = self.get_consecutive_loss_adjustment()
            position_fraction *= loss_factor
            
            # Apply confidence adjustment if available
            if confidence is not None:
                # Reduce size for low confidence (below 0.7)
                if confidence < 0.7:
                    confidence_factor = 0.5 + (0.5 * confidence / 0.7)
                    position_fraction *= confidence_factor
            
            # Apply volatility adjustment if available
            if volatility_factor is not None and volatility_factor > 1.0:
                # Reduce size for high volatility
                vol_factor = 1.0 / volatility_factor
                position_fraction *= vol_factor
        
        else:  # Default to fixed risk
            position_fraction = self.default_risk_per_trade
            
        # Apply maximum risk limit
        position_fraction = min(position_fraction, self.max_risk_per_trade)
        
        # Calculate position size in currency
        position_size = self.account_balance * position_fraction
        
        # Apply minimum trade size
        position_size = max(position_size, self.min_trade_size)
        
        # Ensure position size doesn't exceed max exposure
        max_position = self.account_balance * self.max_exposure
        position_size = min(position_size, max_position)
        
        # Prepare result
        result = {
            'position_size': position_size,
            'position_fraction': position_fraction,
            'method': method.value,
            'win_probability': win_probability,
            'risk_reward_ratio': risk_reward_ratio,
        }
        
        # Add additional factors if used
        if method in [SizingMethod.DYNAMIC, SizingMethod.DRAWDOWN_ADJUSTED]:
            result['drawdown_factor'] = self.get_drawdown_adjustment()
            result['consecutive_loss_factor'] = self.get_consecutive_loss_adjustment()
            
        if confidence is not None:
            result['confidence'] = confidence
            
        if volatility_factor is not None:
            result['volatility_factor'] = volatility_factor
            
        return result
    
    def get_sizing_summary(self, sizing_info):
        """
        Get a human-readable summary of position sizing.
        
        Args:
            sizing_info: Dictionary with position sizing information
            
        Returns:
            String with sizing summary
        """
        if not sizing_info:
            return "No position sizing information available"
            
        position_size = sizing_info.get('position_size', 0)
        position_fraction = sizing_info.get('position_fraction', 0)
        method = sizing_info.get('method', 'unknown')
        win_probability = sizing_info.get('win_probability', 0)
        
        # Format summary
        summary = (
            f"Position Size: {position_size:.2f} ({position_fraction:.2%} of account)\n"
            f"Method: {method.capitalize()}\n"
            f"Win Probability: {win_probability:.2%}\n"
        )
        
        # Add risk reward if available
        if 'risk_reward_ratio' in sizing_info:
            summary += f"Risk/Reward: {sizing_info['risk_reward_ratio']:.2f}\n"
            
        # Add adjustment factors if available
        if 'drawdown_factor' in sizing_info:
            summary += f"Drawdown Adjustment: {sizing_info['drawdown_factor']:.2f}\n"
            
        if 'consecutive_loss_factor' in sizing_info:
            summary += f"Consecutive Loss Adjustment: {sizing_info['consecutive_loss_factor']:.2f}\n"
            
        if 'confidence' in sizing_info:
            summary += f"Confidence: {sizing_info['confidence']:.2f}\n"
            
        if 'volatility_factor' in sizing_info:
            summary += f"Volatility Factor: {sizing_info['volatility_factor']:.2f}"
            
        return summary
