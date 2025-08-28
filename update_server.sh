#!/bin/bash

# Script to safely update the IQ-720 Trading Bot
# This script will stop any running bot instances, backup the current code,
# and update to the latest version from the repository

echo "===== IQ-720 Trading Bot Updater ====="
echo "This script will stop any running bot, backup the current code, and update to the latest version."
echo ""

# Check if running as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root" 
   exit 1
fi

# Function to check if tmux session exists
check_tmux_session() {
  tmux has-session -t $1 2>/dev/null
}

# Step 1: Check and stop any running bot instances
echo "Step 1: Checking for running bot instances..."

if check_tmux_session "trading_bot"; then
  echo "Trading bot is running in tmux session. Stopping..."
  tmux send-keys -t trading_bot C-c
  sleep 2
  # Send another Ctrl+C just to be sure
  tmux send-keys -t trading_bot C-c
  sleep 1
  echo "Bot stopped."
else
  echo "No trading bot running in tmux session."
fi

# Check for any Python processes running the bot
BOT_PIDS=$(pgrep -f "python.*src.main")
if [ ! -z "$BOT_PIDS" ]; then
  echo "Found running bot processes. Stopping PID(s): $BOT_PIDS"
  kill $BOT_PIDS
  sleep 2
  # Force kill if still running
  kill -9 $BOT_PIDS 2>/dev/null
  echo "Processes stopped."
else
  echo "No bot processes found running outside of tmux."
fi

# Step 2: Backup current code
echo ""
echo "Step 2: Creating backup of current code..."

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${HOME}/iq-720-bot-backups"
mkdir -p $BACKUP_DIR

if [ -d "${HOME}/iq-720-trading-bot" ]; then
  cp -r ${HOME}/iq-720-trading-bot ${BACKUP_DIR}/iq-720-trading-bot_${TIMESTAMP}
  echo "Backup created at: ${BACKUP_DIR}/iq-720-trading-bot_${TIMESTAMP}"
else
  echo "Bot directory not found at ${HOME}/iq-720-trading-bot"
  echo "Creating new installation..."
fi

# Step 3: Update or clone the repository
echo ""
echo "Step 3: Updating bot code..."

if [ -d "${HOME}/iq-720-trading-bot/.git" ]; then
  # Git repo exists, update it
  cd ${HOME}/iq-720-trading-bot
  git fetch origin
  
  # Check if there are changes
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse origin/main)
  
  if [ "$LOCAL" = "$REMOTE" ]; then
    echo "Already up to date."
  else
    echo "Updates available. Pulling changes..."
    git pull origin main
    if [ $? -ne 0 ]; then
      echo "Error pulling updates. Resetting repository..."
      git fetch origin
      git reset --hard origin/main
    fi
  fi
else
  # No git repo, clone fresh
  echo "No existing git repository found. Cloning fresh..."
  if [ -d "${HOME}/iq-720-trading-bot" ]; then
    mv ${HOME}/iq-720-trading-bot ${HOME}/iq-720-trading-bot_old_${TIMESTAMP}
    echo "Moved existing non-git directory to: ${HOME}/iq-720-trading-bot_old_${TIMESTAMP}"
  fi
  
  cd ${HOME}
  git clone https://github.com/Immortalman22/iq-720-trading-bot.git
  
  if [ $? -ne 0 ]; then
    echo "Error cloning repository. Please check your internet connection and GitHub credentials."
    exit 1
  fi
fi

# Step 4: Update dependencies
echo ""
echo "Step 4: Updating dependencies..."

cd ${HOME}/iq-720-trading-bot
if [ -d "venv" ]; then
  source venv/bin/activate
  pip install -r requirements.txt
  echo "Dependencies updated."
else
  echo "Creating new virtual environment..."
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  echo "Virtual environment created and dependencies installed."
fi

# Step 5: Make scripts executable
echo ""
echo "Step 5: Setting permissions..."
chmod +x run_advanced_bot.sh
chmod +x run_basic_bot.sh
chmod +x run_ml_bot.sh
chmod +x update_bot.sh
chmod +x run_final_integration_test.py
echo "Permissions set."

# Step 6: Verify installation
echo ""
echo "Step 6: Verifying installation..."
if [ -f "src/main_advanced.py" ]; then
  echo "Main controller file verified."
else
  echo "Warning: Main controller file not found!"
fi

# Done
echo ""
echo "===== Update Complete ====="
echo "The IQ-720 Trading Bot has been successfully updated."
echo ""
echo "To start the bot:"
echo "  tmux new-session -d -s trading_bot './run_advanced_bot.sh'"
echo ""
echo "To check bot status:"
echo "  tmux attach -t trading_bot"
echo ""
echo "Remember: This version is optimized for manual trading."
echo "Refer to CONSOLIDATED_README.md and FINAL_SUMMARY.md for details."
echo ""
