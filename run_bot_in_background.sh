#!/bin/bash

# Run IQ-720 Trading Bot in Background (using tmux)
# This script runs the optimized trading bot in a detached tmux session

echo "Setting up IQ-720 Trading Bot for background operation..."

# Navigate to the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "tmux is not installed. Installing now..."
    sudo apt-get update && sudo apt-get install -y tmux
fi

# Check for existing session
if tmux has-session -t trading_bot 2>/dev/null; then
    echo "Trading bot session already running"
    echo "To attach to it, run: tmux attach -t trading_bot"
    echo "To kill it, run: tmux kill-session -t trading_bot"
    
    # Ask if user wants to attach to existing session
    read -p "Attach to existing session? (y/n): " choice
    if [[ $choice == "y" || $choice == "Y" ]]; then
        tmux attach -t trading_bot
        exit 0
    else
        echo "Exiting without starting a new session"
        exit 0
    fi
fi

# Create new tmux session and start the bot
echo "Starting trading bot in background session..."
tmux new-session -d -s trading_bot "./run_advanced_bot.sh"

echo "Trading bot is running in background"
echo ""
echo "To view the bot interface:"
echo "  tmux attach -t trading_bot"
echo ""
echo "To detach from the session (leave it running):"
echo "  Press Ctrl+B and then D"
echo ""
echo "To kill the bot:"
echo "  tmux kill-session -t trading_bot"
