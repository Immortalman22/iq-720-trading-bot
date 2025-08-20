# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the IQ-720 Trading Bot.

## Table of Contents
- [Quick Diagnostic Steps](#quick-diagnostic-steps)
- [Common Issues](#common-issues)
  - [Startup Problems](#startup-problems)
  - [Trading Issues](#trading-issues)
  - [Performance Problems](#performance-problems)
  - [Connectivity Issues](#connectivity-issues)
  - [Data Quality Issues](#data-quality-issues)
- [Log Analysis](#log-analysis)
- [System Health Checks](#system-health-checks)
- [Recovery Procedures](#recovery-procedures)
- [Support Resources](#support-resources)

## Quick Diagnostic Steps

1. Check System Status:
```bash
# Docker status
docker-compose ps

# View logs
docker-compose logs --tail=100 trading-bot

# Check system resources
docker stats trading-bot
```

2. Verify Configuration:
```bash
# Validate environment variables
docker-compose config

# Check configuration files
cat .env | grep -v '^#' | grep .
```

3. Test Connectivity:
```bash
# Health check endpoint
curl http://localhost:8080/health

# Test exchange API
curl https://api.exchange.com/v1/ping
```

## Common Issues

### Startup Problems

#### Container Won't Start
```
Problem: Container exits immediately after starting
Symptoms:
- "Exit 1" status in docker-compose ps
- No trading-bot container running

Solutions:
1. Check logs:
   docker-compose logs trading-bot

2. Verify permissions:
   sudo chown -R 1000:1000 data logs backtest_results

3. Check disk space:
   df -h

4. Validate configuration:
   docker-compose config
```

#### Missing Dependencies
```
Problem: Required packages or libraries not found
Symptoms:
- ImportError in logs
- ModuleNotFoundError exceptions

Solutions:
1. Rebuild container:
   docker-compose build --no-cache trading-bot

2. Check requirements:
   cat requirements.txt

3. Verify TA-Lib installation:
   docker exec trading-bot python -c "import talib"
```

### Trading Issues

#### No Trades Executing
```
Problem: Bot is running but not making trades
Symptoms:
- No new entries in trading.log
- Balance unchanged

Solutions:
1. Check trading mode:
   grep TRADE_MODE .env

2. Verify API keys:
   curl -H "X-API-KEY: $API_KEY" https://api.exchange.com/v1/account

3. Check position limits:
   grep MAX_POSITION .env

4. Review signal conditions:
   tail -f logs/trading.log | grep "Signal generated"
```

#### Incorrect Position Sizing
```
Problem: Trade sizes don't match configuration
Symptoms:
- Unexpected position sizes
- Risk limits exceeded

Solutions:
1. Check account balance:
   curl -H "X-API-KEY: $API_KEY" https://api.exchange.com/v1/balance

2. Verify risk settings:
   grep RISK_ .env

3. Review position calculations:
   tail -f logs/trading.log | grep "Position size"
```

### Performance Problems

#### High CPU Usage
```
Problem: Bot consuming excessive CPU
Symptoms:
- High CPU in docker stats
- Slow response times

Solutions:
1. Check resource limits:
   docker stats trading-bot

2. Optimize intervals:
   grep INTERVAL .env

3. Review data caching:
   grep CACHE_ .env

4. Monitor system load:
   top -p $(pgrep -f trading-bot)
```

#### Memory Leaks
```
Problem: Increasing memory usage over time
Symptoms:
- Growing memory consumption
- OOM killer activation

Solutions:
1. Monitor memory:
   docker stats trading-bot

2. Check garbage collection:
   grep MEMORY .env

3. Restart container:
   docker-compose restart trading-bot

4. Update memory limits:
   docker-compose up -d --scale trading-bot=0 && docker-compose up -d
```

### Connectivity Issues

#### API Connection Failures
```
Problem: Can't connect to exchange API
Symptoms:
- Connection timeout errors
- API rate limit errors

Solutions:
1. Check API status:
   curl https://api.exchange.com/v1/status

2. Verify network:
   ping api.exchange.com

3. Review rate limits:
   grep RATE_LIMIT .env

4. Check proxy settings:
   env | grep -i proxy
```

#### WebSocket Disconnections
```
Problem: Frequent WebSocket disconnections
Symptoms:
- Connection reset errors
- Missing market data

Solutions:
1. Monitor connections:
   tail -f logs/errors.log | grep "WebSocket"

2. Check network stability:
   ping -c 100 ws.exchange.com

3. Adjust reconnect settings:
   grep WEBSOCKET_ .env

4. Review error patterns:
   grep -A 5 "WebSocket disconnected" logs/errors.log
```

### Data Quality Issues

#### Price Data Anomalies
```
Problem: Incorrect or missing price data
Symptoms:
- Unusual price movements
- Missing candlesticks

Solutions:
1. Verify data source:
   grep DATA_SOURCE .env

2. Check volume thresholds:
   grep VOLUME_ .env

3. Monitor data quality:
   tail -f logs/trading.log | grep "Price validation"

4. Review edge case handling:
   grep -A 5 "Price anomaly" logs/errors.log
```

#### Volume Data Issues
```
Problem: Incorrect trading volume data
Symptoms:
- Unusual volume spikes
- Missing volume data

Solutions:
1. Check volume filters:
   grep VOLUME_ .env

2. Verify exchange data:
   curl https://api.exchange.com/v1/ticker/24h

3. Monitor volume validation:
   tail -f logs/trading.log | grep "Volume validation"

4. Review volume corrections:
   grep -A 5 "Volume corrected" logs/trading.log
```

## Log Analysis

### Understanding Log Patterns
```
1. Error patterns:
   grep -i error logs/errors.log | sort | uniq -c

2. Warning patterns:
   grep -i warn logs/trading.log | sort | uniq -c

3. Trading patterns:
   grep "Signal generated" logs/trading.log | tail -n 20
```

### Log Locations
```
1. Trading logs:
   /app/logs/trading.log

2. Error logs:
   /app/logs/errors.log

3. Performance logs:
   /app/logs/performance.log

4. Container logs:
   docker-compose logs trading-bot
```

## System Health Checks

### Monitoring Endpoints
```
1. Basic health:
   curl http://localhost:8080/health

2. Detailed status:
   curl http://localhost:8080/status

3. Metrics:
   curl http://localhost:9090/metrics
```

### Resource Monitoring
```
1. Container stats:
   docker stats trading-bot

2. Disk usage:
   du -sh /app/*

3. Network connections:
   netstat -an | grep 8080
```

## Recovery Procedures

### Emergency Shutdown
```
1. Stop trading:
   docker-compose stop trading-bot

2. Close positions:
   python scripts/emergency_close.py

3. Backup data:
   ./scripts/backup/backup.sh
```

### Data Recovery
```
1. List backups:
   ls -l backups/

2. Restore from backup:
   ./scripts/backup/recover.sh backups/latest.tar.gz

3. Verify recovery:
   python scripts/verify_data.py
```

### System Reset
```
1. Stop services:
   docker-compose down

2. Clear state:
   rm -rf data/state/*

3. Reset logs:
   truncate -s 0 logs/*.log

4. Restart clean:
   docker-compose up -d
```

## Support Resources

### Documentation
- [Installation Guide](installation.md)
- [Configuration Guide](configuration.md)
- [API Documentation](api.md)

### Community Resources
- GitHub Issues: [Report a Bug](https://github.com/Immortalman22/iq-720-trading-bot/issues)
- Wiki: [Troubleshooting Wiki](https://github.com/Immortalman22/iq-720-trading-bot/wiki)

### Getting Help
1. Search existing issues
2. Check log files
3. Review documentation
4. Open a new issue with:
   - Error messages
   - Log excerpts
   - Configuration (redacted)
   - Steps to reproduce
