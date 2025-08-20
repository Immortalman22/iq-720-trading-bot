import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
import logging
from pathlib import Path

class BacktestVisualizer:
    def __init__(self, output_dir: str = None):
        self.logger = logging.getLogger(__name__)
        self.output_dir = output_dir or Path.cwd() / "backtest_results"
        self.output_dir.mkdir(exist_ok=True)

    def create_performance_dashboard(self, results: Dict, save_path: str = None) -> None:
        """Create an interactive dashboard of backtest results"""
        try:
            trades_df = pd.DataFrame(results['trades'])
            trades_df['datetime'] = pd.to_datetime(trades_df['entry_time'])
            
            # Create the main figure with subplots
            fig = make_subplots(
                rows=3, cols=2,
                subplot_titles=(
                    'Cumulative Returns', 'Win/Loss Distribution',
                    'Monthly Returns', 'Trade Duration Distribution',
                    'Returns by Hour', 'Rolling Win Rate'
                ),
                vertical_spacing=0.12,
                horizontal_spacing=0.1,
                specs=[
                    [{"type": "scatter"}, {"type": "bar"}],
                    [{"type": "bar"}, {"type": "histogram"}],
                    [{"type": "bar"}, {"type": "scatter"}]
                ]
            )

            # 1. Cumulative Returns
            cumulative_returns = self._calculate_cumulative_returns(trades_df)
            fig.add_trace(
                go.Scatter(
                    x=cumulative_returns.index,
                    y=cumulative_returns.values,
                    name='Cumulative Returns',
                    line=dict(color='blue')
                ),
                row=1, col=1
            )

            # 2. Win/Loss Distribution
            win_loss = self._create_win_loss_distribution(trades_df)
            fig.add_trace(
                go.Bar(
                    x=['Wins', 'Losses'],
                    y=[win_loss['wins'], win_loss['losses']],
                    name='Win/Loss',
                    marker_color=['green', 'red']
                ),
                row=1, col=2
            )

            # 3. Monthly Returns
            monthly_returns = self._calculate_monthly_returns(trades_df)
            fig.add_trace(
                go.Bar(
                    x=monthly_returns.index,
                    y=monthly_returns.values,
                    name='Monthly Returns',
                    marker_color=np.where(monthly_returns >= 0, 'green', 'red')
                ),
                row=2, col=1
            )

            # 4. Trade Duration Distribution
            durations = self._calculate_trade_durations(trades_df)
            fig.add_trace(
                go.Histogram(
                    x=durations,
                    name='Trade Duration',
                    nbinsx=20,
                    marker_color='lightblue'
                ),
                row=2, col=2
            )

            # 5. Returns by Hour
            hourly_returns = self._calculate_hourly_returns(trades_df)
            fig.add_trace(
                go.Bar(
                    x=hourly_returns.index,
                    y=hourly_returns.values,
                    name='Hourly Returns',
                    marker_color='purple'
                ),
                row=3, col=1
            )

            # 6. Rolling Win Rate
            rolling_win_rate = self._calculate_rolling_win_rate(trades_df)
            fig.add_trace(
                go.Scatter(
                    x=rolling_win_rate.index,
                    y=rolling_win_rate.values,
                    name='Rolling Win Rate (20 trades)',
                    line=dict(color='orange')
                ),
                row=3, col=2
            )

            # Update layout
            fig.update_layout(
                height=1200,
                width=1600,
                title_text="Trading Strategy Performance Dashboard",
                showlegend=False
            )

            # Save if path provided
            if save_path:
                fig.write_html(self.output_dir / save_path)
                self.logger.info(f"Dashboard saved to {save_path}")

            return fig

        except Exception as e:
            self.logger.error(f"Error creating performance dashboard: {e}")
            raise

    def create_trade_analysis_report(self, results: Dict, save_path: str = None) -> None:
        """Create detailed trade analysis report"""
        try:
            trades_df = pd.DataFrame(results['trades'])
            
            # Calculate key metrics
            total_trades = len(trades_df)
            winning_trades = len(trades_df[trades_df['profit_loss'] > 0])
            win_rate = (winning_trades / total_trades) * 100
            
            avg_win = trades_df[trades_df['profit_loss'] > 0]['profit_loss'].mean()
            avg_loss = trades_df[trades_df['profit_loss'] < 0]['profit_loss'].mean()
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

            # Create report figure
            fig = go.Figure()

            # Add trade scatter plot
            fig.add_trace(go.Scatter(
                x=trades_df['entry_time'],
                y=trades_df['profit_loss'],
                mode='markers',
                marker=dict(
                    color=np.where(trades_df['profit_loss'] >= 0, 'green', 'red'),
                    size=8
                ),
                name='Trades'
            ))

            # Add annotations with key metrics
            fig.update_layout(
                annotations=[
                    dict(
                        x=0.02,
                        y=0.98,
                        xref="paper",
                        yref="paper",
                        text=f"Total Trades: {total_trades}<br>"
                             f"Win Rate: {win_rate:.2f}%<br>"
                             f"Profit Factor: {profit_factor:.2f}<br>"
                             f"Avg Win: ${avg_win:.2f}<br>"
                             f"Avg Loss: ${avg_loss:.2f}",
                        showarrow=False,
                        font=dict(size=12),
                        align="left",
                        bgcolor="white",
                        bordercolor="black",
                        borderwidth=1
                    )
                ],
                title="Trade Analysis Report",
                xaxis_title="Date",
                yaxis_title="Profit/Loss ($)",
                height=800
            )

            # Save if path provided
            if save_path:
                fig.write_html(self.output_dir / save_path)
                self.logger.info(f"Trade analysis report saved to {save_path}")

            return fig

        except Exception as e:
            self.logger.error(f"Error creating trade analysis report: {e}")
            raise

    def _calculate_cumulative_returns(self, trades_df: pd.DataFrame) -> pd.Series:
        """Calculate cumulative returns over time"""
        if trades_df.empty:
            return pd.Series()
        
        trades_df = trades_df.sort_values('entry_time')
        return trades_df['profit_loss'].cumsum()

    def _create_win_loss_distribution(self, trades_df: pd.DataFrame) -> Dict:
        """Create win/loss distribution data"""
        if trades_df.empty:
            return {'wins': 0, 'losses': 0}
        
        wins = len(trades_df[trades_df['profit_loss'] > 0])
        losses = len(trades_df[trades_df['profit_loss'] < 0])
        return {'wins': wins, 'losses': losses}

    def _calculate_monthly_returns(self, trades_df: pd.DataFrame) -> pd.Series:
        """Calculate returns aggregated by month"""
        if trades_df.empty:
            return pd.Series()
        
        trades_df['month'] = trades_df['entry_time'].dt.to_period('M')
        return trades_df.groupby('month')['profit_loss'].sum()

    def _calculate_trade_durations(self, trades_df: pd.DataFrame) -> pd.Series:
        """Calculate duration of each trade in minutes"""
        if trades_df.empty:
            return pd.Series()
        
        trades_df['duration'] = (
            pd.to_datetime(trades_df['exit_time']) - 
            pd.to_datetime(trades_df['entry_time'])
        ).dt.total_seconds() / 60
        return trades_df['duration']

    def _calculate_hourly_returns(self, trades_df: pd.DataFrame) -> pd.Series:
        """Calculate returns aggregated by hour of day"""
        if trades_df.empty:
            return pd.Series()
        
        trades_df['hour'] = trades_df['entry_time'].dt.hour
        return trades_df.groupby('hour')['profit_loss'].sum()

    def _calculate_rolling_win_rate(self, trades_df: pd.DataFrame, window: int = 20) -> pd.Series:
        """Calculate rolling win rate over specified window of trades"""
        if trades_df.empty:
            return pd.Series()
        
        wins = (trades_df['profit_loss'] > 0).astype(int)
        return wins.rolling(window=window, min_periods=1).mean() * 100
