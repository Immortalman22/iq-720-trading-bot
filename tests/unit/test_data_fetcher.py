import pytest
from unittest.mock import Mock, patch
from src.data_fetcher import IQOptionDataFetcher
from src.utils.config import Config
from datetime import datetime
import json

@pytest.fixture
def mock_config():
    return Config(
        IQ_OPTION_WS_URL="wss://test.iqoption.com/echo/websocket",
        TELEGRAM_BOT_TOKEN="test_token",
        TELEGRAM_CHAT_ID="test_chat_id",
        BINANCE_API_KEY="test_binance_key",
        BINANCE_API_SECRET="test_binance_secret",
        KRAKEN_API_KEY="test_kraken_key",
        KRAKEN_API_SECRET="test_kraken_secret"
    )

@pytest.fixture
def data_fetcher(mock_config):
    callback = Mock()
    return IQOptionDataFetcher(mock_config, callback)

def test_data_fetcher_initialization(data_fetcher):
    assert data_fetcher is not None
    assert data_fetcher.is_connected == False
    assert data_fetcher.using_fallback == False

def test_trading_hours_check(data_fetcher):
    # Test within trading hours (8:00-12:00 GMT)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 8, 17, 9, 0)  # 9:00 GMT
        assert data_fetcher.is_within_trading_hours()
        
        mock_datetime.now.return_value = datetime(2025, 8, 17, 13, 0)  # 13:00 GMT
        assert not data_fetcher.is_within_trading_hours()

@patch('websocket.WebSocketApp')
def test_websocket_connection(mock_ws, data_fetcher):
    data_fetcher.connect()
    mock_ws.assert_called_once()
    assert mock_ws.call_args[1]['on_message'] == data_fetcher._on_message
    assert mock_ws.call_args[1]['on_error'] == data_fetcher._on_error
    assert mock_ws.call_args[1]['on_close'] == data_fetcher._on_close
    assert mock_ws.call_args[1]['on_open'] == data_fetcher._on_open

def test_message_handling(data_fetcher):
    # Test candle message
    candle_message = {
        "name": "candle-generated",
        "msg": {
            "asset": "EURUSD",
            "close": 1.2000,
            "volume": 1000,
            "timestamp": datetime.now().timestamp()
        }
    }
    
    data_fetcher._on_message(None, json.dumps(candle_message))
    data_fetcher.on_candle_callback.assert_called_once()

def test_fallback_switching(data_fetcher):
    # Test switching to fallback on connection error
    data_fetcher._on_error(None, Exception("Connection lost"))
    assert data_fetcher.using_fallback == True
    
    # Test fallback data polling
    with patch('src.utils.fallback_data.FallbackDataManager.get_current_data') as mock_fallback:
        mock_fallback.return_value = {
            'timestamp': datetime.now().timestamp(),
            'price': 1.2000,
            'source': 'Binance'
        }
        data_fetcher._poll_fallback_data()
        data_fetcher.on_candle_callback.assert_called()

def test_historical_data_retrieval(data_fetcher):
    # Test getting historical data from primary source
    data_fetcher.is_connected = True
    data_fetcher.get_historical_data()
    
    # Test getting historical data from fallback
    data_fetcher.is_connected = False
    with patch('src.utils.fallback_data.FallbackDataManager.get_historical_data') as mock_fallback:
        mock_fallback.return_value = "test_data"
        result = data_fetcher.get_historical_data()
        assert result == "test_data"

def test_error_handling(data_fetcher):
    # Test websocket error handling
    data_fetcher._on_error(None, Exception("Test error"))
    assert data_fetcher.is_connected == False
    assert data_fetcher.using_fallback == True
    
    # Test message parsing error
    data_fetcher._on_message(None, "invalid json")
    data_fetcher.on_candle_callback.assert_not_called()

def test_reconnection_logic(data_fetcher):
    # Test reconnection attempt after failure
    data_fetcher.last_pong = datetime.now().timestamp() - 400  # 400 seconds ago
    
    with patch('src.data_fetcher.IQOptionDataFetcher.connect') as mock_connect:
        data_fetcher._poll_fallback_data()
        mock_connect.assert_called_once()
