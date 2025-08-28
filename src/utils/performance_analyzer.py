#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Performance Analysis Tool for IQ-720 Trading Bot

This script analyzes the logs and performance metrics of the improved trading bot,
providing insights and visualizations to help understand its performance.
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import re
import argparse
import numpy as np
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Configure matplotlib for better visualizations
plt.style.use('ggplot')
sns.set_theme(style="whitegrid")


class BotPerformanceAnalyzer:
    """Analyzes trading bot performance based on log files and trade data."""

    def __init__(self, log_file='logs/trading.log', output_dir='analysis_results'):
        """
        Initialize the performance analyzer.
        
        Args:
            log_file (str): Path to the log file
            output_dir (str): Directory to save analysis results
        """
        self.log_file = log_file
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        self.trades_df = None
        self.signals_df = None
        self.market_regimes_df = None
        self.confidence_df = None
        
    def parse_trading_logs(self):
        """Parse trading logs to extract trade data, signals, and performance metrics."""
        print(f"Parsing log file: {self.log_file}")
        
        # Check if log file exists
        if not os.path.exists(self.log_file):
            print(f"Error: Log file {self.log_file} not found")
            return False
            
        # Regular expressions for extracting data
        trade_pattern = r"TRADE: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+Symbol: (\w+/\w+)\s+Action: (BUY|SELL)\s+Price: ([\d\.]+)\s+Size: ([\d\.]+)\s+SL: ([\d\.]+)\s+TP: ([\d\.]+)"
        signal_pattern = r"SIGNAL: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+Symbol: (\w+/\w+)\s+Direction: (BUY|SELL|NEUTRAL)\s+Strength: ([\d\.]+)\s+Confidence: ([\d\.]+)%"
        regime_pattern = r"MARKET REGIME: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+Symbol: (\w+/\w+)\s+Regime: (\w+)\s+Volatility: ([\d\.]+)"
        
        # Initialize empty lists to store data
        trades = []
        signals = []
        regimes = []
        
        # Read log file
        with open(self.log_file, 'r') as f:
            log_content = f.read()
            
        # Extract trades
        for match in re.finditer(trade_pattern, log_content):
            timestamp, symbol, action, price, size, sl, tp = match.groups()
            trades.append({
                'timestamp': pd.to_datetime(timestamp),
                'symbol': symbol,
                'action': action,
                'price': float(price),
                'size': float(size),
                'stop_loss': float(sl),
                'take_profit': float(tp)
            })
            
        # Extract signals
        for match in re.finditer(signal_pattern, log_content):
            timestamp, symbol, direction, strength, confidence = match.groups()
            signals.append({
                'timestamp': pd.to_datetime(timestamp),
                'symbol': symbol,
                'direction': direction,
                'strength': float(strength),
                'confidence': float(confidence)
            })
            
        # Extract market regimes
        for match in re.finditer(regime_pattern, log_content):
            timestamp, symbol, regime, volatility = match.groups()
            regimes.append({
                'timestamp': pd.to_datetime(timestamp),
                'symbol': symbol,
                'regime': regime,
                'volatility': float(volatility)
            })
            
        # Convert to DataFrames
        self.trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        self.signals_df = pd.DataFrame(signals) if signals else pd.DataFrame()
        self.market_regimes_df = pd.DataFrame(regimes) if regimes else pd.DataFrame()
        
        print(f"Extracted {len(self.trades_df)} trades, {len(self.signals_df)} signals, and {len(self.market_regimes_df)} market regime records.")
        return True
    
    def analyze_performance(self):
        """Analyze overall trading performance."""
        if self.trades_df is None or self.trades_df.empty:
            print("No trade data available for analysis")
            return False
            
        print("Analyzing trading performance...")
        
        # Calculate basic statistics
        stats = {
            'total_trades': len(self.trades_df),
            'buy_trades': len(self.trades_df[self.trades_df['action'] == 'BUY']),
            'sell_trades': len(self.trades_df[self.trades_df['action'] == 'SELL']),
            'unique_symbols': self.trades_df['symbol'].nunique(),
            'time_period': f"{self.trades_df['timestamp'].min()} to {self.trades_df['timestamp'].max()}"
        }
        
        print("\nTrading Statistics:")
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Buy Trades: {stats['buy_trades']}")
        print(f"Sell Trades: {stats['sell_trades']}")
        print(f"Unique Symbols: {stats['unique_symbols']}")
        print(f"Time Period: {stats['time_period']}")
        
        return True
        
    def analyze_signal_quality(self):
        """Analyze the quality of trading signals."""
        if self.signals_df is None or self.signals_df.empty:
            print("No signal data available for analysis")
            return False
            
        print("\nAnalyzing signal quality...")
        
        # Calculate signal statistics
        signal_stats = {
            'total_signals': len(self.signals_df),
            'buy_signals': len(self.signals_df[self.signals_df['direction'] == 'BUY']),
            'sell_signals': len(self.signals_df[self.signals_df['direction'] == 'SELL']),
            'neutral_signals': len(self.signals_df[self.signals_df['direction'] == 'NEUTRAL']),
            'avg_confidence': self.signals_df['confidence'].mean(),
            'avg_strength': self.signals_df['strength'].mean()
        }
        
        print("\nSignal Statistics:")
        print(f"Total Signals: {signal_stats['total_signals']}")
        print(f"Buy Signals: {signal_stats['buy_signals']} ({signal_stats['buy_signals']/signal_stats['total_signals']*100:.2f}%)")
        print(f"Sell Signals: {signal_stats['sell_signals']} ({signal_stats['sell_signals']/signal_stats['total_signals']*100:.2f}%)")
        print(f"Neutral Signals: {signal_stats['neutral_signals']} ({signal_stats['neutral_signals']/signal_stats['total_signals']*100:.2f}%)")
        print(f"Average Confidence: {signal_stats['avg_confidence']:.2f}%")
        print(f"Average Strength: {signal_stats['avg_strength']:.2f}")
        
        # Prepare signal confidence distribution visualization
        if len(self.signals_df) > 0:
            plt.figure(figsize=(10, 6))
            sns.histplot(data=self.signals_df, x='confidence', hue='direction', bins=20, kde=True)
            plt.title('Signal Confidence Distribution by Direction')
            plt.xlabel('Confidence (%)')
            plt.ylabel('Frequency')
            plt.savefig(f"{self.output_dir}/signal_confidence_distribution.png")
            plt.close()
            print(f"Signal confidence distribution chart saved to {self.output_dir}/signal_confidence_distribution.png")
            
        return True
        
    def analyze_market_regimes(self):
        """Analyze market regimes and their impact on trading."""
        if self.market_regimes_df is None or self.market_regimes_df.empty:
            print("No market regime data available for analysis")
            return False
            
        print("\nAnalyzing market regimes...")
        
        # Calculate regime statistics
        regime_counts = self.market_regimes_df['regime'].value_counts()
        regime_volatility = self.market_regimes_df.groupby('regime')['volatility'].mean().sort_values(ascending=False)
        
        print("\nMarket Regime Statistics:")
        for regime, count in regime_counts.items():
            print(f"{regime}: {count} instances ({count/len(self.market_regimes_df)*100:.2f}%), " +
                  f"Avg Volatility: {regime_volatility.get(regime, 0):.4f}")
                  
        # Prepare market regime visualization
        if len(self.market_regimes_df) > 0:
            plt.figure(figsize=(10, 6))
            sns.countplot(data=self.market_regimes_df, x='regime', order=regime_counts.index)
            plt.title('Market Regime Distribution')
            plt.xlabel('Regime Type')
            plt.ylabel('Frequency')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/market_regime_distribution.png")
            plt.close()
            print(f"Market regime distribution chart saved to {self.output_dir}/market_regime_distribution.png")
            
            # Volatility by regime
            plt.figure(figsize=(10, 6))
            sns.boxplot(data=self.market_regimes_df, x='regime', y='volatility')
            plt.title('Volatility by Market Regime')
            plt.xlabel('Regime Type')
            plt.ylabel('Volatility')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/volatility_by_regime.png")
            plt.close()
            print(f"Volatility by regime chart saved to {self.output_dir}/volatility_by_regime.png")
            
        return True
        
    def generate_html_report(self):
        """Generate an HTML report of the analysis results."""
        if not (self.trades_df is not None or self.signals_df is not None or self.market_regimes_df is not None):
            print("No data available for report generation")
            return False
            
        print("\nGenerating HTML report...")
        
        # Create report HTML
        report_path = f"{self.output_dir}/performance_analysis_report.html"
        with open(report_path, 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>Trading Bot Performance Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }}
        h1, h2, h3 {{ color: #0066cc; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .section {{ margin-bottom: 30px; background: #f9f9f9; padding: 20px; border-radius: 5px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ text-align: left; padding: 12px; }}
        th {{ background-color: #0066cc; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .chart {{ margin: 20px 0; text-align: center; }}
        .chart img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
        .footer {{ margin-top: 30px; text-align: center; font-size: 0.8em; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Trading Bot Performance Analysis Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Log File: {self.log_file}</p>
        
        <div class="section">
            <h2>Summary</h2>
""")

            # Add summary statistics
            if self.trades_df is not None and not self.trades_df.empty:
                f.write(f"""
            <h3>Trading Statistics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Trades</td><td>{len(self.trades_df)}</td></tr>
                <tr><td>Buy Trades</td><td>{len(self.trades_df[self.trades_df['action'] == 'BUY'])}</td></tr>
                <tr><td>Sell Trades</td><td>{len(self.trades_df[self.trades_df['action'] == 'SELL'])}</td></tr>
                <tr><td>Unique Symbols</td><td>{self.trades_df['symbol'].nunique()}</td></tr>
                <tr><td>Time Period</td><td>{self.trades_df['timestamp'].min()} to {self.trades_df['timestamp'].max()}</td></tr>
            </table>
""")

            # Add signal statistics
            if self.signals_df is not None and not self.signals_df.empty:
                total_signals = len(self.signals_df)
                buy_signals = len(self.signals_df[self.signals_df['direction'] == 'BUY'])
                sell_signals = len(self.signals_df[self.signals_df['direction'] == 'SELL'])
                neutral_signals = len(self.signals_df[self.signals_df['direction'] == 'NEUTRAL'])
                
                f.write(f"""
            <h3>Signal Statistics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Signals</td><td>{total_signals}</td></tr>
                <tr><td>Buy Signals</td><td>{buy_signals} ({buy_signals/total_signals*100:.2f}%)</td></tr>
                <tr><td>Sell Signals</td><td>{sell_signals} ({sell_signals/total_signals*100:.2f}%)</td></tr>
                <tr><td>Neutral Signals</td><td>{neutral_signals} ({neutral_signals/total_signals*100:.2f}%)</td></tr>
                <tr><td>Average Confidence</td><td>{self.signals_df['confidence'].mean():.2f}%</td></tr>
                <tr><td>Average Strength</td><td>{self.signals_df['strength'].mean():.2f}</td></tr>
            </table>
""")

            # Add market regime statistics
            if self.market_regimes_df is not None and not self.market_regimes_df.empty:
                regime_counts = self.market_regimes_df['regime'].value_counts()
                regime_volatility = self.market_regimes_df.groupby('regime')['volatility'].mean().sort_values(ascending=False)
                
                f.write(f"""
            <h3>Market Regime Statistics</h3>
            <table>
                <tr><th>Regime</th><th>Count</th><th>Percentage</th><th>Avg Volatility</th></tr>
""")
                for regime, count in regime_counts.items():
                    f.write(f"""
                <tr>
                    <td>{regime}</td>
                    <td>{count}</td>
                    <td>{count/len(self.market_regimes_df)*100:.2f}%</td>
                    <td>{regime_volatility.get(regime, 0):.4f}</td>
                </tr>
""")
                f.write("""
            </table>
""")

            # Add visualizations
            f.write("""
        </div>
        
        <div class="section">
            <h2>Visualizations</h2>
""")

            # Check if visualization files exist and add them to the report
            signal_chart = f"{self.output_dir}/signal_confidence_distribution.png"
            if os.path.exists(signal_chart):
                f.write(f"""
            <div class="chart">
                <h3>Signal Confidence Distribution</h3>
                <img src="{os.path.basename(signal_chart)}" alt="Signal Confidence Distribution">
            </div>
""")

            regime_chart = f"{self.output_dir}/market_regime_distribution.png"
            if os.path.exists(regime_chart):
                f.write(f"""
            <div class="chart">
                <h3>Market Regime Distribution</h3>
                <img src="{os.path.basename(regime_chart)}" alt="Market Regime Distribution">
            </div>
""")

            volatility_chart = f"{self.output_dir}/volatility_by_regime.png"
            if os.path.exists(volatility_chart):
                f.write(f"""
            <div class="chart">
                <h3>Volatility by Market Regime</h3>
                <img src="{os.path.basename(volatility_chart)}" alt="Volatility by Market Regime">
            </div>
""")

            # Close HTML
            f.write("""
        </div>
        
        <div class="footer">
            <p>IQ-720 Trading Bot Performance Analysis Tool</p>
        </div>
    </div>
</body>
</html>
""")

        print(f"HTML report generated: {report_path}")
        return True

    def run_analysis(self):
        """Run the complete analysis process."""
        if self.parse_trading_logs():
            self.analyze_performance()
            self.analyze_signal_quality()
            self.analyze_market_regimes()
            self.generate_html_report()
            print(f"\nAnalysis complete. Results saved to {self.output_dir}/")
            return True
        return False


def main():
    """Main function to run the performance analyzer."""
    parser = argparse.ArgumentParser(description='Trading Bot Performance Analyzer')
    parser.add_argument('-l', '--log-file', default='logs/trading.log',
                        help='Path to the trading log file (default: logs/trading.log)')
    parser.add_argument('-o', '--output-dir', default='analysis_results',
                        help='Directory to save analysis results (default: analysis_results)')
    args = parser.parse_args()

    analyzer = BotPerformanceAnalyzer(log_file=args.log_file, output_dir=args.output_dir)
    analyzer.run_analysis()


if __name__ == "__main__":
    main()
