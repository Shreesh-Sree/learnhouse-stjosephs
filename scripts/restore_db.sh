#!/usr/bin/env bash
# ==============================================================================
# LearnHouse PostgreSQL Database Restore Script
# Restores a compressed .sql.gz backup file into lms-db.
# ==============================================================================

set -eo pipefail

CONTAINER_NAME="lms-db"
DB_USER="learnhouse"
DB_NAME="learnhouse"

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/backup.sql.gz"
    echo ""
    echo "Available backups in /data/production/lms/backups/postgres/:"
    ls -lh /data/production/lms/backups/postgres/*.sql.gz 2>/dev/null || echo "  (None found)"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file '${BACKUP_FILE}' not found!"
    exit 1
fi

echo "Verifying backup file integrity..."
gzip -t "${BACKUP_FILE}"
echo "Integrity check passed."

# If SHA256 checksum exists, verify it
if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo "Verifying SHA256 checksum..."
    sha256sum -c "${BACKUP_FILE}.sha256"
fi

read -p "WARNING: This will overwrite data in '${DB_NAME}'. Are you sure? (y/N): " -r CONFIRM
if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Restoring database '${DB_NAME}' from '${BACKUP_FILE}'..."
gunzip -c "${BACKUP_FILE}" | docker exec -i -e PGPASSWORD=LearnHouseDB_Pass2026! "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" > /dev/null

echo "Restore complete! Verifying database..."
docker exec -e PGPASSWORD=LearnHouseDB_Pass2026! "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT count(*) AS total_users FROM \"user\";"
