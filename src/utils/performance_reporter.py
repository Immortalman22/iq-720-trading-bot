"""
Performance reporting module for the trading bot.
Generates detailed performance reports and analytics.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from pathlib import Path

from .trade_tracker import TradeTracker
from .logger import TradingBotLogger
from .market_analyzer import MarketAnalyzer

@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    total_return: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_trade_return: float
    avg_win_return: float
    avg_loss_return: float
    total_trades: int
    avg_trades_per_day: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    time_in_market: float  # Percentage
    risk_adjusted_return: float
    calmar_ratio: float
    recovery_factor: float

class PerformanceReporter:
    """
    Generates comprehensive performance reports including metrics,
    visualizations, and detailed analytics.
    """
    def __init__(self, 
                 trade_tracker: TradeTracker,
                 market_analyzer: MarketAnalyzer,
                 report_dir: str = "reports"):
        """
        Initialize the performance reporter.
        
        Args:
            trade_tracker: TradeTracker instance for trade history
            market_analyzer: MarketAnalyzer for market context
            report_dir: Directory to save reports
        """
        self.logger = TradingBotLogger().logger
        self.trade_tracker = trade_tracker
        self.market_analyzer = market_analyzer
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(exist_ok=True)
        
    def generate_report(self, timeframe: str = "all") -> Dict:
        """
        Generate a comprehensive performance report.
        
        Args:
            timeframe: Time period for report ("daily", "weekly", "monthly", "all")
            
        Returns:
            Dict containing report data and file paths
        """
        try:
            # Get trade history
            trades = self.trade_tracker.get_trade_history()
            if not trades:
                self.logger.warning("No trades available for report generation")
                return {}
                
            # Calculate core metrics
            metrics = self._calculate_metrics(trades, timeframe)
            
            # Generate visualizations
            figures = self._generate_visualizations(trades, metrics)
            
            # Save report components
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report = {
                "timestamp": timestamp,
                "timeframe": timeframe,
                "metrics": metrics.__dict__,
                "files": {}
            }
            
            # Save metrics to JSON
            metrics_file = self.report_dir / f"metrics_{timestamp}.json"
            with open(metrics_file, "w") as f:
                json.dump(metrics.__dict__, f, indent=4)
            report["files"]["metrics"] = str(metrics_file)
            
            # Save visualizations
            for name, fig in figures.items():
                fig_file = self.report_dir / f"{name}_{timestamp}.html"
                fig.write_html(str(fig_file))
                report["files"][name] = str(fig_file)
                
            # Generate summary markdown
            summary = self._generate_summary(metrics, timeframe)
            summary_file = self.report_dir / f"summary_{timestamp}.md"
            summary_file.write_text(summary)
            report["files"]["summary"] = str(summary_file)
            
            self.logger.info(f"Performance report generated: {timestamp}")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {}
    
    def _calculate_metrics(self, trades: List[Dict], 
                         timeframe: str) -> PerformanceMetrics:
        """Calculate performance metrics from trade history."""
        if not trades:
            return PerformanceMetrics(
                total_return=0.0, win_rate=0.0, profit_factor=0.0,
                max_drawdown=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
                avg_trade_return=0.0, avg_win_return=0.0, avg_loss_return=0.0,
                total_trades=0, avg_trades_per_day=0.0, max_consecutive_wins=0,
                max_consecutive_losses=0, time_in_market=0.0,
                risk_adjusted_return=0.0, calmar_ratio=0.0, recovery_factor=0.0
            )
        
        # Convert trades to DataFrame for analysis
        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter by timeframe if needed
        if timeframe != "all":
            cutoff = {
                "daily": timedelta(days=1),
                "weekly": timedelta(days=7),
                "monthly": timedelta(days=30)
            }.get(timeframe)
            if cutoff:
                df = df[df['timestamp'] >= datetime.now() - cutoff]
        
        if len(df) == 0:
            return PerformanceMetrics(
                total_return=0.0, win_rate=0.0, profit_factor=0.0,
                max_drawdown=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
                avg_trade_return=0.0, avg_win_return=0.0, avg_loss_return=0.0,
                total_trades=0, avg_trades_per_day=0.0, max_consecutive_wins=0,
                max_consecutive_losses=0, time_in_market=0.0,
                risk_adjusted_return=0.0, calmar_ratio=0.0, recovery_factor=0.0
            )
        
        # Calculate basic metrics
        total_return = df['profit_loss'].sum()
        winning_trades = df[df['profit_loss'] > 0]
        losing_trades = df[df['profit_loss'] < 0]
        
        win_rate = len(winning_trades) / len(df) if len(df) > 0 else 0
        profit_factor = (abs(winning_trades['profit_loss'].sum()) / 
                        abs(losing_trades['profit_loss'].sum())
                        if len(losing_trades) > 0 else float('inf'))
        
        # Calculate drawdown
        cumulative = df['profit_loss'].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(min(drawdown)) if len(drawdown) > 0 else 0
        
        # Calculate ratios
        returns = df['profit_loss'].pct_change()
        risk_free_rate = 0.02  # Assumed annual risk-free rate
        excess_returns = returns - (risk_free_rate / 252)  # Daily adjustment
        
        sharpe_ratio = (np.sqrt(252) * np.mean(excess_returns) / 
                       np.std(returns) if len(returns) > 1 else 0)
        
        downside_returns = returns[returns < 0]
        sortino_ratio = (np.sqrt(252) * np.mean(excess_returns) / 
                        np.std(downside_returns) if len(downside_returns) > 1 else 0)
        
        # Calculate consecutive wins/losses
        streak = df['profit_loss'].apply(lambda x: 1 if x > 0 else -1)
        pos_streaks = [len(list(g)) for k, g in itertools.groupby(streak) if k == 1]
        neg_streaks = [len(list(g)) for k, g in itertools.groupby(streak) if k == -1]
        
        max_consecutive_wins = max(pos_streaks) if pos_streaks else 0
        max_consecutive_losses = max(neg_streaks) if neg_streaks else 0
        
        # Calculate time in market
        total_time = (df['timestamp'].max() - df['timestamp'].min()).total_seconds()
        trade_time = df['duration'].sum().total_seconds()
        time_in_market = trade_time / total_time if total_time > 0 else 0
        
        # Calculate advanced ratios
        trading_days = (df['timestamp'].max() - df['timestamp'].min()).days or 1
        avg_trades_per_day = len(df) / trading_days
        
        calmar_ratio = abs(total_return / max_drawdown) if max_drawdown > 0 else 0
        risk_adjusted_return = total_return * (1 - max_drawdown)
        
        peak_value = cumulative.max()
        valley_value = cumulative[cumulative.idxmin()]
        recovery_factor = ((peak_value - valley_value) / 
                         abs(valley_value) if valley_value != 0 else 0)
        
        return PerformanceMetrics(
            total_return=total_return,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            avg_trade_return=df['profit_loss'].mean(),
            avg_win_return=winning_trades['profit_loss'].mean() if len(winning_trades) > 0 else 0,
            avg_loss_return=losing_trades['profit_loss'].mean() if len(losing_trades) > 0 else 0,
            total_trades=len(df),
            avg_trades_per_day=avg_trades_per_day,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            time_in_market=time_in_market,
            risk_adjusted_return=risk_adjusted_return,
            calmar_ratio=calmar_ratio,
            recovery_factor=recovery_factor
        )
    
    def _generate_visualizations(self, trades: List[Dict], 
                               metrics: PerformanceMetrics) -> Dict[str, go.Figure]:
        """Generate performance visualizations."""
        figures = {}
        
        # Equity curve
        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['cumulative_pnl'] = df['profit_loss'].cumsum()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['cumulative_pnl'],
            mode='lines',
            name='Equity Curve'
        ))
        fig.update_layout(
            title='Equity Curve',
            xaxis_title='Date',
            yaxis_title='Cumulative P&L'
        )
        figures['equity_curve'] = fig
        
        # Drawdown chart
        running_max = df['cumulative_pnl'].expanding().max()
        drawdown = (df['cumulative_pnl'] - running_max) / running_max
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=drawdown,
            mode='lines',
            name='Drawdown',
            fill='tonexty'
        ))
        fig.update_layout(
            title='Drawdown Chart',
            xaxis_title='Date',
            yaxis_title='Drawdown %'
        )
        figures['drawdown'] = fig
        
        # Win/Loss distribution
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=df['profit_loss'],
            name='Trade P&L Distribution'
        ))
        fig.update_layout(
            title='Trade P&L Distribution',
            xaxis_title='Profit/Loss',
            yaxis_title='Frequency'
        )
        figures['pnl_distribution'] = fig
        
        # Time analysis
        df['hour'] = df['timestamp'].dt.hour
        hourly_pnl = df.groupby('hour')['profit_loss'].mean()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=hourly_pnl.index,
            y=hourly_pnl.values,
            name='Average P&L by Hour'
        ))
        fig.update_layout(
            title='Average P&L by Hour',
            xaxis_title='Hour of Day',
            yaxis_title='Average P&L'
        )
        figures['hourly_performance'] = fig
        
        return figures
    
    def _generate_summary(self, metrics: PerformanceMetrics, timeframe: str) -> str:
        """Generate a markdown summary of the performance report."""
        return f"""# Trading Performance Summary ({timeframe})
        
## Key Metrics
- **Total Return**: {metrics.total_return:.2f}
- **Win Rate**: {metrics.win_rate:.2%}
- **Profit Factor**: {metrics.profit_factor:.2f}
- **Max Drawdown**: {metrics.max_drawdown:.2%}

## Risk Metrics
- **Sharpe Ratio**: {metrics.sharpe_ratio:.2f}
- **Sortino Ratio**: {metrics.sortino_ratio:.2f}
- **Calmar Ratio**: {metrics.calmar_ratio:.2f}
- **Risk-Adjusted Return**: {metrics.risk_adjusted_return:.2f}

## Trading Statistics
- **Total Trades**: {metrics.total_trades}
- **Average Trades/Day**: {metrics.avg_trades_per_day:.1f}
- **Average Trade Return**: {metrics.avg_trade_return:.2f}
- **Average Win**: {metrics.avg_win_return:.2f}
- **Average Loss**: {metrics.avg_loss_return:.2f}
- **Max Consecutive Wins**: {metrics.max_consecutive_wins}
- **Max Consecutive Losses**: {metrics.max_consecutive_losses}
- **Time in Market**: {metrics.time_in_market:.2%}
- **Recovery Factor**: {metrics.recovery_factor:.2f}

## Analysis
This report covers the {timeframe} timeframe. The strategy shows a 
{'positive' if metrics.total_return > 0 else 'negative'} total return with a 
{'strong' if metrics.win_rate > 0.6 else 'moderate' if metrics.win_rate > 0.5 else 'weak'} 
win rate of {metrics.win_rate:.2%}.

The risk-adjusted performance metrics indicate 
{'excellent' if metrics.sharpe_ratio > 2 else 'good' if metrics.sharpe_ratio > 1 else 'poor'} 
risk management with a Sharpe ratio of {metrics.sharpe_ratio:.2f}.

### Recommendations
{'Consider increasing position sizes.' if metrics.win_rate > 0.6 and metrics.profit_factor > 2 else
'Maintain current risk levels.' if metrics.win_rate > 0.5 and metrics.profit_factor > 1.5 else
'Consider reducing position sizes and reviewing strategy.'}
