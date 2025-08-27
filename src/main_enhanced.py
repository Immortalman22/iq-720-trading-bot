#!/usr/bin/env python3
"""
Main entry point for the enhanced trading bot.
This version includes all the enhancements:
- Pair-specific logic
- Signal strength ranking
- Correlation analysis
- Performance tracking
- Dynamic asset selection
- Time-based trading logic
- Improved indicator calculations
- Daily email reports at 6:00 AM SAT
"""
import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timedelta
import threading
import signal
from pathlib import Path
import pandas as pd
import numpy as np
import pytz

# Add src directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.utils.enhanced_signal_generator import enhanced_signal_generator, EnhancedSignal
from src.telegram_notifier import TelegramNotifier
from src.utils.email_notifier import email_notifier
from src.utils.task_scheduler import task_scheduler
from src.utils.logger import setup_logger
from src.utils.config import load_config, Config
from src.utils.time_logic import TimeLogic

# Constants
ANALYSIS_ONLY = True  # Set to True for analysis-only mode
MAX_RANKED_SIGNALS = 3  # Maximum number of ranked signals to output
SLEEP_INTERVAL = 60  # Sleep interval in seconds

# South Africa timezone
SAT_TIMEZONE = pytz.timezone('Africa/Johannesburg')

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    logging.info("Shutting down trading bot...")
    task_scheduler.stop()
    sys.exit(0)
    
def generate_daily_report(current_time: datetime = None) -> bool:
    """
    Generate and send the daily report via email.
    
    Args:
        current_time: Current time (provided by scheduler)
        
    Returns:
        True if report was sent successfully
    """
    logger = logging.getLogger(__name__)
    
    # Use current time if not provided
    if not current_time:
        current_time = datetime.now(SAT_TIMEZONE)
        
    logger.info(f"Generating daily report for {current_time.strftime('%Y-%m-%d')}")
    
    try:
        # Get performance data from signal generator
        performance_data = enhanced_signal_generator.performance_tracker.pair_stats
        
        # Get time logic information
        time_logic = TimeLogic()
        market_type = time_logic.get_current_market_type(current_time)
        active_sessions = time_logic.get_current_session(current_time)
        optimal_pairs = time_logic.get_optimal_pairs_for_time(current_time)
        
        # Create report data
        report_data = {
            'total_signals': len(enhanced_signal_generator.recent_signals),
            'total_trades': enhanced_signal_generator.trades_today,
            'winning_trades': enhanced_signal_generator.trades_today - enhanced_signal_generator.consecutive_losses,
            'win_rate': (enhanced_signal_generator.trades_today - enhanced_signal_generator.consecutive_losses) / 
                        max(1, enhanced_signal_generator.trades_today),
            'market_type': market_type,
            'active_sessions': active_sessions,
            'optimal_pairs': optimal_pairs,
            'report_date': current_time
        }
        
        # Send daily report via email
        success = email_notifier.send_daily_report(report_data, performance_data, current_time)
        
        if success:
            logger.info("Daily report email sent successfully")
        else:
            logger.error("Failed to send daily report email")
            
        return success
        
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        return False

def format_signal_message(signal: EnhancedSignal, rank: int = None) -> str:
    """Format signal information for notification message"""
    rank_str = f"RANK #{rank}" if rank is not None else ""
    direction = signal.direction
    pair = signal.asset
    expiry = signal.expiry_minutes
    
    # Format indicators
    indicators = signal.indicators
    rsi = indicators.get('rsi', 'N/A')
    macd = indicators.get('macd', 'N/A')
    macd_signal = indicators.get('macd_signal', 'N/A')
    
    # Add strength score
    strength = signal.strength_score
    
    # Format time context
    time_context = signal.time_context
    
    # Add detailed strength factors
    strength_factors = signal.strength_factors or {}
    factors_str = ", ".join([f"{k}: {v:.2f}" for k, v in strength_factors.items() if v > 0])
    
    # Basic message
    message = f"🚨 {rank_str} {direction} SIGNAL 🚨\n\n"
    message += f"Asset: {pair}\n"
    message += f"Direction: {direction}\n"
    message += f"Expiry: {expiry} min\n"
    message += f"Strength: {strength:.1f}/100\n\n"
    
    # Add technical indicators
    message += "📊 INDICATORS 📊\n"
    message += f"RSI: {rsi:.1f}\n"
    message += f"MACD: {macd:.6f} / Signal: {macd_signal:.6f}\n"
    
    # Add more indicators if available
    if 'stoch_k' in indicators and 'stoch_d' in indicators:
        message += f"Stoch: %K {indicators['stoch_k']:.1f} / %D {indicators['stoch_d']:.1f}\n"
        
    if 'trend_direction' in indicators:
        message += f"Trend: {indicators['trend_direction']}\n"
    
    # Add strength factors
    message += f"\n💪 STRENGTH FACTORS 💪\n{factors_str}\n"
    
    # Add time context
    message += f"\n⏰ TIMING ⏰\n{time_context}\n"
    
    # Add timestamp
    message += f"\n🕒 Signal generated at: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    
    return message

def fetch_candle_data(pair: str, timestamp: int = None) -> dict:
    """
    Mock function to fetch candle data for testing.
    In a real implementation, this would connect to a broker API.
    """
    if timestamp is None:
        timestamp = int(time.time())
        
    # Generate mock data based on time
    hour = datetime.fromtimestamp(timestamp).hour
    
    # Different patterns for different times of day
    if hour < 8:  # Early hours - low volatility
        close = 1.1000 + (np.sin(timestamp / 10000) * 0.002)
        volume = 100 + (np.cos(timestamp / 5000) * 50)
    elif hour < 16:  # Active hours - higher volatility
        close = 1.1000 + (np.sin(timestamp / 5000) * 0.005)
        volume = 300 + (np.cos(timestamp / 3000) * 150)
    else:  # Evening hours - medium volatility
        close = 1.1000 + (np.sin(timestamp / 7500) * 0.003)
        volume = 200 + (np.cos(timestamp / 4000) * 100)
        
    # Create sample candle data
    return {
        'timestamp': timestamp,
        'open': close - 0.0002 + (np.random.random() * 0.0004),
        'high': close + 0.0003 + (np.random.random() * 0.0005),
        'low': close - 0.0003 - (np.random.random() * 0.0005),
        'close': close,
        'volume': volume,
        'asset': pair
    }

def run_trading_bot():
    """Main function to run the trading bot"""
    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config = load_config()
    
    # Initialize Telegram notifier
    telegram_token = config.TELEGRAM_BOT_TOKEN
    telegram_chat_id = config.TELEGRAM_CHAT_ID
    notifier = None
    
    if telegram_token and telegram_chat_id:
        notifier = TelegramNotifier(telegram_token, telegram_chat_id)
        logger.info("Telegram notifier initialized")
    else:
        logger.warning("Telegram configuration missing, notifications disabled")
    
    # Initialize email notifier with config settings
    email_notifier.smtp_server = config.SMTP_SERVER
    email_notifier.smtp_port = config.SMTP_PORT
    email_notifier.smtp_username = config.SMTP_USERNAME
    email_notifier.smtp_password = config.SMTP_PASSWORD
    email_notifier.default_recipients = config.EMAIL_RECIPIENTS
    
    if email_notifier.smtp_username and email_notifier.smtp_password:
        logger.info("Email notifier initialized with configured settings")
    else:
        logger.warning("Email configuration missing, email reporting will not work")
    
    # Initialize time logic
    time_logic = TimeLogic()
    
    # Start task scheduler
    task_scheduler.start()
    
    # Schedule daily report at configured time (default 06:00 SAT)
    daily_report_time = config.DAILY_REPORT_TIME
    task_scheduler.schedule_daily_task(generate_daily_report, daily_report_time)
    logger.info(f"Daily email reports scheduled for {daily_report_time} SAT to {', '.join(config.EMAIL_RECIPIENTS)}")
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Starting enhanced trading bot...")
    
    # List of currency pairs to monitor
    pairs = [
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 
        'USD/CAD', 'NZD/USD', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY'
    ]
    
    # Current time context
    current_time = datetime.now()
    market_type = time_logic.get_current_market_type(current_time)
    current_sessions = time_logic.get_current_session(current_time)
    
    logger.info(f"Current market: {market_type}")
    logger.info(f"Current sessions: {', '.join(current_sessions) if current_sessions else 'None'}")
    
    # Get optimal pairs for current time
    optimal_pairs = time_logic.get_optimal_pairs_for_time(current_time)
    if optimal_pairs:
        logger.info(f"Optimal pairs for current session: {', '.join(optimal_pairs)}")
    
    # Main loop
    tick_counter = 0
    collected_signals = []
    
    while True:
        try:
            # Current timestamp
            current_timestamp = int(time.time())
            current_time = datetime.fromtimestamp(current_timestamp)
            
            # Process each pair
            for pair in pairs:
                # Fetch candle data (in real implementation, get from API)
                candle_data = fetch_candle_data(pair, current_timestamp)
                
                # Process candle data
                signal = enhanced_signal_generator.add_candle(candle_data)
                
                if signal:
                    logger.info(f"Generated {signal.direction} signal for {pair} with strength {signal.strength_score:.1f}")
                    collected_signals.append(signal)
            
            # Every 5 ticks, process collected signals
            if tick_counter % 5 == 0 and collected_signals:
                # Rank and filter signals
                ranked_signals = enhanced_signal_generator.get_ranked_signals(
                    collected_signals, max_signals=MAX_RANKED_SIGNALS
                )
                
                if ranked_signals:
                    logger.info(f"Found {len(ranked_signals)} ranked signals")
                    
                    # Send notifications for ranked signals
                    for i, signal in enumerate(ranked_signals):
                        rank = i + 1
                        message = format_signal_message(signal, rank)
                        
                        if notifier and ANALYSIS_ONLY:
                            notifier.send_message(message)
                            logger.info(f"Sent signal notification for {signal.asset} (Rank {rank})")
                            
                            # In a real implementation, execute trades here if not in analysis-only mode
                            
                    # Generate performance report once per day
                    if current_time.hour == 0 and current_time.minute < 5:
                        report = enhanced_signal_generator.generate_daily_report()
                        if notifier:
                            notifier.send_message(f"📊 Daily Performance Report 📊\n\n{report}")
                
                # Clear collected signals
                collected_signals = []
            
            # Update tick counter
            tick_counter += 1
            
            # Sleep between iterations
            time.sleep(SLEEP_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Enhanced Trading Bot")
    parser.add_argument("--analysis-only", action="store_true", help="Run in analysis-only mode")
    
    args = parser.parse_args()
    
    if args.analysis_only:
        ANALYSIS_ONLY = True
        print("Running in analysis-only mode")
        
    run_trading_bot()
