# 00 · EMPEZAR ACÁ

Este directorio es el manual de operación de Catalaxia. Está escrito para una
persona que **no conoce el proyecto** y que no va a preguntarle nada a nadie.

**No documenta cómo debería funcionar el sistema. Documenta cómo funciona el
código que hay hoy.** Donde el software no alcanza para operar de forma
determinística, dice `SOFTWARE GAP` y no inventa una solución.

Antes de correr nada, leé la sección 4 de este archivo. Hay un puerto que
**nunca** se toca.

---

## 1 · Qué es Catalaxia

Un sistema que toma estados financieros de dos fuentes —**SEC/EDGAR** (Estados
Unidos, XBRL) y **CNV** (Argentina, HTML)—, los normaliza a un modelo común y
calcula ratios, dejando registro de dónde salió cada número.

Hay **dos pipelines**, y no comparten etapas:

```
SEC   S00 → S01 → S02 → S03 → S04 → ratios
CNV   (ver §3: hay tres caminos y sólo uno produjo los datos actuales)
```

## 2 · Qué necesitás instalado

| | verificación |
|---|---|
| Docker corriendo | `docker ps` debe listar `catalaxia-engine-dev` y `catalaxia-db` |
| Python 3.11+ | `python --version` |
| `psql` accesible | vía `docker exec`, no hace falta cliente local |
| El repo | este directorio es `docs/runbooks/` dentro del repo |

Todos los comandos de estos manuales se ejecutan **desde la raíz del repo**.

## 3 · Los caminos reales, y cuál es el oficial

Esto es lo primero que confunde a alguien nuevo, así que va explícito.

### SEC — un solo camino, oficial

Cinco scripts, cada uno con un `STAGE_ID` registrado en la base:

| STAGE_ID | script |
|---|---|
| `S00_bootstrap` | `scripts/engine/s00_smoke.py` |
| `S01_identity` | `scripts/engine/s01_identity.py` |
| `S02_fetch` | `scripts/engine/s02_fetch_ypf.py` |
| `S03_parse` | `scripts/engine/s03_parse_ypf.py` |
| `S04_normalize` | `scripts/engine/s04_normalize.py` |

Después, ratios: `scripts/engine/ratio_engine.py`. Y desde F12, la cadena
formal de validación/certificación/publicación:
`scripts/engine/c10_evaluate.py` → `c11_certificar.py` → `publisher.py`
— no tienen `STAGE_ID` (no escriben `engine.stage_runs`), leen/certifican
lo que S00-S04 ya escribieron. Las 5 etapas se pueden encadenar bajo un
mismo `run_id` con `scripts/engine/e2e_orchestrator.py` (solo S00-S04) o
con `scripts/engine/run_e2e_certified.py` (cadena completa hasta C12,
con advisory lock — es el entrypoint del runtime containerizado,
`Dockerfile.engine`/`docker-compose.yml` perfil `run-e2e`). Detalle
operativo: `02_SEC_EDGAR_E2E_RUNBOOK.md` y
`docs/runbooks/GUIA_OPERATIVA_PIPELINE_ENGINE.md`.

### CNV — tres caminos, y el que produjo los datos NO es el oficial

Esto es un hallazgo de este sprint, no una decisión de diseño documentada:

| camino | script | estado real |
|---|---|---|
| **A · engine** | `scripts/engine/c3_cnv_fetch.py` (`STAGE_ID=C3_CNV_fetch`) | Es el camino con instrumentación (corridas, gates, ledger de descarga). **Pero sólo descarga páginas de visor y de empresa** — `artifact_kind` en el ledger es únicamente `VISOR` y `EMPRESA_PAGE`. **No descarga los estados financieros.** |
| **B · legacy** | `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` → `data/screener.db` | **Es el que produjo todos los datos CNV que hoy existen.** Sin ledger, sin SHA256 almacenado, y descarta documentos en silencio (ver `appendices/ERROR_CATALOG.md`, `CNV-EX-001`). |
| **C · adaptador canónico** | `scripts/engine/c4_cnv_adapter.py` | Lleva lo de (B) al modelo canónico de PostgreSQL. **Vive en un worktree aparte (`catalaxia-cnvmig`, rama `feat/cnv-canonical`) y no está mergeado.** |

**Consecuencia operativa:** hoy no existe un E2E de CNV ejecutable de punta a
punta desde el repo principal. Está registrado como `SOFTWARE GAP SG-01` en
`RUNBOOK_READINESS_REPORT.md`.

### Scripts que NO debés ejecutar

`scripts/engine/` tiene 60 archivos. La mayoría son auditorías puntuales,
bancos de prueba de defectos concretos (`f0NN_*`, `audit_f0NN_*`, `mut_*`) y
adversarios. **No son parte del E2E.** Regla: si el script no aparece en las
tablas de arriba ni en `appendices/COMMAND_REFERENCE.md`, no lo corras como
parte de un pipeline.

Casos peligrosos por nombre —**no ejecutar nunca sin leer el archivo**:

- `scripts/engine/mut_f054_f055.py` — hace `DELETE FROM parsed.facts`
- `scripts/engine/reparse_universo.py` — reprocesa todo el universo
- `scripts/pipeline/fix_*.py` — parches históricos de una sola vez

## 4 · Seguridad de producción — leer antes de correr algo

**Hay dos bases de datos PostgreSQL en esta máquina y se parecen.**

| puerto | contenedor | base | qué es |
|---|---|---|---|
| **5432** | `catalaxia-db` | `catalaxia` | **PRODUCCIÓN. Nunca escribir.** |
| **5433** | `catalaxia-engine-dev` | `catalaxia`, `cnvmig`, … | Desarrollo / fixtures |

Está declarado en `engine/manifest.yaml`:

```yaml
storage:
  dev_target:     127.0.0.1:5433/catalaxia (docker catalaxia-engine-dev)
  prod_protegido: 127.0.0.1:5432/catalaxia (catalaxia-db, jamas escribir)
```

El código tiene un guard real, **EXT-010**, en `engine/config.py`: si
`ENGINE_DB_PORT=5432` y no está `ENGINE_ALLOW_PROD=1`, `load_settings()` lanza
`RuntimeError` y el proceso muere antes de conectar.

**Verificación obligatoria antes de cada E2E** — copiá y pegá:

```bash
python -c "from engine.config import load_settings; s=load_settings(); print(s.describe())"
```

Salida esperada (ejemplo):

```
catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False
```

**Si `prod=True`, o el puerto no es 5433: ABORTAR.** No sigas. Ver
`appendices/RECOVERY_PROCEDURES.md`, caso 20.

Además, `data/screener.db` es un artefacto que varios scripts abren. Anotá su
huella antes de empezar y comparala al terminar:

```bash
stat -c '%y %s' data/screener.db
```

## 5 · Orden de lectura

1. **`01_COMMON_OPERATIONS.md`** — verificación de entorno, cómo mirar corridas,
   cómo leer un gate. Se usa en los dos pipelines.
2. **`02_SEC_EDGAR_E2E_RUNBOOK.md`** — el E2E de SEC, paso a paso, **incluye
   S00-S04, ratios y la cadena C10→C11→C12 (F12)**.
   `02A_SEC_EDGAR_ADR_ANNEX.md` si el emisor tiene ADR.
3. **`03_CNV_E2E_RUNBOOK.md`** — el de CNV, con sus huecos marcados.
4. **`04_MARKET_DATA_E2E.md`**, **`05_RATIO_REFERENCE.md`**,
   **`06_PROVENANCE.md`**, **`07_CERTIFICATION.md`** — según lo que necesites.
5. **`GUIA_OPERATIVA_PIPELINE_ENGINE.md`** — referencia rápida por script
   (input/output/comando/validación/siguiente) de S00-S04, ratios, C10,
   C11 y C12, con ejemplos reales.

Los `appendices/` son de consulta, no de lectura lineal.

## 6 · Convenciones de estos manuales

- **Comando exacto** significa exacto: se copia y se pega, desde la raíz del repo.
- **`SOFTWARE GAP`** = el software no tiene el mecanismo. No hay workaround
  documentado porque no hay mecanismo que documentar.
- **`RUNBOOK GAP`** = el mecanismo existe pero no está documentado de forma que
  un operador nuevo pueda usarlo sin interpretar código.
- Los estados de etapa que verás en la base son los de `engine/states.py`:
  `PLANNED READY RUNNING VALIDATING FAILED FIXING RERUNNING PASSED
  CHECKPOINTED CERTIFIED`. Los gates son `PASS WARNING BLOCK`.
  **No existen `QUARANTINED`, `SKIPPED` ni `RECOVERED`** — ver
  `RUNBOOK_READINESS_REPORT.md` §2.

## 7 · Si algo sale mal

1. Buscá el síntoma en `appendices/ERROR_CATALOG.md`.
2. Si tiene código de error, seguí la acción indicada.
3. Si no lo encontrás, mirá `appendices/RECOVERY_PROCEDURES.md` (20 casos).
4. Si tampoco está: **no improvises sobre la base**. Anotá qué pasó y pará.

**Ninguna instrucción de estos manuales requiere consultar a una IA, a un
desarrollador ni a documentación fuera de este directorio.**
