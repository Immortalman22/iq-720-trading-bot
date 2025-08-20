import backtrader as bt
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
from ..signal_generator import SignalGenerator

class TradingStrategy(bt.Strategy):
    params = (
        ('rsi_period', 14),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('volume_factor', 1.2),
        ('consecutive_candles', 2),
    )

    def __init__(self):
        self.signal_generator = SignalGenerator()
        self.trades = []
        self.consecutive_losses = 0
        self.trades_today = 0
        self.last_trade_time = None
        
        # Initialize indicators
        self.rsi = bt.indicators.RSI(period=self.p.rsi_period)
        self.macd = bt.indicators.MACD(
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.volume_sma = bt.indicators.SMA(self.data.volume, period=10)

    def next(self):
        # Skip if not enough data
        if len(self.data) < self.p.macd_slow + self.p.macd_signal:
            return

        # Check trading conditions
        if not self._check_trading_conditions():
            return

        # Prepare candle data for signal generator
        candle_data = {
            'timestamp': self.data.datetime.datetime(),
            'open': self.data.open[0],
            'high': self.data.high[0],
            'low': self.data.low[0],
            'close': self.data.close[0],
            'volume': self.data.volume[0]
        }

        # Get signal from generator
        signal = self.signal_generator.add_candle(candle_data)
        
        if signal:
            if signal.direction == "BUY" and not self.position:
                self._execute_trade("BUY")
            elif signal.direction == "SELL" and not self.position:
                self._execute_trade("SELL")

    def _check_trading_conditions(self) -> bool:
        """Check if trading conditions are met"""
        current_time = self.data.datetime.datetime()

        # Reset daily counters at start of day
        if self.last_trade_time and current_time.date() > self.last_trade_time.date():
            self.trades_today = 0

        # Check maximum trades per day
        if self.trades_today >= 15:
            return False

        # Check consecutive losses
        if self.consecutive_losses >= 3:
            return False

        # Ensure minimum time between trades (5 minutes)
        if (self.last_trade_time and 
            (current_time - self.last_trade_time) < timedelta(minutes=5)):
            return False

        # Check trading hours (London session: 8:00-12:00 GMT)
        hour = current_time.hour
        if not (8 <= hour < 12):
            return False

        return True

    def _execute_trade(self, direction: str):
        """Execute a trade in the backtesting environment"""
        size = self.broker.getcash() * 0.02  # 2% risk per trade
        
        if direction == "BUY":
            self.buy(size=size)
        else:
            self.sell(size=size)

        self.trades_today += 1
        self.last_trade_time = self.data.datetime.datetime()

    def notify_trade(self, trade):
        """Record trade results"""
        if trade.isclosed:
            self.trades.append({
                'entry_time': trade.dtopen,
                'exit_time': trade.dtclose,
                'entry_price': trade.price,
                'exit_price': trade.pnlcomm,
                'profit_loss': trade.pnlcomm,
                'direction': 'BUY' if trade.size > 0 else 'SELL'
            })

            if trade.pnlcomm > 0:
                self.consecutive_losses = 0
            else:
                self.consecutive_losses += 1
