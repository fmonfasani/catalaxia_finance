# Deployment: Screener v2 → PostgreSQL

**Objetivo:** Migrar 572 empresas desde SQLite (screener.db) a PostgreSQL con histórico completo y API mejorada.

**Estado:** 📋 Plan de ejecución

---

## Fases

### Fase 1: Preparación Local (30 min)

**En laptop:**

```bash
cd d:\Software Development\Porfolio\catalaxia-cedears-prod

# 1. Script de migración (ya creado)
python scripts/tickets/screener/load_screener_ratios.py \
  --db-host localhost \
  --db-port 5432

# Debe mostrar:
# ✓ Schema creado
# ✓ Leyendo screener.db (572 empresas encontradas)
# ✓ Cargando a PostgreSQL
# ✓ MIGRACIÓN COMPLETADA
#   - screener_ratios: 572 empresas
#   - screener_ratios_hist: 572 registros
```

**Verificar tablas locales:**

```sql
SELECT COUNT(*) FROM screener_ratios;      -- 572
SELECT COUNT(*) FROM screener_ratios_hist; -- 572
SELECT COUNT(DISTINCT ticker) FROM screener_ratios_hist;  -- 572
```

### Fase 2: Deploy API a Servidor (30 min)

**Archivos a copiar:**

```
scripts/tickets/screener/load_screener_ratios.py  → /opt/catalaxia/scripts/
api/main.py                                        → /opt/catalaxia/api/
dashboard_estatico.html                            → /var/www/catalaxia/
dashboard_dinamico.html                            → /var/www/catalaxia/
```

**En servidor (SSH: root@89.167.96.239):**

```bash
cd /opt/catalaxia

# 1. Ejecutar migración
python3 scripts/load_screener_ratios.py
# Esperar: "✅ MIGRACIÓN COMPLETADA"

# 2. Recargar API (Docker)
docker-compose restart catalaxia-api

# 3. Verificar health check
curl -s http://api.catalaxia.webshooks.com/ | jq .
# Debe mostrar endpoints v2/

# 4. Test v2 endpoint
curl -s "http://api.catalaxia.webshooks.com/v2/screener?limit=5" | jq '.data[0]'
# Debe devolver 1 fila con campos: ticker, roe, fcf_ce, deuda_ebitda, etc.
```

### Fase 3: Deploy Dashboards a Nginx (15 min)

```bash
# En servidor
cd /var/www/catalaxia

# Recargar dashboards
systemctl reload nginx

# Test
curl -s http://dashboard.catalaxia.webshooks.com/dashboard_estatico.html | head -20
```

---

## URLs de Acceso

**Dashboards:**
- Estático: `http://dashboard.catalaxia.webshooks.com/dashboard_estatico.html`
- Dinámico: `http://dashboard.catalaxia.webshooks.com/dashboard_dinamico.html`

**API:**
- v2 (Nuevo): `http://api.catalaxia.webshooks.com/v2/screener`
- v1 (Legacy): `http://api.catalaxia.webshooks.com/v1/ratios` (TXAR)

---

## Endpoints Disponibles

### v2/screener (572 empresas, formato "ancho")

```bash
# Todas las empresas
GET /v2/screener?limit=100&skip=0
→ {
    "count": 100,
    "total": 572,
    "data": [
      {
        "ticker": "AAPL",
        "grupo": "sp500",
        "precio_usd": 216.22,
        "per": 37.89,
        "roe": 1.41,
        "fcf_ce": 0.76,
        "deuda_ebitda": 0.52,
        ...
      }
    ]
  }

# Por grupo
GET /v2/screener?grupo=sp500&limit=100
GET /v2/screener?grupo=adr&limit=100
GET /v2/screener?grupo=byma_only&limit=100

# Empresa específica
GET /v2/screener/AAPL
→ {
  "ticker": "AAPL",
  "cuit": "0000320193",
  "grupo": "sp500",
  ...
  "fcf_ce": 0.76,
  "deuda_ebitda": 0.52,
  ...
}

# Histórico (cambios en el tiempo)
GET /v2/screener/hist/AAPL?limit=50
→ {
  "ticker": "AAPL",
  "count": 3,
  "data": [
    { "period_ref": "2026-07-09", "fcf_ce": 0.76, "deuda_ebitda": 0.52, ... },
    { "period_ref": "2026-06-30", "fcf_ce": 0.73, "deuda_ebitda": 0.54, ... },
    ...
  ]
}

# Estadísticas generales
GET /v2/stats
→ {
  "total": 572,
  "sp500_count": 499,
  "adr_count": 17,
  "byma_count": 56,
  "roe_coverage": 503,
  "fcf_ce_coverage": 481,
  ...
}
```

### v2/grupos (grupo específico)

```bash
GET /v2/grupos?grupo=sp500
→ {
  "grupo": "sp500",
  "count": 499,
  "data": [
    { "ticker": "A", "sector": "Health Care", "per": 26.68, ... },
    ...
  ]
}
```

---

## Rollback (si es necesario)

```bash
# Restaurar API anterior
cd /opt/catalaxia
git checkout HEAD~1 api/main.py
docker-compose restart catalaxia-api

# Restaurar PostgreSQL
docker exec catalaxia-db psql -U postgres -d catalaxia \
  -c "TRUNCATE TABLE screener_ratios, screener_ratios_hist CASCADE"
```

---

## Validación Post-Deploy

**Checklist:**

- [ ] `GET /v2/screener` devuelve 572 empresas
- [ ] `GET /v2/screener/AAPL` devuelve datos AAPL
- [ ] `GET /v2/screener/hist/TXAR` devuelve histórico
- [ ] `GET /v2/stats` muestra cobertura correcta
- [ ] Dashboard estático carga y muestra tabla
- [ ] Dashboard dinámico muestra gráficos
- [ ] Filtros funcionan (grupo, búsqueda)
- [ ] Ordenamiento por ratios funciona
- [ ] URLs responden en 200ms (monitorear latencia)

---

## Datos Disponibles

**Columnas en screener_ratios:**

Fundamentales: ROE, ROA, Margen Neto, Deuda/EBITDA, EPS, FCF/CE, Payout, CAGR EPS 5y
Valuación: PER, P/B, P/S, Precio USD, Precio ARS, Market Cap, EV/EBITDA
Metadata: Grupo, Sector, Fuente, Flags, período_ref

**Cobertura (% de empresas con dato):**

| Ratio | Cobertura |
|---|---|
| ROE | 88% |
| ROA | 98% |
| Deuda/EBITDA | 61% |
| FCF/CE | 84% |
| PER | 86% |
| CAGR | 67% |

---

## Next Steps

1. **Histórico capturado:** Extender screener_ratios_hist con cambios mensuales (jobs de actualización)
2. **Alertas:** Notificar cambios significativos en ratios
3. **Comparaciones:** Agregar endpoint de benchmarking (vs grupo, vs sector)
4. **Export:** Agregar descarga CSV/JSON filtrada
