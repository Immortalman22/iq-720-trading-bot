# IQ-720 Trading Bot (Advanced Version)

## About This Project

This repository contains an advanced version of the IQ-720 Trading Bot, addressing critical issues in the original implementation and adding sophisticated trading strategies for improved performance.

## Key Improvements

### 1. Fixed Data Leakage Issues
- Proper time-based feature preparation without lookahead bias
- Corrected train/test split implementation
- Ensured feature engineering is contained within each cross-validation fold

### 2. Enhanced ML Model Calibration
- Implemented probability calibration for more accurate confidence scores
- Added uncertainty quantification to prevent overconfidence
- Reduced model complexity to prevent overfitting

### 3. Improved Market Regime Detection
- More sophisticated detection of market regimes (trend, range, volatility)
- Adaptive parameters based on current market conditions
- Session-aware signal generation (adjusting for Asian/London/NY sessions)
- Support for 25+ trading pairs with session-specific filtering
- Dynamic pair correlation analysis for signal confirmation
- Smart market availability detection (Regular vs OTC markets)

### 4. Better Signal Generation Logic
- Combined traditional and ML signals with proper uncertainty handling
- Adjusted confidence calculations to prevent overconfidence
- Added uncertainty metrics to trading signals

### 5. Enhanced Validation
- Comprehensive model evaluation with proper metrics
- Correlation analysis between confidence and actual performance
- Feature importance tracking for better interpretability

### 6. Advanced Trading Strategies
- Return prediction beyond binary direction
- Adaptive exit strategies with dynamic stop-loss/take-profit
- Position sizing using Kelly Criterion
- Volatility-based risk management
- Trailing stop implementation

### 7. Market Availability Management
- Proper distinction between regular and OTC markets
- Trading hour verification for different market types
- Custom notifications for market availability in Telegram messages

## Running the Bot

The bot can be run in different modes:

### Advanced Mode (Full Features)

Run the bot with all advanced trading strategies including adaptive exits and position sizing:

```bash
# Make the script executable if needed
chmod +x run_advanced_bot.sh

# Run the bot in advanced mode
./run_advanced_bot.sh
```

### ML Mode (With machine learning)

Run the bot with machine learning capabilities:

```bash
# Make the script executable if needed
chmod +x run_ml_bot.sh

# Run the bot in ML mode
./run_ml_bot.sh
```

### Basic Mode (No ML dependencies)

Run the bot without machine learning capabilities - requires minimal dependencies:

```bash
# Make the script executable if needed
chmod +x run_basic_bot.sh

# Run the bot in basic mode
./run_basic_bot.sh
```

### ML-Enhanced Mode (Original)

Run the bot with the original ML capabilities:

```bash
# Make the script executable if needed
chmod +x run_ml_bot.sh

# Run the bot with ML capabilities
./run_ml_bot.sh
```

### Improved ML Mode

Run the bot with the improved ML capabilities:

```bash
# Install required dependencies
pip install -r requirements.txt

# Run the improved version
python src/main_enhanced_improved.py
```

## Testing the Improvements

To evaluate the improved components against the original implementation:

```bash
# Run the testing script
python test_improved_components.py
```

This will:
1. Download historical market data
2. Train the improved ML models
3. Evaluate prediction performance
4. Generate a performance report and visualizations

## Enhanced Machine Learning Capabilities

The improved trading bot addresses critical flaws in the original implementation:

### Original ML Features

- **Ensemble Learning**: Combines multiple models including Random Forest, XGBoost, LightGBM, and deep learning models
- **Deep Learning**: LSTM and CNN architectures for sequence-based pattern recognition
- **Explainable AI**: SHAP values for model interpretability and feature importance analysis
- **Anomaly Detection**: Identifies unusual market conditions and regime changes
- **Advanced Feature Engineering**: 60+ technical features derived from price and volume data

### Improvements in the New Version

- **Fixed Data Leakage**: Proper time-based feature generation without future information
- **Confidence Calibration**: Calibrated probability estimates for more reliable confidence scores
- **Uncertainty Quantification**: Added explicit uncertainty estimation to trading decisions
- **Reduced Overfitting**: More robust cross-validation and feature selection
- **Adaptive Parameters**: Trading parameters that adjust to market conditions
- **Better Integration**: Improved combination of technical and ML signals

## Configuration

The bot can be configured using a `config.yaml` file. Key configuration options:

```yaml
telegram:
  token: "YOUR_TELEGRAM_TOKEN"
  chat_id: "YOUR_TELEGRAM_CHAT_ID"

data_source:
  api_key: "YOUR_API_KEY"
  api_secret: "YOUR_API_SECRET"

trading:
  max_positions: 3
  risk_per_trade: 0.01
  default_stop_loss: 0.02
  default_take_profit: 0.04
  max_daily_trades: 5
  min_signal_interval_minutes: 30

use_ml: true
min_confidence: 0.65

ml:
  model_path: "models/"
  confidence_threshold: 0.65
  use_ensemble: true
  lookback_periods: 100
  sequence_length: 20

news_filter:
  enabled: true
  buffer_minutes: 15
  importance_threshold: "medium"
```

Alternatively, create a `.env` file with your credentials:
```
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
API_KEY=your_api_key
API_SECRET=your_api_secret
```

## Improvement Checklist

See the [IMPROVEMENT_CHECKLIST.md](IMPROVEMENT_CHECKLIST.md) file for a detailed list of improvements and their implementation status.

## Documentation

- [Installation Guide](docs/installation.md)
- [Configuration Guide](docs/configuration.md)
- [Market Types Guide](docs/market_types_guide.md)
- [Deployment Guide](docs/deployment.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Enhanced Bot Documentation](docs/enhanced_bot_documentation.md)

## Running the Enhanced Bot with Expanded Pairs

The bot now supports trading on 25+ currency pairs with dynamic correlation analysis:

```bash
# Run the improved bot with basic settings
./run_improved_bot.sh

# Run the bot with expanded pair analysis
./run_expanded_pairs_bot.sh

# Analyze bot performance
./analyze_performance.sh
```

### Configuration

The bot can be configured using the `config.yaml` file. A sample configuration file is provided as `config.yaml.example`.

Key configuration options for the expanded pairs functionality:

```yaml
# Trading pairs configuration
trading_pairs:
  - 'EUR/USD'
  - 'GBP/USD'
  # Add more pairs as needed...

# Enable session-specific pair filtering (focus on active pairs for current session)
session_specific_pairs: true

# Correlation analysis settings
correlation_analysis:
  enabled: true
  correlation_lookback_days: 30
  correlation_update_interval: 6
  high_correlation_threshold: 0.85
  correlation_impact: 0.2
```

## Disclaimer

Trading involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results.
