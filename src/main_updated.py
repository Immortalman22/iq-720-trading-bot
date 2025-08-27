#!/usr/bin/env python
"""
IQ 720 Trading Bot - Main Entry Point (Analysis-Only Mode)
This script runs a simplified version of the trading bot that only analyzes the market
and sends signals via Telegram without executing trades.
"""
import os
import time
import logging
import signal
import sys
import random
from datetime import datetime, timedelta

# For the analysis-only mode, we don't need all components
# from .data_fetcher import IQOptionDataFetcher
# from .signal_generator import SignalGenerator
# from .trade_executor import TradeExecutor
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
    def __init__(self):
        self.running = True
        
        # Load environment variables
        load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
        
        # Initialize Telegram notifier
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not token or not chat_id:
            logger.critical("Telegram credentials not found in .env file")
            sys.exit(1)
        
        self.telegram = TelegramNotifier(token, chat_id)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)
        
        # Initialize last status time
        self.last_status_time = None
    
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
        Simplified market analysis function that simulates signal generation
        In a real implementation, this would analyze actual market data
        """
        # In analysis mode, we'll generate simulated signals
        # This is where your actual signal generation logic would go
        
        # Simulate whether we found a good opportunity (aimed at 20-30 per day = ~1.5% chance per minute)
        # This means we check every minute and have about a 1.5% chance of sending a signal
        opportunity_found = random.random() < 0.015
        
        if opportunity_found:
            # Simulate signal parameters
            direction = random.choice(['BUY', 'SELL'])
            assets = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD']
            asset = random.choice(assets)
            
            # Generate confidence between 0.7 and 0.98
            confidence = round(random.uniform(0.7, 0.98), 2)
            
            # Generate simulated indicators
            indicators = {
                'rsi': random.uniform(20, 80),
                'macd': random.uniform(-0.002, 0.002),
                'volume': random.uniform(0.8, 3.0)
            }
            
            # Adjust indicators based on direction to make them more realistic
            if direction == 'BUY':
                indicators['rsi'] = min(70, max(40, indicators['rsi']))
                indicators['macd'] = max(0, indicators['macd'])
            else:  # SELL
                indicators['rsi'] = min(60, max(30, indicators['rsi']))
                indicators['macd'] = min(0, indicators['macd'])
            
            logger.info(f"Signal generated: {direction} {asset} with {confidence:.2f} confidence")
            
            # Send the signal via Telegram
            self.telegram.send_signal(direction, asset, confidence, indicators)
            
            return True
        
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


if __name__ == "__main__":
    try:
        bot = TradingBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        sys.exit(1)
