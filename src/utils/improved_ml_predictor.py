"""
Improved Machine Learning Predictor for IQ 720 Trading Bot
This module addresses key issues in the original ML predictor:
1. Fixes data leakage problems
2. Implements proper time series handling
3. Adds model calibration for more reliable confidence scores
4. Improves feature engineering and selection
5. Adds proper uncertainty quantification
"""
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model, Model
from tensorflow.keras.layers import Dense, LSTM, Dropout, Conv1D, BatchNormalization, Input
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, VotingClassifier
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, brier_score_loss, log_loss
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import lightgbm as lgb
from pyod.models.iforest import IForest
import shap
import joblib
from typing import Tuple, List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import talib
import os
import matplotlib.pyplot as plt
import logging
from scipy import stats


class ImprovedMLPredictor:
    def __init__(self, lookback_periods: int = 100, sequence_length: int = 20):
        """
        Initialize the improved ML predictor with better defaults and configuration
        
        Args:
            lookback_periods: Number of periods to look back for feature generation
            sequence_length: Length of sequences for deep learning models
        """
        self.logger = logging.getLogger(__name__)
        self.lookback_periods = lookback_periods
        self.sequence_length = sequence_length
        self.models_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
        os.makedirs(self.models_path, exist_ok=True)
        
        # Base classifiers - simplified from original to reduce overfitting
        self.classifiers = {
            'random_forest': RandomForestClassifier(
                n_estimators=100,  # Reduced from 200
                max_depth=8,       # Reduced from 10
                random_state=42,
                class_weight='balanced'
            ),
            'xgboost': xgb.XGBClassifier(
                n_estimators=100,  # Reduced from 200
                learning_rate=0.05, # Reduced from 0.1
                max_depth=5,       # Reduced from 6
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            ),
            'lightgbm': lgb.LGBMClassifier(
                n_estimators=100,  # Reduced from 200
                learning_rate=0.05, # Reduced from 0.1
                max_depth=5,       # Reduced from 6
                random_state=42
            )
        }
        
        # Calibrated versions of classifiers (to be created during training)
        self.calibrated_classifiers = {}
        
        # Ensemble classifier
        self.ensemble_classifier = None
        
        # Deep learning models
        self.lstm_model = None
        
        # Regression model for price prediction
        self.price_predictor = GradientBoostingRegressor(
            n_estimators=100,    # Reduced from 200
            learning_rate=0.05,  # Reduced from 0.1
            max_depth=4,         # Reduced from 5
            random_state=42
        )
        
        # Feature processing
        self.feature_scaler = StandardScaler()
        self.price_scaler = MinMaxScaler(feature_range=(0, 1))
        
        # Anomaly detection
        self.anomaly_detector = IForest(contamination=0.05)
        
        # Model state
        self.is_trained = False
        self.min_confidence_threshold = 0.6  # Reduced from 0.7 to avoid overconfidence
        self.feature_importance = {}
        
        # Feature selection
        self.selected_features_idx = None
        self.feature_names = None
        
        # Performance tracking
        self.performance_history = {
            'accuracy': [],
            'precision': [],
            'recall': [],
            'f1': [],
            'brier_score': [],
            'log_loss': []
        }
        
        # SHAP explainer
        self.shap_explainer = None
        
        # Uncertainty estimation
        self.prediction_std = {}  # Store prediction standard deviations per model
        
    def _prepare_features_single_timepoint(self, data: pd.DataFrame, end_idx: int) -> np.ndarray:
        """
        Create features for a single timepoint without lookahead bias
        
        Args:
            data: DataFrame with OHLCV data
            end_idx: The index position to generate features for
            
        Returns:
            numpy array of features for the single timepoint
        """
        # Ensure we have enough history
        if end_idx < self.lookback_periods:
            return np.array([])
            
        # Get historical data up to this point only
        history = data.iloc[end_idx - self.lookback_periods:end_idx + 1]
        
        # Extract price data
        close_prices = history['close'].values
        open_prices = history['open'].values
        high_prices = history['high'].values
        low_prices = history['low'].values
        volumes = history['volume'].values
        
        features = []
        
        # Basic price features (normalized)
        features.append(close_prices[-1] / close_prices[-2] - 1)  # Last return
        features.append(open_prices[-1] / close_prices[-1] - 1)   # O/C ratio
        features.append(high_prices[-1] / close_prices[-1] - 1)   # H/C ratio
        features.append(low_prices[-1] / close_prices[-1] - 1)    # L/C ratio
        
        # Volume features
        recent_volume_avg = np.mean(volumes[-20:])
        if recent_volume_avg > 0:
            features.append(volumes[-1] / recent_volume_avg)  # Relative volume
        else:
            features.append(1.0)  # Default to neutral
        
        # Log returns over different timeframes
        for period in [1, 3, 5, 10, 20]:
            if period < len(close_prices):
                features.append(np.log(close_prices[-1] / close_prices[-period-1]))
        
        # Trend indicators - multiple timeframes
        for period in [10, 20, 50]:
            if len(close_prices) >= period:
                sma = talib.SMA(close_prices, timeperiod=period)[-1]
                ema = talib.EMA(close_prices, timeperiod=period)[-1]
                features.append(close_prices[-1] / sma - 1)  # Distance from SMA
                features.append(close_prices[-1] / ema - 1)  # Distance from EMA
                
        # Momentum indicators
        for period in [7, 14, 21]:
            if len(close_prices) >= period:
                rsi = talib.RSI(close_prices, timeperiod=period)[-1]
                features.append(rsi / 100.0)  # Normalize RSI to 0-1
                
                mom = talib.MOM(close_prices, timeperiod=period)[-1]
                features.append(mom / close_prices[-period-1])  # Normalized momentum
        
        # MACD
        if len(close_prices) >= 26:
            macd, signal, hist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
            features.append(macd[-1] / close_prices[-1])  # Normalized MACD
            features.append(signal[-1] / close_prices[-1])  # Normalized signal line
            features.append(hist[-1] / close_prices[-1])  # Normalized histogram
            
        # Stochastic oscillator
        if len(close_prices) >= 14:
            slowk, slowd = talib.STOCH(high_prices, low_prices, close_prices)
            features.append(slowk[-1] / 100.0)  # Normalized stochastic K
            features.append(slowd[-1] / 100.0)  # Normalized stochastic D
            
        # ATR - volatility
        for period in [7, 14]:
            if len(close_prices) >= period:
                atr = talib.ATR(high_prices, low_prices, close_prices, timeperiod=period)[-1]
                features.append(atr / close_prices[-1])  # Normalized ATR
        
        # Bollinger Bands
        for period in [20]:
            if len(close_prices) >= period:
                upper, middle, lower = talib.BBANDS(close_prices, timeperiod=period)
                features.append((close_prices[-1] - lower[-1]) / (upper[-1] - lower[-1] if upper[-1] > lower[-1] else 1))
                features.append((upper[-1] - lower[-1]) / middle[-1] if middle[-1] > 0 else 0)  # BB width
        
        # Add time-based features if available
        if isinstance(history.index, pd.DatetimeIndex):
            last_timestamp = history.index[-1]
            # Hour of day (cyclic encoding)
            features.append(np.sin(2 * np.pi * last_timestamp.hour / 24))
            features.append(np.cos(2 * np.pi * last_timestamp.hour / 24))
            # Day of week (cyclic encoding)
            features.append(np.sin(2 * np.pi * last_timestamp.dayofweek / 7))
            features.append(np.cos(2 * np.pi * last_timestamp.dayofweek / 7))
        
        # Clean and return
        feature_array = np.array(features)
        feature_array = np.nan_to_num(feature_array, nan=0)
        
        return feature_array
        
    def prepare_features(self, data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare features for all timepoints in the data without lookahead bias
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Tuple of (feature array, feature names)
        """
        if len(data) <= self.lookback_periods:
            self.logger.error(f"Not enough data for feature generation. Need at least {self.lookback_periods+1} points.")
            return np.array([]), []
            
        # Generate feature names based on first timepoint
        first_features = self._prepare_features_single_timepoint(data, self.lookback_periods)
        if len(first_features) == 0:
            return np.array([]), []
            
        # Pre-allocate feature array
        n_samples = len(data) - self.lookback_periods
        n_features = len(first_features)
        features = np.zeros((n_samples, n_features))
        
        # Generate features for each timepoint without lookahead
        for i in range(self.lookback_periods, len(data)):
            idx = i - self.lookback_periods  # Adjusted index for features array
            features[idx] = self._prepare_features_single_timepoint(data, i)
        
        # Generate feature names
        feature_names = self._generate_feature_names(n_features)
        
        return features, feature_names

    def prepare_labels(self, data: pd.DataFrame, forward_period: int = 5) -> Dict[str, np.ndarray]:
        """
        Create labels for ML models
        
        Args:
            data: DataFrame with OHLCV data
            forward_period: Number of periods to look ahead
            
        Returns:
            Dictionary with labels and mask for valid entries
        """
        # Skip the initial lookback period where we can't generate features
        prices = data['close'].iloc[self.lookback_periods:].values
        
        # Calculate future returns
        future_returns = np.zeros(len(prices))
        for i in range(len(prices) - forward_period):
            future_returns[i] = prices[i + forward_period] / prices[i] - 1
            
        # Binary direction labels (threshold at 0)
        binary_labels = (future_returns > 0).astype(int)
        
        # Create mask for valid labels (not last forward_period entries)
        valid_mask = np.ones_like(binary_labels, dtype=bool)
        valid_mask[-forward_period:] = False
        
        return {
            'binary': binary_labels,
            'returns': future_returns,
            'valid_mask': valid_mask
        }
        
    def train(self, historical_data: pd.DataFrame, forward_period: int = 5):
        """
        Train all ML models using proper time series cross-validation
        
        Args:
            historical_data: DataFrame with OHLCV data
            forward_period: Number of periods to look ahead for labels
        """
        self.logger.info("Preparing features and labels for training...")
        
        # Prepare features properly
        features, feature_names = self.prepare_features(historical_data)
        self.feature_names = feature_names
        
        if len(features) == 0:
            self.logger.error("Failed to prepare features")
            return
            
        # Prepare labels
        labels_dict = self.prepare_labels(historical_data, forward_period)
        binary_labels = labels_dict['binary']
        valid_mask = labels_dict['valid_mask']
        
        # Apply valid mask to features and labels
        features = features[valid_mask]
        binary_labels = binary_labels[valid_mask]
        
        if len(features) < 100:  # Need sufficient data for training
            self.logger.error(f"Not enough valid data points for training. Have {len(features)}, need at least 100.")
            return
            
        # Scale features
        self.feature_scaler.fit(features)
        features_scaled = self.feature_scaler.transform(features)
        
        # Feature selection (using Random Forest importance)
        self._select_features(features_scaled, binary_labels, feature_names)
        
        # Apply feature selection if available
        if self.selected_features_idx is not None:
            features_scaled = features_scaled[:, self.selected_features_idx]
            selected_feature_names = [feature_names[i] for i in self.selected_features_idx]
            self.logger.info(f"Selected {len(selected_feature_names)} features: {selected_feature_names}")
        
        # Use time series cross-validation (more folds than original)
        tscv = TimeSeriesSplit(n_splits=5, test_size=int(0.2 * len(features_scaled)))
        
        # Track predictions for each fold for later calibration
        all_val_probs = {name: np.array([]) for name in self.classifiers.keys()}
        all_val_labels = np.array([])
        
        # Train classical ML models with proper CV
        self.logger.info("Training ML models with time series cross-validation...")
        fold = 0
        
        for train_idx, test_idx in tscv.split(features_scaled):
            fold += 1
            self.logger.info(f"Training fold {fold}/5...")
            
            X_train = features_scaled[train_idx]
            y_train = binary_labels[train_idx]
            X_test = features_scaled[test_idx]
            y_test = binary_labels[test_idx]
            
            # Train each model on this fold
            for name, model in self.classifiers.items():
                # Train the model
                model.fit(X_train, y_train)
                
                # Get validation probabilities
                probs = model.predict_proba(X_test)[:, 1]
                all_val_probs[name] = np.append(all_val_probs[name], probs)
                
                if fold == 1:  # Only collect labels once
                    all_val_labels = np.append(all_val_labels, y_test)
                
                # Evaluate on this fold
                y_pred = model.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)
                self.logger.info(f"{name} fold {fold} accuracy: {accuracy:.4f}")
        
        # Calibrate each model using validation predictions
        self.logger.info("Calibrating models...")
        for name, model in self.classifiers.items():
            # Train a final model on all data
            model.fit(features_scaled, binary_labels)
            
            # Create and train a calibrator using out-of-fold predictions
            calibrated_model = self._calibrate_probabilities(
                all_val_probs[name], 
                all_val_labels,
                model
            )
            
            self.calibrated_classifiers[name] = calibrated_model
        
        # Create final ensemble
        self.logger.info("Creating ensemble model...")
        self._create_ensemble(features_scaled, binary_labels)
        
        # Train LSTM on entire dataset if we have enough data
        if len(features_scaled) >= 1000:
            self.logger.info("Training LSTM model...")
            self._train_lstm(features_scaled, binary_labels)
        
        # Train anomaly detector
        self.logger.info("Training anomaly detector...")
        self.anomaly_detector.fit(features_scaled)
        
        # Create SHAP explainer
        if 'random_forest' in self.classifiers:
            self.logger.info("Creating SHAP explainer...")
            self.shap_explainer = shap.TreeExplainer(self.classifiers['random_forest'])
        
        # Calculate overall performance metrics
        self._calculate_performance_metrics(features_scaled, binary_labels)
        
        # Set trained flag
        self.is_trained = True
        self.logger.info("Model training completed successfully")
        
    def _select_features(self, features: np.ndarray, labels: np.ndarray, feature_names: List[str], 
                       threshold: float = 0.01):
        """
        Select important features using Random Forest importance
        
        Args:
            features: Scaled feature array
            labels: Target labels
            feature_names: List of feature names
            threshold: Minimum importance threshold
        """
        # Create a simple RF model for feature selection
        selector = RandomForestClassifier(
            n_estimators=50, 
            max_depth=5,
            random_state=42
        )
        
        # Fit model
        selector.fit(features, labels)
        
        # Get feature importances
        importances = selector.feature_importances_
        
        # Store feature importance dict
        self.feature_importance = dict(zip(feature_names, importances))
        
        # Select features above threshold
        selected_idx = np.where(importances >= threshold)[0]
        
        # Ensure we have at least 10 features
        if len(selected_idx) < 10:
            # Get top 10 features by importance
            selected_idx = np.argsort(importances)[-10:]
            
        self.selected_features_idx = selected_idx
        
    def _calibrate_probabilities(self, val_probs: np.ndarray, val_labels: np.ndarray, 
                              base_model: object) -> object:
        """
        Calibrate model probabilities using isotonic regression
        
        Args:
            val_probs: Validation set probabilities
            val_labels: Validation set true labels
            base_model: Original trained model
            
        Returns:
            Calibrated model
        """
        # Create calibration model based on validation predictions
        if len(val_probs) >= 30:  # Need sufficient data for calibration
            from sklearn.isotonic import IsotonicRegression
            calibrator = IsotonicRegression(out_of_bounds='clip')
            calibrator.fit(val_probs, val_labels)
            
            # Create a wrapper that applies calibration to predictions
            class CalibratedWrapper:
                def __init__(self, base_model, calibrator):
                    self.base_model = base_model
                    self.calibrator = calibrator
                    
                def predict(self, X):
                    return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)
                    
                def predict_proba(self, X):
                    # Get raw probabilities from base model
                    raw_probs = self.base_model.predict_proba(X)[:, 1]
                    
                    # Calibrate probabilities
                    cal_probs = self.calibrator.predict(raw_probs)
                    
                    # Return in 2-column format expected by scikit-learn
                    return np.vstack((1 - cal_probs, cal_probs)).T
            
            return CalibratedWrapper(base_model, calibrator)
        else:
            return base_model  # Use uncalibrated model if not enough data
            
    def _create_ensemble(self, features: np.ndarray, labels: np.ndarray):
        """
        Create a more sophisticated ensemble model
        
        Args:
            features: Training features
            labels: Training labels
        """
        # Use calibrated models for the ensemble if available
        estimators = []
        for name, model in self.calibrated_classifiers.items():
            estimators.append((name, model))
        
        # If no calibrated models, use original models
        if not estimators:
            estimators = [(name, model) for name, model in self.classifiers.items()]
            
        # Create and train voting classifier with soft voting
        self.ensemble_classifier = VotingClassifier(estimators=estimators, voting='soft')
        self.ensemble_classifier.fit(features, labels)
            
    def _train_lstm(self, features: np.ndarray, labels: np.ndarray):
        """
        Train LSTM model for sequence prediction
        
        Args:
            features: Training features
            labels: Training labels
        """
        # Create sequences for LSTM
        sequences = []
        sequence_labels = []
        
        for i in range(len(features) - self.sequence_length + 1):
            sequences.append(features[i:i+self.sequence_length])
            sequence_labels.append(labels[i+self.sequence_length-1])
        
        sequences = np.array(sequences)
        sequence_labels = np.array(sequence_labels)
        
        # Split into train/validation
        split_idx = int(0.8 * len(sequences))
        train_sequences = sequences[:split_idx]
        train_labels = sequence_labels[:split_idx]
        val_sequences = sequences[split_idx:]
        val_labels = sequence_labels[split_idx:]
        
        # Define LSTM model
        self.lstm_model = Sequential([
            LSTM(32, input_shape=(self.sequence_length, features.shape[1]), return_sequences=True),
            BatchNormalization(),
            Dropout(0.3),
            LSTM(16),
            BatchNormalization(),
            Dropout(0.3),
            Dense(8, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        self.lstm_model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        # Train model
        early_stopping = EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True
        )
        
        self.lstm_model.fit(
            train_sequences, train_labels,
            validation_data=(val_sequences, val_labels),
            epochs=50,
            batch_size=32,
            callbacks=[early_stopping],
            verbose=1
        )
        
    def _calculate_performance_metrics(self, features: np.ndarray, labels: np.ndarray):
        """
        Calculate comprehensive performance metrics using cross-validation
        
        Args:
            features: Training features
            labels: Training labels
        """
        tscv = TimeSeriesSplit(n_splits=5)
        
        metrics = {
            'accuracy': [],
            'precision': [],
            'recall': [],
            'f1': [],
            'brier_score': [],
            'log_loss': []
        }
        
        for train_idx, test_idx in tscv.split(features):
            X_train = features[train_idx]
            y_train = labels[train_idx]
            X_test = features[test_idx]
            y_test = labels[test_idx]
            
            # Train a simple model for evaluation
            model = self.classifiers['random_forest']
            model.fit(X_train, y_train)
            
            # Get predictions
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1]
            
            # Calculate metrics
            metrics['accuracy'].append(accuracy_score(y_test, y_pred))
            metrics['precision'].append(precision_score(y_test, y_pred, zero_division=0))
            metrics['recall'].append(recall_score(y_test, y_pred, zero_division=0))
            metrics['f1'].append(f1_score(y_test, y_pred, zero_division=0))
            metrics['brier_score'].append(brier_score_loss(y_test, y_proba))
            metrics['log_loss'].append(log_loss(y_test, y_proba))
        
        # Store average metrics
        for metric, values in metrics.items():
            self.performance_history[metric].append(np.mean(values))
            self.logger.info(f"Cross-validation {metric}: {np.mean(values):.4f} ± {np.std(values):.4f}")
    
    def predict(self, current_data: pd.DataFrame) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Make trading predictions with uncertainty estimation
        
        Args:
            current_data: DataFrame with recent OHLCV data
            
        Returns:
            Tuple of (prediction, confidence, details dictionary)
        """
        if not self.is_trained:
            self.logger.warning("Models not trained. Attempting to load saved models...")
            try:
                self.load_models()
                if not self.is_trained:
                    return False, 0.0, {"error": "Models not trained or loaded"}
            except Exception as e:
                self.logger.error(f"Failed to load models: {e}")
                return False, 0.0, {"error": "Failed to load models"}
        
        # Prepare features
        features, _ = self.prepare_features(current_data)
        if len(features) == 0:
            return False, 0.0, {"error": "Failed to prepare features"}
        
        # Get the most recent feature vector
        recent_features = features[-1:]
        
        # Scale features
        recent_features_scaled = self.feature_scaler.transform(recent_features)
        
        # Apply feature selection if available
        if self.selected_features_idx is not None:
            recent_features_scaled = recent_features_scaled[:, self.selected_features_idx]
        
        # Check for anomalies
        is_anomaly = self.anomaly_detector.predict(recent_features_scaled)[0] == 1
        anomaly_score = float(self.anomaly_detector.decision_function(recent_features_scaled)[0])
        
        # Get predictions from all models
        predictions = {}
        probabilities = {}
        
        # Get predictions from calibrated models
        for name, model in self.calibrated_classifiers.items():
            try:
                pred = model.predict(recent_features_scaled)[0]
                prob = model.predict_proba(recent_features_scaled)[0][1]
                predictions[name] = bool(pred)
                probabilities[name] = float(prob)
            except Exception as e:
                self.logger.error(f"Error predicting with {name}: {e}")
                predictions[name] = False
                probabilities[name] = 0.0
        
        # Get ensemble prediction
        ensemble_pred = False
        ensemble_prob = 0.0
        
        if self.ensemble_classifier is not None:
            try:
                ensemble_pred = bool(self.ensemble_classifier.predict(recent_features_scaled)[0])
                ensemble_prob = float(self.ensemble_classifier.predict_proba(recent_features_scaled)[0][1])
                predictions['ensemble'] = ensemble_pred
                probabilities['ensemble'] = ensemble_prob
            except Exception as e:
                self.logger.error(f"Error predicting with ensemble: {e}")
        
        # Get LSTM prediction if available and we have enough data
        if self.lstm_model is not None and len(current_data) >= self.lookback_periods + self.sequence_length:
            try:
                # Prepare sequence data
                seq_features, _ = self.prepare_features(current_data.iloc[-(self.lookback_periods + self.sequence_length):])
                if len(seq_features) >= self.sequence_length:
                    seq_features_scaled = self.feature_scaler.transform(seq_features[-self.sequence_length:])
                    
                    # Apply feature selection if available
                    if self.selected_features_idx is not None:
                        seq_features_scaled = seq_features_scaled[:, self.selected_features_idx]
                    
                    seq_data = np.expand_dims(seq_features_scaled, axis=0)
                    lstm_prob = float(self.lstm_model.predict(seq_data, verbose=0)[0][0])
                    lstm_pred = bool(lstm_prob > 0.5)
                    predictions['lstm'] = lstm_pred
                    probabilities['lstm'] = lstm_prob
            except Exception as e:
                self.logger.error(f"Error predicting with LSTM: {e}")
        
        # Calculate prediction uncertainty based on variance between models
        prob_values = list(probabilities.values())
        mean_prob = np.mean(prob_values) if prob_values else 0.5
        std_prob = np.std(prob_values) if len(prob_values) > 1 else 0.5
        
        # Adjust confidence based on uncertainty (higher std = lower confidence)
        uncertainty_factor = 1.0 - min(std_prob * 2, 0.5)  # Convert std to confidence reduction
        
        # Final prediction and confidence
        final_prediction = ensemble_pred if 'ensemble' in predictions else (mean_prob > 0.5)
        raw_confidence = ensemble_prob if 'ensemble' in probabilities else mean_prob
        
        # Adjust confidence based on uncertainty
        adjusted_confidence = raw_confidence * uncertainty_factor
        
        # If prediction is very uncertain, reduce confidence further
        if abs(raw_confidence - 0.5) < 0.15:  # Close to 50/50
            adjusted_confidence *= 0.8
        
        # If anomaly detected, reduce confidence
        if is_anomaly:
            adjusted_confidence *= 0.7
        
        # Generate feature importance/explanation
        top_features = self._explain_prediction(recent_features_scaled[0])
        
        # Prepare detailed results
        prediction_details = {
            'model_predictions': predictions,
            'model_probabilities': probabilities,
            'raw_confidence': float(raw_confidence),
            'adjusted_confidence': float(adjusted_confidence),
            'uncertainty': float(std_prob),
            'top_features': top_features,
            'is_anomaly': bool(is_anomaly),
            'anomaly_score': float(anomaly_score),
            'timestamp': datetime.now().isoformat()
        }
        
        return final_prediction, adjusted_confidence, prediction_details
        
    def _explain_prediction(self, features: np.ndarray) -> Dict[str, float]:
        """
        Generate explanation for the current prediction
        
        Args:
            features: Feature vector to explain
            
        Returns:
            Dictionary mapping feature names to importance values
        """
        # If SHAP explainer available, use it
        if self.shap_explainer is not None:
            try:
                # Get SHAP values
                shap_values = self.shap_explainer.shap_values(features.reshape(1, -1))[1][0]
                
                # Map to feature names
                feature_names = self._get_feature_names()
                if len(feature_names) > len(features):
                    feature_names = feature_names[:len(features)]
                elif len(feature_names) < len(features):
                    feature_names.extend([f'Feature_{i}' for i in range(len(feature_names), len(features))])
                
                # Get top features by absolute SHAP value
                feature_impacts = [(name, float(impact)) for name, impact in zip(feature_names, shap_values)]
                feature_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
                
                return dict(feature_impacts[:5])  # Return top 5 features
                
            except Exception as e:
                self.logger.error(f"Error generating SHAP explanation: {e}")
        
        # Fallback to feature importance if available
        if self.feature_importance:
            # Sort by importance
            sorted_features = sorted(
                self.feature_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            return dict(sorted_features[:5])  # Return top 5 features
        
        # Return empty dict if no explanation available
        return {}
        
    def _get_feature_names(self) -> List[str]:
        """
        Get feature names, accounting for feature selection
        
        Returns:
            List of selected feature names
        """
        if self.feature_names:
            if self.selected_features_idx is not None:
                return [self.feature_names[i] for i in self.selected_features_idx]
            return self.feature_names
        
        # Generate generic feature names
        return [f'Feature_{i}' for i in range(100)]
        
    def validate_prediction(self, prediction: bool, confidence: float, 
                          market_regime: str, session: str, 
                          anomaly_detected: bool = False) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Validate prediction against market conditions with more sophisticated adjustments
        
        Args:
            prediction: The raw prediction (True for buy)
            confidence: The raw confidence score
            market_regime: Current market regime
            session: Current trading session
            anomaly_detected: Whether an anomaly was detected
            
        Returns:
            Tuple of (validated prediction, adjusted confidence, details)
        """
        if confidence < self.min_confidence_threshold:
            return False, confidence, {"reason": "Below confidence threshold"}
        
        # More nuanced regime multipliers
        regime_multipliers = {
            'STRONG_TREND_UP': 1.1 if prediction else 0.8,    # Good for buys, bad for sells
            'TREND_UP': 1.05 if prediction else 0.9,          # Slightly good for buys
            'STRONG_TREND_DOWN': 0.8 if prediction else 1.1,  # Good for sells, bad for buys
            'TREND_DOWN': 0.9 if prediction else 1.05,        # Slightly good for sells
            'CHOPPY': 0.8,                                    # Bad for all signals
            'RANGING': 0.9,                                   # Somewhat bad for all signals
            'HIGH_VOLATILITY': 0.85,                          # Bad for all signals
            'LOW_VOLATILITY': 1.05                            # Slightly good for all signals
        }
        
        # Session multipliers with more nuance
        session_multipliers = {
            'london_ny_overlap': 1.1,    # Highest liquidity, good for trading
            'london_open': 1.05,         # Good liquidity
            'ny_session': 1.0,           # Standard liquidity
            'asian_session': 0.9,        # Lower liquidity
            'weekend': 0.7               # Very low liquidity, avoid trading
        }
        
        # Apply adjustments with additive logic instead of multiplicative to avoid extreme values
        base_confidence = confidence
        confidence_adjustments = []
        applied_adjustments = {}
        
        # Market regime adjustment
        if market_regime in regime_multipliers:
            factor = regime_multipliers[market_regime] - 1.0  # Convert to adjustment
            confidence_adjustments.append(factor * base_confidence)
            applied_adjustments['regime'] = factor
        
        # Session adjustment
        if session in session_multipliers:
            factor = session_multipliers[session] - 1.0  # Convert to adjustment
            confidence_adjustments.append(factor * base_confidence)
            applied_adjustments['session'] = factor
        
        # Anomaly adjustment
        if anomaly_detected:
            factor = -0.2  # Direct reduction
            confidence_adjustments.append(factor * base_confidence)
            applied_adjustments['anomaly'] = factor
            
        # Contra-trend protection
        if (market_regime == 'STRONG_TREND_DOWN' and prediction) or \
           (market_regime == 'STRONG_TREND_UP' and not prediction):
            factor = -0.15  # Direct reduction
            confidence_adjustments.append(factor * base_confidence)
            applied_adjustments['contra_trend'] = factor
        
        # Apply all adjustments
        adjusted_confidence = base_confidence + sum(confidence_adjustments)
        
        # Ensure confidence stays in valid range
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))
        
        # Final validation
        is_valid = adjusted_confidence >= self.min_confidence_threshold
        
        validation_details = {
            'original_confidence': float(base_confidence),
            'adjusted_confidence': float(adjusted_confidence),
            'applied_adjustments': applied_adjustments,
            'is_valid': is_valid
        }
        
        return is_valid, adjusted_confidence, validation_details
    
    def _generate_feature_names(self, n_features: int) -> List[str]:
        """
        Generate feature names based on what we created in prepare_features.
        
        Args:
            n_features: Number of features
            
        Returns:
            List of feature names
        """
        base_names = [
            'Return_1', 'OC_Ratio', 'HC_Ratio', 'LC_Ratio', 'Rel_Volume',
            'LogRet_1', 'LogRet_3', 'LogRet_5', 'LogRet_10', 'LogRet_20',
            'SMA10_Dist', 'EMA10_Dist', 'SMA20_Dist', 'EMA20_Dist', 'SMA50_Dist', 'EMA50_Dist',
            'RSI_7', 'MOM_7', 'RSI_14', 'MOM_14', 'RSI_21', 'MOM_21',
            'MACD', 'Signal', 'Hist',
            'StochK', 'StochD',
            'ATR_7', 'ATR_14',
            'BB_Position', 'BB_Width',
            'Sin_Hour', 'Cos_Hour', 'Sin_Day', 'Cos_Day'
        ]
        
        # If we need more names than we have in base_names, add generic ones
        if n_features > len(base_names):
            for i in range(len(base_names), n_features):
                base_names.append(f'Feature_{i}')
        
        # If we have more names than features, truncate
        return base_names[:n_features]
        
    def save_models(self):
        """Save all trained models to disk."""
        if not self.is_trained:
            return
            
        # Create directories if they don't exist
        model_path = os.path.join(self.models_path, 'improved_models')
        os.makedirs(model_path, exist_ok=True)
        
        # Save base classifiers
        for name, model in self.classifiers.items():
            joblib.dump(model, os.path.join(model_path, f"{name}_classifier.joblib"))
            
        # Save calibrated classifiers if available
        for name, model in self.calibrated_classifiers.items():
            joblib.dump(model, os.path.join(model_path, f"{name}_calibrated.joblib"))
            
        # Save ensemble model
        if self.ensemble_classifier is not None:
            joblib.dump(self.ensemble_classifier, os.path.join(model_path, "ensemble_classifier.joblib"))
            
        # Save LSTM model if available
        if self.lstm_model is not None:
            self.lstm_model.save(os.path.join(model_path, "lstm_model.h5"))
            
        # Save anomaly detector
        joblib.dump(self.anomaly_detector, os.path.join(model_path, "anomaly_detector.joblib"))
            
        # Save scalers
        joblib.dump(self.feature_scaler, os.path.join(model_path, "feature_scaler.joblib"))
        
        # Save feature information
        feature_info = {
            'feature_importance': self.feature_importance,
            'selected_features_idx': self.selected_features_idx,
            'feature_names': self.feature_names
        }
        joblib.dump(feature_info, os.path.join(model_path, "feature_info.joblib"))
        
        # Save performance history
        joblib.dump(self.performance_history, os.path.join(model_path, "performance_history.joblib"))
        
        self.logger.info(f"Models saved to {model_path}")
        
    def load_models(self):
        """Load all models from disk."""
        model_path = os.path.join(self.models_path, 'improved_models')
        
        if not os.path.exists(model_path):
            self.logger.warning(f"Model directory {model_path} not found")
            return
        
        try:
            # Load base classifiers
            for name in self.classifiers.keys():
                model_file = os.path.join(model_path, f"{name}_classifier.joblib")
                if os.path.exists(model_file):
                    self.classifiers[name] = joblib.load(model_file)
                    
            # Load calibrated classifiers
            for name in self.classifiers.keys():
                model_file = os.path.join(model_path, f"{name}_calibrated.joblib")
                if os.path.exists(model_file):
                    self.calibrated_classifiers[name] = joblib.load(model_file)
                    
            # Load ensemble model
            ensemble_file = os.path.join(model_path, "ensemble_classifier.joblib")
            if os.path.exists(ensemble_file):
                self.ensemble_classifier = joblib.load(ensemble_file)
                
            # Load LSTM model if available
            lstm_file = os.path.join(model_path, "lstm_model.h5")
            if os.path.exists(lstm_file):
                self.lstm_model = load_model(lstm_file)
                
            # Load anomaly detector
            anomaly_file = os.path.join(model_path, "anomaly_detector.joblib")
            if os.path.exists(anomaly_file):
                self.anomaly_detector = joblib.load(anomaly_file)
                
            # Load scalers
            scaler_file = os.path.join(model_path, "feature_scaler.joblib")
            if os.path.exists(scaler_file):
                self.feature_scaler = joblib.load(scaler_file)
                
            # Load feature information
            feature_file = os.path.join(model_path, "feature_info.joblib")
            if os.path.exists(feature_file):
                feature_info = joblib.load(feature_file)
                self.feature_importance = feature_info.get('feature_importance', {})
                self.selected_features_idx = feature_info.get('selected_features_idx')
                self.feature_names = feature_info.get('feature_names')
                
            # Load performance history
            perf_file = os.path.join(model_path, "performance_history.joblib")
            if os.path.exists(perf_file):
                self.performance_history = joblib.load(perf_file)
                
            self.is_trained = True
            self.logger.info("Models loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
            self.is_trained = False
