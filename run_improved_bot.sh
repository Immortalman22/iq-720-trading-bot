#!/bin/bash

# Script to run the improved version of the IQ 720 Trading Bot
# This script ensures all dependencies are installed and runs the enhanced version

echo "🤖 Starting IQ 720 Improved Trading Bot..."

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs models

# Run the improved bot
echo "Starting the improved trading bot in analysis mode..."
python src/main_enhanced_improved.py

# Deactivate virtual environment on exit
deactivate
