#!/usr/bin/env python3
"""
Monte Carlo Simulation Module for Trading Strategy Analysis
This module provides tools to evaluate strategy robustness through
Monte Carlo simulations of trade sequences, drawdowns, and returns.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Union
from scipy import stats
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import modules
from src.utils.logger import setup_logger


@dataclass
class MonteCarloResult:
    """Class to store Monte Carlo simulation results"""
    iterations: int
    original_returns: List[float]
    return_paths: np.ndarray
    drawdown_paths: np.ndarray
    final_returns: np.ndarray
    max_drawdowns: np.ndarray
    sharpe_ratios: np.ndarray
    percentiles: Dict[str, float]
    
    def to_dict(self):
        """Convert to dictionary (excluding large arrays)"""
        return {
            'iterations': self.iterations,
            'original_returns_count': len(self.original_returns),
            'original_returns_mean': np.mean(self.original_returns),
            'original_returns_std': np.std(self.original_returns),
            'final_returns_mean': np.mean(self.final_returns),
            'final_returns_std': np.std(self.final_returns),
            'max_drawdown_mean': np.mean(self.max_drawdowns),
            'max_drawdown_std': np.std(self.max_drawdowns),
            'sharpe_ratio_mean': np.mean(self.sharpe_ratios),
            'percentiles': self.percentiles
        }


class MonteCarloSimulator:
    """
    Monte Carlo Simulator for trading strategy analysis
    """
    
    def __init__(self, log_level="INFO"):
        """Initialize simulator with logger"""
        self.logger = setup_logger(level=log_level)
    
    def run_simulation(self, 
                      returns: List[float], 
                      initial_capital: float = 10000.0,
                      iterations: int = 1000,
                      sample_pct: float = 100.0,
                      annual_factor: int = 252,
                      risk_free_rate: float = 0.0) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on trade returns
        
        Args:
            returns: List of trade returns (as percentage or fraction)
            initial_capital: Initial capital for simulation
            iterations: Number of Monte Carlo iterations
            sample_pct: Percentage of trades to sample in each iteration (100 = all)
            annual_factor: Annualization factor for Sharpe ratio
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            
        Returns:
            MonteCarloResult object with simulation results
        """
        self.logger.info(f"Starting Monte Carlo simulation with {iterations} iterations")
        self.logger.info(f"Sample percentage: {sample_pct}%")
        
        if not returns:
            self.logger.error("No returns provided for simulation")
            return None
        
        # Ensure returns are numpy array
        returns_array = np.array(returns)
        
        # Calculate number of trades to sample
        n_trades = max(1, int(len(returns) * (sample_pct / 100)))
        
        # Initialize arrays for results
        return_paths = np.zeros((iterations, n_trades))
        final_returns = np.zeros(iterations)
        max_drawdowns = np.zeros(iterations)
        sharpe_ratios = np.zeros(iterations)
        
        # Run simulation iterations
        for i in tqdm(range(iterations), desc="Monte Carlo Simulation"):
            # Resample trades with replacement
            sampled_returns = np.random.choice(returns_array, size=n_trades, replace=True)
            
            # Store resampled returns
            return_paths[i, :] = sampled_returns
            
            # Calculate cumulative returns
            cum_returns = np.cumprod(1 + sampled_returns) - 1
            
            # Calculate drawdowns
            peak = np.maximum.accumulate(1 + cum_returns)
            drawdown = (1 + cum_returns) / peak - 1
            
            # Store results
            final_returns[i] = cum_returns[-1] if len(cum_returns) > 0 else 0
            max_drawdowns[i] = np.min(drawdown) if len(drawdown) > 0 else 0
            sharpe_ratios[i] = (np.mean(sampled_returns) - risk_free_rate) / np.std(sampled_returns) * np.sqrt(annual_factor) \
                              if np.std(sampled_returns) > 0 else 0
        
        # Calculate percentiles
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_values = {
            f"return_{p}pct": np.percentile(final_returns, p) 
            for p in percentiles
        }
        percentile_values.update({
            f"drawdown_{p}pct": np.percentile(max_drawdowns, p)
            for p in percentiles
        })
        
        # Calculate drawdown paths
        drawdown_paths = np.zeros_like(return_paths)
        for i in range(iterations):
            cum_returns = np.cumprod(1 + return_paths[i, :]) - 1
            peak = np.maximum.accumulate(1 + cum_returns)
            drawdown_paths[i, :] = (1 + cum_returns) / peak - 1
        
        # Log summary of results
        self.logger.info(f"Monte Carlo simulation completed with {iterations} iterations")
        self.logger.info(f"Median final return: {percentile_values['return_50pct']*100:.2f}%")
        self.logger.info(f"5th percentile return: {percentile_values['return_5pct']*100:.2f}%")
        self.logger.info(f"Median max drawdown: {percentile_values['drawdown_50pct']*100:.2f}%")
        self.logger.info(f"95th percentile max drawdown: {percentile_values['drawdown_95pct']*100:.2f}%")
        
        # Create result object
        result = MonteCarloResult(
            iterations=iterations,
            original_returns=returns,
            return_paths=return_paths,
            drawdown_paths=drawdown_paths,
            final_returns=final_returns,
            max_drawdowns=max_drawdowns,
            sharpe_ratios=sharpe_ratios,
            percentiles=percentile_values
        )
        
        return result
    
    def run_block_bootstrap(self, 
                           returns: List[float], 
                           block_size: int = 5,
                           iterations: int = 1000,
                           sample_pct: float = 100.0) -> MonteCarloResult:
        """
        Run block bootstrap Monte Carlo simulation
        This preserves some of the autocorrelation in returns
        
        Args:
            returns: List of trade returns (as percentage or fraction)
            block_size: Size of blocks to sample
            iterations: Number of Monte Carlo iterations
            sample_pct: Percentage of trades to sample in each iteration (100 = all)
            
        Returns:
            MonteCarloResult object with simulation results
        """
        self.logger.info(f"Starting block bootstrap simulation with {iterations} iterations")
        self.logger.info(f"Block size: {block_size}")
        
        if not returns or len(returns) < block_size:
            self.logger.error(f"Not enough returns for block bootstrap with block size {block_size}")
            return None
        
        # Ensure returns are numpy array
        returns_array = np.array(returns)
        
        # Calculate number of trades to sample
        n_trades = max(block_size, int(len(returns) * (sample_pct / 100)))
        # Adjust to be a multiple of block_size
        n_trades = (n_trades // block_size) * block_size
        
        # Number of blocks
        n_blocks = n_trades // block_size
        
        # Create blocks
        blocks = []
        for i in range(len(returns_array) - block_size + 1):
            blocks.append(returns_array[i:i+block_size])
        
        # Initialize arrays for results
        return_paths = np.zeros((iterations, n_trades))
        final_returns = np.zeros(iterations)
        max_drawdowns = np.zeros(iterations)
        sharpe_ratios = np.zeros(iterations)
        
        # Run simulation iterations
        for i in tqdm(range(iterations), desc="Block Bootstrap Simulation"):
            # Sample blocks
            sampled_blocks = [blocks[j] for j in np.random.randint(0, len(blocks), n_blocks)]
            
            # Flatten blocks
            sampled_returns = np.concatenate(sampled_blocks)
            
            # Store resampled returns
            return_paths[i, :] = sampled_returns
            
            # Calculate cumulative returns
            cum_returns = np.cumprod(1 + sampled_returns) - 1
            
            # Calculate drawdowns
            peak = np.maximum.accumulate(1 + cum_returns)
            drawdown = (1 + cum_returns) / peak - 1
            
            # Store results
            final_returns[i] = cum_returns[-1] if len(cum_returns) > 0 else 0
            max_drawdowns[i] = np.min(drawdown) if len(drawdown) > 0 else 0
            sharpe_ratios[i] = np.mean(sampled_returns) / np.std(sampled_returns) * np.sqrt(252) \
                              if np.std(sampled_returns) > 0 else 0
        
        # Calculate percentiles (same as regular simulation)
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_values = {
            f"return_{p}pct": np.percentile(final_returns, p) 
            for p in percentiles
        }
        percentile_values.update({
            f"drawdown_{p}pct": np.percentile(max_drawdowns, p)
            for p in percentiles
        })
        
        # Calculate drawdown paths
        drawdown_paths = np.zeros_like(return_paths)
        for i in range(iterations):
            cum_returns = np.cumprod(1 + return_paths[i, :]) - 1
            peak = np.maximum.accumulate(1 + cum_returns)
            drawdown_paths[i, :] = (1 + cum_returns) / peak - 1
        
        # Create result object
        result = MonteCarloResult(
            iterations=iterations,
            original_returns=returns,
            return_paths=return_paths,
            drawdown_paths=drawdown_paths,
            final_returns=final_returns,
            max_drawdowns=max_drawdowns,
            sharpe_ratios=sharpe_ratios,
            percentiles=percentile_values
        )
        
        return result
    
    def visualize_results(self, result: MonteCarloResult) -> plt.Figure:
        """
        Create visualization of Monte Carlo simulation results
        
        Args:
            result: MonteCarloResult from run_simulation
            
        Returns:
            matplotlib Figure object
        """
        if result is None:
            self.logger.error("No Monte Carlo results to visualize")
            return None
        
        # Set style
        plt.style.use('ggplot')
        sns.set_palette("viridis")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 12))
        
        # Plot 1: Return paths
        ax1 = fig.add_subplot(2, 2, 1)
        
        # Plot a subset of paths
        n_paths_to_plot = min(100, result.iterations)
        indices = np.random.choice(range(result.iterations), n_paths_to_plot, replace=False)
        
        for i in indices:
            cum_returns = np.cumprod(1 + result.return_paths[i, :]) - 1
            ax1.plot(cum_returns, alpha=0.1, color='blue')
        
        # Plot percentile lines
        percentiles_to_plot = [5, 50, 95]
        colors = ['red', 'black', 'green']
        labels = ['5th Percentile', 'Median', '95th Percentile']
        
        for p_idx, p in enumerate(percentiles_to_plot):
            # Calculate percentile path
            p_path = np.zeros(result.return_paths.shape[1])
            for j in range(result.return_paths.shape[1]):
                cum_returns = np.array([np.cumprod(1 + result.return_paths[i, :j+1])[-1] - 1 
                                       for i in range(result.iterations)])
                p_path[j] = np.percentile(cum_returns, p)
            
            ax1.plot(p_path, linewidth=2, color=colors[p_idx], label=labels[p_idx])
        
        ax1.set_title('Monte Carlo Return Paths')
        ax1.set_xlabel('Trade #')
        ax1.set_ylabel('Cumulative Return')
        ax1.legend()
        ax1.grid(True)
        
        # Plot 2: Distribution of final returns
        ax2 = fig.add_subplot(2, 2, 2)
        
        sns.histplot(result.final_returns, kde=True, ax=ax2, bins=30)
        
        # Add vertical lines for percentiles
        percentiles_to_mark = [5, 50, 95]
        colors = ['red', 'black', 'green']
        
        for p_idx, p in enumerate(percentiles_to_mark):
            p_value = result.percentiles[f'return_{p}pct']
            ax2.axvline(p_value, color=colors[p_idx], linestyle='--', 
                       label=f'{p}th Percentile: {p_value*100:.2f}%')
        
        ax2.set_title('Distribution of Final Returns')
        ax2.set_xlabel('Return')
        ax2.set_ylabel('Frequency')
        ax2.legend()
        
        # Plot 3: Distribution of maximum drawdowns
        ax3 = fig.add_subplot(2, 2, 3)
        
        sns.histplot(result.max_drawdowns, kde=True, ax=ax3, bins=30)
        
        # Add vertical lines for percentiles
        for p_idx, p in enumerate(percentiles_to_mark):
            p_value = result.percentiles[f'drawdown_{p}pct']
            ax3.axvline(p_value, color=colors[p_idx], linestyle='--', 
                       label=f'{p}th Percentile: {p_value*100:.2f}%')
        
        ax3.set_title('Distribution of Maximum Drawdowns')
        ax3.set_xlabel('Drawdown')
        ax3.set_ylabel('Frequency')
        ax3.legend()
        
        # Plot 4: Return vs Drawdown scatter
        ax4 = fig.add_subplot(2, 2, 4)
        
        ax4.scatter(result.max_drawdowns, result.final_returns, alpha=0.5)
        
        # Add a line through origin with slope -1 (return = drawdown)
        max_dd = np.min(result.max_drawdowns)
        ax4.plot([max_dd, 0], [0, 0], 'k--', alpha=0.5)
        
        # Calculate correlation
        corr = np.corrcoef(result.max_drawdowns, result.final_returns)[0, 1]
        
        ax4.set_title(f'Return vs Drawdown (correlation: {corr:.2f})')
        ax4.set_xlabel('Maximum Drawdown')
        ax4.set_ylabel('Final Return')
        ax4.grid(True)
        
        # Add title
        fig.suptitle(
            f"Monte Carlo Simulation Results\n"
            f"{result.iterations} iterations with {result.return_paths.shape[1]} trades per path",
            fontsize=16
        )
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        return fig
    
    def simulate_equity_curves(self, 
                              capital: float, 
                              returns: List[float], 
                              iterations: int = 1000,
                              holding_periods: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Simulate equity curves with variable holding periods
        
        Args:
            capital: Initial capital
            returns: List of returns (as percentage or fraction)
            iterations: Number of simulation iterations
            holding_periods: Optional list of holding periods in days for each trade
                            If None, assumes trades are sequential
            
        Returns:
            DataFrame with simulated equity curves
        """
        if not returns:
            self.logger.error("No returns provided for simulation")
            return None
        
        # Default holding periods
        if holding_periods is None:
            holding_periods = [1] * len(returns)
        
        # Ensure lists are the same length
        if len(returns) != len(holding_periods):
            self.logger.error("Returns and holding periods must be same length")
            return None
        
        # Convert to arrays
        returns_array = np.array(returns)
        holding_periods_array = np.array(holding_periods)
        
        # Calculate total trading days
        total_days = np.sum(holding_periods_array)
        
        # Create empty dataframe for equity curves
        equity_curves = pd.DataFrame(index=range(total_days))
        
        # Run simulations
        for i in tqdm(range(iterations), desc="Simulating Equity Curves"):
            # Shuffle the order of trades
            indices = np.random.permutation(len(returns))
            shuffled_returns = returns_array[indices]
            shuffled_holding_periods = holding_periods_array[indices]
            
            # Create a daily equity curve
            equity = np.ones(total_days) * capital
            day_counter = 0
            
            for j, (r, hp) in enumerate(zip(shuffled_returns, shuffled_holding_periods)):
                # Apply return over the holding period
                daily_return = (1 + r) ** (1 / hp) - 1
                
                for d in range(hp):
                    if day_counter < total_days:
                        equity[day_counter] = equity[day_counter - 1] * (1 + daily_return) if day_counter > 0 else capital * (1 + daily_return)
                        day_counter += 1
            
            # Add to dataframe
            equity_curves[f'sim_{i}'] = equity
        
        # Calculate percentiles
        for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
            equity_curves[f'p{p}'] = equity_curves.iloc[:, :iterations].quantile(p/100, axis=1)
        
        return equity_curves
    
    def calculate_confidence_interval(self,
                                    result: MonteCarloResult,
                                    confidence: float = 0.95) -> Dict:
        """
        Calculate confidence intervals for key metrics
        
        Args:
            result: MonteCarloResult from simulation
            confidence: Confidence level (0-1)
            
        Returns:
            Dictionary with confidence intervals
        """
        if result is None:
            self.logger.error("No Monte Carlo results for confidence intervals")
            return None
        
        alpha = 1 - confidence
        
        # Calculate intervals
        final_return_interval = stats.t.interval(
            confidence, 
            len(result.final_returns) - 1,
            loc=np.mean(result.final_returns),
            scale=stats.sem(result.final_returns)
        )
        
        max_drawdown_interval = stats.t.interval(
            confidence, 
            len(result.max_drawdowns) - 1,
            loc=np.mean(result.max_drawdowns),
            scale=stats.sem(result.max_drawdowns)
        )
        
        sharpe_interval = stats.t.interval(
            confidence, 
            len(result.sharpe_ratios) - 1,
            loc=np.mean(result.sharpe_ratios),
            scale=stats.sem(result.sharpe_ratios)
        )
        
        # Create result dictionary
        intervals = {
            'confidence': confidence,
            'final_return': {
                'mean': np.mean(result.final_returns),
                'lower': final_return_interval[0],
                'upper': final_return_interval[1]
            },
            'max_drawdown': {
                'mean': np.mean(result.max_drawdowns),
                'lower': max_drawdown_interval[0],
                'upper': max_drawdown_interval[1]
            },
            'sharpe_ratio': {
                'mean': np.mean(result.sharpe_ratios),
                'lower': sharpe_interval[0],
                'upper': sharpe_interval[1]
            }
        }
        
        # Log results
        self.logger.info(f"{confidence*100}% Confidence Intervals:")
        self.logger.info(f"Final Return: {intervals['final_return']['lower']*100:.2f}% to {intervals['final_return']['upper']*100:.2f}%")
        self.logger.info(f"Max Drawdown: {intervals['max_drawdown']['lower']*100:.2f}% to {intervals['max_drawdown']['upper']*100:.2f}%")
        self.logger.info(f"Sharpe Ratio: {intervals['sharpe_ratio']['lower']:.2f} to {intervals['sharpe_ratio']['upper']:.2f}")
        
        return intervals
    
    def estimate_var_cvar(self,
                        result: MonteCarloResult,
                        confidence: float = 0.95) -> Dict:
        """
        Calculate Value at Risk (VaR) and Conditional Value at Risk (CVaR)
        
        Args:
            result: MonteCarloResult from simulation
            confidence: Confidence level (0-1)
            
        Returns:
            Dictionary with VaR and CVaR
        """
        if result is None:
            self.logger.error("No Monte Carlo results for VaR/CVaR calculation")
            return None
        
        # Sort returns
        sorted_returns = np.sort(result.final_returns)
        
        # Calculate VaR index
        var_index = int(np.floor((1 - confidence) * len(sorted_returns)))
        
        # Calculate VaR
        var = -sorted_returns[var_index]
        
        # Calculate CVaR (average of returns beyond VaR)
        cvar = -np.mean(sorted_returns[:var_index+1])
        
        # Create result dictionary
        risk_metrics = {
            'confidence': confidence,
            'var': var,
            'cvar': cvar,
            'var_percentile': (1 - confidence) * 100
        }
        
        # Log results
        self.logger.info(f"Value at Risk ({confidence*100}%): {var*100:.2f}%")
        self.logger.info(f"Conditional VaR ({confidence*100}%): {cvar*100:.2f}%")
        
        return risk_metrics
    
    def save_results(self, result: MonteCarloResult, filepath: str) -> bool:
        """
        Save Monte Carlo results to file
        
        Args:
            result: MonteCarloResult to save
            filepath: Path to save file
            
        Returns:
            True if successful
        """
        if result is None:
            self.logger.error("No Monte Carlo results to save")
            return False
        
        try:
            # Convert to dictionary (excluding large arrays)
            result_dict = result.to_dict()
            
            # Save to file
            pd.to_pickle(result, filepath)
            self.logger.info(f"Monte Carlo results saved to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving Monte Carlo results: {e}")
            return False
    
    def load_results(self, filepath: str) -> MonteCarloResult:
        """
        Load Monte Carlo results from file
        
        Args:
            filepath: Path to load file
            
        Returns:
            MonteCarloResult object
        """
        try:
            # Load from file
            result = pd.read_pickle(filepath)
            self.logger.info(f"Monte Carlo results loaded from {filepath}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error loading Monte Carlo results: {e}")
            return None


if __name__ == "__main__":
    # Example usage
    pass
