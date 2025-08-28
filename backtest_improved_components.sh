#!/bin/bash

# Backtest Improved Components Script
# This script runs backtesting on the improved trading bot components

echo "Starting backtesting for improved trading components..."

# Ensure we have the necessary Python environment
if [ -f "/workspaces/iq-720-trading-bot/venv/bin/activate" ]; then
    source /workspaces/iq-720-trading-bot/venv/bin/activate
    echo "Virtual environment activated."
else
    echo "Virtual environment not found. Please run setup first."
    exit 1
fi

# Run the backtesting script
python /workspaces/iq-720-trading-bot/test_improved_components.py

# Check if backtesting was successful
if [ $? -eq 0 ]; then
    echo "Backtesting completed successfully."
    echo "Results are available in the logs directory."
else
    echo "Backtesting failed. Check the error logs for details."
    exit 1
fi

# Optional: Generate performance reports
echo "Generating performance reports..."
python << EOF
import sys
sys.path.append('/workspaces/iq-720-trading-bot')
from src.utils.performance_reporter import PerformanceReporter

try:
    reporter = PerformanceReporter(log_file='logs/backtest_improved.log')
    reporter.generate_summary_report(output_file='logs/improved_backtest_summary.html')
    print("Performance report generated: logs/improved_backtest_summary.html")
except Exception as e:
    print(f"Error generating performance report: {e}")
EOF

echo "Backtesting process completed."
