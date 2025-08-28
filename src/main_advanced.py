#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enhanced Main Module for IQ-720 Trading Bot

This module integrates all advanced trading components:
- Enhanced ML predictor
- Dynamic asset selection
- Market regime detection
- Adaptive exit strategies
- Position sizing
- Market availability checks
"""

import os
import sys
import time
import logging
import json
import argparse
import pandas as pd
from datetime import datetime, timedelta
import traceback
from iqoptionapi.stable_api import IQOptionAPI

# Import our enhanced modules
from utils.config import load_config
from utils.logger import setup_logger
from utils.data_fetcher import DataFetcher
from utils.enhanced_trading_strategy import EnhancedTradingStrategy, TradingMode
from utils.market_availability import MarketAvailability
from utils.dynamic_asset_selector import DynamicAssetSelector
from utils.telegram_notifier import TelegramNotifier
from utils.email_notifier import EmailNotifier
from utils.ml_predictor import MLPredictor

# Set up logging
logger = setup_logger("MainEnhanced", "logs/trading.log")

class EnhancedTradingBot:
    """
    Enhanced trading bot with advanced features.
    
    Features:
    - Multi-pair trading with dynamic selection
    - Market regime adaptation
    - Return prediction and position sizing
    - Adaptive exit strategies
    - Market availability checks
    """
    
    def __init__(self, config_path="config.json"):
        """
        Initialize the enhanced trading bot.
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Set up components
        self._setup_components()
        
        # Trading state
        self.is_running = False
        self.last_check_time = None
        self.active_trades = {}
        
        logger.info("Enhanced Trading Bot initialized")
    
    def _setup_components(self):
        """Set up bot components"""
        
        # Set up IQ Option API connection
        self.api = IQOptionAPI(self.config.get("iqoption", {}).get("email"),
                              self.config.get("iqoption", {}).get("password"))
        
        # Set up data fetcher
        self.data_fetcher = DataFetcher(self.api)
        
        # Set up market availability checker
        availability_config = self.config.get("market_availability", {})
        self.market_checker = MarketAvailability(availability_config)
        
        # Set up dynamic asset selector
        asset_selector_config = self.config.get("dynamic_asset_selector", {})
        self.asset_selector = DynamicAssetSelector(asset_selector_config)
        
        # Set up ML predictor
        ml_config = self.config.get("ml_predictor", {})
        self.ml_predictor = MLPredictor(ml_config)
        
        # Set up enhanced trading strategy
        strategy_config = self.config.get("trading_strategy", {})
        account_balance = self.config.get("account", {}).get("initial_balance", 1000)
        self.strategy = EnhancedTradingStrategy(strategy_config, account_balance)
        
        # Set up notification systems
        telegram_config = self.config.get("telegram", {})
        if telegram_config.get("enabled", False):
            self.telegram = TelegramNotifier(
                telegram_config.get("token"),
                telegram_config.get("chat_id")
            )
        else:
            self.telegram = None
            
        email_config = self.config.get("email", {})
        if email_config.get("enabled", False):
            self.email = EmailNotifier(
                email_config.get("smtp_server"),
                email_config.get("port"),
                email_config.get("username"),
                email_config.get("password"),
                email_config.get("from_email"),
                email_config.get("to_email")
            )
        else:
            self.email = None
            
        # Trading parameters
        self.trading_pairs = self.config.get("trading", {}).get("pairs", [])
        self.timeframe = self.config.get("trading", {}).get("timeframe", 5)
        self.check_interval = self.config.get("trading", {}).get("check_interval", 60)
        self.max_active_trades = self.config.get("trading", {}).get("max_active_trades", 3)
    
    def connect(self):
        """
        Connect to IQ Option API.
        
        Returns:
            Boolean indicating success
        """
        try:
            logger.info("Connecting to IQ Option API...")
            self.api.connect()
            
            # Check connection
            if self.api.check_connect():
                logger.info("Successfully connected to IQ Option")
                return True
            else:
                logger.error("Failed to connect to IQ Option")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to IQ Option: {e}")
            return False
    
    def update_account_balance(self):
        """
        Update account balance from IQ Option.
        
        Returns:
            Current balance (float)
        """
        try:
            # Get balance from IQ Option
            balance = self.api.get_balance()
            
            # Update strategy with new balance
            self.strategy.update_account_balance(balance)
            
            logger.info(f"Account balance updated: {balance}")
            return balance
            
        except Exception as e:
            logger.error(f"Error updating account balance: {e}")
            return None
    
    def select_trading_pairs(self, current_time=None):
        """
        Select appropriate trading pairs based on time and availability.
        
        Args:
            current_time: Current time (datetime)
            
        Returns:
            List of trading pairs
        """
        if current_time is None:
            current_time = datetime.now()
            
        # Start with configured pairs
        all_pairs = self.trading_pairs.copy()
        
        # Dynamic selection if enabled
        if self.config.get("trading", {}).get("use_dynamic_selection", False):
            dynamic_pairs = self.asset_selector.select_assets(current_time)
            all_pairs.extend([p for p in dynamic_pairs if p not in all_pairs])
        
        # Filter by market availability
        available_pairs = []
        for pair in all_pairs:
            is_available, market_type = self.market_checker.check_availability(pair, current_time)
            if is_available:
                available_pairs.append((pair, market_type))
                
        # Log available pairs
        logger.info(f"Selected {len(available_pairs)} available trading pairs")
        
        return available_pairs
    
    def fetch_market_data(self, pairs):
        """
        Fetch market data for selected pairs.
        
        Args:
            pairs: List of (pair, market_type) tuples
            
        Returns:
            Dictionary of market data by pair
        """
        market_data = {}
        
        for pair, market_type in pairs:
            try:
                # Get appropriate market type parameter
                market = "turbo-option" if market_type == "regular" else market_type
                
                # Fetch data from IQ Option
                data = self.data_fetcher.get_candles(pair, self.timeframe, 100, market)
                
                if data is not None and len(data) > 0:
                    market_data[pair] = data
                    logger.debug(f"Fetched {len(data)} candles for {pair} ({market_type})")
                    
            except Exception as e:
                logger.error(f"Error fetching data for {pair}: {e}")
                
        logger.info(f"Fetched market data for {len(market_data)} pairs")
        return market_data
    
    def generate_trading_signals(self, market_data):
        """
        Generate trading signals using ML predictor.
        
        Args:
            market_data: Dictionary of market data by pair
            
        Returns:
            Dictionary of trading signals by pair
        """
        signals = {}
        
        for pair, data in market_data.items():
            try:
                # Generate prediction
                prediction = self.ml_predictor.predict(data)
                
                if prediction and 'direction' in prediction:
                    # Add current price
                    prediction['current_price'] = data['close'].iloc[-1]
                    signals[pair] = prediction
                    
            except Exception as e:
                logger.error(f"Error generating signal for {pair}: {e}")
                
        logger.info(f"Generated {len(signals)} trading signals")
        return signals
    
    def execute_signals(self, signals, market_data, current_time=None):
        """
        Execute trading signals.
        
        Args:
            signals: Dictionary of trading signals by pair
            market_data: Dictionary of market data by pair
            current_time: Current time
            
        Returns:
            List of executed trades
        """
        if current_time is None:
            current_time = datetime.now()
            
        # Evaluate signals with enhanced strategy
        evaluated_signals = self.strategy.evaluate_trading_signals(
            signals, market_data, current_time
        )
        
        executed_trades = []
        
        # Execute each signal
        for signal in evaluated_signals:
            try:
                trade_info = self.strategy.execute_trade(signal)
                
                if trade_info:
                    # Execute on IQ Option platform
                    result = self._place_iq_option_trade(trade_info)
                    
                    if result:
                        executed_trades.append(trade_info)
                        
                        # Send notifications
                        self._send_trade_notifications(trade_info, "NEW_TRADE")
                        
            except Exception as e:
                logger.error(f"Error executing trade: {e}")
                
        return executed_trades
    
    def _place_iq_option_trade(self, trade_info):
        """
        Place trade on IQ Option platform.
        
        Args:
            trade_info: Trade information dictionary
            
        Returns:
            Boolean indicating success
        """
        try:
            pair = trade_info.get('pair')
            direction = trade_info.get('direction')
            expiry_minutes = trade_info.get('exit_info', {}).get('time_exit', self.timeframe)
            position_size = trade_info.get('position_info', {}).get('position_size', 1)
            market_type = trade_info.get('market_type', 'regular')
            
            # Choose market type for IQ Option API
            market = "turbo-option" if market_type == "regular" else market_type
            
            # Place trade on IQ Option
            result = self.api.buy(
                price=position_size,
                active=pair,
                direction=direction.lower(),
                duration=expiry_minutes,
                market=market
            )
            
            if result:
                logger.info(f"Successfully placed {direction} trade for {pair} "
                           f"with size {position_size}")
                return True
            else:
                logger.error(f"Failed to place trade for {pair}")
                return False
                
        except Exception as e:
            logger.error(f"Error placing IQ Option trade: {e}")
            return False
    
    def check_active_trades(self, market_data, current_time=None):
        """
        Check active trades for exit conditions and update trailing stops.
        
        Args:
            market_data: Dictionary of market data by pair
            current_time: Current time
            
        Returns:
            List of exited trades
        """
        if current_time is None:
            current_time = datetime.now()
            
        # Get current prices
        current_prices = {}
        for pair, data in market_data.items():
            if len(data) > 0:
                current_prices[pair] = data['close'].iloc[-1]
                
        # Update trailing stops
        self.strategy.update_trailing_stops(current_prices)
        
        # Check exit conditions
        trades_to_exit = self.strategy.check_exit_conditions(current_prices, current_time)
        
        exited_trades = []
        
        # Process trades to exit
        for trade_id, exit_info in trades_to_exit.items():
            try:
                # Close position on IQ Option
                result = self._close_iq_option_trade(exit_info['trade_info'], exit_info['exit_reason'])
                
                if result:
                    # Calculate profit/loss
                    entry_price = exit_info['trade_info'].get('entry_price', 0)
                    exit_price = exit_info['exit_price']
                    direction = exit_info['trade_info'].get('direction')
                    
                    if direction == 'BUY':
                        profit_pct = (exit_price - entry_price) / entry_price
                    else:
                        profit_pct = (entry_price - exit_price) / entry_price
                        
                    # Record trade result
                    win = profit_pct > 0
                    self.strategy.add_trade_result(trade_id, win, profit_pct)
                    
                    # Add exit info to trade info
                    trade_info = exit_info['trade_info'].copy()
                    trade_info['exit_time'] = exit_info['exit_time']
                    trade_info['exit_price'] = exit_price
                    trade_info['exit_reason'] = exit_info['exit_reason']
                    trade_info['profit_pct'] = profit_pct
                    trade_info['win'] = win
                    
                    exited_trades.append(trade_info)
                    
                    # Send notifications
                    self._send_trade_notifications(trade_info, "EXIT_TRADE")
                    
            except Exception as e:
                logger.error(f"Error closing trade {trade_id}: {e}")
                
        return exited_trades
    
    def _close_iq_option_trade(self, trade_info, exit_reason):
        """
        Close trade on IQ Option platform.
        
        Args:
            trade_info: Trade information dictionary
            exit_reason: Reason for closing trade
            
        Returns:
            Boolean indicating success
        """
        try:
            # For IQ Option binary options, we typically can't close early
            # This would be for selling forex/CFD positions
            logger.info(f"Trade {trade_info.get('id')} will close automatically at expiry")
            return True
            
        except Exception as e:
            logger.error(f"Error closing IQ Option trade: {e}")
            return False
    
    def _send_trade_notifications(self, trade_info, event_type):
        """
        Send trade notifications.
        
        Args:
            trade_info: Trade information dictionary
            event_type: Type of event (NEW_TRADE, EXIT_TRADE)
        """
        # Get trade summary
        summary = self.strategy.get_trade_summary(trade_info)
        
        # Add event type specific details
        if event_type == "EXIT_TRADE":
            profit_pct = trade_info.get('profit_pct', 0)
            profit_str = f"{profit_pct:.2%}" if profit_pct is not None else "N/A"
            win_str = "WIN" if trade_info.get('win', False) else "LOSS"
            exit_reason = trade_info.get('exit_reason', 'Unknown')
            
            message = f"TRADE CLOSED: {win_str} ({profit_str})\n"
            message += f"Exit Reason: {exit_reason}\n\n"
            message += summary
            
        else:  # NEW_TRADE
            message = f"NEW TRADE OPENED\n\n{summary}"
            
        # Add market type to message
        market_type = trade_info.get('market_type', 'unknown')
        message += f"\nMarket Type: {'OTC' if market_type == 'otc' else 'Regular'}"
        
        # Send Telegram notification
        if self.telegram:
            try:
                self.telegram.send_message(message)
            except Exception as e:
                logger.error(f"Error sending Telegram notification: {e}")
                
        # Send email notification for significant events
        if self.email and event_type == "EXIT_TRADE":
            try:
                subject = f"IQ-720 Bot: Trade {win_str} - {trade_info.get('pair')} {trade_info.get('direction')}"
                self.email.send_email(subject, message)
            except Exception as e:
                logger.error(f"Error sending email notification: {e}")
    
    def run_trading_cycle(self):
        """Run one complete trading cycle"""
        
        current_time = datetime.now()
        logger.info(f"Starting trading cycle at {current_time}")
        
        try:
            # Select trading pairs
            available_pairs = self.select_trading_pairs(current_time)
            
            if not available_pairs:
                logger.warning("No available trading pairs found")
                return
                
            # Fetch market data
            market_data = self.fetch_market_data(available_pairs)
            
            if not market_data:
                logger.warning("No market data available")
                return
                
            # Check active trades first
            exited_trades = self.check_active_trades(market_data, current_time)
            
            # Generate new signals
            signals = self.generate_trading_signals(market_data)
            
            # Execute signals if we have room for more trades
            active_trade_count = len(self.strategy.active_trades)
            if active_trade_count < self.max_active_trades:
                executed_trades = self.execute_signals(signals, market_data, current_time)
            else:
                logger.info(f"Maximum active trades reached ({active_trade_count}), skipping signal execution")
                executed_trades = []
                
            # Update account balance
            self.update_account_balance()
            
            # Log cycle summary
            logger.info(f"Trading cycle completed: {len(executed_trades)} new trades, "
                       f"{len(exited_trades)} exited trades, "
                       f"{active_trade_count} active trades")
                       
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            logger.error(traceback.format_exc())
    
    def start(self):
        """Start the trading bot"""
        
        logger.info("Starting Enhanced Trading Bot")
        
        # Connect to IQ Option
        if not self.connect():
            logger.error("Failed to connect to IQ Option, stopping bot")
            return
            
        # Update initial account balance
        self.update_account_balance()
        
        # Load trade history if available
        history_path = self.config.get("trading", {}).get("history_path", "trade_history.json")
        if os.path.exists(history_path):
            self.strategy.load_trade_history(history_path)
        
        # Set bot to running
        self.is_running = True
        self.last_check_time = datetime.now()
        
        logger.info("Trading bot started, entering main loop")
        
        # Send startup notification
        if self.telegram:
            self.telegram.send_message("IQ-720 Enhanced Trading Bot started")
        
        # Main bot loop
        while self.is_running:
            try:
                # Run trading cycle
                self.run_trading_cycle()
                
                # Save trade history periodically
                if self.config.get("trading", {}).get("save_history", True):
                    self.strategy.save_trade_history(history_path)
                
                # Process next cycle immediately for manual trading
                # No artificial delays needed for manual trading
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping bot")
                self.stop()
                break
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.error(traceback.format_exc())
    
    def stop(self):
        """Stop the trading bot"""
        
        logger.info("Stopping trading bot")
        
        # Set bot to not running
        self.is_running = False
        
        # Save trade history
        history_path = self.config.get("trading", {}).get("history_path", "trade_history.json")
        self.strategy.save_trade_history(history_path)
        
        # Send shutdown notification
        if self.telegram:
            self.telegram.send_message("IQ-720 Enhanced Trading Bot stopped")
            
        logger.info("Trading bot stopped")


def parse_arguments():
    """Parse command line arguments"""
    
    parser = argparse.ArgumentParser(description="IQ-720 Enhanced Trading Bot")
    parser.add_argument("--config", dest="config_path", default="config.json",
                       help="Path to configuration file")
    return parser.parse_args()


if __name__ == "__main__":
    # Parse arguments
    args = parse_arguments()
    
    # Create and start bot
    bot = EnhancedTradingBot(args.config_path)
    bot.start()
