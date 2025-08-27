"""
Performance tracker for monitoring and analyzing trading performance by currency pair.
"""
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging
import matplotlib.pyplot as plt
from collections import defaultdict

class PairPerformanceTracker:
    """
    Tracks trading performance metrics for each currency pair.
    """
    
    def __init__(self, data_dir: str = 'data/performance'):
        self.logger = logging.getLogger(__name__)
        self.data_dir = Path(data_dir)
        self.trades_file = self.data_dir / 'trades_history.json'
        self.reports_dir = self.data_dir / 'reports'
        
        # Create directories if they don't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data structures
        self.trades_history = defaultdict(list)
        self.pair_stats = defaultdict(lambda: {
            'total_trades': 0, 
            'won': 0,
            'lost': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_profit': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'last_updated': None
        })
        
        # Load existing data if available
        self._load_data()
        
    def _load_data(self) -> None:
        """Load trade history and performance data from file."""
        if self.trades_file.exists():
            try:
                with open(self.trades_file, 'r') as f:
                    data = json.load(f)
                    
                # Convert to defaultdict
                for pair, trades in data.items():
                    self.trades_history[pair] = trades
                    
                self.logger.info(f"Loaded trade history for {len(self.trades_history)} pairs")
                
                # Recalculate stats
                for pair, trades in self.trades_history.items():
                    self._calculate_pair_stats(pair)
                    
            except Exception as e:
                self.logger.error(f"Error loading trade history: {e}")
        
    def _save_data(self) -> None:
        """Save trade history to file."""
        try:
            with open(self.trades_file, 'w') as f:
                json.dump(dict(self.trades_history), f, indent=2, default=str)
                
            self.logger.debug("Trade history saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving trade history: {e}")
    
    def add_trade_result(self, pair: str, direction: str, entry_time: datetime, 
                         exit_time: datetime, profit_pips: float, win: bool,
                         trade_data: Optional[Dict] = None) -> None:
        """
        Add a trade result to the history.
        
        Args:
            pair: Currency pair
            direction: 'BUY' or 'SELL'
            entry_time: Trade entry time
            exit_time: Trade exit time
            profit_pips: Profit/loss in pips
            win: Whether the trade was a win
            trade_data: Additional trade data to store
        """
        # Create trade record
        trade = {
            'pair': pair,
            'direction': direction,
            'entry_time': entry_time.isoformat(),
            'exit_time': exit_time.isoformat(),
            'profit_pips': profit_pips,
            'win': win,
            'data': trade_data or {}
        }
        
        # Add to history
        self.trades_history[pair].append(trade)
        
        # Update stats
        self._calculate_pair_stats(pair)
        
        # Save to file
        self._save_data()
        
    def _calculate_pair_stats(self, pair: str) -> None:
        """Calculate performance statistics for a pair."""
        trades = self.trades_history[pair]
        
        if not trades:
            return
            
        stats = {
            'total_trades': len(trades),
            'won': sum(1 for t in trades if t['win']),
            'lost': sum(1 for t in trades if not t['win']),
            'last_updated': datetime.now().isoformat()
        }
        
        # Calculate win rate
        if stats['total_trades'] > 0:
            stats['win_rate'] = stats['won'] / stats['total_trades']
            
        # Calculate profit metrics
        profits = [t['profit_pips'] for t in trades if t['profit_pips'] > 0]
        losses = [abs(t['profit_pips']) for t in trades if t['profit_pips'] < 0]
        
        # Average profit/loss
        stats['avg_profit'] = np.mean(profits) if profits else 0.0
        stats['avg_loss'] = np.mean(losses) if losses else 0.0
        
        # Largest win/loss
        stats['largest_win'] = max(profits) if profits else 0.0
        stats['largest_loss'] = max(losses) if losses else 0.0
        
        # Calculate profit factor
        total_profit = sum(profits)
        total_loss = sum(losses)
        stats['profit_factor'] = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate consecutive wins/losses
        current_streak = 1
        max_win_streak = 0
        max_loss_streak = 0
        
        # Sort trades by time
        sorted_trades = sorted(trades, key=lambda t: t['entry_time'])
        
        for i in range(1, len(sorted_trades)):
            if sorted_trades[i]['win'] == sorted_trades[i-1]['win']:
                current_streak += 1
            else:
                if sorted_trades[i-1]['win']:
                    max_win_streak = max(max_win_streak, current_streak)
                else:
                    max_loss_streak = max(max_loss_streak, current_streak)
                current_streak = 1
                
        # Check final streak
        if sorted_trades[-1]['win']:
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, current_streak)
            
        stats['max_consecutive_wins'] = max_win_streak
        stats['max_consecutive_losses'] = max_loss_streak
        
        # Update stats dictionary
        self.pair_stats[pair] = stats
        
    def get_pair_performance(self, pair: str) -> Dict:
        """Get performance metrics for a specific pair."""
        return self.pair_stats[pair]
        
    def get_all_pair_performance(self) -> Dict[str, Dict]:
        """Get performance metrics for all pairs."""
        return dict(self.pair_stats)
        
    def get_best_performing_pairs(self, min_trades: int = 10) -> List[Tuple[str, float]]:
        """
        Get pairs with the best win rate (minimum number of trades required).
        
        Args:
            min_trades: Minimum number of trades required
            
        Returns:
            List of (pair, win_rate) tuples sorted by win rate
        """
        qualified_pairs = [
            (pair, stats['win_rate'])
            for pair, stats in self.pair_stats.items()
            if stats['total_trades'] >= min_trades
        ]
        
        # Sort by win rate descending
        return sorted(qualified_pairs, key=lambda x: x[1], reverse=True)
        
    def generate_weekly_report(self) -> Dict:
        """Generate a weekly performance report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'period': 'weekly',
            'overall_stats': {},
            'pair_stats': {},
            'top_pairs': [],
            'bottom_pairs': []
        }
        
        # Calculate date range for the past week
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Filter trades for the past week
        weekly_trades = {}
        for pair, trades in self.trades_history.items():
            filtered_trades = [
                t for t in trades
                if datetime.fromisoformat(t['entry_time']) >= start_date
            ]
            if filtered_trades:
                weekly_trades[pair] = filtered_trades
                
        # Calculate overall stats
        all_trades = [t for trades in weekly_trades.values() for t in trades]
        total_trades = len(all_trades)
        wins = sum(1 for t in all_trades if t['win'])
        
        report['overall_stats'] = {
            'total_trades': total_trades,
            'win_rate': wins / total_trades if total_trades > 0 else 0,
            'total_pairs_traded': len(weekly_trades)
        }
        
        # Calculate pair stats
        for pair, trades in weekly_trades.items():
            wins = sum(1 for t in trades if t['win'])
            win_rate = wins / len(trades) if trades else 0
            
            report['pair_stats'][pair] = {
                'trades': len(trades),
                'wins': wins,
                'losses': len(trades) - wins,
                'win_rate': win_rate
            }
            
        # Get top and bottom pairs
        if weekly_trades:
            pair_win_rates = [(pair, stats['win_rate']) 
                             for pair, stats in report['pair_stats'].items()
                             if stats['trades'] >= 5]  # Minimum 5 trades
            
            pair_win_rates.sort(key=lambda x: x[1], reverse=True)
            
            report['top_pairs'] = pair_win_rates[:3]
            report['bottom_pairs'] = pair_win_rates[-3:]
            
        # Save report
        report_file = self.reports_dir / f"weekly_report_{datetime.now().strftime('%Y%m%d')}.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving weekly report: {e}")
            
        return report
        
    def generate_monthly_report(self) -> Dict:
        """Generate a monthly performance report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'period': 'monthly',
            'overall_stats': {},
            'pair_stats': {},
            'top_pairs': [],
            'bottom_pairs': [],
            'performance_trends': {}
        }
        
        # Calculate date range for the past month
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Filter trades for the past month
        monthly_trades = {}
        for pair, trades in self.trades_history.items():
            filtered_trades = [
                t for t in trades
                if datetime.fromisoformat(t['entry_time']) >= start_date
            ]
            if filtered_trades:
                monthly_trades[pair] = filtered_trades
                
        # Similar calculations to weekly report, but with more detail
        # (implementation omitted for brevity but similar to weekly report)
        
        # Save report
        report_file = self.reports_dir / f"monthly_report_{datetime.now().strftime('%Y%m')}.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving monthly report: {e}")
            
        return report
        
    def plot_pair_performance(self, pair: str, save_to_file: bool = False) -> None:
        """
        Plot performance for a specific pair.
        
        Args:
            pair: Currency pair
            save_to_file: Whether to save plot to file
        """
        if pair not in self.trades_history or not self.trades_history[pair]:
            self.logger.warning(f"No trade history for {pair}")
            return
            
        trades = self.trades_history[pair]
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(trades)
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['exit_time'] = pd.to_datetime(df['exit_time'])
        
        # Sort by time
        df.sort_values('entry_time', inplace=True)
        
        # Calculate cumulative profit
        df['cumulative_pips'] = df['profit_pips'].cumsum()
        
        # Create plot
        plt.figure(figsize=(12, 8))
        
        # Plot cumulative profit
        plt.subplot(2, 1, 1)
        plt.plot(df['entry_time'], df['cumulative_pips'], 'b-')
        plt.title(f"{pair} - Cumulative Performance")
        plt.xlabel('Date')
        plt.ylabel('Pips')
        plt.grid(True)
        
        # Plot win/loss distribution
        plt.subplot(2, 2, 3)
        win_counts = df['win'].value_counts()
        plt.pie(win_counts, labels=['Win', 'Loss'], 
                autopct='%1.1f%%', colors=['green', 'red'])
        plt.title('Win/Loss Distribution')
        
        # Plot trade results
        plt.subplot(2, 2, 4)
        plt.hist(df['profit_pips'], bins=20)
        plt.title('Profit/Loss Distribution')
        plt.xlabel('Pips')
        plt.ylabel('Frequency')
        plt.grid(True)
        
        plt.tight_layout()
        
        if save_to_file:
            plt.savefig(self.reports_dir / f"{pair}_performance.png")
            plt.close()
        else:
            plt.show()
            
    def plot_all_pairs_comparison(self, save_to_file: bool = False) -> None:
        """
        Plot performance comparison across all pairs.
        
        Args:
            save_to_file: Whether to save plot to file
        """
        # Filter pairs with enough trades
        pairs = [pair for pair, stats in self.pair_stats.items() 
                if stats['total_trades'] >= 5]
        
        if not pairs:
            self.logger.warning("Not enough data for pairs comparison")
            return
            
        # Extract win rates and total trades
        win_rates = [self.pair_stats[pair]['win_rate'] for pair in pairs]
        total_trades = [self.pair_stats[pair]['total_trades'] for pair in pairs]
        
        # Create plot
        plt.figure(figsize=(12, 6))
        
        # Plot win rates
        plt.subplot(1, 2, 1)
        y_pos = np.arange(len(pairs))
        plt.barh(y_pos, win_rates, align='center')
        plt.yticks(y_pos, pairs)
        plt.xlabel('Win Rate')
        plt.title('Win Rate by Pair')
        plt.grid(True)
        plt.xlim(0, 1)
        
        # Plot total trades
        plt.subplot(1, 2, 2)
        plt.barh(y_pos, total_trades, align='center')
        plt.yticks(y_pos, pairs)
        plt.xlabel('Total Trades')
        plt.title('Trade Volume by Pair')
        plt.grid(True)
        
        plt.tight_layout()
        
        if save_to_file:
            plt.savefig(self.reports_dir / "pairs_comparison.png")
            plt.close()
        else:
            plt.show()
            
    def simulate_trade_result(self, pair: str, direction: str, win: bool = None) -> None:
        """
        Add a simulated trade result for testing.
        
        Args:
            pair: Currency pair
            direction: 'BUY' or 'SELL'
            win: Whether the trade was a win (if None, random)
        """
        # Generate random win if not specified
        if win is None:
            win = np.random.random() > 0.5
            
        # Generate random profit/loss
        profit_pips = np.random.uniform(10, 20) if win else -np.random.uniform(10, 20)
        
        # Set times
        now = datetime.now()
        entry_time = now - timedelta(hours=np.random.uniform(0, 24))
        exit_time = entry_time + timedelta(minutes=np.random.uniform(5, 60))
        
        # Add trade
        self.add_trade_result(pair, direction, entry_time, exit_time, profit_pips, win)
