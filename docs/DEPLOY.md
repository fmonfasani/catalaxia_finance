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

## Pre-requisitos en VPS (89.167.96.239)

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
cd /opt/catalaxia
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

**Preguntas?** Revisar logs con `docker-compose logs -f`
