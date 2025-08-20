#!/bin/bash
set -e

echo "Building and starting all services..."
docker compose up -d --build

echo "Checking status of all containers..."
docker compose ps

echo "Viewing logs for the trading bot service..."
docker compose logs trading-bot

echo "Opening Prometheus and Grafana in your browser..."
"$BROWSER" http://localhost:9090
"$BROWSER" http://localhost:3000

echo "Verifying healthcheck status..."
docker inspect --format='{{json .State.Health}}' iq-720-trading-bot

echo "Confirming data persistence..."
docker compose exec trading-bot ls /home/trading/data
docker compose exec trading-bot ls /home/trading/logs
docker compose exec trading-bot ls /home/trading/backtest_results
docker compose exec trading-bot ls /home/trading/backups

echo "Deployment complete."
