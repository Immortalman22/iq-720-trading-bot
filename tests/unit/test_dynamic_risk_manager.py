"""Unit tests for the dynamic risk manager."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.utils.dynamic_risk_manager import DynamicRiskManager, RiskParameters
from src.utils.trade_tracker import TradeStats, TradeTracker
from src.utils.market_analyzer import MarketAnalyzer

@pytest.fixture
def mock_trade_tracker():
    tracker = Mock(spec=TradeTracker)
    stats = TradeStats(
        total_trades=20,
        winning_trades=12,
        losing_trades=8,
        total_profit=1000,
        total_loss=-500,
        win_rate=0.6,
        profit_factor=1.5,
        max_drawdown=0.03,
        avg_win=100,
        avg_loss=-70,
        largest_win=300,
        largest_loss=-150,
        avg_holding_time=timedelta(hours=2)
    )
    tracker.get_statistics.return_value = stats
    return tracker

@pytest.fixture
def mock_market_analyzer():
    analyzer = Mock()
    analyzer.get_market_conditions = Mock(return_value={
        'trend_strength': 0.7,
        'regime': 'trending',
        'direction': 'up',
        'volatility': 0.002,
        'support_resistance': {
            'current_price': 1.2000,
            'nearest_support': 1.1950,
            'nearest_resistance': 1.2050
        }
    })
    analyzer.get_volatility = Mock(return_value=0.002)
    analyzer.get_base_volatility = Mock(return_value=0.002)
    return analyzer

@pytest.fixture
def risk_manager(mock_trade_tracker, mock_market_analyzer):
    return DynamicRiskManager(
        mock_trade_tracker,
        mock_market_analyzer,
        RiskParameters(
            base_position_size=1.0,
            max_position_size=2.0,
            min_position_size=0.1,
            max_risk_per_trade=0.02,
            max_total_risk=0.06,
            drawdown_scaling=True,
            volatility_scaling=True,
            win_rate_scaling=True,
            profit_factor_scaling=True
        )
    )

def test_initial_risk_factors(risk_manager):
    """Test initial risk factor values."""
    assert risk_manager.performance_factor == 1.0
    assert risk_manager.market_factor == 1.0

def test_position_size_calculation(risk_manager):
    """Test position size calculation."""
    symbol = "BTCUSDT"
    position_size = risk_manager.calculate_position_size(symbol)
    assert 0.1 <= position_size <= 2.0

def test_performance_factor_scaling(risk_manager, mock_trade_tracker):
    """Test performance-based risk scaling."""
    # Set up good performance stats
    good_stats = TradeStats(
        total_trades=50,
        winning_trades=35,
        losing_trades=15,
        total_profit=2000,
        total_loss=-500,
        win_rate=0.7,
        profit_factor=4.0,
        max_drawdown=0.01
    )
    mock_trade_tracker.get_statistics.return_value = good_stats
    
    risk_manager._update_performance_factor()
    assert risk_manager.performance_factor > 1.0

    # Set up poor performance stats
    poor_stats = TradeStats(
        total_trades=50,
        winning_trades=15,
        losing_trades=35,
        total_profit=500,
        total_loss=-1000,
        win_rate=0.3,
        profit_factor=0.5,
        max_drawdown=0.15
    )
    mock_trade_tracker.get_statistics.return_value = poor_stats
    
    risk_manager._update_performance_factor()
    assert risk_manager.performance_factor < 1.0

def test_market_factor_scaling(risk_manager, mock_market_analyzer):
    """Test market condition-based risk scaling."""
    symbol = "BTCUSDT"
    
    # Test high volatility scenario
    mock_market_analyzer.get_volatility.return_value = 0.8
    mock_market_analyzer.get_trend_strength.return_value = 0.5
    
    risk_manager._update_market_factor(symbol)
    high_vol_factor = risk_manager.market_factor
    assert high_vol_factor < 1.0

    # Test strong trend scenario
    mock_market_analyzer.get_volatility.return_value = 0.5
    mock_market_analyzer.get_trend_strength.return_value = 0.9
    
    risk_manager._update_market_factor(symbol)
    strong_trend_factor = risk_manager.market_factor
    assert strong_trend_factor > 1.0

def test_risk_factors_update_frequency(risk_manager):
    """Test that risk factors don't update too frequently."""
    symbol = "BTCUSDT"
    
    # First update
    risk_manager._update_risk_factors(symbol)
    initial_perf = risk_manager.performance_factor
    initial_market = risk_manager.market_factor
    
    # Immediate second update - should not change factors
    risk_manager._update_risk_factors(symbol)
    assert risk_manager.performance_factor == initial_perf
    assert risk_manager.market_factor == initial_market

def test_drawdown_protection(risk_manager, mock_trade_tracker):
    """Test drawdown protection scaling."""
    stats = TradeStats(
        total_trades=50,
        winning_trades=25,
        losing_trades=25,
        total_profit=1000,
        total_loss=-1000,
        win_rate=0.5,
        profit_factor=1.0,
        max_drawdown=0.2  # 20% drawdown
    )
    mock_trade_tracker.get_statistics.return_value = stats
    
    risk_manager._update_performance_factor()
    assert risk_manager.performance_factor < 0.7  # Significant reduction
        base_position_size=1.0,
        max_position_size=2.0,
        min_position_size=0.1,
        max_risk_per_trade=0.02,
        max_total_risk=0.06
    )
    return DynamicRiskManager(mock_trade_tracker, mock_market_analyzer, params)

def test_initialize_risk_manager(risk_manager):
    """Test risk manager initialization."""
    assert risk_manager.params.base_position_size == 1.0
    assert risk_manager.params.max_position_size == 2.0
    assert risk_manager.params.min_position_size == 0.1
    assert risk_manager.performance_factor == 1.0
    assert risk_manager.market_factor == 1.0
    assert risk_manager.drawdown_factor == 1.0
    assert risk_manager.volatility_factor == 1.0

def test_calculate_position_size_basic(risk_manager):
    """Test basic position size calculation."""
    size = risk_manager.calculate_position_size("EUR/USD", 0.8, 1.2000)
    assert 0.1 <= size <= 2.0

def test_risk_limits(risk_manager):
    """Test risk limits enforcement."""
    # Add some existing risk
    risk_manager.risk_per_symbol = {"GBP/USD": 0.04}
    risk_manager.current_total_risk = 0.04
    
    # Try to open a position that would exceed limits
    size = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    # Should be reduced to fit within limits
    assert size < risk_manager.params.max_position_size

def test_update_risk_state(risk_manager):
    """Test risk state updates."""
    risk_manager.update_risk_state("EUR/USD", 1.0, 1.2000)
    assert "EUR/USD" in risk_manager.risk_per_symbol
    assert risk_manager.current_total_risk > 0

def test_release_risk(risk_manager):
    """Test risk release when closing positions."""
    # Add initial risk
    risk_manager.risk_per_symbol = {"EUR/USD": 0.02}
    risk_manager.current_total_risk = 0.02
    
    # Release the risk
    risk_manager.release_risk("EUR/USD")
    
    assert "EUR/USD" not in risk_manager.risk_per_symbol
    assert risk_manager.current_total_risk == 0

def test_performance_scaling(risk_manager, mock_trade_tracker):
    """Test performance-based position scaling."""
    # Force risk factors update
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    
    # Set good performance stats
    stats = TradeStats(
        total_trades=50,
        winning_trades=35,
        losing_trades=15,
        total_profit=4200,
        total_loss=-900,
        win_rate=0.7,
        profit_factor=2.0,
        max_drawdown=0.02,
        avg_win=120,
        avg_loss=-60,
        largest_win=400,
        largest_loss=-120,
        avg_holding_time=timedelta(hours=2)
    )
    mock_trade_tracker.get_stats.return_value = stats
    
    # Calculate position size
    size1 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    # Set poor performance stats
    stats.win_rate = 0.3
    stats.profit_factor = 0.5
    mock_trade_tracker.get_stats.return_value = stats
    
    # Force update and recalculate
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    size2 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    assert size1 > size2

def test_market_condition_scaling(risk_manager, mock_market_analyzer):
    """Test market condition-based position scaling."""
    # Force risk factors update
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    
    # Set favorable market conditions
    mock_market_analyzer.get_market_conditions.return_value = {
        'trend_strength': 0.9,
        'regime': 'trending'
    }
    
    size1 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    # Set unfavorable market conditions
    mock_market_analyzer.get_market_conditions.return_value = {
        'trend_strength': 0.3,
        'regime': 'volatile'
    }
    
    # Force update and recalculate
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    size2 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    assert size1 > size2

def test_volatility_scaling(risk_manager, mock_market_analyzer):
    """Test volatility-based position scaling."""
    # Force risk factors update
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    
    # Set normal volatility
    mock_market_analyzer.get_volatility.return_value = 0.002
    mock_market_analyzer.get_base_volatility.return_value = 0.002
    
    size1 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    # Set high volatility
    mock_market_analyzer.get_volatility.return_value = 0.004
    
    # Force update and recalculate
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    size2 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    assert size1 > size2

def test_drawdown_protection(risk_manager, mock_trade_tracker):
    """Test drawdown-based position scaling."""
    # Force risk factors update
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    
    # Set low drawdown
    stats = mock_trade_tracker.get_stats.return_value
    stats.max_drawdown = 0.01
    
    size1 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    # Set high drawdown
    stats.max_drawdown = 0.10
    
    # Force update and recalculate
    risk_manager.last_adjustment = datetime.now() - timedelta(hours=1)
    size2 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    
    assert size1 > size2

def test_signal_strength_scaling(risk_manager):
    """Test signal strength impact on position sizing."""
    # Compare positions sizes with different signal strengths
    size1 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    size2 = risk_manager.calculate_position_size("EUR/USD", 0.5, 1.2000)
    
    assert size1 > size2

def test_concurrent_positions(risk_manager):
    """Test handling of multiple concurrent positions."""
    # Open first position
    size1 = risk_manager.calculate_position_size("EUR/USD", 1.0, 1.2000)
    risk_manager.update_risk_state("EUR/USD", size1, 1.2000)
    
    # Try to open second position
    size2 = risk_manager.calculate_position_size("GBP/USD", 1.0, 1.5000)
    risk_manager.update_risk_state("GBP/USD", size2, 1.5000)
    
    # Verify total risk is within limits
    assert risk_manager.current_total_risk <= risk_manager.params.max_total_risk
    
    # Close first position
    risk_manager.release_risk("EUR/USD")
    
    # Verify remaining risk is updated
    assert risk_manager.current_total_risk < risk_manager.params.max_total_risk
