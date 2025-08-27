"""
ML Trading Bot Demo
Demonstrates the enhanced machine learning capabilities of the trading bot
"""
import os
import sys
import logging
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.ml_predictor import MLPredictor
from src.download_historical_data import download_from_yfinance
from src.utils.market_regime import MarketRegimeDetector
from src.utils.pattern_recognition import PatternRecognition


def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("ml_demo")


def download_demo_data(symbol='EURUSD=X', days=365):
    """Download historical data for demo"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    print(f"Downloading historical data for {symbol} from {start_date.date()} to {end_date.date()}...")
    data = download_from_yfinance(symbol, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    if data is None or len(data) < 100:
        print("Failed to download sufficient data.")
        sys.exit(1)
    
    print(f"Downloaded {len(data)} data points")
    return data


def train_ml_models(data):
    """Train ML models on the first 80% of data"""
    split_idx = int(len(data) * 0.8)
    train_data = data.iloc[:split_idx]
    
    print(f"Training ML models on {len(train_data)} data points...")
    predictor = MLPredictor(lookback_periods=100, sequence_length=20)
    try:
        predictor.train(train_data)
        print("Model training completed successfully")
        return predictor, data.iloc[split_idx:]
    except Exception as e:
        print(f"Error training models: {e}")
        sys.exit(1)


def backtest_ml_predictions(predictor, test_data):
    """Backtest ML predictions on test data"""
    results = []
    
    print(f"Backtesting on {len(test_data)} data points...")
    
    # Market regime detector for context
    regime_detector = MarketRegimeDetector()
    
    # For each point in test data
    for i in range(len(test_data) - 5):  # -5 to allow for forward returns calculation
        window = test_data.iloc[:i+1]
        current_date = window.index[-1]
        
        # Get market regime
        prices = window['close'].values
        regime, confidence = regime_detector.detect_regime(prices[-100:] if len(prices) > 100 else prices)
        
        # Get prediction
        try:
            prediction, confidence, details = predictor.predict(window)
            
            # Calculate future return (looking 5 bars ahead)
            future_return = test_data.iloc[i+5]['close'] / test_data.iloc[i]['close'] - 1
            correct = (prediction and future_return > 0) or (not prediction and future_return <= 0)
            
            results.append({
                'date': current_date,
                'prediction': 'BUY' if prediction else 'SELL',
                'confidence': confidence,
                'future_return': future_return,
                'correct': correct,
                'regime': regime.name,
                'top_feature': list(details.get('top_features', {}).keys())[0] if details.get('top_features') else None
            })
        except Exception as e:
            print(f"Error during prediction at {current_date}: {e}")
    
    results_df = pd.DataFrame(results)
    
    # Calculate performance metrics
    accuracy = results_df['correct'].mean()
    win_rate = results_df[results_df['prediction'] == 'BUY']['correct'].mean()
    avg_return = results_df[results_df['prediction'] == 'BUY']['future_return'].mean()
    
    print(f"Overall Accuracy: {accuracy:.4f}")
    print(f"Buy Signal Win Rate: {win_rate:.4f}")
    print(f"Average Return per Buy Signal: {avg_return:.4%}")
    
    return results_df


def visualize_backtest_results(results_df, test_data):
    """Visualize backtest results"""
    # Create plot
    plt.figure(figsize=(15, 12))
    
    # Plot 1: Price chart with buy signals
    plt.subplot(3, 1, 1)
    plt.plot(test_data['close'], color='black', alpha=0.3, label='Price')
    
    # Plot buy signals
    buy_signals = results_df[results_df['prediction'] == 'BUY']
    correct_buys = buy_signals[buy_signals['correct'] == True]
    incorrect_buys = buy_signals[buy_signals['correct'] == False]
    
    plt.scatter(correct_buys['date'], test_data.loc[correct_buys['date']]['close'], 
               color='green', marker='^', s=100, label='Correct Buy')
    plt.scatter(incorrect_buys['date'], test_data.loc[incorrect_buys['date']]['close'], 
               color='red', marker='^', s=100, label='Incorrect Buy')
    
    plt.title('Price Chart with ML Buy Signals')
    plt.legend()
    
    # Plot 2: Prediction Confidence
    plt.subplot(3, 1, 2)
    plt.scatter(results_df['date'], results_df['confidence'], 
               c=results_df['correct'].map({True: 'green', False: 'red'}), alpha=0.7)
    plt.axhline(y=0.7, color='black', linestyle='--')
    plt.title('Prediction Confidence (green=correct, red=incorrect)')
    plt.ylabel('Confidence')
    
    # Plot 3: Performance by market regime
    plt.subplot(3, 1, 3)
    regime_accuracy = results_df.groupby('regime')['correct'].mean()
    regime_counts = results_df.groupby('regime').size()
    
    bars = plt.bar(regime_accuracy.index, regime_accuracy.values)
    
    # Color bars by performance
    for i, bar in enumerate(bars):
        if regime_accuracy.values[i] >= 0.6:
            bar.set_color('green')
        elif regime_accuracy.values[i] <= 0.4:
            bar.set_color('red')
        else:
            bar.set_color('orange')
            
    # Add count labels to bars
    for i, bar in enumerate(bars):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'n={regime_counts.values[i]}', ha='center')
    
    plt.axhline(y=0.5, color='black', linestyle='--')
    plt.title('Prediction Accuracy by Market Regime')
    plt.ylim(0, 1)
    
    plt.tight_layout()
    plt.savefig('demo/ml_backtest_results.png')
    print("Visualization saved as 'demo/ml_backtest_results.png'")
    plt.close()


def feature_importance_demo(predictor):
    """Demonstrate feature importance analysis"""
    plt.figure(figsize=(12, 8))
    importances = predictor.visualize_feature_importance(top_n=15, save_path='demo/ml_feature_importance.png')
    print("Feature importance visualization saved as 'demo/ml_feature_importance.png'")
    return importances


def show_live_prediction_example(predictor, data):
    """Show an example of live prediction with explanation"""
    # Use the last data point for a "live" prediction
    latest_data = data.copy()
    
    # Get prediction
    prediction, confidence, details = predictor.predict(latest_data)
    
    print("\n=== Live Prediction Example ===")
    print(f"Prediction: {'BUY' if prediction else 'SELL'}")
    print(f"Confidence: {confidence:.4f}")
    print("\nTop influential features:")
    
    # Show top features
    for feature, importance in details.get('top_features', {}).items():
        print(f"- {feature}: {importance:.4f}")
    
    # Show model breakdown
    print("\nIndividual model predictions:")
    for model, pred in details.get('model_predictions', {}).items():
        prob = details.get('model_probabilities', {}).get(model, 0)
        print(f"- {model}: {'BUY' if pred else 'SELL'} (confidence: {prob:.4f})")
    
    # Anomaly detection
    print(f"\nAnomaly detected: {details.get('is_anomaly', False)}")
    print(f"Anomaly score: {details.get('anomaly_score', 0):.4f}")
    
    # Price prediction if available
    if details.get('price_prediction') is not None:
        current_price = latest_data['close'].iloc[-1]
        predicted_price = details.get('price_prediction')
        change = (predicted_price / current_price - 1) * 100
        print(f"\nPrice prediction: {predicted_price:.5f} (current: {current_price:.5f}, change: {change:.2f}%)")


def main():
    """Main demo entry point"""
    parser = argparse.ArgumentParser(description="ML Trading Bot Demo")
    parser.add_argument("--days", type=int, default=365, help="Days of historical data to use")
    parser.add_argument("--symbol", default="EURUSD=X", help="Trading symbol")
    args = parser.parse_args()
    
    logger = setup_logging()
    
    # Create demo directory
    os.makedirs("demo", exist_ok=True)
    
    print("=" * 50)
    print("ML TRADING BOT DEMO")
    print("=" * 50)
    
    # Step 1: Download data
    data = download_demo_data(args.symbol, args.days)
    
    # Step 2: Train ML models
    predictor, test_data = train_ml_models(data)
    
    # Step 3: Backtest predictions
    results = backtest_ml_predictions(predictor, test_data)
    
    # Step 4: Visualize results
    visualize_backtest_results(results, test_data)
    
    # Step 5: Feature importance analysis
    feature_importance_demo(predictor)
    
    # Step 6: Live prediction example
    show_live_prediction_example(predictor, data)
    
    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
