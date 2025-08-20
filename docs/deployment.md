# Deployment Guide for IQ-720 Trading Bot

## Pre-Deployment Checklist

1. System Requirements:
   - Python 3.8 or higher
   - Minimum 2GB RAM
   - Stable internet connection
   - Synchronized system time
   - SSH access for remote deployment

2. Configuration Files Ready:
   - Trading credentials
   - Risk parameters
   - Session settings
   - Monitoring thresholds

3. Backup System:
   - Daily automated backups
   - Data persistence
   - State recovery procedures

## Deployment Steps

### 1. Environment Setup

```bash
# Clone the repository (if not already done)
git clone https://github.com/Immortalman22/iq-720-trading-bot.git
cd iq-720-trading-bot

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Create production configuration directory
mkdir -p config

# Copy and edit configuration templates
cp config/production.yml.example config/production.yml
cp config/logging.yml.example config/logging.yml

# Edit the configuration files with your settings
nano config/production.yml
```

### 3. Verify Setup

```bash
# Make verification script executable
chmod +x scripts/verify_production.py

# Run verification
./scripts/verify_production.py
```

### 4. Deploy

```bash
# Make deployment script executable
chmod +x scripts/deploy.sh

# Run deployment
./scripts/deploy.sh
```

### 5. Start Trading Bot

```bash
# Start in production mode
python src/main.py --prod
```

## Monitoring

1. Check Logs:
   ```bash
   tail -f logs/trading.log     # Trading activity
   tail -f logs/errors.log      # Error tracking
   tail -f logs/performance.log # Performance metrics
   ```

2. Monitor Performance:
   - Access dashboard at http://localhost:8080 (if enabled)
   - Check real-time metrics
   - Review trade history

## Maintenance

1. Daily Tasks:
   - Check error logs
   - Verify performance metrics
   - Review trade history
   - Confirm backup completion

2. Weekly Tasks:
   - Review system performance
   - Check pattern reliability
   - Update configurations if needed
   - Verify backup integrity

## Troubleshooting

1. Connection Issues:
   ```bash
   # Check network connectivity
   ping api.iqoption.com
   
   # Check API status
   curl -I https://api.iqoption.com/api/v2/status
   ```

2. Performance Issues:
   ```bash
   # Check system resources
   top
   
   # Check bot process
   ps aux | grep trading_bot
   ```

3. Error Recovery:
   ```bash
   # Stop the bot
   pkill -f "python src/main.py"
   
   # Clear temporary data
   rm -rf /tmp/trading_bot_*
   
   # Restart the bot
   python src/main.py --prod
   ```

## Emergency Procedures

1. Emergency Shutdown:
   ```bash
   # Quick stop
   ./scripts/emergency_stop.sh
   ```

2. State Recovery:
   ```bash
   # Recover from latest backup
   ./scripts/recover.sh
   ```

## Contacts

- Technical Support: [Your Contact]
- Emergency Contact: [Emergency Number]

## Version Information

- Bot Version: [Current Version]
- Last Updated: [Date]
- Deployment Environment: Production

Remember to always test in a demo environment first before deploying to production with real funds.
