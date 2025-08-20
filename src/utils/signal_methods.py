def generate_signal(self) -> Optional[Signal]:
        """Generate trading signal based on market conditions and session timing."""
        if len(self.price_history) < 50:  # Need enough historical data
            return None

        # Check if we're in an optimal trading session
        if not SessionManager.is_optimal_trading_time():
            self.logger.debug("Not in optimal trading session")
            return None

        # Get session-specific thresholds
        momentum_threshold = SessionManager.get_session_momentum_threshold()
        volume_threshold = SessionManager.get_session_volume_threshold()
        confidence_threshold = SessionManager.get_session_confidence_threshold()

        # Calculate technical indicators
        prices = np.array(self.price_history)
        volumes = np.array(self.volume_history)
        
        # RSI for momentum
        rsi = talib.RSI(prices)[-1]
        
        # MACD for trend
        macd, signal, _ = talib.MACD(prices)
        macd_latest = macd[-1]
        signal_latest = signal[-1]
        
        # Bollinger Bands for volatility
        upper, middle, lower = talib.BBANDS(prices)
        bb_width = (upper[-1] - lower[-1]) / middle[-1]

        # Volume analysis
        volume_sma = talib.SMA(volumes, timeperiod=20)[-1]
        volume_sufficient = volumes[-1] > volume_threshold

        # Market condition confidence
        market_confidence = self.market_analyzer.get_market_confidence()
        
        # Initialize indicators dict for signal
        indicators = {
            'rsi': rsi,
            'macd': macd_latest,
            'bb_width': bb_width,
            'volume': volumes[-1],
            'market_confidence': market_confidence
        }

        # Generate signal based on conditions
        signal_direction = None
        confidence = 0.0

        # Strong uptrend conditions
        if (rsi > 50 and macd_latest > signal_latest and 
            market_confidence > confidence_threshold and 
            volume_sufficient):
            signal_direction = "BUY"
            confidence = min(1.0, market_confidence * 1.2)  # Boost confidence slightly

        # Strong downtrend conditions
        elif (rsi < 50 and macd_latest < signal_latest and 
              market_confidence > confidence_threshold and 
              volume_sufficient):
            signal_direction = "SELL"
            confidence = min(1.0, market_confidence * 1.2)

        # If we have a signal direction
        if signal_direction and confidence >= momentum_threshold:
            current_time = self.timestamp_history[-1]
            
            return Signal(
                timestamp=current_time,
                direction=signal_direction,
                asset="EUR/USD",
                expiry_minutes=5,  # Standard for most binary options
                confidence=confidence,
                indicators=indicators
            )

        return None
