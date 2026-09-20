# Deploy en Hetzner — CI/CD automático sin Coolify

**Stack:** Docker Compose + GitHub Actions + Nginx + Certbot  
**Fecha:** Septiembre 2026  
**Reemplaza:** Coolify (eliminado)

---

## Arquitectura del deploy

```
GitHub (main branch)
        │
        │  push → trigger
        ▼
GitHub Actions (CI/CD)
  1. Corre tests (backend + frontend)
  2. Build Docker images
  3. Push a GitHub Container Registry (ghcr.io)
  4. SSH → Hetzner VPS
  5. docker compose pull + up -d --no-deps
        │
        ▼
Hetzner Cloud VPS (CX22 o CX32)
  ├── Nginx (puerto 80/443) → reverse proxy + SSL
  ├── Docker: api (FastAPI, puerto 8100 interno)
  ├── Docker: db (PostgreSQL, solo interno)
  └── Docker: frontend (Next.js, puerto 3000 interno)
```

**Zero-downtime:** `docker compose up -d --no-deps --build` levanta el nuevo container antes de matar el viejo para cada servicio.

---

## Paso 1 — Provisionar el servidor Hetzner

### Specs recomendadas

| Proyecto | Server | RAM | CPU | Disco | Precio/mes |
|---------|--------|-----|-----|-------|-----------|
| Catalaxia solo | **CX22** | 4 GB | 2 vCPU | 40 GB | ~€4.5 |
| Catalaxia + SaaS | **CX32** | 8 GB | 4 vCPU | 80 GB | ~€9 |
| Crecimiento | **CX42** | 16 GB | 8 vCPU | 160 GB | ~€18 |

**Recomendación inicial:** CX22 para Catalaxia solo. Upgrade a CX32 cuando arranque el SaaS (2 minutos de migración en Hetzner, sin cambiar IP si usás floating IP).

### Crear el servidor

```bash
# Via Hetzner Cloud Console o hcloud CLI:
hcloud server create \
  --name catalaxia-prod \
  --type cx22 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key tu-clave-ssh
```

**Opciones importantes:**
- **Ubicación:** `nbg1` (Núremberg) — más cerca de Argentina que Frankfurt
- **OS:** Ubuntu 24.04 LTS (soporte hasta 2029)
- **SSH key:** agregar tu clave pública antes de crear

### Setup inicial del servidor

```bash
# Como root, en el servidor:

# 1. Actualizar sistema
apt update && apt upgrade -y

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# 3. Instalar Nginx + Certbot
apt install -y nginx certbot python3-certbot-nginx

# 4. Instalar hcloud CLI (opcional, para snapshots desde el server)
# apt install -y hcloud-cli

# 5. Crear usuario deploy (no usar root para el deploy)
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# 6. Crear directorio del proyecto
mkdir -p /opt/catalaxia
chown -R deploy:deploy /opt/catalaxia
```

---

## Paso 2 — Configurar GitHub Actions secrets

En tu repo GitHub → Settings → Secrets and variables → Actions:

| Secret | Valor |
|--------|-------|
| `HETZNER_HOST` | IP del servidor (ej: `49.12.xxx.xxx`) |
| `HETZNER_USER` | `deploy` |
| `HETZNER_SSH_KEY` | Contenido de tu clave privada SSH (la que usaste al crear el server) |
| `POSTGRES_PASSWORD` | Password seguro para la DB de producción |
| `API_SECRET_KEY` | Secret para JWT/tokens de la API |
| `GHCR_TOKEN` | GitHub Personal Access Token con `write:packages` |

---

## Paso 3 — GitHub Actions workflow

Crear en `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Hetzner

on:
  push:
    branches: [main]
  workflow_dispatch:  # permite deploy manual desde GitHub UI

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Backend tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest tests/ -v --tb=short

      - name: Frontend lint + typecheck
        run: |
          cd frontend
          npm ci
          npm run lint
          npm run typecheck

  deploy:
    needs: test  # solo deploy si tests pasan
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GHCR_TOKEN }}

      - name: Build y push imagen API
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          file: ./backend/Dockerfile.api
          push: true
          tags: ghcr.io/${{ github.repository }}/api:latest

      - name: Build y push imagen Frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ghcr.io/${{ github.repository }}/frontend:latest

      - name: Deploy en Hetzner
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: ${{ secrets.HETZNER_USER }}
          key: ${{ secrets.HETZNER_SSH_KEY }}
          script: |
            cd /opt/catalaxia
            git pull origin main

            # Escribir .env con secrets (nunca en el repo)
            cat > .env << EOF
            POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}
            API_SECRET_KEY=${{ secrets.API_SECRET_KEY }}
            GHCR_IMAGE=ghcr.io/${{ github.repository }}
            EOF

            # Pull nuevas imágenes y reiniciar contenedores
            docker compose pull
            docker compose up -d --no-deps

            # Limpiar imágenes viejas
            docker image prune -f

            # Verificar que la API responde
            sleep 10
            curl -f http://localhost:8100/health || exit 1

            echo "✅ Deploy exitoso"
```

---

## Paso 4 — docker-compose.yml para producción

```yaml
# /opt/catalaxia/docker-compose.yml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: catalaxia
      POSTGRES_USER: catalaxia
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U catalaxia"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  api:
    image: ghcr.io/${GHCR_IMAGE}/api:latest
    restart: always
    environment:
      DATABASE_URL: postgresql://catalaxia:${POSTGRES_PASSWORD}@db:5432/catalaxia
      SECRET_KEY: ${API_SECRET_KEY}
      LOG_LEVEL: info
    ports:
      - "8100:8100"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - internal

  frontend:
    image: ghcr.io/${GHCR_IMAGE}/frontend:latest
    restart: always
    environment:
      NEXT_PUBLIC_API_URL: https://api.catalaxia.webshooks.com
    ports:
      - "3000:3000"
    networks:
      - internal

volumes:
  pgdata:
    driver: local

networks:
  internal:
    driver: bridge
```

---

## Paso 5 — Nginx + SSL en el servidor

```bash
# En el servidor, como root:

# Crear config de Nginx para la API
cat > /etc/nginx/sites-available/catalaxia-api.conf << 'EOF'
server {
    server_name api.catalaxia.webshooks.com;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (para logs en tiempo real)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    listen 80;
}
EOF

# Crear config para el frontend
cat > /etc/nginx/sites-available/catalaxia-app.conf << 'EOF'
server {
    server_name catalaxia.webshooks.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 80;
}
EOF

# Activar y verificar
ln -s /etc/nginx/sites-available/catalaxia-api.conf /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/catalaxia-app.conf /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# SSL automático con Certbot (Let's Encrypt)
certbot --nginx \
  -d api.catalaxia.webshooks.com \
  -d catalaxia.webshooks.com \
  --non-interactive \
  --agree-tos \
  --email fmonfasani@gmail.com

# Auto-renovación (Certbot ya la agrega, pero verificar):
systemctl status certbot.timer
```

---

## Paso 6 — Backups automáticos de PostgreSQL

```bash
# En el servidor, como root:
cat > /etc/cron.d/catalaxia-backup << 'EOF'
# Backup diario de la DB a las 3 AM
0 3 * * * deploy docker exec catalaxia-db-1 \
  pg_dump -U catalaxia catalaxia | \
  gzip > /opt/catalaxia/backups/catalaxia_$(date +\%Y\%m\%d).sql.gz

# Limpiar backups de más de 30 días
30 3 * * * find /opt/catalaxia/backups -name "*.sql.gz" -mtime +30 -delete
EOF

mkdir -p /opt/catalaxia/backups
chown deploy:deploy /opt/catalaxia/backups
```

**Opcional — backup a Hetzner Object Storage (S3-compatible):**
```bash
pip install awscli
aws configure  # usar credenciales de Hetzner Storage Box o S3-compatible
# agregar al cron: aws s3 cp /opt/catalaxia/backups/catalaxia_$(date +%Y%m%d).sql.gz s3://catalaxia-backups/
```

---

## Monitoreo básico sin Coolify

### Uptime monitoring gratuito

Usar **Better Uptime** (gratis) o **UptimeRobot** (gratis):
- Monitorear `https://api.catalaxia.webshooks.com/health` cada 5 minutos
- Alerta por email si cae
- Sin instalar nada en el servidor

### Ver logs en vivo

```bash
# SSH al servidor y:
docker compose -f /opt/catalaxia/docker-compose.yml logs -f api
docker compose -f /opt/catalaxia/docker-compose.yml logs -f frontend
```

### Health check manual

```bash
curl https://api.catalaxia.webshooks.com/health
# Respuesta esperada: {"status": "ok", "db": "connected"}
```

### Reiniciar un servicio

```bash
docker compose -f /opt/catalaxia/docker-compose.yml restart api
docker compose -f /opt/catalaxia/docker-compose.yml restart frontend
```

---

## Checklist de migración desde Coolify

- [ ] Crear servidor en Hetzner (CX22)
- [ ] Setup inicial (Docker, Nginx, usuario deploy)
- [ ] DNS: apuntar `api.catalaxia.webshooks.com` y `catalaxia.webshooks.com` a la nueva IP
- [ ] Exportar DB de Coolify: `pg_dump` → importar en nuevo server
- [ ] Configurar GitHub Secrets (6 valores)
- [ ] Agregar `.github/workflows/deploy.yml` al repo
- [ ] Configurar Nginx + SSL (Certbot)
- [ ] Primer deploy manual: `git pull && docker compose up -d`
- [ ] Verificar que `/health` responde
- [ ] Configurar cron de backups
- [ ] Setup UptimeRobot para monitoreo
- [ ] Hacer un push a `main` → verificar que GitHub Actions deploya automáticamente
- [ ] Eliminar proyecto de Coolify (después de verificar que todo funciona)

---

## Comparación Coolify vs este setup

| Aspecto | Coolify | Hetzner directo |
|---------|---------|-----------------|
| Control | UI visual | SSH + GitHub Actions |
| Transparencia | Caja negra | Todo en código (`.yml` en el repo) |
| Costo extra | ~€5/mes de overhead | €0 (solo el server) |
| Debug | Logs en UI | `docker logs` — mismo acceso |
| SSL | Automático | Certbot — igual de automático |
| Auto-deploy | Webhook | GitHub Actions — más control |
| Rollback | Manual en UI | `git revert` + push → deploy automático |
| Portabilidad | Depende de Coolify | Docker Compose corre en cualquier VPS |

**Conclusión:** La ventaja real de este setup sobre Coolify es que **todo está en el repo**. El `docker-compose.yml` y el workflow de GitHub Actions son la fuente de verdad — sin dependencias de un panel externo que puede romperse o cambiar.
