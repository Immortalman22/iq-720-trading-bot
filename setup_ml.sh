#!/bin/bash
# Script to install ML dependencies and train ML models

set -e

echo "Installing ML dependencies..."
pip install -r requirements.txt

echo "Creating necessary directories..."
mkdir -p models
mkdir -p logs

echo "Training ML models..."
python src/ml_trainer.py --symbol EURUSD=X --start_date 2019-01-01 --optimize

echo "Running ML demo..."
python demo/ml_trading_demo.py

echo "ML setup completed successfully!"
