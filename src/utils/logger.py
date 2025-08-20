"""Logging configuration for the trading bot."""
import gzip
import json
import logging
import logging.handlers
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import requests
from prometheus_client import Counter, Histogram

class TradingBotLogger:
    """Configure and manage logging for the trading bot."""
    
    # Prometheus metrics
    log_entries = Counter('trading_bot_log_entries_total', 
                         'Total number of log entries', 
                         ['level', 'component'])
    trade_metrics = Histogram('trading_bot_trade_metrics',
                            'Trade execution metrics',
                            ['symbol', 'action'],
                            buckets=[0.1, 0.5, 1.0, 2.0, 5.0])
    
    def __init__(self, log_dir: str = "logs", remote_logging: bool = False,
                 remote_url: Optional[str] = None):
        """Initialize the logger with custom formatting and handlers.
        
        Args:
            log_dir: Directory to store log files
            remote_logging: Whether to enable remote logging
            remote_url: URL for remote logging endpoint
        """
        self.remote_logging = remote_logging
        self.remote_url = remote_url
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("TradingBot")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s'
        )
        
        # File handler for all logs
        main_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "trading.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(file_formatter)
        
        # File handler for errors only
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "errors.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers
        self.logger.addHandler(main_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(console_handler)
        
    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        return self.logger
    
    def add_trade_handler(self, symbol: str) -> None:
        """Add a handler for logging trades for a specific symbol.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD')
        """
        trade_formatter = logging.Formatter(
            '%(asctime)s,%(message)s'  # CSV format
        )
        
        # Create symbol-specific directory
        symbol_dir = self.log_dir / "trades" / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        
        # Create daily trade log file
        today = datetime.now().strftime("%Y-%m-%d")
        trade_handler = logging.FileHandler(
            symbol_dir / f"{today}.csv"
        )
        trade_handler.setLevel(logging.INFO)
        trade_handler.setFormatter(trade_formatter)
        
        # Add handler with a unique name for the symbol
        trade_handler.set_name(f"trade_handler_{symbol}")
        
        # Remove any existing trade handler for this symbol
        self.logger.handlers = [h for h in self.logger.handlers 
                              if h.get_name() != f"trade_handler_{symbol}"]
        self.logger.addHandler(trade_handler)
    
    def log_trade(self, symbol: str, action: str, price: float, 
                  amount: float, timestamp: Optional[datetime] = None,
                  execution_time: Optional[float] = None) -> None:
        """Log a trade with specific formatting and metrics.
        
        Args:
            symbol: Trading pair symbol
            action: 'BUY' or 'SELL'
            price: Trade execution price
            amount: Trade amount
            timestamp: Optional trade timestamp
            execution_time: Time taken to execute the trade (in seconds)
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Ensure trade handler exists for symbol
        handler_name = f"trade_handler_{symbol}"
        if not any(h.get_name() == handler_name for h in self.logger.handlers):
            self.add_trade_handler(symbol)
            
        # Format trade data with timestamp
        trade_data = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')},{symbol},{action},{price:.5f},{amount:.2f}"
        
        # Update trade metrics
        if execution_time is not None:
            self.trade_metrics.labels(
                symbol=symbol,
                action=action
            ).observe(execution_time)
        
        # Log trade with additional context
        self.log_with_metrics(
            logging.INFO,
            trade_data,
            component="trades",
            symbol=symbol,
            action=action,
            price=price,
            amount=amount,
            execution_time=execution_time
        )
        
    def rotate_trade_logs(self) -> None:
        """Rotate trade logs at the start of a new day."""
        for handler in self.logger.handlers:
            if handler.get_name() and handler.get_name().startswith("trade_handler_"):
                symbol = handler.get_name().replace("trade_handler_", "")
                self.logger.removeHandler(handler)
                self.add_trade_handler(symbol)
                
    def compress_old_logs(self, days_threshold: int = 7) -> None:
        """Compress log files older than the specified number of days.
        
        Args:
            days_threshold: Number of days after which to compress logs
        """
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # Compress old general logs
        for log_file in self.log_dir.glob("*.log.*"):
            if log_file.suffix == ".gz":
                continue
                
            try:
                stat = log_file.stat()
                if datetime.fromtimestamp(stat.st_mtime) < cutoff_date:
                    with log_file.open('rb') as f_in:
                        with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()
            except Exception as e:
                self.logger.error(f"Failed to compress {log_file}: {e}")
        
        # Compress old trade logs
        trades_dir = self.log_dir / "trades"
        if trades_dir.exists():
            for symbol_dir in trades_dir.iterdir():
                if not symbol_dir.is_dir():
                    continue
                    
                for trade_file in symbol_dir.glob("*.csv"):
                    try:
                        stat = trade_file.stat()
                        if datetime.fromtimestamp(stat.st_mtime) < cutoff_date:
                            with trade_file.open('rb') as f_in:
                                with gzip.open(f"{trade_file}.gz", 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            trade_file.unlink()
                    except Exception as e:
                        self.logger.error(f"Failed to compress {trade_file}: {e}")
    
    def _send_to_remote(self, log_data: Dict[str, Any]) -> None:
        """Send log data to remote logging service.
        
        Args:
            log_data: Dictionary containing log data
        """
        if not self.remote_logging or not self.remote_url:
            return
            
        try:
            response = requests.post(
                self.remote_url,
                json=log_data,
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            # Log locally but don't raise to avoid disrupting normal operation
            self.logger.warning(f"Failed to send log to remote service: {e}")
    
    def log_with_metrics(self, level: int, msg: str, 
                        component: str = "general", **kwargs) -> None:
        """Log a message and update metrics.
        
        Args:
            level: Logging level (e.g., logging.INFO)
            msg: Message to log
            component: Component name for metrics
            **kwargs: Additional log data
        """
        # Update Prometheus metrics
        self.log_entries.labels(
            level=logging.getLevelName(level),
            component=component
        ).inc()
        
        # Prepare log data
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": logging.getLevelName(level),
            "message": msg,
            "component": component,
            **kwargs
        }
        
        # Local logging
        self.logger.log(level, msg, extra=kwargs)
        
        # Remote logging if enabled
        self._send_to_remote(log_data)

# Global logger instance
trading_logger = TradingBotLogger()
logger = trading_logger.get_logger()
