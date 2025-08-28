#!/bin/bash

# Update Improved Bot Components Script
# This script updates the improved trading bot components from a repository

echo "Starting update process for improved trading components..."

# Ensure we're in the correct directory
cd /workspaces/iq-720-trading-bot || { echo "Failed to change to project directory."; exit 1; }

# Check if git is available
if ! command -v git &>/dev/null; then
    echo "Error: git is not installed. Please install git first."
    exit 1
fi

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Error: This directory is not a git repository."
    echo "Please run this script from the root of the IQ-720 Trading Bot git repository."
    exit 1
fi

# Backup current files
echo "Creating backups of current files..."
timestamp=$(date +"%Y%m%d_%H%M%S")
backup_dir="backups/improved_components_$timestamp"
mkdir -p "$backup_dir"

# List of files to backup
files_to_backup=(
    "src/utils/improved_ml_predictor.py"
    "src/improved_signal_generator.py" 
    "src/main_enhanced_improved.py"
    "test_improved_components.py"
    "run_improved_bot.sh"
)

# Copy each file to the backup directory
for file in "${files_to_backup[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$backup_dir/"
        echo "Backed up: $file"
    else
        echo "Warning: $file not found, skipping backup."
    fi
done

echo "Backup complete. Files saved to $backup_dir/"

# Pull latest changes
echo "Fetching latest changes from remote repository..."
git fetch origin || { echo "Failed to fetch from remote. Check your internet connection."; exit 1; }

# Ask user which branch to update from
echo "Available branches:"
git branch -r | grep -v HEAD | sed 's/origin\///'

read -p "Enter branch name to update from (default: main): " branch_name
branch_name=${branch_name:-main}

echo "Updating improved components from branch: $branch_name"

# Stash local changes if any
git_status=$(git status --porcelain)
if [ -n "$git_status" ]; then
    echo "Local changes detected. Stashing changes..."
    git stash || { echo "Failed to stash local changes."; exit 1; }
    stashed=true
fi

# Checkout the selected branch
echo "Checking out $branch_name branch..."
git checkout "$branch_name" || { echo "Failed to checkout $branch_name branch."; exit 1; }

# Pull the latest changes
echo "Pulling latest changes..."
git pull origin "$branch_name" || { echo "Failed to pull latest changes."; exit 1; }

# Apply stashed changes if any
if [ "$stashed" = true ]; then
    echo "Re-applying stashed changes..."
    git stash pop || { echo "Warning: Failed to re-apply stashed changes."; }
fi

echo "Update process completed."
echo "You may want to run the backtesting script to verify the updated components are working correctly."
echo "To run backtesting: ./backtest_improved_components.sh"
