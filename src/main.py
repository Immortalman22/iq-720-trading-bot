#!/usr/bin/env python
"""
IQ 720 Trading Bot - Main Entry Point
This script initializes and runs the trading bot.
"""
import os
import time
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from .data_fetcher import IQOptionDataFetcher
from .signal_generator import SignalGenerator
from .trade_executor import TradeExecutor
from .telegram_notifier import TelegramNotifier
from .utils.config import Config
from .utils.logger import setup_logger
from .utils.dynamic_risk_manager import DynamicRiskManager

# Configure logging
logger = setup_logger()

class TradingBot:
    def __init__(self):
        self.running = True
        self.config = Config()
        self.signal_generator = SignalGenerator()
        self.risk_manager = DynamicRiskManager(self.config)
        self.trade_executor = TradeExecutor(self.config, self.risk_manager)
        
        # Initialize Telegram notifier if configured
        self.telegram = None
        if self.config.TELEGRAM_ENABLED:
            self.telegram = TelegramNotifier(self.config.TELEGRAM_TOKEN)
            
        # Initialize data fetcher with callback
        self.data_fetcher = IQOptionDataFetcher(
            self.config, 
            self.on_candle_received
        )
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)
    
    def handle_exit(self, signum, frame):
        """Handle exit signals gracefully"""
        logger.info("Received exit signal. Shutting down gracefully...")
        self.running = False
    
    def on_candle_received(self, candle_data: dict) -> None:
        """Callback function for when new candle data is received"""
        try:
            # Generate signal from candle data
            signal = self.signal_generator.add_candle(candle_data)
            
            # If a trading signal was generated, execute it
            if signal:
                logger.info(f"Signal generated: {signal.direction} {signal.asset} "
                           f"with {signal.confidence:.2f} confidence")
                
                # Execute the trade
                trade_result = self.trade_executor.execute_trade(signal)
                
                # Send notification if enabled
                if self.telegram and trade_result:
                    self.telegram.send_trade_notification(signal, trade_result)
        
        except Exception as e:
            logger.error(f"Error processing candle: {str(e)}")
    
    def run(self):
        """Main bot loop"""
        logger.info("Starting IQ 720 Trading Bot...")
        
        # Connect to data source
        self.data_fetcher.connect()
        
        # Main loop - keep the bot alive
        startup_time = datetime.now()
        logger.info(f"Bot started successfully at {startup_time}")
        
        if self.telegram:
            self.telegram.send_message(f"🤖 IQ 720 Trading Bot started at {startup_time}")
        
        # Keep the main thread alive while the data fetcher works in background
        while self.running:
            try:
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
        
        # Cleanup on exit
        self.data_fetcher.disconnect()
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    try:
        bot = TradingBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        sys.exit(1)
