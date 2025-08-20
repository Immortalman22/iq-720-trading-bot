from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException
import krakenex
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, timedelta
import time
import pandas as pd

class DataSourceInterface(ABC):
    @abstractmethod
    def get_current_price(self) -> Optional[float]:
        """Get current price for EUR/USD"""
        pass

    @abstractmethod
    def get_candles(self, interval: str = "1m", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Get historical candle data"""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if the data source is functioning properly"""
        pass

class BinanceDataSource(DataSourceInterface):
    def __init__(self, api_key: str, api_secret: str):
        self.client = BinanceClient(api_key, api_secret)
        self.logger = logging.getLogger(__name__)
        self.symbol = "EURUSDT"  # Using USDT pair as closest to USD
        self.last_check = datetime.now()
        self.is_available = True

    def get_current_price(self) -> Optional[float]:
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {e}")
            self.is_available = False
            return None

    def get_candles(self, interval: str = "1m", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=limit
            )
            
            return [{
                'timestamp': k[0] // 1000,  # Convert ms to s
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            } for k in klines]
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error: {e}")
            self.is_available = False
            return None

    def is_healthy(self) -> bool:
        # Check health every 5 minutes
        if (datetime.now() - self.last_check).total_seconds() > 300:
            try:
                self.client.get_system_status()
                self.is_available = True
            except:
                self.is_available = False
            self.last_check = datetime.now()
        return self.is_available

class KrakenDataSource(DataSourceInterface):
    def __init__(self, api_key: str, api_secret: str):
        self.kraken = krakenex.API(api_key, api_secret)
        self.logger = logging.getLogger(__name__)
        self.pair = "EURUSD"
        self.last_check = datetime.now()
        self.is_available = True

    def get_current_price(self) -> Optional[float]:
        try:
            result = self.kraken.query_public('Ticker', {'pair': self.pair})
            if 'result' in result and self.pair in result['result']:
                return float(result['result'][self.pair]['c'][0])  # Current price
            return None
        except Exception as e:
            self.logger.error(f"Kraken API error: {e}")
            self.is_available = False
            return None

    def get_candles(self, interval: str = "1m", limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        try:
            # Convert interval to Kraken format
            interval_seconds = {
                "1m": 60,
                "5m": 300,
                "15m": 900,
                "1h": 3600,
                "4h": 14400,
                "1d": 86400
            }.get(interval, 60)

            end_time = time.time()
            start_time = end_time - (interval_seconds * limit)

            result = self.kraken.query_public('OHLC', {
                'pair': self.pair,
                'interval': interval_seconds,
                'since': int(start_time)
            })

            if 'result' not in result or self.pair not in result['result']:
                return None

            ohlc_data = result['result'][self.pair]
            return [{
                'timestamp': int(k[0]),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[6])
            } for k in ohlc_data[-limit:]]
        except Exception as e:
            self.logger.error(f"Kraken API error: {e}")
            self.is_available = False
            return None

    def is_healthy(self) -> bool:
        # Check health every 5 minutes
        if (datetime.now() - self.last_check).total_seconds() > 300:
            try:
                self.kraken.query_public('Time')
                self.is_available = True
            except:
                self.is_available = False
            self.last_check = datetime.now()
        return self.is_available

class FallbackDataManager:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.sources: List[DataSourceInterface] = [
            BinanceDataSource(config.BINANCE_API_KEY, config.BINANCE_API_SECRET),
            KrakenDataSource(config.KRAKEN_API_KEY, config.KRAKEN_API_SECRET)
        ]
        self.current_source_index = 0

    def get_healthy_source(self) -> Optional[DataSourceInterface]:
        """Get the first available healthy data source"""
        original_index = self.current_source_index
        
        while True:
            source = self.sources[self.current_source_index]
            if source.is_healthy():
                return source
                
            # Try next source
            self.current_source_index = (self.current_source_index + 1) % len(self.sources)
            
            # If we've tried all sources, return None
            if self.current_source_index == original_index:
                self.logger.error("No healthy data sources available")
                return None

    def get_current_data(self) -> Optional[Dict[str, Any]]:
        """Get current market data from the best available source"""
        source = self.get_healthy_source()
        if not source:
            return None

        current_price = source.get_current_price()
        if not current_price:
            return None

        return {
            'timestamp': int(time.time()),
            'price': current_price,
            'source': source.__class__.__name__
        }

    def get_historical_data(self, interval: str = "1m", limit: int = 100) -> Optional[pd.DataFrame]:
        """Get historical candle data from the best available source"""
        source = self.get_healthy_source()
        if not source:
            return None

        candles = source.get_candles(interval, limit)
        if not candles:
            return None

        df = pd.DataFrame(candles)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('datetime', inplace=True)
        return df
