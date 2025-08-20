# Use Python 3.10 for better performance and compatibility
FROM python:3.10-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/trading/.local/bin:${PATH}"

# Create non-root user
RUN groupadd -r trading && \
    useradd -r -g trading -d /home/trading -m -s /bin/bash trading && \
    chown -R trading:trading /home/trading

# Set working directory
WORKDIR /app

# Install system dependencies including TA-Lib
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    ca-certificates \
    && wget --no-verbose http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && echo "c265b65737f3a54d3371c404b635c6ed4af47c2f ta-lib-0.4.0-src.tar.gz" | sha1sum -c - \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Create final stage
FROM python:3.10-slim

# Copy TA-Lib from builder
COPY --from=builder /usr/lib/libta_lib* /usr/lib/
COPY --from=builder /usr/include/ta-lib /usr/include/ta-lib

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/trading/.local/bin:${PATH}"

# Create non-root user
RUN groupadd -r trading && \
    useradd -r -g trading -d /home/trading -m -s /bin/bash trading && \
    chown -R trading:trading /home/trading

# Install runtime dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory and switch to non-root user
WORKDIR /app
USER trading

# Copy requirements first for better caching
COPY --chown=trading:trading requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY --chown=trading:trading src/ ./src/
COPY --chown=trading:trading scripts/ ./scripts/

# Create necessary directories with correct permissions
RUN mkdir -p /home/trading/data /home/trading/logs /home/trading/backtest_results

# Copy entrypoint script
COPY --chown=trading:trading scripts/entrypoint.sh /home/trading/entrypoint.sh
RUN chmod +x /home/trading/entrypoint.sh

# Add container security labels
LABEL org.label-schema.schema-version="1.0" \
      org.label-schema.name="iq-720-trading-bot" \
      org.label-schema.description="Secure IQ-720 Trading Bot" \
      org.label-schema.vendor="Trading Systems" \
      security.capabilities.drop="ALL" \
      security.privileged="false" \
      security.readonly-rootfs="true"

# Set up healthcheck with proper timeout and non-root path
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import requests; requests.get('http://localhost:8080/health', timeout=5)"]

# Run the bot with proper security context
ENTRYPOINT ["/home/trading/entrypoint.sh"]
CMD ["python", "-m", "src.main"]
