#!/usr/bin/env python
"""
IQ 720 Trading Bot - Enhanced Entry Point
This script runs the improved version of the trading bot with:
- Fixed data leakage issues
- Improved ML model calibration
- Better uncertainty handling
- Enhanced signal generation
- Adaptive parameters based on market conditions
"""
import os
import time
import logging
import signal
import sys
try:
    import yaml
except ImportError:
    print("Warning: yaml module not installed. Installing pyyaml...")
    import sys, subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyyaml'])
    import yaml

try:
    import pytz
except ImportError:
    print("Warning: pytz module not installed. Installing pytz...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pytz'])
    import pytz

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import improved components
from src.data_fetcher import IQOptionDataFetcher
from src.improved_signal_generator import ImprovedSignalGenerator
from src.utils.improved_ml_predictor import ImprovedMLPredictor
from src.utils.market_availability import MarketAvailabilityManager
import requests
try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: dotenv module not installed. Installing python-dotenv...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-dotenv'])
    from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/trading.log")
    ]
)
logger = logging.getLogger("IQ720Bot")

class TelegramNotifier:
    """Telegram notification service for trading signals and status updates"""
    
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
    
    def send_signal(self, signal):
        """Send a trading signal alert to Telegram with uncertainty information"""
        try:
            # Format confidence as percentage and stars
            confidence_pct = signal.confidence * 100
            confidence_stars = "⭐" * int(round(signal.confidence * 5))
            
            # Format uncertainty as a warning level
            uncertainty_pct = signal.uncertainty * 100
            uncertainty_warning = ""
            if signal.uncertainty > 0.4:
                uncertainty_warning = "⚠️ <b>High uncertainty</b>"
            elif signal.uncertainty > 0.25:
                uncertainty_warning = "⚠️ <i>Moderate uncertainty</i>"
            
            # Check if we have correlation confirmation information
            correlation_info = ""
            if hasattr(signal, 'indicators') and 'correlation_confirmation' in signal.indicators:
                correlation_status = signal.indicators['correlation_confirmation']
                
                # Add appropriate emoji based on confirmation level
                emoji = "✅" if "confirmation" in correlation_status.lower() else "⚠️" if "contradiction" in correlation_status.lower() else "➖"
                
                correlation_info = f"\n<b>Correlation Analysis:</b> {emoji} {correlation_status}"
            
            # Get market type badge
            market_badge = "🟢 Regular" if not hasattr(signal, 'market_type') or signal.market_type == 'regular' else "🟠 OTC"
            
            # Format the message
            message = f"""
🚨 <b>TRADING SIGNAL</b> 🚨

Asset: {signal.asset} <b>({market_badge})</b>
Direction: {'📈' if signal.direction == 'BUY' else '📉'} <b>{signal.direction}</b>
Expiry: {signal.expiry_minutes} minute(s)
Confidence: {confidence_stars} ({confidence_pct:.2f}%)
{uncertainty_warning}

<b>Technical Indicators:</b>
RSI: {signal.indicators['rsi']:.2f}
MACD: {signal.indicators['macd']:.5f}
Volume: {signal.indicators['volume_ratio']:.2f}x average
Market Regime: {signal.indicators['regime']}{correlation_info}

⚠️ <i>Manual execution required</i>
⏰ Generated: {datetime.now().strftime('%H:%M:%S')} UTC
"""
            return self.send_message(message.strip())
        except Exception as e:
            self.logger.error(f"Failed to send signal: {str(e)}")
            return False


class EnhancedTradingBot:
    def __init__(self, config_path='config.yaml', analysis_mode=True):
        """Initialize the trading bot with configuration"""
        self.config = self.load_config(config_path)
        self.analysis_mode = analysis_mode
        
        # Create directories if they don't exist
        os.makedirs("logs", exist_ok=True)
        os.makedirs("models", exist_ok=True)
        
        # Set up system components
        self.setup_components()
        
        # Trading state
        self.active = False
        self.last_signal_time = None
        self.last_status_time = None
        
        # ML configuration
        self.use_ml = self.config.get('use_ml', True)  # Default to using ML
        
        logger.info("IQ-720 Enhanced Trading Bot initialized")
    
    def setup_components(self):
        """Set up the necessary components for the trading bot"""
        try:
            # Data fetcher for retrieving market data
            self.data_fetcher = IQOptionDataFetcher(self.config.get('data_source', {}))
            
            # Use improved signal generator
            self.signal_generator = ImprovedSignalGenerator(self.config)
            
            # Initialize pair correlation analyzer
            from src.utils.pair_correlation_analyzer import PairCorrelationAnalyzer
            self.correlation_analyzer = PairCorrelationAnalyzer(
                self.data_fetcher,
                self.config
            )
            
            # Initialize market availability manager
            self.market_availability = MarketAvailabilityManager()
            
            # Trade executor for placing trades (if not in analysis mode)
            if not self.analysis_mode:
                from src.trade_executor import TradeExecutor
                self.trade_executor = TradeExecutor(self.config)
            
            # Telegram notification service
            telegram_token = self.config.get('telegram', {}).get('token', '')
            telegram_chat_id = self.config.get('telegram', {}).get('chat_id', '')
            self.telegram = TelegramNotifier(telegram_token, telegram_chat_id)
            
            # Set running flag
            self.running = True
            
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
        
        # Stop correlation analyzer thread if it exists
        if hasattr(self, 'correlation_analyzer'):
            try:
                self.correlation_analyzer.stop()
                logger.info("Correlation analyzer thread stopped")
            except Exception as e:
                logger.error(f"Error stopping correlation analyzer: {e}")

    def is_time_for_status(self):
        """Check if it's time to send a status message (every :00 and :30)"""
        now = datetime.now()
        minutes = now.minute
        
        # Send at XX:00 and XX:30
        return minutes == 0 or minutes == 30
        
    def _get_confirmation_strength(self, correlation_score):
        """Convert correlation confirmation score to descriptive text"""
        if correlation_score > 0.8:
            return "Strong confirmation"
        elif correlation_score > 0.5:
            return "Moderate confirmation"
        elif correlation_score > 0.2:
            return "Weak confirmation"
        elif correlation_score > -0.2:
            return "Neutral"
        elif correlation_score > -0.5:
            return "Weak contradiction"
        elif correlation_score > -0.8:
            return "Moderate contradiction"
        else:
            return "Strong contradiction"

    def analyze_market_and_generate_signal(self):
        """
        Analyze market data and generate trading signals using improved methods
        """
        # Get latest market data for a wide range of forex pairs, commodities, and indices
        assets = self.config.get('trading_pairs', [
            # Major forex pairs
            'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD',
            # Minor forex pairs
            'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'EUR/AUD', 'GBP/AUD',
            # Exotic pairs
            'USD/SGD', 'USD/ZAR', 'USD/TRY', 'USD/MXN',
            # Commodity pairs
            'USD/NOK', 'USD/SEK', 'USD/DKK', 'AUD/CAD', 'NZD/CAD',
            # Cross pairs
            'EUR/CAD', 'GBP/CAD', 'EUR/NZD', 'GBP/NZD'
        ])
        
        # Get current market session (Asian, European, American)
        current_hour = datetime.now().hour
        current_session = "Asian" if 0 <= current_hour < 8 else "European" if 8 <= current_hour < 16 else "American"
        
        # Optional: Filter pairs by current session for efficiency
        if self.config.get('session_specific_pairs', True):
            session_pairs = {
                "Asian": ['USD/JPY', 'AUD/USD', 'NZD/USD', 'AUD/JPY', 'USD/SGD', 'EUR/JPY', 'GBP/JPY'],
                "European": ['EUR/USD', 'GBP/USD', 'EUR/GBP', 'EUR/JPY', 'EUR/CAD', 'GBP/CAD', 'EUR/AUD', 'GBP/AUD'],
                "American": ['USD/CAD', 'EUR/USD', 'USD/MXN', 'GBP/USD', 'USD/CHF', 'AUD/USD', 'NZD/USD']
            }
            # Get pairs for current session + some universal pairs
            session_specific = set(session_pairs.get(current_session, []))
            universal_pairs = {'EUR/USD', 'GBP/USD', 'USD/JPY'}  # Always analyze these
            assets_to_analyze = list(session_specific.union(universal_pairs))
            logger.info(f"Current session: {current_session}, analyzing {len(assets_to_analyze)} pairs")
        else:
            # Use all configured pairs
            assets_to_analyze = assets
            logger.info(f"Analyzing all {len(assets_to_analyze)} configured pairs")
        
        # Track best signal for potential trade
        best_signal = None
        best_confidence = 0
        
        for asset in assets_to_analyze:
            try:
                # Check market availability
                market_status = self.market_availability.get_best_available_market(asset)
                if not market_status[0]:
                    logger.debug(f"Market not available for {asset}: {market_status[2]}")
                    continue
                
                # Get market type (regular or otc)
                market_type = market_status[1]
                logger.debug(f"Analyzing {asset} ({market_type})")
                
                # Get candle data
                candle_data = self.data_fetcher.get_candles(asset)
                if not candle_data or len(candle_data) < 50:  # Need sufficient data for analysis
                    logger.debug(f"Not enough data for {asset}, skipping")
                    continue
                    
                # Generate signal using improved signal generator
                signal = self.signal_generator.add_candle(candle_data[-1], asset_name=asset)
                
                # If a valid signal is generated, track it as a potential trade
                if signal and signal.confidence >= self.config.get('min_confidence', 0.6):
                    # Add market type to signal
                    signal.market_type = market_type
                    
                    logger.info(f"Signal detected: {signal.direction} {signal.asset} ({signal.market_type}) with {signal.confidence:.2f} confidence (uncertainty: {signal.uncertainty:.2f})")
                    
                    # Store the best signal based on confidence and uncertainty
                    adjusted_confidence = signal.confidence * (1 - signal.uncertainty)  # Adjust for uncertainty
                    if adjusted_confidence > best_confidence:
                        best_confidence = adjusted_confidence
                        best_signal = signal
                    
            except Exception as e:
                logger.error(f"Error analyzing {asset}: {e}")
        
        # After analyzing all assets, execute the best signal if one was found
        if best_signal and best_confidence > self.config.get('min_confidence', 0.6):
            # Check for correlation confirmation if correlation analyzer is initialized
            correlation_confirmation = 0
            if hasattr(self, 'correlation_analyzer') and self.correlation_analyzer.is_initialized:
                # Get correlation confirmation score (-1 to 1)
                correlation_confirmation = self.correlation_analyzer.evaluate_signal_confirmation(best_signal)
                
                # Get highly correlated pairs
                correlated_group = self.correlation_analyzer.get_correlation_group(best_signal.asset)
                
                if correlated_group and len(correlated_group) > 1:
                    logger.info(f"Correlated pairs for {best_signal.asset}: {', '.join([p for p in correlated_group if p != best_signal.asset])}")
                
                # Log confirmation score
                logger.info(f"Correlation confirmation score: {correlation_confirmation:.2f} ({self._get_confirmation_strength(correlation_confirmation)})")
                
                # Adjust confidence based on correlation confirmation
                # Strong confirmation can boost confidence, strong contradiction can reduce it
                if correlation_confirmation != 0:
                    # Scale confirmation effect by configuration
                    confirmation_impact = self.config.get('correlation_impact', 0.2)
                    adjusted_confidence = best_signal.confidence * (1 + correlation_confirmation * confirmation_impact)
                    
                    # Cap at 0.95 to prevent overconfidence
                    adjusted_confidence = min(adjusted_confidence, 0.95)
                    logger.info(f"Confidence adjusted from {best_signal.confidence:.2f} to {adjusted_confidence:.2f} based on correlation analysis")
                    best_signal.confidence = adjusted_confidence
            
            # Log the signal selection
            logger.info(f"Best signal selected: {best_signal.direction} {best_signal.asset} with {best_signal.confidence:.2f} confidence (uncertainty: {best_signal.uncertainty:.2f})")
            
            # Add correlation info to the signal for notification
            if hasattr(best_signal, 'indicators') and correlation_confirmation != 0:
                best_signal.indicators['correlation_confirmation'] = self._get_confirmation_strength(correlation_confirmation)
            
            # Send notification
            self.telegram.send_signal(best_signal)
            
            # Execute trade if not in analysis mode
            if not self.analysis_mode and hasattr(self, 'trade_executor'):
                self.trade_executor.execute_trade(
                    best_signal.asset,
                    best_signal.direction,
                    best_signal.expiry_minutes,
                    confidence=best_signal.confidence
                )
            
            return True
            
        logger.debug("No qualifying signals found in this analysis cycle")
        return False

    def run(self):
        """Main bot loop - Enhanced version with better error handling and status reporting"""
        logger.info(f"Starting IQ 720 Enhanced Trading Bot in {'Analysis-Only' if self.analysis_mode else 'Live Trading'} Mode...")
        
        # Send startup message
        startup_time = datetime.now()
        startup_msg = f"🤖 IQ 720 Enhanced Trading Bot started in <b>{'Analysis-Only' if self.analysis_mode else 'Live Trading'}</b> Mode at {startup_time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.telegram.send_message(startup_msg)
        logger.info("Bot started successfully")
        
        # Reset daily counters at startup
        self.signal_generator.reset_daily_counter()
        
        # Main loop
        while self.running:
            try:
                # Check if it's a new day (midnight UTC) to reset counters
                current_time = datetime.now()
                if current_time.hour == 0 and current_time.minute < 5:
                    if not self.last_status_time or self.last_status_time.day != current_time.day:
                        logger.info("New day detected, resetting daily counters")
                        self.signal_generator.reset_daily_counter()
                        self.telegram.send_message("📅 New trading day started. Daily counters reset.")
                
                # Check if it's time for a status update (:00 or :30)
                if self.is_time_for_status():
                    # Only send if we haven't sent a status message in the last minute
                    if not self.last_status_time or (current_time - self.last_status_time).total_seconds() > 60:
                        # Prepare correlation status if available
                        correlation_status = ""
                        if hasattr(self, 'correlation_analyzer') and self.correlation_analyzer.is_initialized:
                            status = self.correlation_analyzer.get_status_summary()
                            correlation_status = f"\nCorrelation Analysis: Active ({status['pairs_analyzed']} pairs, {status['correlation_groups']} groups)"
                            
                        # Get market availability information
                        market_status = ""
                        if hasattr(self, 'market_availability'):
                            status = self.market_availability.get_market_status_summary()
                            regular_count = len(status['regular_open'])
                            otc_count = len(status['otc_open'])
                            market_status = f"\nMarkets: {regular_count} regular & {otc_count} OTC markets open"
                        
                        # Build status message
                        status_msg = (
                            f"📊 Bot Status Update: Running and monitoring markets\n"
                            f"Time: {current_time.strftime('%H:%M')}\n"
                            f"Market Regime: {self.signal_generator.current_regime.value if hasattr(self.signal_generator, 'current_regime') else 'Unknown'}\n"
                            f"Session: {self.signal_generator.current_session.value if hasattr(self.signal_generator, 'current_session') else 'Unknown'}\n"
                            f"Signals Today: {self.signal_generator.trades_today}"
                            f"{correlation_status}"
                            f"{market_status}"
                        )
                        self.telegram.send_message(status_msg)
                        self.last_status_time = current_time
                        logger.info("Sent regular status update")
                
                # Check for trading opportunities
                self.analyze_market_and_generate_signal()
                
                # Sleep to prevent excessive API calls
                time.sleep(30)  # Check every 30 seconds instead of 60
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                # Sleep for a short time to prevent excessive error logging
                time.sleep(10)
        
        # Send shutdown message
        shutdown_time = datetime.now()
        shutdown_msg = f"🛑 IQ 720 Enhanced Trading Bot shutting down at {shutdown_time.strftime('%Y-%m-%d %H:%M:%S')}"
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
                
                # Enhanced default configuration
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
                        'risk_per_trade': 0.01,  # Reduced from 0.02
                        'default_stop_loss': 0.02,  # Tighter stop loss
                        'default_take_profit': 0.04,  # Adjusted take profit
                        'max_daily_trades': 5,
                        'min_signal_interval_minutes': 30
                    },
                    'use_ml': True,
                    'min_confidence': 0.65,
                    'ml': {
                        'model_path': 'models/',
                        'confidence_threshold': 0.65,
                        'use_ensemble': True,
                        'lookback_periods': 100,
                        'sequence_length': 20
                    },
                    'trading_pairs': [
                        # Major forex pairs
                        'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD',
                        # Minor forex pairs
                        'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'EUR/AUD', 'GBP/AUD',
                        # Exotic pairs
                        'USD/SGD', 'USD/ZAR', 'USD/TRY', 'USD/MXN',
                        # Commodity pairs
                        'USD/NOK', 'USD/SEK', 'USD/DKK', 'AUD/CAD', 'NZD/CAD',
                        # Cross pairs
                        'EUR/CAD', 'GBP/CAD', 'EUR/NZD', 'GBP/NZD'
                    ],
                    'session_specific_pairs': True,  # Enable session-specific pair filtering
                    'news_filter': {
                        'enabled': True,
                        'buffer_minutes': 15,
                        'importance_threshold': 'medium'
                    }
                }
                
                return default_config
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Basic default configuration as fallback
            return {
                'telegram': {'token': '', 'chat_id': ''},
                'data_source': {'api_key': '', 'api_secret': ''},
                'trading': {'max_positions': 2, 'risk_per_trade': 0.01},
                'use_ml': True,
                'min_confidence': 0.65
            }


if __name__ == "__main__":
    # Load environment variables from .env file if present
    load_dotenv()
    
    try:
        # Default to analysis mode for safety
        bot = EnhancedTradingBot(analysis_mode=True)
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        sys.exit(1)
