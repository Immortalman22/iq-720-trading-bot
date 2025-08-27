"""
Machine Learning Module for EUR/USD Trading
Implements advanced ML models for pattern recognition and price prediction.
Features:
- Ensemble learning with multiple model architectures
- Deep learning sequence models for time series forecasting
- Explainable AI for model interpretability
- Anomaly detection for market regime changes
- Feature importance analysis
- Hyperparameter optimization
"""
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model, Model
from tensorflow.keras.layers import Dense, LSTM, Dropout, Conv1D, BatchNormalization, Input
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor, VotingClassifier
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, mean_squared_error
import xgboost as xgb
import lightgbm as lgb
from pyod.models.iforest import IForest
import shap
import optuna
from optuna.integration import TFKerasPruningCallback
import joblib
from typing import Tuple, List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import talib
import os
import matplotlib.pyplot as plt
import logging

class MLPredictor:
    def __init__(self, lookback_periods: int = 100, sequence_length: int = 20):
        self.logger = logging.getLogger(__name__)
        self.lookback_periods = lookback_periods
        self.sequence_length = sequence_length
        self.models_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
        os.makedirs(self.models_path, exist_ok=True)
        
        # Multiple models for ensemble predictions
        self.classifiers = {
            'random_forest': RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            ),
            'xgboost': xgb.XGBClassifier(
                n_estimators=200, 
                learning_rate=0.1,
                max_depth=6,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            ),
            'lightgbm': lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )
        }
        
        # Ensemble classifier
        self.ensemble_classifier = None
        
        # Deep learning models
        self.lstm_model = None
        self.cnn_model = None
        
        # Regression models
        self.price_predictor = GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        # Feature processing
        self.feature_scaler = StandardScaler()
        self.price_scaler = MinMaxScaler(feature_range=(0, 1))
        
        # Anomaly detection for market regime changes
        self.anomaly_detector = IForest(contamination=0.05)
        
        # Model state
        self.is_trained = False
        self.min_confidence_threshold = 0.7
        self.feature_importance = {}
        
        # SHAP explainer
        self.shap_explainer = None
        
    def prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """
        Create advanced feature set from price data.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            numpy array of features
        """
        features = []
        
        # Ensure we have all needed columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in data.columns:
                self.logger.error(f"Missing required column: {col}")
                return np.array([])
        
        # Extract price data
        close_prices = data['close'].values
        open_prices = data['open'].values
        high_prices = data['high'].values
        low_prices = data['low'].values
        volumes = data['volume'].values
        
        # Basic price features
        features.append(close_prices)
        features.append(open_prices / close_prices - 1)  # O/C ratio
        features.append(high_prices / close_prices - 1)  # H/C ratio
        features.append(low_prices / close_prices - 1)   # L/C ratio
        features.append(volumes / np.mean(volumes[-20:]))  # Relative volume
        
        # Log returns over different timeframes
        for period in [1, 3, 5, 10]:
            features.append(np.log(close_prices[period:] / close_prices[:-period] if period < len(close_prices) else np.zeros_like(close_prices)))
        
        # Trend indicators - multiple timeframes
        for period in [10, 20, 50, 100]:
            if len(close_prices) >= period:
                features.append(talib.SMA(close_prices, timeperiod=period))
                features.append(talib.EMA(close_prices, timeperiod=period))
                # Distance from MA
                sma = talib.SMA(close_prices, timeperiod=period)
                features.append((close_prices - sma) / sma)
        
        # Crossover signals
        sma20 = talib.SMA(close_prices, timeperiod=20)
        sma50 = talib.SMA(close_prices, timeperiod=50)
        features.append((sma20 - sma50) / close_prices)  # Normalized crossover
        
        # Momentum indicators
        for period in [7, 14, 21]:
            features.append(talib.RSI(close_prices, timeperiod=period))
            features.append(talib.MOM(close_prices, timeperiod=period))
            
        # MACD with different parameters
        for (fast, slow, signal) in [(12, 26, 9), (8, 21, 5)]:
            macd_line, signal_line, hist = talib.MACD(close_prices, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            features.append(macd_line)
            features.append(signal_line)
            features.append(hist)
        
        # Stochastic oscillator
        slowk, slowd = talib.STOCH(high_prices, low_prices, close_prices)
        features.append(slowk)
        features.append(slowd)
        
        # Volatility indicators
        for period in [7, 14, 21]:
            features.append(talib.ATR(high_prices, low_prices, close_prices, timeperiod=period))
        
        # Bollinger Bands
        for period in [10, 20, 40]:
            upper, middle, lower = talib.BBANDS(close_prices, timeperiod=period)
            features.append((close_prices - lower) / (upper - lower))  # BB position
            features.append((upper - lower) / middle)  # BB width
        
        # Volume indicators
        features.append(talib.OBV(close_prices, volumes))
        features.append(talib.AD(high_prices, low_prices, close_prices, volumes))
        
        # Price patterns
        pattern_funcs = [
            talib.CDLENGULFING,
            talib.CDLHAMMER,
            talib.CDLHARAMI,
            talib.CDLMARUBOZU,
            talib.CDL3WHITESOLDIERS,
            talib.CDL3BLACKCROWS,
            talib.CDLEVENINGSTAR,
            talib.CDLMORNINGSTAR,
            talib.CDLSHOOTINGSTAR,
            talib.CDLDOJI
        ]
        for func in pattern_funcs:
            pattern = func(open_prices, high_prices, low_prices, close_prices)
            features.append(pattern)
        
        # Time-based features
        if isinstance(data.index, pd.DatetimeIndex):
            timestamps = data.index
        else:
            # Try to convert to datetime if not already
            try:
                timestamps = pd.to_datetime(data.index)
            except:
                # Use integer values if conversion not possible
                timestamps = np.arange(len(data))
                self.logger.warning("Could not convert index to datetime, using integer sequence instead")
        
        # Check if timestamps is a DatetimeIndex before extracting time features
        if isinstance(timestamps, pd.DatetimeIndex):
            features.append(timestamps.hour.values)
            features.append(timestamps.dayofweek.values)
            features.append(np.sin(2 * np.pi * timestamps.dayofweek.values / 7))  # Cyclical encoding for day of week
            features.append(np.cos(2 * np.pi * timestamps.dayofweek.values / 7))
            features.append(np.sin(2 * np.pi * timestamps.hour.values / 24))      # Cyclical encoding for hour
            features.append(np.cos(2 * np.pi * timestamps.hour.values / 24))
        
        # Stack and clean features
        feature_array = np.column_stack([f for f in features if len(f) == len(close_prices)])
        feature_array = np.nan_to_num(feature_array, nan=0)
        
        return feature_array
        
    def prepare_labels(self, data: pd.DataFrame, forward_period: int = 5, threshold: float = 0.0) -> Dict[str, np.ndarray]:
        """
        Create multi-purpose labels for training different models:
        - Binary direction prediction (1 for price increase, 0 for decrease)
        - Price change magnitude (percent change)
        - Multi-class price movement (strong up, up, neutral, down, strong down)
        
        Args:
            data: DataFrame with price data
            forward_period: Number of periods to look ahead
            threshold: Minimum change threshold to consider significant
            
        Returns:
            Dictionary of labels arrays for different models
        """
        # Calculate future returns
        future_returns = data['close'].pct_change(forward_period).shift(-forward_period)
        
        # Binary direction labels
        binary_labels = (future_returns > threshold).astype(int)
        
        # Multi-class labels based on magnitude
        multiclass_labels = np.zeros_like(future_returns)
        multiclass_labels[(future_returns > 0.01)] = 2  # Strong up
        multiclass_labels[(future_returns > threshold) & (future_returns <= 0.01)] = 1  # Up
        multiclass_labels[(future_returns < -0.01)] = -2  # Strong down
        multiclass_labels[(future_returns < -threshold) & (future_returns >= -0.01)] = -1  # Down
        
        # Create mask for valid labels (not NaN)
        valid_mask = ~np.isnan(future_returns)
        
        return {
            'binary': binary_labels[valid_mask],
            'multiclass': multiclass_labels[valid_mask],
            'regression': future_returns.values[valid_mask],
            'valid_mask': valid_mask
        }
    
    def prepare_sequences(self, features: np.ndarray, sequence_length: int) -> np.ndarray:
        """
        Prepare sequence data for LSTM/CNN models.
        
        Args:
            features: 2D array of features
            sequence_length: Length of sequence for each sample
            
        Returns:
            3D array of shape (samples, sequence_length, features)
        """
        n_samples = features.shape[0] - sequence_length + 1
        n_features = features.shape[1]
        
        sequences = np.zeros((n_samples, sequence_length, n_features))
        
        for i in range(n_samples):
            sequences[i] = features[i:i+sequence_length]
            
        return sequences
    
    def build_lstm_model(self, input_shape: Tuple[int, int]) -> Model:
        """
        Build a deep LSTM model for sequence prediction.
        
        Args:
            input_shape: Tuple of (sequence_length, n_features)
            
        Returns:
            Compiled Keras model
        """
        inputs = Input(shape=input_shape)
        
        # First LSTM layer with batch normalization
        x = LSTM(64, return_sequences=True)(inputs)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        
        # Second LSTM layer
        x = LSTM(32)(x)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        
        # Output layers
        x = Dense(16, activation='relu')(x)
        outputs = Dense(1, activation='sigmoid')(x)
        
        model = Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def build_cnn_model(self, input_shape: Tuple[int, int]) -> Model:
        """
        Build a 1D CNN model for sequence classification.
        
        Args:
            input_shape: Tuple of (sequence_length, n_features)
            
        Returns:
            Compiled Keras model
        """
        inputs = Input(shape=input_shape)
        
        # Conv layers with different filter sizes
        x1 = Conv1D(filters=32, kernel_size=3, activation='relu')(inputs)
        x1 = BatchNormalization()(x1)
        x1 = tf.keras.layers.GlobalMaxPooling1D()(x1)
        
        x2 = Conv1D(filters=32, kernel_size=5, activation='relu')(inputs)
        x2 = BatchNormalization()(x2)
        x2 = tf.keras.layers.GlobalMaxPooling1D()(x2)
        
        # Combine features
        x = tf.keras.layers.concatenate([x1, x2])
        x = Dense(32, activation='relu')(x)
        x = Dropout(0.2)(x)
        outputs = Dense(1, activation='sigmoid')(x)
        
        model = Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
        
    def train(self, historical_data: pd.DataFrame, optimize_hyperparams: bool = False):
        """
        Train all machine learning models on historical data.
        
        Args:
            historical_data: DataFrame with OHLCV data
            optimize_hyperparams: Whether to use hyperparameter optimization
        """
        self.logger.info("Preparing features and labels for training...")
        
        # Prepare features
        features = self.prepare_features(historical_data)
        if len(features) == 0:
            self.logger.error("Failed to prepare features")
            return
            
        # Prepare labels
        labels_dict = self.prepare_labels(historical_data, forward_period=5, threshold=0.0001)
        
        # Filter valid rows
        valid_mask = labels_dict['valid_mask']
        features = features[:-5]  # Remove last 5 rows where we don't have future data
        
        if len(features) < self.lookback_periods:
            self.logger.error(f"Not enough data for training. Need at least {self.lookback_periods} rows.")
            return
            
        # Scale features
        self.feature_scaler.fit(features)
        features_scaled = self.feature_scaler.transform(features)
        
        # Scale prices for regression
        prices = historical_data['close'].values[:-5]
        self.price_scaler.fit(prices.reshape(-1, 1))
        
        # For deep learning models, prepare sequence data
        sequence_data = self.prepare_sequences(features_scaled, self.sequence_length)
        sequence_labels = labels_dict['binary'][self.sequence_length-1:]
        
        # Use time series cross-validation
        tscv = TimeSeriesSplit(n_splits=5)
        cv_scores = {model: [] for model in self.classifiers.keys()}
        cv_scores.update({'lstm': [], 'cnn': [], 'ensemble': []})
        
        # Train classical ML models
        self.logger.info("Training classical ML models...")
        for train_idx, test_idx in tscv.split(features_scaled):
            X_train = features_scaled[train_idx]
            y_train = labels_dict['binary'][train_idx]
            X_test = features_scaled[test_idx]
            y_test = labels_dict['binary'][test_idx]
            
            # Train each model
            for name, model in self.classifiers.items():
                if optimize_hyperparams and name == 'xgboost':
                    # Example of hyperparameter optimization for XGBoost
                    model = self._optimize_xgboost(X_train, y_train)
                    self.classifiers[name] = model
                else:
                    model.fit(X_train, y_train)
                
                # Evaluate
                y_pred = model.predict(X_test)
                score = accuracy_score(y_test, y_pred)
                cv_scores[name].append(score)
                
            # Train price predictor on positive samples only
            mask = y_train == 1
            if np.any(mask):
                self.price_predictor.fit(
                    X_train[mask],
                    prices[train_idx][mask]
                )
        
        # Create and train ensemble model
        self.logger.info("Creating ensemble model...")
        self.ensemble_classifier = VotingClassifier(
            estimators=[(name, model) for name, model in self.classifiers.items()],
            voting='soft'
        )
        self.ensemble_classifier.fit(features_scaled, labels_dict['binary'])
        
        # Train deep learning models if we have enough data
        if len(sequence_data) >= 100:  # Minimum for deep learning
            self.logger.info("Training deep learning models...")
            
            # Split sequence data
            train_size = int(0.8 * len(sequence_data))
            seq_X_train = sequence_data[:train_size]
            seq_y_train = sequence_labels[:train_size]
            seq_X_val = sequence_data[train_size:]
            seq_y_val = sequence_labels[train_size:]
            
            # LSTM model
            self.lstm_model = self.build_lstm_model((self.sequence_length, features_scaled.shape[1]))
            early_stopping = EarlyStopping(monitor='val_loss', patience=5)
            self.lstm_model.fit(
                seq_X_train, seq_y_train,
                validation_data=(seq_X_val, seq_y_val),
                epochs=50,
                batch_size=32,
                callbacks=[early_stopping],
                verbose=0
            )
            
            # CNN model
            self.cnn_model = self.build_cnn_model((self.sequence_length, features_scaled.shape[1]))
            self.cnn_model.fit(
                seq_X_train, seq_y_train,
                validation_data=(seq_X_val, seq_y_val),
                epochs=50,
                batch_size=32,
                callbacks=[early_stopping],
                verbose=0
            )
        
        # Train anomaly detector
        self.logger.info("Training anomaly detector...")
        self.anomaly_detector.fit(features_scaled)
        
        # Create SHAP explainer
        self.logger.info("Creating SHAP explainer...")
        self.shap_explainer = shap.TreeExplainer(self.classifiers['random_forest'])
        
        # Calculate and store feature importance
        feature_names = self._generate_feature_names(features_scaled.shape[1])
        self.feature_importance = dict(zip(
            feature_names,
            self.classifiers['random_forest'].feature_importances_
        ))
        
        # Log training results
        for model, scores in cv_scores.items():
            if scores:
                self.logger.info(f"{model} CV accuracy: {np.mean(scores):.4f} ± {np.std(scores):.4f}")
        
        # Save models
        self.save_models()
        
        self.is_trained = True
        self.logger.info("Model training completed successfully")
    
    def _optimize_xgboost(self, X_train, y_train):
        """
        Optimize XGBoost hyperparameters using Optuna.
        """
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 5),
                'use_label_encoder': False,
                'eval_metric': 'logloss',
                'random_state': 42
            }
            
            # Create time series splits for CV
            tscv = TimeSeriesSplit(n_splits=3)
            scores = []
            
            for train_idx, val_idx in tscv.split(X_train):
                X_tr = X_train[train_idx]
                y_tr = y_train[train_idx]
                X_val = X_train[val_idx]
                y_val = y_train[val_idx]
                
                model = xgb.XGBClassifier(**params)
                model.fit(X_tr, y_tr)
                y_pred = model.predict(X_val)
                score = accuracy_score(y_val, y_pred)
                scores.append(score)
            
            return np.mean(scores)
        
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=20)
        
        # Get best parameters and create model
        best_params = study.best_params
        best_params.update({
            'use_label_encoder': False,
            'eval_metric': 'logloss',
            'random_state': 42
        })
        
        return xgb.XGBClassifier(**best_params)
    
    def _generate_feature_names(self, n_features: int) -> List[str]:
        """Generate feature names based on what we created in prepare_features."""
        # This is a best-effort attempt to match features with names
        base_names = [
            'Close', 'O/C_Ratio', 'H/C_Ratio', 'L/C_Ratio', 'Rel_Volume',
            'LogRet1', 'LogRet3', 'LogRet5', 'LogRet10',
            'SMA10', 'EMA10', 'SMA10_Dist',
            'SMA20', 'EMA20', 'SMA20_Dist',
            'SMA50', 'EMA50', 'SMA50_Dist',
            'SMA100', 'EMA100', 'SMA100_Dist',
            'SMA20_SMA50_Cross',
            'RSI7', 'MOM7', 'RSI14', 'MOM14', 'RSI21', 'MOM21',
            'MACD1', 'Signal1', 'Hist1', 'MACD2', 'Signal2', 'Hist2',
            'StochK', 'StochD',
            'ATR7', 'ATR14', 'ATR21',
            'BB20_Pos', 'BB20_Width', 'BB10_Pos', 'BB10_Width', 'BB40_Pos', 'BB40_Width',
            'OBV', 'AD'
        ]
        
        # Add pattern names
        pattern_names = [
            'Engulfing', 'Hammer', 'Harami', 'Marubozu', 
            '3WhiteSoldiers', '3BlackCrows', 'EveningStar', 
            'MorningStar', 'ShootingStar', 'Doji'
        ]
        base_names.extend(pattern_names)
        
        # Time-based features
        time_names = ['Hour', 'DayOfWeek', 'Sin_DayOfWeek', 'Cos_DayOfWeek', 'Sin_Hour', 'Cos_Hour']
        base_names.extend(time_names)
        
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
        model_path = self.models_path
        os.makedirs(model_path, exist_ok=True)
        
        # Save classical models
        for name, model in self.classifiers.items():
            joblib.dump(model, os.path.join(model_path, f"{name}_classifier.joblib"))
            
        joblib.dump(self.price_predictor, os.path.join(model_path, "price_predictor.joblib"))
        joblib.dump(self.feature_scaler, os.path.join(model_path, "feature_scaler.joblib"))
        joblib.dump(self.price_scaler, os.path.join(model_path, "price_scaler.joblib"))
        joblib.dump(self.anomaly_detector, os.path.join(model_path, "anomaly_detector.joblib"))
        
        # Save ensemble model
        if self.ensemble_classifier is not None:
            joblib.dump(self.ensemble_classifier, os.path.join(model_path, "ensemble_classifier.joblib"))
        
        # Save deep learning models
        if self.lstm_model is not None:
            self.lstm_model.save(os.path.join(model_path, "lstm_model.h5"))
            
        if self.cnn_model is not None:
            self.cnn_model.save(os.path.join(model_path, "cnn_model.h5"))
            
        # Save feature importance
        joblib.dump(self.feature_importance, os.path.join(model_path, "feature_importance.joblib"))
        
        self.logger.info(f"Models saved to {model_path}")
        
    def load_models(self):
        """Load all models from disk."""
        model_path = self.models_path
        
        try:
            # Load classical models
            for name in self.classifiers.keys():
                model_file = os.path.join(model_path, f"{name}_classifier.joblib")
                if os.path.exists(model_file):
                    self.classifiers[name] = joblib.load(model_file)
                    
            # Load other models
            self.price_predictor = joblib.load(os.path.join(model_path, "price_predictor.joblib"))
            self.feature_scaler = joblib.load(os.path.join(model_path, "feature_scaler.joblib"))
            self.price_scaler = joblib.load(os.path.join(model_path, "price_scaler.joblib"))
            self.anomaly_detector = joblib.load(os.path.join(model_path, "anomaly_detector.joblib"))
            
            # Load ensemble model
            ensemble_file = os.path.join(model_path, "ensemble_classifier.joblib")
            if os.path.exists(ensemble_file):
                self.ensemble_classifier = joblib.load(ensemble_file)
            
            # Load deep learning models
            lstm_file = os.path.join(model_path, "lstm_model.h5")
            if os.path.exists(lstm_file):
                self.lstm_model = load_model(lstm_file)
                
            cnn_file = os.path.join(model_path, "cnn_model.h5")
            if os.path.exists(cnn_file):
                self.cnn_model = load_model(cnn_file)
                
            # Load feature importance
            importance_file = os.path.join(model_path, "feature_importance.joblib")
            if os.path.exists(importance_file):
                self.feature_importance = joblib.load(importance_file)
                
            self.is_trained = True
            self.logger.info("Models loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
            self.is_trained = False
        
    def predict(self, current_data: pd.DataFrame) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Make trading predictions using ensemble of ML models.
        
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
        features = self.prepare_features(current_data)
        if len(features) == 0:
            return False, 0.0, {"error": "Failed to prepare features"}
            
        features_scaled = self.feature_scaler.transform(features[-1:])  # Only last row
        
        # Check for market regime change/anomaly
        is_anomaly = self.anomaly_detector.predict(features_scaled)[0] == 1
        anomaly_score = self.anomaly_detector.decision_function(features_scaled)[0]
        
        # Get predictions from all models
        predictions = {}
        probabilities = {}
        
        # Get predictions from classical ML models
        for name, model in self.classifiers.items():
            try:
                pred = model.predict(features_scaled)[0]
                prob = model.predict_proba(features_scaled)[0]
                predictions[name] = bool(pred)
                probabilities[name] = float(prob[1])  # Probability of positive class
            except Exception as e:
                self.logger.error(f"Error predicting with {name}: {e}")
                predictions[name] = False
                probabilities[name] = 0.0
        
        # Get ensemble prediction if available
        if self.ensemble_classifier is not None:
            try:
                predictions['ensemble'] = bool(self.ensemble_classifier.predict(features_scaled)[0])
                probabilities['ensemble'] = float(self.ensemble_classifier.predict_proba(features_scaled)[0][1])
            except Exception as e:
                self.logger.error(f"Error predicting with ensemble: {e}")
                predictions['ensemble'] = False
                probabilities['ensemble'] = 0.0
                
        # Get deep learning predictions if available and we have enough data
        sequence_predictions = {}
        if len(current_data) >= self.sequence_length and (self.lstm_model is not None or self.cnn_model is not None):
            # Prepare sequence data
            recent_data = current_data[-self.sequence_length:]
            seq_features = self.prepare_features(recent_data)
            if len(seq_features) == self.sequence_length:
                seq_features_scaled = self.feature_scaler.transform(seq_features)
                seq_data = np.expand_dims(seq_features_scaled, axis=0)  # Add batch dimension
                
                # LSTM prediction
                if self.lstm_model is not None:
                    try:
                        lstm_prob = self.lstm_model.predict(seq_data, verbose=0)[0][0]
                        predictions['lstm'] = bool(lstm_prob > 0.5)
                        probabilities['lstm'] = float(lstm_prob)
                        sequence_predictions['lstm'] = float(lstm_prob)
                    except Exception as e:
                        self.logger.error(f"Error predicting with LSTM: {e}")
                
                # CNN prediction
                if self.cnn_model is not None:
                    try:
                        cnn_prob = self.cnn_model.predict(seq_data, verbose=0)[0][0]
                        predictions['cnn'] = bool(cnn_prob > 0.5)
                        probabilities['cnn'] = float(cnn_prob)
                        sequence_predictions['cnn'] = float(cnn_prob)
                    except Exception as e:
                        self.logger.error(f"Error predicting with CNN: {e}")
        
        # Weighted voting to get final prediction
        # Weights based on historical performance (could be dynamic based on recent accuracy)
        weights = {
            'random_forest': 0.25,
            'xgboost': 0.3,
            'lightgbm': 0.25,
            'ensemble': 0.4,  # Higher weight for ensemble
            'lstm': 0.3,
            'cnn': 0.3
        }
        
        # Calculate weighted probability
        weighted_sum = 0.0
        total_weight = 0.0
        
        for model, prob in probabilities.items():
            if model in weights:
                weighted_sum += prob * weights[model]
                total_weight += weights[model]
                
        # Get final prediction
        final_probability = weighted_sum / total_weight if total_weight > 0 else 0.0
        final_prediction = final_probability > 0.5
        
        # Get price prediction if buy signal
        price_prediction = None
        if final_prediction:
            try:
                # Convert scaled prediction back to original scale
                scaled_pred = self.price_predictor.predict(features_scaled)[0]
                price_prediction = self.price_scaler.inverse_transform([[scaled_pred]])[0][0]
            except Exception as e:
                self.logger.error(f"Error predicting price: {e}")
        
        # Generate SHAP values for explainability
        shap_values = None
        feature_names = self._generate_feature_names(features_scaled.shape[1])
        top_features = {}
        
        try:
            if self.shap_explainer is not None:
                shap_values = self.shap_explainer.shap_values(features_scaled)[0]
                
                # Get top features by absolute SHAP value
                feature_impacts = list(zip(feature_names, shap_values))
                feature_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
                top_features = {name: float(impact) for name, impact in feature_impacts[:5]}
        except Exception as e:
            self.logger.error(f"Error calculating SHAP values: {e}")
            
        if not top_features:
            # Fallback to traditional feature importance
            top_features = self._get_top_features(features_scaled[0])
            
        # Prepare detailed prediction results
        prediction_details = {
            'model_predictions': {model: bool(pred) for model, pred in predictions.items()},
            'model_probabilities': {model: float(prob) for model, prob in probabilities.items()},
            'sequence_predictions': sequence_predictions,
            'price_prediction': float(price_prediction) if price_prediction is not None else None,
            'confidence': float(final_probability),
            'top_features': top_features,
            'is_anomaly': bool(is_anomaly),
            'anomaly_score': float(anomaly_score),
            'timestamp': datetime.now().isoformat()
        }
        
        return final_prediction, final_probability, prediction_details
        
    def _get_top_features(self, features: np.ndarray, top_n: int = 5) -> Dict[str, float]:
        """
        Get the most influential features for the current prediction.
        
        Args:
            features: Feature vector
            top_n: Number of top features to return
            
        Returns:
            Dictionary of feature name to impact score
        """
        if not self.feature_importance:
            return {}
            
        feature_names = list(self.feature_importance.keys())
        if len(feature_names) > len(features):
            feature_names = feature_names[:len(features)]
        elif len(feature_names) < len(features):
            # Add generic names if needed
            for i in range(len(feature_names), len(features)):
                feature_names.append(f'Feature_{i}')
        
        # Get importance from random forest as default
        if 'random_forest' in self.classifiers:
            importances = self.classifiers['random_forest'].feature_importances_
        else:
            # Use stored feature importance
            importances = list(self.feature_importance.values())
            if len(importances) < len(features):
                importances.extend([0.001] * (len(features) - len(importances)))
            
        feature_impacts = {}
        for name, importance, value in zip(feature_names, importances, features):
            feature_impacts[name] = float(importance * abs(value))
            
        return dict(sorted(feature_impacts.items(), key=lambda x: x[1], reverse=True)[:top_n])

    def validate_prediction(self, prediction: bool, confidence: float, 
                          market_regime: str, session: str, 
                          anomaly_detected: bool = False) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Validate ML prediction against market conditions and adjust confidence.
        
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
            
        # Define adjustment factors
        regime_multipliers = {
            'STRONG_TREND_UP': 1.2,
            'TREND_UP': 1.1,
            'STRONG_TREND_DOWN': 1.2,
            'TREND_DOWN': 1.1,
            'CHOPPY': 0.7,
            'RANGING': 0.8,
            'HIGH_VOLATILITY': 0.8,
            'LOW_VOLATILITY': 1.1
        }
        
        session_multipliers = {
            'london_ny_overlap': 1.2,
            'london_open': 1.1,
            'ny_session': 1.0,
            'asian_session': 0.7,
            'weekend': 0.6
        }
        
        # Apply adjustments
        adjusted_confidence = confidence
        applied_adjustments = {}
        
        # Market regime adjustment
        if market_regime in regime_multipliers:
            factor = regime_multipliers[market_regime]
            adjusted_confidence *= factor
            applied_adjustments['regime'] = factor
        
        # Session adjustment
        if session in session_multipliers:
            factor = session_multipliers[session]
            adjusted_confidence *= factor
            applied_adjustments['session'] = factor
        
        # Anomaly adjustment
        if anomaly_detected:
            adjusted_confidence *= 0.7  # Reduce confidence if anomaly detected
            applied_adjustments['anomaly'] = 0.7
            
        # Contra-trend protection
        if (market_regime == 'STRONG_TREND_DOWN' and prediction) or \
           (market_regime == 'STRONG_TREND_UP' and not prediction):
            adjusted_confidence *= 0.8  # Reduce confidence for counter-trend trades
            applied_adjustments['contra_trend'] = 0.8
            
        # Final validation
        is_valid = adjusted_confidence >= self.min_confidence_threshold
        
        validation_details = {
            'original_confidence': float(confidence),
            'adjusted_confidence': float(adjusted_confidence),
            'applied_adjustments': applied_adjustments,
            'is_valid': is_valid
        }
        
        return is_valid, adjusted_confidence, validation_details
        
    def evaluate_model_performance(self, historical_data: pd.DataFrame, 
                                 forward_period: int = 5) -> Dict[str, Any]:
        """
        Evaluate model performance on historical data.
        
        Args:
            historical_data: DataFrame with OHLCV data for backtesting
            forward_period: Number of periods to look ahead for evaluating predictions
            
        Returns:
            Dictionary with performance metrics
        """
        if not self.is_trained:
            return {'error': 'Models not trained'}
            
        results = {}
        
        try:
            # Prepare features and labels
            features = self.prepare_features(historical_data)
            labels_dict = self.prepare_labels(historical_data, forward_period=forward_period)
            
            # Remove last rows where we don't have future data
            valid_mask = labels_dict['valid_mask']
            features = features[:-forward_period]
            
            if len(features) == 0:
                return {'error': 'Not enough data for evaluation'}
                
            # Scale features
            features_scaled = self.feature_scaler.transform(features)
            
            # Evaluate each model
            models_to_evaluate = {}
            models_to_evaluate.update(self.classifiers)
            
            if self.ensemble_classifier:
                models_to_evaluate['ensemble'] = self.ensemble_classifier
                
            for name, model in models_to_evaluate.items():
                try:
                    y_pred = model.predict(features_scaled)
                    y_prob = model.predict_proba(features_scaled)[:, 1]
                    y_true = labels_dict['binary']
                    
                    results[name] = {
                        'accuracy': float(accuracy_score(y_true, y_pred)),
                        'precision': float(precision_score(y_true, y_pred)),
                        'recall': float(recall_score(y_true, y_pred)),
                        'f1_score': float(f1_score(y_true, y_pred)),
                        'auc_roc': float(roc_auc_score(y_true, y_prob))
                    }
                except Exception as e:
                    self.logger.error(f"Error evaluating {name}: {e}")
                    results[name] = {'error': str(e)}
            
            # Evaluate regression model
            try:
                # Filter for positive signals only
                buy_signals = labels_dict['binary'] == 1
                if np.any(buy_signals):
                    y_true_reg = historical_data['close'].values[:-forward_period][buy_signals]
                    y_pred_reg = self.price_predictor.predict(features_scaled[buy_signals])
                    
                    results['price_predictor'] = {
                        'mse': float(mean_squared_error(y_true_reg, y_pred_reg)),
                        'rmse': float(np.sqrt(mean_squared_error(y_true_reg, y_pred_reg))),
                        'mean_abs_error': float(np.mean(np.abs(y_true_reg - y_pred_reg)))
                    }
            except Exception as e:
                self.logger.error(f"Error evaluating price predictor: {e}")
                results['price_predictor'] = {'error': str(e)}
                
            return results
            
        except Exception as e:
            self.logger.error(f"Error in model evaluation: {e}")
            return {'error': str(e)}
            
    def visualize_feature_importance(self, top_n: int = 15, save_path: str = None) -> Dict[str, float]:
        """
        Visualize the importance of features in the model.
        
        Args:
            top_n: Number of top features to visualize
            save_path: Path to save the visualization
            
        Returns:
            Dictionary of top feature importances
        """
        if not self.feature_importance:
            return {}
            
        # Sort features by importance
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        # Create visualization
        names = [f[0] for f in sorted_features]
        values = [f[1] for f in sorted_features]
        
        plt.figure(figsize=(10, 6))
        plt.barh(names, values)
        plt.xlabel('Importance')
        plt.title('Top Feature Importance')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()
            
        return dict(sorted_features)
