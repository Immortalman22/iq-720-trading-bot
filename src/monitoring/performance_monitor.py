"""
Advanced Monitoring System
Provides real-time analytics and trading performance optimization.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import threading
import queue

class TradingMetricType(Enum):
    EXECUTION = "EXECUTION"
    PERFORMANCE = "PERFORMANCE"
    RISK = "RISK"
    MARKET = "MARKET"
    PATTERN = "PATTERN"

@dataclass
class TradeMetrics:
    entry_time: datetime
    exit_time: datetime
    direction: str
    profit_loss: float
    pattern_used: str
    execution_speed: float
    market_condition: str
    success: bool
    confidence_level: float
    session_name: str

class AdvancedMonitor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics_queue = queue.Queue()
        self.trade_history: List[TradeMetrics] = []
        self.pattern_performance = {}
        self.session_performance = {}
        self.market_condition_stats = {}
        self.alerts = []
        
        # Performance thresholds
        self.min_pattern_reliability = 0.8  # 80% minimum success rate
        self.min_session_performance = 0.75
        self.max_consecutive_losses = 3
        self.max_drawdown = 0.1  # 10%
        
        # Initialize monitoring
        self._start_monitoring_thread()

    def _start_monitoring_thread(self):
        """Start the monitoring thread."""
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Process new metrics
                while not self.metrics_queue.empty():
                    metric = self.metrics_queue.get_nowait()
                    self._process_metric(metric)

                # Analyze patterns
                self._analyze_pattern_performance()
                # Analyze sessions
                self._analyze_session_performance()
                # Check for alerts
                self._check_alert_conditions()

                # Sleep for a short duration
                threading.Event().wait(1.0)
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")

    def add_trade_metric(self, metric: TradeMetrics):
        """Add new trade metric for analysis."""
        self.metrics_queue.put(metric)
        self.trade_history.append(metric)
        
        # Keep only last 1000 trades for memory efficiency
        if len(self.trade_history) > 1000:
            self.trade_history.pop(0)

    def _process_metric(self, metric: TradeMetrics):
        """Process new trading metric."""
        # Update pattern performance
        if metric.pattern_used not in self.pattern_performance:
            self.pattern_performance[metric.pattern_used] = {
                'total': 0,
                'successful': 0,
                'avg_profit': 0.0,
                'recent_reliability': []
            }
            
        pattern_stats = self.pattern_performance[metric.pattern_used]
        pattern_stats['total'] += 1
        if metric.success:
            pattern_stats['successful'] += 1
        pattern_stats['avg_profit'] = (
            (pattern_stats['avg_profit'] * (pattern_stats['total'] - 1) +
             metric.profit_loss) / pattern_stats['total']
        )
        pattern_stats['recent_reliability'].append(1 if metric.success else 0)
        if len(pattern_stats['recent_reliability']) > 20:
            pattern_stats['recent_reliability'].pop(0)

        # Update session performance
        if metric.session_name not in self.session_performance:
            self.session_performance[metric.session_name] = {
                'total': 0,
                'successful': 0,
                'avg_profit': 0.0,
                'best_patterns': {}
            }
            
        session_stats = self.session_performance[metric.session_name]
        session_stats['total'] += 1
        if metric.success:
            session_stats['successful'] += 1
        session_stats['avg_profit'] = (
            (session_stats['avg_profit'] * (session_stats['total'] - 1) +
             metric.profit_loss) / session_stats['total']
        )
        
        # Update market condition stats
        if metric.market_condition not in self.market_condition_stats:
            self.market_condition_stats[metric.market_condition] = {
                'total': 0,
                'successful': 0,
                'avg_profit': 0.0,
                'best_patterns': {}
            }
            
        market_stats = self.market_condition_stats[metric.market_condition]
        market_stats['total'] += 1
        if metric.success:
            market_stats['successful'] += 1
        market_stats['avg_profit'] = (
            (market_stats['avg_profit'] * (market_stats['total'] - 1) +
             metric.profit_loss) / market_stats['total']
        )

    def _analyze_pattern_performance(self):
        """Analyze and optimize pattern performance."""
        for pattern, stats in self.pattern_performance.items():
            if stats['total'] >= 10:  # Minimum trades for analysis
                success_rate = stats['successful'] / stats['total']
                recent_reliability = np.mean(stats['recent_reliability'])
                
                if success_rate < self.min_pattern_reliability:
                    self.alerts.append({
                        'type': 'PATTERN_ALERT',
                        'message': f'Pattern {pattern} below minimum reliability: {success_rate:.2%}',
                        'suggested_action': 'Consider increasing pattern threshold'
                    })
                    
                if recent_reliability < success_rate - 0.1:
                    self.alerts.append({
                        'type': 'PATTERN_ALERT',
                        'message': f'Pattern {pattern} showing declining performance',
                        'suggested_action': 'Review market conditions for this pattern'
                    })

    def _analyze_session_performance(self):
        """Analyze and optimize session performance."""
        for session, stats in self.session_performance.items():
            if stats['total'] >= 5:  # Minimum trades for analysis
                success_rate = stats['successful'] / stats['total']
                
                if success_rate < self.min_session_performance:
                    self.alerts.append({
                        'type': 'SESSION_ALERT',
                        'message': f'Session {session} below minimum performance: {success_rate:.2%}',
                        'suggested_action': 'Consider increasing criteria for this session'
                    })

    def _check_alert_conditions(self):
        """Check for alert conditions."""
        if len(self.trade_history) >= 3:
            recent_trades = self.trade_history[-3:]
            if all(not trade.success for trade in recent_trades):
                self.alerts.append({
                    'type': 'CONSECUTIVE_LOSSES',
                    'message': 'Three consecutive losing trades detected',
                    'suggested_action': 'Pause trading and review market conditions'
                })

        # Calculate current drawdown
        if len(self.trade_history) >= 2:
            profits = [t.profit_loss for t in self.trade_history]
            cumulative = np.cumsum(profits)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative) / peak
            
            if np.max(drawdown) > self.max_drawdown:
                self.alerts.append({
                    'type': 'DRAWDOWN_ALERT',
                    'message': f'Maximum drawdown exceeded: {np.max(drawdown):.2%}',
                    'suggested_action': 'Consider reducing position sizes or increasing criteria'
                })

    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary."""
        if not self.trade_history:
            return {}

        recent_trades = self.trade_history[-50:]  # Last 50 trades
        total_trades = len(recent_trades)
        successful_trades = sum(1 for t in recent_trades if t.success)
        
        return {
            'overall_win_rate': successful_trades / total_trades if total_trades > 0 else 0,
            'pattern_reliability': {
                pattern: {
                    'success_rate': stats['successful'] / stats['total'],
                    'avg_profit': stats['avg_profit'],
                    'recent_reliability': np.mean(stats['recent_reliability'])
                }
                for pattern, stats in self.pattern_performance.items()
                if stats['total'] > 0
            },
            'session_performance': {
                session: {
                    'success_rate': stats['successful'] / stats['total'],
                    'avg_profit': stats['avg_profit']
                }
                for session, stats in self.session_performance.items()
                if stats['total'] > 0
            },
            'market_conditions': {
                condition: {
                    'success_rate': stats['successful'] / stats['total'],
                    'avg_profit': stats['avg_profit']
                }
                for condition, stats in self.market_condition_stats.items()
                if stats['total'] > 0
            },
            'alerts': self.alerts[-5:]  # Last 5 alerts
        }

    def get_optimization_suggestions(self) -> List[Dict]:
        """Get suggestions for trading optimization."""
        suggestions = []
        
        # Analyze pattern performance
        for pattern, stats in self.pattern_performance.items():
            if stats['total'] >= 10:
                success_rate = stats['successful'] / stats['total']
                if success_rate < self.min_pattern_reliability:
                    suggestions.append({
                        'type': 'PATTERN',
                        'target': pattern,
                        'current_performance': success_rate,
                        'suggestion': 'Increase pattern validation criteria',
                        'priority': 'HIGH' if success_rate < 0.7 else 'MEDIUM'
                    })

        # Analyze session performance
        for session, stats in self.session_performance.items():
            if stats['total'] >= 5:
                success_rate = stats['successful'] / stats['total']
                if success_rate < self.min_session_performance:
                    suggestions.append({
                        'type': 'SESSION',
                        'target': session,
                        'current_performance': success_rate,
                        'suggestion': 'Review session trading criteria',
                        'priority': 'HIGH' if success_rate < 0.65 else 'MEDIUM'
                    })

        # Analyze market conditions
        for condition, stats in self.market_condition_stats.items():
            if stats['total'] >= 5:
                success_rate = stats['successful'] / stats['total']
                if success_rate < 0.75:
                    suggestions.append({
                        'type': 'MARKET_CONDITION',
                        'target': condition,
                        'current_performance': success_rate,
                        'suggestion': 'Adjust criteria for this market condition',
                        'priority': 'MEDIUM'
                    })

        return suggestions
