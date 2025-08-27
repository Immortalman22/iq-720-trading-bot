"""
Enhanced Machine Learning Trainer for Trading Bot
Trains and optimizes ML models for market prediction and pattern recognition
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from src.utils.ml_predictor import MLPredictor
from src.download_historical_data import download_from_yfinance, download_multiple_sources


def setup_logging(log_level=logging.INFO):
    """Set up logging configuration"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/ml_training.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("ml_trainer")


def load_historical_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load historical data for training
    
    Args:
        symbol: Trading symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with OHLCV data
    """
    logger = logging.getLogger("ml_trainer")
    logger.info(f"Loading historical data for {symbol} from {start_date} to {end_date}")
    
    try:
        # Try to load from multiple sources
        data = download_multiple_sources(symbol, start_date, end_date)
        if data is None or len(data) < 100:
            # Fallback to Yahoo Finance
            data = download_from_yfinance(symbol, start_date, end_date)
    except Exception as e:
        logger.error(f"Error downloading from multiple sources: {e}")
        # Fallback to Yahoo Finance
        data = download_from_yfinance(symbol, start_date, end_date)
    
    if data is None or len(data) < 100:
        logger.error(f"Failed to load sufficient historical data")
        return None
    
    logger.info(f"Loaded {len(data)} data points")
    return data


def prepare_validation_data(data: pd.DataFrame, validation_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data into training and validation sets
    
    Args:
        data: Full historical dataset
        validation_size: Proportion to use for validation
        
    Returns:
        Tuple of (training_data, validation_data)
    """
    split_idx = int(len(data) * (1 - validation_size))
    return data.iloc[:split_idx], data.iloc[split_idx:]


def visualize_predictions(model: MLPredictor, validation_data: pd.DataFrame, save_path: str = None):
    """
    Visualize model predictions on validation data
    
    Args:
        model: Trained MLPredictor
        validation_data: Validation dataset
        save_path: Path to save the visualization
    """
    # Generate predictions for each validation data point
    predictions = []
    confidences = []
    actuals = []
    
    # Step through validation data
    for i in range(len(validation_data) - 5):
        window = validation_data.iloc[:i+1]
        try:
            pred, conf, _ = model.predict(window)
            predictions.append(1 if pred else 0)
            confidences.append(conf)
            # Actual outcome (price went up in next 5 periods?)
            future_return = validation_data.iloc[i+5]['close'] / validation_data.iloc[i]['close'] - 1
            actuals.append(1 if future_return > 0 else 0)
        except:
            continue
    
    if not predictions:
        return
    
    # Create visualization
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Validation data price
    plt.subplot(3, 1, 1)
    plt.plot(validation_data['close'], label='Close Price')
    plt.title('Validation Data Close Price')
    plt.legend()
    
    # Plot 2: Prediction confidence
    plt.subplot(3, 1, 2)
    
    # Create colormap based on prediction correctness
    colors = []
    for i in range(len(predictions)):
        if predictions[i] == actuals[i]:
            colors.append('green')  # Correct prediction
        else:
            colors.append('red')    # Incorrect prediction
    
    plt.scatter(range(len(confidences)), confidences, c=colors, alpha=0.7)
    plt.axhline(y=0.5, color='k', linestyle='--')
    plt.title('Prediction Confidence (green=correct, red=incorrect)')
    plt.ylim(0, 1)
    
    # Plot 3: Accuracy over time
    plt.subplot(3, 1, 3)
    rolling_accuracy = []
    window_size = 20
    for i in range(len(predictions)):
        if i < window_size:
            window_acc = np.mean([1 if predictions[j] == actuals[j] else 0 for j in range(i+1)])
        else:
            window_acc = np.mean([1 if predictions[j] == actuals[j] else 0 for j in range(i-window_size, i+1)])
        rolling_accuracy.append(window_acc)
    
    plt.plot(rolling_accuracy, label='Rolling Accuracy')
    plt.axhline(y=0.5, color='k', linestyle='--')
    plt.title(f'Rolling Accuracy (window={window_size})')
    plt.ylim(0, 1)
    plt.legend()
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
    else:
        plt.show()


def optimize_and_train(data: pd.DataFrame, hyperparameter_optimization: bool = False) -> MLPredictor:
    """
    Train and optimize ML models
    
    Args:
        data: Historical OHLCV data
        hyperparameter_optimization: Whether to use hyperparameter optimization
        
    Returns:
        Trained MLPredictor
    """
    logger = logging.getLogger("ml_trainer")
    
    # Create output directory
    os.makedirs("models", exist_ok=True)
    
    # Initialize ML predictor
    ml_predictor = MLPredictor(lookback_periods=100, sequence_length=20)
    
    # Train models
    logger.info(f"Training ML models with hyperparameter optimization: {hyperparameter_optimization}")
    try:
        ml_predictor.train(data, optimize_hyperparams=hyperparameter_optimization)
        logger.info("Model training completed successfully")
    except Exception as e:
        logger.error(f"Error during model training: {e}")
        return None
    
    # Evaluate model performance
    evaluation = ml_predictor.evaluate_model_performance(data)
    logger.info("Model evaluation results:")
    for model_name, metrics in evaluation.items():
        if isinstance(metrics, dict) and 'error' not in metrics:
            logger.info(f"- {model_name}: Accuracy={metrics.get('accuracy', 'N/A'):.4f}, "
                      f"Precision={metrics.get('precision', 'N/A'):.4f}, "
                      f"Recall={metrics.get('recall', 'N/A'):.4f}, "
                      f"F1={metrics.get('f1_score', 'N/A'):.4f}")
    
    # Generate feature importance visualization
    try:
        ml_predictor.visualize_feature_importance(save_path="models/feature_importance.png")
        logger.info("Feature importance visualization saved to models/feature_importance.png")
    except Exception as e:
        logger.error(f"Error generating feature importance visualization: {e}")
    
    return ml_predictor


def main():
    """Main entry point for ML training"""
    parser = argparse.ArgumentParser(description="Train and optimize ML models for trading")
    parser.add_argument("--symbol", default="EURUSD=X", help="Trading symbol to download data for")
    parser.add_argument("--start_date", default="2018-01-01", help="Start date for historical data (YYYY-MM-DD)")
    parser.add_argument("--end_date", default=None, help="End date for historical data (YYYY-MM-DD)")
    parser.add_argument("--optimize", action="store_true", help="Perform hyperparameter optimization")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(log_level)
    
    # Set default end date to current date if not provided
    if not args.end_date:
        args.end_date = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"Starting ML training for {args.symbol} from {args.start_date} to {args.end_date}")
    
    # Load historical data
    data = load_historical_data(args.symbol, args.start_date, args.end_date)
    if data is None or len(data) < 100:
        logger.error("Insufficient historical data. Exiting.")
        return
    
    # Split into training and validation sets
    train_data, validation_data = prepare_validation_data(data)
    logger.info(f"Split data into {len(train_data)} training samples and {len(validation_data)} validation samples")
    
    # Train and optimize ML models
    ml_predictor = optimize_and_train(train_data, hyperparameter_optimization=args.optimize)
    if ml_predictor is None:
        logger.error("ML training failed. Exiting.")
        return
    
    # Visualize predictions on validation data
    logger.info("Generating prediction visualization on validation data")
    try:
        visualize_predictions(ml_predictor, validation_data, save_path="models/prediction_validation.png")
        logger.info("Prediction visualization saved to models/prediction_validation.png")
    except Exception as e:
        logger.error(f"Error visualizing predictions: {e}")
    
    logger.info("ML training and optimization completed successfully")


if __name__ == "__main__":
    main()
