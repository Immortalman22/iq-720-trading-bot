#!/usr/bin/env python3
"""
Advanced backtesting framework for trading strategies with
comprehensive performance analytics, Monte Carlo simulations,
and visualization tools.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from scipy import stats
from joblib import Parallel, delayed
import multiprocessing
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Union, Callable, Any, Tuple

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.utils.logger import setup_logger
from src.backtesting.strategy import TradingStrategy

@dataclass
class Trade:
    """Class to store trade information"""
    id: str
    pair: str
    direction: str  # "LONG" or "SHORT"
    entry_time: datetime
    entry_price: float
    stop_loss: float = None
    take_profit: float = None
    exit_time: datetime = None
    exit_price: float = None
    quantity: float = 1.0
    commission: float = 0.0
    slippage: float = 0.0
    profit_loss: float = 0.0
    exit_reason: str = None  # "tp", "sl", "manual", "signal", "timeout"
    drawdown: float = 0.0
    max_favorable_excursion: float = 0.0  # Maximum profit during trade
    max_adverse_excursion: float = 0.0  # Maximum loss during trade
    trade_duration: timedelta = None
    tags: List[str] = field(default_factory=list)
    notes: str = None
    
    def calculate_profit_loss(self):
        """Calculate profit or loss for this trade"""
        if self.exit_price is None:
            return 0
        
        direction_multiplier = 1 if self.direction == "LONG" else -1
        price_diff = (self.exit_price - self.entry_price) * direction_multiplier
        total_commission = self.commission * 2  # Entry and exit
        
        self.profit_loss = (price_diff - total_commission) * self.quantity
        return self.profit_loss
    
    def calculate_drawdown(self, min_price):
        """Calculate maximum drawdown during trade"""
        if self.direction == "LONG":
            lowest = min(min_price, self.exit_price or min_price)
            self.drawdown = (self.entry_price - lowest) / self.entry_price
        else:  # SHORT
            highest = max(min_price, self.exit_price or min_price)
            self.drawdown = (highest - self.entry_price) / self.entry_price
        
        return self.drawdown
    
    def calculate_duration(self):
        """Calculate trade duration"""
        if self.exit_time is not None:
            self.trade_duration = self.exit_time - self.entry_time
        return self.trade_duration
    
    def to_dict(self):
        """Convert trade to dictionary"""
        return asdict(self)


@dataclass
class BacktestResult:
    """Class to store backtest results"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = None
    metrics: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_metrics(self):
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            logging.warning("No trades to calculate metrics")
            return {}
        
        # Extract trade data
        profits = [t.profit_loss for t in self.trades if t.profit_loss > 0]
        losses = [t.profit_loss for t in self.trades if t.profit_loss < 0]
        all_returns = [t.profit_loss / self.initial_capital for t in self.trades]
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = len(profits)
        losing_trades = len(losses)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Profit metrics
        gross_profit = sum(profits) if profits else 0
        gross_loss = sum(losses) if losses else 0
        net_profit = gross_profit + gross_loss
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')
        
        # Risk metrics
        if losses and winning_trades > 0 and losing_trades > 0:
            avg_win = sum(profits) / winning_trades
            avg_loss = abs(sum(losses) / losing_trades)
            risk_reward_ratio = avg_win / avg_loss if avg_loss != 0 else float('inf')
        else:
            avg_win = 0
            avg_loss = 0
            risk_reward_ratio = 0
        
        # Compute drawdowns from equity curve
        if self.equity_curve is not None and not self.equity_curve.empty:
            drawdowns = self._calculate_drawdowns(self.equity_curve)
            max_drawdown = drawdowns['drawdown'].max() if not drawdowns.empty else 0
            max_drawdown_duration = drawdowns['drawdown_duration'].max() if not drawdowns.empty else 0
        else:
            max_drawdown = 0
            max_drawdown_duration = 0
        
        # Calculate Sharpe ratio
        if len(all_returns) > 1:
            sharpe_ratio = np.mean(all_returns) / np.std(all_returns) * np.sqrt(252) if np.std(all_returns) != 0 else 0
        else:
            sharpe_ratio = 0
            
        # Other statistical metrics
        if len(all_returns) > 1:
            sortino_ratio = self._calculate_sortino_ratio(all_returns)
            calmar_ratio = self._calculate_calmar_ratio(self.equity_curve) if self.equity_curve is not None else 0
        else:
            sortino_ratio = 0
            calmar_ratio = 0
        
        # Store all metrics
        self.metrics = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_profit': net_profit,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'risk_reward_ratio': risk_reward_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_drawdown_duration,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'roi': (net_profit / self.initial_capital) if self.initial_capital > 0 else 0,
            'avg_trade_duration': np.mean([t.trade_duration.total_seconds() / 3600 for t in self.trades if t.trade_duration]),
            'longest_winning_streak': self._calculate_longest_streak(True),
            'longest_losing_streak': self._calculate_longest_streak(False),
            'avg_bars_in_trade': self._calculate_avg_bars_in_trade(),
        }
        
        return self.metrics
    
    def _calculate_drawdowns(self, equity_curve):
        """Calculate drawdowns from equity curve"""
        # Make a copy to avoid modifying the original
        if equity_curve.empty:
            return pd.DataFrame()
            
        equity = equity_curve.copy()
        
        # Calculate running maximum
        equity['running_max'] = equity['equity'].cummax()
        
        # Calculate drawdown and drawdown duration
        equity['drawdown'] = (equity['equity'] / equity['running_max']) - 1
        equity['drawdown'] = equity['drawdown'].abs()
        
        # Mark drawdown start and end
        equity['is_drawdown'] = equity['drawdown'] > 0
        equity['drawdown_start'] = equity['is_drawdown'] & ~equity['is_drawdown'].shift(1).fillna(False)
        equity['drawdown_end'] = ~equity['is_drawdown'] & equity['is_drawdown'].shift(1).fillna(False)
        
        # Calculate drawdown duration
        equity['drawdown_id'] = equity['drawdown_start'].cumsum()
        equity['drawdown_duration'] = equity.groupby('drawdown_id').cumcount()
        
        # Only keep rows where drawdown is happening
        drawdown_periods = equity[equity['is_drawdown']]
        
        return drawdown_periods
    
    def _calculate_sortino_ratio(self, returns, risk_free_rate=0.0, target_return=0.0):
        """
        Calculate Sortino ratio (like Sharpe but only considers downside deviation)
        """
        # Filter for negative returns (downside)
        downside_returns = [r for r in returns if r < target_return]
        
        if not downside_returns:
            return float('inf')  # No downside returns
        
        # Calculate downside deviation
        downside_deviation = np.sqrt(np.mean([(r - target_return)**2 for r in downside_returns]))
        
        if downside_deviation == 0:
            return float('inf')
            
        # Calculate Sortino ratio
        sortino = (np.mean(returns) - risk_free_rate) / downside_deviation
        
        return sortino * np.sqrt(252)  # Annualized
    
    def _calculate_calmar_ratio(self, equity_curve, years=3):
        """
        Calculate Calmar ratio (annualized return / maximum drawdown)
        """
        if equity_curve is None or equity_curve.empty:
            return 0
            
        # Calculate compound annual growth rate
        start_equity = equity_curve['equity'].iloc[0]
        end_equity = equity_curve['equity'].iloc[-1]
        
        # Calculate years duration
        days_diff = (equity_curve.index[-1] - equity_curve.index[0]).days
        year_frac = days_diff / 365.25
        
        # Check for division by zero or near-zero
        if year_frac < 0.01:  # If less than ~3.65 days
            return 0
        
        # Calculate CAGR
        cagr = (end_equity / start_equity) ** (1 / year_frac) - 1
        
        # Calculate max drawdown
        drawdowns = self._calculate_drawdowns(equity_curve)
        max_drawdown = drawdowns['drawdown'].max() if not drawdowns.empty else 0
        
        if max_drawdown == 0:
            return float('inf')
            
        return cagr / max_drawdown
    
    def _calculate_longest_streak(self, winning=True):
        """Calculate longest winning or losing streak"""
        if not self.trades:
            return 0
            
        # Create a list of 1s (wins) and 0s (losses)
        results = [1 if t.profit_loss > 0 else 0 for t in self.trades]
        
        # Find the longest streak
        target = 1 if winning else 0
        longest = current = 0
        
        for r in results:
            if r == target:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
                
        return longest
    
    def _calculate_avg_bars_in_trade(self):
        """Calculate average number of bars (candles) in each trade"""
        # This would require knowledge of the timeframe and data
        # For now, return a placeholder
        return 0
    
    def to_dict(self):
        """Convert result to dictionary"""
        result_dict = {
            'strategy_name': self.strategy_name,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': self.initial_capital,
            'trades': [t.to_dict() for t in self.trades],
            'metrics': self.metrics,
            'parameters': self.parameters
        }
        
        # Convert equity curve to dict if exists
        if self.equity_curve is not None:
            result_dict['equity_curve'] = self.equity_curve.to_dict()
            
        return result_dict
    
    def to_json(self, path=None):
        """Save backtest results as JSON"""
        result_dict = self.to_dict()
        
        # Convert complex objects to strings
        for trade in result_dict['trades']:
            if isinstance(trade['entry_time'], datetime):
                trade['entry_time'] = trade['entry_time'].isoformat()
            if isinstance(trade['exit_time'], datetime):
                trade['exit_time'] = trade['exit_time'].isoformat()
            if isinstance(trade['trade_duration'], timedelta):
                trade['trade_duration'] = str(trade['trade_duration'])
        
        if path:
            with open(path, 'w') as f:
                json.dump(result_dict, f, indent=2)
                
        return json.dumps(result_dict, indent=2)


class Backtester:
    """
    Advanced backtesting engine with comprehensive performance analytics
    """
    
    def __init__(self, 
                data: pd.DataFrame, 
                strategy: TradingStrategy,
                initial_capital: float = 10000.0,
                commission: float = 0.0,
                slippage: float = 0.0,
                position_size: float = 1.0,
                log_level: str = "INFO"):
        """
        Initialize backtester with data and strategy
        
        Args:
            data: DataFrame with OHLCV data
            strategy: Trading strategy instance
            initial_capital: Initial capital for backtesting
            commission: Commission per trade (percentage)
            slippage: Slippage per trade (percentage)
            position_size: Position size as percentage of capital (0-1)
            log_level: Logging level
        """
        self.data = data.copy()
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = position_size
        
        # Set up logger
        self.logger = setup_logger(level=log_level)
        
        # Initialize results
        self.trades = []
        self.equity_curve = None
        self.metrics = {}
        
        # Check if data has required columns
        required_cols = ['open', 'high', 'low', 'close']
        missing_cols = [col for col in required_cols if col not in self.data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in data: {missing_cols}")
        
        # Ensure data is sorted by date
        if not self.data.index.is_monotonic_increasing:
            self.data = self.data.sort_index()
            
    def run(self, start_date=None, end_date=None) -> BacktestResult:
        """
        Run backtest over the specified period
        
        Args:
            start_date: Start date for backtest (default: beginning of data)
            end_date: End date for backtest (default: end of data)
            
        Returns:
            BacktestResult object with trades and performance metrics
        """
        # Set start and end dates
        if start_date is None:
            start_date = self.data.index[0]
        if end_date is None:
            end_date = self.data.index[-1]
            
        # Filter data to specified range
        data = self.data.loc[start_date:end_date].copy()
        if data.empty:
            self.logger.error(f"No data available for period {start_date} to {end_date}")
            return None
            
        self.logger.info(f"Running backtest from {start_date} to {end_date}")
        self.logger.info(f"Data shape: {data.shape}")
        
        # Initialize variables
        capital = self.initial_capital
        position = None
        equity = [capital]
        equity_ts = [data.index[0]]
        open_trade = None
        
        # Initialize result object
        result = BacktestResult(
            strategy_name=self.strategy.name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            parameters=self.strategy.get_parameters()
        )
        
        # Run strategy on data
        signals = self.strategy.generate_signals(data)
        
        # Iterate through each candle
        for i, (timestamp, candle) in enumerate(data.iterrows()):
            current_price = candle['close']
            
            # Skip first candle as we need previous data
            if i == 0:
                equity.append(capital)
                equity_ts.append(timestamp)
                continue
                
            # Get signal for this candle
            signal = signals.loc[timestamp] if timestamp in signals.index else None
            
            # Handle open position
            if open_trade:
                # Calculate unrealized P&L
                direction_mult = 1 if open_trade.direction == "LONG" else -1
                unrealized_pnl = (current_price - open_trade.entry_price) * direction_mult * open_trade.quantity
                
                # Update max favorable/adverse excursions
                if unrealized_pnl > open_trade.max_favorable_excursion:
                    open_trade.max_favorable_excursion = unrealized_pnl
                if unrealized_pnl < open_trade.max_adverse_excursion:
                    open_trade.max_adverse_excursion = unrealized_pnl
                
                # Check for stop loss or take profit
                if open_trade.stop_loss is not None:
                    if (open_trade.direction == "LONG" and current_price <= open_trade.stop_loss) or \
                       (open_trade.direction == "SHORT" and current_price >= open_trade.stop_loss):
                        # Close position at stop loss
                        exit_price = open_trade.stop_loss
                        open_trade.exit_time = timestamp
                        open_trade.exit_price = exit_price
                        open_trade.exit_reason = "sl"
                        open_trade.calculate_profit_loss()
                        open_trade.calculate_duration()
                        
                        # Update capital
                        capital += open_trade.profit_loss
                        
                        # Add trade to list
                        result.trades.append(open_trade)
                        open_trade = None
                        
                        self.logger.debug(f"Stop loss triggered at {timestamp}: {exit_price}")
                        
                elif open_trade.take_profit is not None:
                    if (open_trade.direction == "LONG" and current_price >= open_trade.take_profit) or \
                       (open_trade.direction == "SHORT" and current_price <= open_trade.take_profit):
                        # Close position at take profit
                        exit_price = open_trade.take_profit
                        open_trade.exit_time = timestamp
                        open_trade.exit_price = exit_price
                        open_trade.exit_reason = "tp"
                        open_trade.calculate_profit_loss()
                        open_trade.calculate_duration()
                        
                        # Update capital
                        capital += open_trade.profit_loss
                        
                        # Add trade to list
                        result.trades.append(open_trade)
                        open_trade = None
                        
                        self.logger.debug(f"Take profit triggered at {timestamp}: {exit_price}")
                        
                # Check for exit signal
                if signal is not None and signal == -1 * direction_mult:  # Exit signal
                    # Apply slippage
                    exit_price = current_price * (1 - self.slippage) if open_trade.direction == "LONG" else \
                                 current_price * (1 + self.slippage)
                                 
                    open_trade.exit_time = timestamp
                    open_trade.exit_price = exit_price
                    open_trade.exit_reason = "signal"
                    open_trade.calculate_profit_loss()
                    open_trade.calculate_duration()
                    
                    # Update capital
                    capital += open_trade.profit_loss
                    
                    # Add trade to list
                    result.trades.append(open_trade)
                    open_trade = None
                    
                    self.logger.debug(f"Exit signal at {timestamp}: {exit_price}")
            
            # Check for entry signals if no position
            if open_trade is None and signal is not None:
                if signal == 1:  # Long signal
                    # Apply slippage
                    entry_price = current_price * (1 + self.slippage)
                    
                    # Calculate position size
                    quantity = (capital * self.position_size) / entry_price
                    
                    # Create new trade
                    open_trade = Trade(
                        id=f"T{len(result.trades) + 1}",
                        pair=self.data['pair'].iloc[0] if 'pair' in self.data.columns else "Unknown",
                        direction="LONG",
                        entry_time=timestamp,
                        entry_price=entry_price,
                        quantity=quantity,
                        commission=self.commission * entry_price * quantity,
                        slippage=self.slippage
                    )
                    
                    # Set stop loss and take profit if provided by strategy
                    if hasattr(self.strategy, 'get_stop_loss'):
                        open_trade.stop_loss = self.strategy.get_stop_loss(data.iloc[:i+1], "LONG")
                    if hasattr(self.strategy, 'get_take_profit'):
                        open_trade.take_profit = self.strategy.get_take_profit(data.iloc[:i+1], "LONG")
                    
                    self.logger.debug(f"Long entry at {timestamp}: {entry_price}")
                    
                elif signal == -1:  # Short signal
                    # Apply slippage
                    entry_price = current_price * (1 - self.slippage)
                    
                    # Calculate position size
                    quantity = (capital * self.position_size) / entry_price
                    
                    # Create new trade
                    open_trade = Trade(
                        id=f"T{len(result.trades) + 1}",
                        pair=self.data['pair'].iloc[0] if 'pair' in self.data.columns else "Unknown",
                        direction="SHORT",
                        entry_time=timestamp,
                        entry_price=entry_price,
                        quantity=quantity,
                        commission=self.commission * entry_price * quantity,
                        slippage=self.slippage
                    )
                    
                    # Set stop loss and take profit if provided by strategy
                    if hasattr(self.strategy, 'get_stop_loss'):
                        open_trade.stop_loss = self.strategy.get_stop_loss(data.iloc[:i+1], "SHORT")
                    if hasattr(self.strategy, 'get_take_profit'):
                        open_trade.take_profit = self.strategy.get_take_profit(data.iloc[:i+1], "SHORT")
                    
                    self.logger.debug(f"Short entry at {timestamp}: {entry_price}")
            
            # Update equity curve
            if open_trade:
                # Calculate unrealized P&L
                direction_mult = 1 if open_trade.direction == "LONG" else -1
                unrealized_pnl = (current_price - open_trade.entry_price) * direction_mult * open_trade.quantity
                current_equity = capital + unrealized_pnl
            else:
                current_equity = capital
                
            equity.append(current_equity)
            equity_ts.append(timestamp)
        
        # Close any open trades at the end of the backtest
        if open_trade:
            exit_price = data['close'].iloc[-1]
            open_trade.exit_time = data.index[-1]
            open_trade.exit_price = exit_price
            open_trade.exit_reason = "end_of_backtest"
            open_trade.calculate_profit_loss()
            open_trade.calculate_duration()
            
            # Update capital
            capital += open_trade.profit_loss
            
            # Add trade to list
            result.trades.append(open_trade)
            
            # Update final equity
            equity[-1] = capital
        
        # Create equity curve DataFrame
        equity_df = pd.DataFrame({
            'equity': equity
        }, index=equity_ts)
        result.equity_curve = equity_df
        
        # Calculate metrics
        result.calculate_metrics()
        
        self.logger.info(f"Backtest completed: {len(result.trades)} trades executed")
        self.logger.info(f"Final equity: ${equity[-1]:.2f}")
        self.logger.info(f"Net profit: ${result.metrics['net_profit']:.2f}")
        self.logger.info(f"Win rate: {result.metrics['win_rate']*100:.1f}%")
        
        return result
    
    def monte_carlo_analysis(self, backtest_result, iterations=1000, resample_pct=100):
        """
        Perform Monte Carlo simulation to test robustness of strategy
        
        Args:
            backtest_result: BacktestResult object from previous backtest
            iterations: Number of Monte Carlo iterations
            resample_pct: Percentage of trades to resample (100 = all trades)
            
        Returns:
            DataFrame with Monte Carlo results
        """
        if not backtest_result.trades:
            self.logger.error("No trades to perform Monte Carlo analysis")
            return None
            
        self.logger.info(f"Running Monte Carlo analysis with {iterations} iterations")
        
        # Extract trade returns
        original_returns = [(t.profit_loss / self.initial_capital) for t in backtest_result.trades]
        
        # Calculate number of trades to resample
        n_trades = int(len(original_returns) * (resample_pct / 100))
        
        # Store results
        monte_carlo_results = []
        
        for i in tqdm(range(iterations), desc="Monte Carlo Simulation"):
            # Resample trades with replacement
            sampled_returns = np.random.choice(original_returns, size=n_trades, replace=True)
            
            # Calculate cumulative returns
            cumulative_returns = np.cumprod(1 + sampled_returns) - 1
            
            # Calculate drawdowns
            peak = np.maximum.accumulate(1 + cumulative_returns)
            drawdown = (1 + cumulative_returns) / peak - 1
            
            # Store results
            monte_carlo_results.append({
                'iteration': i,
                'final_return': cumulative_returns[-1],
                'max_drawdown': drawdown.min() if len(drawdown) > 0 else 0,
                'sharpe_ratio': np.mean(sampled_returns) / np.std(sampled_returns) * np.sqrt(252) \
                                if np.std(sampled_returns) > 0 else 0,
                'returns': cumulative_returns.tolist()
            })
        
        # Convert to DataFrame
        mc_df = pd.DataFrame(monte_carlo_results)
        
        # Calculate percentiles
        percentiles = [5, 25, 50, 75, 95]
        percentile_values = {
            f"return_{p}pct": np.percentile(mc_df['final_return'], p) 
            for p in percentiles
        }
        percentile_values.update({
            f"drawdown_{p}pct": np.percentile(mc_df['max_drawdown'], p)
            for p in percentiles
        })
        
        # Log results
        self.logger.info("Monte Carlo Analysis Results:")
        self.logger.info(f"Return (median): {percentile_values['return_50pct']*100:.2f}%")
        self.logger.info(f"Return (5% worst): {percentile_values['return_5pct']*100:.2f}%")
        self.logger.info(f"Max Drawdown (median): {percentile_values['drawdown_50pct']*100:.2f}%")
        self.logger.info(f"Max Drawdown (95% worst): {percentile_values['drawdown_95pct']*100:.2f}%")
        
        return mc_df, percentile_values
    
    def visualize_results(self, backtest_result, monte_carlo_results=None):
        """
        Create comprehensive visualization of backtest results
        
        Args:
            backtest_result: BacktestResult object from previous backtest
            monte_carlo_results: Optional results from monte_carlo_analysis
            
        Returns:
            matplotlib figure
        """
        if backtest_result is None or backtest_result.equity_curve is None:
            self.logger.error("No backtest results to visualize")
            return None
            
        # Set style
        plt.style.use('ggplot')
        sns.set_palette("viridis")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 2, height_ratios=[2, 1, 1.5, 1.5])
        
        # Subplot 1: Equity curve
        ax1 = fig.add_subplot(gs[0, :])
        equity_curve = backtest_result.equity_curve['equity']
        equity_curve.plot(ax=ax1, linewidth=2)
        ax1.set_title('Equity Curve')
        ax1.set_ylabel('Equity ($)')
        ax1.set_xlabel('')
        ax1.grid(True)
        
        # Calculate drawdowns for visualization
        if not equity_curve.empty:
            peak = equity_curve.cummax()
            drawdown = (equity_curve - peak) / peak * 100
            
            # Add drawdown to the same axis with secondary y-axis
            ax1_dd = ax1.twinx()
            drawdown.plot(ax=ax1_dd, color='red', alpha=0.3, linewidth=1)
            ax1_dd.set_ylabel('Drawdown (%)')
            ax1_dd.set_ylim(bottom=min(drawdown.min() * 1.5, -5), top=5)
        
        # Subplot 2: Monthly returns heatmap
        ax2 = fig.add_subplot(gs[1, 0])
        if not equity_curve.empty:
            # Calculate daily returns
            daily_returns = equity_curve.pct_change().fillna(0)
            
            # Group by year and month
            monthly_returns = daily_returns.groupby([
                daily_returns.index.year.rename('Year'),
                daily_returns.index.month.rename('Month')
            ]).apply(lambda x: (1 + x).prod() - 1)
            
            # Convert to DataFrame and pivot
            monthly_returns_df = monthly_returns.reset_index()
            if not monthly_returns_df.empty:
                monthly_returns_pivot = monthly_returns_df.pivot_table(
                    index='Year', 
                    columns='Month', 
                    values=0
                ).fillna(0)
                
                # Plot heatmap
                sns.heatmap(
                    monthly_returns_pivot * 100,
                    ax=ax2,
                    cmap=sns.diverging_palette(10, 130, n=100),
                    center=0,
                    annot=True,
                    fmt=".1f"
                )
                ax2.set_title('Monthly Returns (%)')
                
                # Format x-axis as month names
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                ax2.set_xticklabels(month_names, rotation=0)
            else:
                ax2.text(0.5, 0.5, "Insufficient data for monthly returns", 
                        ha='center', va='center', transform=ax2.transAxes)
        else:
            ax2.text(0.5, 0.5, "No equity data available", 
                    ha='center', va='center', transform=ax2.transAxes)
        
        # Subplot 3: Trade outcomes
        ax3 = fig.add_subplot(gs[1, 1])
        if backtest_result.trades:
            trade_outcomes = [t.profit_loss for t in backtest_result.trades]
            trade_durations = [t.trade_duration.total_seconds() / 3600 if t.trade_duration else 0 
                              for t in backtest_result.trades]
            
            # Calculate win rate
            win_rate = sum(1 for t in trade_outcomes if t > 0) / len(trade_outcomes)
            
            # Create scatter plot of trade outcomes
            scatter = ax3.scatter(
                range(len(trade_outcomes)),
                trade_outcomes,
                c=['green' if t > 0 else 'red' for t in trade_outcomes],
                alpha=0.6,
                s=[min(d, 100) for d in trade_durations]  # Size based on duration
            )
            
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax3.set_title(f'Trade Outcomes (Win Rate: {win_rate:.1%})')
            ax3.set_xlabel('Trade #')
            ax3.set_ylabel('Profit/Loss ($)')
            
            # Add annotation for best and worst trades
            best_trade = max(trade_outcomes)
            worst_trade = min(trade_outcomes)
            best_idx = trade_outcomes.index(best_trade)
            worst_idx = trade_outcomes.index(worst_trade)
            
            ax3.annotate(f"Best: ${best_trade:.2f}", 
                        xy=(best_idx, best_trade),
                        xytext=(10, 20),
                        textcoords="offset points",
                        arrowprops=dict(arrowstyle="->"))
            ax3.annotate(f"Worst: ${worst_trade:.2f}", 
                        xy=(worst_idx, worst_trade),
                        xytext=(10, -20),
                        textcoords="offset points",
                        arrowprops=dict(arrowstyle="->"))
        else:
            ax3.text(0.5, 0.5, "No trades executed", 
                    ha='center', va='center', transform=ax3.transAxes)
        
        # Subplot 4: Monte Carlo equity curves
        ax4 = fig.add_subplot(gs[2, :])
        if monte_carlo_results is not None and len(monte_carlo_results[0]) > 0:
            mc_df, percentiles = monte_carlo_results
            
            # Plot sample of Monte Carlo paths
            sample_size = min(100, len(mc_df))
            sample = mc_df.sample(sample_size)
            
            # Create arrays for each path
            for _, row in sample.iterrows():
                returns = row['returns']
                equity = self.initial_capital * np.array([1] + [1 + r for r in returns])
                ax4.plot(equity, color='blue', alpha=0.05)
            
            # Plot percentile curves
            percentiles_to_plot = [5, 50, 95]
            colors = ['red', 'black', 'green']
            
            # Calculate percentile curves
            if len(sample) > 0 and len(sample.iloc[0]['returns']) > 0:
                # Get returns by index position across all iterations
                all_returns = np.array([mc_df.iloc[i]['returns'] for i in range(len(mc_df))])
                
                # Calculate percentiles at each step
                percentile_curves = {}
                for p in percentiles_to_plot:
                    percentile_returns = np.percentile(all_returns, p, axis=0)
                    percentile_equity = self.initial_capital * np.array([1] + [1 + r for r in percentile_returns])
                    percentile_curves[p] = percentile_equity
                
                # Plot percentile curves
                for i, p in enumerate(percentiles_to_plot):
                    ax4.plot(percentile_curves[p], color=colors[i], linewidth=2, 
                            label=f"{p}th Percentile")
                
                ax4.set_title('Monte Carlo Simulation: Equity Curves')
                ax4.set_ylabel('Equity ($)')
                ax4.set_xlabel('Trade #')
                ax4.legend()
                ax4.grid(True)
            else:
                ax4.text(0.5, 0.5, "Insufficient Monte Carlo data", 
                        ha='center', va='center', transform=ax4.transAxes)
        else:
            ax4.text(0.5, 0.5, "No Monte Carlo results available", 
                    ha='center', va='center', transform=ax4.transAxes)
        
        # Subplot 5: Trade metrics
        ax5 = fig.add_subplot(gs[3, 0])
        if backtest_result.metrics:
            metrics = backtest_result.metrics
            
            # Select key metrics to display
            display_metrics = [
                ('Net Profit', f"${metrics['net_profit']:.2f}"),
                ('Return on Investment', f"{metrics['roi']*100:.2f}%"),
                ('Win Rate', f"{metrics['win_rate']*100:.2f}%"),
                ('Profit Factor', f"{metrics['profit_factor']:.2f}"),
                ('Sharpe Ratio', f"{metrics['sharpe_ratio']:.2f}"),
                ('Max Drawdown', f"{metrics['max_drawdown']*100:.2f}%"),
                ('Avg Win/Loss', f"{metrics['risk_reward_ratio']:.2f}"),
                ('Total Trades', f"{metrics['total_trades']}")
            ]
            
            # Create a table
            ax5.axis('tight')
            ax5.axis('off')
            table = ax5.table(cellText=[[v[0], v[1]] for v in display_metrics],
                             colWidths=[0.6, 0.4],
                             loc='center',
                             cellLoc='left')
            table.auto_set_font_size(False)
            table.set_fontsize(12)
            table.scale(1, 2)
            
            ax5.set_title('Performance Metrics')
        else:
            ax5.text(0.5, 0.5, "No performance metrics available", 
                    ha='center', va='center', transform=ax5.transAxes)
        
        # Subplot 6: Distribution of returns
        ax6 = fig.add_subplot(gs[3, 1])
        if backtest_result.trades:
            trade_returns = [t.profit_loss / self.initial_capital for t in backtest_result.trades]
            
            # Plot histogram
            sns.histplot(trade_returns, kde=True, ax=ax6, bins=20)
            
            # Add normal distribution for comparison
            x = np.linspace(min(trade_returns), max(trade_returns), 100)
            mu, std = stats.norm.fit(trade_returns)
            p = stats.norm.pdf(x, mu, std)
            ax6.plot(x, p * len(trade_returns) * (max(trade_returns) - min(trade_returns)) / 20, 
                    'r-', linewidth=2, alpha=0.6)
            
            ax6.set_title('Distribution of Trade Returns')
            ax6.set_xlabel('Return (%)')
            ax6.set_ylabel('Frequency')
            
            # Add annotation with distribution statistics
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            textstr = f"Mean: {mu*100:.2f}%\nStd Dev: {std*100:.2f}%"
            ax6.text(0.05, 0.95, textstr, transform=ax6.transAxes, fontsize=10,
                    verticalalignment='top', bbox=props)
        else:
            ax6.text(0.5, 0.5, "No trade return data available", 
                    ha='center', va='center', transform=ax6.transAxes)
        
        # Add title
        fig.suptitle(
            f"Backtest Results: {backtest_result.strategy_name}\n"
            f"Period: {backtest_result.start_date.date()} to {backtest_result.end_date.date()}",
            fontsize=16
        )
        
        plt.tight_layout(rect=[0, 0, 1, 0.97])
        
        return fig
    
    def optimize_parameters(self, parameter_space, n_trials=10, parallel=True):
        """
        Optimize strategy parameters using grid search
        
        Args:
            parameter_space: Dictionary of parameters to optimize with lists of values
            n_trials: Number of trials for each parameter combination (for Monte Carlo)
            parallel: Whether to use parallel processing
            
        Returns:
            DataFrame with optimization results
        """
        self.logger.info("Starting parameter optimization")
        
        # Generate all parameter combinations
        import itertools
        param_names = list(parameter_space.keys())
        param_values = list(parameter_space.values())
        param_combinations = list(itertools.product(*param_values))
        
        self.logger.info(f"Testing {len(param_combinations)} parameter combinations")
        
        # Function to evaluate a parameter combination
        def evaluate_params(params):
            # Create parameter dict
            param_dict = dict(zip(param_names, params))
            
            # Update strategy parameters
            self.strategy.set_parameters(param_dict)
            
            # Run backtest
            result = self.run()
            
            if result is None or not result.metrics:
                return {
                    'params': param_dict,
                    'sharpe_ratio': -999,
                    'net_profit': -999,
                    'max_drawdown': 1,
                    'win_rate': 0,
                    'profit_factor': 0,
                    'trades': 0
                }
            
            # Return key metrics
            return {
                'params': param_dict,
                'sharpe_ratio': result.metrics.get('sharpe_ratio', 0),
                'net_profit': result.metrics.get('net_profit', 0),
                'max_drawdown': result.metrics.get('max_drawdown', 1),
                'win_rate': result.metrics.get('win_rate', 0),
                'profit_factor': result.metrics.get('profit_factor', 0),
                'trades': result.metrics.get('total_trades', 0)
            }
        
        # Run optimization
        results = []
        if parallel:
            # Use parallel processing
            n_cores = multiprocessing.cpu_count()
            self.logger.info(f"Using {n_cores} CPU cores for parallel optimization")
            results = Parallel(n_jobs=n_cores)(
                delayed(evaluate_params)(params) for params in tqdm(param_combinations)
            )
        else:
            # Sequential processing
            for params in tqdm(param_combinations):
                results.append(evaluate_params(params))
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        
        # Sort by Sharpe ratio (or other metric)
        results_df = results_df.sort_values('sharpe_ratio', ascending=False)
        
        # Display best parameters
        best_params = results_df.iloc[0]['params']
        self.logger.info("Optimization complete")
        self.logger.info(f"Best parameters: {best_params}")
        self.logger.info(f"Sharpe ratio: {results_df.iloc[0]['sharpe_ratio']:.2f}")
        self.logger.info(f"Net profit: ${results_df.iloc[0]['net_profit']:.2f}")
        
        return results_df, best_params


def save_backtest_report(result, monte_carlo=None, filepath=None):
    """
    Generate and save comprehensive backtest report
    
    Args:
        result: BacktestResult object
        monte_carlo: Optional tuple with (mc_df, percentiles)
        filepath: Path to save HTML report
        
    Returns:
        HTML report as string
    """
    if not result or not result.metrics:
        logging.error("No valid backtest result to generate report")
        return None
    
    try:
        import jinja2
        import base64
        from io import BytesIO
    except ImportError:
        logging.error("jinja2 required for HTML report generation")
        return None
    
    # Create visualizations
    backtester = Backtester(pd.DataFrame(), None)  # Dummy backtester for visualization methods
    fig = backtester.visualize_results(result, monte_carlo)
    
    # Save plot to buffer
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    # Create Jinja2 template
    template_str = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Backtest Report: {{ result.strategy_name }}</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            h1, h2, h3 {
                color: #2c3e50;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f2f2f2;
            }
            .chart-container {
                max-width: 100%;
                margin: 30px 0;
            }
            .chart-container img {
                max-width: 100%;
                height: auto;
            }
            .metrics-container {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                justify-content: space-between;
            }
            .metric-card {
                flex: 1;
                min-width: 200px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f8f9fa;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                margin: 10px 0;
            }
            .positive {
                color: #28a745;
            }
            .negative {
                color: #dc3545;
            }
            .trades-table {
                font-size: 14px;
            }
            .trades-container {
                max-height: 500px;
                overflow-y: auto;
            }
        </style>
    </head>
    <body>
        <h1>Backtest Report: {{ result.strategy_name }}</h1>
        <p>Period: {{ result.start_date.strftime('%Y-%m-%d') }} to {{ result.end_date.strftime('%Y-%m-%d') }}</p>
        
        <div class="chart-container">
            <img src="data:image/png;base64,{{ img_str }}" alt="Backtest Results">
        </div>
        
        <h2>Performance Summary</h2>
        <div class="metrics-container">
            <div class="metric-card">
                <h3>Net Profit</h3>
                <div class="metric-value {% if result.metrics.net_profit > 0 %}positive{% else %}negative{% endif %}">
                    ${{ "%.2f"|format(result.metrics.net_profit) }}
                </div>
                <p>Return: {{ "%.2f"|format(result.metrics.roi * 100) }}%</p>
            </div>
            
            <div class="metric-card">
                <h3>Sharpe Ratio</h3>
                <div class="metric-value {% if result.metrics.sharpe_ratio > 1 %}positive{% else %}negative{% endif %}">
                    {{ "%.2f"|format(result.metrics.sharpe_ratio) }}
                </div>
                <p>Sortino: {{ "%.2f"|format(result.metrics.sortino_ratio) }}</p>
            </div>
            
            <div class="metric-card">
                <h3>Win Rate</h3>
                <div class="metric-value {% if result.metrics.win_rate > 0.5 %}positive{% else %}negative{% endif %}">
                    {{ "%.1f"|format(result.metrics.win_rate * 100) }}%
                </div>
                <p>Profit Factor: {{ "%.2f"|format(result.metrics.profit_factor) }}</p>
            </div>
            
            <div class="metric-card">
                <h3>Max Drawdown</h3>
                <div class="metric-value negative">
                    {{ "%.2f"|format(result.metrics.max_drawdown * 100) }}%
                </div>
                <p>Duration: {{ result.metrics.max_drawdown_duration }} bars</p>
            </div>
        </div>
        
        <h2>Detailed Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Trades</td>
                <td>{{ result.metrics.total_trades }}</td>
                <td>Winning Trades</td>
                <td>{{ result.metrics.winning_trades }}</td>
            </tr>
            <tr>
                <td>Losing Trades</td>
                <td>{{ result.metrics.losing_trades }}</td>
                <td>Win Rate</td>
                <td>{{ "%.2f"|format(result.metrics.win_rate * 100) }}%</td>
            </tr>
            <tr>
                <td>Gross Profit</td>
                <td>${{ "%.2f"|format(result.metrics.gross_profit) }}</td>
                <td>Gross Loss</td>
                <td>${{ "%.2f"|format(result.metrics.gross_loss) }}</td>
            </tr>
            <tr>
                <td>Average Win</td>
                <td>${{ "%.2f"|format(result.metrics.avg_win) }}</td>
                <td>Average Loss</td>
                <td>${{ "%.2f"|format(result.metrics.avg_loss) }}</td>
            </tr>
            <tr>
                <td>Risk-Reward Ratio</td>
                <td>{{ "%.2f"|format(result.metrics.risk_reward_ratio) }}</td>
                <td>Profit Factor</td>
                <td>{{ "%.2f"|format(result.metrics.profit_factor) }}</td>
            </tr>
            <tr>
                <td>Sharpe Ratio</td>
                <td>{{ "%.2f"|format(result.metrics.sharpe_ratio) }}</td>
                <td>Sortino Ratio</td>
                <td>{{ "%.2f"|format(result.metrics.sortino_ratio) }}</td>
            </tr>
            <tr>
                <td>Calmar Ratio</td>
                <td>{{ "%.2f"|format(result.metrics.calmar_ratio) }}</td>
                <td>Max Drawdown</td>
                <td>{{ "%.2f"|format(result.metrics.max_drawdown * 100) }}%</td>
            </tr>
            <tr>
                <td>Avg Trade Duration</td>
                <td>{{ "%.1f"|format(result.metrics.avg_trade_duration) }} hours</td>
                <td>Longest Winning Streak</td>
                <td>{{ result.metrics.longest_winning_streak }}</td>
            </tr>
            <tr>
                <td>Longest Losing Streak</td>
                <td>{{ result.metrics.longest_losing_streak }}</td>
                <td>Return on Investment</td>
                <td>{{ "%.2f"|format(result.metrics.roi * 100) }}%</td>
            </tr>
        </table>
        
        {% if monte_carlo %}
        <h2>Monte Carlo Analysis</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>5th Percentile</th>
                <th>25th Percentile</th>
                <th>50th Percentile (Median)</th>
                <th>75th Percentile</th>
                <th>95th Percentile</th>
            </tr>
            <tr>
                <td>Final Return</td>
                <td>{{ "%.2f"|format(monte_carlo[1].return_5pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].return_25pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].return_50pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].return_75pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].return_95pct * 100) }}%</td>
            </tr>
            <tr>
                <td>Max Drawdown</td>
                <td>{{ "%.2f"|format(monte_carlo[1].drawdown_5pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].drawdown_25pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].drawdown_50pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].drawdown_75pct * 100) }}%</td>
                <td>{{ "%.2f"|format(monte_carlo[1].drawdown_95pct * 100) }}%</td>
            </tr>
        </table>
        {% endif %}
        
        <h2>Strategy Parameters</h2>
        <table>
            <tr>
                <th>Parameter</th>
                <th>Value</th>
            </tr>
            {% for key, value in result.parameters.items() %}
            <tr>
                <td>{{ key }}</td>
                <td>{{ value }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <h2>Trade List ({{ result.trades|length }} trades)</h2>
        <div class="trades-container">
            <table class="trades-table">
                <tr>
                    <th>ID</th>
                    <th>Pair</th>
                    <th>Direction</th>
                    <th>Entry Time</th>
                    <th>Exit Time</th>
                    <th>Entry Price</th>
                    <th>Exit Price</th>
                    <th>P/L ($)</th>
                    <th>Duration</th>
                    <th>Exit Reason</th>
                </tr>
                {% for trade in result.trades %}
                <tr>
                    <td>{{ trade.id }}</td>
                    <td>{{ trade.pair }}</td>
                    <td>{{ trade.direction }}</td>
                    <td>{{ trade.entry_time.strftime('%Y-%m-%d %H:%M') }}</td>
                    <td>{{ trade.exit_time.strftime('%Y-%m-%d %H:%M') if trade.exit_time else 'Open' }}</td>
                    <td>{{ "%.5f"|format(trade.entry_price) }}</td>
                    <td>{{ "%.5f"|format(trade.exit_price) if trade.exit_price else '-' }}</td>
                    <td class="{% if trade.profit_loss > 0 %}positive{% elif trade.profit_loss < 0 %}negative{% endif %}">
                        {{ "%.2f"|format(trade.profit_loss) }}
                    </td>
                    <td>{{ trade.trade_duration }}</td>
                    <td>{{ trade.exit_reason }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <footer>
            <p>Report generated on {{ now.strftime('%Y-%m-%d %H:%M:%S') }}</p>
        </footer>
    </body>
    </html>
    """
    
    # Render template
    template = jinja2.Template(template_str)
    html = template.render(
        result=result,
        monte_carlo=monte_carlo,
        img_str=img_str,
        now=datetime.now()
    )
    
    # Save to file if path provided
    if filepath:
        with open(filepath, 'w') as f:
            f.write(html)
            logging.info(f"Backtest report saved to {filepath}")
    
    return html


if __name__ == "__main__":
    # Example usage
    pass
