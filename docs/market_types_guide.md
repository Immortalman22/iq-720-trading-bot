# IQ 720 Trading Bot - Market Types Guide

## Understanding Market Types in IQ Option

IQ Option offers two types of markets for trading currencies:

1. **Regular Markets** - These follow standard forex market hours and are typically open from Sunday evening to Friday evening (22:00 Sunday to 22:00 Friday UTC).

2. **OTC Markets** (Over-The-Counter) - These are synthetic markets provided by IQ Option that may be available outside regular market hours, including weekends.

## How the Bot Handles Market Types

The IQ 720 Trading Bot has been enhanced to automatically:

1. **Detect Available Markets** - The bot checks whether a pair is available for trading as either a regular or OTC market based on the current time.

2. **Display Market Type in Signals** - All signals now clearly indicate whether they are for regular (🟢) or OTC (🟠) markets.

3. **Filter Closed Markets** - The bot only analyzes and generates signals for currently available markets, preventing signals for closed markets.

4. **Adapt to Weekends** - On weekends, the bot automatically switches to analyzing only OTC markets that are available.

## Market Availability Configuration

The bot uses the `market_schedule.yaml` file to determine market availability. This file contains:

- Trading hours for regular and OTC markets
- Weekend availability settings
- Pair-specific availability for both regular and OTC markets

Example configuration:

```yaml
forex:
  regular:
    sunday_open: "22:00"   # Regular markets open Sunday evening UTC
    friday_close: "22:00"  # Regular markets close Friday evening UTC
    weekend: false         # Regular markets not available on weekends
    
  otc:
    weekend: true          # OTC markets available on weekends
    weekend_open: "00:00"  # OTC markets open all weekend
    weekend_close: "23:59"

pairs:
  EUR/USD:
    regular: true
    otc: true             # EUR/USD is available as both regular and OTC
  USD/ZAR:
    regular: true
    otc: false            # USD/ZAR only available as regular market
```

## Recommended Best Practices

1. **Regular Markets During Standard Hours** - For major pairs like EUR/USD, GBP/USD, etc., regular markets generally offer better liquidity during standard trading hours.

2. **OTC Markets for Weekends** - If you want to trade on weekends, use the OTC markets. Be aware that OTC markets may behave differently than regular markets.

3. **Updating Market Availability** - If you notice a pair is not available on IQ Option when the bot says it should be (or vice versa), update the `market_schedule.yaml` file accordingly.

## Example: How to Read Signal Messages

The bot's Telegram notifications now include market type information:

```
🚨 TRADING SIGNAL 🚨

Asset: EUR/USD (🟢 Regular)
Direction: 📈 BUY
Expiry: 5 minute(s)
Confidence: ⭐⭐⭐⭐ (87.50%)

Technical Indicators:
RSI: 28.45
MACD: 0.00123
Volume: 1.35x average
Market Regime: TRENDING
```

```
🚨 TRADING SIGNAL 🚨

Asset: GBP/USD (🟠 OTC)
Direction: 📉 SELL
Expiry: 5 minute(s)
Confidence: ⭐⭐⭐ (65.25%)

Technical Indicators:
RSI: 73.12
MACD: -0.00087
Volume: 0.95x average
Market Regime: RANGING
```

## Troubleshooting

If you receive signals for markets that appear to be closed on IQ Option:

1. **Check the Market Type** - Make sure you're looking at the right market type (Regular or OTC) as indicated in the signal.

2. **Update Market Schedule** - Edit the `market_schedule.yaml` file to reflect the actual availability of markets on IQ Option.

3. **Timezone Issues** - Verify that your system's timezone settings are correct. The bot uses UTC for all time calculations.

4. **IQ Option Platform Changes** - IQ Option may occasionally change their market availability. Keep the configuration updated.
