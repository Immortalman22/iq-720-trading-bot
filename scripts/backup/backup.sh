#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/app/backups"
DATA_DIR="/app/data"
LOGS_DIR="/app/logs"
BACKUP_RETENTION_DAYS=30
S3_BUCKET="your-backup-bucket"  # Replace with your S3 bucket
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="trading_bot_backup_${TIMESTAMP}"

# Ensure backup directory exists
mkdir -p ${BACKUP_DIR}

# Function to check if required tools are installed
check_requirements() {
    command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed. Aborting." >&2; exit 1; }
    command -v tar >/dev/null 2>&1 || { echo "tar is required but not installed. Aborting." >&2; exit 1; }
}

# Function to create backup
create_backup() {
    echo "Creating backup: ${BACKUP_NAME}"
    
    # Create temporary directory for backup
    TMP_DIR=$(mktemp -d)
    
    # Backup trading data
    if [ -d "${DATA_DIR}" ]; then
        echo "Backing up trading data..."
        cp -r ${DATA_DIR} ${TMP_DIR}/data
    fi
    
    # Backup configuration
    echo "Backing up configuration..."
    cp /app/.env ${TMP_DIR}/env_backup
    cp /app/docker-compose.yml ${TMP_DIR}/docker-compose_backup.yml
    
    # Backup recent logs
    if [ -d "${LOGS_DIR}" ]; then
        echo "Backing up recent logs..."
        find ${LOGS_DIR} -type f -mtime -7 -exec cp {} ${TMP_DIR}/logs/ \;
    fi
    
    # Create compressed archive
    tar -czf ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz -C ${TMP_DIR} .
    
    # Cleanup temporary directory
    rm -rf ${TMP_DIR}
    
    echo "Backup created successfully: ${BACKUP_NAME}.tar.gz"
}

# Function to upload backup to S3
upload_to_s3() {
    echo "Uploading backup to S3..."
    aws s3 cp ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz s3://${S3_BUCKET}/backups/
    
    if [ $? -eq 0 ]; then
        echo "Backup uploaded successfully to S3"
    else
        echo "Failed to upload backup to S3"
        exit 1
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    echo "Cleaning up old backups..."
    
    # Local cleanup
    find ${BACKUP_DIR} -type f -name "trading_bot_backup_*.tar.gz" -mtime +${BACKUP_RETENTION_DAYS} -delete
    
    # S3 cleanup
    aws s3 ls s3://${S3_BUCKET}/backups/ | grep "trading_bot_backup_" | while read -r line; do
        createDate=$(echo $line | awk {'print $1" "$2'})
        createDate=$(date -d "$createDate" +%s)
        olderThan=$(date -d "${BACKUP_RETENTION_DAYS} days ago" +%s)
        
        if [[ $createDate -lt $olderThan ]]; then
            fileName=$(echo $line | awk {'print $4'})
            echo "Deleting old backup: $fileName"
            aws s3 rm s3://${S3_BUCKET}/backups/$fileName
        fi
    done
}

# Main execution
check_requirements
create_backup
upload_to_s3
cleanup_old_backups

echo "Backup process completed successfully!"
