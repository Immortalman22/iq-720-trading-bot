"""
Edge case handler for the trading system.
Handles various failure scenarios and data anomalies.
"""
from typing import Optional, Dict, Any, List
import numpy as np
from datetime import datetime, timedelta
import logging

class EdgeCaseHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_valid_price: Optional[float] = None
        self.price_history: List[float] = []
        self.gap_threshold = 0.0020  # 20 pips for EUR/USD
        self.volatility_threshold = 0.0030  # 30 pips for EUR/USD
        self.consecutive_gaps = 0
        self.max_gaps = 3

    def validate_candle(self, candle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate candle data and handle potential anomalies.
        Returns corrected candle or None if data is invalid.
        """
        try:
            # Basic structure validation
            required_fields = ['open', 'high', 'low', 'close', 'timestamp', 'volume']
            if not all(field in candle for field in required_fields):
                self.logger.warning("Missing required fields in candle data")
                return None

            # Convert numeric fields to float and create working copy
            numeric_fields = ['open', 'high', 'low', 'close']
            candle_copy = candle.copy()
            for field in numeric_fields:
                candle_copy[field] = float(candle_copy[field])

            # Convert timestamp if needed
            if isinstance(candle_copy['timestamp'], (int, float)):
                candle_copy['timestamp'] = datetime.fromtimestamp(candle_copy['timestamp'])

            # Initial price range validation and correction
            if not self._validate_price_range([
                candle_copy['open'],
                candle_copy['high'],
                candle_copy['low'],
                candle_copy['close']
            ]):
                # Fix basic price ordering
                candle_copy['high'] = max(
                    candle_copy['high'],
                    candle_copy['open'],
                    candle_copy['close']
                )
                candle_copy['low'] = min(
                    candle_copy['low'],
                    candle_copy['open'],
                    candle_copy['close']
                )

            # Gap detection and handling must happen first
            if self.last_valid_price is not None:
                current_gap = abs(float(candle_copy['open']) - float(self.last_valid_price))
                if current_gap > self.gap_threshold:
                    self.logger.warning("Price gap detected")
                    # Force the open price to be within threshold
                    gap_direction = 1 if candle_copy['open'] > self.last_valid_price else -1
                    candle_copy['open'] = float(self.last_valid_price + (self.gap_threshold * 0.5 * gap_direction))
                    
                    # Adjust other prices proportionally
                    scale = self.gap_threshold / current_gap
                    orig_range = float(candle_copy['high']) - float(candle_copy['low'])
                    new_range = orig_range * scale * 0.5
                    
                    # Recalculate all prices relative to new open
                    candle_copy['close'] = float(candle_copy['open'] + (new_range * gap_direction * 0.5))
                    candle_copy['high'] = float(max(candle_copy['open'], candle_copy['close']) + (new_range * 0.25))
                    candle_copy['low'] = float(min(candle_copy['open'], candle_copy['close']) - (new_range * 0.25))

            # Always check volatility after gap handling
            current_range = float(candle_copy['high']) - float(candle_copy['low'])
            if current_range > self.volatility_threshold:
                self.logger.warning("Abnormal volatility detected")
                # Center everything on open price for stability
                center = float(candle_copy['open'])
                max_range = self.volatility_threshold * 0.75  # Use 75% of threshold
                half_range = max_range / 2
                
                # Calculate new prices centered on open
                if float(candle_copy['close']) > float(candle_copy['open']):
                    candle_copy['close'] = float(center + half_range * 0.5)
                    candle_copy['high'] = float(center + half_range)
                    candle_copy['low'] = float(center - half_range)
                else:
                    candle_copy['close'] = float(center - half_range * 0.5)
                    candle_copy['high'] = float(center + half_range)
                    candle_copy['low'] = float(center - half_range)

            # Final validation - ensure high/low bounds are respected
            candle_copy['high'] = float(max(
                candle_copy['high'],
                candle_copy['open'],
                candle_copy['close']
            ))
            candle_copy['low'] = float(min(
                candle_copy['low'],
                candle_copy['open'],
                candle_copy['close']
            ))

            # Update history and return validated candle
            self._update_history(candle_copy['close'])
            return candle_copy

            # Update history
            self._update_history(candle_copy['close'])
            return candle_copy

        except Exception as e:
            self.logger.error(f"Error validating candle: {e}")
            return None

    def _validate_price_range(self, prices: List[float]) -> bool:
        """Check if prices are in valid range and properly ordered."""
        if not prices or any(not isinstance(p, (int, float)) for p in prices):
            return False

        try:
            open_price, high, low, close = prices
            return (
                all(p > 0 for p in prices) and  # All prices must be positive
                high >= max(open_price, close) and  # High must be highest
                low <= min(open_price, close)  # Low must be lowest
            )
        except Exception:
            return False

    def _validate_price_gap(self, current_open: float) -> bool:
        """Check for significant price gaps."""
        if not self.last_valid_price:
            return True

        gap_size = abs(current_open - self.last_valid_price)
        if gap_size > self.gap_threshold:
            self.consecutive_gaps += 1
            return self.consecutive_gaps <= self.max_gaps
        
        self.consecutive_gaps = 0
        return True

    def _validate_volatility(self, prices: List[float]) -> bool:
        """Check for abnormal volatility."""
        open_price, high, low, close = prices
        candle_range = high - low
        return candle_range <= self.volatility_threshold

    def _fix_price_range(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Fix invalid price ranges while preserving relative movements."""
        if not self.last_valid_price:
            return None

        # Use last valid price as reference
        reference = self.last_valid_price
        prices = [candle[f] for f in ['open', 'high', 'low', 'close']]
        
        # Calculate valid high and low
        original_range = max(prices) - min(prices)
        if original_range > self.volatility_threshold:
            original_range = self.volatility_threshold

        # Rebuild candle preserving direction but fixing order
        direction = 1 if prices[-1] > prices[0] else -1
        fixed = {}
        fixed['open'] = reference
        fixed['close'] = reference * (1 + 0.0001 * direction)  # Small movement
        fixed['high'] = max(fixed['open'], fixed['close']) + (original_range * 0.5)
        fixed['low'] = min(fixed['open'], fixed['close']) - (original_range * 0.5)

        return fixed

    def _handle_price_gap(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Handle price gaps by interpolating missing data."""
        if not self.last_valid_price:
            return None

        current_open = float(candle['open'])
        gap_size = current_open - self.last_valid_price
        
        if abs(gap_size) > self.gap_threshold:
            # Create maximally conservative gap fix
            fixed = {}
            
            # Use 25% of threshold for maximum safety
            allowed_gap = self.gap_threshold * 0.25
            gap_direction = 1 if gap_size > 0 else -1
            
            # Set new open extremely close to last valid price
            fixed['open'] = float(self.last_valid_price + (allowed_gap * gap_direction))
            
            # Keep a very tight range
            new_range = allowed_gap * 0.5
            
            # Set all prices relative to the new open
            if gap_direction > 0:
                fixed['close'] = float(fixed['open'] + (new_range * 0.5))
                fixed['high'] = float(fixed['open'] + new_range)
                fixed['low'] = float(fixed['open'])
            else:
                fixed['close'] = float(fixed['open'] - (new_range * 0.5))
                fixed['high'] = float(fixed['open'])
                fixed['low'] = float(fixed['open'] - new_range)
            
            return fixed
            
        return None

    def _handle_volatility(self, candle: Dict[str, Any]) -> Dict[str, Any]:
        """Handle abnormal volatility by capping price movements."""
        if not self.last_valid_price:
            return candle

        # Use last valid price as reference
        reference = float(self.last_valid_price)
        current_range = float(candle['high']) - float(candle['low'])
        
        if current_range > self.volatility_threshold:
            fixed = {}
            
            # Use 75% of threshold for maximum safety
            safe_range = self.volatility_threshold * 0.75
            half_range = safe_range / 2
            
            # Center everything around reference price
            fixed['high'] = float(reference + half_range)
            fixed['low'] = float(reference - half_range)
            
            # Calculate new open/close preserving direction but within tight range
            if float(candle['close']) > float(candle['open']):
                fixed['open'] = float(reference - (half_range * 0.5))
                fixed['close'] = float(reference + (half_range * 0.5))
            else:
                fixed['open'] = float(reference + (half_range * 0.5))
                fixed['close'] = float(reference - (half_range * 0.5))
            
            return fixed
        
        return None

    def _update_history(self, close_price: float) -> None:
        """Update price history for future validations."""
        self.last_valid_price = close_price
        self.price_history.append(close_price)
        
        # Keep limited history
        max_history = 100
        if len(self.price_history) > max_history:
            self.price_history = self.price_history[-max_history:]
