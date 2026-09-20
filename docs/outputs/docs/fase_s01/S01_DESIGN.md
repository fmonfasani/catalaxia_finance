# S01_DESIGN.md — Entity Identity (fase S01)

2026-08-23 · Estado: **CHECKPOINTED con gate PASS (4/4)** · run_id=63d4b9f8a6ad43788738a539b35d0aa5 · git=f51043c2

## 1. Objetivo cumplido

Identidad canónica y determinística por entidad económica. El caso YPF del enunciado queda resuelto y verificado:

| Identificador | Mercado | Estado |
|---|---|---|
| `CIK 0000904851` | SEC (fuente de registro) | ACTIVE · identidad canónica `CIK:0000904851` |
| `TICKER YPF` | US/NYSE | ACTIVE |
| `TICKER YPFD` | BYMA | ACTIVE (vía resolución manual declarada) |
| `YF_SYMBOL YPF` | yahoo | ACTIVE (regla derivada listing-US) |
| `YF_SYMBOL YPFD.BA` | yahoo | ACTIVE (regla derivada sufijo .BA) |
| CUIT / CNV_ID | AR | NULL — se llenarán en fase CNV; jamás fabricar |

`legal_name = "YPF SOCIEDAD ANONIMA"` verbatim de la fuente de registro.

## 2. Política de fuente de registro (decisión clave de diseño)

1. La identidad nace SOLO de `company_tickers.json` (SEC) descargado a RAW inmutable con manifest SHA256 (`data/raw/catalogo_edgar/`, hash `0f91b088…bd`).
2. Catálogos legacy (`scripts/screener/datos/*.csv`) JAMÁS definen identidad: solo aportan alias BYMA candidatos y sirven de contraste.
3. Toda discrepancia contra la fuente de registro → fila en `identity.identifier_reviews` (OPEN) + identificador DISPUTADO/excluido. Resolución solo por vía manual declarativa (`data/catalogo/engine_identity_resolutions.csv`, versionado, con autor y motivo).
4. `entity_id` determinista: `CIK:{cik10}` hoy; `CUIT:{cuit}` / `CNV:{id}` cuando existan fuentes. Sin UUIDs aleatorios (reproducibilidad clase A).
5. EXT-NEW-002 estructural: tickers NO existen en `identity.entities`; viven solo en `identifiers`/`classifications`.

## 3. Modelo implementado (migración `002_s01_identity.sql`)

| Tabla | PK / claves | Rol |
|---|---|---|
| identity.entities | entity_id; UNIQUE(cik), UNIQUE(cuit), UNIQUE(cnv_id) | identidad pura |
| identity.identifiers | UNIQUE(id_type,id_value,marketplace); FK→entities; status ACTIVE/RETIRED/DISPUTED | todos los alias externos |
| identity.classifications | UNIQUE(entity,class_type,value) | clasificación separada de identidad |
| identity.identifier_reviews | review_id; status OPEN/RESOLVED/REJECTED; resolved_entity_id + nota | gobernanza EXT-NEW-012 |

## 4. Pipeline de siembra (idempotente, clase A sobre RAW)

1. Bulk-seed desde catálogo SEC: **7.998 entidades, 18.401 identificadores, 10.403 símbolos yahoo derivados** (reglas declaradas `derived_rule:v1`: US→símbolo directo; BYMA→sufijo `.BA`).
2. Cruce CEDEARs legacy → links BYMA (10 calzados; el CSV es un sample de 10 filas, no universo).
3. Contraste catálogo legacy vs fuente de registro → **4 conflictos OPEN** (ver §6).
4. Resoluciones manuales declarativas → YPFD/BYMA + YPFD.BA/yahoo activos con provenance `[by federico]`.
5. Segunda corrida = 0 inserciones nuevas (dedup verificada).

## 5. Checks (PIPELINE_VALIDATION_SPECIFICATION §2, fila S01)

| Check | Resultado | Evidencia |
|---|---|---|
| C-S01-001 unicidad canónica | PASS | 0 grupos (tipo,valor,mercado) con >1 entidad ACTIVE |
| C-S01-002 discrepancias fuera de identidad usable | PASS | 4 reviews OPEN; nada DISPUTADO quedó usable |
| C-S01-003 identidad≠clasificación | PASS | entities sin columnas ticker (information_schema) |
| C-S01-004 golden YPF | PASS | entidad única + 5 identificadores requeridos + conflicto 1104659 registrado |

## 6. Hallazgos (insumo para fases futuras)

1. **R-16 NUEVO**: catálogo legacy `acciones_argentinas_usa.csv` tiene CIKs podridos en 4 casos confirmados:

   | Ticker | CIK legacy (podrido) | Entidad real (fuente de registro) |
   |---|---|---|
   | YPF | 1104659 (no existe en SEC) | CIK:0000904851 YPF SOCIEDAD ANONIMA |
   | GGAL | 1069595 | CIK:0001114700 |
   | BMA | 1113245 | CIK:0001347426 |
   | CRESY | 1082722 | CIK:0001034957 |

   Implicancia: cualquier output del screener legacy que haya usado ese catálogo puede estar construido sobre identidades equivocadas → antes de reutilizar comparaciones legacy, verificar contra engine. Cola exportada: `IDENTITY_REVIEWS_2026-08-23.csv`.
2. Ningún catálogo del repo contiene el ticker BYMA real de YPF (`YPFD`) → resuelto por instrucción humana declarada; queda pendiente contraste documental cuando entre una fuente BYMA (nota ya registrada en la resolución).
3. Incidente operativo corregido: corrida inicial colgada por conexión psycopg2 sin timeout → `connect_args={connect_timeout:5, statement_timeout:120s}` en `engine/db.py`; siembra convertida a bulk (13k entradas en segundos); PYTHONUNBUFFERED para logs en vivo.

## 7. Handoff a S02 FETCH

- Consumir `identity.entities WHERE cik IS NOT NULL` como universo descargable (empieza por YPF FAST mode).
- `download_log` append-only por (cik, form, filed_at) con sha256 + http_status (cierra gaps 6–8 de PROVENANCE_SPEC).
- Portar invalidación por fecha explícita desde `_caducidad.py`; jamás "si tengo fecha salto" (EXT-019).
- Rate limit: secuencial, UA "Federico Monfasani fmonfasani@gmail.com", sleep ~0.3s.
