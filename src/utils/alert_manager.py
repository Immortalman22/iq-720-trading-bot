"""
Customizable alert system for trading notifications.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Callable
from enum import Enum
import json
from datetime import datetime, time
from pathlib import Path
import logging

from .telegram_notifier import TelegramNotifier
from .trade_tracker import TradeStats
from .market_analyzer import MarketRegime

class AlertType(Enum):
    """Types of alerts that can be configured."""
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    PERFORMANCE = "performance"
    RISK_LEVEL = "risk_level"
    MARKET_REGIME = "market_regime"
    CUSTOM = "custom"

class AlertPriority(Enum):
    """Priority levels for alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AlertRule:
    """Configuration for a single alert rule."""
    type: AlertType
    enabled: bool = True
    priority: AlertPriority = AlertPriority.MEDIUM
    conditions: Dict = None  # Specific conditions for the alert
    quiet_period: int = 0  # Minutes between repeated alerts
    active_hours: List[tuple] = None  # List of (start_time, end_time) tuples
    max_daily: int = None  # Maximum alerts per day
    format_template: str = None  # Custom message template
    notification_channels: List[str] = None  # List of channels to notify

class AlertManager:
    """
    Manages customizable trading alerts with support for multiple
    notification channels and complex alerting rules.
    """
    def __init__(self, 
                 telegram_notifier: TelegramNotifier,
                 config_path: str = "config/alerts.json"):
        """
        Initialize the alert manager.
        
        Args:
            telegram_notifier: TelegramNotifier instance
            config_path: Path to alert configuration file
        """
        self.logger = logging.getLogger(__name__)
        self.telegram = telegram_notifier
        self.config_path = Path(config_path)
        self.alerts: Dict[str, AlertRule] = {}
        self.alert_history: Dict[str, List[datetime]] = {}
        
        # Load configuration
        self._load_config()
        
    def _load_config(self) -> None:
        """Load alert configuration from file."""
        try:
            if not self.config_path.exists():
                self._create_default_config()
            
            with open(self.config_path) as f:
                config = json.load(f)
                
            self.alerts = {
                name: AlertRule(
                    type=AlertType(rule['type']),
                    enabled=rule.get('enabled', True),
                    priority=AlertPriority(rule.get('priority', 'medium')),
                    conditions=rule.get('conditions', {}),
                    quiet_period=rule.get('quiet_period', 0),
                    active_hours=[(time.fromisoformat(t[0]), time.fromisoformat(t[1]))
                                for t in rule.get('active_hours', [])] if rule.get('active_hours') else None,
                    max_daily=rule.get('max_daily'),
                    format_template=rule.get('format_template'),
                    notification_channels=rule.get('notification_channels', ['telegram'])
                )
                for name, rule in config.items()
            }
            
        except Exception as e:
            self.logger.error(f"Error loading alert configuration: {e}")
            self._create_default_config()
            
    def _create_default_config(self) -> None:
        """Create default alert configuration."""
        default_config = {
            "trade_entry": {
                "type": "trade_entry",
                "priority": "medium",
                "conditions": {
                    "min_confidence": 0.7
                },
                "quiet_period": 5,
                "notification_channels": ["telegram"]
            },
            "trade_exit": {
                "type": "trade_exit",
                "priority": "medium",
                "conditions": {
                    "min_profit": 0.0
                },
                "quiet_period": 5,
                "notification_channels": ["telegram"]
            },
            "drawdown": {
                "type": "drawdown",
                "priority": "high",
                "conditions": {
                    "threshold": 0.1
                },
                "quiet_period": 60,
                "notification_channels": ["telegram"]
            },
            "volatility": {
                "type": "volatility",
                "priority": "medium",
                "conditions": {
                    "threshold": 0.8
                },
                "quiet_period": 30,
                "notification_channels": ["telegram"]
            }
        }
        
        self.config_path.parent.mkdir(exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
            
        self.alerts = {
            name: AlertRule(
                type=AlertType(rule['type']),
                priority=AlertPriority(rule['priority']),
                conditions=rule['conditions'],
                quiet_period=rule['quiet_period'],
                notification_channels=rule['notification_channels']
            )
            for name, rule in default_config.items()
        }
        
    def should_alert(self, alert_name: str, data: Dict) -> bool:
        """
        Check if an alert should be triggered based on its rules.
        
        Args:
            alert_name: Name of the alert rule to check
            data: Data to evaluate against the alert conditions
            
        Returns:
            bool: Whether the alert should be triggered
        """
        if alert_name not in self.alerts:
            return False
            
        rule = self.alerts[alert_name]
        if not rule.enabled:
            return False
            
        # Check quiet period
        if alert_name in self.alert_history:
            last_alert = self.alert_history[alert_name][-1]
            minutes_since = (datetime.now() - last_alert).total_seconds() / 60
            if minutes_since < rule.quiet_period:
                return False
                
        # Check daily limit
        if rule.max_daily:
            today_alerts = [
                ts for ts in self.alert_history.get(alert_name, [])
                if ts.date() == datetime.now().date()
            ]
            if len(today_alerts) >= rule.max_daily:
                return False
                
        # Check active hours
        if rule.active_hours:
            current_time = datetime.now().time()
            is_active = any(
                start <= current_time <= end
                for start, end in rule.active_hours
            )
            if not is_active:
                return False
                
        # Check conditions
        if not rule.conditions:
            return True
            
        return self._evaluate_conditions(rule.conditions, data)
        
    def _evaluate_conditions(self, conditions: Dict, data: Dict) -> bool:
        """Evaluate alert conditions against provided data."""
        try:
            for key, value in conditions.items():
                if key not in data:
                    continue
                    
                if isinstance(value, (int, float)):
                    if key.startswith('min_'):
                        if data[key[4:]] < value:
                            return False
                    elif key.startswith('max_'):
                        if data[key[4:]] > value:
                            return False
                    else:
                        if data[key] != value:
                            return False
                elif isinstance(value, list):
                    if data[key] not in value:
                        return False
                elif isinstance(value, dict):
                    if not self._evaluate_conditions(value, data):
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Error evaluating conditions: {e}")
            return False
            
    async def trigger_alert(self, alert_name: str, data: Dict) -> None:
        """
        Trigger an alert if conditions are met.
        
        Args:
            alert_name: Name of the alert rule to trigger
            data: Data to include in the alert
        """
        if not self.should_alert(alert_name, data):
            return
            
        rule = self.alerts[alert_name]
        
        # Record alert
        if alert_name not in self.alert_history:
            self.alert_history[alert_name] = []
        self.alert_history[alert_name].append(datetime.now())
        
        # Format message
        if rule.format_template:
            message = rule.format_template.format(**data)
        else:
            message = self._default_format(alert_name, rule, data)
            
        # Send notifications
        for channel in rule.notification_channels:
            if channel == 'telegram':
                await self._send_telegram(message, rule.priority)
                
        self.logger.info(f"Alert triggered: {alert_name}")
        
    def _default_format(self, name: str, rule: AlertRule, data: Dict) -> str:
        """Create default formatted message for an alert."""
        priority_symbols = {
            AlertPriority.LOW: "ℹ️",
            AlertPriority.MEDIUM: "⚠️",
            AlertPriority.HIGH: "🚨",
            AlertPriority.CRITICAL: "‼️"
        }
        
        message = f"{priority_symbols[rule.priority]} <b>{name.upper()}</b>\n\n"
        
        # Add relevant data fields
        for key, value in data.items():
            if isinstance(value, (int, float)):
                message += f"{key.replace('_', ' ').title()}: {value:,.2f}\n"
            else:
                message += f"{key.replace('_', ' ').title()}: {value}\n"
                
        return message
        
    async def _send_telegram(self, message: str, priority: AlertPriority) -> None:
        """Send alert via Telegram."""
        try:
            await self.telegram.bot.send_message(
                chat_id=self.telegram.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            self.logger.error(f"Failed to send Telegram alert: {e}")
