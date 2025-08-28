#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Return Prediction Model for IQ-720 Trading Bot

This module extends the binary classification approach to predict expected returns,
enabling more sophisticated trading decisions based on risk/reward calculations.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib
import logging
import os
from datetime import datetime
import matplotlib.pyplot as plt

logger = logging.getLogger("ReturnPredictionModel")

class ReturnPredictionModel:
    """
    Predicts expected returns for trading decisions, extending beyond binary
    classification to enable risk/reward-based position sizing and exits.
    """
    
    def __init__(self, config=None):
        """
        Initialize the return prediction model.
        
        Args:
            config: Configuration dictionary for model parameters
        """
        self.config = config or {}
        self.base_model_path = self.config.get('model_path', 'models/')
        self.lookback_periods = self.config.get('lookback_periods', 100)
        self.prediction_horizons = self.config.get('prediction_horizons', [5, 15, 30, 60])
        self.feature_importance = {}
        
        # Create model directory if it doesn't exist
        os.makedirs(self.base_model_path, exist_ok=True)
        
        # Initialize models dictionary
        self.models = {}
        self.scalers = {}
        self.uncertainty_models = {}
        
    def prepare_features(self, data, target_col=None):
        """
        Prepare features for return prediction model.
        
        Args:
            data: DataFrame with OHLCV data and technical indicators
            target_col: Name of target column (if preparing for training)
            
        Returns:
            X: Feature matrix
            y: Target vector (if target_col provided)
        """
        # Ensure data is sorted by time
        if 'timestamp' in data.columns:
            data = data.sort_values('timestamp')
            
        # Extract features
        features = []
        feature_names = []
        
        # Price-based features
        for col in ['open', 'high', 'low', 'close']:
            if col in data.columns:
                # Price changes over multiple timeframes
                for periods in [1, 3, 5, 10, 20]:
                    if len(data) > periods:
                        col_name = f"{col}_pct_{periods}"
                        data[col_name] = data[col].pct_change(periods)
                        features.append(data[col_name].values)
                        feature_names.append(col_name)
                        
                # Volatility features
                if col in ['high', 'low', 'close'] and len(data) > 20:
                    for periods in [5, 10, 20]:
                        col_name = f"{col}_std_{periods}"
                        data[col_name] = data[col].rolling(periods).std()
                        features.append(data[col_name].values)
                        feature_names.append(col_name)
        
        # Volume features
        if 'volume' in data.columns and len(data) > 20:
            # Volume changes
            for periods in [1, 5, 10]:
                col_name = f"volume_pct_{periods}"
                data[col_name] = data['volume'].pct_change(periods)
                features.append(data[col_name].values)
                feature_names.append(col_name)
                
            # Volume moving averages
            for periods in [5, 10, 20]:
                col_name = f"volume_ma_{periods}"
                data[col_name] = data['volume'].rolling(periods).mean()
                features.append(data[col_name].values)
                feature_names.append(col_name)
                
            # Volume relative to moving average
            col_name = "volume_rel_ma"
            data[col_name] = data['volume'] / data['volume'].rolling(20).mean()
            features.append(data[col_name].values)
            feature_names.append(col_name)
        
        # Add technical indicators if available
        tech_indicators = [
            'rsi', 'macd', 'macd_signal', 'macd_hist', 'bb_upper', 'bb_middle',
            'bb_lower', 'adx', 'cci', 'stoch_k', 'stoch_d', 'obv', 'atr'
        ]
        
        for indicator in tech_indicators:
            if indicator in data.columns:
                features.append(data[indicator].values)
                feature_names.append(indicator)
                
                # Add change in indicator
                if len(data) > 1:
                    col_name = f"{indicator}_change"
                    data[col_name] = data[indicator].diff()
                    features.append(data[col_name].values)
                    feature_names.append(col_name)
        
        # Prepare the feature matrix
        X = np.column_stack(features)
        
        # Replace NaN values with 0
        X = np.nan_to_num(X, nan=0.0)
        
        # Prepare target if target_col is provided
        if target_col and target_col in data.columns:
            y = data[target_col].values
            y = np.nan_to_num(y, nan=0.0)
            return X, y, feature_names
        
        return X, None, feature_names
        
    def create_return_targets(self, data, horizons=None):
        """
        Create target variables for different prediction horizons.
        
        Args:
            data: DataFrame with OHLCV data
            horizons: List of future periods to predict returns for
            
        Returns:
            DataFrame with added target columns
        """
        if horizons is None:
            horizons = self.prediction_horizons
            
        df = data.copy()
        
        # Add future returns for each horizon
        for horizon in horizons:
            target_col = f"future_return_{horizon}"
            df[target_col] = df['close'].shift(-horizon) / df['close'] - 1.0
            
            # Add target direction (for evaluation purposes)
            df[f"future_direction_{horizon}"] = np.where(df[target_col] > 0, 1, -1)
            
            # Add target magnitude categories
            df[f"return_magnitude_{horizon}"] = pd.qcut(
                df[target_col].abs(), 
                q=5, 
                labels=['very_small', 'small', 'medium', 'large', 'very_large'],
                duplicates='drop'
            )
            
        return df
        
    def train_return_models(self, data, horizons=None, validation_split=0.2):
        """
        Train models to predict returns for different time horizons.
        
        Args:
            data: DataFrame with OHLCV data and technical indicators
            horizons: List of future periods to predict returns for
            validation_split: Fraction of data to use for validation
            
        Returns:
            Dictionary with training metrics
        """
        if horizons is None:
            horizons = self.prediction_horizons
            
        metrics = {}
        
        # Prepare data with target variables
        df = self.create_return_targets(data, horizons)
        
        # Train models for each horizon
        for horizon in horizons:
            target_col = f"future_return_{horizon}"
            if target_col not in df.columns or df[target_col].isna().all():
                logger.warning(f"Target column {target_col} not found or all NaN, skipping")
                continue
                
            # Drop rows with NaN targets
            valid_data = df.dropna(subset=[target_col])
            if len(valid_data) < 100:
                logger.warning(f"Not enough valid data for horizon {horizon}, skipping")
                continue
                
            logger.info(f"Training return prediction model for horizon {horizon} with {len(valid_data)} samples")
            
            # Prepare features and target
            X, y, feature_names = self.prepare_features(valid_data, target_col=target_col)
            
            # Use time series split for validation
            tscv = TimeSeriesSplit(n_splits=5)
            split_id = 0
            
            for train_idx, val_idx in tscv.split(X):
                if split_id < 4:  # Use only the last split for validation
                    split_id += 1
                    continue
                    
                X_train, X_val = X[train_idx], X[val_idx]
                y_train, y_val = y[train_idx], y[val_idx]
                
                # Create and fit scaler
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_val_scaled = scaler.transform(X_val)
                
                # Save scaler
                scaler_path = os.path.join(self.base_model_path, f"return_scaler_{horizon}.pkl")
                joblib.dump(scaler, scaler_path)
                self.scalers[horizon] = scaler
                
                # Create and train return prediction model
                models = {
                    'gbr': GradientBoostingRegressor(
                        n_estimators=100,
                        max_depth=4,
                        learning_rate=0.1,
                        subsample=0.8,
                        random_state=42
                    ),
                    'rf': RandomForestRegressor(
                        n_estimators=100,
                        max_depth=6,
                        random_state=42
                    ),
                    'elastic': ElasticNet(
                        alpha=0.5,
                        l1_ratio=0.5,
                        random_state=42
                    )
                }
                
                model_metrics = {}
                best_model_name = None
                best_model_rmse = float('inf')
                
                # Train and evaluate each model
                for model_name, model in models.items():
                    model.fit(X_train_scaled, y_train)
                    y_pred = model.predict(X_val_scaled)
                    
                    # Calculate metrics
                    rmse = np.sqrt(mean_squared_error(y_val, y_pred))
                    mae = mean_absolute_error(y_val, y_pred)
                    r2 = r2_score(y_val, y_pred)
                    
                    # Direction accuracy
                    direction_accuracy = np.mean((y_val > 0) == (y_pred > 0))
                    
                    model_metrics[model_name] = {
                        'rmse': rmse,
                        'mae': mae,
                        'r2': r2,
                        'direction_accuracy': direction_accuracy
                    }
                    
                    # Track best model
                    if rmse < best_model_rmse:
                        best_model_rmse = rmse
                        best_model_name = model_name
                
                # Save the best model
                if best_model_name:
                    best_model = models[best_model_name]
                    
                    # Get feature importance if available
                    if hasattr(best_model, 'feature_importances_'):
                        importances = best_model.feature_importances_
                        self.feature_importance[horizon] = {
                            feature_names[i]: importances[i]
                            for i in range(len(feature_names))
                        }
                    
                    # Save model
                    model_path = os.path.join(self.base_model_path, f"return_model_{horizon}.pkl")
                    joblib.dump(best_model, model_path)
                    self.models[horizon] = best_model
                    
                    # Train uncertainty model (predicts squared error)
                    y_pred = best_model.predict(X_train_scaled)
                    squared_errors = (y_train - y_pred) ** 2
                    
                    uncertainty_model = GradientBoostingRegressor(
                        n_estimators=50,
                        max_depth=3,
                        learning_rate=0.05,
                        subsample=0.8,
                        random_state=42
                    )
                    
                    uncertainty_model.fit(X_train_scaled, squared_errors)
                    uncertainty_path = os.path.join(self.base_model_path, f"uncertainty_model_{horizon}.pkl")
                    joblib.dump(uncertainty_model, uncertainty_path)
                    self.uncertainty_models[horizon] = uncertainty_model
                    
                    # Add uncertainty metrics
                    uncertainty_pred = np.sqrt(uncertainty_model.predict(X_val_scaled))
                    coverage_68 = np.mean(np.abs(y_val - y_pred) < uncertainty_pred)
                    coverage_95 = np.mean(np.abs(y_val - y_pred) < 2 * uncertainty_pred)
                    
                    model_metrics['uncertainty'] = {
                        'coverage_68': coverage_68,
                        'coverage_95': coverage_95
                    }
                    
                    metrics[horizon] = {
                        'best_model': best_model_name,
                        'metrics': model_metrics
                    }
                    
                    logger.info(f"Horizon {horizon}: Best model {best_model_name} with RMSE {best_model_rmse:.6f}, "
                                f"Direction accuracy {model_metrics[best_model_name]['direction_accuracy']:.2f}")
                    
                break  # Only use the last split
                
        # Visualize feature importances
        self._plot_feature_importance()
                
        return metrics
    
    def load_models(self):
        """
        Load previously trained models from disk.
        
        Returns:
            bool: True if models were loaded successfully
        """
        try:
            loaded_models = 0
            
            for horizon in self.prediction_horizons:
                model_path = os.path.join(self.base_model_path, f"return_model_{horizon}.pkl")
                scaler_path = os.path.join(self.base_model_path, f"return_scaler_{horizon}.pkl")
                uncertainty_path = os.path.join(self.base_model_path, f"uncertainty_model_{horizon}.pkl")
                
                if os.path.exists(model_path) and os.path.exists(scaler_path):
                    self.models[horizon] = joblib.load(model_path)
                    self.scalers[horizon] = joblib.load(scaler_path)
                    loaded_models += 1
                    
                    if os.path.exists(uncertainty_path):
                        self.uncertainty_models[horizon] = joblib.load(uncertainty_path)
                    
            logger.info(f"Loaded {loaded_models} return prediction models")
            return loaded_models > 0
            
        except Exception as e:
            logger.error(f"Error loading return prediction models: {str(e)}")
            return False
    
    def predict_returns(self, data, horizons=None):
        """
        Predict returns for different horizons.
        
        Args:
            data: DataFrame with OHLCV data and technical indicators
            horizons: List of horizons to predict for
            
        Returns:
            DataFrame with predicted returns and uncertainty
        """
        if horizons is None:
            horizons = self.prediction_horizons
            
        if not self.models:
            if not self.load_models():
                logger.error("No models available for return prediction")
                return None
                
        # Prepare features
        X, _, _ = self.prepare_features(data)
        
        # Make predictions for each horizon
        predictions = {}
        
        for horizon in horizons:
            if horizon not in self.models or horizon not in self.scalers:
                logger.debug(f"No model available for horizon {horizon}")
                continue
                
            # Scale features
            X_scaled = self.scalers[horizon].transform(X)
            
            # Predict returns
            predicted_returns = self.models[horizon].predict(X_scaled)
            
            # Predict uncertainty if available
            if horizon in self.uncertainty_models:
                predicted_uncertainty = np.sqrt(self.uncertainty_models[horizon].predict(X_scaled))
            else:
                # Fall back to simple uncertainty estimate
                predicted_uncertainty = np.std(predicted_returns) * np.ones_like(predicted_returns)
                
            # Store predictions
            predictions[f"predicted_return_{horizon}"] = predicted_returns
            predictions[f"return_uncertainty_{horizon}"] = predicted_uncertainty
            predictions[f"return_lower_bound_{horizon}"] = predicted_returns - 2 * predicted_uncertainty
            predictions[f"return_upper_bound_{horizon}"] = predicted_returns + 2 * predicted_uncertainty
            predictions[f"return_sharpe_{horizon}"] = predicted_returns / (predicted_uncertainty + 1e-6)
            
        # Convert to DataFrame
        result = pd.DataFrame(predictions, index=data.index[-len(X):])
        
        return result
        
    def evaluate_predictions(self, data, horizons=None):
        """
        Evaluate return predictions against actual returns.
        
        Args:
            data: DataFrame with OHLCV data and prediction targets
            horizons: List of horizons to evaluate
            
        Returns:
            Dictionary of evaluation metrics
        """
        if horizons is None:
            horizons = self.prediction_horizons
            
        # Get predictions
        predictions = self.predict_returns(data, horizons)
        
        if predictions is None:
            return None
            
        # Create return targets
        target_data = self.create_return_targets(data, horizons)
        
        # Align predictions with targets
        aligned_data = target_data.iloc[-len(predictions):].copy()
        for col in predictions.columns:
            aligned_data[col] = predictions[col].values
        
        # Calculate metrics for each horizon
        metrics = {}
        
        for horizon in horizons:
            target_col = f"future_return_{horizon}"
            pred_col = f"predicted_return_{horizon}"
            
            if target_col not in aligned_data.columns or pred_col not in aligned_data.columns:
                continue
                
            # Drop rows with NaN targets
            valid_data = aligned_data.dropna(subset=[target_col])
            
            if len(valid_data) < 10:
                logger.warning(f"Not enough valid data to evaluate horizon {horizon}")
                continue
                
            # Get actual and predicted values
            y_true = valid_data[target_col].values
            y_pred = valid_data[pred_col].values
            
            # Calculate metrics
            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            mae = mean_absolute_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)
            
            # Direction accuracy
            direction_accuracy = np.mean((y_true > 0) == (y_pred > 0))
            
            # Uncertainty evaluation
            if f"return_uncertainty_{horizon}" in valid_data.columns:
                uncertainty = valid_data[f"return_uncertainty_{horizon}"].values
                coverage_68 = np.mean(np.abs(y_true - y_pred) < uncertainty)
                coverage_95 = np.mean(np.abs(y_true - y_pred) < 2 * uncertainty)
            else:
                coverage_68 = None
                coverage_95 = None
                
            metrics[horizon] = {
                'rmse': rmse,
                'mae': mae,
                'r2': r2,
                'direction_accuracy': direction_accuracy,
                'coverage_68': coverage_68,
                'coverage_95': coverage_95,
                'samples': len(valid_data)
            }
            
        return metrics
        
    def _plot_feature_importance(self):
        """
        Plot and save feature importance charts for each horizon.
        """
        for horizon, importances in self.feature_importance.items():
            # Sort importances
            sorted_importances = sorted(importances.items(), key=lambda x: x[1], reverse=True)
            features = [x[0] for x in sorted_importances[:20]]  # Top 20 features
            values = [x[1] for x in sorted_importances[:20]]
            
            # Create plot
            plt.figure(figsize=(10, 8))
            plt.barh(range(len(features)), values, align='center')
            plt.yticks(range(len(features)), features)
            plt.xlabel('Importance')
            plt.title(f'Feature Importance for {horizon} Period Return Prediction')
            plt.tight_layout()
            
            # Save plot
            plot_dir = os.path.join(self.base_model_path, 'plots')
            os.makedirs(plot_dir, exist_ok=True)
            plt.savefig(os.path.join(plot_dir, f'feature_importance_return_{horizon}.png'))
            plt.close()
            
    def get_trade_recommendation(self, data, horizons=None, 
                                 min_return=0.005, min_sharpe=0.5,
                                 confidence_threshold=0.6):
        """
        Get trade recommendation based on return predictions.
        
        Args:
            data: DataFrame with OHLCV data and technical indicators
            horizons: List of horizons to consider
            min_return: Minimum expected return to consider a trade
            min_sharpe: Minimum Sharpe ratio to consider a trade
            confidence_threshold: Minimum confidence level
            
        Returns:
            Dictionary with trade recommendation
        """
        if horizons is None:
            horizons = self.prediction_horizons
            
        # Get return predictions
        predictions = self.predict_returns(data, horizons)
        
        if predictions is None or len(predictions) == 0:
            return None
            
        # Get the most recent prediction
        latest = predictions.iloc[-1].to_dict()
        
        # Find the best horizon based on risk-adjusted return
        best_horizon = None
        best_sharpe = -float('inf')
        
        for horizon in horizons:
            sharpe_col = f"return_sharpe_{horizon}"
            return_col = f"predicted_return_{horizon}"
            
            if sharpe_col not in latest or return_col not in latest:
                continue
                
            sharpe = latest[sharpe_col]
            expected_return = latest[return_col]
            
            # Check if this horizon is better than current best
            if sharpe > best_sharpe and abs(expected_return) > min_return and abs(sharpe) > min_sharpe:
                best_sharpe = sharpe
                best_horizon = horizon
                
        if best_horizon is None:
            return {
                'recommendation': 'NEUTRAL',
                'reason': 'No horizon meets the return and Sharpe criteria',
                'confidence': 0.0,
                'expected_return': 0.0,
                'uncertainty': 0.0,
                'horizon': None
            }
            
        # Get metrics for best horizon
        expected_return = latest[f"predicted_return_{best_horizon}"]
        uncertainty = latest[f"return_uncertainty_{best_horizon}"]
        lower_bound = latest[f"return_lower_bound_{best_horizon}"]
        upper_bound = latest[f"return_upper_bound_{best_horizon}"]
        sharpe = latest[f"return_sharpe_{best_horizon}"]
        
        # Determine direction and confidence
        if expected_return > min_return and lower_bound > 0:
            # Strong buy case: positive even at lower bound
            direction = "BUY"
            confidence = min(0.95, 0.7 + abs(sharpe) * 0.1)  # Cap at 0.95
        elif expected_return < -min_return and upper_bound < 0:
            # Strong sell case: negative even at upper bound
            direction = "SELL"
            confidence = min(0.95, 0.7 + abs(sharpe) * 0.1)  # Cap at 0.95
        elif expected_return > min_return:
            # Mild buy case
            direction = "BUY"
            confidence = 0.5 + abs(sharpe) * 0.1
        elif expected_return < -min_return:
            # Mild sell case
            direction = "SELL"
            confidence = 0.5 + abs(sharpe) * 0.1
        else:
            direction = "NEUTRAL"
            confidence = 0.0
            
        # Threshold confidence
        if confidence < confidence_threshold:
            direction = "NEUTRAL"
            confidence = 0.0
            
        # Calculate optimal position size based on Kelly criterion
        if direction in ["BUY", "SELL"]:
            # Kelly fraction = edge / odds = expected_return / variance
            kelly_fraction = abs(expected_return) / (uncertainty**2 + 1e-6)
            # Cap at 1.0 and scale by confidence
            kelly_fraction = min(1.0, kelly_fraction) * confidence
        else:
            kelly_fraction = 0.0
            
        # Create recommendation
        recommendation = {
            'recommendation': direction,
            'confidence': confidence,
            'expected_return': expected_return,
            'uncertainty': uncertainty,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'sharpe_ratio': sharpe,
            'horizon': best_horizon,
            'optimal_size': kelly_fraction
        }
        
        return recommendation
