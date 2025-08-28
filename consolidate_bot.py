#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script consolidates trading bot components to resolve redundancies
and ensures consistency across the codebase.
"""

import os
import sys
import shutil
from datetime import datetime
import re

def backup_file(file_path):
    """Create a backup of a file before modifying it"""
    if os.path.exists(file_path):
        backup_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        filename = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
        
        shutil.copy2(file_path, backup_path)
        print(f"Created backup at {backup_path}")
        return True
    return False

def create_consolidated_readme():
    """Create a README explaining the consolidated structure"""
    content = """# IQ-720 Trading Bot - Consolidated Version

## Overview

This trading bot has been consolidated to remove redundancies and improve maintainability. The following changes have been made:

1. **Main Controller File**: `main_advanced.py` is now the primary controller file.
   - Run using: `./run_advanced_bot.sh`

2. **Signal Generation**:
   - Signal generation is now integrated into the `EnhancedTradingStrategy` class
   - Uses the ML predictor for signal generation
   - Leverages utility modules like `signal_ranker.py` for additional capabilities

3. **Human-like Behavior**:
   - All artificial delays and human behavior simulation have been removed
   - The bot is optimized for manual trading signals

## Usage

For manual trading signals:

```bash
./run_advanced_bot.sh
```

## Previous Versions

The previous versions of the controller files have been retained for reference:
- `main.py` - Original controller
- `main_updated.py` - First updated version
- `main_enhanced.py` - Enhanced version
- `main_enhanced_improved.py` - Version with improved signal generator

You can still run these versions using their respective scripts if needed.
"""

    readme_path = os.path.join('/workspaces/iq-720-trading-bot', 'CONSOLIDATED_README.md')
    with open(readme_path, 'w') as f:
        f.write(content)
        
    print(f"Created consolidated README at {readme_path}")

def consolidate_components():
    """Consolidate trading bot components"""
    project_root = "/workspaces/iq-720-trading-bot"
    
    print("=== IQ-720 Trading Bot Consolidation ===")
    print("This script will consolidate components to remove redundancies.")
    
    # Create consolidated readme
    create_consolidated_readme()
    
    # No need to modify files since we've already removed delays
    # We're just creating documentation on the current state
    
    print("\nConsolidation complete. The main_advanced.py file is now the primary controller.")
    print("Run the bot using: ./run_advanced_bot.sh")

if __name__ == "__main__":
    consolidate_components()
