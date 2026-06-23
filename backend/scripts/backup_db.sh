#!/bin/bash
set -euo pipefail

# InnovOS Database Backup Script
# Usage: ./scripts/backup_db.sh [output_dir]
# Requires: pg_dump, DATABASE_URL in .env or environment

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${1:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/innovos_$TIMESTAMP.sql.gz"

# Load .env if present
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
    echo "Error: DATABASE_URL is not set"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Backing up to $BACKUP_FILE ..."
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"
echo "Done: $(du -h "$BACKUP_FILE" | cut -f1)"

# Keep only last 30 backups
find "$BACKUP_DIR" -name "innovos_*.sql.gz" -mtime +30 -delete
echo "Cleaned backups older than 30 days."
