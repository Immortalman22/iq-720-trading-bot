import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.signal_generator import SignalGenerator, Signal
import numpy as np

@pytest.fixture
def signal_generator():
    return SignalGenerator()

@pytest.fixture
def sample_candle_data():
    base_time = datetime.now()
    base_price = 1.2000
    
    def generate_candle(index):
        return {
            'timestamp': (base_time + timedelta(minutes=index)).timestamp(),
            'open': base_price + np.sin(index) * 0.0010,
            'high': base_price + np.sin(index) * 0.0015,
            'low': base_price + np.sin(index) * 0.0005,
            'close': base_price + np.sin(index) * 0.0010,
            'volume': 1000 + np.random.randint(-200, 200)
        }
    
    return [generate_candle(i) for i in range(100)]

def test_signal_generator_initialization(signal_generator):
    assert signal_generator is not None
    assert len(signal_generator.price_history) == 0
    assert signal_generator.consecutive_losses == 0
    assert signal_generator.trades_today == 0

def test_add_candle_basic(signal_generator, sample_candle_data):
    # Add a single candle
    signal = signal_generator.add_candle(sample_candle_data[0])
    assert len(signal_generator.price_history) == 1
    assert signal is None  # Not enough data for signal

def test_signal_generation(signal_generator, sample_candle_data):
    # Add enough candles for signal generation
    for candle in sample_candle_data[:30]:
        signal_generator.add_candle(candle)
    
    # Test with strong buy conditions
    buy_candle = {
        'timestamp': datetime.now().timestamp(),
        'open': 1.2000,
        'high': 1.2010,
        'low': 1.1990,
        'close': 1.2005,
        'volume': 1500  # Higher volume
    }
    
    with patch('src.utils.market_analyzer.MarketAnalyzer.is_favorable_condition') as mock_market:
        mock_market.return_value = (True, 0.8, "Strong trend")
        signal = signal_generator.add_candle(buy_candle)
        
        if signal:
            assert isinstance(signal, Signal)
            assert signal.direction in ['BUY', 'SELL']
            assert signal.confidence > 0

def test_trading_conditions(signal_generator):
    # Test maximum trades per day
    signal_generator.trades_today = 15
    assert not signal_generator._check_trading_conditions()
    
    # Test consecutive losses
    signal_generator.trades_today = 0
    signal_generator.consecutive_losses = 3
    assert not signal_generator._check_trading_conditions()

def test_record_trade_results(signal_generator):
    # Test winning trade
    signal_generator.record_trade_result(True)
    assert signal_generator.consecutive_losses == 0
    
    # Test losing trade
    signal_generator.record_trade_result(False)
    assert signal_generator.consecutive_losses == 1

@patch('src.utils.news.forex_news.ForexNewsFilter.is_news_time')
def test_news_event_blocking(mock_news, signal_generator):
    # Test that signals are blocked during news events
    mock_news.return_value = True
    assert not signal_generator._check_trading_conditions()
    
    mock_news.return_value = False
    with patch('src.utils.market_analyzer.MarketAnalyzer.is_favorable_condition') as mock_market:
        mock_market.return_value = (True, 0.8, "Strong trend")
        assert signal_generator._check_trading_conditions()

def test_signal_confidence_calculation(signal_generator, sample_candle_data):
    # Add data and generate signal
    for candle in sample_candle_data[:30]:
        signal_generator.add_candle(candle)
    
    # Create ideal conditions for a signal
    perfect_candle = {
        'timestamp': datetime.now().timestamp(),
        'open': 1.2000,
        'high': 1.2020,
        'low': 1.1990,
        'close': 1.2015,
        'volume': 2000  # Very high volume
    }
    
    with patch('src.utils.market_analyzer.MarketAnalyzer.is_favorable_condition') as mock_market:
        mock_market.return_value = (True, 0.9, "Perfect conditions")
        signal = signal_generator.add_candle(perfect_candle)
        
        if signal:
            assert 0 <= signal.confidence <= 1
            assert isinstance(signal.indicators, dict)

def test_minimum_time_between_signals(signal_generator):
    signal_generator.last_signal_time = datetime.now()
    assert not signal_generator._check_trading_conditions()
    
    signal_generator.last_signal_time = datetime.now() - timedelta(minutes=6)
    with patch('src.utils.market_analyzer.MarketAnalyzer.is_favorable_condition') as mock_market:
        mock_market.return_value = (True, 0.8, "Good conditions")
        assert signal_generator._check_trading_conditions()
