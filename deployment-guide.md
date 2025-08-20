### Deployment Instructions for "720 IQ" Trading Bot

**Objective**: Deploy the bot securely for 24/7 operation while complying with IQ Option’s ToS.

#### 1. Infrastructure Setup
```bash
# Spin up a cheap Linux VPS (Ubuntu 22.04 recommended)
# DigitalOcean/AWS Lightsail (~$5/month)
ssh root@your-vps-ip
```

#### 2. Clone & Configure the Bot
```bash
git clone https://github.com/your-username/720-iq-trading-bot.git
cd 720-iq-trading-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Secure Credentials
```bash
# Store secrets in environment variables (never in code!)
echo "TELEGRAM_TOKEN=your_token_here" >> .env
echo "IQ_EMAIL=your_email" >> .env
echo "IQ_PASSWORD=your_password" >> .env
chmod 600 .env  # Restrict file permissions
```

#### 4. Run the Bot Persistently
```bash
# Use tmux to keep the bot running after SSH disconnect
tmux new -s trading_bot
python src/main.py  # Start the bot
# Detach with Ctrl+B, then D
```

#### 5. Automate Restarts (Optional)
```bash
# Add a cron job to restart on crashes (every 6 hours)
(crontab -l ; echo "0 */6 * * * cd /path/to/bot && venv/bin/python src/main.py") | crontab -
```

#### 6. Monitoring & Logs
```bash
# Check bot status
tmux attach -t trading_bot

# View logs
tail -f bot.log  # Ensure your code writes logs to this file
```

#### 7. Compliance Safeguards
- Randomize delays between signals (2-10 sec) to mimic human behavior.
- Avoid trading 24/7 – sync with London session hours (8AM-12PM GMT).

---

### Key Files to Verify Before Deployment
1. `src/main.py` (No direct IQ Option API trading – manual execution only).
2. `.gitignore` (Excludes `.env` and logs).
3. `requirements.txt` (All dependencies pinned).

**Next**:
- Test in demo mode for 48 hours.
- Gradually increase trade frequency.

Let me know if you need help with Dockerizing or CI/CD pipelines!
