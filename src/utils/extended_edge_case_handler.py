"""Extended edge case handler for trading data anomalies."""
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import math
import statistics
import logging

@dataclass
class DataAnomalyReport:
    """Report detailing data anomalies and corrections."""
    original_data: Dict
    corrected_data: Optional[Dict]
    anomalies: List[str]
    correction_applied: bool
    confidence: float  # Confidence in the correction
    severity: str  # 'low', 'medium', 'high'

class ExtendedEdgeCaseHandler:
    """
    Enhanced edge case handler with advanced anomaly detection
    and correction capabilities.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Price history for trend analysis
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.timestamp_history: List[datetime] = []
        self.anomaly_history: List[DataAnomalyReport] = []
        
        # Thresholds
        self.gap_threshold = 0.0020  # 20 pips
        self.volatility_threshold = 0.0030  # 30 pips
        self.volume_anomaly_threshold = 3.0  # z-score threshold for volume anomalies
        self.severe_anomaly_threshold = 5.0  # z-score threshold for severe anomalies
        self.correction_factor = 0.5  # How much to correct anomalies 
        self.tick_threshold = 100  # Minimum ticks for validity
        self.timestamp_gap_threshold = 300  # 5 minutes
        
        # Base confidence settings
        self.base_confidence = 0.9  # Start with high confidence
        self.min_confidence = 0.2  # Minimum confidence threshold
        
        # Validation settings
        self.require_multiple_validations = True  # Require multiple checks
        self.strict_mode = True  # Enable strict validation mode
        self.severity_threshold = 4  # Severity threshold for rejection
        
        # State tracking
        self.consecutive_anomalies = 0
        self.max_consecutive_anomalies = 5
        self.last_valid_state = None
        
    def validate_data(self, data: Dict[str, Any]) -> DataAnomalyReport:
        """
        Validate trading data for multiple types of anomalies.
        
        Args:
            data: Trading data to validate
            
        Returns:
            DataAnomalyReport detailing any anomalies and corrections
        """
        anomalies = []
        corrections_needed = False
        corrected = data.copy()
        
        try:
            # Check for ticker freezing
            if self._is_ticker_frozen(data):
                anomalies.append("ticker_frozen")
                corrections_needed = True
                
            # Check for timestamp anomalies
            if not self._validate_timestamp(data):
                anomalies.append("invalid_timestamp")
                corrections_needed = True
                
            # Check for volume anomalies and apply correction
            volume = float(data.get('volume', 0))
            if not self.validate_volume(volume):
                anomalies.append("abnormal_volume")
                corrections_needed = True
                # Apply volume correction
                if 'volume' in corrected:
                    corrected['volume'] = self.correct_volume(volume)
                
            # Check for tick count validity
            if not self._validate_tick_count(data):
                anomalies.append("insufficient_ticks")
                corrections_needed = True
                
            # Check for order book anomalies
            if not self._validate_order_book(data):
                anomalies.append("order_book_anomaly")
                corrections_needed = True
                
            # Only proceed with price validation if we have basic validity
            if corrections_needed:
                corrected = self._apply_corrections(data, anomalies)
                
            # Track anomaly history
            if anomalies:
                self.consecutive_anomalies += 1
            else:
                self.consecutive_anomalies = 0
                
            # Determine severity
            severity = self._calculate_severity(anomalies)
            
            # Calculate confidence in corrections
            confidence = self._calculate_confidence(anomalies, corrected)
            
            # Update state if data is valid
            if not corrections_needed or confidence > 0.7:
                self._update_state(corrected)
                
            return DataAnomalyReport(
                original_data=data,
                corrected_data=corrected if corrections_needed else None,
                anomalies=anomalies,
                correction_applied=corrections_needed,
                confidence=confidence,
                severity=severity
            )
            
        except Exception as e:
            self.logger.error(f"Error in data validation: {e}")
            return DataAnomalyReport(
                original_data=data,
                corrected_data=None,
                anomalies=["validation_error"],
                correction_applied=False,
                confidence=0.0,
                severity="high"
            )
            
    def _is_ticker_frozen(self, data: Dict[str, Any]) -> bool:
        """Check for frozen ticker data."""
        if not self.price_history:
            return False
            
        # Check if price hasn't changed for multiple periods
        current_price = float(data.get('close', 0))
        frozen_threshold = 5  # Number of periods to consider frozen
        frozen_pip_threshold = 0.0001  # Minimum price movement threshold
        
        if len(self.price_history) >= frozen_threshold:
            recent_prices = self.price_history[-frozen_threshold:]
            # Consider frozen if all recent prices are within 0.1 pip
            if all(abs(p - current_price) <= frozen_pip_threshold for p in recent_prices):
                return True
                
        return False
        
    def _validate_timestamp(self, data: Dict[str, Any]) -> bool:
        """Validate timestamp sequencing and gaps."""
        try:
            current_time = self._parse_timestamp(data.get('timestamp'))
            if not current_time:
                return False
                
            if not self.timestamp_history:
                return True
                
            last_time = self.timestamp_history[-1]
            
            # Check for future timestamps
            if current_time > datetime.now() + timedelta(minutes=1):
                return False
                
            # Check for backwards time
            if current_time <= last_time:
                return False
                
            # Check for large gaps
            gap = (current_time - last_time).total_seconds()
            if gap > self.timestamp_gap_threshold:
                return False
                
            return True
            
        except Exception:
            return False
            
    def validate_volume(self, volume: float) -> bool:
        """
        Validate volume data and determine if correction is needed.
        Returns False if volume needs correction.
        """
        if not self.volume_history or volume <= 0:
            return True

        # Calculate rolling statistics with exponential weighting
        recent_volumes = self.volume_history[-10:]  # Focus on recent history
        weights = [0.9 ** i for i in range(len(recent_volumes))]
        weighted_mean = sum(v * w for v, w in zip(recent_volumes, weights)) / sum(weights)
        
        # Calculate weighted standard deviation
        weighted_var = sum(w * ((v - weighted_mean) ** 2) 
                         for v, w in zip(recent_volumes, weights)) / sum(weights)
        weighted_std = math.sqrt(weighted_var)

        # Calculate z-score
        z_score = (volume - weighted_mean) / weighted_std if weighted_std > 0 else 0

        # Return True if volume is within normal range
        return abs(z_score) <= self.volume_anomaly_threshold

    def correct_volume(self, volume: float) -> float:
        """
        Apply volume correction based on historical data.
        """
        if not self.volume_history or volume <= 0:
            return volume

        recent_volumes = self.volume_history[-10:]
        weights = [0.9 ** i for i in range(len(recent_volumes))]
        weighted_mean = sum(v * w for v, w in zip(recent_volumes, weights)) / sum(weights)
        
        weighted_var = sum(w * ((v - weighted_mean) ** 2) 
                         for v, w in zip(recent_volumes, weights)) / sum(weights)
        weighted_std = math.sqrt(weighted_var)

        z_score = (volume - weighted_mean) / weighted_std if weighted_std > 0 else 0

        if abs(z_score) > self.volume_anomaly_threshold:
            if abs(z_score) > self.severe_anomaly_threshold:
                # For severe anomalies, correct more aggressively
                correction = 0.2
            else:
                # For minor anomalies, use dynamic correction
                correction = min(0.8, self.correction_factor / abs(z_score))
            
            corrected_volume = weighted_mean + ((volume - weighted_mean) * correction)
            self.logger.info(f"Volume corrected from {volume} to {corrected_volume} (z-score: {z_score:.2f})")
            return corrected_volume

        return volume

    def _validate_tick_count(self, data: Dict[str, Any]) -> bool:
        """Validate tick count for data quality."""
        return int(data.get('tick_count', 0)) >= self.tick_threshold
        
    def _validate_order_book(self, data: Dict[str, Any]) -> bool:
        """Validate order book consistency."""
        try:
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            close_price = float(data.get('close', 0))
            
            if not bids or not asks:
                return True  # Skip if no order book data
                
            # Check for crossed or inverted prices
            if any(bid[0] >= ask[0] for bid in bids for ask in asks):
                return False
                
            # Check price alignment with last trade
            if close_price > 0:
                if bids[0][0] > close_price or asks[0][0] < close_price:
                    return False
                
            # Check for unrealistic spreads
            spread = asks[0][0] - bids[0][0]
            if spread > self.gap_threshold * 2 or spread < 0:
                return False
                
            # Check for price continuity in order book
            for i in range(1, len(bids)):
                if bids[i][0] > bids[i-1][0]:  # Bids should be descending
                    return False
            for i in range(1, len(asks)):
                if asks[i][0] < asks[i-1][0]:  # Asks should be ascending
                    return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f"Order book validation error: {e}")
            return False  # Fail closed on validation errors
            
    def _apply_corrections(self, data: Dict[str, Any], 
                         anomalies: List[str]) -> Dict[str, Any]:
        """Apply corrections to anomalous data."""
        corrected = data.copy()
        
        try:
            if "ticker_frozen" in anomalies:
                # Use trend-based interpolation
                if len(self.price_history) >= 2:
                    trend = self.price_history[-1] - self.price_history[-2]
                    corrected['close'] = self.price_history[-1] + (trend * 0.5)
                    
            if "invalid_timestamp" in anomalies:
                if self.timestamp_history:
                    # Project next timestamp based on average interval
                    avg_interval = np.mean([
                        (t2 - t1).total_seconds()
                        for t1, t2 in zip(self.timestamp_history[-10:], 
                                        self.timestamp_history[-9:])
                    ])
                    corrected['timestamp'] = self.timestamp_history[-1] + \
                                           timedelta(seconds=avg_interval)
                                           
            if "abnormal_volume" in anomalies and 'volume' in data:
                corrected['volume'] = self.correct_volume(float(data['volume']))
                                        
            if "order_book_anomaly" in anomalies:
                if "bids" in data and "asks" in data:
                    mid_price = float(corrected.get('close', 0))
                    spread = self.gap_threshold
                    corrected['bids'] = [[mid_price - spread/2, 1.0]]
                    corrected['asks'] = [[mid_price + spread/2, 1.0]]
                    
            return corrected
            
        except Exception as e:
            self.logger.error(f"Error applying corrections: {e}")
            return data
            
    def _calculate_severity(self, anomalies: List[str]) -> str:
        """Calculate severity of anomalies."""
        if not anomalies:
            return "low"
            
        severity_weights = {
            "ticker_frozen": 3,
            "invalid_timestamp": 2,
            "abnormal_volume": 1,
            "insufficient_ticks": 1,
            "order_book_anomaly": 3,  # Increased weight for order book issues
            "validation_error": 3
        }
        
        total_weight = sum(severity_weights.get(a, 1) for a in anomalies)
        
        # Check for combinations that indicate serious issues
        if len(set(anomalies) & {"order_book_anomaly", "invalid_timestamp"}) > 1:
            return "high"
            
        # Multiple anomalies are more severe
        if len(anomalies) >= 3:
            return "high"
            
        # Weight-based severity with thresholds
        if total_weight >= self.severity_threshold:
            return "high"
        elif total_weight >= self.severity_threshold * 0.7:
            return "medium"
        return "low"
        
    def _calculate_confidence(self, anomalies: List[str], 
                            corrected: Dict[str, Any]) -> float:
        """Calculate confidence in corrections."""
        if not anomalies:
            return 1.0
            
        current_confidence = self.base_confidence
        
        # Base penalties for each anomaly type
        confidence_penalties = {
            "ticker_frozen": 0.25,
            "invalid_timestamp": 0.15,
            "abnormal_volume": 0.15,
            "insufficient_ticks": 0.10,
            "order_book_anomaly": 0.20,
            "validation_error": 0.40
        }
        
        # Apply multiplicative penalties with exponential decay
        penalty_sum = sum(confidence_penalties.get(a, 0.1) for a in anomalies)
        current_confidence *= (1.0 - (1.0 - math.exp(-0.5 * penalty_sum)))
        
        # Apply exponential decay for consecutive anomalies that grows more aggressively
        consecutive_factor = min(0.8, 0.2 * math.log(1 + self.consecutive_anomalies))
        current_confidence *= (1.0 - consecutive_factor)
        
        # Add extra penalty for combinations of serious issues
        if len(set(anomalies) & {"order_book_anomaly", "invalid_timestamp", "abnormal_volume"}) > 1:
            current_confidence *= 0.8
            
        # Ensure we don't return less than min_confidence
        return max(current_confidence, self.min_confidence)
        
    def _update_state(self, data: Dict[str, Any]) -> None:
        """Update internal state with validated data."""
        try:
            # Update price history
            close_price = float(data.get('close', 0))
            if close_price > 0:
                self.price_history.append(close_price)
                
            # Update volume history
            volume = float(data.get('volume', 0))
            if volume > 0:
                self.volume_history.append(volume)
                
            # Update timestamp history
            timestamp = self._parse_timestamp(data.get('timestamp'))
            if timestamp:
                self.timestamp_history.append(timestamp)
                
            # Keep limited history
            max_history = 100
            self.price_history = self.price_history[-max_history:]
            self.volume_history = self.volume_history[-max_history:]
            self.timestamp_history = self.timestamp_history[-max_history:]
            
            # Update last valid state
            self.last_valid_state = {
                'price': close_price,
                'volume': volume,
                'timestamp': timestamp
            }
            
        except Exception as e:
            self.logger.error(f"Error updating state: {e}")
            
    def _parse_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """Parse timestamp from multiple formats."""
        try:
            if isinstance(timestamp, datetime):
                return timestamp
            elif isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                return datetime.fromisoformat(timestamp)
            return None
        except Exception:
            return None
