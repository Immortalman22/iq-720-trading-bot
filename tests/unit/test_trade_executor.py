"""Unit tests for the trade executor."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.trade_executor import TradeExecutor, ExecutionParameters
from src.utils.dynamic_risk_manager import RiskParameters
from src.utils.trade_tracker import TradeTracker, Trade
from src.utils.market_analyzer import MarketAnalyzer
from src.signal_generator import Signal

@pytest.fixture
def mock_trade_tracker():
    return Mock(spec=TradeTracker)

@pytest.fixture
def mock_market_analyzer():
    analyzer = Mock()
    analyzer.check_market_conditions = Mock(
        return_value=(True, 0.8, "Strong trend")
    )
    analyzer.get_market_conditions = Mock(return_value={
        'trend_strength': 0.7,
        'regime': 'trending',
        'direction': 'up',
        'volatility': 0.002
    })
    analyzer.get_volatility = Mock(return_value=0.002)
    analyzer.get_base_volatility = Mock(return_value=0.002)
    return analyzer

@pytest.fixture
def executor(mock_trade_tracker, mock_market_analyzer):
    execution_params = ExecutionParameters(
        min_confidence=0.6,
        max_daily_trades=10,
        min_time_between_trades=15,
        recovery_mode_threshold=3,
        enable_recovery_mode=True,
        base_trade_size=1.0
    )
    risk_params = RiskParameters(
        base_position_size=1.0,
        max_position_size=2.0,
        min_position_size=0.1,
        max_risk_per_trade=0.02,
        max_total_risk=0.06
    )
    return TradeExecutor(
        mock_trade_tracker,
        mock_market_analyzer,
        execution_params,
        risk_params
    )

@pytest.fixture
def valid_signal():
    return Signal(
        timestamp=datetime.now(),
        direction="BUY",
        asset="EUR/USD",
        expiry_minutes=60,
        confidence=0.8,
        indicators={
            'entry_price': 1.2000,
            'rsi': 65,
            'trend': 'up'
        }
    )

def test_process_valid_signal(executor, valid_signal):
    """Test processing a valid trading signal."""
    trade = executor.process_signal(valid_signal)
    
    assert trade is not None
    assert trade.symbol == "EUR/USD"
    assert trade.direction == "buy"
    assert trade.status == "open"
    assert 0.1 <= trade.position_size <= 2.0
    assert trade.entry_price == 1.2000

def test_reject_low_confidence_signal(executor, valid_signal):
    """Test rejection of low confidence signals."""
    valid_signal.confidence = 0.3
    trade = executor.process_signal(valid_signal)
    
    assert trade is None

def test_reject_unfavorable_market(executor, valid_signal, mock_market_analyzer):
    """Test rejection when market conditions are unfavorable."""
    mock_market_analyzer.check_market_conditions = Mock(
        return_value=(False, 0.3, "High volatility")
    )
    trade = executor.process_signal(valid_signal)
    
    assert trade is None

def test_daily_trade_limit(executor, valid_signal):
    """Test enforcement of daily trade limit."""
    # Execute max allowed trades
    executed = 0
    trade_time = datetime.now()
    
    for i in range(executor.params.max_daily_trades):
        # Use different symbols and times to avoid rejection
        valid_signal.asset = f"PAIR{i}/USD"
        valid_signal.timestamp = trade_time
        executor.last_trade_time = trade_time - timedelta(minutes=16)
        
        trade = executor.process_signal(valid_signal)
        assert trade is not None
        executed += 1
        
        trade_time += timedelta(minutes=20)
    
    # Next trade should be rejected
    valid_signal.asset = "FINAL/USD"
    valid_signal.timestamp = trade_time
    executor.last_trade_time = trade_time - timedelta(minutes=16)
    assert executor.process_signal(valid_signal) is None
    assert executed == executor.params.max_daily_trades

def test_time_between_trades(executor, valid_signal):
    """Test minimum time between trades requirement."""
    # Set initial time
    trade_time = datetime.now()
    valid_signal.timestamp = trade_time
    executor.last_trade_time = trade_time - timedelta(minutes=16)
    
    # Execute first trade
    trade1 = executor.process_signal(valid_signal)
    assert trade1 is not None
    
    # Try immediate second trade with different symbol
    valid_signal.asset = "EUR/GBP"
    valid_signal.timestamp = trade_time  # Same time as first trade
    trade2 = executor.process_signal(valid_signal)
    assert trade2 is None  # Should be rejected due to time
    
    # Move time forward and try again
    trade_time += timedelta(minutes=20)
    valid_signal.timestamp = trade_time
    executor.last_trade_time = trade_time - timedelta(minutes=16)
    trade3 = executor.process_signal(valid_signal)
    assert trade3 is not None

def test_recovery_mode(executor, valid_signal):
    """Test recovery mode activation after losses."""
    # Create some losing trades
    for i in range(executor.params.recovery_mode_threshold):
        # Use different symbols and adjust times
        valid_signal.asset = f"PAIR{i}/USD"
        valid_signal.timestamp += timedelta(minutes=20)
        executor.last_trade_time = valid_signal.timestamp - timedelta(minutes=16)
        
        trade = executor.process_signal(valid_signal)
        assert trade is not None
        executor.close_trade(
            trade.id,
            exit_price=1.1900,  # Loss
            exit_time=valid_signal.timestamp
        )
    
    # Next trade should be rejected due to recovery mode
    valid_signal.asset = "FINAL/USD"
    valid_signal.timestamp += timedelta(minutes=20)
    executor.last_trade_time = valid_signal.timestamp - timedelta(minutes=16)
    assert executor.process_signal(valid_signal) is None

def test_close_trade(executor, valid_signal):
    """Test proper trade closure."""
    # Open trade
    trade = executor.process_signal(valid_signal)
    assert trade is not None
    assert trade.status == "open"
    
    # Close trade with profit
    closed_trade = executor.close_trade(
        trade.id,
        exit_price=1.2100,
        exit_time=datetime.now()
    )
    
    assert closed_trade is not None
    assert closed_trade.status == "closed"
    assert closed_trade.exit_price == 1.2100
    assert closed_trade.profit_loss > 0

def test_reject_duplicate_symbol(executor, valid_signal):
    """Test rejection of duplicate trades for same symbol."""
    # Open first trade
    trade1 = executor.process_signal(valid_signal)
    assert trade1 is not None
    
    # Try to open second trade for same symbol
    trade2 = executor.process_signal(valid_signal)
    assert trade2 is None

def test_daily_stats_reset(executor, valid_signal):
    """Test daily statistics reset."""
    # Execute some trades
    executed = 0
    for i in range(5):
        # Use different symbols and times
        valid_signal.asset = f"PAIR{i}/USD"
        valid_signal.timestamp += timedelta(minutes=20)
        executor.last_trade_time = valid_signal.timestamp - timedelta(minutes=16)
        
        trade = executor.process_signal(valid_signal)
        assert trade is not None
        executed += 1
    
    # Move to next day
    valid_signal.timestamp += timedelta(days=1)
    executor._check_daily_reset(valid_signal.timestamp)
    
    # Should be able to trade again
    assert executor.daily_trade_count == 0
    valid_signal.asset = "NEXT/USD"
    executor.last_trade_time = valid_signal.timestamp - timedelta(minutes=16)
    assert executor.process_signal(valid_signal) is not None

def test_pnl_calculation(executor, valid_signal):
    """Test PnL calculation for different trade directions."""
    # Long trade with profit
    valid_signal.direction = "BUY"
    valid_signal.asset = "EUR/USD"
    trade_time = datetime.now()
    valid_signal.timestamp = trade_time
    executor.last_trade_time = trade_time - timedelta(minutes=16)
    
    long_trade = executor.process_signal(valid_signal)
    assert long_trade is not None
    closed_long = executor.close_trade(
        long_trade.id,
        exit_price=1.2100,  # 100 pip profit
        exit_time=trade_time + timedelta(minutes=30)
    )
    assert closed_long.profit_loss > 0
    
    # Short trade with profit
    valid_signal.direction = "SELL"
    valid_signal.asset = "GBP/USD"
    trade_time = datetime.now() + timedelta(minutes=60)
    valid_signal.timestamp = trade_time
    executor.last_trade_time = trade_time - timedelta(minutes=16)
    
    short_trade = executor.process_signal(valid_signal)
    assert short_trade is not None
    closed_short = executor.close_trade(
        short_trade.id,
        exit_price=1.1900,  # 100 pip profit
        exit_time=trade_time + timedelta(minutes=30)
    )
    assert closed_short.profit_loss > 0
