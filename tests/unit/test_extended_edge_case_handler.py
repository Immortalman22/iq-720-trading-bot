"""Unit tests for the extended edge case handler."""
import pytest
from datetime import datetime, timedelta
from src.utils.extended_edge_case_handler import ExtendedEdgeCaseHandler, DataAnomalyReport

@pytest.fixture
def handler():
    """Create a fresh edge case handler for each test."""
    return ExtendedEdgeCaseHandler()

@pytest.fixture
def sample_data():
    """Generate sample trading data."""
    return {
        'timestamp': datetime.now().isoformat(),
        'open': 1.2000,
        'high': 1.2010,
        'low': 1.1990,
        'close': 1.2005,
        'volume': 1000,
        'tick_count': 150,
        'bids': [[1.2000, 1.0], [1.1995, 2.0]],
        'asks': [[1.2010, 1.0], [1.2015, 2.0]]
    }

def test_normal_data_validation(handler, sample_data):
    """Test validation of normal, well-formed data."""
    report = handler.validate_data(sample_data)
    assert not report.anomalies
    assert report.confidence == 1.0
    assert report.severity == "low"
    assert not report.correction_applied

def test_frozen_ticker_detection(handler, sample_data):
    """Test detection of frozen ticker data."""
    # Feed the same price multiple times
    for _ in range(6):
        handler._update_state({'close': 1.2000, 'timestamp': datetime.now()})
    
    sample_data['close'] = 1.2000
    report = handler.validate_data(sample_data)
    assert "ticker_frozen" in report.anomalies
    assert report.severity in ["medium", "high"]
    assert report.correction_applied

def test_timestamp_validation(handler, sample_data):
    """Test timestamp sequence validation."""
    # Future timestamp
    sample_data['timestamp'] = (datetime.now() + timedelta(minutes=5)).isoformat()
    report = handler.validate_data(sample_data)
    assert "invalid_timestamp" in report.anomalies
    
    # Backwards time
    handler._update_state({'timestamp': datetime.now()})
    sample_data['timestamp'] = (datetime.now() - timedelta(minutes=5)).isoformat()
    report = handler.validate_data(sample_data)
    assert "invalid_timestamp" in report.anomalies

def test_volume_anomaly_detection(handler, sample_data):
    """Test abnormal volume detection."""
    # Initialize volume history
    for _ in range(5):
        handler._update_state({'volume': 1000})
    
    # Spike volume without corresponding price movement
    sample_data['volume'] = 5000  # 5x normal
    sample_data['close'] = sample_data['open']  # No price movement
    report = handler.validate_data(sample_data)
    assert "abnormal_volume" in report.anomalies

def test_order_book_validation(handler, sample_data):
    """Test order book consistency checks."""
    # Create crossed order book
    sample_data['bids'] = [[1.2020, 1.0]]  # Bid above ask
    sample_data['asks'] = [[1.2010, 1.0]]
    report = handler.validate_data(sample_data)
    assert "order_book_anomaly" in report.anomalies

def test_tick_count_validation(handler, sample_data):
    """Test tick count validation."""
    sample_data['tick_count'] = 50  # Below threshold
    report = handler.validate_data(sample_data)
    assert "insufficient_ticks" in report.anomalies

def test_multiple_anomalies_severity(handler, sample_data):
    """Test severity calculation with multiple anomalies."""
    # Create multiple anomalies
    sample_data.update({
        'tick_count': 50,
        'volume': 5000,
        'bids': [[1.2020, 1.0]],
        'asks': [[1.2010, 1.0]]
    })
    report = handler.validate_data(sample_data)
    assert len(report.anomalies) > 2
    assert report.severity == "high"

def test_consecutive_anomalies(handler, sample_data):
    """Test handling of consecutive anomalies."""
    # Generate multiple anomalous data points
    for _ in range(6):
        sample_data['tick_count'] = 50
        report = handler.validate_data(sample_data)
    
    assert report.severity == "high"
    assert report.confidence < 0.5

def test_correction_confidence(handler, sample_data):
    """Test confidence calculation in corrections."""
    # Single minor anomaly
    sample_data['tick_count'] = 50
    report = handler.validate_data(sample_data)
    high_confidence = report.confidence
    
    # Multiple serious anomalies
    sample_data.update({
        'tick_count': 50,
        'volume': 5000,
        'timestamp': (datetime.now() + timedelta(minutes=5)).isoformat()
    })
    report = handler.validate_data(sample_data)
    low_confidence = report.confidence
    
    assert high_confidence > low_confidence

def test_state_management(handler, sample_data):
    """Test internal state management."""
    # Update state multiple times
    for i in range(150):
        sample_data['close'] = 1.2000 + (i * 0.0001)
        handler._update_state(sample_data)
    
    # Check history length limits
    assert len(handler.price_history) <= 100
    assert len(handler.volume_history) <= 100
    assert len(handler.timestamp_history) <= 100
