# Installation Guide

This guide provides step-by-step instructions for installing and configuring the IQ-720 Trading Bot.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
  - [Docker Installation (Recommended)](#docker-installation-recommended)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- CPU: 2+ cores recommended
- RAM: 4GB minimum, 8GB recommended
- Storage: 20GB minimum for logs and data
- OS: Ubuntu 20.04+ or similar Linux distribution

### Required Software
- Docker 20.10+ and Docker Compose 2.0+ (for Docker installation)
- Python 3.10+ (for manual installation)
- Git
- TA-Lib

## Installation Methods

### Docker Installation (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/Immortalman22/iq-720-trading-bot.git
cd iq-720-trading-bot
```

2. Create and configure the environment file:
```bash
cp .env.example .env
# Edit .env with your settings
nano .env
```

3. Build and start the containers:
```bash
docker-compose up -d
```

4. Verify the installation:
```bash
docker-compose ps  # Check container status
curl http://localhost:8080/health  # Check health endpoint
```

### Manual Installation

1. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y build-essential wget python3.10 python3.10-dev python3-pip

# Install TA-Lib
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
cd ..
rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
```

2. Clone and set up the project:
```bash
git clone https://github.com/Immortalman22/iq-720-trading-bot.git
cd iq-720-trading-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Configure the environment:
```bash
cp .env.example .env
# Edit .env with your settings
nano .env
```

4. Create required directories:
```bash
mkdir -p data logs backtest_results backups
```

## Configuration

### Required Environment Variables
- `API_KEY`: Your trading API key
- `API_SECRET`: Your trading API secret
- `TRADE_MODE`: "live" or "paper"
- `RISK_LEVEL`: 1-5 (default: 3)
- `MAX_POSITION_SIZE`: Maximum position size in base currency
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for notifications
- `TELEGRAM_CHAT_ID`: Telegram chat ID for notifications

### Optional Environment Variables
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `BACKTEST_MODE`: Enable/disable backtesting (default: false)
- `DATA_SOURCE`: Primary data source (default: binance)
- `BACKUP_ENABLED`: Enable automated backups (default: true)

## Security Considerations

1. File Permissions:
```bash
# Set correct permissions for sensitive files
chmod 600 .env
chmod -R 700 data logs backtest_results backups
```

2. Network Security:
- The bot runs in an isolated Docker network
- Only required ports (8080, 9090) are exposed locally
- All external connections use TLS/SSL

3. Container Security:
- Containers run as non-root user
- Root filesystem is read-only
- All capabilities are dropped
- No privilege escalation allowed

## Troubleshooting

### Common Issues

1. Container fails to start:
```bash
# Check container logs
docker-compose logs trading-bot

# Verify environment variables
docker-compose config

# Check disk space
df -h
```

2. Connection issues:
```bash
# Test network connectivity
curl -v https://api.exchange.com

# Check DNS resolution
nslookup api.exchange.com
```

3. Permission issues:
```bash
# Fix directory permissions
sudo chown -R $(id -u):$(id -g) data logs backtest_results backups
```

### Log Locations
- Application logs: `logs/trading.log`
- Error logs: `logs/errors.log`
- Container logs: Use `docker-compose logs`

### Support
For additional support:
1. Check the [Troubleshooting Guide](./troubleshooting.md)
2. Review [Common Issues](./common-issues.md)
3. Open an issue on GitHub
