"""
Machine Learning Module for EUR/USD Trading
Implements advanced ML models for pattern recognition and price prediction.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib
from typing import Tuple, List, Dict, Optional
from datetime import datetime, timedelta
import talib

class MLPredictor:
    def __init__(self, lookback_periods: int = 100):
        self.lookback_periods = lookback_periods
        self.pattern_classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.price_predictor = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.min_confidence_threshold = 0.7
        self.feature_importance = {}
        
    def prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """Create feature set from price data."""
        features = []
        
        # Technical indicators
        close_prices = data['close'].values
        high_prices = data['high'].values
        low_prices = data['low'].values
        volumes = data['volume'].values
        
        # Trend indicators
        features.append(talib.SMA(close_prices, timeperiod=20))
        features.append(talib.SMA(close_prices, timeperiod=50))
        features.append(talib.EMA(close_prices, timeperiod=13))
        features.append(talib.EMA(close_prices, timeperiod=26))
        
        # Momentum indicators
        features.append(talib.RSI(close_prices, timeperiod=14))
        macd, signal, _ = talib.MACD(close_prices)
        features.append(macd)
        features.append(signal)
        
        # Volatility indicators
        features.append(talib.ATR(high_prices, low_prices, close_prices, timeperiod=14))
        upper, middle, lower = talib.BBANDS(close_prices)
        features.append((close_prices - lower) / (upper - lower))  # BB position
        
        # Volume indicators
        features.append(talib.OBV(close_prices, volumes))
        
        # Price patterns
        features.append(talib.CDLENGULFING(open_prices, high_prices, low_prices, close_prices))
        features.append(talib.CDLHAMMER(open_prices, high_prices, low_prices, close_prices))
        features.append(talib.CDLHARAMI(open_prices, high_prices, low_prices, close_prices))
        
        # Time-based features
        timestamps = pd.to_datetime(data.index)
        features.append(timestamps.hour.values)
        features.append(timestamps.dayofweek.values)
        
        # Stack and clean features
        feature_array = np.column_stack(features)
        feature_array = np.nan_to_num(feature_array, nan=0)
        
        return feature_array
        
    def prepare_labels(self, data: pd.DataFrame, forward_period: int = 5) -> np.ndarray:
        """Create labels for training (1 for price increase, 0 for decrease)."""
        future_returns = data['close'].pct_change(forward_period).shift(-forward_period)
        labels = (future_returns > 0).astype(int)
        return labels[:-forward_period]  # Remove last few rows where we don't have future data
        
    def train(self, historical_data: pd.DataFrame):
        """Train the ML models on historical data."""
        features = self.prepare_features(historical_data)
        labels = self.prepare_labels(historical_data)
        
        # Remove rows with missing labels
        valid_idx = ~np.isnan(labels)
        features = features[valid_idx]
        labels = labels[valid_idx]
        
        # Scale features
        features_scaled = self.scaler.fit_transform(features)
        
        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=5)
        for train_idx, test_idx in tscv.split(features_scaled):
            X_train = features_scaled[train_idx]
            y_train = labels[train_idx]
            X_test = features_scaled[test_idx]
            y_test = labels[test_idx]
            
            # Train pattern classifier
            self.pattern_classifier.fit(X_train, y_train)
            
            # Train price predictor on successful patterns
            mask = y_train == 1
            if np.any(mask):
                self.price_predictor.fit(X_train[mask], 
                                       historical_data['close'].values[train_idx][mask])
        
        # Calculate feature importance
        feature_names = [
            'SMA20', 'SMA50', 'EMA13', 'EMA26', 'RSI', 'MACD', 'Signal',
            'ATR', 'BB_Position', 'OBV', 'Engulfing', 'Hammer', 'Harami',
            'Hour', 'DayOfWeek'
        ]
        self.feature_importance = dict(zip(feature_names, 
                                         self.pattern_classifier.feature_importances_))
        
        self.is_trained = True
        
    def predict(self, current_data: pd.DataFrame) -> Tuple[bool, float, Dict]:
        """Make trading predictions using the trained models."""
        if not self.is_trained:
            return False, 0.0, {}
            
        # Prepare features
        features = self.prepare_features(current_data)
        features_scaled = self.scaler.transform(features[-1:])  # Only last row
        
        # Get pattern prediction and probability
        pattern_pred = self.pattern_classifier.predict(features_scaled)
        pattern_prob = self.pattern_classifier.predict_proba(features_scaled)[0]
        
        # Get price prediction if pattern is detected
        price_pred = None
        if pattern_pred[0] == 1:
            price_pred = self.price_predictor.predict(features_scaled)[0]
            
        # Calculate confidence score
        confidence = pattern_prob[1]  # Probability of positive class
        
        # Prepare prediction details
        prediction_details = {
            'pattern_probability': pattern_prob[1],
            'price_prediction': price_pred,
            'confidence': confidence,
            'top_features': self._get_top_features(features_scaled[0])
        }
        
        return bool(pattern_pred[0]), confidence, prediction_details
        
    def _get_top_features(self, features: np.ndarray, top_n: int = 3) -> Dict[str, float]:
        """Get the most influential features for current prediction."""
        feature_names = list(self.feature_importance.keys())
        feature_impacts = {}
        
        for name, importance, value in zip(feature_names, 
                                         self.pattern_classifier.feature_importances_,
                                         features):
            feature_impacts[name] = importance * abs(value)
            
        return dict(sorted(feature_impacts.items(), 
                         key=lambda x: x[1], 
                         reverse=True)[:top_n])

    def validate_prediction(self, prediction: bool, confidence: float,
                          market_regime: str, session: str) -> Tuple[bool, float]:
        """Validate ML prediction against market conditions."""
        if confidence < self.min_confidence_threshold:
            return False, confidence
            
        # Adjust confidence based on market regime
        regime_multipliers = {
            'STRONG_TREND_UP': 1.2,
            'STRONG_TREND_DOWN': 1.2,
            'CHOPPY': 0.8,
            'HIGH_VOLATILITY': 0.9,
            'LOW_VOLATILITY': 1.1
        }
        
        # Adjust confidence based on session
        session_multipliers = {
            'london_ny_overlap': 1.2,
            'london_open': 1.1,
            'ny_session': 1.0,
            'asian_session': 0.8
        }
        
        # Apply multipliers
        adjusted_confidence = confidence
        if market_regime in regime_multipliers:
            adjusted_confidence *= regime_multipliers[market_regime]
        if session in session_multipliers:
            adjusted_confidence *= session_multipliers[session]
            
        # Final validation
        is_valid = adjusted_confidence >= self.min_confidence_threshold
        
        return is_valid, adjusted_confidence
