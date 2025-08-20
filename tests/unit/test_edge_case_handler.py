"""Tests for edge case handling in data processing."""
import pytest
from datetime import datetime
from src.utils.edge_case_handler import EdgeCaseHandler

@pytest.fixture
def edge_handler():
    return EdgeCaseHandler()

def test_validation_missing_fields(edge_handler):
    """Test validation of candle with missing fields."""
    incomplete_candle = {
        'open': 1.2000,
        'high': 1.2010,
        # missing 'low' and 'close'
        'timestamp': datetime.now(),
        'volume': 1000
    }
    result = edge_handler.validate_candle(incomplete_candle)
    assert result is None

def test_validation_price_range(edge_handler):
    """Test validation of candle with invalid price range."""
    invalid_candle = {
        'open': 1.2000,
        'high': 1.1990,  # high < open
        'low': 1.1980,
        'close': 1.1995,
        'timestamp': datetime.now(),
        'volume': 1000
    }
    result = edge_handler.validate_candle(invalid_candle)
    assert result is not None
    assert result['high'] >= result['low']
    assert result['high'] >= result['open']
    assert result['high'] >= result['close']

def test_validation_price_gap(edge_handler):
    """Test validation of candle with price gap."""
    # First candle to set reference
    base_candle = {
        'open': 1.2000,
        'high': 1.2010,
        'low': 1.1990,
        'close': 1.2005,
        'timestamp': datetime.now(),
        'volume': 1000
    }
    edge_handler.validate_candle(base_candle)

    # Gap candle
    gap_candle = {
        'open': 1.2100,  # 95 pip gap
        'high': 1.2110,
        'low': 1.2090,
        'close': 1.2095,
        'timestamp': datetime.now(),
        'volume': 1000
    }
    result = edge_handler.validate_candle(gap_candle)
    assert result is not None
    assert abs(result['open'] - 1.2005) < 0.0020  # Gap should be reduced

def test_validation_volatility(edge_handler):
    """Test validation of candle with excessive volatility."""
    volatile_candle = {
        'open': 1.2000,
        'high': 1.2100,  # 100 pip range
        'low': 1.1900,
        'close': 1.2050,
        'timestamp': datetime.now(),
        'volume': 1000
    }
    result = edge_handler.validate_candle(volatile_candle)
    assert result is not None
    assert result['high'] - result['low'] <= edge_handler.volatility_threshold

def test_consecutive_gaps(edge_handler):
    """Test handling of consecutive price gaps."""
    # Set initial price
    base_candle = {
        'open': 1.2000,
        'high': 1.2010,
        'low': 1.1990,
        'close': 1.2005,
        'timestamp': datetime.now(),
        'volume': 1000
    }
    edge_handler.validate_candle(base_candle)

    # Create multiple gap candles
    last_valid = None
    for i in range(edge_handler.max_gaps + 1):
        gap_candle = {
            'open': 1.2000 + (0.0050 * (i + 1)),  # 50 pip gaps
            'high': 1.2010 + (0.0050 * (i + 1)),
            'low': 1.1990 + (0.0050 * (i + 1)),
            'close': 1.2005 + (0.0050 * (i + 1)),
            'timestamp': datetime.now(),
            'volume': 1000
        }
        result = edge_handler.validate_candle(gap_candle)
        if i < edge_handler.max_gaps:
            assert result is not None
            last_valid = result
        else:
            # Should reject after max consecutive gaps
            assert result is None or abs(result['open'] - last_valid['close']) < edge_handler.gap_threshold

def test_timestamp_conversion(edge_handler):
    """Test handling of different timestamp formats."""
    unix_timestamp = datetime.now().timestamp()
    candle = {
        'open': 1.2000,
        'high': 1.2010,
        'low': 1.1990,
        'close': 1.2005,
        'timestamp': unix_timestamp,
        'volume': 1000
    }
    result = edge_handler.validate_candle(candle)
    assert result is not None
    assert isinstance(result['timestamp'], datetime)

def test_price_history_limit(edge_handler):
    """Test that price history is properly limited."""
    # Add many candles
    for i in range(150):  # More than max_history
        candle = {
            'open': 1.2000 + (0.0001 * i),
            'high': 1.2010 + (0.0001 * i),
            'low': 1.1990 + (0.0001 * i),
            'close': 1.2005 + (0.0001 * i),
            'timestamp': datetime.now(),
            'volume': 1000
        }
        edge_handler.validate_candle(candle)
    
    # Check history length
    assert len(edge_handler.price_history) <= 100  # max_history

def test_valid_candle_passthrough(edge_handler):
    """Test that valid candles pass through unchanged."""
    valid_candle = {
        'open': 1.2000,
        'high': 1.2010,
        'low': 1.1990,
        'close': 1.2005,
        'timestamp': datetime.now(),
        'volume': 1000
    }
    result = edge_handler.validate_candle(valid_candle.copy())
    assert result == valid_candle
