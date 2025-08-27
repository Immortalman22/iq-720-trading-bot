#!/bin/bash

# Update script for the enhanced trading bot
# This script will update the bot on the production server

# Configuration
REMOTE_USER="root"
REMOTE_SERVER="178.128.42.164"
REMOTE_DIR="/root/iq-720-trading-bot"
LOCAL_DIR="$(pwd)"
BACKUP_DIR="${REMOTE_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
TMUX_SESSION="trading_bot"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting upgrade process for IQ-720 Trading Bot...${NC}"
echo "Local directory: $LOCAL_DIR"
echo "Remote directory: $REMOTE_DIR"

# Function to run a command on the remote server
remote_command() {
    ssh $REMOTE_USER@$REMOTE_SERVER "$1"
}

# Check if we can connect to the remote server
echo -e "${YELLOW}Checking connection to remote server...${NC}"
if ! remote_command "echo Connection successful"; then
    echo -e "${RED}Cannot connect to remote server. Please check your SSH configuration.${NC}"
    exit 1
fi

# Check if the trading bot is running in a tmux session
echo -e "${YELLOW}Checking if trading bot is running...${NC}"
if remote_command "tmux has-session -t $TMUX_SESSION 2>/dev/null"; then
    echo "Trading bot is running in tmux session '$TMUX_SESSION'"
    
    # Ask for confirmation before stopping
    read -p "Do you want to stop the trading bot before updating? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Stopping the trading bot...${NC}"
        remote_command "tmux send-keys -t $TMUX_SESSION C-c"
        sleep 2
        echo "Trading bot stopped"
    else
        echo "Continuing without stopping the trading bot"
    fi
else
    echo "Trading bot is not running in tmux session '$TMUX_SESSION'"
fi

# Create a backup of the current code on the remote server
echo -e "${YELLOW}Creating backup of current code on remote server...${NC}"
remote_command "mkdir -p $BACKUP_DIR && cp -r $REMOTE_DIR/src $BACKUP_DIR/ && cp -r $REMOTE_DIR/scripts $BACKUP_DIR/"
echo "Backup created at $BACKUP_DIR"

# Sync files to the remote server
echo -e "${YELLOW}Syncing files to remote server...${NC}"
rsync -avz --exclude '.git/' --exclude '.venv/' --exclude '__pycache__/' \
    --exclude 'logs/' --exclude '*.log' --exclude 'data/' \
    $LOCAL_DIR/src/ $REMOTE_USER@$REMOTE_SERVER:$REMOTE_DIR/src/

# Copy the main_enhanced.py script
rsync -avz $LOCAL_DIR/src/main_enhanced.py $REMOTE_USER@$REMOTE_SERVER:$REMOTE_DIR/main_enhanced.py

# Make the main script executable on the remote server
remote_command "chmod +x $REMOTE_DIR/main_enhanced.py"

# Check if requirements have changed and update if needed
if [[ -f "$LOCAL_DIR/requirements.txt" ]]; then
    echo -e "${YELLOW}Updating Python dependencies...${NC}"
    rsync -avz $LOCAL_DIR/requirements.txt $REMOTE_USER@$REMOTE_SERVER:$REMOTE_DIR/requirements.txt
    remote_command "pip install -r $REMOTE_DIR/requirements.txt"
fi

# Check if .env file exists and update email settings if needed
if [[ -f "$LOCAL_DIR/.env" ]]; then
    echo -e "${YELLOW}Updating environment variables...${NC}"
    rsync -avz $LOCAL_DIR/.env $REMOTE_USER@$REMOTE_SERVER:$REMOTE_DIR/.env
else
    echo -e "${YELLOW}Setting up email configuration...${NC}"
    
    # Ask for email configuration
    read -p "Enter SMTP server (default: smtp.gmail.com): " smtp_server
    smtp_server=${smtp_server:-smtp.gmail.com}
    
    read -p "Enter SMTP port (default: 587): " smtp_port
    smtp_port=${smtp_port:-587}
    
    read -p "Enter SMTP username (email address): " smtp_username
    
    # Use stty to hide password input
    echo -n "Enter SMTP password: "
    stty -echo
    read smtp_password
    stty echo
    echo
    
    # Create or update .env file on remote server
    remote_command "echo \"SMTP_SERVER=$smtp_server\" >> $REMOTE_DIR/.env"
    remote_command "echo \"SMTP_PORT=$smtp_port\" >> $REMOTE_DIR/.env"
    remote_command "echo \"SMTP_USERNAME=$smtp_username\" >> $REMOTE_DIR/.env"
    remote_command "echo \"SMTP_PASSWORD=$smtp_password\" >> $REMOTE_DIR/.env"
    remote_command "echo \"EMAIL_RECIPIENTS=[\\\"aurevian22@gmail.com\\\", \\\"galdiale@gmail.com\\\"]\" >> $REMOTE_DIR/.env"
    remote_command "echo \"DAILY_REPORT_TIME=06:00\" >> $REMOTE_DIR/.env"
    
    echo "Email configuration added to .env file"
fi

# Ask if we should restart the trading bot
read -p "Do you want to restart the trading bot with the new code? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting the enhanced trading bot...${NC}"
    
    # Check if the tmux session exists, if not create it
    if ! remote_command "tmux has-session -t $TMUX_SESSION 2>/dev/null"; then
        remote_command "tmux new-session -d -s $TMUX_SESSION"
    fi
    
    # Start the bot in the tmux session
    remote_command "tmux send-keys -t $TMUX_SESSION 'cd $REMOTE_DIR && python main_enhanced.py --analysis-only' C-m"
    echo -e "${GREEN}Enhanced trading bot started in tmux session '$TMUX_SESSION'${NC}"
    echo "You can attach to the session with: ssh $REMOTE_USER@$REMOTE_SERVER -t tmux attach -t $TMUX_SESSION"
fi

echo -e "${GREEN}Upgrade process completed successfully!${NC}"
echo "The enhanced trading bot has been deployed with the following improvements:"
echo "✅ Pair-specific indicator settings"
echo "✅ Signal strength ranking system"
echo "✅ Correlation analysis to prevent overtrading"
echo "✅ Performance tracking per currency pair"
echo "✅ Dynamic asset selection based on volatility"
echo "✅ Time-based trading logic for different market sessions"
echo "✅ Improved indicator calculations with noise reduction"
echo
echo "To view the trading bot logs, use:"
echo "ssh $REMOTE_USER@$REMOTE_SERVER -t tmux attach -t $TMUX_SESSION"
