# Server Management Instructions

## Step 1: Stop the Running Bot

1. Connect to your server:
   ```bash
   ssh root@178.128.42.164
   ```

2. Attach to the running tmux session:
   ```bash
   tmux attach -t trading_bot
   ```

3. Stop the bot by pressing `Ctrl+C`

4. You can either detach from tmux (`Ctrl+B` followed by `D`) or exit the session (`Ctrl+D` or type `exit`)

## Step 2: Update the Repository

1. Navigate to your bot directory:
   ```bash
   cd ~/iq-720-trading-bot
   ```

2. Pull the latest changes:
   ```bash
   git pull origin main
   ```

   If you encounter any conflicts, resolve them or consider backing up and cloning fresh:
   ```bash
   cd ~
   mv iq-720-trading-bot iq-720-trading-bot.bak
   git clone https://github.com/Immortalman22/iq-720-trading-bot.git
   ```

## Step 3: Install Dependencies

1. Make sure your virtual environment is activated:
   ```bash
   source venv/bin/activate  # If using venv
   ```

2. Update dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Step 4: Start the Optimized Bot

1. Start the bot using the advanced script in a tmux session:
   ```bash
   tmux new-session -d -s trading_bot './run_advanced_bot.sh'
   ```

2. To check on the bot:
   ```bash
   tmux attach -t trading_bot
   ```

3. To detach without stopping (once attached):
   - Press `Ctrl+B` followed by `D`

## Important Notes

- The bot has been optimized for manual trading - it will generate signals without artificial delays
- Use `main_advanced.py` as the primary controller
- Review signals and execute trades manually for best results
- Check the `CONSOLIDATED_README.md` and `FINAL_SUMMARY.md` for detailed documentation

## Troubleshooting

If you encounter any issues with the bot:

1. Check the logs:
   ```bash
   cat logs/trading.log
   ```

2. Run the integration test to verify system integrity:
   ```bash
   python run_final_integration_test.py
   ```

3. If you need to switch back to the previous version temporarily:
   ```bash
   # If you created a backup as suggested above
   cd ~
   mv iq-720-trading-bot iq-720-trading-bot.new
   mv iq-720-trading-bot.bak iq-720-trading-bot
   ```
