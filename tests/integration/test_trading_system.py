import pytest
from datetime import datetime, timedelta
from src.signal_generator import SignalGenerator
from src.data_fetcher import IQOptionDataFetcher
from src.utils.market_analyzer import MarketAnalyzer
from src.utils.news.forex_news import ForexNewsFilter
from src.utils.config import Config
import pandas as pd
import numpy as np

class TestIntegration:
    @pytest.fixture
    def setup_components(self):
        config = Config.load_from_env()
        signal_generator = SignalGenerator()
        data_fetcher = IQOptionDataFetcher(config, signal_generator.add_candle)
        market_analyzer = MarketAnalyzer()
        news_filter = ForexNewsFilter()
        
        return {
            'config': config,
            'signal_generator': signal_generator,
            'data_fetcher': data_fetcher,
            'market_analyzer': market_analyzer,
            'news_filter': news_filter
        }

    def test_full_signal_generation_pipeline(self, setup_components):
        """Test the complete signal generation pipeline"""
        components = setup_components
        signal_gen = components['signal_generator']
        market_analyzer = components['market_analyzer']

        # Create sample market data
        base_price = 1.2000
        timestamps = pd.date_range(
            start=datetime.now() - timedelta(hours=1),
            end=datetime.now(),
            freq='1min'
        )

        signals = []
        for i, timestamp in enumerate(timestamps):
            # Generate realistic price movement
            price = base_price + np.sin(i/10) * 0.0010
            volume = 1000 + np.random.randint(-200, 200)

            candle = {
                'timestamp': timestamp.timestamp(),
                'open': price - 0.0002,
                'high': price + 0.0003,
                'low': price - 0.0003,
                'close': price,
                'volume': volume
            }

            # Process candle through the pipeline
            signal = signal_gen.add_candle(candle)
            if signal:
                signals.append(signal)

        # Verify signal properties
        for signal in signals:
            assert hasattr(signal, 'direction')
            assert hasattr(signal, 'confidence')
            assert hasattr(signal, 'indicators')
            assert 0 <= signal.confidence <= 1

    def test_news_and_market_conditions_integration(self, setup_components):
        """Test integration between news filter and market analysis"""
        components = setup_components
        signal_gen = components['signal_generator']
        news_filter = components['news_filter']
        market_analyzer = components['market_analyzer']

        # Set up a test scenario
        current_time = datetime.now()
        
        # 1. No news, good market conditions
        with pytest.MonkeyPatch.context() as m:
            m.setattr(news_filter, 'is_news_time', lambda x, y: False)
            m.setattr(market_analyzer, 'is_favorable_condition', 
                     lambda: (True, 0.8, "Good conditions"))
            
            assert signal_gen._check_trading_conditions()

        # 2. News event, good market conditions
        with pytest.MonkeyPatch.context() as m:
            m.setattr(news_filter, 'is_news_time', lambda x, y: True)
            m.setattr(market_analyzer, 'is_favorable_condition',
                     lambda: (True, 0.8, "Good conditions"))
            
            assert not signal_gen._check_trading_conditions()

        # 3. No news, bad market conditions
        with pytest.MonkeyPatch.context() as m:
            m.setattr(news_filter, 'is_news_time', lambda x, y: False)
            m.setattr(market_analyzer, 'is_favorable_condition',
                     lambda: (False, 0.3, "Poor conditions"))
            
            assert not signal_gen._check_trading_conditions()

    def test_fallback_data_integration(self, setup_components):
        """Test integration with fallback data sources"""
        components = setup_components
        data_fetcher = components['data_fetcher']
        signal_gen = components['signal_generator']

        # Simulate primary source failure
        data_fetcher._on_error(None, Exception("Connection lost"))
        assert data_fetcher.using_fallback

        # Test fallback data processing
        test_data = {
            'timestamp': datetime.now().timestamp(),
            'price': 1.2000,
            'source': 'Binance',
            'volume': 1000
        }

        with pytest.MonkeyPatch.context() as m:
            m.setattr(data_fetcher.fallback, 'get_current_data',
                     lambda: test_data)
            
            data_fetcher._poll_fallback_data()
            # Verify data was processed by signal generator
            assert len(signal_gen.price_history) > 0

    def test_risk_management_integration(self, setup_components):
        """Test integration of risk management rules"""
        components = setup_components
        signal_gen = components['signal_generator']

        # Test consecutive losses limit
        for _ in range(3):
            signal_gen.record_trade_result(False)
        
        # Should not generate signals after 3 losses
        candle = {
            'timestamp': datetime.now().timestamp(),
            'close': 1.2000,
            'volume': 1000
        }
        assert signal_gen.add_candle(candle) is None

        # Reset and test daily trade limit
        signal_gen.consecutive_losses = 0
        signal_gen.trades_today = 15
        assert signal_gen.add_candle(candle) is None
