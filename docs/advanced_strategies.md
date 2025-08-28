# Advanced Trading Strategies Guide

This document explains the advanced trading strategies implemented in the latest version of the IQ-720 Trading Bot.

## Table of Contents

1. [Return Prediction](#return-prediction)
2. [Adaptive Exit Strategies](#adaptive-exit-strategies)
3. [Position Sizing](#position-sizing)
4. [Market Availability Management](#market-availability-management)
5. [Configuration Guide](#configuration-guide)

## Return Prediction

The return prediction module goes beyond simple binary (UP/DOWN) predictions and estimates the expected return magnitude for each trade.

### Key Features

- **Expected Return Estimation**: Predicts the magnitude of price movement, not just direction
- **Probabilistic Distribution**: Provides a distribution of potential outcomes
- **Risk-Reward Assessment**: Enables better trade selection based on potential reward
- **Return-Based Confidence**: Adjusts confidence based on predicted return magnitude

### How It Works

1. Multiple regression models estimate the expected price movement
2. Historical volatility is used to create a distribution of potential outcomes
3. The probability of reaching various profit targets is calculated
4. Trades are only taken if the expected return meets minimum thresholds

## Adaptive Exit Strategies

The adaptive exit strategies module dynamically adjusts stop-loss and take-profit levels based on market conditions.

### Exit Strategy Types

- **Fixed**: Simple fixed percentage stop-loss and take-profit
- **Volatility-Based**: Adjusts exit levels based on current market volatility
- **Prediction-Based**: Sets targets based on ML-predicted price movement
- **Time-Based**: Adjusts expiry times based on market conditions
- **Trailing**: Implements trailing stops that follow the price movement
- **Combined**: Uses a combination of the above strategies for optimal exits

### Dynamic Adjustments

- Higher volatility → Wider stops to avoid premature exits
- Strong predictions → Tighter stops and more ambitious targets
- Trending markets → Trailing stops to capture more movement
- Ranging markets → Fixed targets to capture predictable reversals

## Position Sizing

The position sizing module implements intelligent sizing strategies to optimize risk management.

### Sizing Methods

- **Fixed**: Simple fixed percentage of account balance
- **Fixed Risk**: Adjusts position size to risk a fixed percentage of account
- **Kelly Criterion**: Mathematical formula for optimal bet sizing
- **Fractional Kelly**: Conservative version of Kelly (half-Kelly)
- **Dynamic**: Adaptive sizing based on multiple factors
- **Drawdown-Adjusted**: Reduces position sizes during drawdown periods
- **Confidence-Based**: Adjusts size based on prediction confidence
- **Volatility-Scaled**: Inversely scales position with market volatility

### Kelly Criterion Implementation

The Kelly Criterion calculates optimal position size using:
- Win probability (from ML predictions)
- Win/loss ratio (from historical performance)
- Expected return (from return prediction)

Formula: `Kelly Fraction = (p * b - q) / b`
- `p` = win probability
- `q` = loss probability (1 - p)
- `b` = win/loss ratio

For safety, we implement Half-Kelly (50% of the calculated Kelly value) by default.

## Market Availability Management

The market availability module ensures we only trade when markets are available and differentiates between regular and OTC markets.

### Features

- **Market Hours**: Tracks trading hours for different market types
- **OTC Detection**: Identifies Over-The-Counter markets (-OTC suffix)
- **Market Type Notification**: Includes market type in Telegram messages
- **Holiday Calendar**: Avoids trading on major market holidays
- **Session Awareness**: Adjusts for Asian, London, and New York sessions

### Market Types

1. **Regular Markets**: Standard forex markets following normal trading hours
   - Trading hours: Monday to Friday, variable hours
   - Example pairs: EURUSD, GBPUSD, USDJPY

2. **OTC Markets**: Over-The-Counter markets with extended availability
   - Trading hours: Generally available 7 days a week
   - Example pairs: EURUSD-OTC, GBPUSD-OTC, USDJPY-OTC
   - Identified by "-OTC" suffix in pair name

## Configuration Guide

The advanced trading strategies can be configured in the `config_advanced.json` file. Here are the key parameters:

### Trading Strategy Settings

```json
"trading_strategy": {
    "trading_mode": "balanced",
    "min_confidence": 0.65,
    "min_correlation_confirmation": 0.6,
    "use_market_regime": true,
    "check_market_availability": true,
    "position_sizing_method": "fractional_kelly",
    "exit_strategy_type": "combined",
    "max_active_trades": 3,
    "required_correlation_pairs": 2
}
```

- `trading_mode`: Overall risk approach (conservative/balanced/aggressive/adaptive)
- `min_confidence`: Minimum prediction confidence threshold
- `min_correlation_confirmation`: Minimum correlation confirmation level
- `position_sizing_method`: Position sizing algorithm to use
- `exit_strategy_type`: Exit strategy type to use

### Exit Strategy Settings

```json
"exit_strategies": {
    "default_stop_loss": 0.02,
    "default_take_profit": 0.04,
    "volatility_multiplier": 2.0,
    "trailing_activation": 0.5,
    "trailing_step": 0.2
}
```

- `default_stop_loss`: Default stop loss percentage (2%)
- `default_take_profit`: Default take profit percentage (4%)
- `volatility_multiplier`: Multiplier for volatility-based exits
- `trailing_activation`: When trailing stop activates (50% of take profit)
- `trailing_step`: How much trailing stop follows price (20% of movement)

### Position Sizing Settings

```json
"position_sizing": {
    "default_risk_per_trade": 0.02,
    "max_risk_per_trade": 0.05,
    "min_trade_size": 1.0,
    "kelly_fraction": 0.5,
    "max_exposure": 0.25,
    "drawdown_scaling_enabled": true,
    "max_consecutive_losses": 3
}
```

- `default_risk_per_trade`: Default risk per trade (2%)
- `max_risk_per_trade`: Maximum risk per trade (5%)
- `kelly_fraction`: Fraction of Kelly to use (0.5 = Half-Kelly)
- `max_exposure`: Maximum account exposure (25%)
- `drawdown_scaling_enabled`: Reduce position sizes during drawdowns
- `max_consecutive_losses`: Reduce after consecutive losses
