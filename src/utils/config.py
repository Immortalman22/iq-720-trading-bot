import os
import json
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

@dataclass
class Config:
    IQ_OPTION_WS_URL: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    BINANCE_API_KEY: str
    BINANCE_API_SECRET: str
    KRAKEN_API_KEY: str
    KRAKEN_API_SECRET: str
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_RECIPIENTS: List[str]
    DAILY_REPORT_TIME: str  # Format: "HH:MM" in SAT timezone

    @classmethod
    def load_from_env(cls) -> 'Config':
        load_dotenv()
        
        # Default email recipients
        default_recipients = ["aurevian22@gmail.com", "galdiale@gmail.com"]
        
        # Parse email recipients from env if available
        email_recipients_str = os.getenv('EMAIL_RECIPIENTS', '')
        if email_recipients_str:
            try:
                email_recipients = json.loads(email_recipients_str)
            except:
                email_recipients = default_recipients
        else:
            email_recipients = default_recipients
        
        return cls(
            IQ_OPTION_WS_URL=os.getenv('IQ_OPTION_WS_URL', 'wss://iqoption.com/echo/websocket'),
            TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            TELEGRAM_CHAT_ID=os.getenv('TELEGRAM_CHAT_ID', ''),
            BINANCE_API_KEY=os.getenv('BINANCE_API_KEY', ''),
            BINANCE_API_SECRET=os.getenv('BINANCE_API_SECRET', ''),
            KRAKEN_API_KEY=os.getenv('KRAKEN_API_KEY', ''),
            KRAKEN_API_SECRET=os.getenv('KRAKEN_API_SECRET', ''),
            SMTP_SERVER=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            SMTP_PORT=int(os.getenv('SMTP_PORT', '587')),
            SMTP_USERNAME=os.getenv('SMTP_USERNAME', ''),
            SMTP_PASSWORD=os.getenv('SMTP_PASSWORD', ''),
            EMAIL_RECIPIENTS=email_recipients,
            DAILY_REPORT_TIME=os.getenv('DAILY_REPORT_TIME', '06:00')  # Default to 6:00 AM SAT
        )
