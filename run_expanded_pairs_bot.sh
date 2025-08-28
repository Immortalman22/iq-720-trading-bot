#!/bin/bash

# Enhanced Trading Bot Runner with Expanded Pairs
# This script runs the improved trading bot with expanded pair analysis

echo "Starting IQ 720 Enhanced Trading Bot with Expanded Pairs Analysis..."

# Ensure we have the necessary Python environment
if [ -f "/workspaces/iq-720-trading-bot/venv/bin/activate" ]; then
    source /workspaces/iq-720-trading-bot/venv/bin/activate
    echo "Virtual environment activated."
else
    echo "Virtual environment not found. Creating new environment..."
    python -m venv venv
    source /workspaces/iq-720-trading-bot/venv/bin/activate
    
    # Install required packages
    pip install -r requirements.txt
    pip install pyyaml
    echo "Environment created and dependencies installed."
fi

# Ensure config file exists
if [ ! -f "config.yaml" ] && [ -f "config.yaml.example" ]; then
    echo "Config file not found. Creating from example..."
    cp config.yaml.example config.yaml
    echo "Please edit config.yaml with your API credentials and preferences."
    echo "For now, using default configuration with analysis mode enabled."
fi

# Run the bot
echo "Starting the trading bot..."
python -m src.main_enhanced_improved

# Check exit status
if [ $? -eq 0 ]; then
    echo "Bot exited successfully."
else
    echo "Bot exited with an error. Check logs for details."
fi
