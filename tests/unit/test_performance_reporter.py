"""Unit tests for the performance reporter."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from pathlib import Path

from src.utils.performance_reporter import PerformanceReporter, PerformanceMetrics
from src.utils.trade_tracker import TradeTracker
from src.utils.market_analyzer import MarketAnalyzer

@pytest.fixture
def sample_trades():
    """Generate sample trade data for testing."""
    now = datetime.now()
    trades = []
    for i in range(20):
        profit = 100 if i % 2 == 0 else -50  # Alternating wins/losses
        trades.append({
            'timestamp': now - timedelta(hours=i),
            'symbol': 'BTCUSDT',
            'entry_price': 50000,
            'exit_price': 50000 + profit,
            'position_size': 1.0,
            'profit_loss': profit,
            'direction': 'long',
            'duration': timedelta(minutes=30)
        })
    return trades

@pytest.fixture
def mock_trade_tracker(sample_trades):
    """Create a mock TradeTracker."""
    tracker = Mock(spec=TradeTracker)
    tracker.get_trade_history.return_value = sample_trades
    return tracker

@pytest.fixture
def mock_market_analyzer():
    """Create a mock MarketAnalyzer."""
    analyzer = Mock(spec=MarketAnalyzer)
    return analyzer

@pytest.fixture
def reporter(mock_trade_tracker, mock_market_analyzer, tmp_path):
    """Create a PerformanceReporter instance with mocked dependencies."""
    return PerformanceReporter(
        trade_tracker=mock_trade_tracker,
        market_analyzer=mock_market_analyzer,
        report_dir=str(tmp_path)
    )

def test_report_generation(reporter, sample_trades):
    """Test basic report generation."""
    report = reporter.generate_report()
    assert isinstance(report, dict)
    assert 'metrics' in report
    assert 'files' in report
    assert 'timestamp' in report

def test_metrics_calculation(reporter, sample_trades):
    """Test performance metrics calculation."""
    metrics = reporter._calculate_metrics(sample_trades, "all")
    assert isinstance(metrics, PerformanceMetrics)
    assert metrics.total_return == 500  # 10 wins * 100 - 10 losses * 50
    assert metrics.win_rate == 0.5  # Alternating wins/losses
    assert metrics.profit_factor == 2.0  # 1000 / 500
    assert metrics.total_trades == 20

def test_visualization_generation(reporter, sample_trades):
    """Test visualization generation."""
    metrics = reporter._calculate_metrics(sample_trades, "all")
    figures = reporter._generate_visualizations(sample_trades, metrics)
    assert isinstance(figures, dict)
    assert 'equity_curve' in figures
    assert 'drawdown' in figures
    assert 'pnl_distribution' in figures
    assert 'hourly_performance' in figures

def test_summary_generation(reporter):
    """Test summary markdown generation."""
    metrics = PerformanceMetrics(
        total_return=1000.0,
        win_rate=0.65,
        profit_factor=2.5,
        max_drawdown=0.1,
        sharpe_ratio=2.1,
        sortino_ratio=3.0,
        avg_trade_return=50.0,
        avg_win_return=100.0,
        avg_loss_return=-30.0,
        total_trades=100,
        avg_trades_per_day=5.0,
        max_consecutive_wins=5,
        max_consecutive_losses=2,
        time_in_market=0.7,
        risk_adjusted_return=900.0,
        calmar_ratio=10.0,
        recovery_factor=5.0
    )
    
    summary = reporter._generate_summary(metrics, "daily")
    assert isinstance(summary, str)
    assert "Trading Performance Summary" in summary
    assert "Total Return: 1000.00" in summary
    assert "Win Rate: 65.00%" in summary

def test_empty_trade_history(reporter):
    """Test report generation with no trades."""
    reporter.trade_tracker.get_trade_history.return_value = []
    report = reporter.generate_report()
    assert isinstance(report, dict)
    assert not report  # Should return empty dict

def test_timeframe_filtering(reporter, sample_trades):
    """Test report generation with different timeframes."""
    for timeframe in ["daily", "weekly", "monthly", "all"]:
        report = reporter.generate_report(timeframe)
        assert isinstance(report, dict)
        assert report['timeframe'] == timeframe

def test_file_saving(reporter, sample_trades, tmp_path):
    """Test that report files are saved correctly."""
    report = reporter.generate_report()
    
    # Check that files exist
    for file_path in report['files'].values():
        assert Path(file_path).exists()
        
    # Check file types
    assert any(f.endswith('.json') for f in report['files'].values())
    assert any(f.endswith('.html') for f in report['files'].values())
    assert any(f.endswith('.md') for f in report['files'].values())
