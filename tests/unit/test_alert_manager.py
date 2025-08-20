"""Unit tests for the alert manager."""
import pytest
from datetime import datetime, time
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.utils.alert_manager import (
    AlertManager, AlertType, AlertPriority, AlertRule
)
from src.telegram_notifier import TelegramNotifier

@pytest.fixture
def mock_telegram():
    """Create a mock TelegramNotifier."""
    notifier = Mock(spec=TelegramNotifier)
    notifier.bot = AsyncMock()
    notifier.chat_id = "123456"
    return notifier

@pytest.fixture
def sample_config(tmp_path):
    """Create a sample alert configuration file."""
    config = {
        "test_alert": {
            "type": "trade_entry",
            "enabled": True,
            "priority": "high",
            "conditions": {
                "min_confidence": 0.8,
                "max_risk": 0.02
            },
            "quiet_period": 10,
            "max_daily": 50,
            "notification_channels": ["telegram"]
        }
    }
    
    config_file = tmp_path / "alerts.json"
    with open(config_file, 'w') as f:
        json.dump(config, f)
    return config_file

@pytest.fixture
def alert_manager(mock_telegram, sample_config):
    """Create an AlertManager instance with mock dependencies."""
    return AlertManager(mock_telegram, str(sample_config))

def test_load_config(alert_manager):
    """Test configuration loading."""
    assert "test_alert" in alert_manager.alerts
    rule = alert_manager.alerts["test_alert"]
    assert rule.type == AlertType.TRADE_ENTRY
    assert rule.priority == AlertPriority.HIGH
    assert rule.conditions["min_confidence"] == 0.8

def test_create_default_config(tmp_path):
    """Test default configuration creation."""
    config_path = tmp_path / "default_alerts.json"
    manager = AlertManager(Mock(spec=TelegramNotifier), str(config_path))
    
    assert config_path.exists()
    assert "trade_entry" in manager.alerts
    assert "drawdown" in manager.alerts

def test_should_alert_conditions(alert_manager):
    """Test alert condition evaluation."""
    data = {
        "confidence": 0.9,
        "risk": 0.01
    }
    assert alert_manager.should_alert("test_alert", data)
    
    data["confidence"] = 0.7  # Below min_confidence
    assert not alert_manager.should_alert("test_alert", data)

def test_quiet_period(alert_manager):
    """Test quiet period enforcement."""
    data = {
        "confidence": 0.9,
        "risk": 0.01
    }
    
    # First alert should work
    assert alert_manager.should_alert("test_alert", data)
    alert_manager.alert_history["test_alert"] = [datetime.now()]
    
    # Second alert within quiet period should not
    assert not alert_manager.should_alert("test_alert", data)

def test_active_hours(alert_manager):
    """Test active hours restriction."""
    rule = alert_manager.alerts["test_alert"]
    rule.active_hours = [
        (time(9, 0), time(17, 0))  # 9 AM to 5 PM
    ]
    
    data = {
        "confidence": 0.9,
        "risk": 0.01
    }
    
    with patch('datetime.datetime') as mock_dt:
        # Test during active hours
        mock_dt.now.return_value = datetime(2025, 8, 18, 13, 0)  # 1 PM
        assert alert_manager.should_alert("test_alert", data)
        
        # Test outside active hours
        mock_dt.now.return_value = datetime(2025, 8, 18, 20, 0)  # 8 PM
        assert not alert_manager.should_alert("test_alert", data)

def test_max_daily_alerts(alert_manager):
    """Test maximum daily alerts limit."""
    rule = alert_manager.alerts["test_alert"]
    rule.max_daily = 2
    
    data = {
        "confidence": 0.9,
        "risk": 0.01
    }
    
    today = datetime.now()
    alert_manager.alert_history["test_alert"] = [today, today]
    assert not alert_manager.should_alert("test_alert", data)

@pytest.mark.asyncio
async def test_trigger_alert(alert_manager):
    """Test alert triggering and notification."""
    data = {
        "confidence": 0.9,
        "risk": 0.01,
        "symbol": "BTCUSDT",
        "price": 50000
    }
    
    await alert_manager.trigger_alert("test_alert", data)
    
    # Check that Telegram message was sent
    alert_manager.telegram.bot.send_message.assert_called_once()
    
    # Check alert history
    assert "test_alert" in alert_manager.alert_history
    assert len(alert_manager.alert_history["test_alert"]) == 1

def test_custom_message_template(alert_manager):
    """Test custom message template formatting."""
    rule = alert_manager.alerts["test_alert"]
    rule.format_template = "Alert: {symbol} at {price:,.0f}"
    
    data = {
        "confidence": 0.9,
        "risk": 0.01,
        "symbol": "BTCUSDT",
        "price": 50000
    }
    
    message = alert_manager._default_format("test_alert", rule, data)
    assert "BTCUSDT" in message
    assert "50,000" in message
