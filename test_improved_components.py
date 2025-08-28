#!/usr/bin/env python
"""
Testing script for improved IQ 720 Trading Bot components
This script evaluates the performance of the improved ML predictor and signal generator
"""
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import argparse
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.utils.improved_ml_predictor import ImprovedMLPredictor
from src.improved_signal_generator import ImprovedSignalGenerator
from src.download_historical_data import download_from_yfinance


def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("test_improved_components")


def download_test_data(symbol='EURUSD=X', days=180):
    """Download historical data for testing"""
    logger = logging.getLogger("test_improved_components")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"Downloading historical data for {symbol} from {start_date.date()} to {end_date.date()}...")
    data = download_from_yfinance(symbol, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    
    if data is None or len(data) < 100:
        logger.error("Failed to download sufficient data")
        sys.exit(1)
    
    logger.info(f"Downloaded {len(data)} data points")
    return data


def split_data(data, train_ratio=0.6, validation_ratio=0.2):
    """Split data into training, validation and test sets"""
    train_size = int(len(data) * train_ratio)
    validation_size = int(len(data) * validation_ratio)
    
    train_data = data.iloc[:train_size]
    validation_data = data.iloc[train_size:train_size + validation_size]
    test_data = data.iloc[train_size + validation_size:]
    
    return train_data, validation_data, test_data


def evaluate_ml_predictor(train_data, test_data):
    """Evaluate the improved ML predictor"""
    logger = logging.getLogger("test_improved_components")
    logger.info("Evaluating improved ML predictor...")
    
    # Create and train predictor
    predictor = ImprovedMLPredictor(lookback_periods=50, sequence_length=10)
    predictor.train(train_data)
    
    # Evaluate on test data
    predictions = []
    confidences = []
    actuals = []
    timestamps = []
    uncertainties = []
    
    forward_period = 5  # Looking 5 candles ahead
    
    # Make predictions on test data
    for i in range(len(test_data) - forward_period):
        window = test_data.iloc[:i+1]
        current_time = window.index[-1]
        
        # Get prediction
        try:
            prediction, confidence, details = predictor.predict(window)
            
            # Calculate future return (looking forward_period bars ahead)
            future_return = test_data.iloc[i+forward_period]['close'] / test_data.iloc[i]['close'] - 1
            actual = future_return > 0  # True if price went up
            
            # Store results
            predictions.append(prediction)
            confidences.append(confidence)
            actuals.append(actual)
            timestamps.append(current_time)
            uncertainties.append(details.get('uncertainty', 0.5))
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
    
    # Calculate metrics
    results = pd.DataFrame({
        'timestamp': timestamps,
        'prediction': predictions,
        'confidence': confidences,
        'actual': actuals,
        'uncertainty': uncertainties
    })
    
    # Calculate metrics only on predictions with sufficient confidence
    high_conf = results[results['confidence'] >= 0.65]
    
    if len(high_conf) > 0:
        accuracy = accuracy_score(high_conf['actual'], high_conf['prediction'])
        precision = precision_score(high_conf['actual'], high_conf['prediction'], zero_division=0)
        recall = recall_score(high_conf['actual'], high_conf['prediction'], zero_division=0)
        f1 = f1_score(high_conf['actual'], high_conf['prediction'], zero_division=0)
        
        # Calculate confusion matrix
        cm = confusion_matrix(high_conf['actual'], high_conf['prediction'])
        
        logger.info(f"ML Predictor Evaluation (confidence >= 0.65):")
        logger.info(f"Number of predictions: {len(high_conf)}")
        logger.info(f"Accuracy: {accuracy:.4f}")
        logger.info(f"Precision: {precision:.4f}")
        logger.info(f"Recall: {recall:.4f}")
        logger.info(f"F1 Score: {f1:.4f}")
        logger.info(f"Confusion Matrix:\n{cm}")
        
        # Analyze prediction accuracy by confidence
        confidence_bins = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for i in range(len(confidence_bins) - 1):
            low = confidence_bins[i]
            high = confidence_bins[i+1]
            subset = results[(results['confidence'] >= low) & (results['confidence'] < high)]
            if len(subset) > 0:
                bin_accuracy = accuracy_score(subset['actual'], subset['prediction'])
                logger.info(f"Confidence {low:.1f}-{high:.1f}: {len(subset)} predictions, accuracy: {bin_accuracy:.4f}")
                
        # Analyze prediction accuracy by uncertainty
        uncertainty_bins = [0, 0.2, 0.3, 0.4, 0.5, 1.0]
        for i in range(len(uncertainty_bins) - 1):
            low = uncertainty_bins[i]
            high = uncertainty_bins[i+1]
            subset = results[(results['uncertainty'] >= low) & (results['uncertainty'] < high)]
            if len(subset) > 0:
                bin_accuracy = accuracy_score(subset['actual'], subset['prediction'])
                logger.info(f"Uncertainty {low:.1f}-{high:.1f}: {len(subset)} predictions, accuracy: {bin_accuracy:.4f}")
        
    else:
        logger.warning("No predictions with confidence >= 0.65")
    
    return results


def evaluate_signal_generator(train_data, test_data, symbol='EURUSD'):
    """Evaluate the improved signal generator"""
    logger = logging.getLogger("test_improved_components")
    logger.info("Evaluating improved signal generator...")
    
    # Create signal generator
    config = {
        'ml_confidence_threshold': 0.6,
        'min_signal_interval_minutes': 10  # Reduce for testing
    }
    signal_gen = ImprovedSignalGenerator(config=config)
    
    # Train the ML component using training data
    signal_gen.historical_data = train_data
    if not signal_gen.ml_predictor.is_trained:
        signal_gen.ml_predictor.train(train_data)
    
    # Generate signals on test data
    signals = []
    
    # Convert DataFrame to candle format
    for i in range(len(test_data)):
        candle = {
            'open': float(test_data.iloc[i]['open']),
            'high': float(test_data.iloc[i]['high']),
            'low': float(test_data.iloc[i]['low']),
            'close': float(test_data.iloc[i]['close']),
            'volume': float(test_data.iloc[i]['volume']),
            'timestamp': int(test_data.index[i].timestamp())
        }
        
        signal = signal_gen.add_candle(candle, asset_name=symbol)
        if signal:
            # Calculate future return based on signal expiry
            expiry_idx = min(i + signal.expiry_minutes, len(test_data) - 1)
            future_price = test_data.iloc[expiry_idx]['close']
            entry_price = test_data.iloc[i]['close']
            
            if signal.direction == "BUY":
                profit_pct = (future_price / entry_price - 1) * 100
                is_correct = profit_pct > 0
            else:  # SELL
                profit_pct = (entry_price / future_price - 1) * 100
                is_correct = profit_pct > 0
            
            signals.append({
                'timestamp': test_data.index[i],
                'direction': signal.direction,
                'confidence': signal.confidence,
                'uncertainty': signal.uncertainty,
                'expiry_minutes': signal.expiry_minutes,
                'profit_pct': profit_pct,
                'is_correct': is_correct
            })
    
    # Analyze signals
    if signals:
        signals_df = pd.DataFrame(signals)
        
        # Overall performance
        win_rate = signals_df['is_correct'].mean()
        avg_profit = signals_df['profit_pct'].mean()
        total_signals = len(signals_df)
        
        logger.info(f"Signal Generator Evaluation:")
        logger.info(f"Total signals: {total_signals}")
        logger.info(f"Win rate: {win_rate:.4f}")
        logger.info(f"Average profit: {avg_profit:.2f}%")
        
        # Analyze by confidence level
        confidence_bins = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for i in range(len(confidence_bins) - 1):
            low = confidence_bins[i]
            high = confidence_bins[i+1]
            subset = signals_df[(signals_df['confidence'] >= low) & (signals_df['confidence'] < high)]
            if len(subset) > 0:
                bin_win_rate = subset['is_correct'].mean()
                bin_avg_profit = subset['profit_pct'].mean()
                logger.info(f"Confidence {low:.1f}-{high:.1f}: {len(subset)} signals, win rate: {bin_win_rate:.4f}, avg profit: {bin_avg_profit:.2f}%")
                
        # Analyze by uncertainty
        uncertainty_bins = [0, 0.2, 0.3, 0.4, 0.5, 1.0]
        for i in range(len(uncertainty_bins) - 1):
            low = uncertainty_bins[i]
            high = uncertainty_bins[i+1]
            subset = signals_df[(signals_df['uncertainty'] >= low) & (signals_df['uncertainty'] < high)]
            if len(subset) > 0:
                bin_win_rate = subset['is_correct'].mean()
                logger.info(f"Uncertainty {low:.1f}-{high:.1f}: {len(subset)} signals, win rate: {bin_win_rate:.4f}")
                
        # Analyze by direction
        buy_signals = signals_df[signals_df['direction'] == 'BUY']
        sell_signals = signals_df[signals_df['direction'] == 'SELL']
        
        if len(buy_signals) > 0:
            buy_win_rate = buy_signals['is_correct'].mean()
            buy_avg_profit = buy_signals['profit_pct'].mean()
            logger.info(f"BUY signals: {len(buy_signals)}, win rate: {buy_win_rate:.4f}, avg profit: {buy_avg_profit:.2f}%")
        
        if len(sell_signals) > 0:
            sell_win_rate = sell_signals['is_correct'].mean()
            sell_avg_profit = sell_signals['profit_pct'].mean()
            logger.info(f"SELL signals: {len(sell_signals)}, win rate: {sell_win_rate:.4f}, avg profit: {sell_avg_profit:.2f}%")
        
        return signals_df
    else:
        logger.warning("No signals generated during test period")
        return None


def plot_results(ml_results, signals_df=None, test_data=None):
    """Plot evaluation results"""
    logger = logging.getLogger("test_improved_components")
    
    if test_data is None:
        logger.warning("No test data provided for plotting")
        return
    
    # Create figure with multiple subplots
    plt.figure(figsize=(15, 12))
    
    # Plot 1: Price chart with signals
    plt.subplot(3, 1, 1)
    plt.title('Price Chart with Trading Signals')
    plt.plot(test_data.index, test_data['close'], label='Close Price')
    
    if signals_df is not None and len(signals_df) > 0:
        buy_signals = signals_df[signals_df['direction'] == 'BUY']
        sell_signals = signals_df[signals_df['direction'] == 'SELL']
        
        # Plot buy signals
        if len(buy_signals) > 0:
            plt.scatter(buy_signals['timestamp'], 
                       [test_data.loc[t, 'close'] for t in buy_signals['timestamp']], 
                       marker='^', color='green', s=100, label='Buy Signal')
        
        # Plot sell signals
        if len(sell_signals) > 0:
            plt.scatter(sell_signals['timestamp'], 
                       [test_data.loc[t, 'close'] for t in sell_signals['timestamp']], 
                       marker='v', color='red', s=100, label='Sell Signal')
    
    plt.grid(True)
    plt.legend()
    
    # Plot 2: ML Prediction Accuracy vs Confidence
    if ml_results is not None and len(ml_results) > 0:
        plt.subplot(3, 1, 2)
        plt.title('ML Prediction Accuracy vs Confidence')
        
        # Create confidence bins
        confidence_bins = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
        accuracy_by_confidence = []
        
        for i in range(len(confidence_bins) - 1):
            low = confidence_bins[i]
            high = confidence_bins[i+1]
            subset = ml_results[(ml_results['confidence'] >= low) & (ml_results['confidence'] < high)]
            if len(subset) > 10:  # Only consider bins with sufficient data
                bin_accuracy = accuracy_score(subset['actual'], subset['prediction'])
                accuracy_by_confidence.append((low + high) / 2, bin_accuracy, len(subset))
        
        if accuracy_by_confidence:
            x, y, sizes = zip(*accuracy_by_confidence)
            plt.scatter(x, y, s=[min(s, 300) for s in sizes], alpha=0.6)
            plt.plot(x, y, 'b--')
            
        # Plot the ideal line (x=y)
        plt.plot([0.5, 1.0], [0.5, 1.0], 'r--', label='Ideal Calibration')
        
        plt.xlim(0.5, 1.0)
        plt.ylim(0, 1.0)
        plt.grid(True)
        plt.xlabel('Confidence')
        plt.ylabel('Accuracy')
        plt.legend()
    
    # Plot 3: Signal Performance by Confidence
    if signals_df is not None and len(signals_df) > 0:
        plt.subplot(3, 1, 3)
        plt.title('Signal Win Rate by Confidence')
        
        # Create confidence bins
        confidence_bins = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        win_rates = []
        
        for i in range(len(confidence_bins) - 1):
            low = confidence_bins[i]
            high = confidence_bins[i+1]
            subset = signals_df[(signals_df['confidence'] >= low) & (signals_df['confidence'] < high)]
            if len(subset) > 0:  # Only consider bins with data
                bin_win_rate = subset['is_correct'].mean()
                win_rates.append(((low + high) / 2, bin_win_rate, len(subset)))
        
        if win_rates:
            x, y, sizes = zip(*win_rates)
            plt.bar(x, y, width=0.08, alpha=0.7)
            
            # Add count labels
            for i, (xi, yi, count) in enumerate(win_rates):
                plt.text(xi, yi + 0.02, f"{count}", ha='center')
        
        plt.xlim(0.5, 1.0)
        plt.ylim(0, 1.0)
        plt.grid(True)
        plt.xlabel('Confidence')
        plt.ylabel('Win Rate')
    
    plt.tight_layout()
    
    # Save figure
    output_dir = os.path.join(project_root, 'results')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'evaluation_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
    plt.savefig(output_file)
    logger.info(f"Results plot saved to: {output_file}")
    
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Test improved IQ 720 Trading Bot components')
    parser.add_argument('--symbol', default='EURUSD=X', help='Symbol to test (default: EURUSD=X)')
    parser.add_argument('--days', type=int, default=180, help='Number of days of historical data (default: 180)')
    args = parser.parse_args()
    
    logger = setup_logging()
    logger.info("Starting component evaluation")
    
    # Download test data
    data = download_test_data(symbol=args.symbol, days=args.days)
    
    # Split data
    train_data, validation_data, test_data = split_data(data)
    logger.info(f"Data split: Training ({len(train_data)} samples), Validation ({len(validation_data)} samples), Test ({len(test_data)} samples)")
    
    # Evaluate ML predictor
    ml_results = evaluate_ml_predictor(train_data, validation_data)
    
    # Evaluate signal generator (using validation data for signals)
    symbol_name = args.symbol.replace('=X', '')
    signals_df = evaluate_signal_generator(train_data, validation_data, symbol=symbol_name)
    
    # Plot results
    plot_results(ml_results, signals_df, validation_data)
    
    logger.info("Evaluation complete")


if __name__ == "__main__":
    main()
