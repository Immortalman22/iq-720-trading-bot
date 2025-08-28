# IQ-720 Trading Bot

## Overview

The IQ-720 Trading Bot is an advanced algorithmic trading system optimized for manual trading. It generates high-quality trading signals using machine learning and advanced technical analysis without artificial delays or human-like behavior simulation.

## Features

- **ML-Enhanced Signal Generation**: Leverages machine learning for high-probability trade signals
- **Dynamic Asset Selection**: Automatically selects the best performing assets
- **Market Regime Detection**: Adapts trading strategies based on current market conditions
- **Adaptive Position Sizing**: Calculates optimal position sizes based on confidence and market conditions
- **Signal Quality Ranking**: Ranks signals by probability of success and expected return
- **Manual Trading Support**: Optimized for manual execution of trading signals

## Installation

### Prerequisites
- Python 3.8+
- Git
- IQ Option API access

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Immortalman22/iq-720-trading-bot.git
cd iq-720-trading-bot
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure your settings:
   - Copy `config_advanced.json.example` to `config_advanced.json`
   - Update with your IQ Option credentials and preferences

## Usage

### For Manual Trading

1. Start the bot:
```bash
./run_advanced_bot.sh
```

2. The bot will:
   - Connect to IQ Option
   - Analyze market data
   - Generate trading signals
   - Display signals with entry/exit points and confidence levels

3. Execute trades manually based on the signals

### Server Deployment

For running on a server:

1. Use the provided `update_server.sh` script for safe updates
2. Use tmux to manage bot sessions:
```bash
tmux new-session -d -s trading_bot './run_advanced_bot.sh'
tmux attach -t trading_bot  # To view the bot
```

3. Refer to `SERVER_MANAGEMENT.md` for detailed server instructions

## Documentation

- `CONSOLIDATED_README.md` - Main documentation for the consolidated bot
- `FINAL_SUMMARY.md` - Summary of features and improvements
- `docs/` - Detailed documentation on specific components
- `SERVER_MANAGEMENT.md` - Instructions for server deployment

## License

This project is licensed under the MIT License - see the LICENSE file for details.
