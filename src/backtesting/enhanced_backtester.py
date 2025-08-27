"""
Enhanced backtesting framework for IQ-720 Trading Bot.
Supports comprehensive historical analysis from 2013 to present.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
import os
import pickle
import json
from pathlib import Path
import pytz
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox
from scipy import stats
from tqdm import tqdm

# Import trading modules
from ..utils.enhanced_signal_generator import enhanced_signal_generator, EnhancedSignal
from ..utils.pair_specific_settings import pair_settings
from ..utils.time_logic import TimeLogic
from ..utils.improved_indicators import improved_indicators

# Data download and handling
import yfinance as yf
import requests
import zipfile
import io

class HistoricalDataManager:
    """
    Manages historical data acquisition and preprocessing for backtesting.
    Supports multiple data sources including Forex, Crypto, and Stocks.
    """
    
    def __init__(self, data_dir: str = 'data/historical'):
        self.logger = logging.getLogger(__name__)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Define timeframes
        self.timeframes = {
            '1m': '1 minute',
            '5m': '5 minutes',
            '15m': '15 minutes',
            '30m': '30 minutes',
            '1h': '1 hour', 
            '4h': '4 hours',
            'D': '1 day'
        }
        
        # Define available currency pairs
        self.forex_pairs = [
            'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 
            'USDCAD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY'
        ]
        
        self.crypto_pairs = [
            'BTC-USD', 'ETH-USD', 'XRP-USD', 'LTC-USD', 'BCH-USD'
        ]
        
    def download_forex_data(self, pair: str, start_date: str, end_date: str, 
                          timeframe: str = 'H1') -> Optional[pd.DataFrame]:
        """
        Download Forex historical data from Dukascopy or similar source.
        
        Args:
            pair: Currency pair (e.g. 'EURUSD')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timeframe: Timeframe (e.g. 'H1' for hourly)
            
        Returns:
            DataFrame with OHLCV data or None if download fails
        """
        try:
            # Standardize pair format
            pair = pair.replace('/', '')
            
            # Create file path for cached data
            file_path = self.data_dir / f"{pair}_{timeframe}_{start_date}_{end_date}.csv"
            
            # Check if data already exists
            if file_path.exists():
                self.logger.info(f"Loading cached data for {pair} from {file_path}")
                return pd.read_csv(file_path, index_col=0, parse_dates=True)
                
            # For demo purposes, we'll use yfinance as a data source
            # In production, you'd want to use a proper Forex data API
            self.logger.info(f"Downloading {pair} data from {start_date} to {end_date}")
            
            # Convert to yfinance format
            yf_pair = f"{pair[0:3]}{pair[3:6]}=X"
            
            # Download data
            data = yf.download(
                yf_pair,
                start=start_date,
                end=end_date,
                interval=self._convert_timeframe_to_yf(timeframe)
            )
            
            # Check if data is empty
            if data.empty:
                self.logger.warning(f"No data retrieved for {pair}")
                return None
                
            # Save to cache
            data.to_csv(file_path)
            
            self.logger.info(f"Successfully downloaded {len(data)} candles for {pair}")
            return data
            
        except Exception as e:
            self.logger.error(f"Error downloading Forex data: {e}")
            return None
            
    def download_bulk_forex_data(self, pairs: List[str], start_date: str, end_date: str, 
                               timeframe: str = 'H1') -> Dict[str, pd.DataFrame]:
        """
        Download historical data for multiple pairs.
        
        Args:
            pairs: List of currency pairs
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timeframe: Timeframe (e.g. 'H1' for hourly)
            
        Returns:
            Dictionary mapping pairs to their DataFrames
        """
        results = {}
        
        for pair in tqdm(pairs, desc="Downloading historical data"):
            data = self.download_forex_data(pair, start_date, end_date, timeframe)
            if data is not None:
                results[pair] = data
                
        return results
    
    def _convert_timeframe_to_yf(self, timeframe: str) -> str:
        """Convert timeframe to yfinance format"""
        mapping = {
            'M1': '1m',
            'M5': '5m',
            'M15': '15m',
            'M30': '30m',
            'H1': '1h',
            'H4': '4h',
            'D1': '1d',
            'W1': '1wk',
            'MN': '1mo'
        }
        return mapping.get(timeframe, '1h')
    
    def resample_data(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Resample OHLCV data to a different timeframe.
        
        Args:
            df: DataFrame with OHLCV data
            timeframe: Target timeframe (e.g. '1H', '4H', '1D')
            
        Returns:
            Resampled DataFrame
        """
        # Make sure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            
        # Resample
        resampled = df.resample(timeframe).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        return resampled
    
    def merge_datasets(self, dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Merge multiple pair datasets into a single multi-pair DataFrame.
        
        Args:
            dfs: Dictionary mapping pairs to DataFrames
            
        Returns:
            Multi-pair DataFrame with hierarchical columns
        """
        merged = None
        
        for pair, df in dfs.items():
            # Create multi-index columns with pair as top level
            pair_df = df.copy()
            pair_df.columns = pd.MultiIndex.from_product([[pair], pair_df.columns])
            
            if merged is None:
                merged = pair_df
            else:
                # Join on index (timestamp)
                merged = merged.join(pair_df, how='outer')
                
        return merged
    
    def split_data(self, df: pd.DataFrame, train_ratio: float = 0.7, 
                 val_ratio: float = 0.15) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split data into training, validation and test sets.
        
        Args:
            df: DataFrame with OHLCV data
            train_ratio: Proportion for training set
            val_ratio: Proportion for validation set
            
        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        # Calculate split indices
        n = len(df)
        train_idx = int(n * train_ratio)
        val_idx = train_idx + int(n * val_ratio)
        
        # Split the data
        train_df = df.iloc[:train_idx]
        val_df = df.iloc[train_idx:val_idx]
        test_df = df.iloc[val_idx:]
        
        return train_df, val_df, test_df
        
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create additional features for backtesting.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with additional features
        """
        # Make a copy to avoid modifying the original
        result = df.copy()
        
        # Basic features
        result['returns'] = result['Close'].pct_change()
        result['log_returns'] = np.log(result['Close'] / result['Close'].shift(1))
        result['volatility'] = result['log_returns'].rolling(20).std() * np.sqrt(252)
        result['range'] = (result['High'] - result['Low']) / result['Close'].shift(1)
        
        # Time-based features
        result['hour'] = result.index.hour
        result['day_of_week'] = result.index.dayofweek
        result['month'] = result.index.month
        
        # Add market session info
        time_logic = TimeLogic()
        
        # Apply market session logic
        result['market_session'] = result.index.map(
            lambda dt: ','.join(time_logic.get_current_session(dt)) 
            if time_logic.get_current_session(dt) else 'None'
        )
        
        result['market_type'] = result.index.map(
            lambda dt: time_logic.get_current_market_type(dt)
        )
        
        return result

class EnhancedBacktester:
    """
    Enhanced backtesting engine with comprehensive analysis capabilities.
    """
    
    def __init__(self, data_dir: str = 'data/backtest_results'):
        self.logger = logging.getLogger(__name__)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize components
        self.data_manager = HistoricalDataManager()
        self.time_logic = TimeLogic()
        
        # Performance tracking
        self.trades = []
        self.equity_curve = None
        self.performance_metrics = {}
        self.pair_performance = {}
        
        # Settings
        self.commission = 0.0002  # 2 pips per trade (0.02%)
        self.slippage = 0.0001    # 1 pip slippage (0.01%)
        self.initial_balance = 10000
        
    def run_backtest(self, data: Union[pd.DataFrame, Dict[str, pd.DataFrame]], 
                   start_date: Optional[str] = None, 
                   end_date: Optional[str] = None,
                   config: Optional[Dict] = None) -> Dict:
        """
        Run a backtest on historical data.
        
        Args:
            data: DataFrame or dict of DataFrames with OHLCV data
            start_date: Start date for backtest (if None, use all data)
            end_date: End date for backtest (if None, use all data)
            config: Configuration dict for backtest settings
            
        Returns:
            Dictionary with backtest results
        """
        self.logger.info("Starting backtest...")
        
        # Initialize configuration
        self._initialize_backtest(config)
        
        # Convert dates to datetime if provided
        if start_date:
            start_date = pd.to_datetime(start_date)
        if end_date:
            end_date = pd.to_datetime(end_date)
            
        # Reset previous results
        self.trades = []
        self.equity_curve = None
        
        # Process data based on type
        if isinstance(data, dict):
            # Multi-pair backtest
            results = self._run_multi_pair_backtest(data, start_date, end_date)
        else:
            # Single-pair backtest
            pair = config.get('pair', 'EURUSD')
            results = self._run_single_pair_backtest(data, pair, start_date, end_date)
            
        # Calculate performance metrics
        self._calculate_performance_metrics()
        
        # Generate equity curve
        self._generate_equity_curve()
        
        # Combine all results
        full_results = {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'metrics': self.performance_metrics,
            'pair_performance': self.pair_performance
        }
        
        self.logger.info(f"Backtest completed with {len(self.trades)} trades")
        
        return full_results
    
    def _initialize_backtest(self, config: Optional[Dict] = None):
        """Initialize backtest configuration"""
        config = config or {}
        
        # Set default settings
        self.commission = config.get('commission', 0.0002)
        self.slippage = config.get('slippage', 0.0001)
        self.initial_balance = config.get('initial_balance', 10000)
        self.risk_per_trade = config.get('risk_per_trade', 0.02)  # 2% risk
        
    def _run_single_pair_backtest(self, data: pd.DataFrame, pair: str,
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None) -> Dict:
        """Run backtest on a single pair"""
        # Filter by date if specified
        df = data.copy()
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
            
        # Initialize balance and tracking variables
        balance = self.initial_balance
        trades = []
        active_trades = []
        
        # Get pair-specific settings
        pair_config = pair_settings.get_settings(pair.replace('', '/'))
        
        # Process each candle
        for idx, (timestamp, candle) in enumerate(df.iterrows()):
            # Skip if not enough data for indicators
            if idx < 50:
                continue
                
            # Create candle data for signal generator
            candle_data = {
                'timestamp': timestamp.timestamp(),
                'open': candle['Open'],
                'high': candle['High'],
                'low': candle['Low'],
                'close': candle['Close'],
                'volume': candle['Volume'],
                'asset': pair.replace('', '/')
            }
            
            # Check if we need to close any active trades
            self._process_trade_exits(active_trades, timestamp, candle, pair)
            
            # Generate trading signal
            signal = enhanced_signal_generator.add_candle(candle_data)
            
            # Process signal if generated
            if signal and not active_trades:  # Only one trade at a time for now
                trade = self._process_signal(signal, timestamp, candle, balance, pair)
                if trade:
                    trades.append(trade)
                    active_trades.append(trade)
                    
        # Close any remaining trades at the end of the backtest
        if active_trades and len(df) > 0:
            last_timestamp = df.index[-1]
            last_candle = df.iloc[-1]
            self._process_trade_exits(active_trades, last_timestamp, last_candle, pair)
            
        # Store trades
        self.trades = trades
        
        return {'trades': trades}
    
    def _run_multi_pair_backtest(self, data_dict: Dict[str, pd.DataFrame],
                              start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None) -> Dict:
        """Run backtest on multiple pairs"""
        # Initialize balance and tracking variables
        balance = self.initial_balance
        trades = []
        active_trades = {}  # Dictionary mapping pair to active trade
        
        # Align all dataframes to the same timeframe
        aligned_data = {}
        common_index = None
        
        for pair, df in data_dict.items():
            # Filter by date if specified
            filtered_df = df.copy()
            if start_date:
                filtered_df = filtered_df[filtered_df.index >= start_date]
            if end_date:
                filtered_df = filtered_df[filtered_df.index <= end_date]
                
            aligned_data[pair] = filtered_df
            
            # Update common index
            if common_index is None:
                common_index = filtered_df.index
            else:
                common_index = common_index.intersection(filtered_df.index)
                
        # Ensure all dataframes have the same index
        for pair in aligned_data:
            aligned_data[pair] = aligned_data[pair].loc[common_index]
            
        # Process each timestamp
        for idx, timestamp in enumerate(common_index):
            if idx < 50:  # Skip first 50 candles for indicators
                continue
                
            # Process all pairs at this timestamp
            signals = []
            
            for pair, df in aligned_data.items():
                # Get candle at this timestamp
                candle = df.loc[timestamp]
                
                # Check if we need to close any active trades
                if pair in active_trades:
                    self._process_trade_exits([active_trades[pair]], timestamp, candle, pair)
                    if pair not in active_trades:  # Trade was closed
                        continue
                
                # Create candle data for signal generator
                candle_data = {
                    'timestamp': timestamp.timestamp(),
                    'open': candle['Open'],
                    'high': candle['High'],
                    'low': candle['Low'],
                    'close': candle['Close'],
                    'volume': candle['Volume'],
                    'asset': pair.replace('', '/')
                }
                
                # Generate trading signal
                signal = enhanced_signal_generator.add_candle(candle_data)
                
                # Add signal to list if generated
                if signal:
                    signals.append((pair, signal, candle))
                    
            # Rank and filter signals
            if signals:
                ranked_signals = self._rank_and_filter_signals(signals)
                
                # Process top signals
                for pair, signal, candle in ranked_signals:
                    if pair not in active_trades:  # Only one trade per pair
                        trade = self._process_signal(signal, timestamp, candle, balance, pair)
                        if trade:
                            trades.append(trade)
                            active_trades[pair] = trade
                            
        # Close any remaining trades at the end of the backtest
        for pair, trade in list(active_trades.items()):
            if pair in aligned_data and len(aligned_data[pair]) > 0:
                last_timestamp = aligned_data[pair].index[-1]
                last_candle = aligned_data[pair].iloc[-1]
                self._process_trade_exits([trade], last_timestamp, last_candle, pair)
                
        # Store trades
        self.trades = trades
        
        return {'trades': trades}
    
    def _process_signal(self, signal, timestamp, candle, balance, pair):
        """Process a trading signal and create a trade if valid"""
        # Check if we should take this trade
        if not self._validate_trade_conditions(signal, timestamp, pair):
            return None
            
        # Calculate position size based on risk
        risk_amount = balance * self.risk_per_trade
        
        # Calculate entry price (with slippage)
        if signal.direction == "BUY":
            entry_price = candle['Ask'] if 'Ask' in candle else candle['Close'] * (1 + self.slippage)
        else:  # SELL
            entry_price = candle['Bid'] if 'Bid' in candle else candle['Close'] * (1 - self.slippage)
            
        # Create trade object
        trade = {
            'id': len(self.trades) + 1,
            'pair': pair,
            'direction': signal.direction,
            'entry_time': timestamp,
            'entry_price': entry_price,
            'position_size': risk_amount / (0.01 * entry_price),  # Simplified position sizing
            'stop_loss': None,  # Will be set based on ATR or fixed risk
            'take_profit': None,  # Will be set based on RR ratio
            'exit_time': None,
            'exit_price': None,
            'profit_loss': None,
            'profit_pips': None,
            'status': 'OPEN',
            'signal_strength': signal.strength_score,
            'session': self.time_logic.get_current_session(timestamp)
        }
        
        # Set stop loss and take profit
        self._set_trade_risk_parameters(trade, candle)
        
        return trade
    
    def _process_trade_exits(self, trades, timestamp, candle, pair):
        """Process potential exits for active trades"""
        for trade in list(trades):
            if trade['pair'] != pair:
                continue
                
            # Check if we hit stop loss or take profit
            if trade['direction'] == "BUY":
                # Check stop loss
                if trade['stop_loss'] >= candle['Low']:
                    self._close_trade(trade, timestamp, trade['stop_loss'], 'SL')
                    trades.remove(trade)
                    continue
                    
                # Check take profit
                if trade['take_profit'] <= candle['High']:
                    self._close_trade(trade, timestamp, trade['take_profit'], 'TP')
                    trades.remove(trade)
                    continue
                    
            else:  # SELL
                # Check stop loss
                if trade['stop_loss'] <= candle['High']:
                    self._close_trade(trade, timestamp, trade['stop_loss'], 'SL')
                    trades.remove(trade)
                    continue
                    
                # Check take profit
                if trade['take_profit'] >= candle['Low']:
                    self._close_trade(trade, timestamp, trade['take_profit'], 'TP')
                    trades.remove(trade)
                    continue
    
    def _close_trade(self, trade, timestamp, price, reason):
        """Close a trade and calculate profit/loss"""
        # Calculate exit price with slippage
        if trade['direction'] == "BUY":
            exit_price = price * (1 - self.slippage)
        else:  # SELL
            exit_price = price * (1 + self.slippage)
            
        # Calculate profit/loss
        if trade['direction'] == "BUY":
            profit_pips = (exit_price - trade['entry_price']) / 0.0001
            profit_loss = profit_pips * 0.0001 * trade['position_size'] - self.commission
        else:  # SELL
            profit_pips = (trade['entry_price'] - exit_price) / 0.0001
            profit_loss = profit_pips * 0.0001 * trade['position_size'] - self.commission
            
        # Update trade
        trade['exit_time'] = timestamp
        trade['exit_price'] = exit_price
        trade['profit_loss'] = profit_loss
        trade['profit_pips'] = profit_pips
        trade['status'] = 'CLOSED'
        trade['exit_reason'] = reason
        
    def _validate_trade_conditions(self, signal, timestamp, pair):
        """Validate if we should take this trade based on various conditions"""
        # Check time-based conditions
        sessions = self.time_logic.get_current_session(timestamp)
        market_type = self.time_logic.get_current_market_type(timestamp)
        
        # Only trade forex during active sessions
        if market_type == 'forex' and not sessions:
            return False
            
        # Check for recent trades on this pair
        recent_trades = [t for t in self.trades[-20:] if t['pair'] == pair]
        if recent_trades:
            # Don't take another trade if recent one was a loss
            last_trade = recent_trades[-1]
            if last_trade['status'] == 'CLOSED' and last_trade['profit_loss'] < 0:
                # Check if we've had too many consecutive losses
                consecutive_losses = 0
                for t in reversed(recent_trades):
                    if t['profit_loss'] < 0:
                        consecutive_losses += 1
                    else:
                        break
                        
                if consecutive_losses >= 3:  # Don't trade after 3 consecutive losses
                    return False
            
            # Don't take another trade too soon after previous one
            if last_trade['exit_time'] and (timestamp - last_trade['exit_time']).total_seconds() < 3600:
                return False
                
        # Check signal strength
        if signal.strength_score < 65:  # Require stronger signals in backtest
            return False
            
        return True
    
    def _set_trade_risk_parameters(self, trade, candle):
        """Set stop loss and take profit levels for a trade"""
        # Calculate ATR-based stop loss
        atr = candle.get('ATR', (candle['High'] - candle['Low']) * 0.5)  # Use half range if ATR not available
        
        if trade['direction'] == "BUY":
            # Stop loss below entry, 1.5x ATR
            trade['stop_loss'] = trade['entry_price'] - (1.5 * atr)
            # Take profit 2:1 risk-reward
            trade['take_profit'] = trade['entry_price'] + (3 * atr)
        else:  # SELL
            # Stop loss above entry, 1.5x ATR
            trade['stop_loss'] = trade['entry_price'] + (1.5 * atr)
            # Take profit 2:1 risk-reward
            trade['take_profit'] = trade['entry_price'] - (3 * atr)
    
    def _rank_and_filter_signals(self, signals):
        """Rank and filter signals from multiple pairs"""
        # Extract signal objects for ranking
        signal_objs = [s[1] for s in signals]
        
        # Use the enhanced signal generator's ranking function
        ranked_signals = enhanced_signal_generator.get_ranked_signals(signal_objs, max_signals=3)
        
        # Match back with the pair and candle data
        result = []
        for ranked in ranked_signals:
            for pair, signal, candle in signals:
                if signal is ranked:
                    result.append((pair, signal, candle))
                    break
                    
        return result
    
    def _generate_equity_curve(self):
        """Generate equity curve from trades"""
        if not self.trades:
            self.equity_curve = pd.DataFrame({
                'balance': [self.initial_balance]
            }, index=[pd.Timestamp.now()])
            return
            
        # Create a list of balance changes
        balance_changes = []
        
        # Add initial balance
        balance_changes.append({
            'timestamp': self.trades[0]['entry_time'] - pd.Timedelta(days=1),
            'change': 0,
            'balance': self.initial_balance
        })
        
        # Add each trade's profit/loss
        for trade in self.trades:
            if trade['status'] == 'CLOSED' and trade['profit_loss'] is not None:
                balance_changes.append({
                    'timestamp': trade['exit_time'],
                    'change': trade['profit_loss'],
                    'trade_id': trade['id']
                })
                
        # Sort by timestamp
        balance_changes.sort(key=lambda x: x['timestamp'])
        
        # Calculate running balance
        balance = self.initial_balance
        for change in balance_changes:
            if 'balance' not in change:
                balance += change['change']
                change['balance'] = balance
                
        # Convert to DataFrame
        self.equity_curve = pd.DataFrame(balance_changes).set_index('timestamp')
    
    def _calculate_performance_metrics(self):
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            self.performance_metrics = {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'expected_payoff': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'calmar_ratio': 0
            }
            return
            
        # Filter closed trades
        closed_trades = [t for t in self.trades if t['status'] == 'CLOSED' and t['profit_loss'] is not None]
        
        if not closed_trades:
            return
            
        # Basic metrics
        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t['profit_loss'] > 0)
        losing_trades = sum(1 for t in closed_trades if t['profit_loss'] <= 0)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t['profit_loss'] for t in closed_trades if t['profit_loss'] > 0)
        gross_loss = abs(sum(t['profit_loss'] for t in closed_trades if t['profit_loss'] <= 0))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        expected_payoff = sum(t['profit_loss'] for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        # Advanced metrics
        if self.equity_curve is not None and len(self.equity_curve) > 1:
            # Calculate returns
            self.equity_curve['returns'] = self.equity_curve['balance'].pct_change()
            
            # Sharpe ratio
            risk_free_rate = 0.02  # 2% annual risk-free rate
            excess_returns = self.equity_curve['returns'].dropna() - risk_free_rate / 252
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if len(excess_returns) > 0 else 0
            
            # Sortino ratio (downside risk only)
            negative_returns = excess_returns[excess_returns < 0]
            sortino_ratio = excess_returns.mean() / negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
            
            # Maximum drawdown
            cumulative_returns = (1 + self.equity_curve['returns'].fillna(0)).cumprod()
            running_max = cumulative_returns.cummax()
            drawdown = (cumulative_returns / running_max - 1) * 100
            max_drawdown = abs(drawdown.min())
            
            # Calmar ratio
            annual_return = (self.equity_curve['balance'].iloc[-1] / self.initial_balance) ** (252 / len(self.equity_curve)) - 1
            calmar_ratio = annual_return / (max_drawdown / 100) if max_drawdown > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0
            max_drawdown = 0
            calmar_ratio = 0
            
        # Store metrics
        self.performance_metrics = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'expected_payoff': expected_payoff,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio
        }
        
        # Calculate per-pair metrics
        self._calculate_pair_performance()
        
    def _calculate_pair_performance(self):
        """Calculate performance metrics per currency pair"""
        # Group trades by pair
        pairs = set(t['pair'] for t in self.trades)
        
        for pair in pairs:
            # Filter trades for this pair
            pair_trades = [t for t in self.trades if t['pair'] == pair and t['status'] == 'CLOSED']
            
            if not pair_trades:
                continue
                
            # Calculate metrics
            total_trades = len(pair_trades)
            winning_trades = sum(1 for t in pair_trades if t['profit_loss'] > 0)
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            gross_profit = sum(t['profit_loss'] for t in pair_trades if t['profit_loss'] > 0)
            gross_loss = abs(sum(t['profit_loss'] for t in pair_trades if t['profit_loss'] <= 0))
            
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            expected_payoff = sum(t['profit_loss'] for t in pair_trades) / total_trades if total_trades > 0 else 0
            
            # Store metrics
            self.pair_performance[pair] = {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'expected_payoff': expected_payoff
            }
    
    def monte_carlo_analysis(self, n_simulations: int = 1000) -> Dict:
        """
        Perform Monte Carlo analysis on the backtest results.
        
        Args:
            n_simulations: Number of simulations to run
            
        Returns:
            Dictionary with Monte Carlo analysis results
        """
        if not self.trades or len(self.trades) < 10:
            return {'error': 'Not enough trades for Monte Carlo analysis'}
            
        # Filter closed trades
        closed_trades = [t for t in self.trades if t['status'] == 'CLOSED' and t['profit_loss'] is not None]
        
        # Extract profit/loss from each trade
        pnl = [t['profit_loss'] for t in closed_trades]
        
        # Run simulations
        simulations = []
        
        for _ in range(n_simulations):
            # Randomly shuffle trades
            np.random.shuffle(pnl)
            
            # Calculate equity curve
            equity = np.cumsum([0] + pnl) + self.initial_balance
            
            # Calculate metrics
            final_balance = equity[-1]
            max_equity = np.maximum.accumulate(equity)
            drawdowns = (max_equity - equity) / max_equity * 100
            max_drawdown = drawdowns.max()
            
            simulations.append({
                'equity': equity,
                'final_balance': final_balance,
                'max_drawdown': max_drawdown
            })
            
        # Calculate statistics
        final_balances = [s['final_balance'] for s in simulations]
        max_drawdowns = [s['max_drawdown'] for s in simulations]
        
        # Calculate percentiles
        results = {
            'final_balance': {
                'mean': np.mean(final_balances),
                'median': np.median(final_balances),
                'std': np.std(final_balances),
                'worst_5pct': np.percentile(final_balances, 5),
                'best_5pct': np.percentile(final_balances, 95)
            },
            'max_drawdown': {
                'mean': np.mean(max_drawdowns),
                'median': np.median(max_drawdowns),
                'worst_5pct': np.percentile(max_drawdowns, 95)
            },
            'win_probability': sum(1 for b in final_balances if b > self.initial_balance) / n_simulations
        }
        
        return results
        
    def walk_forward_analysis(self, data: pd.DataFrame, window_size: int = 252, 
                            step_size: int = 63) -> Dict:
        """
        Perform walk-forward analysis on the backtest.
        
        Args:
            data: DataFrame with OHLCV data
            window_size: Size of the training window (in candles)
            step_size: Size of each step forward (in candles)
            
        Returns:
            Dictionary with walk-forward analysis results
        """
        if len(data) < window_size * 2:
            return {'error': 'Not enough data for walk-forward analysis'}
            
        # Initialize results
        results = []
        
        # Loop through the data with sliding windows
        for i in range(0, len(data) - window_size * 2, step_size):
            # Split data into in-sample and out-of-sample
            in_sample = data.iloc[i:i + window_size]
            out_sample = data.iloc[i + window_size:i + window_size * 2]
            
            # Run backtest on in-sample data
            self.run_backtest(in_sample)
            in_sample_metrics = self.performance_metrics.copy()
            
            # Run backtest on out-of-sample data
            self.run_backtest(out_sample)
            out_sample_metrics = self.performance_metrics.copy()
            
            # Store results
            results.append({
                'period_start': in_sample.index[0],
                'period_end': out_sample.index[-1],
                'in_sample': in_sample_metrics,
                'out_sample': out_sample_metrics
            })
            
        return {'periods': results}
        
    def optimize_parameters(self, data: pd.DataFrame, param_grid: Dict, 
                          target_metric: str = 'sharpe_ratio') -> Dict:
        """
        Optimize strategy parameters using grid search.
        
        Args:
            data: DataFrame with OHLCV data
            param_grid: Dictionary mapping parameter names to lists of values
            target_metric: Metric to optimize
            
        Returns:
            Dictionary with optimization results
        """
        # Generate all parameter combinations
        import itertools
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))
        
        # Initialize results
        results = []
        
        # Test each combination
        for combo in tqdm(combinations, desc="Parameter optimization"):
            params = dict(zip(param_names, combo))
            
            # Run backtest with these parameters
            self.run_backtest(data, config={'params': params})
            
            # Extract target metric
            metric_value = self.performance_metrics.get(target_metric, 0)
            
            # Store results
            results.append({
                'params': params,
                target_metric: metric_value
            })
            
        # Sort by target metric
        results.sort(key=lambda x: x[target_metric], reverse=True)
        
        return {
            'best_params': results[0]['params'],
            'best_value': results[0][target_metric],
            'all_results': results
        }
    
    def save_results(self, filename: str, results: Dict) -> str:
        """
        Save backtest results to file.
        
        Args:
            filename: Base filename (without extension)
            results: Dictionary with results
            
        Returns:
            Path to saved file
        """
        # Create filepath
        filepath = self.data_dir / f"{filename}.json"
        
        # Convert DataFrame to list for JSON serialization
        serializable_results = results.copy()
        
        if 'equity_curve' in serializable_results and isinstance(serializable_results['equity_curve'], pd.DataFrame):
            serializable_results['equity_curve'] = serializable_results['equity_curve'].reset_index().to_dict('records')
            
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, default=str)
            
        self.logger.info(f"Saved backtest results to {filepath}")
        
        return str(filepath)
    
    def load_results(self, filename: str) -> Dict:
        """
        Load backtest results from file.
        
        Args:
            filename: Base filename (without extension)
            
        Returns:
            Dictionary with results
        """
        # Create filepath
        filepath = self.data_dir / f"{filename}.json"
        
        # Check if file exists
        if not filepath.exists():
            self.logger.error(f"Results file not found: {filepath}")
            return {}
            
        # Load from file
        with open(filepath, 'r') as f:
            results = json.load(f)
            
        # Convert equity curve back to DataFrame if needed
        if 'equity_curve' in results and isinstance(results['equity_curve'], list):
            results['equity_curve'] = pd.DataFrame(results['equity_curve'])
            if 'timestamp' in results['equity_curve']:
                results['equity_curve']['timestamp'] = pd.to_datetime(results['equity_curve']['timestamp'])
                results['equity_curve'].set_index('timestamp', inplace=True)
                
        self.logger.info(f"Loaded backtest results from {filepath}")
        
        return results
        
class BacktestVisualizer:
    """
    Enhanced visualization tools for backtest results.
    """
    
    def __init__(self, output_dir: str = 'data/backtest_results'):
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
    def create_performance_dashboard(self, results: Dict, save_path: Optional[str] = None):
        """
        Create a comprehensive performance dashboard.
        
        Args:
            results: Dictionary with backtest results
            save_path: Path to save the plot (if None, display instead)
        """
        if 'equity_curve' not in results or results['equity_curve'] is None:
            self.logger.error("No equity curve data found")
            return
            
        # Set up the figure
        fig, axs = plt.subplots(3, 2, figsize=(15, 18))
        plt.subplots_adjust(hspace=0.4, wspace=0.3)
        fig.suptitle('Backtest Performance Dashboard', fontsize=16)
        
        # 1. Equity Curve
        equity_curve = results['equity_curve']
        axs[0, 0].plot(equity_curve.index, equity_curve['balance'])
        axs[0, 0].set_title('Equity Curve')
        axs[0, 0].set_xlabel('Date')
        axs[0, 0].set_ylabel('Balance')
        axs[0, 0].grid(True)
        
        # 2. Drawdown Chart
        if 'balance' in equity_curve.columns:
            # Calculate drawdown
            rolling_max = equity_curve['balance'].cummax()
            drawdown = (equity_curve['balance'] / rolling_max - 1) * 100
            
            axs[0, 1].fill_between(drawdown.index, drawdown, 0, color='red', alpha=0.3)
            axs[0, 1].set_title('Drawdown')
            axs[0, 1].set_xlabel('Date')
            axs[0, 1].set_ylabel('Drawdown %')
            axs[0, 1].grid(True)
        
        # 3. Monthly Returns Heatmap
        if 'returns' in equity_curve.columns:
            # Calculate monthly returns
            monthly_returns = equity_curve['returns'].dropna()
            monthly_returns = monthly_returns.groupby([monthly_returns.index.year, monthly_returns.index.month]).sum()
            
            # Reshape to matrix
            years = sorted(set([i[0] for i in monthly_returns.index]))
            months = range(1, 13)
            
            # Create matrix
            returns_matrix = np.zeros((len(years), 12))
            
            for i, year in enumerate(years):
                for j, month in enumerate(months):
                    if (year, month) in monthly_returns.index:
                        returns_matrix[i, j] = monthly_returns[(year, month)] * 100
            
            # Create heatmap
            sns.heatmap(returns_matrix, ax=axs[1, 0], 
                      cmap='RdYlGn', center=0, 
                      xticklabels=['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'],
                      yticklabels=years)
            axs[1, 0].set_title('Monthly Returns (%)')
            axs[1, 0].set_xlabel('Month')
            axs[1, 0].set_ylabel('Year')
        
        # 4. Trade Results Distribution
        if 'trades' in results and results['trades']:
            profits = [t['profit_loss'] for t in results['trades'] if t['status'] == 'CLOSED']
            if profits:
                axs[1, 1].hist(profits, bins=50, alpha=0.75)
                axs[1, 1].set_title('Trade Profit/Loss Distribution')
                axs[1, 1].set_xlabel('Profit/Loss')
                axs[1, 1].set_ylabel('Frequency')
                axs[1, 1].grid(True)
        
        # 5. Performance Metrics Table
        if 'metrics' in results:
            metrics = results['metrics']
            metrics_text = "\n".join([
                f"Total Trades: {metrics.get('total_trades', 0)}",
                f"Win Rate: {metrics.get('win_rate', 0):.2%}",
                f"Profit Factor: {metrics.get('profit_factor', 0):.2f}",
                f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}",
                f"Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%",
                f"Sortino Ratio: {metrics.get('sortino_ratio', 0):.2f}",
                f"Calmar Ratio: {metrics.get('calmar_ratio', 0):.2f}"
            ])
            axs[2, 0].axis('off')
            axs[2, 0].text(0.1, 0.5, metrics_text, fontsize=12)
            axs[2, 0].set_title('Performance Metrics')
        
        # 6. Pair Performance Comparison
        if 'pair_performance' in results:
            pair_perf = results['pair_performance']
            pairs = list(pair_perf.keys())
            win_rates = [pair_perf[p]['win_rate'] for p in pairs]
            
            axs[2, 1].bar(pairs, win_rates)
            axs[2, 1].set_title('Win Rate by Currency Pair')
            axs[2, 1].set_xlabel('Currency Pair')
            axs[2, 1].set_ylabel('Win Rate')
            axs[2, 1].set_ylim([0, 1])
            axs[2, 1].grid(True)
            plt.setp(axs[2, 1].xaxis.get_majorticklabels(), rotation=45)
        
        # Save or show
        if save_path:
            save_file = self.output_dir / save_path
            plt.savefig(save_file, dpi=300, bbox_inches='tight')
            self.logger.info(f"Performance dashboard saved to {save_file}")
        else:
            plt.tight_layout()
            plt.show()
            
    def create_trade_analysis_report(self, results: Dict, save_path: Optional[str] = None):
        """
        Create detailed trade analysis report.
        
        Args:
            results: Dictionary with backtest results
            save_path: Path to save the plot (if None, display instead)
        """
        if 'trades' not in results or not results['trades']:
            self.logger.error("No trade data found")
            return
            
        # Convert trades to DataFrame
        trades = pd.DataFrame(results['trades'])
        
        # Filter closed trades
        closed_trades = trades[trades['status'] == 'CLOSED'].copy()
        
        if closed_trades.empty:
            self.logger.error("No closed trades found")
            return
            
        # Calculate trade duration
        closed_trades['duration'] = (closed_trades['exit_time'] - closed_trades['entry_time']).dt.total_seconds() / 3600  # hours
        
        # Set up the figure
        fig, axs = plt.subplots(2, 2, figsize=(15, 12))
        plt.subplots_adjust(hspace=0.3, wspace=0.3)
        fig.suptitle('Trade Analysis Report', fontsize=16)
        
        # 1. Trade Results by Direction
        direction_grouped = closed_trades.groupby('direction')['profit_loss'].agg(['count', 'mean', 'sum'])
        direction_grouped['win_rate'] = closed_trades[closed_trades['profit_loss'] > 0].groupby('direction')['profit_loss'].count() / direction_grouped['count']
        
        colors = ['green' if x > 0 else 'red' for x in direction_grouped['sum']]
        axs[0, 0].bar(direction_grouped.index, direction_grouped['sum'], color=colors)
        axs[0, 0].set_title('Profit/Loss by Direction')
        axs[0, 0].set_xlabel('Direction')
        axs[0, 0].set_ylabel('Total Profit/Loss')
        
        for i, d in enumerate(direction_grouped.index):
            axs[0, 0].annotate(f"Win: {direction_grouped.loc[d, 'win_rate']:.1%}", 
                            xy=(i, direction_grouped.loc[d, 'sum']),
                            xytext=(0, 10), textcoords='offset points',
                            ha='center')
        
        # 2. Trade Results by Trading Session
        if 'session' in closed_trades.columns:
            # Convert session list to string if needed
            if closed_trades['session'].apply(type).eq(list).any():
                closed_trades['session_str'] = closed_trades['session'].apply(lambda x: ','.join(x) if x else 'None')
            else:
                closed_trades['session_str'] = closed_trades['session']
                
            session_grouped = closed_trades.groupby('session_str')['profit_loss'].sum().sort_values()
            
            colors = ['green' if x > 0 else 'red' for x in session_grouped.values]
            axs[0, 1].barh(session_grouped.index, session_grouped.values, color=colors)
            axs[0, 1].set_title('Profit/Loss by Trading Session')
            axs[0, 1].set_xlabel('Total Profit/Loss')
            axs[0, 1].set_ylabel('Session')
        
        # 3. Trade Duration vs. Profit
        axs[1, 0].scatter(closed_trades['duration'], closed_trades['profit_loss'], 
                         alpha=0.6, c=['green' if p > 0 else 'red' for p in closed_trades['profit_loss']])
        axs[1, 0].set_title('Trade Duration vs. Profit')
        axs[1, 0].set_xlabel('Duration (hours)')
        axs[1, 0].set_ylabel('Profit/Loss')
        axs[1, 0].grid(True)
        
        # Add trend line
        if len(closed_trades) > 1:
            z = np.polyfit(closed_trades['duration'], closed_trades['profit_loss'], 1)
            p = np.poly1d(z)
            axs[1, 0].plot(closed_trades['duration'], p(closed_trades['duration']), "r--", alpha=0.3)
        
        # 4. Consecutive Wins and Losses
        if len(closed_trades) > 0:
            # Calculate streaks
            closed_trades['win'] = closed_trades['profit_loss'] > 0
            streaks = []
            current_streak = 1
            current_win = closed_trades.iloc[0]['win']
            
            for i in range(1, len(closed_trades)):
                if closed_trades.iloc[i]['win'] == current_win:
                    current_streak += 1
                else:
                    streaks.append((current_win, current_streak))
                    current_streak = 1
                    current_win = closed_trades.iloc[i]['win']
                    
            streaks.append((current_win, current_streak))
            
            # Convert to DataFrame
            streak_df = pd.DataFrame(streaks, columns=['is_win', 'length'])
            
            # Plot
            win_streaks = streak_df[streak_df['is_win']]['length']
            loss_streaks = streak_df[~streak_df['is_win']]['length']
            
            axs[1, 1].hist([win_streaks, loss_streaks], bins=range(1, max(streak_df['length']) + 2), 
                         label=['Winning Streaks', 'Losing Streaks'], alpha=0.7, color=['green', 'red'])
            axs[1, 1].set_title('Distribution of Win/Loss Streaks')
            axs[1, 1].set_xlabel('Streak Length')
            axs[1, 1].set_ylabel('Frequency')
            axs[1, 1].legend()
            axs[1, 1].grid(True)
        
        # Save or show
        if save_path:
            save_file = self.output_dir / save_path
            plt.savefig(save_file, dpi=300, bbox_inches='tight')
            self.logger.info(f"Trade analysis report saved to {save_file}")
        else:
            plt.tight_layout()
            plt.show()
            
    def create_monte_carlo_visualization(self, mc_results: Dict, save_path: Optional[str] = None):
        """
        Visualize Monte Carlo simulation results.
        
        Args:
            mc_results: Dictionary with Monte Carlo analysis results
            save_path: Path to save the plot (if None, display instead)
        """
        if 'final_balance' not in mc_results or 'max_drawdown' not in mc_results:
            self.logger.error("Invalid Monte Carlo results format")
            return
            
        # Set up the figure
        fig, axs = plt.subplots(1, 2, figsize=(15, 6))
        plt.subplots_adjust(wspace=0.3)
        fig.suptitle('Monte Carlo Analysis Results', fontsize=16)
        
        # 1. Final Balance Distribution
        final_balance = mc_results['final_balance']
        x = np.linspace(final_balance['worst_5pct'], final_balance['best_5pct'], 100)
        
        # Fit a normal distribution
        mu = final_balance['mean']
        sigma = final_balance['std']
        y = stats.norm.pdf(x, mu, sigma)
        
        axs[0].plot(x, y, 'r-', lw=2)
        axs[0].axvline(final_balance['mean'], color='k', linestyle='--', alpha=0.3)
        axs[0].axvline(final_balance['worst_5pct'], color='r', linestyle='--', alpha=0.3)
        axs[0].axvline(final_balance['best_5pct'], color='g', linestyle='--', alpha=0.3)
        
        axs[0].set_title('Final Balance Distribution')
        axs[0].set_xlabel('Final Balance')
        axs[0].set_ylabel('Probability Density')
        
        # Add text annotations
        axs[0].annotate(f"Mean: {final_balance['mean']:.2f}", 
                      xy=(0.05, 0.95), xycoords='axes fraction',
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        axs[0].annotate(f"Worst 5%: {final_balance['worst_5pct']:.2f}", 
                      xy=(0.05, 0.9), xycoords='axes fraction',
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        axs[0].annotate(f"Best 5%: {final_balance['best_5pct']:.2f}", 
                      xy=(0.05, 0.85), xycoords='axes fraction',
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        
        # 2. Maximum Drawdown Distribution
        max_drawdown = mc_results['max_drawdown']
        x = np.linspace(0, max_drawdown['worst_5pct'] * 1.5, 100)
        
        # Fit a lognormal distribution (since drawdowns are positive and right-skewed)
        params = stats.lognorm.fit(x)
        y = stats.lognorm.pdf(x, *params)
        
        axs[1].plot(x, y, 'r-', lw=2)
        axs[1].axvline(max_drawdown['mean'], color='k', linestyle='--', alpha=0.3)
        axs[1].axvline(max_drawdown['worst_5pct'], color='r', linestyle='--', alpha=0.3)
        
        axs[1].set_title('Maximum Drawdown Distribution')
        axs[1].set_xlabel('Maximum Drawdown (%)')
        axs[1].set_ylabel('Probability Density')
        
        # Add text annotations
        axs[1].annotate(f"Mean: {max_drawdown['mean']:.2f}%", 
                      xy=(0.05, 0.95), xycoords='axes fraction',
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        axs[1].annotate(f"Worst 5%: {max_drawdown['worst_5pct']:.2f}%", 
                      xy=(0.05, 0.9), xycoords='axes fraction',
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        axs[1].annotate(f"Win Probability: {mc_results['win_probability']:.2%}", 
                      xy=(0.05, 0.85), xycoords='axes fraction',
                      bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        
        # Save or show
        if save_path:
            save_file = self.output_dir / save_path
            plt.savefig(save_file, dpi=300, bbox_inches='tight')
            self.logger.info(f"Monte Carlo visualization saved to {save_file}")
        else:
            plt.tight_layout()
            plt.show()

# Initialize the enhanced backtester
enhanced_backtester = EnhancedBacktester()
