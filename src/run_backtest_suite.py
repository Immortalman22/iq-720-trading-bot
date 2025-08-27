#!/usr/bin/env python3
"""
IQ-720 Trading Bot: Comprehensive Backtesting Suite
This script performs extensive backtesting from 2013 to present across multiple currency pairs.
"""
import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add src directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.backtesting.enhanced_backtester import EnhancedBacktester, HistoricalDataManager, BacktestVisualizer
from src.utils.logger import setup_logger
from src.utils.time_logic import TimeLogic
from src.utils.pair_specific_settings import pair_settings
from src.utils.enhanced_signal_generator import enhanced_signal_generator

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="IQ-720 Trading Bot Backtesting Suite")
    
    parser.add_argument(
        "--pairs", 
        type=str, 
        nargs="+", 
        default=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"],
        help="Currency pairs to test (e.g. EURUSD GBPUSD)"
    )
    
    parser.add_argument(
        "--start-date", 
        type=str, 
        default="2013-01-01",
        help="Start date for backtesting (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--end-date", 
        type=str, 
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date for backtesting (YYYY-MM-DD)"
    )
    
    parser.add_argument(
        "--timeframe", 
        type=str, 
        default="H1",
        choices=["M5", "M15", "M30", "H1", "H4", "D1"],
        help="Timeframe for backtesting"
    )
    
    parser.add_argument(
        "--monte-carlo", 
        action="store_true",
        help="Run Monte Carlo simulations"
    )
    
    parser.add_argument(
        "--walk-forward", 
        action="store_true",
        help="Run walk-forward optimization"
    )
    
    parser.add_argument(
        "--optimize", 
        action="store_true",
        help="Run parameter optimization"
    )
    
    parser.add_argument(
        "--initial-balance", 
        type=float, 
        default=10000,
        help="Initial balance for backtesting"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="data/backtest_results",
        help="Directory to save results"
    )
    
    return parser.parse_args()

def print_section(title):
    """Print a section heading"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def print_metrics(metrics):
    """Print performance metrics in a formatted way"""
    print("\nPERFORMANCE METRICS")
    print("-" * 50)
    print(f"Total Trades: {metrics.get('total_trades', 0)}")
    print(f"Win Rate: {metrics.get('win_rate', 0):.2%}")
    print(f"Profit Factor: {metrics.get('profit_factor', 0):.2f}")
    print(f"Expected Payoff: {metrics.get('expected_payoff', 0):.2f}")
    print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}")
    print(f"Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
    print(f"Calmar Ratio: {metrics.get('calmar_ratio', 0):.2f}")
    print("-" * 50)

def print_pair_performance(pair_performance):
    """Print performance by pair in a formatted way"""
    print("\nPERFORMANCE BY PAIR")
    print("-" * 70)
    print(f"{'PAIR':<10} {'TRADES':<8} {'WIN RATE':<10} {'PROFIT FACTOR':<15} {'EXPECTANCY':<10}")
    print("-" * 70)
    
    for pair, metrics in pair_performance.items():
        print(f"{pair:<10} {metrics.get('total_trades', 0):<8} {metrics.get('win_rate', 0):.2%:<10} "
              f"{metrics.get('profit_factor', 0):.2f:<15} {metrics.get('expected_payoff', 0):.2f:<10}")
    print("-" * 70)

def run_comprehensive_backtest(args):
    """Run a comprehensive backtest based on the provided arguments"""
    # Set up logging
    setup_logger()
    logger = logging.getLogger(__name__)
    
    print_section("IQ-720 Trading Bot: Comprehensive Backtesting Suite")
    
    # Initialize components
    backtester = EnhancedBacktester(data_dir=args.output_dir)
    data_manager = HistoricalDataManager()
    visualizer = BacktestVisualizer(output_dir=args.output_dir)
    
    # Print configuration
    print(f"Currency Pairs: {', '.join(args.pairs)}")
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Initial Balance: ${args.initial_balance:,.2f}")
    print(f"Output Directory: {args.output_dir}")
    
    print_section("Downloading Historical Data")
    
    # Download historical data
    data_dict = data_manager.download_bulk_forex_data(
        pairs=args.pairs,
        start_date=args.start_date,
        end_date=args.end_date,
        timeframe=args.timeframe
    )
    
    if not data_dict:
        logger.error("Failed to download historical data")
        return
        
    print(f"Successfully downloaded data for {len(data_dict)} pairs")
    
    # Run single-pair backtests
    print_section("Running Individual Pair Backtests")
    
    single_results = {}
    
    for pair, data in data_dict.items():
        print(f"\nBacktesting {pair}...")
        
        # Run backtest
        results = backtester.run_backtest(
            data=data,
            start_date=args.start_date,
            end_date=args.end_date,
            config={
                'pair': pair,
                'initial_balance': args.initial_balance
            }
        )
        
        # Print metrics
        print(f"Completed backtest for {pair} with {len(results['trades'])} trades")
        print_metrics(results['metrics'])
        
        # Save results
        backtester.save_results(f"{pair}_backtest", results)
        
        # Create visualizations
        visualizer.create_performance_dashboard(results, f"{pair}_dashboard.png")
        visualizer.create_trade_analysis_report(results, f"{pair}_analysis.png")
        
        # Store results for later
        single_results[pair] = results
    
    # Run multi-pair backtest
    print_section("Running Multi-Pair Backtest")
    
    multi_results = backtester.run_backtest(
        data=data_dict,
        start_date=args.start_date,
        end_date=args.end_date,
        config={
            'initial_balance': args.initial_balance
        }
    )
    
    # Print metrics
    print(f"Completed multi-pair backtest with {len(multi_results['trades'])} trades")
    print_metrics(multi_results['metrics'])
    print_pair_performance(multi_results['pair_performance'])
    
    # Save results
    backtester.save_results("multi_pair_backtest", multi_results)
    
    # Create visualizations
    visualizer.create_performance_dashboard(multi_results, "multi_pair_dashboard.png")
    visualizer.create_trade_analysis_report(multi_results, "multi_pair_analysis.png")
    
    # Run Monte Carlo simulations if requested
    if args.monte_carlo:
        print_section("Running Monte Carlo Simulations")
        
        mc_results = backtester.monte_carlo_analysis(n_simulations=1000)
        
        # Print results
        print("Monte Carlo Analysis Results:")
        print(f"Win Probability: {mc_results['win_probability']:.2%}")
        print(f"Average Final Balance: ${mc_results['final_balance']['mean']:,.2f}")
        print(f"Worst 5% Final Balance: ${mc_results['final_balance']['worst_5pct']:,.2f}")
        print(f"Average Max Drawdown: {mc_results['max_drawdown']['mean']:.2f}%")
        print(f"Worst 5% Max Drawdown: {mc_results['max_drawdown']['worst_5pct']:.2f}%")
        
        # Create visualization
        visualizer.create_monte_carlo_visualization(mc_results, "monte_carlo_analysis.png")
        
        # Save results
        backtester.save_results("monte_carlo_analysis", mc_results)
    
    # Run walk-forward analysis if requested
    if args.walk_forward:
        print_section("Running Walk-Forward Analysis")
        
        # Use the pair with the best performance for walk-forward analysis
        best_pair = max(single_results.keys(), 
                      key=lambda p: single_results[p]['metrics']['sharpe_ratio'])
        
        print(f"Selected {best_pair} for walk-forward analysis (best Sharpe ratio)")
        
        # Run walk-forward analysis
        wfa_results = backtester.walk_forward_analysis(
            data=data_dict[best_pair],
            window_size=252,  # Approximately 1 year of data
            step_size=63      # Approximately 3 months forward
        )
        
        # Print results
        if 'error' in wfa_results:
            print(f"Error in walk-forward analysis: {wfa_results['error']}")
        else:
            periods = wfa_results['periods']
            print(f"Completed walk-forward analysis with {len(periods)} periods")
            
            # Calculate in-sample vs out-of-sample performance
            is_win_rates = [p['in_sample']['win_rate'] for p in periods]
            os_win_rates = [p['out_sample']['win_rate'] for p in periods]
            
            is_sharpe = [p['in_sample'].get('sharpe_ratio', 0) for p in periods]
            os_sharpe = [p['out_sample'].get('sharpe_ratio', 0) for p in periods]
            
            print(f"Average In-Sample Win Rate: {np.mean(is_win_rates):.2%}")
            print(f"Average Out-of-Sample Win Rate: {np.mean(os_win_rates):.2%}")
            print(f"Average In-Sample Sharpe: {np.mean(is_sharpe):.2f}")
            print(f"Average Out-of-Sample Sharpe: {np.mean(os_sharpe):.2f}")
            
            # Save results
            backtester.save_results("walk_forward_analysis", wfa_results)
    
    # Run parameter optimization if requested
    if args.optimize:
        print_section("Running Parameter Optimization")
        
        # Define parameter grid
        param_grid = {
            'rsi_period': [9, 14, 21],
            'rsi_overbought': [70, 75, 80],
            'rsi_oversold': [20, 25, 30],
            'macd_fast': [8, 12, 16],
            'macd_slow': [21, 26, 30]
        }
        
        # Use the pair with the best performance for optimization
        best_pair = max(single_results.keys(), 
                      key=lambda p: single_results[p]['metrics']['sharpe_ratio'])
        
        print(f"Selected {best_pair} for parameter optimization (best Sharpe ratio)")
        
        # Run optimization
        opt_results = backtester.optimize_parameters(
            data=data_dict[best_pair],
            param_grid=param_grid,
            target_metric='sharpe_ratio'
        )
        
        # Print results
        print("Optimal Parameters:")
        for param, value in opt_results['best_params'].items():
            print(f"  {param}: {value}")
        print(f"Best Sharpe Ratio: {opt_results['best_value']:.2f}")
        
        # Save results
        backtester.save_results("parameter_optimization", opt_results)
    
    print_section("Backtest Suite Completed")
    print(f"All results and visualizations saved to: {args.output_dir}")

if __name__ == "__main__":
    args = parse_arguments()
    run_comprehensive_backtest(args)
