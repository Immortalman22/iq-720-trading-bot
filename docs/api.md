# API Documentation

This document describes the APIs exposed by the IQ-720 Trading Bot, including WebSocket endpoints, HTTP endpoints, and integration interfaces.

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [WebSocket API](#websocket-api)
- [HTTP Endpoints](#http-endpoints)
- [Integration Interfaces](#integration-interfaces)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

## Overview

The IQ-720 Trading Bot provides several interfaces:
1. WebSocket API for real-time data and trading
2. HTTP REST API for configuration and monitoring
3. Integration interfaces for external systems

### API Versioning
- Current version: v1
- Version format: /v{version_number}/endpoint
- All endpoints prefixed with /api

## Authentication

### API Keys
```http
Authorization: Bearer <api_key>
```

### WebSocket Authentication
```javascript
{
    "action": "authenticate",
    "token": "<api_key>"
}
```

### Key Management
- Generate keys via admin interface
- Scope-based permissions
- Key rotation recommended every 90 days

## WebSocket API

### Connection

```javascript
WebSocket URL: wss://trading-bot:8080/ws/v1/market
```

### Message Format
```javascript
{
    "action": "<action_name>",
    "data": {
        // action-specific data
    },
    "requestId": "<uuid>",  // optional
    "timestamp": "<iso8601>"
}
```

### Market Data Stream

#### Subscribe to Symbol
```javascript
// Request
{
    "action": "subscribe",
    "data": {
        "symbol": "EUR/USD",
        "interval": "1m"
    }
}

// Response
{
    "event": "subscribed",
    "symbol": "EUR/USD",
    "interval": "1m"
}
```

#### Real-time Candle Data
```javascript
{
    "event": "candle",
    "symbol": "EUR/USD",
    "interval": "1m",
    "data": {
        "timestamp": "2025-08-18T07:00:00Z",
        "open": 1.2345,
        "high": 1.2350,
        "low": 1.2340,
        "close": 1.2348,
        "volume": 1000000
    }
}
```

#### Trading Signals
```javascript
{
    "event": "signal",
    "symbol": "EUR/USD",
    "data": {
        "type": "LONG",
        "confidence": 0.95,
        "entry": 1.2348,
        "stopLoss": 1.2330,
        "takeProfit": 1.2380,
        "timeframe": "1m",
        "indicators": {
            "rsi": 32,
            "macd": "bullish",
            "volume": "increasing"
        }
    }
}
```

## HTTP Endpoints

### Health and Status

#### Get Health Status
```http
GET /api/v1/health

Response 200 OK:
{
    "status": "healthy",
    "uptime": 3600,
    "lastCheck": "2025-08-18T07:00:00Z"
}
```

#### Get System Status
```http
GET /api/v1/status

Response 200 OK:
{
    "trading": {
        "active": true,
        "mode": "live",
        "positions": 2
    },
    "performance": {
        "cpu": 15.5,
        "memory": 512,
        "connections": 10
    }
}
```

### Trading Operations

#### Get Active Positions
```http
GET /api/v1/positions

Response 200 OK:
{
    "positions": [
        {
            "id": "pos_123",
            "symbol": "EUR/USD",
            "type": "LONG",
            "entry": 1.2348,
            "size": 1000,
            "pnl": 50.25
        }
    ]
}
```

#### Place New Order
```http
POST /api/v1/orders

Request:
{
    "symbol": "EUR/USD",
    "type": "MARKET",
    "side": "BUY",
    "quantity": 1000,
    "stopLoss": 1.2330,
    "takeProfit": 1.2380
}

Response 201 Created:
{
    "orderId": "ord_123",
    "status": "FILLED",
    "filledPrice": 1.2348
}
```

### Configuration

#### Get Configuration
```http
GET /api/v1/config

Response 200 OK:
{
    "trading": {
        "mode": "live",
        "riskLevel": 3,
        "maxPositions": 5
    },
    "indicators": {
        "rsi": {
            "period": 14,
            "overbought": 70,
            "oversold": 30
        }
    }
}
```

#### Update Configuration
```http
PATCH /api/v1/config

Request:
{
    "trading": {
        "riskLevel": 2
    }
}

Response 200 OK:
{
    "status": "updated",
    "changes": ["riskLevel"]
}
```

### Analytics

#### Get Performance Metrics
```http
GET /api/v1/metrics

Response 200 OK:
{
    "daily": {
        "trades": 45,
        "winRate": 0.89,
        "pnl": 250.75
    },
    "weekly": {
        "trades": 215,
        "winRate": 0.92,
        "pnl": 1250.50
    }
}
```

## Integration Interfaces

### Telegram Notifications
```python
from src.telegram_notifier import TelegramNotifier

notifier = TelegramNotifier(config)
notifier.send_alert("New trade opened: EUR/USD LONG")
```

### External Data Sources
```python
from src.utils.fallback_data import FallbackDataManager

data_manager = FallbackDataManager(config)
candles = data_manager.get_historical_data("EUR/USD", "1m")
```

## Error Handling

### Error Response Format
```javascript
{
    "error": {
        "code": "INVALID_ORDER",
        "message": "Insufficient balance",
        "details": {
            "required": 1000,
            "available": 500
        }
    }
}
```

### Common Error Codes
- `INVALID_AUTH`: Authentication failed
- `INVALID_ORDER`: Order validation failed
- `RATE_LIMITED`: Too many requests
- `MARKET_CLOSED`: Trading not available
- `INSUFFICIENT_FUNDS`: Not enough balance
- `INVALID_PARAMS`: Invalid request parameters

## Rate Limiting

### Limits
- WebSocket: 100 messages/second
- REST API: 60 requests/minute
- Historical Data: 10 requests/minute

### Rate Limit Headers
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1692345600
```

## Examples

### Trading Bot Integration
```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    if data["event"] == "signal":
        process_signal(data["data"])

ws = websocket.WebSocketApp(
    "wss://trading-bot:8080/ws/v1/market",
    on_message=on_message
)
ws.run_forever()
```

### Order Management
```python
import requests

def place_order(symbol, side, quantity):
    response = requests.post(
        "https://trading-bot:8080/api/v1/orders",
        json={
            "symbol": symbol,
            "type": "MARKET",
            "side": side,
            "quantity": quantity
        },
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return response.json()

# Place a buy order
order = place_order("EUR/USD", "BUY", 1000)
print(f"Order placed: {order['orderId']}")
```

### Performance Monitoring
```python
import requests
from datetime import datetime, timedelta

def get_daily_performance():
    end = datetime.now()
    start = end - timedelta(days=1)
    
    response = requests.get(
        "https://trading-bot:8080/api/v1/metrics",
        params={
            "start": start.isoformat(),
            "end": end.isoformat()
        },
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return response.json()

performance = get_daily_performance()
print(f"Win Rate: {performance['daily']['winRate']}")
```
