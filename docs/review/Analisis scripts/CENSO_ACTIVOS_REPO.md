# CENSO DE ACTIVOS DEL REPOSITORIO — Catalaxia

Fecha: 2026-09-06 · Alcance: inventario completo de código, config y migraciones del repo
`catalaxia-cedears-prod` (Git). Evidencia cruda en `docs/review/censo_assets/`.

---

## 1. Resumen ejecutivo

- **672 activos clasificados**: 616 scripts `.py` + 56 componentes no-Python (44 SQL, 3 Shell, 1 PS1, 2 Dockerfiles, 2 YAML, 1 nginx, 1 toml, 1 .env.example, 1 CODEOWNERS).
- **Fuera de este censo** (no son código/config): 169 `.md` de documentación, y artefactos de propuesta (`.docx`/`.xlsx`/`.pdf`/`.pptx`), más `data/` (raw CSVs/JSON duplicables).
- La mayor parte del código vive en **3 zonas funcionales**: `scripts/` (tickets CNV y screener, pipeline, engine), `backend/` (API/calculators) y `_research/`.
- **36 activos de riesgo ALTO** (5,8 %), 23 de ellos ya en `docs/screener/failed_investing_scraping/` (demos dead-end del scraping investing.com). **23 acciones DROP / 14 DELETE / 85 OVERWRITE** mapeadas por capa.
- **Halafazgos críticos para atender**: `deploy.py` con credenciales root hardcodeadas, `migrate_sqlite_to_pg.py` marcado REVIEW, duplicación de dos pipelines funcionales (`engine/s0..s4` vs `pipeline/f1..f8`), y 45 filas con `accion` no normalizable (NA) que requieren revisión humana.

## 2. Metodología

1. Inventario con `git ls-files`, excluyendo `data/` y venv.
2. Partición de los `.py` en 18 batches (~616 archivos) por directorio/propósito.
3. Clasificación por 18 agentes LLM con esquema canónico de 25 columnas:
   `id, rel_path, lang, grupo_actual, tipo, proposito, capas_primaria, capas_secundarias, cruza_capas, compatibilidad, lee, escribe, modifica, acceso_destructivo, provenance, idempotencia, determinismo, reproducibilidad, duplicacion, duplicado_de, dependencias, accion, complejidad, riesgo, evidencia`.
4. Los batches `engine` (37) y `scr_screener_b` (43) se re-clasificaron 2 veces hasta alcanzar esquema y vocabulario canónicos (validación automática por fila).
5. Fusión en `catalaxia_censo_py_master.csv` (616 filas, sin duplicados de `rel_path`) + `catalaxia_censo_no_py.csv` (56 filas, clasificadas manualmente).
6. Agregación con **normalización de vocabulario**: la taxonomía de capas y tipos derivó entre agentes (p. ej. `03_RAW`, `10_VALIDACION`, `AUDITORIA`, `P0`). Se mapeó a la capa canónica `01_FUENTES..19_DOCS` y a tipologías estándar. Los valores no mapeables quedan como `NA`.

**Taxonomía canónica de capas usada para agregar**

| Código | Capa | Código | Capa |
|---|---|---|---|
| 01_FUENTES | Fuentes (SEC/CNV/yfinance/raw) | 11_PLATAFORMA_WEB | Web/API |
| 02_IDENTIDAD | Identidad de empresas/instrumentos | 12_PUBLICACION | Publicación/API v2 |
| 03_PRECIOS_MERCADO | Precios y mercado | 13_ORQUESTACION | Orquestación/jobs |
| 04_DATOS_EMPRESA | Datos financieros de empresa | 14_STATS | Validación/auditoría/stats |
| 05_CNV | Capa CNV | 15_ECC | ECC/certificación/provenance |
| 06_DATOS_DEMO | Datos demo | 16_ETL_MISC | ETL misceláneo/medallion |
| 07_SCRAPING | Scraping | 17_TESTS | Tests |
| 08_RATIOS | Ratios | 18_INFRA | Infra/deploy |
| 09_ESTRATEGIAS | Estrategias | 19_DOCS | Docs/código demostrativo |
| 10_MERCADO_CTA | Mercado BYMA/CTA | 00_OTROS | No determinable |

## 3. Distribución por capa primaria (616 `.py`)

| Capa | n | % | Capa | n | % |
|---|---|---:|---:|---|---:|---:|
| 01_FUENTES | 93 | 15,1 | 03_PRECIOS_MERCADO | 20 | 3,2 |
| 16_ETL_MISC | 81 | 13,1 | 07_SCRAPING | 17 | 2,8 |
| 14_STATS | 77 | 12,5 | 13_ORQUESTACION | 10 | 1,6 |
| 05_CNV | 72 | 11,7 | 15_ECC | 8 | 1,3 |
| 08_RATIOS | 68 | 11,0 | 17_TESTS | 6 | 1,0 |
| 02_IDENTIDAD | 66 | 10,7 | 06_DATOS_DEMO | 6 | 1,0 |
| 19_DOCS | 31 | 5,0 | 18_INFRA | 6 | 1,0 |
| 04_DATOS_EMPRESA | 26 | 4,2 | 00_OTROS | 5 | 0,8 |
| 12_PUBLICACION | 22 | 3,6 | 10_MERCADO_CTA / 11_PLATAFORMA_WEB | 1+1 | 0,3 |

## 4. Distribución por tipo

| Tipo | n | Tipo | n |
|---|---:|---:|---:|
| analisis_informes | 196 | monitor | 7 |
| oneshot | 100 | test_int_open | 4 |
| etl_intermedio | 67 | kernel/model | 3 |
| etl_raw | 62 | test_synthetic | 2 |
| etl | 31 | script_deploy | 2 |
| banco_ataques | 20 | shell_tool | 2 |
| test_file | 19 | infra | 2 |
| publicador | 12 | test_INIT / fuente_datos_cruda / fixture | 1+1+1 |
| scheduler | 11 + 2 ADAPT | script_carga | 10 |
| sql_migration | 9 | oneshot_reparacion | 7 |

## 5. Acción recomendada

| Acción | n | Comentario |
|---|---:|---|
| KEEP | 277 | Conservar |
| DELETE | 132 | Borrar candidatos (65 en `scripts/*` — probes/tmp; 32 ticks a `screener`, 20 a `cnv`) |
| MERGE_REPLACE | 45 | Fusionar/reemplazar duplicados |
| ARCHIVE | 41 | Archivar (16 batch CNV, 9 scraping dead-end, 10 ETL misc) |
| ADAPT | 30 | Adaptar a pipeline nuevo |
| DEPRECATE | 21 | Deprecar (parcial/reemplazado) |
| REVIEW | 16 | Requiere revisión humana (ver §10) |
| REWRITE | 8 | Reescribir (p. ej. `f6_sec`, parte `12_PUBLICACION`) |
| PENDING | 1 | Pendiente |
| NA | 45 | Acción no normalizable → revisar |

Suma: 616. De las 45 `NA`, la mayoría son archivos con clasificador distante (probes de experimentos) donde no se pudo decidir.

## 6. Compatibilidad

| Nivel | n | % |
|---|---:|---:|
| FULL | 365 | 59,3 |
| PARCIAL | 193 | 31,3 |
| NO | 35 | 5,7 |
| NA | 23 | 3,7 |

## 7. Complejidad y riesgo

| Complejidad | n | | Riesgo | n |
|---|---:|---:|---|---:|
| BAJA | 271 | | BAJO | 425 |
| MEDIA | 242 | | MEDIO | 114 |
| ALTA | 80 | | **ALTO** | **36** |
| NA | 23 | | NA | 41 |

Riesgo ALTO por capa: 07_SCRAPING=7, 12_PUBLICACION=5, 08_RATIOS=4, 05_CNV=4, 02_IDENTIDAD=4, 18_INFRA=3, 13_ORQUESTACION=3, 16_ETL_MISC=3, 14_STATS=2, 01_FUENTES=1.

## 8. Acceso destructivo por capa (solo capas con incidencia)

| Capa | DROP | TRUNCATE | DELETE | OVERWRITE |
|---|---:|---:|---:|---:|
| 08_RATIOS | 5 | – | 2 | 11 |
| 04_DATOS_EMPRESA | 5 | – | 4 | 10 |
| 13_ORQUESTACION | 3 | – | – | 3 |
| 05_CNV | 2 | – | – | 10 |
| 03_PRECIOS_MERCADO | 2 | – | 2 | 6 |
| 16_ETL_MISC | 2 | – | – | 4 |
| 19_DOCS | – | – | – | 18 |
| 12_PUBLICACION | 1 | 1 | – | 2 |
| 01_FUENTES | – | – | 3 | 3 |
| 02_IDENTIDAD | – | – | 1 | 3 |
| 07_SCRAPING | – | – | – | 6 |
| 06_DATOS_DEMO | 1 | – | 1 | 4 |
| 17_TESTS / 18_INFRA / 11_PLATAFORMA_WEB | 1+1+0 | – | 0+1+0 | 1+1+1 |

Total destructivo: **DROP 23 · TRUNCATE 1 · DELETE 14 · OVERWRITE 85** — 123 de 616 (20 %).

## 9. Capas cruzadas (primaria <-> secundaria), top

| Par | n | Par | n |
|---|---:|---:|---:|
| 01_FUENTES <-> 16_ETL_MISC | 32 | 08_RATIOS <-> 05_CNV | 17 |
| 16_ETL_MISC <-> 01_FUENTES | 31 | 16_ETL_MISC <-> 12_PUBLICACION | 16 |
| 01_FUENTES <-> 01_FUENTES | 23 | 14_STATS <-> 02_IDENTIDAD | 16 |
| 02_IDENTIDAD <-> 01_FUENTES | 22 | 02_IDENTIDAD <-> 15_ECC | 14 |
| 14_STATS <-> 01_FUENTES | 19 | 08_RATIOS <-> 14_STATS | 14 |
| 14_STATS <-> 08_RATIOS | 18 | 05_CNV <-> 02_IDENTIDAD | 14 |

Secundarias agregadas más frecuentes: 01_FUENTES=138, 08_RATIOS=69, 05_CNV=67, 16_ETL_MISC=60, 14_STATS=56, 12_PUBLICACION=53, 02_IDENTIDAD=53, 15_ECC=48.
El grafo confirma flujos esperados: **fuentes → identidad → normalización → ratios → publicación**, con auditoría/stats como capa transversal.

## 10. Hallazgos a atender

**Críticos (riesgo ALTO + acción ≠ KEEP)**
1. `deploy.py` — credenciales root hardcodeadas (REVIEW, ALTO). Quitar credenciales antes de cualquier uso.
2. `scripts/tickets/screener/migrate_sqlite_to_pg.py` — migración SQLite→PG sin certificación previa; documenta pérdida de 12 columnas del screener (REVIEW, ALTO).
3. `scripts/tickets/screener/run_screener.py` (y `run_update.py`/`run_all.py`) — reconstruyen tablas con DROP+CREATE fases s0..s8+s5 sobre `screener.db` de producción (REVIEW, ALTO).
4. `scripts/tickets/screener/aplicar_pk_cnv_v2.py` — reconstruye `cnv_estados_v2` con swap por renombrado y respaldo `pre_pk`; PK recreada (KEEP, ALTO).
5. `scripts/deploy/sincronizar_a_produccion.py` — DELETE+INSERT real sobre PostgreSQL prod, 7 tablas (KEEP, ALTO).
6. `scripts/engine/adversario_ratios.py` — banca adversarial con `DROP` y mutaciones en copia descartable `adversario_ratios_mut`; único con acceso DROP + ALTO en engine (KEEP, ALTO).
7. `scripts/engine/cnv_negative_pilot.py` — responsable del incidente `CNV_NEGATIVE_PILOT_20`; ahora con fingerprint antes/después y forense propio (REVIEW).

**Duplicaciones / dos pipelines del mismo dominio**
- `engine/s00..s04` (identity/fetch/parse/normalize) vs `pipeline/f1..f8`: conviven dos flujos para identidad+EEFF. `engine/identity.py` y `pipeline/f1_identidad.py` marcados **MERGE_REPLACE**; `pipeline/f6_sec.py` **REWRITE**.
- `_research/schema/001_initial_schema.sql` = copia exacta de `migrations/001_initial_schema.sql` (MERGE_REPLACE).
- `scripts/tickets/cnv/carga_estados_investing_10empresas.py` está **incompleta (2/10 empresas)** y duplica `carga_investing_10_full.py` (MERGE_REPLACE).
- `scripts/market/10b_actualizar_mep_hoy.py` duplica `actualizar_dolares.py`.

**Ruido / legacy**
- `docs/screener/failed_investing_scraping/` — 12 demos dead-end del scraping de investing.com (bloqueado por Cloudflare): ARCHIVE.
- `xbrlparse_v2_backup.py` — backup de 600+ líneas sin integrar: ARCHIVE/REVIEW.
- `tmp_byma_audit.py`, `tmp_byma3.py` — rutas absolutas `D:\` en raíz: ARCHIVE.
- `scripts/market/b4_mercado.py` — fecha `HOY` hardcodeada a 2026-08-22 (stale): revisar.
- `migrations/003_screener_iamc_mep.sql` — **NO APLICADA**: necesita autorización explícita (REVIEW).

## 11. Componentes no-Python (56)

| Grupo | n | Detalle |
|---|---:|---|
| Migraciones SQL root | 5 | `migrations/001..005` (schema, alinear prod, IAMC→MEP, tablas API, rango 52w) |
| Migraciones engine | 29 | `migrations/engine/001..031` (s00 bootstrap → s04 derived, checks f028..f045, menor privilegio) |
| Migraciones market | 3 | roles read-only, venue_ticker, invariantes corrida |
| Schemas/init | 5 | `sql/init/01_schema`, `scripts/pipeline/schema_v1` (medallion), `scripts/market/market_schema` (M19), `_research/schema/001` (duplicado), `docs/review/identity_v1_audit*.sql` (auditorías) |
| Deploy/shell/ps | 4 | `deploy.sh`, `scripts/setup_vps.sh`, `scripts/backup.sh`, `setup_scheduler.ps1` (Task Scheduler) |
| Infra | 5 | `Dockerfile`, `Dockerfile.api`, `docker-compose.yml` (postgres:16), `nginx/nginx.conf` |
| Config | 5 | `backend/pyproject.toml` (ruff), `engine/manifest.yaml`, `.env.example`, `.github/CODEOWNERS` |

## 12. Calidad y pendientes

- **26 campos NA** de un total de 15 400 (616 × 25): accion=45, riesgo=41, compat=23, complejidad=23 (un archivo puede estar en más de una). Ninguno bloquea el cálculo de matrices.
- Dos batches (`engine`, `scr_screener_b`) fueron re-clasificados hasta obtener vocabulario canónico validado.
- **Pendientes recomendados**:
  1. Revisar las 45 filas con `accion=NA` (listadas en el CSV maestro, columna `accion`).
  2. Resolver el conflicto `engine/s0..s4` vs `pipeline/f1..f8` antes de la migración de identidad.
  3. Tomar decisión explícita sobre `migrations/003_screener_iamc_mep.sql` (aplicar/descartar).
  4. Mover a ARCHIVE los 12 demos de `failed_investing_scraping` + `xbrlparse_v2_backup.py`.
  5. Sanear credenciales en `deploy.py`.

## Apéndice A — Assets del censo

Los CSVs maestros son evidencia y fuente de los agregados:

- `docs/review/censo_assets/catalaxia_censo_py_master.csv` — 616 filas, esquema 25 columnas.
- `docs/review/censo_assets/catalaxia_censo_no_py.csv` — 56 filas, mismo esquema.

Regeneración: `git ls-files` → partición en batches → clasificación (agentes LLM) → `merge.ps1` → `agg.ps1`/`agg2.ps1` (normalización) → este documento.

## Apéndice B — Hotlist ALTO (36) agrupada

- 12 demos `docs/screener/failed_investing_scraping/*` (REVIEW, ALTO) — dead-end scraping.
- Núcleo live: `api/main.py`, `engine/db.py`, `engine/identity_v1.py`, `engine/s03.py`, `scripts/engine/s01..s04`, `scripts/pipeline/run_pipeline.py`, `validar_suite.py`, `scripts/tickets/screener/run_all/update`, `publicar_screener_v2.py`, `scripts/tickets/cnv/metadata/recompute_ttm.py`.
- Migración/duplicación: `engine/identity.py` (MERGE_REPLACE), `pipeline/f1_identidad.py` (MERGE_REPLACE), `pipeline/f5_screener.py` (ADAPT), `pipeline/f6_sec.py` (REWRITE).
- Infra: `deploy.py` (REVIEW), `scripts/deploy/sincronizar_a_produccion.py`, `scripts/engine/adversario_ratios.py`.