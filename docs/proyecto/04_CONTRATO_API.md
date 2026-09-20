# Contrato de API (backend ↔ frontend)

> **El documento más importante para no bloquearse.** Se acuerda el **día 1**. Con esto los
> frontends arrancan con **datos mock** y no esperan al backend. Dueño: Federico + Mateo.
> Versión del contrato: **v1** (cambios se versionan acá y se avisan).

---

## 1. Reglas del contrato

- Base URL (staging): `https://api.catalaxia.<dominio>/v1` (Federico avisa la real).
- Respuestas **JSON**, `Content-Type: application/json`, códigos HTTP estándar.
- Errores: `{ "error": { "code": "...", "message": "..." } }` con 4xx/5xx.
- Paginación: `?page=1&page_size=50` → `{ "items": [...], "total": N, "page": 1, "page_size": 50 }`.
- **Los front programan contra estos shapes.** Hay un `mocks/` con estos JSON de ejemplo (Federico
  lo entrega el día 1) para desarrollar sin backend.

## 2. Endpoints

### `GET /empresas` — screener
Query params: `grupo` (sp500|adr|byma), `sector`, `per_lt`, `per_gt`, `roe_gt`, `solo_limpias=true`,
`sort` (ej. `per`, `-roe`), `page`, `page_size`, `q` (ticker/nombre).

```json
// 200 OK
{
  "items": [
    {
      "id": "0000320193",
      "ticker": "AAPL",
      "nombre": "Apple Inc.",
      "grupo": "sp500",
      "sector": "Technology",
      "precio_usd": 231.4,
      "precio_ars": null,
      "per": 37.9,
      "pb": 51.2,
      "roe": 1.47,
      "margen_neto": 0.25,
      "ev_ebitda": 27.1,
      "deuda_ebitda": 1.1,
      "flag_no_significativo": false,
      "dato_desactualizado": false
    }
  ],
  "total": 572, "page": 1, "page_size": 50
}
```

### `GET /empresas/{id}` — detalle (fundamentales + instrumentos anidados)
```json
// 200 OK
{
  "id": "YPF", "ticker": "YPF", "nombre": "YPF S.A.", "grupo": "adr",
  "sector": "Energy", "pais": "AR",
  "fundamentales": { "per": 6.8, "roe": 0.18, "margen_operativo": 0.21, "ev_ebitda": 3.2, "...": "..." },
  "precio": { "usd": 47.9, "ars": 75775, "ccl": 1578, "fuente": "yfinance/IAMC" },
  "instrumentos": [
    { "tipo": "adr",   "ticker": "YPF",  "mercado": "NYSE", "moneda": "USD",
      "isin": "US9842451000", "ratio": 1, "ratio_tipo": "adr",
      "precio": 47.9, "fuente": "SEC F-6", "source_url": "https://sec.gov/..." },
    { "tipo": "ordinaria_ar", "ticker": "YPFD", "mercado": "BYMA", "moneda": "ARS",
      "isin": "ARYPF...", "precio": 75775, "fuente": "IAMC", "source_url": "https://iamc.com.ar/..." }
  ],
  "dividendos_adr": [ { "fecha": "2026-03-15", "monto_adr": 0.9, "moneda": "USD" } ],
  "flag_no_significativo": false
}
```

### `GET /instrumentos` — lista de instrumentos
Query: `tipo` (cedear|adr|ordinaria_us|ordinaria_ar), `mercado`, `empresa_id`, `page`, `page_size`.
```json
{ "items": [
    { "empresa_id": "0000320193", "tipo": "cedear", "ticker": "AAPL",
      "mercado": "BYMA", "moneda": "ARS", "ratio": 20, "ratio_tipo": "cedear",
      "precio": 12500, "fuente": "Comafi", "source_url": "https://comafi.com.ar/..." }
  ], "total": 733, "page": 1, "page_size": 50 }
```

### `GET /cobertura` — salud del dataset (para chips de confianza)
```json
{
  "generated_at": "2026-07-11T12:00:00Z",
  "empresas": 572, "instrumentos": 733,
  "por_grupo": { "sp500": 499, "adr": 17, "byma": 56 },
  "cedears_con_ratio": 144,
  "cobertura_ratios": { "per": 0.93, "roe": 0.9, "ev_ebitda": 0.8 }
}
```

### `POST /jobs/{tipo}` + `GET /jobs/{id}/status`
`tipo` ∈ `precios | financials | rebuild`.
```json
// POST -> 202 Accepted
{ "id": 128, "tipo": "precios", "estado": "running", "started_at": "2026-07-11T12:00:00Z" }
// GET /jobs/128/status -> 200
{ "id": 128, "tipo": "precios", "estado": "done", "finished_at": "...", "detalle": { "actualizadas": 572 } }
```

## 3. Enum / valores fijos (para que el front tipee)
- `grupo`: `sp500 | adr | byma`
- `instrumento.tipo`: `ordinaria_us | adr | cedear | ordinaria_ar`
- `moneda`: `USD | ARS`
- `job.tipo`: `precios | financials | rebuild` · `job.estado`: `pending | running | done | error`

## 4. Versionado del contrato
- Cambios **retrocompatibles** (agregar campo): se documentan acá, no rompen a nadie.
- Cambios **rompientes** (renombrar/quitar): se avisan en el canal, se sube a `v2` y se acuerda fecha.
- Federico mantiene los `mocks/*.json` alineados con esta versión.
