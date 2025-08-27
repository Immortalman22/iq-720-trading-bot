#!/usr/bin/env python3
"""
Performance Attribution Module
This module analyzes trading strategy performance attribution and factor analysis
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
import statsmodels.api as sm

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import modules
from src.utils.logger import setup_logger


@dataclass
class AttributionResult:
    """Class to store performance attribution results"""
    factors: List[str]
    exposures: pd.DataFrame
    returns: pd.DataFrame
    attribution: pd.DataFrame
    r_squared: float
    factor_contribution: Dict[str, float]
    unexplained: float
    cumulative_attribution: pd.DataFrame
    
    def to_dict(self):
        """Convert to dictionary (excluding large DataFrames)"""
        return {
            'factors': self.factors,
            'r_squared': self.r_squared,
            'factor_contribution': self.factor_contribution,
            'unexplained': self.unexplained
        }


class PerformanceAttribution:
    """
    Tools for analyzing performance attribution in trading strategies
    """
    
    def __init__(self, log_level="INFO"):
        """Initialize with logger"""
        self.logger = setup_logger(level=log_level)
    
    def factor_attribution(self, 
                         strategy_returns: pd.Series, 
                         factor_returns: pd.DataFrame) -> AttributionResult:
        """
        Perform factor attribution analysis using regression
        
        Args:
            strategy_returns: Series of strategy returns
            factor_returns: DataFrame of factor returns
            
        Returns:
            AttributionResult object with attribution data
        """
        if strategy_returns.empty or factor_returns.empty:
            self.logger.error("Empty returns data provided")
            return None
            
        # Align data
        common_index = strategy_returns.index.intersection(factor_returns.index)
        if len(common_index) < 10:
            self.logger.error("Insufficient overlapping data points for attribution")
            return None
            
        strategy_returns = strategy_returns.loc[common_index]
        factor_returns = factor_returns.loc[common_index]
        
        # Run regression
        X = sm.add_constant(factor_returns)
        model = sm.OLS(strategy_returns, X)
        results = model.fit()
        
        # Extract factor exposures (betas)
        exposures = results.params
        alpha = exposures['const'] if 'const' in exposures else 0
        exposures = exposures.drop('const') if 'const' in exposures else exposures
        
        # Calculate attribution
        attribution = pd.DataFrame(index=common_index)
        for factor in factor_returns.columns:
            attribution[factor] = factor_returns[factor] * exposures[factor]
        
        # Add alpha component
        attribution['alpha'] = alpha / len(common_index)
        
        # Add unexplained component
        attribution['unexplained'] = strategy_returns - attribution.sum(axis=1)
        
        # Calculate cumulative attribution
        cum_attribution = attribution.cumsum()
        cum_attribution['strategy'] = strategy_returns.cumsum()
        
        # Calculate factor contribution percentages
        total_return = strategy_returns.sum()
        factor_contribution = {}
        for factor in factor_returns.columns:
            factor_attribution = attribution[factor].sum()
            factor_contribution[factor] = factor_attribution / total_return if total_return != 0 else 0
            
        # Alpha contribution
        alpha_attribution = attribution['alpha'].sum()
        factor_contribution['alpha'] = alpha_attribution / total_return if total_return != 0 else 0
        
        # Unexplained contribution
        unexplained_attribution = attribution['unexplained'].sum()
        unexplained_pct = unexplained_attribution / total_return if total_return != 0 else 0
        
        # Create result object
        result = AttributionResult(
            factors=factor_returns.columns.tolist(),
            exposures=pd.DataFrame({'exposure': exposures}),
            returns=factor_returns,
            attribution=attribution,
            r_squared=results.rsquared,
            factor_contribution=factor_contribution,
            unexplained=unexplained_pct,
            cumulative_attribution=cum_attribution
        )
        
        # Log results
        self.logger.info(f"Factor attribution complete with {len(factor_returns.columns)} factors")
        self.logger.info(f"R-squared: {results.rsquared:.4f}")
        
        return result
    
    def time_based_attribution(self, 
                             returns: pd.Series, 
                             periods: Dict[str, List]) -> pd.DataFrame:
        """
        Analyze returns across different time periods
        
        Args:
            returns: Series of returns indexed by datetime
            periods: Dictionary with period names and lists of date ranges
            
        Returns:
            DataFrame with returns by period
        """
        if returns.empty:
            self.logger.error("Empty returns data provided")
            return pd.DataFrame()
            
        # Create results DataFrame
        results = pd.DataFrame(columns=[
            'period', 'start_date', 'end_date', 'total_return', 
            'annualized_return', 'sharpe_ratio', 'win_rate', 'contribution'
        ])
        
        # Calculate overall return for contribution calculation
        overall_return = (1 + returns).prod() - 1
        
        # Analyze each period
        for period_name, date_ranges in periods.items():
            for i, (start, end) in enumerate(date_ranges):
                # Filter returns for this period
                period_returns = returns.loc[start:end]
                
                if period_returns.empty:
                    continue
                    
                # Calculate metrics
                total_return = (1 + period_returns).prod() - 1
                
                # Calculate years duration
                days_diff = (period_returns.index[-1] - period_returns.index[0]).days
                year_frac = max(days_diff / 365.25, 1/252)  # Minimum 1 trading day
                
                # Calculate annualized return
                annualized_return = (1 + total_return) ** (1 / year_frac) - 1
                
                # Calculate Sharpe ratio (annualized)
                sharpe_ratio = (np.mean(period_returns) / np.std(period_returns)) * np.sqrt(252) \
                              if np.std(period_returns) > 0 else 0
                
                # Calculate win rate
                win_rate = np.mean(period_returns > 0) if len(period_returns) > 0 else 0
                
                # Calculate contribution to overall return
                contribution = total_return / overall_return if overall_return != 0 else 0
                
                # Add to results
                results = pd.concat([results, pd.DataFrame({
                    'period': f"{period_name}_{i+1}",
                    'start_date': start,
                    'end_date': end,
                    'total_return': total_return,
                    'annualized_return': annualized_return,
                    'sharpe_ratio': sharpe_ratio,
                    'win_rate': win_rate,
                    'contribution': contribution
                }, index=[0])], ignore_index=True)
        
        # Calculate aggregate metrics for each period type
        period_types = set([p.split('_')[0] for p in results['period']])
        
        for p_type in period_types:
            type_results = results[results['period'].str.startswith(p_type + '_')]
            
            if type_results.empty:
                continue
                
            # Calculate aggregate metrics
            agg_return = type_results['total_return'].sum()
            agg_contrib = type_results['contribution'].sum()
            
            # Add to results
            results = pd.concat([results, pd.DataFrame({
                'period': p_type + '_TOTAL',
                'start_date': type_results['start_date'].min(),
                'end_date': type_results['end_date'].max(),
                'total_return': agg_return,
                'annualized_return': np.nan,  # Not applicable for aggregate
                'sharpe_ratio': np.nan,  # Not applicable for aggregate
                'win_rate': np.nan,  # Not applicable for aggregate
                'contribution': agg_contrib
            }, index=[0])], ignore_index=True)
        
        # Sort by contribution
        results = results.sort_values('contribution', ascending=False)
        
        return results
    
    def market_regime_attribution(self, 
                                strategy_returns: pd.Series, 
                                market_returns: pd.Series,
                                volatility: pd.Series = None,
                                n_regimes: int = 4) -> pd.DataFrame:
        """
        Attribute performance to different market regimes
        
        Args:
            strategy_returns: Series of strategy returns
            market_returns: Series of market benchmark returns
            volatility: Series of market volatility (optional)
            n_regimes: Number of regimes to analyze
            
        Returns:
            DataFrame with returns by market regime
        """
        if strategy_returns.empty or market_returns.empty:
            self.logger.error("Empty returns data provided")
            return pd.DataFrame()
            
        # Align data
        common_index = strategy_returns.index.intersection(market_returns.index)
        if len(common_index) < n_regimes * 10:
            self.logger.error("Insufficient data points for regime analysis")
            return pd.DataFrame()
            
        strategy_returns = strategy_returns.loc[common_index]
        market_returns = market_returns.loc[common_index]
        
        # Create DataFrame for analysis
        df = pd.DataFrame({
            'strategy': strategy_returns,
            'market': market_returns
        })
        
        # Add volatility if provided
        if volatility is not None:
            volatility = volatility.loc[common_index]
            df['volatility'] = volatility
            
            # Define regimes based on returns and volatility
            df['return_quantile'] = pd.qcut(df['market'], n_regimes // 2, labels=False)
            df['vol_quantile'] = pd.qcut(df['volatility'], 2, labels=False)
            df['regime'] = df['return_quantile'] + df['vol_quantile'] * (n_regimes // 2)
            
            regime_names = {
                0: 'Low_Return_Low_Vol',
                1: 'High_Return_Low_Vol',
                2: 'Low_Return_High_Vol',
                3: 'High_Return_High_Vol'
            }
        else:
            # Define regimes based on returns only
            df['regime'] = pd.qcut(df['market'], n_regimes, labels=False)
            
            regime_names = {i: f"Regime_{i+1}" for i in range(n_regimes)}
        
        # Replace regime numbers with names
        df['regime_name'] = df['regime'].map(regime_names)
        
        # Calculate statistics by regime
        regime_stats = df.groupby('regime_name').agg({
            'strategy': ['mean', 'std', 'count', lambda x: (x > 0).mean()],
            'market': ['mean', 'std']
        })
        
        # Flatten column MultiIndex
        regime_stats.columns = [f"{col[0]}_{col[1]}" for col in regime_stats.columns]
        
        # Rename columns
        regime_stats = regime_stats.rename(columns={
            'strategy_mean': 'avg_return',
            'strategy_std': 'volatility',
            'strategy_count': 'n_days',
            'strategy_<lambda_0>': 'win_rate',
            'market_mean': 'market_return',
            'market_std': 'market_volatility'
        })
        
        # Calculate contribution
        strategy_total_return = (1 + strategy_returns).prod() - 1
        
        for regime in regime_stats.index:
            regime_returns = df.loc[df['regime_name'] == regime, 'strategy']
            regime_total_return = (1 + regime_returns).prod() - 1
            regime_stats.loc[regime, 'total_return'] = regime_total_return
            regime_stats.loc[regime, 'contribution'] = regime_total_return / strategy_total_return \
                                                     if strategy_total_return != 0 else 0
            
            # Calculate annualized metrics
            n_days = regime_stats.loc[regime, 'n_days']
            if n_days > 0:
                ann_factor = 252 / n_days * len(df)  # Scale based on proportion of days
                regime_stats.loc[regime, 'ann_return'] = (1 + regime_stats.loc[regime, 'avg_return']) ** ann_factor - 1
                regime_stats.loc[regime, 'ann_sharpe'] = regime_stats.loc[regime, 'avg_return'] / regime_stats.loc[regime, 'volatility'] * np.sqrt(252) \
                                                        if regime_stats.loc[regime, 'volatility'] > 0 else 0
        
        # Calculate beta by regime
        for regime in regime_stats.index:
            regime_data = df.loc[df['regime_name'] == regime]
            if len(regime_data) > 1:
                X = sm.add_constant(regime_data['market'])
                model = sm.OLS(regime_data['strategy'], X).fit()
                regime_stats.loc[regime, 'beta'] = model.params['market']
                regime_stats.loc[regime, 'alpha'] = model.params['const'] * 252  # Annualized alpha
            else:
                regime_stats.loc[regime, 'beta'] = np.nan
                regime_stats.loc[regime, 'alpha'] = np.nan
        
        # Sort by contribution
        regime_stats = regime_stats.sort_values('contribution', ascending=False)
        
        return regime_stats
    
    def trade_attribution(self, 
                        trades: List[Dict], 
                        attributes: List[str]) -> pd.DataFrame:
        """
        Attribute performance to different trade attributes
        
        Args:
            trades: List of trade dictionaries with profit_loss and attributes
            attributes: List of attributes to analyze
            
        Returns:
            DataFrame with returns by attribute
        """
        if not trades:
            self.logger.error("No trades provided for attribution")
            return pd.DataFrame()
            
        # Convert to DataFrame
        trades_df = pd.DataFrame(trades)
        
        # Check if required columns exist
        required_cols = ['profit_loss'] + attributes
        missing_cols = [col for col in required_cols if col not in trades_df.columns]
        
        if missing_cols:
            self.logger.error(f"Missing required columns in trades: {missing_cols}")
            return pd.DataFrame()
            
        # Calculate total profit
        total_profit = trades_df['profit_loss'].sum()
        
        # Initialize results
        results = []
        
        # Analyze each attribute
        for attr in attributes:
            # Group by attribute
            grouped = trades_df.groupby(attr).agg({
                'profit_loss': ['sum', 'mean', 'count'],
            })
            
            # Flatten column MultiIndex
            grouped.columns = [f"{col[0]}_{col[1]}" for col in grouped.columns]
            
            # Calculate win rate and contribution
            for value in grouped.index:
                attr_trades = trades_df[trades_df[attr] == value]
                
                win_rate = (attr_trades['profit_loss'] > 0).mean()
                contribution = grouped.loc[value, 'profit_loss_sum'] / total_profit if total_profit != 0 else 0
                
                # Add to results
                results.append({
                    'attribute': attr,
                    'value': value,
                    'total_profit': grouped.loc[value, 'profit_loss_sum'],
                    'avg_profit': grouped.loc[value, 'profit_loss_mean'],
                    'num_trades': grouped.loc[value, 'profit_loss_count'],
                    'win_rate': win_rate,
                    'contribution': contribution
                })
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        
        # Sort by contribution
        if not results_df.empty:
            results_df = results_df.sort_values(['attribute', 'contribution'], ascending=[True, False])
        
        return results_df
    
    def visualize_factor_attribution(self, result: AttributionResult) -> plt.Figure:
        """
        Visualize factor attribution results
        
        Args:
            result: AttributionResult from factor_attribution
            
        Returns:
            matplotlib Figure
        """
        if result is None:
            self.logger.error("No attribution results to visualize")
            return None
            
        # Set style
        plt.style.use('ggplot')
        sns.set_palette("viridis")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 12))
        
        # Plot 1: Cumulative attribution
        ax1 = fig.add_subplot(2, 2, 1)
        
        # Plot cumulative strategy returns
        result.cumulative_attribution['strategy'].plot(ax=ax1, linewidth=2, color='black', label='Strategy')
        
        # Plot factor contributions
        for factor in result.factors:
            result.cumulative_attribution[factor].plot(ax=ax1, linewidth=1, alpha=0.7, label=factor)
            
        # Plot alpha
        result.cumulative_attribution['alpha'].plot(ax=ax1, linewidth=1, linestyle='--', label='Alpha')
        
        ax1.set_title('Cumulative Return Attribution')
        ax1.set_ylabel('Cumulative Return')
        ax1.legend()
        ax1.grid(True)
        
        # Plot 2: Factor exposures
        ax2 = fig.add_subplot(2, 2, 2)
        
        # Create bar chart of factor exposures
        exposures = result.exposures['exposure']
        exposures.plot(kind='bar', ax=ax2, color='steelblue')
        
        ax2.set_title('Factor Exposures (Betas)')
        ax2.set_xlabel('Factor')
        ax2.set_ylabel('Exposure')
        ax2.grid(True)
        
        # Plot 3: Factor contribution pie chart
        ax3 = fig.add_subplot(2, 2, 3)
        
        # Extract contribution percentages
        contrib = result.factor_contribution.copy()
        
        # Add unexplained to make it 100%
        contrib['unexplained'] = result.unexplained
        
        # Remove tiny values for better visualization
        small_threshold = 0.03  # 3%
        small_factors = {k: v for k, v in contrib.items() if abs(v) < small_threshold}
        if small_factors:
            contrib['other'] = sum(small_factors.values())
            for k in small_factors:
                del contrib[k]
        
        # Create pie chart
        colors = sns.color_palette("Set2", len(contrib))
        ax3.pie(
            [abs(v) for v in contrib.values()],
            labels=[f"{k} ({v*100:.1f}%)" for k, v in contrib.items()],
            autopct='%1.1f%%',
            startangle=90,
            colors=colors
        )
        
        ax3.set_title(f'Factor Contribution (R² = {result.r_squared:.2f})')
        
        # Plot 4: Rolling factor attribution
        ax4 = fig.add_subplot(2, 2, 4)
        
        # Calculate rolling factor attribution
        rolling_window = min(60, len(result.attribution) // 4)  # Adjust window size based on data length
        rolling_attr = result.attribution.rolling(window=rolling_window).sum()
        
        # Plot rolling attribution for each factor
        for factor in result.factors:
            rolling_attr[factor].plot(ax=ax4, linewidth=1, alpha=0.7, label=factor)
            
        # Plot alpha
        rolling_attr['alpha'].plot(ax=ax4, linewidth=1, linestyle='--', label='Alpha')
        
        ax4.set_title(f'Rolling {rolling_window}-Period Factor Attribution')
        ax4.set_ylabel('Attribution')
        ax4.legend()
        ax4.grid(True)
        
        # Add title
        fig.suptitle('Factor Performance Attribution Analysis', fontsize=16)
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        return fig
    
    def visualize_regime_attribution(self, regime_stats: pd.DataFrame) -> plt.Figure:
        """
        Visualize market regime attribution results
        
        Args:
            regime_stats: DataFrame from market_regime_attribution
            
        Returns:
            matplotlib Figure
        """
        if regime_stats.empty:
            self.logger.error("Empty regime statistics provided")
            return None
            
        # Set style
        plt.style.use('ggplot')
        sns.set_palette("viridis")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 12))
        
        # Plot 1: Returns by regime
        ax1 = fig.add_subplot(2, 2, 1)
        
        # Sort by market return for clearer visualization
        plot_data = regime_stats.sort_values('market_return')
        
        # Create bar chart of returns
        plot_data[['avg_return', 'market_return']].plot(kind='bar', ax=ax1)
        
        ax1.set_title('Average Daily Returns by Regime')
        ax1.set_xlabel('Regime')
        ax1.set_ylabel('Average Return')
        ax1.grid(True)
        
        # Plot 2: Contribution by regime
        ax2 = fig.add_subplot(2, 2, 2)
        
        # Sort by contribution
        plot_data = regime_stats.sort_values('contribution', ascending=False)
        
        # Create bar chart of contribution
        plot_data['contribution'].plot(kind='bar', ax=ax2, color='steelblue')
        
        ax2.set_title('Return Contribution by Regime')
        ax2.set_xlabel('Regime')
        ax2.set_ylabel('Contribution')
        ax2.grid(True)
        
        # Plot 3: Risk metrics by regime
        ax3 = fig.add_subplot(2, 2, 3)
        
        # Sort by volatility
        plot_data = regime_stats.sort_values('volatility')
        
        # Create bar chart of volatility and win rate
        plot_data[['volatility', 'win_rate']].plot(kind='bar', ax=ax3)
        
        ax3.set_title('Risk Metrics by Regime')
        ax3.set_xlabel('Regime')
        ax3.set_ylabel('Value')
        ax3.grid(True)
        
        # Plot 4: Alpha and beta by regime
        ax4 = fig.add_subplot(2, 2, 4)
        
        # Sort by beta
        if 'beta' in regime_stats.columns:
            plot_data = regime_stats.sort_values('beta')
            
            # Create scatter plot of alpha vs beta
            ax4.scatter(plot_data['beta'], plot_data['alpha'], s=100)
            
            # Add regime labels
            for i, row in plot_data.iterrows():
                ax4.annotate(
                    i,
                    xy=(row['beta'], row['alpha']),
                    xytext=(5, 5),
                    textcoords='offset points'
                )
            
            ax4.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax4.axvline(1, color='black', linestyle='--', linewidth=0.5)
            
            ax4.set_title('Alpha vs Beta by Regime')
            ax4.set_xlabel('Beta')
            ax4.set_ylabel('Alpha (annualized)')
            ax4.grid(True)
        else:
            ax4.text(0.5, 0.5, "Alpha/Beta data not available", 
                    ha='center', va='center', transform=ax4.transAxes)
        
        # Add title
        fig.suptitle('Market Regime Attribution Analysis', fontsize=16)
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        return fig


if __name__ == "__main__":
    # Example usage
    pass
