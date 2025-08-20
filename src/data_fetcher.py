import websocket
import json
import time
from datetime import datetime, timezone
import logging
from typing import Callable, Optional, Dict, Any
from .utils.config import Config
from .utils.fallback_data import FallbackDataManager
from .utils.edge_case_handler import EdgeCaseHandler

class IQOptionDataFetcher:
    def __init__(self, config: Config, on_candle_callback: Callable):
        self.config = config
        self.ws = None
        self.on_candle_callback = on_candle_callback
        self.logger = logging.getLogger(__name__)
        self.last_pong = time.time()
        self.is_connected = False
        self.fallback = FallbackDataManager(config)
        self.using_fallback = False
        self.last_fallback_check = time.time()
        self.edge_handler = EdgeCaseHandler()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.error_cooldown = 60  # 1 minute cooldown after max errors

    def connect(self):
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            self.config.IQ_OPTION_WS_URL,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        self.ws.run_forever(ping_interval=30, ping_timeout=10)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("name") == "candle-generated":
                candle_data = data["msg"]
                if candle_data["asset"] == "EURUSD":
                    # Validate and handle edge cases
                    validated_candle = self.edge_handler.validate_candle(candle_data)
                    if validated_candle:
                        self.consecutive_errors = 0  # Reset error count on success
                        self.on_candle_callback(validated_candle)
                    else:
                        self._handle_invalid_data()
            elif data.get("name") == "pong":
                self.last_pong = time.time()
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            self._handle_error()

    def _handle_invalid_data(self):
        """Handle invalid data by incrementing error count and possibly switching to fallback"""
        self.consecutive_errors += 1
        self.logger.warning(f"Invalid data received. Consecutive errors: {self.consecutive_errors}")
        
        if self.consecutive_errors >= self.max_consecutive_errors:
            self.logger.error("Too many consecutive errors, switching to fallback")
            self._switch_to_fallback()

    def _handle_error(self):
        """Handle general errors in data processing"""
        self.consecutive_errors += 1
        if self.consecutive_errors >= self.max_consecutive_errors:
            self.logger.error("Too many consecutive errors, switching to fallback")
            self._switch_to_fallback()

    def _on_error(self, ws, error):
        self.logger.error(f"WebSocket error: {error}")
        self.is_connected = False
        self._switch_to_fallback()

    def _on_close(self, ws, close_status_code, close_msg):
        self.logger.info("WebSocket connection closed")
        self.is_connected = False
        self._switch_to_fallback()

    def _on_open(self, ws):
        self.logger.info("WebSocket connection established")
        self.is_connected = True
        # Subscribe to EUR/USD 1-minute candles
        subscribe_message = {
            "name": "subscribeMessage",
            "msg": {
                "name": "candle-generated",
                "params": {
                    "routingFilters": {
                        "active": "EURUSD",
                        "size": 60  # 1 minute in seconds
                    }
                }
            }
        }
        ws.send(json.dumps(subscribe_message))

    def is_within_trading_hours(self) -> bool:
        """Check if current time is within London session trading hours"""
        current_time = datetime.now(timezone.utc)
        hour = current_time.hour
        return 8 <= hour < 12  # 8:00 AM - 12:00 PM GMT

    def _switch_to_fallback(self):
        """Switch to fallback data sources when primary connection fails"""
        self.using_fallback = True
        self.logger.info("Switching to fallback data sources")
        
        # Start fallback data polling
        self._poll_fallback_data()

    def _poll_fallback_data(self):
        """Poll fallback data sources for updates"""
        try:
            current_time = time.time()
            
            # Only poll every minute
            if current_time - self.last_fallback_check < 60:
                return
                
            data = self.fallback.get_current_data()
            if data:
                candle_data = {
                    'asset': 'EURUSD',
                    'timestamp': data['timestamp'],
                    'close': data['price'],
                    'source': data['source']
                }
                self.on_candle_callback(candle_data)
                self.last_fallback_check = current_time
                
                # Try to reconnect to primary source every 5 minutes
                if current_time - self.last_pong > 300:
                    self.connect()
                    
        except Exception as e:
            self.logger.error(f"Error in fallback data polling: {e}")

    def get_historical_data(self, interval: str = "1m", limit: int = 100):
        """Get historical candle data from either primary or fallback sources"""
        if self.is_connected:
            # Implementation for IQ Option historical data
            pass
        else:
            return self.fallback.get_historical_data(interval, limit)
