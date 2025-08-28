#!/bin/bash

# Run Advanced IQ-720 Trading Bot (Optimized for Manual Trading)
# This script runs the trading bot with all sleep delays removed
# while maintaining full functionality including ML components

echo "Starting IQ-720 Advanced Trading Bot (Optimized for Manual Trading)..."

# Navigate to the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Setup virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating Python environment..."
source .venv/bin/activate

# Function to patch sleep calls
patch_sleeps() {
    # Create a temporary Python script to patch the sleep function
    cat > patch_sleep.py << 'EOF'
import builtins
import sys
import types
import time

# Store the original sleep function
original_sleep = time.sleep

# Replace sleep with a no-op function
def no_sleep(seconds):
    print(f"Sleep call bypassed: {seconds}s")
    return

# Patch the time module
time.sleep = no_sleep

# Continue with normal execution
module_name = sys.argv[1]
exec(f"import {module_name}")
module = sys.modules[module_name]

# Call the main function if it exists
if hasattr(module, 'main'):
    module.main()
EOF

    echo "Sleep functions patched - all artificial delays removed"
}

# Create the patch
patch_sleeps

# Run the bot with patched sleep function
echo "Launching optimized trading bot with full ML capabilities..."
python patch_sleep.py src.main "$@"

# Capture exit code
EXIT_CODE=$?

# Clean up
rm -f patch_sleep.py

# Deactivate virtual environment
deactivate

echo "Trading bot execution completed"

# Return the exit code from the Python script
exit $EXIT_CODE
