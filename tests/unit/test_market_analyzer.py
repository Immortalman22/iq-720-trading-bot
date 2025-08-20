import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.utils.market_analyzer import MarketAnalyzer

@pytest.fixture
def market_analyzer():
    return MarketAnalyzer()

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

def test_market_analyzer_initialization(market_analyzer):
    assert market_analyzer is not None
    assert len(market_analyzer.price_history) == 0
    assert len(market_analyzer.volume_history) == 0
    assert len(market_analyzer.timestamp_history) == 0

def test_add_candle(market_analyzer, sample_candle_data):
    # Add a single candle
    market_analyzer.add_candle(sample_candle_data[0])
    assert len(market_analyzer.price_history) == 1
    assert len(market_analyzer.volume_history) == 1
    assert len(market_analyzer.timestamp_history) == 1

def test_market_conditions_insufficient_data(market_analyzer):
    conditions = market_analyzer.get_market_conditions()
    assert conditions is None

def test_market_conditions_calculation(market_analyzer, sample_candle_data):
    # Add enough candles for analysis
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    conditions = market_analyzer.get_market_conditions()
    assert conditions is not None
    assert 'regime' in conditions
    assert 'volatility' in conditions
    assert 'trend_strength' in conditions
    assert 'volume_profile' in conditions

def test_favorable_conditions(market_analyzer, sample_candle_data):
    # Add trending market data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    is_favorable, confidence, reason = market_analyzer.is_favorable_condition()
    assert isinstance(is_favorable, bool)
    assert 0 <= confidence <= 1
    assert isinstance(reason, str)

def test_regime_detection(market_analyzer, sample_candle_data):
    # Add trending market data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    regime = market_analyzer._detect_market_regime()
    assert regime.type in ['trending', 'ranging', 'volatile']
    assert 0 <= regime.strength <= 1
    assert regime.direction in ['up', 'down', None]
    assert 0 <= regime.volatility <= 1
    assert 0 <= regime.confidence <= 1

def test_trend_strength_calculation(market_analyzer, sample_candle_data):
    # Add data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    trend_strength = market_analyzer._calculate_trend_strength()
    assert 0 <= trend_strength <= 1

def test_volume_profile_analysis(market_analyzer, sample_candle_data):
    # Add data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    volume_profile = market_analyzer._analyze_volume_profile()
    assert 'above_average' in volume_profile
    assert 'strength' in volume_profile
    assert isinstance(volume_profile['above_average'], bool)
    assert 0 <= volume_profile['strength'] <= 1

def test_support_resistance_levels(market_analyzer, sample_candle_data):
    # Add data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    levels = market_analyzer._find_support_resistance()
    assert 'support' in levels
    assert 'resistance' in levels
    assert isinstance(levels['support'], (float, int))
    assert isinstance(levels['resistance'], (float, int))
    assert levels['support'] <= levels['resistance']

def test_technical_indicators(market_analyzer, sample_candle_data):
    # Add data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    # Test RSI
    rsi = market_analyzer.calculate_rsi()
    assert 0 <= rsi <= 100
    
    # Test MACD
    macd, signal = market_analyzer.calculate_macd()
    assert isinstance(macd, float)
    assert isinstance(signal, float)
    
    # Test Bollinger Bands
    upper, middle, lower = market_analyzer.calculate_bollinger_bands()
    assert upper >= middle >= lower
    
def test_favorable_conditions_with_indicators(market_analyzer):
    """Test favorable conditions detection with technical indicators."""
    # Add uptrending data
    base_price = 1.2000
    timestamp = datetime.now()
    
    for i in range(50):
        price = base_price + (i * 0.0001)  # Steadily increasing price
        candle = {
            'timestamp': (timestamp + timedelta(minutes=i)).timestamp(),
            'open': price,
            'high': price + 0.0005,
            'low': price - 0.0005,
            'close': price,
            'volume': 1000
        }
        market_analyzer.add_candle(candle)
    
    # Get trading conditions
    is_favorable, confidence, reason = market_analyzer.is_favorable_condition()
    
    # Should detect favorable conditions in a clear uptrend
    assert is_favorable
    assert confidence > 0.5
    assert "trend" in reason.lower()

def test_momentum_calculation(market_analyzer, sample_candle_data):
    """Test momentum indicator calculations."""
    # Add data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    momentum = market_analyzer._calculate_momentum()
    assert 'rsi' in momentum
    assert 'macd' in momentum
    assert 'momentum_strength' in momentum
    assert 0 <= momentum['rsi'] <= 100
    assert isinstance(momentum['macd'], float)
    assert 0 <= momentum['momentum_strength'] <= 1

def test_support_resistance_with_price(market_analyzer, sample_candle_data):
    """Test support and resistance levels with current price."""
    # Add data
    for candle in sample_candle_data[:50]:
        market_analyzer.add_candle(candle)
    
    levels = market_analyzer._find_support_resistance()
    assert 'current_price' in levels
    assert 'nearest_support' in levels
    assert 'nearest_resistance' in levels
    assert levels['nearest_support'] < levels['current_price']
    assert levels['nearest_resistance'] > levels['current_price']
