"""Test suite for the trading bot logger."""
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
import pytest
from src.utils.logger import TradingBotLogger

@pytest.fixture(scope="function")
def test_log_dir(tmp_path):
    """Create a temporary directory for log files."""
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir()
    yield log_dir
    # Cleanup
    shutil.rmtree(log_dir)

def test_logger_initialization(test_log_dir):
    """Test basic logger setup."""
    logger = TradingBotLogger(str(test_log_dir))
    assert logger.log_dir.exists()
    assert (test_log_dir / "trading.log").exists()
    assert (test_log_dir / "errors.log").exists()

def test_log_levels(test_log_dir):
    """Test that different log levels are correctly handled."""
    logger = TradingBotLogger(str(test_log_dir))
    log = logger.get_logger()
    
    test_msg = "Test message"
    log.debug(test_msg)
    log.info(test_msg)
    log.warning(test_msg)
    log.error(test_msg)
    
    with open(test_log_dir / "trading.log") as f:
        content = f.read()
        assert "DEBUG" in content
        assert "INFO" in content
        assert "WARNING" in content
        assert "ERROR" in content
    
    with open(test_log_dir / "errors.log") as f:
        content = f.read()
        assert "DEBUG" not in content
        assert "INFO" not in content
        assert "WARNING" not in content
        assert "ERROR" in content

def test_trade_logging(test_log_dir):
    """Test trade-specific logging functionality."""
    logger = TradingBotLogger(str(test_log_dir))
    symbol = "EURUSD"
    
    # Log a trade
    logger.log_trade(symbol, "BUY", 1.1234, 100.00)
    
    # Check trade log file exists
    today = datetime.now().strftime("%Y-%m-%d")
    trade_log_path = test_log_dir / "trades" / symbol / f"{today}.csv"
    assert trade_log_path.exists()
    
    # Verify trade log content
    with open(trade_log_path) as f:
        content = f.read()
        assert symbol in content
        assert "BUY" in content
        assert "1.1234" in content
        assert "100.00" in content

def test_log_rotation(test_log_dir):
    """Test that log rotation works correctly."""
    logger = TradingBotLogger(str(test_log_dir))
    log = logger.get_logger()
    
    # Write more than 10MB of data
    large_msg = "X" * 1024  # 1KB
    for _ in range(11000):  # ~11MB
        log.info(large_msg)
    
    # Check that rotation occurred
    assert (test_log_dir / "trading.log").exists()
    assert (test_log_dir / "trading.log.1").exists()

def test_trade_log_rotation(test_log_dir):
    """Test trade log rotation at day boundary."""
    logger = TradingBotLogger(str(test_log_dir))
    symbol = "EURUSD"
    
    # Log initial trade
    logger.log_trade(symbol, "BUY", 1.1234, 100.00)
    
    # Log another trade
    logger.log_trade(symbol, "SELL", 1.1234, 100.00)
    
    # Check trade log file
    today = datetime.now().strftime("%Y-%m-%d")
    trade_log_path = test_log_dir / "trades" / symbol / f"{today}.csv"
    
    # Read all lines from the file
    with open(trade_log_path) as f:
        lines = f.readlines()
    
    # Verify we have two trades
    assert len(lines) == 2, f"Expected 2 trades, got {len(lines)}"
    
    # Verify trade contents
    for line in lines:
        assert symbol in line, f"Symbol {symbol} not found in line: {line}"
        assert any(action in line for action in ["BUY", "SELL"]), f"No action found in line: {line}"
        assert "1.12340" in line, f"Price not found in line: {line}"
        assert "100.00" in line, f"Amount not found in line: {line}"
