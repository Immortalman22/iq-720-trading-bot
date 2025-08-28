#!/bin/bash

# Performance Analyzer Script
# This script runs the performance analyzer on trading logs

echo "Starting performance analysis for the trading bot..."

# Ensure we have the necessary Python environment
if [ -f "/workspaces/iq-720-trading-bot/venv/bin/activate" ]; then
    source /workspaces/iq-720-trading-bot/venv/bin/activate
    echo "Virtual environment activated."
else
    echo "Virtual environment not found. Please run setup first."
    exit 1
fi

# Default log file
LOG_FILE="logs/trading.log"
OUTPUT_DIR="analysis_results"

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -l|--log-file) LOG_FILE="$2"; shift ;;
        -o|--output-dir) OUTPUT_DIR="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo "Using log file: $LOG_FILE"
echo "Output directory: $OUTPUT_DIR"

# Run the performance analyzer
python /workspaces/iq-720-trading-bot/src/utils/performance_analyzer.py --log-file "$LOG_FILE" --output-dir "$OUTPUT_DIR"

# Check if analysis was successful
if [ $? -eq 0 ]; then
    echo "Performance analysis completed successfully."
    echo "Results are available in the $OUTPUT_DIR directory."
    
    # Try to open the HTML report if browser environment variable is set
    if [ -n "$BROWSER" ] && [ -f "$OUTPUT_DIR/performance_analysis_report.html" ]; then
        echo "Opening performance report in browser..."
        "$BROWSER" "$OUTPUT_DIR/performance_analysis_report.html"
    else
        echo "Report generated at: $OUTPUT_DIR/performance_analysis_report.html"
    fi
else
    echo "Performance analysis failed. Check the error logs for details."
    exit 1
fi

echo "Analysis process completed."
