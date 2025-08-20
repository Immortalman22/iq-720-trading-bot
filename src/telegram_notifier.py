import asyncio
from telegram import Bot
from telegram.error import TelegramError
import logging
from datetime import datetime
from typing import Optional
from .signal_generator import Signal

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.logger = logging.getLogger(__name__)
        self.last_signal_time: Optional[datetime] = None

    async def send_signal(self, signal: Signal):
        """Send a trading signal alert to Telegram"""
        try:
            # Format the message
            message = self._format_signal_message(signal)
            
            # Add random delay (1-3 seconds) to simulate human behavior
            delay = round(1 + 2 * signal.confidence, 2)  # Higher confidence = slightly longer delay
            await asyncio.sleep(delay)
            
            # Send the message
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.last_signal_time = signal.timestamp
            self.logger.info(f"Signal sent successfully: {signal.direction} {signal.asset}")
            
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            raise

    def _format_signal_message(self, signal: Signal) -> str:
        """Format the signal data into a readable Telegram message"""
        confidence_stars = "⭐" * int(round(signal.confidence * 5))  # 0-5 stars based on confidence
        
        message = f"""
🚨 <b>TRADING SIGNAL</b> 🚨

Asset: {signal.asset}
Direction: {'📈' if signal.direction == 'BUY' else '📉'} <b>{signal.direction}</b>
Expiry: {signal.expiry_minutes} minute(s)
Confidence: {confidence_stars} ({signal.confidence:.2%})

<b>Technical Indicators:</b>
RSI: {signal.indicators['rsi']:.2f}
MACD: {signal.indicators['macd']:.5f}
Volume: {signal.indicators['volume_ratio']:.2f}x average

⚠️ <i>Manual execution required</i>
⏰ Generated: {signal.timestamp.strftime('%H:%M:%S')} UTC
"""
        return message.strip()
