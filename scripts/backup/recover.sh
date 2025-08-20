#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/app/backups"
S3_BUCKET="your-backup-bucket"  # Replace with your S3 bucket
RECOVERY_DIR="/app/recovery"

# Function to check if required tools are installed
check_requirements() {
    command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed. Aborting." >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { echo "tar is required but not installed. Aborting." >&2; exit 1; }
}

# Function to list available backups
list_backups() {
    echo "Available backups in S3:"
    aws s3 ls s3://${S3_BUCKET}/backups/
}

# Function to download backup from S3
download_backup() {
    local BACKUP_NAME=$1
    
    if [ -z "${BACKUP_NAME}" ]; then
        echo "Error: Backup name not provided"
        exit 1
    }
    
    echo "Downloading backup: ${BACKUP_NAME}"
    mkdir -p ${RECOVERY_DIR}
    aws s3 cp s3://${S3_BUCKET}/backups/${BACKUP_NAME} ${RECOVERY_DIR}/
    
    if [ $? -eq 0 ]; then
        echo "Backup downloaded successfully"
    else
        echo "Failed to download backup"
        exit 1
    fi
}

# Function to restore backup
restore_backup() {
    local BACKUP_FILE=$1
    
    if [ ! -f "${RECOVERY_DIR}/${BACKUP_FILE}" ]; then
        echo "Error: Backup file not found"
        exit 1
    }
    
    echo "Stopping trading bot services..."
    docker-compose down
    
    echo "Creating backup of current state..."
    ./scripts/backup/backup.sh
    
    echo "Restoring from backup..."
    # Create temporary directory for restoration
    TMP_DIR=$(mktemp -d)
    
    # Extract backup
    tar -xzf ${RECOVERY_DIR}/${BACKUP_FILE} -C ${TMP_DIR}
    
    # Restore data
    if [ -d "${TMP_DIR}/data" ]; then
        echo "Restoring trading data..."
        rm -rf /app/data/*
        cp -r ${TMP_DIR}/data/* /app/data/
    fi
    
    # Restore configuration
    echo "Restoring configuration..."
    cp ${TMP_DIR}/env_backup /app/.env
    cp ${TMP_DIR}/docker-compose_backup.yml /app/docker-compose.yml
    
    # Cleanup
    rm -rf ${TMP_DIR}
    
    echo "Restarting trading bot services..."
    docker-compose up -d
    
    echo "Waiting for services to start..."
    sleep 30
    
    # Verify restoration
    if docker-compose ps | grep -q "trading-bot.*Up"; then
        echo "Restoration completed successfully!"
    else
        echo "Warning: Services may not have started properly"
        docker-compose logs
    fi
}

# Function to verify backup integrity
verify_backup() {
    local BACKUP_FILE=$1
    
    echo "Verifying backup integrity..."
    
    # Create temporary directory for verification
    TMP_DIR=$(mktemp -d)
    
    # Try to extract backup
    if tar -tzf ${RECOVERY_DIR}/${BACKUP_FILE} > /dev/null 2>&1; then
        echo "Backup archive is valid"
        
        # Extract and check for required files
        tar -xzf ${RECOVERY_DIR}/${BACKUP_FILE} -C ${TMP_DIR}
        
        # Check for essential components
        REQUIRED_FILES=("env_backup" "docker-compose_backup.yml")
        for file in "${REQUIRED_FILES[@]}"; do
            if [ ! -f "${TMP_DIR}/${file}" ]; then
                echo "Warning: Missing required file: ${file}"
                rm -rf ${TMP_DIR}
                return 1
            fi
        done
        
        echo "Backup contains all required components"
        rm -rf ${TMP_DIR}
        return 0
    else
        echo "Error: Backup archive is corrupted"
        rm -rf ${TMP_DIR}
        return 1
    fi
}

# Main execution
check_requirements

case "$1" in
    "list")
        list_backups
        ;;
    "download")
        if [ -z "$2" ]; then
            echo "Error: Please provide backup name"
            exit 1
        fi
        download_backup "$2"
        ;;
    "restore")
        if [ -z "$2" ]; then
            echo "Error: Please provide backup file name"
            exit 1
        fi
        if verify_backup "$2"; then
            restore_backup "$2"
        else
            echo "Error: Backup verification failed"
            exit 1
        fi
        ;;
    "verify")
        if [ -z "$2" ]; then
            echo "Error: Please provide backup file name"
            exit 1
        fi
        verify_backup "$2"
        ;;
    *)
        echo "Usage: $0 {list|download|restore|verify} [backup_name]"
        exit 1
        ;;
esac
