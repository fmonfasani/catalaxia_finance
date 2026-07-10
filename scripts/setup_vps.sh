#!/usr/bin/env bash
# setup_vps.sh — Instalacion automatizada del pipeline Catalaxia en VPS Hetzner
# Ejecutar como root en el VPS
#
# Uso:
#   chmod +x setup_vps.sh && ./setup_vps.sh
#
# Requiere: Docker, Docker Compose, git (preinstalados en la imagen Ubuntu de Hetzner)
set -euo pipefail

# ── Configuracion ────────────────────────────────────────────────────
PROJECT_DIR="/infra/projects/0009-catalaxia"
REPO_URL="git@github.com:anomalyco/catalaxia-cedears-prod.git"  # <-- CAMBIAR
BRANCH="main"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-catalaxia_prod_2024}"
DB_NAME="catalaxia"
DB_USER="catalaxia"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_DIR="${PROJECT_DIR}/logs"
DATA_DIR="${PROJECT_DIR}/data"

echo "========================================"
echo "  Catalaxia — Instalacion VPS"
echo "========================================"
echo ""

# ── 1. Verificar prerequisitos ──────────────────────────────────────
echo "[1/8] Verificando prerequisitos..."

for cmd in docker docker-compose git; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERROR: $cmd no instalado"
        exit 1
    fi
done
echo "  Docker: $(docker --version)"
echo "  Compose: $(docker compose version)"
echo "  Git: $(git --version)"
echo "  OK"

# ── 2. Crear estructura de directorios ───────────────────────────────
echo ""
echo "[2/8] Creando estructura de directorios..."
mkdir -p "${PROJECT_DIR}"
mkdir -p "${BACKUP_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${DATA_DIR}"/{logs,raw/{companyfacts,submissions}}
echo "  Directorios creados en ${PROJECT_DIR}"
echo "  OK"

# ── 3. Clonar (o actualizar) repo ───────────────────────────────────
echo ""
echo "[3/8] Clonando repositorio..."
if [ -d "${PROJECT_DIR}/.git" ]; then
    echo "  Repo existente, actualizando..."
    cd "${PROJECT_DIR}"
    git fetch origin "${BRANCH}"
    git reset --hard "origin/${BRANCH}"
else
    git clone "${REPO_URL}" "${PROJECT_DIR}" --branch "${BRANCH}"
    cd "${PROJECT_DIR}"
fi
echo "  OK"

# ── 4. Preparar .env ────────────────────────────────────────────────
echo ""
echo "[4/8] Configurando .env..."
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    cat > "${PROJECT_DIR}/.env" <<EOF
# Catalaxia — Variables de entorno
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DB_TYPE=postgresql
DB_HOST=db
DB_PORT=5432
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
EOF
    echo "  .env creado"
else
    echo "  .env ya existe, se conserva"
fi
# Proteger .env
chmod 600 "${PROJECT_DIR}/.env"
echo "  OK"

# ── 5. Levantar PostgreSQL ──────────────────────────────────────────
echo ""
echo "[5/8] Levantando PostgreSQL..."
cd "${PROJECT_DIR}"
docker compose up -d db
echo "  Esperando que PostgreSQL esté saludable..."
for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U "${DB_USER}" -d "${DB_NAME}" &>/dev/null; then
        echo "  PostgreSQL listo!"
        break
    fi
    sleep 2
done
echo "  OK"

# ── 6. Migrar datos (si existe screener.db) ─────────────────────────
echo ""
echo "[6/8] Migrando datos desde SQLite..."
SCREENER_DB="${DATA_DIR}/screener.db"
if [ -f "${SCREENER_DB}" ]; then
    echo "  screener.db encontrado, migrando a PostgreSQL..."
    docker compose run --rm -e DB_TYPE=postgresql \
        -e DB_HOST=db -e DB_PORT=5432 \
        -e DB_NAME=${DB_NAME} -e DB_USER=${DB_USER} \
        -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
        pipeline python scripts/tickets/screener/migrate_sqlite_to_pg.py
    echo "  Migracion completada"
else
    echo "  No hay screener.db — se correra pipeline completo luego"
fi
echo "  OK"

# ── 7. Probar pipeline ─────────────────────────────────────────────
echo ""
echo "[7/8] Probando pipeline (modo rebuild)..."
docker compose run --rm pipeline python scripts/tickets/screener/run_update.py --rebuild --quiet
echo "  Pipeline OK"

# ── 8. Configurar cron jobs ─────────────────────────────────────────
echo ""
echo "[8/8] Configurando cron jobs..."

CRON_FILE="/etc/cron.d/catalaxia"
cat > "${CRON_FILE}" <<'CRON'
# Catalaxia — Pipeline de actualizacion
# Daily: precios yfinance (lun-vie 18hs)
30 18 * * 1-5 root cd /infra/projects/0009-catalaxia && /usr/bin/docker compose run --rm pipeline python scripts/tickets/screener/run_update.py --daily --quiet >> /infra/projects/0009-catalaxia/logs/cron_daily.log 2>&1

# Monthly: IPC (1ro del mes 08hs)
0 8 1 * * root cd /infra/projects/0009-catalaxia && /usr/bin/docker compose run --rm pipeline python scripts/tickets/screener/run_update.py --monthly --quiet >> /infra/projects/0009-catalaxia/logs/cron_monthly.log 2>&1

# Quarterly: EDGAR+CNV (1ro del trimestre 10hs)
0 10 1 1,4,7,10 * root cd /infra/projects/0009-catalaxia && /usr/bin/docker compose run --rm pipeline python scripts/tickets/screener/run_update.py --quarterly --quiet >> /infra/projects/0009-catalaxia/logs/cron_quarterly.log 2>&1

# Annual: ADR ratios (1ro de enero 12hs)
0 12 1 1 * root cd /infra/projects/0009-catalaxia && /usr/bin/docker compose run --rm pipeline python scripts/tickets/screener/run_update.py --annual --quiet >> /infra/projects/0009-catalaxia/logs/cron_annual.log 2>&1

# Backup diario: DB + exports (030hs todos los dias)
0 3 * * * root /infra/projects/0009-catalaxia/scripts/backup.sh >> /infra/projects/0009-catalaxia/logs/cron_backup.log 2>&1
CRON

chmod 644 "${CRON_FILE}"
systemctl restart cron 2>/dev/null || service cron restart 2>/dev/null || /etc/init.d/cron restart 2>/dev/null || echo "  ATENCION: recargar cron manualmente"
echo "  Cron jobs instalados en ${CRON_FILE}"
echo "  OK"

# ── Resumen ─────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  INSTALACION COMPLETADA"
echo "========================================"
echo ""
echo "  Proyecto:   ${PROJECT_DIR}"
echo "  DB:         PostgreSQL (container: catalaxia-db)"
echo "  Backups:    ${BACKUP_DIR}"
echo "  Logs:       ${LOG_DIR}"
echo ""
echo "  Comandos utiles:"
echo "    docker compose -f ${PROJECT_DIR}/docker-compose.yml up -d db       # iniciar solo DB"
echo "    docker compose -f ${PROJECT_DIR}/docker-compose.yml run --rm pipeline python scripts/tickets/screener/run_all.py  # rebuild completo"
echo "    docker compose -f ${PROJECT_DIR}/docker-compose.yml run --rm pipeline python scripts/tickets/screener/run_update.py --daily  # daily update"
echo "    ${PROJECT_DIR}/scripts/backup.sh  # backup manual"
echo ""
echo "  Para exportar la DB local a PostgreSQL:"
echo "    1) Copiar data/screener.db a ${DATA_DIR}/ en el VPS"
echo "    2) docker compose run --rm pipeline python scripts/tickets/screener/migrate_sqlite_to_pg.py"
echo ""
