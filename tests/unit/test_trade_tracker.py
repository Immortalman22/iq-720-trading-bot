"""Tests for the trade tracking system."""
import pytest
from datetime import datetime, timedelta
from src.utils.trade_tracker import TradeTracker, Trade, TradeStats

@pytest.fixture
def tracker():
    """Create a fresh trade tracker for each test."""
    return TradeTracker()

@pytest.fixture
def sample_trade():
    """Create a sample trade for testing."""
    return Trade(
        id="test_trade_1",
        symbol="EUR/USD",
        entry_price=1.2000,
        position_size=1.0,
        entry_time=datetime.now(),
        direction="long",
        stop_loss=1.1950,
        take_profit=1.2100,
        tags=["test", "sample"],
        metadata={"strategy": "test_strategy"}
    )

def test_open_trade(tracker, sample_trade):
    """Test opening a new trade."""
    assert tracker.open_trade(sample_trade)
    assert sample_trade.id in tracker.active_trades
    assert tracker.get_trade(sample_trade.id) == sample_trade

def test_close_trade(tracker, sample_trade):
    """Test closing a trade and statistics update."""
    tracker.open_trade(sample_trade)
    exit_price = 1.2050  # 50 pip profit
    
    closed_trade = tracker.close_trade(sample_trade.id, exit_price)
    assert closed_trade is not None
    assert closed_trade.status == "closed"
    assert closed_trade.exit_price == exit_price
    assert closed_trade.profit_loss == 0.0050  # 50 pip profit
    
    # Check statistics
    stats = tracker.get_stats()
    assert stats.total_trades == 1
    assert stats.winning_trades == 1
    assert stats.total_profit == 0.0050

def test_multiple_trades(tracker):
    """Test handling multiple trades and statistics calculation."""
    # Create and close several trades
    trades = [
        ("trade1", 1.2000, 1.2050, "long"),  # Win
        ("trade2", 1.2050, 1.2000, "long"),  # Loss
        ("trade3", 1.2000, 1.2100, "long"),  # Big win
        ("trade4", 1.2100, 1.2080, "short")  # Win
    ]
    
    for trade_id, entry, exit, direction in trades:
        trade = Trade(
            id=trade_id,
            symbol="EUR/USD",
            entry_price=entry,
            position_size=1.0,
            direction=direction,
            entry_time=datetime.now()
        )
        tracker.open_trade(trade)
        tracker.close_trade(trade_id, exit)
    
    stats = tracker.get_stats()
    assert stats.total_trades == 4
    assert stats.winning_trades == 3
    assert stats.losing_trades == 1
    assert stats.win_rate == 0.75
    assert stats.largest_win == 0.0100  # 100 pip win from trade3

def test_timeframe_filtering(tracker):
    """Test getting statistics for different timeframes."""
    # Create trades with different dates
    old_trade = Trade(
        id="old_trade",
        symbol="EUR/USD",
        entry_price=1.2000,
        position_size=1.0,
        direction="long",
        entry_time=datetime.now() - timedelta(days=40)  # 40 days ago
    )
    
    new_trade = Trade(
        id="new_trade",
        symbol="EUR/USD",
        entry_price=1.2000,
        position_size=1.0,
        direction="long",
        entry_time=datetime.now() - timedelta(days=1)  # Yesterday
    )
    
    # Process trades
    tracker.open_trade(old_trade)
    tracker.close_trade(old_trade.id, 1.2050)
    tracker.open_trade(new_trade)
    tracker.close_trade(new_trade.id, 1.2050)
    
    # Check different timeframes
    month_stats = tracker.get_stats("month")
    assert month_stats.total_trades == 1  # Only new trade
    
    all_stats = tracker.get_stats("all")
    assert all_stats.total_trades == 2  # Both trades

def test_trade_history(tracker, sample_trade):
    """Test trade history tracking by symbol."""
    tracker.open_trade(sample_trade)
    tracker.close_trade(sample_trade.id, 1.2050)
    
    assert len(tracker.trade_history[sample_trade.symbol]) == 1
    assert tracker.trade_history[sample_trade.symbol][0].id == sample_trade.id

def test_error_handling(tracker):
    """Test error handling for invalid operations."""
    # Try to close non-existent trade
    result = tracker.close_trade("non_existent", 1.2000)
    assert result is None
    
    # Try to get non-existent trade
    trade = tracker.get_trade("non_existent")
    assert trade is None
    
    # Try to get stats with invalid timeframe
    stats = tracker.get_stats("invalid_timeframe")
    assert isinstance(stats, TradeStats)
    assert stats.total_trades == 0

def test_drawdown_calculation(tracker):
    """Test maximum drawdown calculation."""
    trades = [
        ("trade1", 1.2000, 1.2050, "long"),  # +50
        ("trade2", 1.2050, 1.1950, "long"),  # -100
        ("trade3", 1.1950, 1.2000, "long")   # +50
    ]
    
    for trade_id, entry, exit, direction in trades:
        trade = Trade(
            id=trade_id,
            symbol="EUR/USD",
            entry_price=entry,
            position_size=1.0,
            direction=direction,
            entry_time=datetime.now()
        )
        tracker.open_trade(trade)
        tracker.close_trade(trade_id, exit)
    
    stats = tracker.get_stats()
    assert stats.max_drawdown == 0.0100  # 100 pip drawdown

def test_profit_factor_calculation(tracker):
    """Test profit factor calculation."""
    trades = [
        ("trade1", 1.2000, 1.2030, "long"),  # +30
        ("trade2", 1.2030, 1.2000, "long"),  # -30
        ("trade3", 1.2000, 1.2040, "long")   # +40
    ]
    
    for trade_id, entry, exit, direction in trades:
        trade = Trade(
            id=trade_id,
            symbol="EUR/USD",
            entry_price=entry,
            position_size=1.0,
            direction=direction,
            entry_time=datetime.now()
        )
        tracker.open_trade(trade)
        tracker.close_trade(trade_id, exit)
    
    stats = tracker.get_stats()
    expected_profit_factor = (0.0030 + 0.0040) / 0.0030  # (30 + 40) / 30
    assert abs(stats.profit_factor - expected_profit_factor) < 0.0001
