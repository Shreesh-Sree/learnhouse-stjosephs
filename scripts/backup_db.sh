#!/usr/bin/env bash
# ==============================================================================
# LearnHouse Automated PostgreSQL Backup Script
# Creates compressed, timestamped database dumps with SHA256 integrity verification
# and automated retention rotation.
# ==============================================================================

set -eo pipefail

BACKUP_DIR="/data/production/lms/backups/postgres"
CONTAINER_NAME="lms-db"
DB_USER="learnhouse"
DB_NAME="learnhouse"
RETENTION_DAYS=14
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/learnhouse_backup_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
LOG_FILE="${BACKUP_DIR}/backup.log"

mkdir -p "${BACKUP_DIR}"

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*" | tee -a "${LOG_FILE}"
}

log "Starting database backup for '${DB_NAME}' from container '${CONTAINER_NAME}'..."

# Verify container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "ERROR: Container '${CONTAINER_NAME}' is not running! Aborting backup."
    exit 1
fi

# Execute pg_dump, pipe through gzip -9
if docker exec -e PGPASSWORD=LearnHouseDB_Pass2026! "${CONTAINER_NAME}" \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists --no-owner | gzip -9 > "${BACKUP_FILE}"; then
    
    # Test gzip integrity
    if gzip -t "${BACKUP_FILE}"; then
        FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
        sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
        log "SUCCESS: Backup created at ${BACKUP_FILE} (Size: ${FILE_SIZE})"
    else
        log "ERROR: Backup file corrupted, gzip test failed! Removing ${BACKUP_FILE}"
        rm -f "${BACKUP_FILE}"
        exit 1
    fi
else
    log "ERROR: pg_dump failed! Removing partial backup ${BACKUP_FILE}"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Automated retention cleanup: remove backups older than RETENTION_DAYS
log "Rotating backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "learnhouse_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "learnhouse_backup_*.sql.gz.sha256" -type f -mtime +${RETENTION_DAYS} -delete

TOTAL_BACKUPS=$(find "${BACKUP_DIR}" -name "learnhouse_backup_*.sql.gz" -type f | wc -l)
log "Retention rotation complete. Total backups preserved: ${TOTAL_BACKUPS}."
