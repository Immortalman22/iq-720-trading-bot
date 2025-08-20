"""
Real-time Signal Optimizer
Ensures fast and reliable signal generation for live trading conditions.
"""
from typing import Dict, Optional, List
from datetime import datetime
import numpy as np
from dataclasses import dataclass

@dataclass
class RealTimeMetrics:
    execution_time: float
    signal_lag: float
    data_freshness: float

class RealTimeOptimizer:
    def __init__(self):
        self.max_acceptable_delay = 0.5  # Maximum acceptable delay in seconds
        self.performance_history: List[RealTimeMetrics] = []
        self.buffer_size = 100  # Keep last 100 candles max
        self.min_required_data = 20  # Minimum candles needed for reliable signals
        
    def optimize_data_buffer(self, data_buffer: List[float]) -> List[float]:
        """Keep only essential data points for real-time analysis."""
        if len(data_buffer) > self.buffer_size:
            return data_buffer[-self.buffer_size:]
        return data_buffer

    def validate_data_freshness(self, timestamp: datetime) -> bool:
        """Ensure data is fresh enough for trading decisions."""
        delay = (datetime.now() - timestamp).total_seconds()
        return delay <= self.max_acceptable_delay

    def check_signal_viability(self, 
                             signal_time: datetime,
                             current_price: float,
                             execution_latency: float) -> bool:
        """Check if a signal is still valid given real-world execution times."""
        # If execution would take too long, reject signal
        if execution_latency > self.max_acceptable_delay:
            return False
            
        # If signal is too old, reject it
        if (datetime.now() - signal_time).total_seconds() > self.max_acceptable_delay:
            return False
            
        return True

    def get_optimal_timeframe(self, execution_speed: float) -> int:
        """Determine optimal timeframe based on execution capabilities."""
        if execution_speed < 0.1:  # Very fast execution
            return 1  # 1-minute timeframe
        elif execution_speed < 0.3:  # Moderate execution
            return 2  # 2-minute timeframe
        else:  # Slower execution
            return 5  # 5-minute timeframe

    def optimize_indicator_settings(self, execution_time: float) -> Dict:
        """Optimize technical indicator settings for real-time performance."""
        # Adjust indicator periods based on execution speed
        if execution_time < 0.1:  # Fast execution
            return {
                'rsi_period': 14,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'bb_period': 20
            }
        else:  # Slower execution
            return {
                'rsi_period': 7,  # Faster RSI
                'macd_fast': 8,   # Faster MACD
                'macd_slow': 17,
                'macd_signal': 9,
                'bb_period': 15    # Faster Bollinger Bands
            }

    def should_skip_calculation(self, 
                              last_calc_time: datetime,
                              min_interval: float = 0.1) -> bool:
        """Determine if we should skip calculations to maintain performance."""
        time_since_last = (datetime.now() - last_calc_time).total_seconds()
        return time_since_last < min_interval

    def log_performance_metrics(self, metrics: RealTimeMetrics):
        """Log performance metrics for monitoring."""
        self.performance_history.append(metrics)
        if len(self.performance_history) > 1000:
            self.performance_history.pop(0)

    def get_performance_stats(self) -> Dict:
        """Get performance statistics for monitoring."""
        if not self.performance_history:
            return {}
            
        exec_times = [m.execution_time for m in self.performance_history]
        signal_lags = [m.signal_lag for m in self.performance_history]
        
        return {
            'avg_execution_time': np.mean(exec_times),
            'max_execution_time': np.max(exec_times),
            'avg_signal_lag': np.mean(signal_lags),
            'max_signal_lag': np.max(signal_lags),
            'performance_rating': 'good' if np.mean(exec_times) < 0.1 else 'warning'
        }
