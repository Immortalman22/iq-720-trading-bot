#!/usr/bin/env python
"""
IQ 720 Trading Bot - Main Entry Point with ML Capabilities
This script runs an enhanced version of the trading bot that analyzes the market
using both traditional indicators and machine learning predictions.
"""
import os
import time
import logging
import signal
import sys
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import components
from .data_fetcher import IQOptionDataFetcher
from .signal_generator import SignalGenerator
# from .trade_executor import TradeExecutor  # Commented for analysis-only mode
from .utils.ml_predictor import MLPredictor
from telegram import Bot
import requests
import asyncio
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("IQ720Bot")

class TelegramNotifier:
    """Simplified Telegram notifier for analysis-only mode"""
    
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.logger = logging.getLogger("TelegramNotifier")
    
    def send_message(self, message):
        """Send a simple message to Telegram"""
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            )
            response.raise_for_status()
            self.logger.info(f"Message sent successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message: {str(e)}")
            return False
    
    def send_signal(self, direction, asset, confidence, indicators):
        """Send a trading signal alert to Telegram"""
        try:
            # Format confidence as percentage and stars
            confidence_pct = confidence * 100
            confidence_stars = "⭐" * int(round(confidence * 5))
            
            # Format the message
            message = f"""
🚨 <b>TRADING SIGNAL</b> 🚨

Asset: {asset}
Direction: {'📈' if direction == 'BUY' else '📉'} <b>{direction}</b>
Expiry: 15 minute(s)
Confidence: {confidence_stars} ({confidence_pct:.2f}%)

<b>Technical Indicators:</b>
RSI: {indicators['rsi']:.2f}
MACD: {indicators['macd']:.5f}
Volume: {indicators['volume']:.2f}x average

⚠️ <i>Manual execution required</i>
⏰ Generated: {datetime.now().strftime('%H:%M:%S')} UTC
"""
            return self.send_message(message.strip())
        except Exception as e:
            self.logger.error(f"Failed to send signal: {str(e)}")
            return False


class TradingBot:
    def __init__(self, config_path='config.yaml', analysis_mode=False):
        """Initialize the trading bot with configuration"""
        self.config = self.load_config(config_path)
        self.analysis_mode = analysis_mode
        
        # Create session manager
        from src.utils.session_manager import SessionManager
        self.session_manager = SessionManager(self.config)
        
        # Set up system components
        self.setup_components()
        
        # Trading state
        self.active = False
        self.last_signal_time = None
        
        # ML configuration
        self.use_ml = self.config.get('use_ml', False)
        if self.use_ml:
            self.initialize_ml_predictor()
        
        logger.info("IQ-720 Trading Bot initialized")
    
    def initialize_ml_predictor(self):
        """Initialize the ML predictor component if ML is enabled"""
        try:
            # Import here to avoid dependency issues if ML is not enabled
            import importlib
            
            # Check if ml_predictor module is available
            try:
                ml_module = importlib.import_module("src.utils.ml_predictor")
                
                # Get ML configuration
                ml_config = self.config.get('ml', {})
                model_path = ml_config.get('model_path', 'models/ensemble_model')
                
                # Initialize ML predictor
                self.ml_predictor = ml_module.MLPredictor(
                    config=ml_config,
                    model_path=model_path
                )
                
                # Load models
                self.ml_predictor.load_models()
                logger.info("ML predictor initialized successfully")
                
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning(f"ML predictor module not available: {e}")
                logger.warning("Running without ML capabilities")
                self.use_ml = False
                
        except Exception as e:
            logger.error(f"Error initializing ML predictor: {e}")
            logger.warning("Continuing without ML capabilities")
            self.use_ml = False
    
    def setup_components(self):
        """Set up the necessary components for the trading bot"""
        try:
            # Data fetcher for retrieving market data
            from src.data_fetcher import DataFetcher
            self.data_fetcher = DataFetcher(self.config)
            
            # Signal generator to identify trading opportunities
            from src.signal_generator import SignalGenerator
            self.signal_generator = SignalGenerator(self.config)
            
            # Trade executor for placing trades (if not in analysis mode)
            if not self.analysis_mode:
                from src.trade_executor import TradeExecutor
                self.trade_executor = TradeExecutor(self.config)
            
            # Telegram notification service
            # Using the simplified version defined in this file
            telegram_token = self.config.get('telegram', {}).get('token', '')
            telegram_chat_id = self.config.get('telegram', {}).get('chat_id', '')
            self.telegram = TelegramNotifier(telegram_token, telegram_chat_id)
            
            # Set running flag
            self.running = True
            self.last_status_time = None
            
            # Register signal handlers
            signal.signal(signal.SIGINT, self.handle_exit)
            signal.signal(signal.SIGTERM, self.handle_exit)
            
        except Exception as e:
            logger.error(f"Error setting up components: {e}")
            sys.exit(1)
    
    def handle_exit(self, signum, frame):
        """Handle exit signals gracefully"""
        logger.info("Received exit signal. Shutting down gracefully...")
        self.running = False

    def is_time_for_status(self):
        """Check if it's time to send a status message (every :00 and :30)"""
        now = datetime.now()
        minutes = now.minute
        
        # Send at XX:00 and XX:30
        return minutes == 0 or minutes == 30

    def analyze_market_and_generate_signal(self):
        """
        Analyze market data and generate trading signals using both traditional indicators and ML
        """
        # Get latest market data for common forex pairs
        assets = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD']
        signals = []
        
        for asset in assets:
            try:
                # Get candle data
                candle_data = self.data_fetcher.get_candles(asset)
                if not candle_data or len(candle_data) < 50:  # Need sufficient data for analysis
                    continue
                    
                # Convert to DataFrame for ML processing
                df = pd.DataFrame(candle_data)
                
                # Process with traditional signal generator
                signal = self.signal_generator.add_candle(candle_data[-1])
                
                # If no traditional signal, continue to next asset
                if not signal:
                    continue
                    
                # Use ML to validate signal if available
                ml_prediction = None
                ml_confidence = 0.0
                ml_details = {}
                
                if self.use_ml and hasattr(self, 'ml_predictor'):
                    try:
                        # Get ML prediction
                        prediction, confidence, details = self.ml_predictor.predict(df)
                        
                        # Get market regime from signal generator
                        market_regime = self.signal_generator.current_regime.name if self.signal_generator.current_regime else "UNKNOWN"
                        
                        # Validate ML prediction against market conditions
                        is_valid, adjusted_confidence, validation_details = self.ml_predictor.validate_prediction(
                            prediction, 
                            confidence, 
                            market_regime, 
                            "unknown",  # Session info not available in basic version
                            details.get('is_anomaly', False)
                        )
                        
                        ml_prediction = "BUY" if prediction else "SELL"
                        ml_confidence = adjusted_confidence
                        ml_details = {
                            "prediction": ml_prediction,
                            "confidence": ml_confidence,
                            "top_features": details.get("top_features", {})
                        }
                        
                        # If ML and traditional signals agree, boost confidence
                        if (signal.direction == "BUY" and ml_prediction == "BUY") or \
                           (signal.direction == "SELL" and ml_prediction == "SELL"):
                            signal.confidence = (signal.confidence * 0.6) + (ml_confidence * 0.4)
                            logger.info(f"ML prediction confirms {signal.direction} signal, boosting confidence to {signal.confidence:.2f}")
                        else:
                            # ML contradicts traditional signal, reduce confidence
                            signal.confidence = signal.confidence * 0.8
                            logger.info(f"ML prediction contradicts traditional signal, reducing confidence")
                    
                    except Exception as e:
                        logger.error(f"Error using ML predictor: {e}")
                
                # Add ML details to indicators
                signal.indicators['ml_prediction'] = ml_prediction
                signal.indicators['ml_confidence'] = ml_confidence
                if ml_details.get("top_features"):
                    signal.indicators['ml_top_features'] = list(ml_details.get("top_features", {}).keys())[:3]
                
                # Only send signals with sufficient confidence
                if signal.confidence >= 0.7:
                    logger.info(f"Signal generated: {signal.direction} {signal.asset} with {signal.confidence:.2f} confidence")
                    self.telegram.send_signal(signal.direction, signal.asset, signal.confidence, signal.indicators)
                    return True
                    
            except Exception as e:
                logger.error(f"Error analyzing {asset}: {e}")
        
        return False

    def run(self):
        """Main bot loop - Analysis Only Mode"""
        logger.info("Starting IQ 720 Trading Bot in Analysis-Only Mode...")
        
        # Send startup message
        startup_time = datetime.now()
        startup_msg = f"🤖 IQ 720 Trading Bot started in <b>Analysis-Only Mode</b> at {startup_time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.telegram.send_message(startup_msg)
        logger.info("Bot started successfully")
        
        # Main loop - check market every minute
        while self.running:
            try:
                # Check if it's time for a status update (:00 or :30)
                if self.is_time_for_status():
                    current_time = datetime.now()
                    
                    # Only send if we haven't sent a status message in the last minute
                    # This prevents duplicate messages if the loop runs multiple times during XX:00 or XX:30
                    if not self.last_status_time or (current_time - self.last_status_time).total_seconds() > 60:
                        status_msg = f"📊 Bot Status Update: Running and monitoring markets at {current_time.strftime('%H:%M')}"
                        self.telegram.send_message(status_msg)
                        self.last_status_time = current_time
                        logger.info("Sent regular status update")
                
                # Check for trading opportunities
                self.analyze_market_and_generate_signal()
                
                # Sleep for 60 seconds before checking again
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                # Sleep for a short time to prevent excessive error logging
                time.sleep(10)
        
        # Send shutdown message
        shutdown_time = datetime.now()
        shutdown_msg = f"🛑 IQ 720 Trading Bot shutting down at {shutdown_time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.telegram.send_message(shutdown_msg)
        logger.info("Bot shutdown complete")


    def load_config(self, config_path):
        """Load configuration from file or use default values"""
        try:
            # Try to load from file
            import yaml
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    config = yaml.safe_load(file)
                logger.info(f"Configuration loaded from {config_path}")
                return config
            else:
                logger.warning(f"Config file {config_path} not found, using default configuration")
                
                # Default configuration
                default_config = {
                    'telegram': {
                        'token': os.environ.get('TELEGRAM_TOKEN', ''),
                        'chat_id': os.environ.get('TELEGRAM_CHAT_ID', ''),
                    },
                    'data_source': {
                        'api_key': os.environ.get('API_KEY', ''),
                        'api_secret': os.environ.get('API_SECRET', ''),
                    },
                    'trading': {
                        'max_positions': 3,
                        'risk_per_trade': 0.02,
                        'default_stop_loss': 0.03,
                        'default_take_profit': 0.06,
                    },
                    'use_ml': False,
                    'ml': {
                        'model_path': 'models/',
                        'confidence_threshold': 0.7,
                        'use_ensemble': True
                    }
                }
                
                return default_config
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Basic default configuration as fallback
            return {
                'telegram': {'token': '', 'chat_id': ''},
                'data_source': {'api_key': '', 'api_secret': ''},
                'trading': {'max_positions': 3, 'risk_per_trade': 0.02},
                'use_ml': False
            }


if __name__ == "__main__":
    # Load environment variables from .env file if present
    load_dotenv()
    
    try:
        bot = TradingBot(analysis_mode=True)
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        sys.exit(1)
