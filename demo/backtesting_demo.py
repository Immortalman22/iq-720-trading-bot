#!/usr/bin/env python3
"""
Backtesting Framework Demo
Demonstrates how to use the comprehensive backtesting framework
"""
import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.utils.logger import setup_logger
from src.backtesting.comprehensive_backtest import ComprehensiveBacktest
from src.backtesting.strategy import TradingStrategy


class SimpleMovingAverageStrategy(TradingStrategy):
    """
    Simple Moving Average Crossover Strategy
    
    This strategy generates buy signals when the fast moving average crosses above
    the slow moving average, and sell signals when the fast moving average crosses
    below the slow moving average.
    """
    
    def __init__(self, fast_ma=20, slow_ma=50):
        """Initialize with default parameters"""
        self.name = "SimpleMovingAverageStrategy"
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        
    def set_parameters(self, parameters):
        """Set strategy parameters"""
        if 'fast_ma' in parameters:
            self.fast_ma = parameters['fast_ma']
        if 'slow_ma' in parameters:
            self.slow_ma = parameters['slow_ma']
            
    def get_parameters(self):
        """Get strategy parameters"""
        return {
            'fast_ma': self.fast_ma,
            'slow_ma': self.slow_ma
        }
            
    def generate_signals(self, data):
        """
        Generate trading signals
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Series with trading signals (1 for buy, -1 for sell, 0 for no action)
        """
        if len(data) < self.slow_ma:
            return pd.Series(0, index=data.index)
            
        # Calculate moving averages
        fast_ma = data['close'].rolling(self.fast_ma).mean()
        slow_ma = data['close'].rolling(self.slow_ma).mean()
        
        # Initialize signals
        signals = pd.Series(0, index=data.index)
        
        # Generate signals
        signals[(fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))] = 1  # Buy
        signals[(fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))] = -1  # Sell
        
        return signals
        
    def get_stop_loss(self, data, direction):
        """
        Generate stop loss for new positions
        
        Args:
            data: DataFrame with OHLCV data
            direction: "LONG" or "SHORT"
            
        Returns:
            Stop loss price or None
        """
        # Use a simple ATR-based stop loss
        if 'atr' in data.columns:
            atr = data['atr'].iloc[-1]
            current_price = data['close'].iloc[-1]
            
            if direction == "LONG":
                return current_price - 3 * atr
            else:
                return current_price + 3 * atr
        
        # Fallback to a fixed percentage stop loss
        current_price = data['close'].iloc[-1]
        if direction == "LONG":
            return current_price * 0.95  # 5% stop loss
        else:
            return current_price * 1.05  # 5% stop loss
            
    def get_take_profit(self, data, direction):
        """
        Generate take profit for new positions
        
        Args:
            data: DataFrame with OHLCV data
            direction: "LONG" or "SHORT"
            
        Returns:
            Take profit price or None
        """
        # Use a simple ATR-based take profit
        if 'atr' in data.columns:
            atr = data['atr'].iloc[-1]
            current_price = data['close'].iloc[-1]
            
            if direction == "LONG":
                return current_price + 5 * atr
            else:
                return current_price - 5 * atr
        
        # Fallback to a fixed percentage take profit
        current_price = data['close'].iloc[-1]
        if direction == "LONG":
            return current_price * 1.10  # 10% take profit
        else:
            return current_price * 0.90  # 10% take profit


def fetch_demo_data():
    """
    Fetch demo data or use built-in data
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        # Try to use yfinance to get real data
        import yfinance as yf
        print("Downloading sample data from Yahoo Finance...")
        
        # Download EURUSD data
        data = yf.download(
            "EURUSD=X",
            start="2018-01-01",
            end="2023-01-01",
            interval="1d",
            progress=False
        )
        
        # Rename columns
        data.columns = [c.lower() for c in data.columns]
        
        # Calculate some basic indicators
        data['returns'] = data['close'].pct_change()
        data['volatility'] = data['returns'].rolling(20).std()
        data['atr'] = data['high'].rolling(14).max() - data['low'].rolling(14).min()
        
        print(f"Downloaded {len(data)} data points")
        return data
        
    except (ImportError, Exception) as e:
        print(f"Error fetching data from Yahoo Finance: {e}")
        print("Generating synthetic data instead...")
        
        # Generate synthetic data
        start_date = datetime(2018, 1, 1)
        end_date = datetime(2023, 1, 1)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Create DataFrame
        import numpy as np
        n = len(dates)
        close = 1.2 + np.cumsum(np.random.normal(0, 0.005, n))
        high = close + np.random.uniform(0, 0.01, n)
        low = close - np.random.uniform(0, 0.01, n)
        open_price = low + np.random.uniform(0, 0.01, n) * (high - low)
        volume = np.random.uniform(1000, 5000, n)
        
        data = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'returns': pd.Series(close).pct_change(),
        }, index=dates)
        
        # Calculate indicators
        data['volatility'] = data['returns'].rolling(20).std()
        data['atr'] = data['high'].rolling(14).max() - data['low'].rolling(14).min()
        
        print(f"Generated {len(data)} synthetic data points")
        return data


def run_demo():
    """Run the backtesting framework demo"""
    logger = setup_logger(level="INFO")
    
    # Get data
    data = fetch_demo_data()
    
    # Create strategy
    strategy = SimpleMovingAverageStrategy(fast_ma=20, slow_ma=50)
    
    # Create backtester
    backtester = ComprehensiveBacktest(
        strategy=strategy,
        data=data,
        initial_capital=10000.0,
        commission=0.0001,  # 1 pip commission
        slippage=0.0001,    # 1 pip slippage
        position_size=0.1,  # 10% of capital per trade
        output_dir="results/backtests",
        log_level="INFO"
    )
    
    print("\n" + "="*80)
    print("DEMO 1: Running Basic Comprehensive Backtest")
    print("="*80)
    
    # Run basic backtest
    results = backtester.run_full_analysis(
        start_date=data.index[100],  # Start after warmup period
        end_date=data.index[-1],
        mc_iterations=500,  # Lower for demo
        save_results=True,
        save_figures=True
    )
    
    # Print summary
    if results['success']:
        print("\nBacktest Results:")
        print(f"Net profit: ${results['net_profit']:.2f} ({results['roi']*100:.2f}%)")
        print(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
        print(f"Max drawdown: {results['max_drawdown']*100:.2f}%")
        print(f"Win rate: {results['win_rate']*100:.2f}%")
        print(f"Total trades: {results['total_trades']}")
    
    print("\n" + "="*80)
    print("DEMO 2: Running Parameter Optimization")
    print("="*80)
    
    # Define parameter space
    parameter_space = {
        'fast_ma': [5, 10, 15, 20, 25],
        'slow_ma': [30, 40, 50, 60]
    }
    
    # Define train and test periods
    train_start = data.index[100]  # Start after warmup period
    train_end = data.index[int(len(data) * 0.7)]  # 70% for training
    test_start = train_end
    test_end = data.index[-1]
    
    # Run optimization
    opt_results = backtester.optimize_and_test(
        parameter_space=parameter_space,
        train_period=(train_start, train_end),
        test_period=(test_start, test_end),
        n_trials=1,  # Low for demo
        parallel=True
    )
    
    # Print summary
    if opt_results['success']:
        print("\nOptimization Results:")
        print(f"Best parameters: {opt_results['best_parameters']}")
        print("\nTraining Performance:")
        if opt_results['train_performance']:
            print(f"Sharpe ratio: {opt_results['train_performance']['sharpe_ratio']:.2f}")
            print(f"Net profit: ${opt_results['train_performance']['net_profit']:.2f}")
        print("\nTest Performance:")
        if opt_results['test_performance']:
            print(f"Sharpe ratio: {opt_results['test_performance']['sharpe_ratio']:.2f}")
            print(f"Net profit: ${opt_results['test_performance']['net_profit']:.2f}")
            print(f"Win rate: {opt_results['test_performance']['win_rate']*100:.2f}%")
            print(f"Total trades: {opt_results['test_performance']['total_trades']}")
    
    print("\n" + "="*80)
    print("DEMO 3: Running Walk-Forward Analysis")
    print("="*80)
    
    # Define smaller parameter space for speed
    parameter_space = {
        'fast_ma': [10, 20],
        'slow_ma': [40, 60]
    }
    
    # Run walk-forward analysis with reduced windows for demo
    wfa_results = backtester.walk_forward_analysis(
        parameter_space=parameter_space,
        start_date=data.index[100],  # Start after warmup period
        end_date=data.index[-1],
        window_size=180,  # 6 months
        test_size=90,    # 3 months
        step_size=90,    # 3 months
        save_results=True
    )
    
    # Print summary
    if wfa_results['success']:
        print("\nWalk-Forward Analysis Results:")
        print(f"Windows analyzed: {wfa_results['windows']}")
        print(f"Successful windows: {wfa_results['successful_windows']}")
        
        if wfa_results['combined_metrics']:
            print("\nCombined Test Performance:")
            print(f"Total return: {wfa_results['combined_metrics']['total_return']*100:.2f}%")
            print(f"Annual return: {wfa_results['combined_metrics']['annual_return']*100:.2f}%")
            print(f"Sharpe ratio: {wfa_results['combined_metrics']['sharpe_ratio']:.2f}")
            print(f"Max drawdown: {wfa_results['combined_metrics']['max_drawdown']*100:.2f}%")
        
        print("\nParameter Stability:")
        for param, stats in wfa_results['parameter_stability'].items():
            if stats['mean'] is not None:
                print(f"{param}: mean={stats['mean']:.1f}, std={stats['std']:.1f}, range=[{stats['min']}, {stats['max']}]")
    
    print("\n" + "="*80)
    print("DEMO COMPLETED")
    print("="*80)
    print("\nCheck the 'results/backtests' directory for detailed reports and visualizations.")


if __name__ == "__main__":
    run_demo()
