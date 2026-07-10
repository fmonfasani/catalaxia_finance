#!/usr/bin/env bash
# backup.sh — Backup diario de PostgreSQL + exports
# Ejecutar via cron o manualmente
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="/infra/projects/0009-catalaxia"
BACKUP_DIR="${PROJECT_DIR}/backups"
DATA_DIR="${PROJECT_DIR}/data"
RETENTION_DAYS=30

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Iniciando backup..."

# 1. Dump PostgreSQL
echo "  Dump PostgreSQL..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    pg_dump -U catalaxia catalaxia --no-owner --no-acl \
    > "${BACKUP_DIR}/catalaxia_db_${DATE}.sql"
gzip "${BACKUP_DIR}/catalaxia_db_${DATE}.sql"
echo "  DB dump: ${BACKUP_DIR}/catalaxia_db_${DATE}.sql.gz"

# 2. Copiar exports
if [ -f "${DATA_DIR}/screener_export.csv" ]; then
    cp "${DATA_DIR}/screener_export.csv" "${BACKUP_DIR}/screener_export_${DATE}.csv"
fi
if [ -f "${DATA_DIR}/screener_export.json" ]; then
    cp "${DATA_DIR}/screener_export.json" "${BACKUP_DIR}/screener_export_${DATE}.json"
fi
if [ -f "${DATA_DIR}/instrumentos.csv" ]; then
    cp "${DATA_DIR}/instrumentos.csv" "${BACKUP_DIR}/instrumentos_${DATE}.csv"
fi
if [ -f "${DATA_DIR}/instrumentos.json" ]; then
    cp "${DATA_DIR}/instrumentos.json" "${BACKUP_DIR}/instrumentos_${DATE}.json"
fi
if [ -f "${DATA_DIR}/cedear_ratios.csv" ]; then
    cp "${DATA_DIR}/cedear_ratios.csv" "${BACKUP_DIR}/cedear_ratios_${DATE}.csv"
fi
echo "  Exports copiados"

# 3. Limpiar backups viejos
find "${BACKUP_DIR}" -name "catalaxia_db_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "screener_export_*.csv" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "screener_export_*.json" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "instrumentos_*.csv" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "instrumentos_*.json" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "cedear_ratios_*.csv" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
echo "  Backup viejos (>${RETENTION_DAYS} dias) eliminados"

echo "[$(date)] Backup completado"
