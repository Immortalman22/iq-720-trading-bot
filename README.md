# iq-720-trading-bot
"AI-powered trading bot for IQ Option with 90%+ win rate signals."

## Enhanced Machine Learning Capabilities

The trading bot now includes advanced machine learning capabilities for more accurate market predictions:

### Machine Learning Features

- **Ensemble Learning**: Combines multiple models including Random Forest, XGBoost, LightGBM, and deep learning models
- **Deep Learning**: LSTM and CNN architectures for sequence-based pattern recognition
- **Explainable AI**: SHAP values for model interpretability and feature importance analysis
- **Anomaly Detection**: Identifies unusual market conditions and regime changes
- **Advanced Feature Engineering**: 60+ technical features derived from price and volume data
- **Hyperparameter Optimization**: Automated tuning for optimal model performance
- **Market Regime Awareness**: Models adjust to different market conditions

### Using the ML Components

1. **Install Dependencies**: Run the setup script
   ```bash
   ./setup_ml.sh
   ```

2. **Train Models**: Use the ML trainer with your own parameters
   ```bash
   python src/ml_trainer.py --symbol EURUSD=X --start_date 2020-01-01
   ```

3. **Run Demo**: See ML prediction capabilities in action
   ```bash
   python demo/ml_trading_demo.py
   ```
