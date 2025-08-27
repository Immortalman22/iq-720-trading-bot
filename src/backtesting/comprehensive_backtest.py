#!/usr/bin/env python3
"""
Comprehensive Backtesting Module
This module integrates all backtesting tools for a complete analysis
"""
import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Union, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.utils.logger import setup_logger
from src.backtesting.advanced_backtest import Backtester, BacktestResult, save_backtest_report
from src.backtesting.monte_carlo import MonteCarloSimulator
from src.backtesting.drawdown_analyzer import DrawdownAnalyzer
from src.backtesting.performance_attribution import PerformanceAttribution
from src.backtesting.strategy import TradingStrategy


class ComprehensiveBacktest:
    """
    Comprehensive backtesting framework that integrates all analysis tools
    """
    
    def __init__(self, 
                 strategy: TradingStrategy,
                 data: pd.DataFrame,
                 initial_capital: float = 10000.0,
                 commission: float = 0.0,
                 slippage: float = 0.0,
                 position_size: float = 1.0,
                 output_dir: str = "results/backtests",
                 log_level: str = "INFO"):
        """
        Initialize comprehensive backtester
        
        Args:
            strategy: TradingStrategy instance
            data: DataFrame with OHLCV data
            initial_capital: Initial capital for backtesting
            commission: Commission per trade (percentage)
            slippage: Slippage per trade (percentage)
            position_size: Position size as percentage of capital (0-1)
            output_dir: Directory for output files
            log_level: Logging level
        """
        self.strategy = strategy
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = position_size
        self.output_dir = Path(output_dir)
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        self.logger = setup_logger(level=log_level)
        
        # Initialize components
        self.backtester = Backtester(
            data=data,
            strategy=strategy,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            position_size=position_size,
            log_level=log_level
        )
        
        self.mc_simulator = MonteCarloSimulator(log_level=log_level)
        self.drawdown_analyzer = DrawdownAnalyzer(log_level=log_level)
        self.performance_attribution = PerformanceAttribution(log_level=log_level)
        
        # Initialize result storage
        self.backtest_result = None
        self.mc_result = None
        self.drawdown_report = None
        
    def run_full_analysis(self,
                        start_date=None,
                        end_date=None,
                        mc_iterations: int = 1000,
                        save_results: bool = True,
                        save_figures: bool = True,
                        market_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Run a comprehensive backtest with all analyses
        
        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            mc_iterations: Number of Monte Carlo iterations
            save_results: Whether to save results to files
            save_figures: Whether to save figures to files
            market_data: Optional market data for benchmark comparison
            
        Returns:
            Dictionary with results summary
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{self.strategy.name}_{timestamp}"
        
        self.logger.info(f"Starting comprehensive backtest for {self.strategy.name}")
        self.logger.info(f"Run ID: {run_id}")
        
        # Step 1: Run basic backtest
        self.logger.info("Step 1: Running basic backtest")
        self.backtest_result = self.backtester.run(start_date, end_date)
        
        if self.backtest_result is None:
            self.logger.error("Backtest failed, aborting comprehensive analysis")
            return {'success': False, 'error': 'Backtest failed'}
        
        # Step 2: Run Monte Carlo simulation
        self.logger.info("Step 2: Running Monte Carlo simulation")
        trade_returns = [(t.profit_loss / self.initial_capital) for t in self.backtest_result.trades]
        
        if not trade_returns:
            self.logger.warning("No trades for Monte Carlo simulation, skipping")
            self.mc_result = None
        else:
            self.mc_result = self.mc_simulator.run_simulation(
                returns=trade_returns,
                initial_capital=self.initial_capital,
                iterations=mc_iterations
            )
        
        # Step 3: Analyze drawdowns
        self.logger.info("Step 3: Analyzing drawdowns")
        if self.backtest_result.equity_curve is not None and not self.backtest_result.equity_curve.empty:
            self.drawdown_report = self.drawdown_analyzer.create_drawdown_report(
                self.backtest_result.equity_curve['equity']
            )
            
            # Get top drawdowns
            self.top_drawdowns = self.drawdown_analyzer.identify_drawdown_periods(
                self.backtest_result.equity_curve['equity']
            )
        else:
            self.logger.warning("No equity curve for drawdown analysis, skipping")
            self.drawdown_report = None
            self.top_drawdowns = []
            
        # Step 4: Performance attribution
        self.logger.info("Step 4: Analyzing performance attribution")
        if market_data is not None:
            # Calculate strategy returns
            strategy_returns = self.backtest_result.equity_curve['equity'].pct_change().fillna(0)
            
            # Align market data
            common_index = strategy_returns.index.intersection(market_data.index)
            if len(common_index) > 0:
                market_returns = market_data.loc[common_index].pct_change().fillna(0)
                
                # Run attribution
                self.regime_attribution = self.performance_attribution.market_regime_attribution(
                    strategy_returns=strategy_returns.loc[common_index],
                    market_returns=market_returns
                )
                
                # Factor attribution if multiple market factors provided
                if isinstance(market_returns, pd.DataFrame) and market_returns.shape[1] > 1:
                    self.factor_attribution = self.performance_attribution.factor_attribution(
                        strategy_returns=strategy_returns.loc[common_index],
                        factor_returns=market_returns
                    )
                else:
                    self.factor_attribution = None
            else:
                self.logger.warning("No overlapping dates with market data, skipping attribution")
                self.regime_attribution = None
                self.factor_attribution = None
        else:
            self.regime_attribution = None
            self.factor_attribution = None
            
        # Trade attribution
        if self.backtest_result.trades:
            # Convert trades to list of dicts
            trade_dicts = [t.to_dict() for t in self.backtest_result.trades]
            
            # Check if trades have direction and exit_reason attributes
            attributes = []
            if 'direction' in trade_dicts[0]:
                attributes.append('direction')
            if 'exit_reason' in trade_dicts[0]:
                attributes.append('exit_reason')
                
            if attributes:
                self.trade_attribution = self.performance_attribution.trade_attribution(
                    trades=trade_dicts,
                    attributes=attributes
                )
            else:
                self.trade_attribution = None
        else:
            self.trade_attribution = None
            
        # Step 5: Create visualizations
        self.logger.info("Step 5: Creating visualizations")
        
        # Main backtest visualization
        self.backtest_fig = self.backtester.visualize_results(
            self.backtest_result, 
            self.mc_result
        )
        
        # Drawdown visualization
        if self.drawdown_report is not None and not self.drawdown_report.empty:
            self.drawdown_fig = self.drawdown_analyzer.visualize_drawdowns(
                self.backtest_result.equity_curve['equity']
            )
        else:
            self.drawdown_fig = None
            
        # Monte Carlo visualization
        if self.mc_result is not None:
            self.mc_fig = self.mc_simulator.visualize_results(self.mc_result)
        else:
            self.mc_fig = None
            
        # Factor attribution visualization
        if self.factor_attribution is not None:
            self.factor_fig = self.performance_attribution.visualize_factor_attribution(self.factor_attribution)
        else:
            self.factor_fig = None
            
        # Regime attribution visualization
        if self.regime_attribution is not None and not self.regime_attribution.empty:
            self.regime_fig = self.performance_attribution.visualize_regime_attribution(self.regime_attribution)
        else:
            self.regime_fig = None
            
        # Step 6: Save results
        if save_results:
            self.logger.info("Step 6: Saving results")
            results_path = self.output_dir / run_id
            results_path.mkdir(exist_ok=True)
            
            # Save backtest result
            if self.backtest_result is not None:
                self.backtest_result.to_json(results_path / "backtest_result.json")
                
                # Save HTML report
                save_backtest_report(
                    self.backtest_result,
                    self.mc_result,
                    filepath=results_path / "backtest_report.html"
                )
                
            # Save Monte Carlo result
            if self.mc_result is not None:
                pd.to_pickle(self.mc_result, results_path / "monte_carlo_result.pkl")
                
            # Save drawdown report
            if self.drawdown_report is not None and not self.drawdown_report.empty:
                self.drawdown_report.to_csv(results_path / "drawdown_report.csv")
                
            # Save regime attribution
            if self.regime_attribution is not None and not self.regime_attribution.empty:
                self.regime_attribution.to_csv(results_path / "regime_attribution.csv")
                
            # Save trade attribution
            if self.trade_attribution is not None and not self.trade_attribution.empty:
                self.trade_attribution.to_csv(results_path / "trade_attribution.csv")
                
            # Save figures
            if save_figures:
                # Create figures directory
                figures_path = results_path / "figures"
                figures_path.mkdir(exist_ok=True)
                
                # Save all figures
                if self.backtest_fig is not None:
                    self.backtest_fig.savefig(figures_path / "backtest_results.png", dpi=150)
                    
                if self.drawdown_fig is not None:
                    self.drawdown_fig.savefig(figures_path / "drawdowns.png", dpi=150)
                    
                if self.mc_fig is not None:
                    self.mc_fig.savefig(figures_path / "monte_carlo.png", dpi=150)
                    
                if self.factor_fig is not None:
                    self.factor_fig.savefig(figures_path / "factor_attribution.png", dpi=150)
                    
                if self.regime_fig is not None:
                    self.regime_fig.savefig(figures_path / "regime_attribution.png", dpi=150)
        
        # Create results summary
        summary = {
            'success': True,
            'run_id': run_id,
            'strategy_name': self.strategy.name,
            'start_date': self.backtest_result.start_date.strftime('%Y-%m-%d'),
            'end_date': self.backtest_result.end_date.strftime('%Y-%m-%d'),
            'total_trades': len(self.backtest_result.trades),
            'net_profit': self.backtest_result.metrics['net_profit'],
            'roi': self.backtest_result.metrics['roi'],
            'sharpe_ratio': self.backtest_result.metrics['sharpe_ratio'],
            'max_drawdown': self.backtest_result.metrics['max_drawdown'],
            'win_rate': self.backtest_result.metrics['win_rate'],
            'profit_factor': self.backtest_result.metrics['profit_factor'],
            'monte_carlo': {
                'return_median': self.mc_result.percentiles['return_50pct'] if self.mc_result else None,
                'return_worst5pct': self.mc_result.percentiles['return_5pct'] if self.mc_result else None,
                'max_drawdown_median': self.mc_result.percentiles['drawdown_50pct'] if self.mc_result else None,
                'max_drawdown_worst95pct': self.mc_result.percentiles['drawdown_95pct'] if self.mc_result else None
            } if self.mc_result else None,
            'parameters': self.strategy.get_parameters()
        }
        
        self.logger.info("Comprehensive backtest completed successfully")
        
        return summary
        
    def optimize_and_test(self, 
                        parameter_space: Dict[str, List],
                        train_period: Tuple[datetime, datetime],
                        test_period: Tuple[datetime, datetime],
                        n_trials: int = 10,
                        parallel: bool = True) -> Dict[str, Any]:
        """
        Optimize parameters in training period and test in out-of-sample period
        
        Args:
            parameter_space: Dictionary of parameters to optimize with lists of values
            train_period: Tuple of (start_date, end_date) for training period
            test_period: Tuple of (start_date, end_date) for testing period
            n_trials: Number of trials for each parameter combination
            parallel: Whether to use parallel processing
            
        Returns:
            Dictionary with optimization and test results
        """
        # Set up run ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{self.strategy.name}_opt_{timestamp}"
        
        self.logger.info(f"Starting parameter optimization for {self.strategy.name}")
        self.logger.info(f"Run ID: {run_id}")
        
        # Step 1: Run optimization on training period
        self.logger.info("Step 1: Optimizing on training period")
        train_start, train_end = train_period
        
        # Filter data for training period
        train_data = self.data.loc[train_start:train_end].copy()
        
        # Create backtester for training
        train_backtester = Backtester(
            data=train_data,
            strategy=self.strategy,
            initial_capital=self.initial_capital,
            commission=self.commission,
            slippage=self.slippage,
            position_size=self.position_size
        )
        
        # Run optimization
        opt_results, best_params = train_backtester.optimize_parameters(
            parameter_space=parameter_space,
            n_trials=n_trials,
            parallel=parallel
        )
        
        # Step 2: Test best parameters on test period
        self.logger.info("Step 2: Testing best parameters on test period")
        test_start, test_end = test_period
        
        # Filter data for test period
        test_data = self.data.loc[test_start:test_end].copy()
        
        # Create backtester for testing with best parameters
        self.strategy.set_parameters(best_params)
        
        test_backtester = Backtester(
            data=test_data,
            strategy=self.strategy,
            initial_capital=self.initial_capital,
            commission=self.commission,
            slippage=self.slippage,
            position_size=self.position_size
        )
        
        # Run test
        test_result = test_backtester.run()
        
        # Step 3: Create visualizations and save results
        self.logger.info("Step 3: Creating visualizations and saving results")
        
        # Create output directory
        results_path = self.output_dir / run_id
        results_path.mkdir(parents=True, exist_ok=True)
        
        # Save optimization results
        opt_results.to_csv(results_path / "optimization_results.csv")
        
        with open(results_path / "best_parameters.json", "w") as f:
            json.dump(best_params, f, indent=4)
        
        # Save test results
        if test_result is not None:
            test_result.to_json(results_path / "test_result.json")
            
            # Save HTML report
            save_backtest_report(
                test_result,
                None,
                filepath=results_path / "test_report.html"
            )
            
            # Create and save test visualization
            test_fig = test_backtester.visualize_results(test_result)
            test_fig.savefig(results_path / "test_results.png", dpi=150)
        
        # Create comparison table
        top_n_params = min(10, len(opt_results))
        top_params = opt_results.head(top_n_params)
        
        # Create a summary of train vs test performance
        summary = {
            'success': test_result is not None,
            'run_id': run_id,
            'strategy_name': self.strategy.name,
            'train_period': {
                'start_date': train_start.strftime('%Y-%m-%d'),
                'end_date': train_end.strftime('%Y-%m-%d')
            },
            'test_period': {
                'start_date': test_start.strftime('%Y-%m-%d'),
                'end_date': test_end.strftime('%Y-%m-%d')
            },
            'best_parameters': best_params,
            'train_performance': {
                'sharpe_ratio': opt_results.iloc[0]['sharpe_ratio'],
                'net_profit': opt_results.iloc[0]['net_profit'],
                'max_drawdown': opt_results.iloc[0]['max_drawdown'],
                'win_rate': opt_results.iloc[0]['win_rate'],
            } if not opt_results.empty else None,
            'test_performance': {
                'total_trades': len(test_result.trades),
                'net_profit': test_result.metrics['net_profit'],
                'roi': test_result.metrics['roi'],
                'sharpe_ratio': test_result.metrics['sharpe_ratio'],
                'max_drawdown': test_result.metrics['max_drawdown'],
                'win_rate': test_result.metrics['win_rate'],
                'profit_factor': test_result.metrics['profit_factor'],
            } if test_result is not None else None,
            'top_parameters': top_params.to_dict(orient='records') if not top_params.empty else []
        }
        
        # Save summary
        with open(results_path / "optimization_summary.json", "w") as f:
            json.dump(summary, f, indent=4)
            
        self.logger.info(f"Optimization and testing completed successfully")
        self.logger.info(f"Results saved to {results_path}")
        
        return summary
    
    def walk_forward_analysis(self,
                           parameter_space: Dict[str, List],
                           start_date: datetime,
                           end_date: datetime,
                           window_size: int = 360,  # days
                           test_size: int = 180,   # days
                           step_size: int = 180,    # days
                           save_results: bool = True) -> Dict[str, Any]:
        """
        Perform walk-forward analysis with rolling optimization
        
        Args:
            parameter_space: Dictionary of parameters to optimize with lists of values
            start_date: Overall start date
            end_date: Overall end date
            window_size: Size of sliding window in days
            test_size: Size of out-of-sample test window in days
            step_size: Step size for sliding window in days
            save_results: Whether to save results to files
            
        Returns:
            Dictionary with walk-forward results
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{self.strategy.name}_wfa_{timestamp}"
        
        self.logger.info(f"Starting walk-forward analysis for {self.strategy.name}")
        self.logger.info(f"Run ID: {run_id}")
        
        # Create output directory
        if save_results:
            results_path = self.output_dir / run_id
            results_path.mkdir(parents=True, exist_ok=True)
            
        # Generate window dates
        current_date = start_date
        windows = []
        
        while current_date + timedelta(days=window_size + test_size) <= end_date:
            train_start = current_date
            train_end = current_date + timedelta(days=window_size)
            test_start = train_end
            test_end = test_start + timedelta(days=test_size)
            
            windows.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })
            
            current_date += timedelta(days=step_size)
            
        self.logger.info(f"Created {len(windows)} windows for walk-forward analysis")
        
        # Run optimization and testing for each window
        window_results = []
        combined_test_data = []
        all_params = []
        
        for i, window in enumerate(windows):
            self.logger.info(f"Processing window {i+1}/{len(windows)}")
            
            # Define train and test periods
            train_period = (window['train_start'], window['train_end'])
            test_period = (window['test_start'], window['test_end'])
            
            # Run optimization and test
            result = self.optimize_and_test(
                parameter_space=parameter_space,
                train_period=train_period,
                test_period=test_period,
                n_trials=1,  # Lower for walk-forward
                parallel=True
            )
            
            # Extract test performance
            if result['success'] and result['test_performance'] is not None:
                # Add window info to result
                result['window'] = {
                    'index': i,
                    'train_start': window['train_start'].strftime('%Y-%m-%d'),
                    'train_end': window['train_end'].strftime('%Y-%m-%d'),
                    'test_start': window['test_start'].strftime('%Y-%m-%d'),
                    'test_end': window['test_end'].strftime('%Y-%m-%d')
                }
                
                window_results.append(result)
                
                # Add to combined test data
                test_start = window['test_start']
                test_end = window['test_end']
                
                # Filter data for test period
                test_data = self.data.loc[test_start:test_end].copy()
                
                # Set strategy parameters
                self.strategy.set_parameters(result['best_parameters'])
                
                # Create backtester
                test_backtester = Backtester(
                    data=test_data,
                    strategy=self.strategy,
                    initial_capital=self.initial_capital,
                    commission=self.commission,
                    slippage=self.slippage,
                    position_size=self.position_size
                )
                
                # Run backtest
                test_result = test_backtester.run()
                
                if test_result is not None and test_result.equity_curve is not None:
                    # Add equity curve to combined data
                    equity_curve = test_result.equity_curve.copy()
                    equity_curve['window'] = i
                    combined_test_data.append(equity_curve)
                    
                # Save parameters
                all_params.append({
                    'window': i,
                    'test_start': window['test_start'].strftime('%Y-%m-%d'),
                    'test_end': window['test_end'].strftime('%Y-%m-%d'),
                    'parameters': result['best_parameters'],
                    'test_performance': result['test_performance']
                })
        
        # Combine test equity curves
        if combined_test_data:
            combined_equity = pd.concat(combined_test_data)
            
            # Calculate combined statistics
            if not combined_equity.empty:
                equity_series = combined_equity['equity']
                
                # Calculate returns
                returns = equity_series.pct_change().dropna()
                
                # Calculate metrics
                total_return = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1
                annual_return = ((1 + total_return) ** (252 / len(returns))) - 1 if len(returns) > 0 else 0
                sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
                
                # Calculate drawdowns
                drawdown_df = self.drawdown_analyzer.calculate_drawdowns(equity_series)
                max_drawdown = abs(drawdown_df['drawdown_pct'].min())
                
                combined_metrics = {
                    'total_return': total_return,
                    'annual_return': annual_return,
                    'sharpe_ratio': sharpe_ratio,
                    'max_drawdown': max_drawdown,
                    'win_rate': np.mean(returns > 0)
                }
            else:
                combined_metrics = None
        else:
            combined_equity = None
            combined_metrics = None
            
        # Create parameter stability analysis
        param_stability = {}
        for param in parameter_space.keys():
            param_values = [p['parameters'][param] for p in all_params if param in p['parameters']]
            param_stability[param] = {
                'values': param_values,
                'mean': np.mean(param_values) if param_values else None,
                'std': np.std(param_values) if param_values else None,
                'min': min(param_values) if param_values else None,
                'max': max(param_values) if param_values else None
            }
            
        # Create summary of results
        summary = {
            'success': len(window_results) > 0,
            'run_id': run_id,
            'strategy_name': self.strategy.name,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'window_size': window_size,
            'test_size': test_size,
            'step_size': step_size,
            'windows': len(windows),
            'successful_windows': len(window_results),
            'combined_metrics': combined_metrics,
            'parameter_stability': param_stability,
            'window_results': window_results
        }
        
        # Save results
        if save_results:
            # Save summary
            with open(results_path / "wfa_summary.json", "w") as f:
                json.dump(summary, f, indent=4)
                
            # Save parameter history
            param_history_df = pd.DataFrame(all_params)
            if not param_history_df.empty:
                param_history_df.to_csv(results_path / "parameter_history.csv", index=False)
                
            # Save combined equity curve
            if combined_equity is not None and not combined_equity.empty:
                combined_equity.to_csv(results_path / "combined_equity.csv")
                
                # Create visualization of combined equity
                plt.figure(figsize=(12, 8))
                
                # Plot equity curve
                plt.plot(combined_equity.index, combined_equity['equity'], linewidth=2)
                
                # Add vertical lines for window boundaries
                window_boundaries = [w['test_start'] for w in windows[1:]]
                for boundary in window_boundaries:
                    plt.axvline(boundary, color='gray', linestyle='--', alpha=0.7)
                    
                plt.title(f"Walk-Forward Analysis: Combined Equity Curve")
                plt.xlabel("Date")
                plt.ylabel("Equity")
                plt.grid(True)
                
                # Save figure
                plt.savefig(results_path / "combined_equity.png", dpi=150)
                
        self.logger.info("Walk-forward analysis completed successfully")
        
        return summary


def main():
    """Main function for command line interface"""
    parser = argparse.ArgumentParser(description="Comprehensive Backtesting Tool")
    
    # Required arguments
    parser.add_argument("--data", type=str, required=True,
                      help="Path to data file (CSV)")
    parser.add_argument("--strategy", type=str, required=True,
                      help="Strategy module:class to use (e.g. src.strategies.trend:TrendStrategy)")
    
    # Optional arguments
    parser.add_argument("--start-date", type=str, default=None,
                      help="Start date for backtest (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None,
                      help="End date for backtest (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=10000.0,
                      help="Initial capital")
    parser.add_argument("--commission", type=float, default=0.0,
                      help="Commission per trade (percentage)")
    parser.add_argument("--slippage", type=float, default=0.0,
                      help="Slippage per trade (percentage)")
    parser.add_argument("--position-size", type=float, default=1.0,
                      help="Position size as percentage of capital (0-1)")
    parser.add_argument("--params", type=str, default=None,
                      help="JSON file with strategy parameters")
    parser.add_argument("--output-dir", type=str, default="results/backtests",
                      help="Directory for output files")
    parser.add_argument("--mc-iterations", type=int, default=1000,
                      help="Number of Monte Carlo iterations")
    parser.add_argument("--market-data", type=str, default=None,
                      help="Path to market data file for benchmark comparison")
    parser.add_argument("--log-level", type=str, default="INFO",
                      choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                      help="Logging level")
    
    args = parser.parse_args()
    
    # Setup logger
    logger = setup_logger(level=args.log_level)
    
    # Load data
    logger.info(f"Loading data from {args.data}")
    data = pd.read_csv(args.data, index_col=0, parse_dates=True)
    logger.info(f"Loaded {len(data)} data points")
    
    # Load strategy
    logger.info(f"Loading strategy {args.strategy}")
    try:
        module_name, class_name = args.strategy.split(":")
        import importlib
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        strategy = strategy_class()
    except (ValueError, ImportError, AttributeError) as e:
        logger.error(f"Error loading strategy: {e}")
        return
    
    # Load parameters if provided
    if args.params:
        logger.info(f"Loading parameters from {args.params}")
        try:
            with open(args.params, "r") as f:
                params = json.load(f)
            strategy.set_parameters(params)
        except Exception as e:
            logger.error(f"Error loading parameters: {e}")
            return
    
    # Load market data if provided
    market_data = None
    if args.market_data:
        logger.info(f"Loading market data from {args.market_data}")
        try:
            market_data = pd.read_csv(args.market_data, index_col=0, parse_dates=True)
            logger.info(f"Loaded {len(market_data)} market data points")
        except Exception as e:
            logger.error(f"Error loading market data: {e}")
    
    # Create comprehensive backtester
    backtester = ComprehensiveBacktest(
        strategy=strategy,
        data=data,
        initial_capital=args.capital,
        commission=args.commission,
        slippage=args.slippage,
        position_size=args.position_size,
        output_dir=args.output_dir,
        log_level=args.log_level
    )
    
    # Parse dates
    start_date = pd.to_datetime(args.start_date) if args.start_date else None
    end_date = pd.to_datetime(args.end_date) if args.end_date else None
    
    # Run analysis
    results = backtester.run_full_analysis(
        start_date=start_date,
        end_date=end_date,
        mc_iterations=args.mc_iterations,
        save_results=True,
        save_figures=True,
        market_data=market_data
    )
    
    # Print summary
    if results['success']:
        logger.info("Backtest completed successfully")
        logger.info(f"Strategy: {results['strategy_name']}")
        logger.info(f"Period: {results['start_date']} to {results['end_date']}")
        logger.info(f"Net profit: ${results['net_profit']:.2f} ({results['roi']*100:.2f}%)")
        logger.info(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
        logger.info(f"Max drawdown: {results['max_drawdown']*100:.2f}%")
        logger.info(f"Win rate: {results['win_rate']*100:.2f}%")
    else:
        logger.error("Backtest failed")
        logger.error(results.get('error', 'Unknown error'))


if __name__ == "__main__":
    main()
