#!/bin/bash
set -e

# Initialize logs directory
mkdir -p /app/logs

# Wait for any required services (if needed)
# Example: wait-for-it.sh database:5432

# Check if environment variables are set
required_vars=("IQ_OPTION_WS_URL" "TELEGRAM_BOT_TOKEN" "TELEGRAM_CHAT_ID")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required environment variable $var is not set"
        exit 1
    fi
done

# Run database migrations if needed
# Example: python -m alembic upgrade head

# Start the monitoring server in the background
python -m src.monitoring.server &

# Execute the main command
exec "$@"
