#!/bin/bash
# run_basic_bot.sh - Script to run IQ-720 Trading Bot without ML dependencies

set -e

echo "Starting IQ-720 Trading Bot in basic mode (without ML)..."

# Check if Python is installed and available
if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found. Please install Python 3.7+ and try again."
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "ERROR: pip not found. Please install pip and try again."
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment. Please install venv package and try again."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install basic requirements (without ML dependencies)
echo "Installing basic requirements..."
pip install requests pandas numpy python-dotenv pyyaml

# Check if .env file exists, create template if not
if [ ! -f ".env" ]; then
    echo "Creating template .env file..."
    cat > .env << EOF
# IQ-720 Trading Bot Environment Variables
# Replace these values with your actual credentials

# Telegram Bot credentials
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# API credentials for data source
API_KEY=your_api_key
API_SECRET=your_api_secret
EOF
    echo "Please edit the .env file with your actual credentials."
fi

# Create a basic config file if it doesn't exist
if [ ! -f "config.yaml" ]; then
    echo "Creating basic config.yaml file..."
    cat > config.yaml << EOF
# IQ-720 Trading Bot Configuration

# Telegram notification settings
telegram:
  token: \${TELEGRAM_TOKEN:-your_telegram_bot_token}
  chat_id: \${TELEGRAM_CHAT_ID:-your_telegram_chat_id}

# Data source API settings
data_source:
  api_key: \${API_KEY:-your_api_key}
  api_secret: \${API_SECRET:-your_api_secret}

# Trading parameters
trading:
  max_positions: 3
  risk_per_trade: 0.02
  default_stop_loss: 0.03
  default_take_profit: 0.06

# ML settings (disabled in basic mode)
use_ml: false
EOF
    echo "Created basic config.yaml file."
fi

# Run the bot in analysis mode (without ML)
echo "Running the bot in analysis mode (no ML)..."
python -m src.main || python -m src.main_updated

echo "Bot started successfully. Check the terminal output and Telegram for signals."

# Deactivate virtual environment when done
# Comment this out if you want to keep the environment active
# deactivate
