#!/bin/bash
set -e

# Deploy script for the IQ-720 Trading Bot
# This script helps manage deployment to different environments

# Default values
ENV="production"
ACTION="deploy"
DOCKER_REGISTRY="your-registry.com"  # Replace with your registry

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -e|--environment)
            ENV="$2"
            shift
            shift
            ;;
        -a|--action)
            ACTION="$2"
            shift
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Load environment variables
if [ -f ".env.${ENV}" ]; then
    source ".env.${ENV}"
else
    echo "Error: Environment file .env.${ENV} not found"
    exit 1
fi

# Function to check requirements
check_requirements() {
    command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting." >&2; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required but not installed. Aborting." >&2; exit 1; }
}

# Function to build and push Docker image
build_and_push() {
    echo "Building Docker image..."
    docker build -t ${DOCKER_REGISTRY}/iq-720-trading-bot:${ENV} .
    
    echo "Pushing image to registry..."
    docker push ${DOCKER_REGISTRY}/iq-720-trading-bot:${ENV}
}

# Function to deploy the application
deploy() {
    echo "Deploying to ${ENV} environment..."
    
    # Pull latest images
    docker-compose -f docker-compose.yml pull
    
    # Deploy with zero downtime
    docker-compose -f docker-compose.yml up -d --remove-orphans
    
    # Wait for health check
    echo "Waiting for health check..."
    sleep 30
    
    # Verify deployment
    if docker-compose ps | grep -q "trading-bot.*Up"; then
        echo "Deployment successful!"
    else
        echo "Deployment failed!"
        docker-compose logs
        exit 1
    fi
}

# Function to rollback deployment
rollback() {
    echo "Rolling back to previous version..."
    docker-compose -f docker-compose.yml down
    docker-compose -f docker-compose.yml up -d --no-deps trading-bot
}

# Function to check logs
check_logs() {
    echo "Checking logs..."
    docker-compose logs --tail=100 trading-bot
}

# Main execution
check_requirements

case $ACTION in
    "deploy")
        build_and_push
        deploy
        check_logs
        ;;
    "rollback")
        rollback
        check_logs
        ;;
    "logs")
        check_logs
        ;;
    *)
        echo "Unknown action: $ACTION"
        exit 1
        ;;
esac

echo "Operation completed successfully!"
