import os
from dataclasses import dataclass
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

    @classmethod
    def load_from_env(cls) -> 'Config':
        load_dotenv()
        
        return cls(
            IQ_OPTION_WS_URL=os.getenv('IQ_OPTION_WS_URL', 'wss://iqoption.com/echo/websocket'),
            TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            TELEGRAM_CHAT_ID=os.getenv('TELEGRAM_CHAT_ID', ''),
            BINANCE_API_KEY=os.getenv('BINANCE_API_KEY', ''),
            BINANCE_API_SECRET=os.getenv('BINANCE_API_SECRET', ''),
            KRAKEN_API_KEY=os.getenv('KRAKEN_API_KEY', ''),
            KRAKEN_API_SECRET=os.getenv('KRAKEN_API_SECRET', '')
        )
