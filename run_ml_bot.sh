#!/bin/bash
# run_ml_bot.sh - Script to run IQ-720 Trading Bot with ML capabilities

set -e

echo "Starting IQ-720 Trading Bot with ML capabilities..."

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
if [ ! -d "venv-ml" ]; then
    echo "Creating virtual environment for ML..."
    python -m venv venv-ml
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment. Please install venv package and try again."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating ML virtual environment..."
source venv-ml/bin/activate

# Install ML requirements
echo "Installing ML requirements (this might take a while)..."
pip install -r requirements.txt

# Create an ML-enabled config file if it doesn't exist
if [ ! -f "config_ml.yaml" ]; then
    echo "Creating ML-enabled config.yaml file..."
    cat > config_ml.yaml << EOF
# IQ-720 Trading Bot Configuration with ML

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

# ML settings
use_ml: true
ml:
  model_path: models/ensemble_model
  confidence_threshold: 0.7
  use_ensemble: true
  models:
    - name: random_forest
      enabled: true
    - name: xgboost
      enabled: true
    - name: lightgbm
      enabled: true
    - name: lstm
      enabled: false  # Deep learning models require more data
EOF
    echo "Created ML-enabled config_ml.yaml file."
fi

# Run the bot with ML capabilities
echo "Running the bot with ML capabilities..."
python -m src.main_updated --config config_ml.yaml

echo "Bot started successfully. Check the terminal output and Telegram for signals."

# Deactivate virtual environment when done
# Comment this out if you want to keep the environment active
# deactivate
