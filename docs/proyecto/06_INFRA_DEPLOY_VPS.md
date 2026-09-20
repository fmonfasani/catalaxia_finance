# Guía de infraestructura y deploy — Docker en la VPS Hetzner

> La VPS **ya existe** (la misma de **wapsell**, Hetzner). Todo el stack de Catalaxia va
> **dockerizado** en un proyecto nuevo, **conviviendo** con wapsell (puertos y subdominio propios).
> Dueño único: **Federico**. Archivos listos en [`infra/`](infra/).

---

## 1. Convivencia con wapsell (importante)

En esa VPS ya corre wapsell con **nginx en el host** terminando TLS (:443) y contenedores en
`:3010` (app) y `:8000` (api). Para no chocar:

| Recurso | wapsell (existe) | Catalaxia (nuevo) |
|---|---|---|
| Carpeta | `/opt/wapsell` | **`/opt/catalaxia`** |
| API (host) | `127.0.0.1:8000` | **`127.0.0.1:8100`** |
| Postgres (host) | — | **`127.0.0.1:5433`** (solo local) |
| Front (host) | `127.0.0.1:3010` | **`127.0.0.1:3011`** (si va en la VPS) |
| Subdominio | `api.wapsell.com` | **`api.catalaxia.<dominio>`** |
| Reverse proxy | **nginx del host** (compartido) | usa el mismo nginx del host |

> **Decisión de diseño (honesta):** un solo proceso puede dueñar el :443. Como wapsell ya usa el
> **nginx del host** como edge, Catalaxia **dockeriza app + DB** y publica su API agregando un
> *vhost* a ese nginx del host. Es lo más simple y sin riesgo. Si más adelante se quiere un edge
> proxy 100% dockerizado y único para toda la VPS, se migra a **Traefik** (tarea aparte).

## 2. Qué va en Docker

- **`db`** — PostgreSQL 16 (contenedor, volumen persistente `pgdata`).
- **`api`** — FastAPI + Uvicorn; el **ORM (SQLAlchemy) vive dentro de esta imagen** (no es un
  contenedor aparte).
- **`web`** *(opcional)* — Next.js, si el frontend se sirve desde la VPS (si no, va a Vercel).
- **Reverse proxy** — el **nginx del host** (compartido con wapsell) vía `nginx-catalaxia.conf`.

Archivos: `infra/docker-compose.yml` · `infra/backend.Dockerfile` · `infra/.env.example` ·
`infra/nginx-catalaxia.conf`.

## 3. Puesta en marcha (Semana 1, Federico)

```bash
# 1) Proyecto nuevo en la VPS
ssh root@<vps-hetzner>
mkdir -p /opt/catalaxia && cd /opt/catalaxia
git clone <repo> .                      # repo con backend/ (+ frontend/ opcional)
cp infra/docker-compose.yml .           # a la raíz
cp infra/backend.Dockerfile backend/Dockerfile
cp infra/.env.example .env && nano .env # completar POSTGRES_PASSWORD, dominio, CORS

# 2) Levantar el stack (db + api) dockerizado
docker compose up -d --build
docker compose ps                       # db healthy, api up
docker compose logs -f api

# 3) Crear esquema + cargar datos (dentro del contenedor db/api)
docker compose exec -T db psql -U catalaxia -d catalaxia < backend/schema.sql
docker compose exec api python scripts/cargar_datos.py   # 572 empresas + 733 instrumentos
docker compose exec -T db psql -U catalaxia -d catalaxia -c "select count(*) from empresas;"  # 572

# 4) Publicar la API por el nginx del host + TLS
cp infra/nginx-catalaxia.conf /etc/nginx/sites-available/api.catalaxia.conf
ln -s /etc/nginx/sites-available/api.catalaxia.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d api.catalaxia.<dominio>     # HTTPS

# 5) Verificar
curl https://api.catalaxia.<dominio>/v1/cobertura   # {empresas:572, instrumentos:733, ...}
```

## 4. CORS (habilita a los front a consumir la VPS)
En `.env`: `CORS_ORIGINS=http://localhost:3000,https://catalaxia.<dominio>`.
En FastAPI, `CORSMiddleware` lee esa lista. **Apenas la API responde por HTTPS, avisar la URL al
equipo** — ese es el desbloqueo de Joaquín y Aldana (pasan de mocks a la VPS real).

## 5. Backups (Postgres en Docker)
```bash
# cron diario en el host (3 AM) — pg_dump vía docker exec
0 3 * * * cd /opt/catalaxia && docker compose exec -T db pg_dump -U catalaxia catalaxia | gzip > /opt/backups/catalaxia_$(date +\%F).sql.gz
# retención 14 días
30 3 * * * find /opt/backups -name 'catalaxia_*.sql.gz' -mtime +14 -delete
```
Restore de prueba (verificar que sirve): `gunzip -c backup.sql.gz | docker compose exec -T db psql -U catalaxia -d catalaxia`.

## 6. Jobs (scheduler) en Docker
- APScheduler corre **dentro del contenedor `api`** (o un servicio `worker` aparte si conviene
  aislarlo). Escribe cada corrida en la tabla `jobs`.
- Cadencia: **precios** diario · **financials** trimestral · **rebuild** on-demand (`POST /jobs/rebuild`).

## 7. Checklist de infra (DoD)
- [ ] `docker compose ps`: `db` healthy + `api` up, con `restart: always`.
- [ ] `https://api.catalaxia.<dominio>/v1/cobertura` responde 572 / 733 / 144.
- [ ] `nginx -t` ok y NO rompió los vhosts de wapsell.
- [ ] Backup diario corriendo + un restore de prueba hecho.
- [ ] CORS ok y **URL avisada al equipo**.
- [ ] Puertos no chocan con wapsell (8100 / 5433 / 3011).

## 8. Comandos útiles
```bash
docker compose up -d --build     # rebuild + levantar
docker compose logs -f api       # logs
docker compose restart api       # reiniciar solo la api
docker compose down              # bajar (los datos persisten en el volumen pgdata)
docker compose exec db psql -U catalaxia catalaxia   # consola SQL
```
