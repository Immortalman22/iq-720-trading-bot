# IQ-720 Trading Bot - Consolidated Version

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
