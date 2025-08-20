"""
Risk Management Demo Script.
Demonstrates the dynamic risk management system with simulated market scenarios.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.utils.trade_tracker import TradeTracker, Trade
from src.utils.market_analyzer import MarketAnalyzer
from src.utils.dynamic_risk_manager import DynamicRiskManager, RiskParameters
from src.trade_executor import TradeExecutor, ExecutionParameters
from src.signal_generator import Signal

def simulate_market_conditions(market_analyzer: MarketAnalyzer, scenario: str):
    """Simulate different market conditions."""
    candles = []
    base_price = 1.2000
    timestamp = datetime.now()
    
    if scenario == "trending_up":
        # Strong uptrend with moderate volatility
        volatility = 0.0002
        for i in range(50):
            price = base_price + (i * 0.0002) + np.random.normal(0, volatility)
            candles.append({
                'timestamp': timestamp + timedelta(minutes=i),
                'open': price - volatility,
                'high': price + volatility * 2,
                'low': price - volatility * 2,
                'close': price,
                'volume': 1000 + np.random.randint(-200, 200)
            })
            
    elif scenario == "ranging":
        # Range-bound with low volatility
        volatility = 0.0001
        for i in range(50):
            oscillation = 0.0004 * np.sin(i / 8)
            price = base_price + oscillation + np.random.normal(0, volatility)
            candles.append({
                'timestamp': timestamp + timedelta(minutes=i),
                'open': price - volatility,
                'high': price + volatility * 2,
                'low': price - volatility * 2,
                'close': price,
                'volume': 800 + np.random.randint(-100, 100)
            })
            
    elif scenario == "volatile":
        # High volatility with sharp moves
        volatility = 0.0004
        for i in range(50):
            shock = 0.0008 if np.random.random() < 0.1 else 0
            price = base_price + np.random.normal(0, volatility) + shock
            candles.append({
                'timestamp': timestamp + timedelta(minutes=i),
                'open': price - volatility,
                'high': price + volatility * 3,
                'low': price - volatility * 3,
                'close': price,
                'volume': 1500 + np.random.randint(-300, 300)
            })
    
    # Feed candles to market analyzer
    for candle in candles:
        market_analyzer.add_candle(candle)
    
    return candles

def simulate_trades(scenario_name: str, win_rate: float = 0.6):
    """Simulate a sequence of trades with given win rate."""
    trades = []
    base_price = 1.2000
    timestamp = datetime.now() - timedelta(days=7)
    
    for i in range(20):
        is_win = np.random.random() < win_rate
        entry_price = base_price + np.random.normal(0, 0.0002)
        
        if is_win:
            exit_price = entry_price + 0.0020  # 20 pip win
            profit = 20.0
        else:
            exit_price = entry_price - 0.0030  # 30 pip loss
            profit = -30.0
            
        trade = Trade(
            id=f"hist_trade_{i}",
            symbol="EUR/USD",
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=timestamp + timedelta(hours=i*4),
            exit_time=timestamp + timedelta(hours=i*4 + 2),
            position_size=1.0,
            direction="buy",
            status="closed",
            profit_loss=profit,
            tags=["historical"]
        )
        trades.append(trade)
    
    return trades

def run_demo():
    """Run the risk management demonstration."""
    print("\n=== Dynamic Risk Management Demo ===\n")
    
    # Initialize components
    trade_tracker = TradeTracker()
    market_analyzer = MarketAnalyzer()
    
    risk_params = RiskParameters(
        base_position_size=1.0,
        max_position_size=2.0,
        min_position_size=0.1,
        max_risk_per_trade=0.02,
        max_total_risk=0.06
    )
    
    exec_params = ExecutionParameters(
        min_confidence=0.6,
        max_daily_trades=10,
        min_time_between_trades=15,
        recovery_mode_threshold=3
    )
    
    executor = TradeExecutor(
        trade_tracker=trade_tracker,
        market_analyzer=market_analyzer,
        risk_params=risk_params,
        execution_params=exec_params
    )
    
    # Scenario 1: Normal Market with Good Performance
    print("\n1. Normal Market with Good Performance")
    print("--------------------------------------")
    
    # Add historical trades with good performance
    historical_trades = simulate_trades(
        scenario_name="normal",
        win_rate=0.7
    )
    for trade in historical_trades:
        trade_tracker.track_trade(trade)
    
    # Simulate trending market
    print("\nSimulating trending market conditions...")
    candles = simulate_market_conditions(market_analyzer, "trending_up")
    
    # Generate and execute signals
    print("\nExecuting trades in trending market:")
    base_time = datetime.now()
    for i in range(5):
        signal = Signal(
            timestamp=base_time + timedelta(minutes=i*20),
            direction="BUY",
            asset="EUR/USD",
            expiry_minutes=60,
            confidence=0.8,
            indicators={
                'entry_price': candles[i]['close'],
                'trend': 'up',
                'momentum': 'strong'
            }
        )
        
        trade = executor.process_signal(signal)
        if trade:
            print(f"Trade {i+1}: Position Size = {trade.position_size:.2f}")
            # Simulate trade completion
            pnl = 20.0 if np.random.random() < 0.7 else -15.0
            executor.close_trade(
                trade.id,
                exit_price=trade.entry_price + (0.0001 * pnl),
                exit_time=signal.timestamp + timedelta(minutes=30)
            )
    
    # Scenario 2: Volatile Market after Drawdown
    print("\n2. Volatile Market after Drawdown")
    print("--------------------------------")
    
    # Add some losing trades
    drawdown_trades = simulate_trades(
        scenario_name="drawdown",
        win_rate=0.3
    )
    for trade in drawdown_trades[-5:]:  # Add last 5 trades
        trade_tracker.track_trade(trade)
    
    # Simulate volatile market
    print("\nSimulating volatile market conditions...")
    candles = simulate_market_conditions(market_analyzer, "volatile")
    
    # Generate and execute signals
    print("\nExecuting trades in volatile market:")
    base_time = datetime.now()
    for i in range(5):
        signal = Signal(
            timestamp=base_time + timedelta(minutes=i*20),
            direction="BUY",
            asset="EUR/USD",
            expiry_minutes=60,
            confidence=0.7,
            indicators={
                'entry_price': candles[i]['close'],
                'trend': 'unclear',
                'volatility': 'high'
            }
        )
        
        trade = executor.process_signal(signal)
        if trade:
            print(f"Trade {i+1}: Position Size = {trade.position_size:.2f}")
            # Simulate trade completion
            pnl = 25.0 if np.random.random() < 0.5 else -20.0
            executor.close_trade(
                trade.id,
                exit_price=trade.entry_price + (0.0001 * pnl),
                exit_time=signal.timestamp + timedelta(minutes=30)
            )
    
    # Scenario 3: Range-bound Market Recovery
    print("\n3. Range-bound Market Recovery")
    print("-----------------------------")
    
    # Add some mixed performance trades
    recovery_trades = simulate_trades(
        scenario_name="recovery",
        win_rate=0.6
    )
    for trade in recovery_trades[-10:]:  # Add last 10 trades
        trade_tracker.track_trade(trade)
    
    # Simulate ranging market
    print("\nSimulating range-bound market conditions...")
    candles = simulate_market_conditions(market_analyzer, "ranging")
    
    # Generate and execute signals
    print("\nExecuting trades in ranging market:")
    base_time = datetime.now()
    for i in range(5):
        signal = Signal(
            timestamp=base_time + timedelta(minutes=i*20),
            direction="BUY",
            asset="EUR/USD",
            expiry_minutes=60,
            confidence=0.75,
            indicators={
                'entry_price': candles[i]['close'],
                'trend': 'ranging',
                'volatility': 'low'
            }
        )
        
        trade = executor.process_signal(signal)
        if trade:
            print(f"Trade {i+1}: Position Size = {trade.position_size:.2f}")
            # Simulate trade completion
            pnl = 15.0 if np.random.random() < 0.6 else -12.0
            executor.close_trade(
                trade.id,
                exit_price=trade.entry_price + (0.0001 * pnl),
                exit_time=signal.timestamp + timedelta(minutes=30)
            )
    
    # Print final statistics
    print("\nFinal Trading Statistics")
    print("----------------------")
    stats = trade_tracker.get_stats("total")
    print(f"Total Trades: {stats.total_trades}")
    print(f"Win Rate: {stats.win_rate:.2%}")
    print(f"Profit Factor: {stats.profit_factor:.2f}")
    print(f"Max Drawdown: {stats.max_drawdown:.2%}")
    print(f"Average Win: {stats.avg_win:.1f} pips")
    print(f"Average Loss: {abs(stats.avg_loss):.1f} pips")

if __name__ == "__main__":
    run_demo()
