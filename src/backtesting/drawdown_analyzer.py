#!/usr/bin/env python3
"""
Drawdown Analysis Module
This module provides tools for analyzing drawdowns in trading strategies
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import modules
from src.utils.logger import setup_logger


@dataclass
class DrawdownEvent:
    """Class to store information about a drawdown event"""
    id: int
    start_date: datetime
    end_date: Optional[datetime]
    recovery_date: Optional[datetime]
    max_drawdown_date: datetime
    max_drawdown_pct: float
    max_drawdown_value: float
    start_value: float
    end_value: Optional[float]
    recovery_value: Optional[float]
    duration_days: Optional[int]
    recovery_days: Optional[int]
    total_days: Optional[int]
    underwater_series: pd.Series = None
    
    def is_recovered(self) -> bool:
        """Check if drawdown has recovered"""
        return self.recovery_date is not None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        result = {
            'id': self.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'recovery_date': self.recovery_date,
            'max_drawdown_date': self.max_drawdown_date,
            'max_drawdown_pct': self.max_drawdown_pct,
            'max_drawdown_value': self.max_drawdown_value,
            'start_value': self.start_value,
            'end_value': self.end_value,
            'recovery_value': self.recovery_value,
            'duration_days': self.duration_days,
            'recovery_days': self.recovery_days,
            'total_days': self.total_days,
        }
        
        # Don't include underwater series in dict
        return result


class DrawdownAnalyzer:
    """
    Tools for analyzing drawdowns in trading strategies
    """
    
    def __init__(self, log_level="INFO"):
        """Initialize with logger"""
        self.logger = setup_logger(level=log_level)
    
    def calculate_drawdowns(self, equity_curve: pd.Series) -> pd.DataFrame:
        """
        Calculate drawdowns from equity curve
        
        Args:
            equity_curve: Series with equity values indexed by dates
            
        Returns:
            DataFrame with drawdown statistics
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return pd.DataFrame()
            
        # Make a copy to avoid modifying the original
        equity = equity_curve.copy()
        
        # Calculate running maximum
        running_max = equity.cummax()
        
        # Calculate drawdown
        drawdown = (equity / running_max) - 1
        
        # Calculate underwater equity
        underwater = running_max - equity
        
        # Create result DataFrame
        result = pd.DataFrame({
            'equity': equity,
            'peak': running_max,
            'drawdown_pct': drawdown,
            'underwater': underwater
        })
        
        return result
    
    def identify_drawdown_periods(self, equity_curve: pd.Series, 
                                 threshold: float = 0.0) -> List[DrawdownEvent]:
        """
        Identify individual drawdown periods
        
        Args:
            equity_curve: Series with equity values indexed by dates
            threshold: Minimum drawdown to consider (e.g. 0.01 for 1%)
            
        Returns:
            List of DrawdownEvent objects
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return []
            
        # Calculate drawdowns
        dd_df = self.calculate_drawdowns(equity_curve)
        
        # Find drawdown start and end points
        in_drawdown = False
        current_dd = None
        drawdowns = []
        dd_id = 0
        
        # Previous peak value and date
        prev_peak = equity_curve.iloc[0]
        prev_peak_date = equity_curve.index[0]
        
        for date, row in dd_df.iterrows():
            dd_pct = row['drawdown_pct']
            
            # Check for new peak
            if row['equity'] > prev_peak:
                prev_peak = row['equity']
                prev_peak_date = date
            
            # Start of new drawdown
            if not in_drawdown and dd_pct < -threshold:
                dd_id += 1
                in_drawdown = True
                current_dd = DrawdownEvent(
                    id=dd_id,
                    start_date=prev_peak_date,
                    end_date=None,
                    recovery_date=None,
                    max_drawdown_date=date,
                    max_drawdown_pct=dd_pct,
                    max_drawdown_value=row['underwater'],
                    start_value=prev_peak,
                    end_value=None,
                    recovery_value=None,
                    duration_days=None,
                    recovery_days=None,
                    total_days=None
                )
            
            # Update max drawdown if deeper
            elif in_drawdown and dd_pct < current_dd.max_drawdown_pct:
                current_dd.max_drawdown_pct = dd_pct
                current_dd.max_drawdown_date = date
                current_dd.max_drawdown_value = row['underwater']
            
            # End of drawdown
            elif in_drawdown and dd_pct >= -threshold:
                in_drawdown = False
                current_dd.end_date = date
                current_dd.end_value = row['equity']
                
                # Calculate duration
                current_dd.duration_days = (date - current_dd.start_date).days
                
                # Add to list
                drawdowns.append(current_dd)
                current_dd = None
        
        # If still in a drawdown at the end, close it
        if in_drawdown:
            last_date = dd_df.index[-1]
            current_dd.end_date = last_date
            current_dd.end_value = dd_df.iloc[-1]['equity']
            current_dd.duration_days = (last_date - current_dd.start_date).days
            drawdowns.append(current_dd)
        
        # Find recovery periods for each drawdown
        for dd in drawdowns:
            if dd.end_date is None:
                continue
                
            # Look for recovery after end_date
            recovery_idx = None
            for i, (date, row) in enumerate(dd_df.loc[dd.end_date:].iterrows()):
                if row['equity'] >= dd.start_value:
                    recovery_idx = i
                    dd.recovery_date = date
                    dd.recovery_value = row['equity']
                    break
            
            # Calculate recovery days
            if dd.recovery_date is not None:
                dd.recovery_days = (dd.recovery_date - dd.end_date).days
                dd.total_days = (dd.recovery_date - dd.start_date).days
            
            # Store underwater series
            if dd.start_date and dd.recovery_date:
                dd.underwater_series = dd_df.loc[dd.start_date:dd.recovery_date, 'underwater']
            elif dd.start_date and dd.end_date:
                dd.underwater_series = dd_df.loc[dd.start_date:dd.end_date, 'underwater']
        
        # Sort by drawdown percentage
        drawdowns.sort(key=lambda x: x.max_drawdown_pct)
        
        self.logger.info(f"Identified {len(drawdowns)} drawdown periods")
        
        return drawdowns
    
    def calculate_ulcer_index(self, equity_curve: pd.Series, window: int = None) -> Union[float, pd.Series]:
        """
        Calculate Ulcer Index (UI) - square root of mean squared drawdown
        Higher values indicate higher risk of large drawdowns
        
        Args:
            equity_curve: Series with equity values indexed by dates
            window: Rolling window size (None for full series)
            
        Returns:
            Ulcer Index value or Series if window is specified
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return 0.0 if window is None else pd.Series()
            
        # Calculate drawdowns
        dd_df = self.calculate_drawdowns(equity_curve)
        
        # Square drawdown percentages
        squared_dd = dd_df['drawdown_pct'] ** 2
        
        if window is None:
            # Calculate UI for full series
            ui = np.sqrt(squared_dd.mean())
            return ui
        else:
            # Calculate rolling UI
            rolling_ui = squared_dd.rolling(window=window).mean().apply(np.sqrt)
            return rolling_ui
    
    def calculate_pain_index(self, equity_curve: pd.Series, window: int = None) -> Union[float, pd.Series]:
        """
        Calculate Pain Index - average of absolute drawdown values
        
        Args:
            equity_curve: Series with equity values indexed by dates
            window: Rolling window size (None for full series)
            
        Returns:
            Pain Index value or Series if window is specified
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return 0.0 if window is None else pd.Series()
            
        # Calculate drawdowns
        dd_df = self.calculate_drawdowns(equity_curve)
        
        # Get absolute drawdown values
        abs_dd = abs(dd_df['drawdown_pct'])
        
        if window is None:
            # Calculate Pain Index for full series
            pain = abs_dd.mean()
            return pain
        else:
            # Calculate rolling Pain Index
            rolling_pain = abs_dd.rolling(window=window).mean()
            return rolling_pain
    
    def calculate_calmar_ratio(self, equity_curve: pd.Series, 
                              risk_free_rate: float = 0.0, 
                              period_years: int = 3) -> float:
        """
        Calculate Calmar Ratio (annualized return / max drawdown)
        
        Args:
            equity_curve: Series with equity values indexed by dates
            risk_free_rate: Annual risk-free rate
            period_years: Period for calculation in years
            
        Returns:
            Calmar Ratio
        """
        if equity_curve.empty or len(equity_curve) < 2:
            self.logger.error("Insufficient data for Calmar Ratio")
            return 0.0
            
        # Calculate drawdowns
        dd_df = self.calculate_drawdowns(equity_curve)
        
        # Get max drawdown
        max_dd = abs(dd_df['drawdown_pct'].min())
        
        if max_dd == 0:
            return float('inf')  # Avoid division by zero
            
        # Calculate annualized return
        start_value = equity_curve.iloc[0]
        end_value = equity_curve.iloc[-1]
        
        # Calculate years duration
        days_diff = (equity_curve.index[-1] - equity_curve.index[0]).days
        year_frac = days_diff / 365.25
        
        # Check for very short periods
        if year_frac < 0.01:  # Less than ~3.65 days
            return 0.0
        
        # Calculate annualized return
        total_return = (end_value / start_value) - 1
        annualized_return = ((1 + total_return) ** (1 / year_frac)) - 1
        excess_return = annualized_return - risk_free_rate
        
        # Calculate Calmar ratio
        calmar = excess_return / max_dd
        
        return calmar
    
    def calculate_sterling_ratio(self, equity_curve: pd.Series,
                                risk_free_rate: float = 0.0,
                                n_drawdowns: int = 10) -> float:
        """
        Calculate Sterling Ratio (annualized return / average of N largest drawdowns)
        
        Args:
            equity_curve: Series with equity values indexed by dates
            risk_free_rate: Annual risk-free rate
            n_drawdowns: Number of largest drawdowns to average
            
        Returns:
            Sterling Ratio
        """
        if equity_curve.empty or len(equity_curve) < 2:
            self.logger.error("Insufficient data for Sterling Ratio")
            return 0.0
            
        # Identify drawdown periods
        drawdowns = self.identify_drawdown_periods(equity_curve)
        
        if not drawdowns:
            return float('inf')  # No drawdowns
            
        # Get N largest drawdowns
        largest_dds = sorted(drawdowns, key=lambda x: x.max_drawdown_pct)[:min(n_drawdowns, len(drawdowns))]
        avg_dd = np.mean([abs(dd.max_drawdown_pct) for dd in largest_dds])
        
        if avg_dd == 0:
            return float('inf')  # Avoid division by zero
            
        # Calculate annualized return
        start_value = equity_curve.iloc[0]
        end_value = equity_curve.iloc[-1]
        
        # Calculate years duration
        days_diff = (equity_curve.index[-1] - equity_curve.index[0]).days
        year_frac = days_diff / 365.25
        
        # Check for very short periods
        if year_frac < 0.01:  # Less than ~3.65 days
            return 0.0
        
        # Calculate annualized return
        total_return = (end_value / start_value) - 1
        annualized_return = ((1 + total_return) ** (1 / year_frac)) - 1
        excess_return = annualized_return - risk_free_rate
        
        # Calculate Sterling ratio
        sterling = excess_return / avg_dd
        
        return sterling
    
    def visualize_drawdowns(self, equity_curve: pd.Series, 
                           top_n: int = 5) -> plt.Figure:
        """
        Visualize the largest drawdown periods
        
        Args:
            equity_curve: Series with equity values indexed by dates
            top_n: Number of largest drawdowns to visualize
            
        Returns:
            matplotlib Figure
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return None
            
        # Calculate drawdowns
        dd_df = self.calculate_drawdowns(equity_curve)
        
        # Identify drawdown periods
        drawdowns = self.identify_drawdown_periods(equity_curve)
        
        # Sort by drawdown percentage (descending)
        drawdowns.sort(key=lambda x: x.max_drawdown_pct)
        
        # Take top N
        top_drawdowns = drawdowns[:min(top_n, len(drawdowns))]
        
        # Set style
        plt.style.use('ggplot')
        sns.set_palette("viridis")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 12))
        
        # Plot 1: Equity curve with drawdowns highlighted
        ax1 = fig.add_subplot(2, 1, 1)
        
        # Plot equity curve
        equity_curve.plot(ax=ax1, linewidth=2, color='blue', label='Equity')
        
        # Highlight drawdown periods
        colors = sns.color_palette("husl", len(top_drawdowns))
        
        for i, dd in enumerate(top_drawdowns):
            if dd.start_date and dd.recovery_date:
                ax1.axvspan(dd.start_date, dd.recovery_date, 
                           alpha=0.3, color=colors[i], 
                           label=f"DD #{dd.id}: {dd.max_drawdown_pct*100:.1f}%")
            elif dd.start_date and dd.end_date:
                ax1.axvspan(dd.start_date, dd.end_date, 
                           alpha=0.3, color=colors[i], 
                           label=f"DD #{dd.id}: {dd.max_drawdown_pct*100:.1f}%")
        
        ax1.set_title('Equity Curve with Major Drawdowns')
        ax1.set_ylabel('Equity')
        ax1.legend()
        ax1.grid(True)
        
        # Plot 2: Drawdown underwater chart
        ax2 = fig.add_subplot(2, 1, 2)
        
        # Plot all drawdowns
        dd_df['drawdown_pct'].plot(ax=ax2, linewidth=1, color='gray', alpha=0.3)
        
        # Highlight top drawdowns
        for i, dd in enumerate(top_drawdowns):
            if dd.underwater_series is not None:
                dd_series = dd_df.loc[dd.underwater_series.index, 'drawdown_pct']
                dd_series.plot(ax=ax2, linewidth=2, color=colors[i], 
                              label=f"DD #{dd.id}: {dd.max_drawdown_pct*100:.1f}%")
        
        ax2.set_title('Drawdowns Over Time')
        ax2.set_ylabel('Drawdown %')
        ax2.set_ylim(min(dd_df['drawdown_pct'].min() * 1.1, -0.05), 0.01)
        ax2.legend()
        ax2.grid(True)
        
        plt.tight_layout()
        
        return fig
    
    def create_drawdown_report(self, equity_curve: pd.Series) -> pd.DataFrame:
        """
        Create a comprehensive drawdown report
        
        Args:
            equity_curve: Series with equity values indexed by dates
            
        Returns:
            DataFrame with drawdown statistics
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return pd.DataFrame()
            
        # Identify drawdown periods
        drawdowns = self.identify_drawdown_periods(equity_curve)
        
        # Create DataFrame from drawdowns
        dd_data = []
        for dd in drawdowns:
            dd_dict = dd.to_dict()
            
            # Format dates as strings
            for key in ['start_date', 'end_date', 'recovery_date', 'max_drawdown_date']:
                if dd_dict[key] is not None:
                    dd_dict[key] = dd_dict[key].strftime('%Y-%m-%d')
                    
            dd_data.append(dd_dict)
            
        df = pd.DataFrame(dd_data)
        
        # Calculate additional statistics
        if not df.empty:
            # Convert percentages to actual percentages
            df['max_drawdown_pct'] = df['max_drawdown_pct'] * 100
            
            # Add recovery status
            df['recovered'] = df['recovery_date'].notna()
            
            # Add time to recovery ratio (recovery time / drawdown time)
            mask = (df['duration_days'] > 0) & (df['recovery_days'].notna())
            df.loc[mask, 'recovery_ratio'] = df.loc[mask, 'recovery_days'] / df.loc[mask, 'duration_days']
            
            # Sort by drawdown percentage
            df = df.sort_values('max_drawdown_pct', ascending=True)
        
        return df
    
    def calculate_recovery_statistics(self, equity_curve: pd.Series) -> Dict:
        """
        Calculate recovery statistics from drawdowns
        
        Args:
            equity_curve: Series with equity values indexed by dates
            
        Returns:
            Dictionary with recovery statistics
        """
        if equity_curve.empty:
            self.logger.error("Empty equity curve provided")
            return {}
            
        # Identify drawdown periods
        drawdowns = self.identify_drawdown_periods(equity_curve)
        
        if not drawdowns:
            return {
                'count': 0,
                'avg_drawdown': 0,
                'avg_recovery_days': 0,
                'avg_drawdown_days': 0,
                'recovery_ratio': 0
            }
        
        # Calculate statistics
        recovered = [dd for dd in drawdowns if dd.is_recovered()]
        
        if not recovered:
            return {
                'count': len(drawdowns),
                'recovered_count': 0,
                'avg_drawdown': np.mean([abs(dd.max_drawdown_pct) for dd in drawdowns]) * 100,
                'avg_recovery_days': 0,
                'avg_drawdown_days': np.mean([dd.duration_days for dd in drawdowns if dd.duration_days]),
                'recovery_ratio': 0
            }
            
        stats = {
            'count': len(drawdowns),
            'recovered_count': len(recovered),
            'recovery_rate': len(recovered) / len(drawdowns),
            'avg_drawdown': np.mean([abs(dd.max_drawdown_pct) for dd in drawdowns]) * 100,
            'avg_recovery_days': np.mean([dd.recovery_days for dd in recovered if dd.recovery_days]),
            'avg_drawdown_days': np.mean([dd.duration_days for dd in drawdowns if dd.duration_days]),
            'max_drawdown': abs(min([dd.max_drawdown_pct for dd in drawdowns])) * 100,
            'max_recovery_days': max([dd.recovery_days for dd in recovered if dd.recovery_days] or [0]),
            'max_drawdown_days': max([dd.duration_days for dd in drawdowns if dd.duration_days] or [0])
        }
        
        # Recovery ratio (recovery time / drawdown time)
        recovery_ratios = [dd.recovery_days / dd.duration_days 
                          for dd in recovered 
                          if dd.recovery_days and dd.duration_days and dd.duration_days > 0]
        
        stats['avg_recovery_ratio'] = np.mean(recovery_ratios) if recovery_ratios else 0
        
        return stats


if __name__ == "__main__":
    # Example usage
    pass
