import backtrader as bt
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import numpy as np
from .strategy import TradingStrategy
from ..visualization.backtest_visualizer import BacktestVisualizer

class BacktestEngine:
    def __init__(self, data_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.cerebro = bt.Cerebro()
        self.data_path = data_path
        self.results = None
        
        # Set up cerebro
        self.cerebro.addstrategy(TradingStrategy)
        self.cerebro.broker.setcash(10000.0)  # Start with 10k
        self.cerebro.broker.setcommission(commission=0.002)  # 0.2% commission

    def load_data(self, start_date: datetime = None, end_date: datetime = None) -> bool:
        """Load historical data for backtesting"""
        try:
            if not self.data_path:
                self.logger.error("No data path specified")
                return False

            # Load data from CSV
            df = pd.read_csv(self.data_path)
            df['datetime'] = pd.to_datetime(df['timestamp'])
            df.set_index('datetime', inplace=True)

            # Filter by date range if specified
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]

            # Create backtrader data feed
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,  # Index is already datetime
                open='open',
                high='high',
                low='low',
                close='close',
                volume='volume',
                openinterest=-1  # Not used
            )

            self.cerebro.adddata(data)
            return True

        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            return False

    def optimize_parameters(self, parameter_ranges: Dict) -> Tuple[Dict, float]:
        """Optimize strategy parameters using grid search"""
        try:
            # Store original strategy
            original_strategy = self.cerebro.strats[0][0]

            # Create parameter combinations
            param_combinations = []
            for rsi_period in parameter_ranges.get('rsi_period', [14]):
                for rsi_ob in parameter_ranges.get('rsi_overbought', [70]):
                    for rsi_os in parameter_ranges.get('rsi_oversold', [30]):
                        for macd_fast in parameter_ranges.get('macd_fast', [12]):
                            for macd_slow in parameter_ranges.get('macd_slow', [26]):
                                param_combinations.append({
                                    'rsi_period': rsi_period,
                                    'rsi_overbought': rsi_ob,
                                    'rsi_oversold': rsi_os,
                                    'macd_fast': macd_fast,
                                    'macd_slow': macd_slow
                                })

            # Test each combination
            best_params = None
            best_sharpe = float('-inf')

            for params in param_combinations:
                self.cerebro = bt.Cerebro()
                self.cerebro.addstrategy(TradingStrategy, **params)
                self.cerebro.broker.setcash(10000.0)
                self.cerebro.broker.setcommission(commission=0.002)
                
                if self.load_data():
                    results = self.cerebro.run()
                    sharpe = self._calculate_sharpe_ratio(results[0])
                    
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = params

            # Restore original strategy
            self.cerebro = bt.Cerebro()
            self.cerebro.addstrategy(original_strategy)
            self.cerebro.broker.setcash(10000.0)
            self.cerebro.broker.setcommission(commission=0.002)

            return best_params, best_sharpe

        except Exception as e:
            self.logger.error(f"Error in parameter optimization: {e}")
            return None, None

    def run(self) -> Optional[Dict]:
        """Run the backtest and return results"""
        try:
            self.results = self.cerebro.run()
            
            if not self.results:
                return None

            # Calculate performance metrics
            metrics = self._calculate_metrics(self.results[0])
            
            return metrics

        except Exception as e:
            self.logger.error(f"Error running backtest: {e}")
            return None

    def _calculate_metrics(self, strategy) -> Dict:
        """Calculate performance metrics"""
        trades = strategy.trades
        
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }

        # Calculate metrics
        profitable_trades = sum(1 for t in trades if t['profit_loss'] > 0)
        total_trades = len(trades)
        win_rate = (profitable_trades / total_trades) * 100

        profits = [t['profit_loss'] for t in trades]
        avg_profit = sum(profits) / len(profits)
        
        sharpe = self._calculate_sharpe_ratio(strategy)
        max_dd = self._calculate_max_drawdown(strategy)

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'trades': trades  # Detailed trade history
        }

    def _calculate_sharpe_ratio(self, strategy) -> float:
        """Calculate Sharpe ratio"""
        returns = pd.Series([t['profit_loss'] for t in strategy.trades])
        if len(returns) < 2:
            return 0
        
        return np.sqrt(252) * (returns.mean() / returns.std())

    def _calculate_max_drawdown(self, strategy) -> float:
        """Calculate maximum drawdown"""
        value = strategy.broker.getvalue()
        peak = value
        max_dd = 0

        for trade in strategy.trades:
            value += trade['profit_loss']
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd * 100  # Convert to percentage

    def plot_results(self, output_dir: str = None):
        """Generate interactive plots of backtest results"""
        if not self.results:
            self.logger.error("No results to plot. Run backtest first.")
            return

        try:
            metrics = self._calculate_metrics(self.results[0])
            visualizer = BacktestVisualizer(output_dir)

            # Generate performance dashboard
            visualizer.create_performance_dashboard(
                metrics,
                save_path='performance_dashboard.html'
            )

            # Generate trade analysis report
            visualizer.create_trade_analysis_report(
                metrics,
                save_path='trade_analysis.html'
            )

            self.logger.info("Backtest visualization completed successfully")
            
            return {
                'dashboard_path': 'performance_dashboard.html',
                'analysis_path': 'trade_analysis.html'
            }

        except Exception as e:
            self.logger.error(f"Error generating backtest visualizations: {e}")
            return None
