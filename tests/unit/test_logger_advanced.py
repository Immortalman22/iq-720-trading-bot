"""Test compression and metrics functionality of the logger."""
import gzip
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from unittest.mock import patch, Mock
from prometheus_client import REGISTRY, Counter, Histogram
from src.utils.logger import TradingBotLogger

# Reset metrics between tests
@pytest.fixture(autouse=True)
def clear_metrics():
    """Clear Prometheus metrics before each test."""
    for metric in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(metric)
    yield

@pytest.fixture(scope="function")
def mock_requests():
    """Mock requests for testing remote logging."""
    with patch('src.utils.logger.requests') as mock:
        mock.post.return_value.status_code = 200
        yield mock

def test_log_compression(test_log_dir):
    """Test that old logs are properly compressed."""
    logger = TradingBotLogger(str(test_log_dir))
    
    # Create an old log file
    old_log = test_log_dir / "trading.log.1"
    old_log.write_text("Old log data")
    
    # Set file modification time to 8 days ago
    old_time = time.time() - (8 * 24 * 60 * 60)
    os.utime(old_log, (old_time, old_time))
    
    # Compress old logs
    logger.compress_old_logs(days_threshold=7)
    
    # Check that original file is gone and compressed file exists
    assert not old_log.exists()
    assert (test_log_dir / "trading.log.1.gz").exists()
    
    # Verify compressed content
    with gzip.open(test_log_dir / "trading.log.1.gz", 'rt') as f:
        assert f.read() == "Old log data"

def test_remote_logging(test_log_dir, mock_requests):
    """Test that logs are sent to remote service."""
    logger = TradingBotLogger(
        str(test_log_dir),
        remote_logging=True,
        remote_url="http://logging-service.com"
    )
    
    # Log a trade
    logger.log_trade("EURUSD", "BUY", 1.1234, 100.00, execution_time=0.5)
    
    # Verify remote logging call
    assert mock_requests.post.called
    call_args = mock_requests.post.call_args
    assert call_args[0][0] == "http://logging-service.com"
    
    # Verify log data
    log_data = json.loads(json.dumps(call_args[1]['json']))
    assert log_data['component'] == "trades"
    assert log_data['symbol'] == "EURUSD"
    assert log_data['action'] == "BUY"
    assert log_data['price'] == 1.1234
    assert log_data['amount'] == 100.00
    assert log_data['execution_time'] == 0.5

def test_metrics_recording(test_log_dir):
    """Test that Prometheus metrics are properly recorded."""
    logger = TradingBotLogger(str(test_log_dir))
    
    # Log some activity
    logger.log_trade("EURUSD", "BUY", 1.1234, 100.00, execution_time=0.5)
    logger.log_with_metrics(logging.ERROR, "Test error", component="testing")
    
    # Get metrics
    log_entries = logger.log_entries.collect()[0]
    trade_metrics = logger.trade_metrics.collect()[0]
    
    # Verify log entries metric
    error_samples = [s for s in log_entries.samples 
                    if s.labels['level'] == 'ERROR']
    assert len(error_samples) > 0
    assert error_samples[0].value == 1.0
    
    # Verify trade metrics
    trade_samples = [s for s in trade_metrics.samples 
                    if s.labels['symbol'] == 'EURUSD' 
                    and s.labels['action'] == 'BUY']
    assert len(trade_samples) > 0

def test_compressed_trade_logs(test_log_dir):
    """Test compression of old trade logs."""
    logger = TradingBotLogger(str(test_log_dir))
    
    # Create and age some trade logs
    symbol = "EURUSD"
    old_date = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
    trade_dir = test_log_dir / "trades" / symbol
    trade_dir.mkdir(parents=True)
    
    old_trade_log = trade_dir / f"{old_date}.csv"
    old_trade_log.write_text("timestamp,symbol,action,price,amount\n")
    
    # Set file modification time
    old_time = time.time() - (8 * 24 * 60 * 60)
    os.utime(old_trade_log, (old_time, old_time))
    
    # Compress old logs
    logger.compress_old_logs(days_threshold=7)
    
    # Verify compression
    assert not old_trade_log.exists()
    assert (old_trade_log.with_suffix('.csv.gz')).exists()
