"""
Trade execution module with integrated risk management.
Handles the execution of trades based on signals while applying dynamic risk management.
"""
from typing import Optional, Dict
from datetime import datetime
import logging
from dataclasses import dataclass
from .utils.dynamic_risk_manager import DynamicRiskManager, RiskParameters
from .utils.trade_tracker import TradeTracker, Trade
from .utils.market_analyzer import MarketAnalyzer
from .utils.logger import TradingBotLogger
from .utils.extended_edge_case_handler import ExtendedEdgeCaseHandler, DataAnomalyReport
from .signal_generator import Signal

@dataclass
class ExecutionParameters:
    """Parameters for trade execution."""
    min_confidence: float = 0.6
    max_daily_trades: int = 10
    min_time_between_trades: int = 15  # minutes
    recovery_mode_threshold: int = 3  # consecutive losses
    enable_recovery_mode: bool = True
    base_trade_size: float = 1.0
    
    # Edge case handling parameters
    edge_case_min_confidence: float = 0.7  # Minimum confidence for edge case corrections
    max_consecutive_anomalies: int = 5  # Maximum allowed consecutive anomalies
    reject_high_severity_anomalies: bool = True  # Reject trades with high severity anomalies
    enable_data_correction: bool = True  # Enable automatic data corrections

class TradeExecutor:
    """
    Handles trade execution with dynamic risk management.
    Integrates signal validation, risk management, and trade tracking.
    """
    def __init__(self, 
                 trade_tracker: TradeTracker,
                 market_analyzer: MarketAnalyzer,
                 execution_params: Optional[ExecutionParameters] = None,
                 risk_params: Optional[RiskParameters] = None):
        """
        Initialize the trade executor.
        
        Args:
            trade_tracker: Trade tracking system
            market_analyzer: Market analysis system
            execution_params: Optional execution parameters
            risk_params: Optional risk parameters
        """
        self.logger = TradingBotLogger().logger
        self.trade_tracker = trade_tracker
        self.market_analyzer = market_analyzer
        self.params = execution_params or ExecutionParameters()
        
        # Initialize edge case handler
        self.edge_case_handler = ExtendedEdgeCaseHandler()
        self.edge_case_handler.max_consecutive_anomalies = self.params.max_consecutive_anomalies
        
        # Initialize risk manager
        self.risk_manager = DynamicRiskManager(
            trade_tracker=trade_tracker,
            market_analyzer=market_analyzer,
            base_params=risk_params
        )
        
        # State tracking
        self.active_trades: Dict[str, Trade] = {}
        self.last_trade_time: Optional[datetime] = None
        self.daily_trade_count = 0
        self.consecutive_losses = 0
        self.daily_stats_reset_time = None

    def process_signal(self, signal: Signal) -> Optional[Trade]:
        """
        Process a trading signal and execute if conditions are met.
        
        Args:
            signal: The trading signal to process
            
        Returns:
            Executed trade or None if signal was rejected
        """
        try:
            # Reset daily stats if needed
            self._check_daily_reset(signal.timestamp)
            
            # Validate and process signal data for anomalies
            signal_data = {
                'timestamp': signal.timestamp,
                'close': float(signal.indicators.get('close', 0)),
                'volume': float(signal.indicators.get('volume', 0)),
                'tick_count': int(signal.indicators.get('tick_count', 0)),
                'bids': signal.indicators.get('bids', []),
                'asks': signal.indicators.get('asks', [])
            }
            
            anomaly_report = self.edge_case_handler.validate_data(signal_data)
            
            # Handle anomalies based on settings
            if anomaly_report.anomalies:
                if anomaly_report.severity == "high" and self.params.reject_high_severity_anomalies:
                    self.logger.warning(f"Signal rejected - High severity anomalies detected: {anomaly_report.anomalies}")
                    return None
                    
                if anomaly_report.confidence < self.params.edge_case_min_confidence:
                    self.logger.warning(f"Signal rejected - Low confidence in data corrections: {anomaly_report.confidence}")
                    return None
                    
                if self.params.enable_data_correction and anomaly_report.corrected_data:
                    # Update signal with corrected data
                    signal.indicators.update(anomaly_report.corrected_data)
                    self.logger.info(f"Applied data corrections for anomalies: {anomaly_report.anomalies}")
            
            # Validate signal
            if not self._validate_signal(signal):
                return None
            
            # Check if we can trade
            if not self._can_trade(signal):
                return None
            
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                symbol=signal.asset,
                signal_strength=signal.confidence,
                entry_price=float(signal.indicators.get('entry_price', 0))
            )
            
            if position_size <= 0:
                self.logger.info(f"Signal rejected - Risk limits reached for {signal.asset}")
                return None
            
            # Create and execute trade
            trade = self._create_trade(signal, position_size)
            if not trade:
                return None
            
            # Update risk state
            self.risk_manager.update_risk_state(
                symbol=trade.symbol,
                position_size=trade.position_size,
                entry_price=trade.entry_price
            )
            
            # Update state
            self._update_state_after_trade(trade)
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error processing signal: {e}")
            return None

    def close_trade(self, 
                   trade_id: str, 
                   exit_price: float,
                   exit_time: datetime) -> Optional[Trade]:
        """
        Close an active trade.
        
        Args:
            trade_id: ID of the trade to close
            exit_price: Exit price
            exit_time: Exit timestamp
            
        Returns:
            Closed trade or None if trade not found
        """
        try:
            if trade_id not in self.active_trades:
                self.logger.warning(f"Trade {trade_id} not found in active trades")
                return None
            
            trade = self.active_trades[trade_id]
            
            # Update trade
            trade.exit_price = exit_price
            trade.exit_time = exit_time
            trade.status = "closed"
            trade.profit_loss = self._calculate_pnl(trade)
            
            # Release risk allocation
            self.risk_manager.release_risk(trade.symbol)
            
            # Update consecutive losses tracking
            if trade.profit_loss < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0
            
            # Remove from active trades
            del self.active_trades[trade_id]
            
            return trade
            
        except Exception as e:
            self.logger.error(f"Error closing trade: {e}")
            return None

    def _validate_signal(self, signal: Signal) -> bool:
        """Validate if a signal meets execution criteria."""
        try:
            # Check confidence
            if signal.confidence < self.params.min_confidence:
                self.logger.info(
                    f"Signal rejected - Low confidence: {signal.confidence:.2f}"
                )
                return False
            
            # Check market conditions
            is_favorable, confidence, reason = (
                self.market_analyzer.check_market_conditions(signal.asset)
            )
            if not is_favorable:
                self.logger.info(
                    f"Signal rejected - Unfavorable market conditions: {reason}"
                )
                return False
            
            # Check if asset already has active trade
            active_symbols = {
                t.symbol for t in self.active_trades.values()
                if t.status == "open"
            }
            if signal.asset in active_symbols:
                self.logger.info(
                    f"Signal rejected - Active trade exists for {signal.asset}"
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating signal: {e}")
            return False

    def _can_trade(self, signal: Signal) -> bool:
        """Check if we can take new trades."""
        try:
            # Check daily trade limit
            if self.daily_trade_count >= self.params.max_daily_trades:
                self.logger.info("Signal rejected - Daily trade limit reached")
                return False
            
            # Check minimum time between trades
            if self.last_trade_time and signal.timestamp:
                time_diff = signal.timestamp - self.last_trade_time
                minutes_since_last = time_diff.total_seconds() / 60
                
                if minutes_since_last < self.params.min_time_between_trades:
                    self.logger.info(
                        f"Signal rejected - Too soon after last trade "
                        f"({minutes_since_last:.1f} min)"
                    )
                    return False
            
            # Check recovery mode
            if (self.params.enable_recovery_mode and 
                self.consecutive_losses >= self.params.recovery_mode_threshold):
                self.logger.info(
                    f"Signal rejected - In recovery mode after "
                    f"{self.consecutive_losses} consecutive losses"
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking trade conditions: {e}")
            return False

    def _create_trade(self, 
                     signal: Signal, 
                     position_size: float) -> Optional[Trade]:
        """Create a new trade from a signal."""
        try:
            entry_price = float(signal.indicators.get('entry_price', 0))
            if entry_price <= 0:
                self.logger.error("Invalid entry price in signal")
                return None
            
            trade = Trade(
                id=f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=signal.asset,
                entry_price=entry_price,
                entry_time=signal.timestamp,
                position_size=position_size,
                direction=signal.direction.lower(),
                status="open",
                tags=[f"confidence_{signal.confidence:.2f}"],
                metadata={
                    "signal_indicators": signal.indicators,
                    "expiry_minutes": signal.expiry_minutes
                }
            )
            
            self.active_trades[trade.id] = trade
            return trade
            
        except Exception as e:
            self.logger.error(f"Error creating trade: {e}")
            return None

    def _update_state_after_trade(self, trade: Trade) -> None:
        """Update internal state after executing a trade."""
        try:
            self.last_trade_time = datetime.now()  # Use current time instead of entry_time
            self.daily_trade_count += 1
            
        except Exception as e:
            self.logger.error(f"Error updating state after trade: {e}")

    def _check_daily_reset(self, current_time: datetime) -> None:
        """Reset daily tracking if needed."""
        try:
            if not self.daily_stats_reset_time:
                self.daily_stats_reset_time = current_time
                return
                
            if current_time.date() > self.daily_stats_reset_time.date():
                self.daily_trade_count = 0
                self.daily_stats_reset_time = current_time
                
        except Exception as e:
            self.logger.error(f"Error checking daily reset: {e}")

    def _calculate_pnl(self, trade: Trade) -> float:
        """Calculate profit/loss for a trade."""
        try:
            if not trade.exit_price:
                return 0.0
                
            # For forex pairs, convert price difference to pips
            price_diff = (
                (trade.exit_price - trade.entry_price) * 10000
                if trade.direction == "buy"
                else (trade.entry_price - trade.exit_price) * 10000
            )
            
            # Each pip is worth 0.0001 * position_size * 10 for standard forex
            return price_diff * trade.position_size / 10
            
        except Exception as e:
            self.logger.error(f"Error calculating PnL: {e}")
            return 0.0
