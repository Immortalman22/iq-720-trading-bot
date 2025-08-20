"""
Trading session manager for optimizing trades based on market hours.
Specifically optimized for South African time zone (SAST/GMT+2).
"""
from datetime import datetime, time
from enum import Enum
from typing import Optional

class TradingSession(Enum):
    ASIAN = "ASIAN"
    LONDON_PRE = "LONDON_PRE"
    LONDON = "LONDON"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    NEW_YORK = "NEW_YORK"
    OFF_HOURS = "OFF_HOURS"

class SessionManager:
    # Define session times in SAST (GMT+2)
    SESSION_TIMES = {
        TradingSession.ASIAN: (time(0, 0), time(8, 0)),
        TradingSession.LONDON_PRE: (time(8, 0), time(9, 0)),
        TradingSession.LONDON: (time(9, 0), time(14, 0)),
        TradingSession.LONDON_NY_OVERLAP: (time(14, 0), time(18, 0)),
        TradingSession.NEW_YORK: (time(18, 0), time(22, 0)),
        TradingSession.OFF_HOURS: (time(22, 0), time(23, 59, 59))
    }

    # Session-specific settings
    SESSION_CONFIGS = {
        TradingSession.ASIAN: {
            'momentum_threshold': 0.8,  # Higher threshold due to lower volatility
            'min_volume': 1000,
            'confidence_threshold': 0.8
        },
        TradingSession.LONDON_PRE: {
            'momentum_threshold': 0.6,
            'min_volume': 800,
            'confidence_threshold': 0.7
        },
        TradingSession.LONDON: {
            'momentum_threshold': 0.5,
            'min_volume': 500,
            'confidence_threshold': 0.65
        },
        TradingSession.LONDON_NY_OVERLAP: {
            'momentum_threshold': 0.4,  # Lower threshold due to higher liquidity
            'min_volume': 300,
            'confidence_threshold': 0.6
        },
        TradingSession.NEW_YORK: {
            'momentum_threshold': 0.5,
            'min_volume': 500,
            'confidence_threshold': 0.65
        },
        TradingSession.OFF_HOURS: {
            'momentum_threshold': 0.9,  # Very high threshold during off hours
            'min_volume': 1200,
            'confidence_threshold': 0.85
        }
    }

    @classmethod
    def get_current_session(cls) -> TradingSession:
        """Get the current trading session based on SAST time."""
        current_time = datetime.now().time()
        
        for session, (start, end) in cls.SESSION_TIMES.items():
            if start <= current_time < end:
                return session
            
        return TradingSession.OFF_HOURS

    @classmethod
    def get_session_config(cls, session: Optional[TradingSession] = None) -> dict:
        """Get configuration for the specified or current session."""
        if session is None:
            session = cls.get_current_session()
        return cls.SESSION_CONFIGS[session]

    @classmethod
    def is_optimal_trading_time(cls) -> bool:
        """Check if current time is optimal for trading."""
        current_session = cls.get_current_session()
        return current_session in [
            TradingSession.LONDON_NY_OVERLAP,
            TradingSession.LONDON,
            TradingSession.NEW_YORK
        ]

    @classmethod
    def get_session_momentum_threshold(cls) -> float:
        """Get the momentum threshold for the current session."""
        return cls.get_session_config()['momentum_threshold']

    @classmethod
    def get_session_volume_threshold(cls) -> float:
        """Get the minimum volume threshold for the current session."""
        return cls.get_session_config()['min_volume']

    @classmethod
    def get_session_confidence_threshold(cls) -> float:
        """Get the confidence threshold for the current session."""
        return cls.get_session_config()['confidence_threshold']
