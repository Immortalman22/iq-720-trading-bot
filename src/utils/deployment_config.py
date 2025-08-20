"""
Production Deployment Configuration Manager
Handles all production-specific settings and monitoring.
"""
import os
import json
import logging
from typing import Dict, Optional
from datetime import datetime
import threading
from pathlib import Path
import yaml

class DeploymentConfig:
    def __init__(self, config_path: str = "config/production.yml"):
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        self.config = self._load_config()
        self.performance_monitor = PerformanceMonitor()
        self.last_backup = None
        self.backup_interval = 3600  # 1 hour
        self._initialize_logging()
        
    def _load_config(self) -> Dict:
        """Load production configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.warning("Config not found, using defaults")
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict:
        """Get default production configuration."""
        return {
            'trading': {
                'max_daily_trades': 20,
                'max_concurrent_trades': 3,
                'max_daily_loss': 5.0,  # Percentage
                'min_win_rate': 80.0,  # Percentage
                'max_risk_per_trade': 2.0,  # Percentage
                'emergency_stop_loss': 10.0  # Percentage
            },
            'performance': {
                'max_signal_delay': 0.5,  # seconds
                'max_execution_time': 1.0,  # seconds
                'min_data_freshness': 0.2,  # seconds
                'monitoring_interval': 60  # seconds
            },
            'security': {
                'max_failed_attempts': 3,
                'lockout_duration': 300,  # seconds
                'required_ssl': True,
                'api_rate_limit': 100  # per minute
            },
            'backup': {
                'interval': 3600,  # seconds
                'keep_versions': 24,  # number of backups to keep
                'backup_path': 'backups/',
                'include_state': True
            }
        }
        
    def _initialize_logging(self):
        """Setup production logging."""
        log_config = {
            'version': 1,
            'handlers': {
                'file': {
                    'class': 'logging.FileHandler',
                    'filename': 'logs/production.log',
                    'mode': 'a',
                    'formatter': 'detailed'
                },
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple'
                }
            },
            'formatters': {
                'detailed': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                },
                'simple': {
                    'format': '%(levelname)s - %(message)s'
                }
            },
            'loggers': {
                '': {
                    'handlers': ['file', 'console'],
                    'level': 'INFO'
                }
            }
        }
        logging.config.dictConfig(log_config)

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'signal_generation_times': [],
            'execution_times': [],
            'win_rate': 0.0,
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'average_profit': 0.0,
            'system_load': 0.0
        }
        self.start_monitoring()
        
    def start_monitoring(self):
        """Start performance monitoring thread."""
        self.monitoring_thread = threading.Thread(
            target=self._monitor_performance,
            daemon=True
        )
        self.monitoring_thread.start()
        
    def _monitor_performance(self):
        """Continuous performance monitoring."""
        while True:
            try:
                self._update_metrics()
                self._check_alerts()
                threading.Event().wait(60)  # Check every minute
            except Exception as e:
                logging.error(f"Performance monitoring error: {e}")
                
    def _update_metrics(self):
        """Update performance metrics."""
        self.metrics['system_load'] = self._get_system_load()
        
        # Calculate moving averages
        if self.metrics['signal_generation_times']:
            avg_signal_time = sum(self.metrics['signal_generation_times'][-100:]) / \
                            len(self.metrics['signal_generation_times'][-100:])
            if avg_signal_time > 0.5:  # Alert if signal generation is slow
                logging.warning(f"Signal generation time high: {avg_signal_time:.2f}s")
                
        # Update win rate
        if self.metrics['total_trades'] > 0:
            self.metrics['win_rate'] = (self.metrics['successful_trades'] / 
                                      self.metrics['total_trades'] * 100)
                
    def _check_alerts(self):
        """Check for alert conditions."""
        # Check win rate
        if self.metrics['total_trades'] >= 10:  # Enough trades for meaningful data
            if self.metrics['win_rate'] < 80.0:
                logging.warning(f"Win rate below target: {self.metrics['win_rate']:.1f}%")
                
        # Check system load
        if self.metrics['system_load'] > 80.0:
            logging.warning(f"High system load: {self.metrics['system_load']:.1f}%")
            
    def _get_system_load(self) -> float:
        """Get current system load."""
        try:
            return os.getloadavg()[0] * 100
        except:
            return 0.0
            
    def log_trade(self, success: bool, profit: float):
        """Log trade result."""
        self.metrics['total_trades'] += 1
        if success:
            self.metrics['successful_trades'] += 1
        else:
            self.metrics['failed_trades'] += 1
            
        # Update average profit
        total_profit = (self.metrics['average_profit'] * 
                       (self.metrics['total_trades'] - 1) + profit)
        self.metrics['average_profit'] = total_profit / self.metrics['total_trades']
        
    def get_metrics(self) -> Dict:
        """Get current performance metrics."""
        return self.metrics.copy()
