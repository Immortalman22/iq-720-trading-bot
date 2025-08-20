"""
Trade tracking and statistics module.
Handles tracking of trade performance, metrics, and historical statistics.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
import logging
from .logger import TradingBotLogger

@dataclass
class TradeStats:
    """Statistics for a collection of trades."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_holding_time: timedelta = timedelta()

@dataclass
class Trade:
    """Individual trade details."""
    id: str
    symbol: str
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: datetime = None
    exit_time: Optional[datetime] = None
    position_size: float = 0.0
    direction: str = "long"  # "long" or "short"
    status: str = "open"  # "open", "closed", "cancelled"
    profit_loss: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    tags: List[str] = None
    metadata: Dict[str, Any] = None

class TradeTracker:
    """
    Trade tracking system for monitoring and analyzing trading performance.
    Provides real-time statistics and historical analysis.
    """
    def __init__(self):
        """Initialize trade tracker."""
        self.logger = TradingBotLogger().logger
        self.trades: Dict[str, Trade] = {}
        self.last_update = datetime.now()
        
    def track_trade(self, trade: Trade) -> None:
        """Add or update a trade in the tracking system."""
        try:
            # Initialize lists if None
            if trade.tags is None:
                trade.tags = []
            if trade.metadata is None:
                trade.metadata = {}
                
            self.trades[trade.id] = trade
            self.last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error tracking trade: {e}")
            raise
            
    def get_stats(self, timeframe: str = "total") -> TradeStats:
        """
        Get trading statistics for the specified timeframe.
        
        Args:
            timeframe: 'total', 'day', 'week', or 'month'
            
        Returns:
            TradeStats object with calculated metrics
        """
        try:
            # Filter trades by timeframe
            start_time = None
            if timeframe == "day":
                start_time = datetime.now() - timedelta(days=1)
            elif timeframe == "week":
                start_time = datetime.now() - timedelta(days=7)
            elif timeframe == "month":
                start_time = datetime.now() - timedelta(days=30)
                
            # Get relevant trades
            relevant_trades = [
                t for t in self.trades.values()
                if t.status == "closed" and 
                (start_time is None or t.exit_time >= start_time)
            ]
            
            if not relevant_trades:
                return TradeStats()
            
            # Calculate basic metrics
            total_trades = len(relevant_trades)
            winning_trades = len([t for t in relevant_trades if t.profit_loss > 0])
            losing_trades = len([t for t in relevant_trades if t.profit_loss < 0])
            
            wins = [t.profit_loss for t in relevant_trades if t.profit_loss > 0]
            losses = [t.profit_loss for t in relevant_trades if t.profit_loss < 0]
            
            total_profit = sum(wins) if wins else 0.0
            total_loss = sum(losses) if losses else 0.0
            
            # Calculate win rate and profit factor
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            profit_factor = (
                abs(total_profit / total_loss) if total_loss != 0 
                else float('inf') if total_profit > 0 
                else 0.0
            )
            
            # Calculate averages
            avg_win = np.mean(wins) if wins else 0.0
            avg_loss = np.mean(losses) if losses else 0.0
            largest_win = max(wins) if wins else 0.0
            largest_loss = min(losses) if losses else 0.0
            
            # Calculate max drawdown
            max_drawdown = self._calculate_max_drawdown(relevant_trades)
            
            # Calculate average holding time
            holding_times = [
                (t.exit_time - t.entry_time)
                for t in relevant_trades
                if t.exit_time and t.entry_time
            ]
            avg_holding_time = (
                sum(holding_times, timedelta()) / len(holding_times)
                if holding_times else timedelta()
            )
            
            return TradeStats(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                total_profit=total_profit,
                total_loss=total_loss,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_win=avg_win,
                avg_loss=avg_loss,
                largest_win=largest_win,
                largest_loss=largest_loss,
                avg_holding_time=avg_holding_time
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating trade stats: {e}")
            return TradeStats()
            
    def _calculate_max_drawdown(self, trades: List[Trade]) -> float:
        """Calculate maximum drawdown from a list of trades."""
        try:
            if not trades:
                return 0.0
                
            # Sort trades by exit time
            sorted_trades = sorted(
                [t for t in trades if t.exit_time],
                key=lambda x: x.exit_time
            )
            
            # Calculate cumulative PnL
            cumulative_pnl = []
            current_pnl = 0.0
            
            for trade in sorted_trades:
                current_pnl += trade.profit_loss
                cumulative_pnl.append(current_pnl)
            
            # Calculate maximum drawdown
            peak = float('-inf')
            max_dd = 0.0
            
            for pnl in cumulative_pnl:
                if pnl > peak:
                    peak = pnl
                dd = (peak - pnl) / (peak if peak > 0 else 1.0)
                max_dd = max(max_dd, dd)
            
            return max_dd
            
        except Exception as e:
            self.logger.error(f"Error calculating max drawdown: {e}")
            return 0.0
    def __init__(self):
        logger = TradingBotLogger()
        self.logger = logger.logger
        self.active_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.trade_history: Dict[str, List[Trade]] = {}  # By symbol
        self.current_stats: TradeStats = TradeStats()
        
        # Performance tracking
        self.equity_curve: List[float] = []
        self.daily_stats: Dict[str, TradeStats] = {}
        self.max_equity: float = 0.0
        self.current_drawdown: float = 0.0

    def open_trade(self, trade: Trade) -> bool:
        """
        Register a new trade in the system.
        Returns True if successful, False otherwise.
        """
        try:
            if trade.id in self.active_trades:
                self.logger.warning(f"Trade {trade.id} already exists")
                return False
            
            trade.entry_time = trade.entry_time or datetime.now()
            trade.status = "open"
            self.active_trades[trade.id] = trade
            
            # Initialize symbol history if needed
            if trade.symbol not in self.trade_history:
                self.trade_history[trade.symbol] = []
            
            self.logger.info(f"Opened new trade: {trade.id} for {trade.symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error opening trade: {e}")
            return False

    def close_trade(self, trade_id: str, exit_price: float) -> Optional[Trade]:
        """
        Close an existing trade and update statistics.
        Returns the closed trade if successful, None otherwise.
        """
        try:
            if trade_id not in self.active_trades:
                self.logger.warning(f"Trade {trade_id} not found")
                return None
            
            trade = self.active_trades[trade_id]
            trade.exit_time = datetime.now()
            trade.exit_price = exit_price
            trade.status = "closed"
            
            # Calculate P/L (rounded to 4 decimal places for pip precision)
            multiplier = 1 if trade.direction == "long" else -1
            trade.profit_loss = round(
                (exit_price - trade.entry_price) * trade.position_size * multiplier, 
                4
            )
            
            # Update statistics
            self._update_stats(trade)
            
            # Move to closed trades
            del self.active_trades[trade_id]
            self.closed_trades.append(trade)
            self.trade_history[trade.symbol].append(trade)
            
            self.logger.info(f"Closed trade {trade_id} with P/L: {trade.profit_loss}")
            return trade
            
        except Exception as e:
            self.logger.error(f"Error closing trade: {e}")
            return None

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get details of a specific trade by ID."""
        return self.active_trades.get(trade_id) or next(
            (t for t in self.closed_trades if t.id == trade_id), None
        )

    def get_stats(self, timeframe: str = "all") -> TradeStats:
        """
        Get trading statistics for the specified timeframe.
        Timeframe can be 'day', 'week', 'month', 'year', or 'all'.
        """
        try:
            if timeframe == "all":
                return self.current_stats
            
            # Filter trades by timeframe
            now = datetime.now()
            delta = {
                "day": timedelta(days=1),
                "week": timedelta(days=7),
                "month": timedelta(days=30),
                "year": timedelta(days=365)
            }.get(timeframe)
            
            if not delta:
                self.logger.warning(f"Invalid timeframe: {timeframe}")
                return TradeStats()
            
            start_time = now - delta
            filtered_trades = [
                t for t in self.closed_trades 
                if t.entry_time and t.entry_time >= start_time
            ]
            
            return self._calculate_stats(filtered_trades)
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return TradeStats()

    def _update_stats(self, trade: Trade) -> None:
        """Update trading statistics with a newly closed trade."""
        try:
            stats = self.current_stats
            stats.total_trades += 1
            
            profit_loss = round(trade.profit_loss, 4)  # Ensure consistent precision
            if profit_loss > 0:
                stats.winning_trades += 1
                stats.total_profit = round(stats.total_profit + profit_loss, 4)
                stats.largest_win = round(max(stats.largest_win, profit_loss), 4)
            else:
                stats.losing_trades += 1
                stats.total_loss = round(stats.total_loss + abs(profit_loss), 4)
                stats.largest_loss = round(max(stats.largest_loss, abs(profit_loss)), 4)
            
            # Update win rate and profit factor
            stats.win_rate = round(stats.winning_trades / stats.total_trades, 4)
            if stats.total_loss > 0:
                stats.profit_factor = round(stats.total_profit / stats.total_loss, 4)
            
            # Update averages
            if stats.winning_trades > 0:
                stats.avg_win = round(stats.total_profit / stats.winning_trades, 4)
            if stats.losing_trades > 0:
                stats.avg_loss = round(stats.total_loss / stats.losing_trades, 4)
            
            # Update equity curve and drawdown
            current_equity = round(sum(t.profit_loss for t in self.closed_trades), 4)
            self.equity_curve.append(current_equity)
            self.max_equity = round(max(self.max_equity, current_equity), 4)
            
            # Calculate drawdown from peak
            drawdown = round(self.max_equity - current_equity, 4)
            self.current_drawdown = round(max(self.current_drawdown, drawdown), 4)
            stats.max_drawdown = self.current_drawdown
            
            # Update holding time statistics
            if trade.entry_time and trade.exit_time:
                holding_time = trade.exit_time - trade.entry_time
                if stats.total_trades == 1:
                    stats.avg_holding_time = holding_time
                else:
                    total_time = stats.avg_holding_time * (stats.total_trades - 1)
                    stats.avg_holding_time = (total_time + holding_time) / stats.total_trades
            
        except Exception as e:
            self.logger.error(f"Error updating stats: {e}")

    def _calculate_stats(self, trades: List[Trade]) -> TradeStats:
        """Calculate statistics for a list of trades."""
        stats = TradeStats()
        
        if not trades:
            return stats
            
        stats.total_trades = len(trades)
        stats.winning_trades = sum(1 for t in trades if t.profit_loss > 0)
        stats.losing_trades = stats.total_trades - stats.winning_trades
        
        profits = [t.profit_loss for t in trades if t.profit_loss > 0]
        losses = [abs(t.profit_loss) for t in trades if t.profit_loss < 0]
        
        stats.total_profit = sum(profits)
        stats.total_loss = sum(losses)
        stats.largest_win = max(profits) if profits else 0
        stats.largest_loss = max(losses) if losses else 0
        
        if stats.total_trades > 0:
            stats.win_rate = stats.winning_trades / stats.total_trades
        if stats.total_loss > 0:
            stats.profit_factor = stats.total_profit / stats.total_loss
        if profits:
            stats.avg_win = sum(profits) / len(profits)
        if losses:
            stats.avg_loss = sum(losses) / len(losses)
            
        # Calculate average holding time
        holding_times = [
            t.exit_time - t.entry_time 
            for t in trades 
            if t.entry_time and t.exit_time
        ]
        if holding_times:
            total_time = sum(holding_times, timedelta())
            stats.avg_holding_time = total_time / len(holding_times)
            
        return stats
