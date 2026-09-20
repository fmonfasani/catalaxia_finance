# 04 â€” PIPELINE REAL BYMAStocks
Estado: FASE 1 (auditorÃ­a). QuÃ© corre de verdad HOY, no el diseÃ±o nominal.

## 1. Los pipelines reales

No existe "el pipeline": hay **3 pipelines de datos** + 1 API + set de tickets de reparaciÃ³n.

### 1.1 Engine canÃ³nico (el mÃ¡s cercano a la arquitectura oficial)
- Orquestador: `engine/manifest.yaml` â€” `pipeline_version: s0-bootstrap-v1`, contrato por fases.
- Etapas visibles: `scripts/engine/s00_smoke.py`, `s01_identity.py`, `s02_fetch_ypf.py`, `s03_parse_ypf.py`, `s04_normalize.py`, mÃ¡s `engine/{config,db,identity_v1,s03,fetch,states,report,hashout,xbrlparse}.py`.
- Dependencias: `engine/db.py`/`engine/config.py` base; escribe a `engine.stage_runs` (checkpoints) y tablas `engine.*`.
- Estado: es el nÃºcleo en construcciÃ³n/reconciliaciÃ³n. **[VERIFICADO POR CÃ“DIGO]**.

### 1.2 Pipeline legacy `scripts/pipeline/`
- Orquestador: `run_pipeline.py` (f1..f6).
- Hallazgos deep audit:
  - `f3_normalizar_cnv.py` **muerto / no invocado** en run_pipeline actual (fuentes corruptas). **[VERIFICADO POR EJECUCIÃ“N implÃ­cita, deep audit]**
  - `f6_sec.py` **mezcla RATIOS + CERTIFICACIÃ“N + PUBLICACIÃ“N** (capa rota). `DECISION_REQUIRED`.
  - `f1_identidad.py` duplicada de `identity_v1`. `f4_ratios.py` sin provenance de insumos (I-006 ausente).
- Estado: parcialmente funcional pero **superado por engine canÃ³nico** y sin gobierno de certificaciÃ³n.

### 1.3 Screener tickets
- Orquestadores: `run_all.py`, `run_screener.py`, `run_update.py`.
- Orquesta fases `s0..s8`: DROP+CREATE/rebuild; chequear 572 filas como **warning** (no vincula publicaciÃ³n).
- `run_update.py` **borra RAW EDGAR** (:297-300) para forzar re-descarga â†’ viola I-001. `DECISION_REQUIRED`.
- Sin transaccionalidad entre fases (fallo intermedio deja estado parcial).

### 1.4 API
- `api/main.py` publica `screener` (v2) y `silver_norm/validaciones` (v1 legacy) **sin gate de certificaciÃ³n**.

## 2. Flujo de datos real (resumen de hoja)

```text
FUENTES (01) â”€  engine/s02_fetch, cnv/discovery, tickets/sec_edgar/descarga
IDENTIDAD(02)â”€  engine/identity_v1.py (authoritative) vs f1_identidad (legacy dup) vs construir_base/catalogo
RAW(03)      â”€  data/raw/ (fingerprint) [AMENAZA: run_update.py lo borra]
PARSED(04)   â”€  engine/s03_parse, engine/xbrlparse
NORMALIZADO(05)- engine/s04_normalize vs f3 (dead) vs tickets s*
EF/Model(06-07)- scripts/engine/ratio_inputs, ratio_defs, s04-derived
RATIOS(08)   â”€  f4_ratios / ratio_engine (duplicados parciales)
PROVENANCE(09)- engine/report, states; identity_v1.source (parcial)
VALIDACION(10)- validar_suite (18 checks, real) + tests/ + market/tests
CERTIFICACION(11)- f6_sec y validar_suite autocertifican (regla privada) â†’ sin capa 11 independiente
PUBLICACION(12)- api/main.py + gen_screener_html (respetan certificaciÃ³n? api NO gatea)
```

## 3. Brechas de flujo (concordancia)

| Capa | Pierna real | Brecha |
|---|---|---|
| 01 | s02_fetch, discovery, sec_edgar | mÃºltiples fuentes desconectadas |
| 02 | identity_v1 + f1_identidad + construir_* | **3 identidades paralelas** |
| 03 | data/raw | raw borrable en run_update |
| 04 | s03/xbrlparse | dependencia fuerte config |
| 05 | s04 | f3 dead, pero f3b existe |
| 06/07 | ratio_inputs/ratio_defs | modelo parcial |
| 08 | f4 vs ratio_engine | duplicaciÃ³n |
| 09 | report/states/source | provenance OK solo en engine |
| 10 | validar_suite | real pero sin gates vinculantes |
| 11 | (no hay) | **mÃ¡xima brecha** |
| 12 | api + html | no gatea certificaciÃ³n |

`VERIFICADO POR CÃ“DIGO` (fuentes de scripts y deep audit).

## 4. Gaps casa1 de certificaciÃ³n (crÃ­tico)

- Ninguna capa 11 real: `validar_suite` y `f6_sec` autocertifican internamente (la misma entidad que calcula decide el sello). Es la violaciÃ³n arquitectÃ³nica nÂº1: un componente NO puede ser juez de su propia capa (harness, secc. 1.10/1.11; regla "VALIDACIÃ“N no equivale a CERTIFICACIÃ“N").
- `run_all` no aborta en FAILED â†’ puede marcar "ok" un pipeline incompleto.
- `api/main.py` publica sin verificar certificaciÃ³n de `screener`.

## 5. RecomendaciÃ³n (NO ejecutada)

1. Basar la reingenierÃ­a en el **engine canÃ³nico** como Ãºnico pipeline 01-07/09.
2. Levantar una **capa 11 independiente** (que lea stage_runs/assertions y emita certificaciÃ³n) antes de tocar PUBLICACIÃ“N.
3. Gatear `api` y `gen_screener_html` sobre la certificaciÃ³n emitida.
4. Retirar progresivamente pipeline legacy y tickets (10_DELETE/09_MERGE).