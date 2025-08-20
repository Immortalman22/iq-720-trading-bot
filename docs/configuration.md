# Configuration Guide

This guide provides detailed information about configuring and tuning the IQ-720 Trading Bot.

## Table of Contents
- [Basic Configuration](#basic-configuration)
- [Trading Parameters](#trading-parameters)
- [Risk Management](#risk-management)
- [Technical Analysis](#technical-analysis)
- [Monitoring & Alerts](#monitoring--alerts)
- [Backup Configuration](#backup-configuration)
- [Advanced Settings](#advanced-settings)

## Basic Configuration

### Environment Variables (.env)

#### Essential Settings
```ini
# API Configuration
API_KEY=your_api_key
API_SECRET=your_api_secret
TRADE_MODE=live  # or 'paper' for paper trading

# Basic Trading Parameters
TRADING_PAIRS=BTC/USDT,ETH/USDT,XRP/USDT
BASE_CURRENCY=USDT
QUOTE_CURRENCIES=BTC,ETH,XRP

# Operation Mode
TRADING_ENABLED=true
BACKTEST_MODE=false
```

#### Logging Configuration
```ini
# Logging Settings
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=detailed  # basic, detailed, json
LOG_RETENTION_DAYS=30
ENABLE_TRADE_LOGS=true
ENABLE_PERFORMANCE_LOGS=true
```

## Trading Parameters

### Position Sizing
```ini
# Position Limits
MAX_POSITION_SIZE=1000  # Maximum position size in USDT
MIN_POSITION_SIZE=10    # Minimum position size in USDT
MAX_POSITIONS=5         # Maximum concurrent positions

# Order Configuration
ORDER_TYPE=LIMIT       # MARKET, LIMIT
SLIPPAGE_TOLERANCE=0.1 # Maximum allowed slippage %
```

### Trading Timeframes
```ini
# Analysis Timeframes
PRIMARY_TIMEFRAME=1h    # Primary analysis timeframe
SECONDARY_TIMEFRAME=15m # Secondary confirmation timeframe
TREND_TIMEFRAME=4h     # Trend analysis timeframe
```

## Risk Management

### Risk Parameters
```ini
# Risk Limits
RISK_LEVEL=3                 # 1-5 (1:conservative, 5:aggressive)
MAX_DRAWDOWN=10              # Maximum allowed drawdown %
POSITION_RISK_PERCENT=2      # Risk per trade %
DAILY_RISK_LIMIT=5          # Maximum daily risk %
WEEKLY_RISK_LIMIT=20        # Maximum weekly risk %

# Stop Loss Configuration
ENABLE_STOP_LOSS=true
STOP_LOSS_TYPE=TRAILING    # FIXED, TRAILING, ATR
STOP_LOSS_PERCENT=2        # Initial stop loss %
TRAILING_STOP_ACTIVATION=1 # Profit % to activate trailing
```

### Dynamic Risk Management
```ini
# Dynamic Risk Adjustment
ENABLE_DYNAMIC_RISK=true
VOLATILITY_ADJUSTMENT=true
TREND_RISK_ADJUSTMENT=true
WIN_RATE_SCALING=true

# Recovery Mode
ENABLE_RECOVERY_MODE=true
MAX_RECOVERY_ATTEMPTS=3
RECOVERY_RISK_REDUCTION=50  # Reduce risk by % in recovery
```

## Technical Analysis

### Indicator Configuration
```ini
# RSI Settings
RSI_PERIOD=14
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30

# MACD Settings
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9

# Bollinger Bands
BB_PERIOD=20
BB_STD_DEV=2
```

### Volume Analysis
```ini
# Volume Requirements
MIN_24H_VOLUME=1000000     # Minimum 24h volume in USDT
VOLUME_MA_PERIOD=20        # Volume moving average period
VOLUME_VARIANCE_LIMIT=200  # Maximum allowed volume variance %
```

## Monitoring & Alerts

### Telegram Notifications
```ini
# Telegram Settings
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
NOTIFICATION_LEVEL=IMPORTANT  # ALL, IMPORTANT, CRITICAL
QUIET_HOURS_START=23         # Hour to start quiet period
QUIET_HOURS_END=7           # Hour to end quiet period
```

### Health Monitoring
```ini
# Health Check Configuration
HEALTH_CHECK_INTERVAL=30    # Seconds between health checks
HEALTH_CHECK_TIMEOUT=10     # Health check timeout seconds
MAX_HEALTH_FAILURES=3       # Failures before restart
```

### Prometheus Metrics
```ini
# Metrics Configuration
ENABLE_METRICS=true
METRICS_PORT=9090
METRICS_PATH=/metrics
COLLECT_DETAILED_METRICS=true
```

## Backup Configuration

### Automated Backups
```ini
# Backup Settings
BACKUP_ENABLED=true
BACKUP_INTERVAL=24        # Hours between backups
BACKUP_RETENTION_DAYS=30  # Days to keep backups

# S3 Configuration (if using S3)
S3_BUCKET=your-backup-bucket
S3_PREFIX=trading-bot/
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

## Advanced Settings

### Performance Optimization
```ini
# System Resources
MAX_MEMORY_USAGE=4096    # Maximum memory usage in MB
CPU_THREAD_LIMIT=4       # Maximum CPU threads
DISK_SPACE_LIMIT=20      # Maximum disk usage in GB

# Cache Settings
ENABLE_CACHE=true
CACHE_TTL=300           # Cache time-to-live in seconds
MAX_CACHE_SIZE=1000     # Maximum cache entries
```

### Network Configuration
```ini
# API Rate Limiting
MAX_REQUESTS_PER_MIN=60
RATE_LIMIT_STRATEGY=ADAPTIVE  # FIXED, ADAPTIVE
RETRY_ATTEMPTS=3
RETRY_DELAY=1                 # Seconds between retries

# WebSocket Settings
WEBSOCKET_RECONNECT_ATTEMPTS=3
WEBSOCKET_PING_INTERVAL=30
```

### Error Handling
```ini
# Error Management
MAX_ERROR_RETRIES=3
ERROR_COOLDOWN=300      # Seconds to wait after max retries
CRITICAL_ERRORS=CONNECTION,API_ERROR,INSUFFICIENT_FUNDS
```

## Example Configurations

### Conservative Setup
```ini
RISK_LEVEL=1
MAX_POSITION_SIZE=500
POSITION_RISK_PERCENT=1
STOP_LOSS_PERCENT=1.5
TRAILING_STOP_ACTIVATION=0.5
```

### Aggressive Setup
```ini
RISK_LEVEL=4
MAX_POSITION_SIZE=2000
POSITION_RISK_PERCENT=3
STOP_LOSS_PERCENT=3
TRAILING_STOP_ACTIVATION=1.5
```

### High-Frequency Setup
```ini
PRIMARY_TIMEFRAME=5m
SECONDARY_TIMEFRAME=1m
MAX_POSITIONS=10
ORDER_TYPE=MARKET
SLIPPAGE_TOLERANCE=0.2
```
