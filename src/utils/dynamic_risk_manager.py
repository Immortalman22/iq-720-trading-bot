"""
Dynamic risk adjustment system.
Adjusts position sizes and risk parameters based on performance and market conditions.
"""
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
from .trade_tracker import TradeStats, TradeTracker
from .market_analyzer import MarketAnalyzer
from .logger import TradingBotLogger

@dataclass
class RiskParameters:
    """Risk parameters for trading decisions."""
    base_position_size: float = 1.0
    max_position_size: float = 2.0
    min_position_size: float = 0.1
    max_risk_per_trade: float = 0.02  # 2% per trade
    max_total_risk: float = 0.06  # 6% total risk
    drawdown_scaling: bool = True
    volatility_scaling: bool = True
    win_rate_scaling: bool = True
    profit_factor_scaling: bool = True

class DynamicRiskManager:
    """
    Manages dynamic risk adjustment based on performance metrics,
    market conditions, and account statistics.
    """
    def __init__(self, 
                 trade_tracker: TradeTracker,
                 market_analyzer: MarketAnalyzer,
                 base_params: Optional[RiskParameters] = None):
        """
        Initialize the risk manager.
        
        Args:
            trade_tracker: TradeTracker instance for performance metrics
            market_analyzer: MarketAnalyzer instance for market conditions
            base_params: Optional base risk parameters
        """
        self.logger = TradingBotLogger().logger
        self.trade_tracker = trade_tracker
        self.market_analyzer = market_analyzer
        self.params = base_params or RiskParameters()
        
        # Risk adjustment factors
        self.performance_factor = 1.0
        self.market_factor = 1.0
        
        # Historical factors
        self._prev_performance_factor = 1.0
        self._prev_market_factor = 1.0
        self._last_update = datetime.now()
        
    def calculate_position_size(self, symbol: str) -> float:
        """
        Calculate the optimal position size based on current conditions.
        
        Args:
            symbol: Trading symbol to calculate position size for
            
        Returns:
            float: Adjusted position size as a multiplier of base size
        """
        self._update_risk_factors(symbol)
        
        # Combine factors with weights
        total_factor = (self.performance_factor * 0.6 + 
                       self.market_factor * 0.4)
        
        # Apply to base position size with limits
        position_size = self.params.base_position_size * total_factor
        return max(min(position_size, self.params.max_position_size), 
                  self.params.min_position_size)
    
    def _update_risk_factors(self, symbol: str) -> None:
        """
        Update performance and market risk factors.
        
        Args:
            symbol: Trading symbol to analyze
        """
        now = datetime.now()
        # Only update every 15 minutes
        if (now - self._last_update) < timedelta(minutes=15):
            return
            
        self._prev_performance_factor = self.performance_factor
        self._prev_market_factor = self.market_factor
        
        # Update performance factor
        if self.params.win_rate_scaling or self.params.profit_factor_scaling:
            self._update_performance_factor()
            
        # Update market factor
        if self.params.volatility_scaling:
            self._update_market_factor(symbol)
            
        self._last_update = now
        
        # Log significant changes
        if (abs(self.performance_factor - self._prev_performance_factor) > 0.1 or
            abs(self.market_factor - self._prev_market_factor) > 0.1):
            self.logger.info(
                f"Risk factors updated - Perf: {self.performance_factor:.2f} "
                f"(prev: {self._prev_performance_factor:.2f}), "
                f"Market: {self.market_factor:.2f} "
                f"(prev: {self._prev_market_factor:.2f})"
            )
    
    def _update_performance_factor(self) -> None:
        """Update the performance-based risk factor."""
        stats = self.trade_tracker.get_statistics()
        
        # Start with base factor
        factor = 1.0
        
        if self.params.win_rate_scaling:
            # Scale based on win rate (0.5 = breakeven)
            win_rate = stats.win_rate if stats.win_rate else 0.5
            win_factor = (win_rate - 0.5) * 2  # -1 to 1 range
            factor *= (1 + win_factor * 0.3)  # ±30% adjustment
        
        if self.params.profit_factor_scaling:
            # Scale based on profit factor (1.0 = breakeven)
            profit_factor = stats.profit_factor if stats.profit_factor else 1.0
            pf_factor = min((profit_factor - 1.0), 1.0)  # 0 to 1 range
            factor *= (1 + pf_factor * 0.3)  # +30% max adjustment
        
        if self.params.drawdown_scaling:
            # Reduce size during drawdowns
            max_dd = stats.max_drawdown if stats.max_drawdown else 0.0
            if max_dd > 0:
                # Exponential reduction as drawdown increases
                dd_factor = np.exp(-2 * max_dd)  # Exponential decay
                factor *= dd_factor
        
        self.performance_factor = max(min(factor, 1.5), 0.5)  # Limit range
    
    def _update_market_factor(self, symbol: str) -> None:
        """
        Update the market condition-based risk factor.
        
        Args:
            symbol: Trading symbol to analyze
        """
        # Get market volatility
        volatility = self.market_analyzer.get_volatility(symbol)
        # Get market regime (trending vs ranging)
        trend_strength = self.market_analyzer.get_trend_strength(symbol)
        
        # Start with base factor
        factor = 1.0
        
        if self.params.volatility_scaling:
            # Scale down in high volatility, up in low volatility
            vol_factor = 1.0 - (volatility - 0.5) * 0.6  # ±30% adjustment
            factor *= vol_factor
        
        # Adjust for trend strength
        trend_factor = 1.0 + (trend_strength - 0.5) * 0.4  # ±20% adjustment
        factor *= trend_factor
        
        self.market_factor = max(min(factor, 1.5), 0.5)  # Limit range
        self.drawdown_factor = 1.0
        self.volatility_factor = 1.0
        
        # Risk state tracking
        self.current_total_risk = 0.0
        self.risk_per_symbol: Dict[str, float] = {}
        self.last_adjustment = datetime.now()
        self.adjustment_frequency = timedelta(minutes=15)

    def calculate_position_size(self, 
                              symbol: str,
                              signal_strength: float,
                              entry_price: float) -> float:
        """
        Calculate the appropriate position size based on current conditions.
        
        Args:
            symbol: Trading symbol
            signal_strength: Signal confidence (0.0 to 1.0)
            entry_price: Proposed entry price
            
        Returns:
            Adjusted position size
        """
        try:
            # Update factors if needed
            self._update_risk_factors()
            
            # Base position calculation
            base_size = self.params.base_position_size
            
            # Apply risk factors
            risk_adjusted_size = base_size * (
                self.performance_factor *
                self.market_factor *
                self.drawdown_factor *
                self.volatility_factor *
                signal_strength
            )
            
            # Apply limits
            position_size = max(
                min(risk_adjusted_size, self.params.max_position_size),
                self.params.min_position_size
            )
            
            # Check total risk limits
            if not self._validate_risk_limits(symbol, position_size, entry_price):
                self.logger.warning(f"Risk limits reached for {symbol}, reducing position")
                position_size = self._adjust_for_risk_limits(symbol, position_size, entry_price)
            
            return round(position_size, 2)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return self.params.min_position_size

    def update_risk_state(self, 
                         symbol: str, 
                         position_size: float, 
                         entry_price: float) -> None:
        """Update risk tracking state when a new position is opened."""
        try:
            risk = self._calculate_position_risk(position_size, entry_price)
            self.risk_per_symbol[symbol] = risk
            self.current_total_risk = sum(self.risk_per_symbol.values())
            
        except Exception as e:
            self.logger.error(f"Error updating risk state: {e}")

    def release_risk(self, symbol: str) -> None:
        """Release risk allocation when a position is closed."""
        try:
            if symbol in self.risk_per_symbol:
                self.current_total_risk -= self.risk_per_symbol[symbol]
                del self.risk_per_symbol[symbol]
                
        except Exception as e:
            self.logger.error(f"Error releasing risk: {e}")

    def _update_risk_factors(self) -> None:
        """Update all risk adjustment factors."""
        now = datetime.now()
        if now - self.last_adjustment < self.adjustment_frequency:
            return

        try:
            # Get latest statistics
            stats = self.trade_tracker.get_stats("week")  # Use weekly performance
            
            # Performance-based adjustment
            self._update_performance_factor(stats)
            
            # Market conditions adjustment
            self._update_market_factor()
            
            # Drawdown-based adjustment
            if self.params.drawdown_scaling:
                self._update_drawdown_factor(stats)
            
            # Volatility-based adjustment
            if self.params.volatility_scaling:
                self._update_volatility_factor()
            
            self.last_adjustment = now
            
        except Exception as e:
            self.logger.error(f"Error updating risk factors: {e}")

    def _update_performance_factor(self, stats: TradeStats) -> None:
        """Update the performance-based risk factor."""
        try:
            # Start with base factor
            factor = 1.0
            
            if stats.total_trades >= 10:  # Require minimum sample size
                # Win rate scaling
                if self.params.win_rate_scaling:
                    win_rate_factor = min(stats.win_rate * 1.5, 1.5)  # Max 50% increase
                    factor *= win_rate_factor
                
                # Profit factor scaling
                if self.params.profit_factor_scaling and stats.profit_factor > 0:
                    profit_factor = min(stats.profit_factor, 2.0) / 1.5  # Normalize
                    factor *= profit_factor
            
            # Smooth transitions
            self.performance_factor = (self.performance_factor * 0.7 + factor * 0.3)
            
        except Exception as e:
            self.logger.error(f"Error updating performance factor: {e}")

    def _update_market_factor(self) -> None:
        """Update the market conditions risk factor."""
        try:
            conditions = self.market_analyzer.get_market_conditions()
            
            # Start with base factor
            factor = 1.0
            
            # Adjust for trend strength
            trend_strength = conditions.get('trend_strength', 0.5)
            factor *= max(0.5, min(1.5, trend_strength))
            
            # Adjust for market regime
            regime = conditions.get('regime', 'normal')
            regime_factors = {
                'trending': 1.2,
                'ranging': 0.8,
                'volatile': 0.6,
                'normal': 1.0
            }
            factor *= regime_factors.get(regime, 1.0)
            
            # Smooth transitions
            self.market_factor = (self.market_factor * 0.7 + factor * 0.3)
            
        except Exception as e:
            self.logger.error(f"Error updating market factor: {e}")

    def _update_drawdown_factor(self, stats: TradeStats) -> None:
        """Update the drawdown-based risk factor."""
        try:
            max_allowed_dd = self.params.max_total_risk * 2  # Double the max risk
            current_dd = stats.max_drawdown
            
            if current_dd > 0:
                # Reduce risk as drawdown increases
                factor = max(0.5, 1 - (current_dd / max_allowed_dd))
            else:
                factor = 1.0
            
            # Smooth transitions
            self.drawdown_factor = (self.drawdown_factor * 0.7 + factor * 0.3)
            
        except Exception as e:
            self.logger.error(f"Error updating drawdown factor: {e}")

    def _update_volatility_factor(self) -> None:
        """Update the volatility-based risk factor."""
        try:
            volatility = self.market_analyzer.get_volatility()
            base_volatility = self.market_analyzer.get_base_volatility()
            
            if base_volatility > 0:
                vol_ratio = volatility / base_volatility
                # Reduce position size in high volatility
                factor = 1 / max(1, vol_ratio)
                # Increase size in low volatility (up to 20%)
                if vol_ratio < 1:
                    factor = min(1.2, 1 + (1 - vol_ratio) * 0.2)
            else:
                factor = 1.0
            
            # Smooth transitions
            self.volatility_factor = (self.volatility_factor * 0.7 + factor * 0.3)
            
        except Exception as e:
            self.logger.error(f"Error updating volatility factor: {e}")

    def _validate_risk_limits(self, 
                            symbol: str, 
                            position_size: float, 
                            entry_price: float) -> bool:
        """Check if the position respects risk limits."""
        try:
            new_risk = self._calculate_position_risk(position_size, entry_price)
            current_risk = sum(
                r for s, r in self.risk_per_symbol.items() if s != symbol
            )
            total_risk = current_risk + new_risk
            
            return total_risk <= self.params.max_total_risk
            
        except Exception as e:
            self.logger.error(f"Error validating risk limits: {e}")
            return False

    def _adjust_for_risk_limits(self, 
                              symbol: str, 
                              position_size: float, 
                              entry_price: float) -> float:
        """Adjust position size to respect risk limits."""
        try:
            current_risk = sum(
                r for s, r in self.risk_per_symbol.items() if s != symbol
            )
            remaining_risk = self.params.max_total_risk - current_risk
            
            if remaining_risk <= 0:
                return 0
            
            # Scale position size to fit remaining risk
            current_risk_per_unit = self._calculate_position_risk(1.0, entry_price)
            if current_risk_per_unit > 0:
                adjusted_size = remaining_risk / current_risk_per_unit
                return min(position_size, adjusted_size)
            
            return self.params.min_position_size
            
        except Exception as e:
            self.logger.error(f"Error adjusting for risk limits: {e}")
            return self.params.min_position_size

    def _calculate_position_risk(self, 
                               position_size: float, 
                               entry_price: float) -> float:
        """Calculate the risk exposure of a position."""
        try:
            # Use ATR or similar for risk calculation
            volatility = self.market_analyzer.get_volatility()
            risk_per_pip = position_size * entry_price * 0.0001  # For forex
            return risk_per_pip * volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating position risk: {e}")
            return 0.0
