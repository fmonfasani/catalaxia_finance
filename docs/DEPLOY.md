# 🚀 Despliegue a Producción - Catalaxia Finance

## Estructura

```
docker-compose.yml      ← Orquestación de servicios
├── PostgreSQL (db)      → Base de datos
├── FastAPI (api)        → API en puerto 8100
└── Nginx (nginx)        → Reverse proxy + static files

Dockerfile.api          ← Build para el API
Dockerfile              ← Build para el pipeline

public/                 ← Archivos HTML estáticos
├── dashboard_final_v2.html
└── screener_final.html

nginx/nginx.conf        ← Configuración de Nginx
```

## Pre-requisitos en VPS (la IP real va en `CATALAXIA_HOST` del entorno, nunca en código/docs)

- Docker + Docker Compose instalados
- Puerto 8100 disponible (interno)
- Dominio `api.catalaxia.webshooks.com` apuntando a la VPS
- Nginx principal en la VPS configurado para proxy

## Despliegue Local (Desarrollo)

### 1. Crear archivo `.env`

```bash
cat > .env << EOF
POSTGRES_PASSWORD=tu_password_seguro_aqui
EOF
```

### 2. Ejecutar deploy script

```bash
chmod +x deploy.sh
./deploy.sh
```

### 3. Verificar servicios

```bash
docker-compose ps
docker-compose logs -f api
```

### 4. Acceder

- Dashboard: http://localhost:8080/
- Screener: http://localhost:8080/screener
- API Health: http://localhost:8080/health

---

## Despliegue en Producción (VPS)

### 1. En la VPS, clonar repo

```bash
cd /infra/projects/0009-catalaxia
git pull origin main
```

### 2. Crear `.env` con password de producción

```bash
cat > .env << EOF
POSTGRES_PASSWORD=$(openssl rand -base64 32)
EOF
chmod 600 .env
```

### 3. Ejecutar deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Configurar Nginx reverso (en VPS, fuera de Docker)

La VPS tiene nginx en `127.0.0.1:80`. Este archivo ya existe en:
`/etc/nginx/sites-available/api.catalaxia.conf`

Si no existe, crear:

```nginx
server {
    server_name api.catalaxia.webshooks.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    listen 80;
}
```

Luego:
```bash
sudo ln -s /etc/nginx/sites-available/api.catalaxia.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d api.catalaxia.webshooks.com
```

### 5. Verificar despliegue

```bash
curl https://api.catalaxia.webshooks.com/health

# Si responde "ok", está funcionando ✅
```

### 6. Variables de seguridad (F10)

El API es **fail-closed**: sin `API_KEY` configurada responde 503 en todos los
endpoints. Agregar al `.env` de producción:

```bash
# Clave de acceso al API (header `X-API-Key`, obligatoria en TODOS los endpoints).
# Generar con: openssl rand -base64 32
API_KEY=<clave_secreta>

# Orígenes cross-origin permitidos (coma separada). Vacío = solo mismo-origen.
# "%" NO se usa: si se requiere cualquier origen, literal "*" (sin credenciales).
API_CORS_ORIGINS=https://api.catalaxia.webshooks.com
```

Verificar autenticación:

```bash
curl -i https://api.catalaxia.webshooks.com/v2/screener          # 401/503 (sin clave)
curl -H "X-API-Key: $API_KEY" https://api.catalaxia.webshooks.com/v2/screener
```

Los jobs de extracción y run_update verifican certificados TLS por defecto
(`REQUESTS_VERIFY=1`). No configurar `REQUESTS_VERIFY=0` salvo breaking de
certificado de una fuente, y solo transitoriamente (riesgo MITM / integridad
de RAW).

---

## URLs en Producción

| Recurso | URL |
|---------|-----|
| Dashboard | https://api.catalaxia.webshooks.com/ |
| Screener | https://api.catalaxia.webshooks.com/screener |
| API v2 | https://api.catalaxia.webshooks.com/v2/... |
| Health Check | https://api.catalaxia.webshooks.com/health |

---

## Logs

### Ver logs en tiempo real

```bash
docker-compose logs -f
```

### Ver logs de un servicio específico

```bash
docker-compose logs -f api
docker-compose logs -f nginx
docker-compose logs -f db
```

### Persistencia de logs

```bash
# En la VPS
tail -f /var/lib/docker/containers/*/logs/*
```

---

## Troubleshooting

### API no responde (503)

```bash
docker-compose logs api
# Verificar que PostgreSQL esté healthy:
docker-compose logs db
```

### Nginx error (502 Bad Gateway)

```bash
docker-compose logs nginx
# Verificar que api:8100 esté accesible:
docker exec catalaxia-nginx curl http://api:8100/health
```

### CORS errors en frontend

- Verificar que `nginx.conf` tiene `proxy_set_header` correctos
- Revisar que API devuelve headers de CORS:
  ```bash
  curl -I https://api.catalaxia.webshooks.com/v2/screener
  ```

### Database connection errors

```bash
docker-compose exec db psql -U catalaxia -d catalaxia -c "SELECT 1;"
```

---

## Actualizar código

Después de `git pull`:

```bash
./deploy.sh
```

Esto rebuildeará las imágenes y reiniciará los servicios.

---

## Backup de datos

```bash
# Backup de PostgreSQL
docker-compose exec db pg_dump -U catalaxia catalaxia > catalaxia_backup.sql

# Restore
docker-compose exec -T db psql -U catalaxia catalaxia < catalaxia_backup.sql
```

---

## Pipeline ENGINE certificado (S00→C12) — run por corrida

El runtime productivo del engine (ver `docs/review/26_F12_ARCHITECTURE_DECISION.md`,
"Execution chain") se lanza en su propio contenedor, imagen `Dockerfile.engine`,
y **no** se prende con `docker compose up` (profile `run-e2e`). Un solo comando
aplica migraciones pendientes (vía administrativa, F-025), encadena
S00→S04 → ratio_engine → C10 → C11 → C12 con abort-on-fail, y deja un report
JSON en `outputs/e2e/`:

```bash
# Modo FAST (default) — cadena completa hasta C11, C12 queda en SKIPPED si
# no se declara el destino de integración (ENGINE_PUBLISH_SOURCE).
docker compose --profile run-e2e run --rm engine

# Modo completo
docker compose --profile run-e2e run --rm engine --mode FULL

# Con C12 (publicación a staging): definir el origen antes de correr
ENGINE_PUBLISH_SOURCE=derived.fact docker compose --profile run-e2e run --rm engine
```

Guardas y exit codes (entrypoint `scripts/engine/run_e2e_certified.py`):

- `0` cadena PASS/CERTIFICADA (o C12_SKIPPED declarado).
- `1` cadena abortada (BLOCK / NEGADA / publish fallido / migraciones).
- `2` EXT-010 (destino 5432 sin `ENGINE_ALLOW_PROD=1` explícito) o error de uso.
- `3` lock ocupado: otra corrida de la cadena sigue activa (advisory lock de PG,
  vale entre contenedores/hosts que compartan la base).

La cadena se agenda en el VPS con cron (no es un servicio long-running):

```bash
# /etc/cron.d/catalaxia-engine (requiere .env en /infra/projects/0009-catalaxia)
30 6 * * 1-5 deploy   cd /infra/projects/0009-catalaxia && docker compose --profile run-e2e run --rm engine >> data/logs/engine_e2e.log 2>&1
```

Los datos de trabajo (`data/raw/engine`, `data/screener.db` de solo lectura) y
los outputs se montan como volúmenes (`./data`, `./outputs`). El rol de
aplicación sigue siendo `catalaxia_engine` (F-025); la migración `035` habilita
su LOGIN y el entrypoint asigna la password por bootstrap administrativo con la
misma variable `ENGINE_ADMIN_DB_PASSWORD` que usa para migrar.

**Preguntas?** Revisar logs con `docker-compose logs -f`
