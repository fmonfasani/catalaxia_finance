# PARTE I — CÓMO USAR ESTE MANUAL

**Prefacio. No es uno de los 17 capítulos obligatorios del alcance.** Es la
puerta de entrada: orienta **antes de tocar un comando** y declara las reglas
con las que está escrito todo lo que sigue.

Está escrita para una persona que **no conoce el proyecto** y que no va a
preguntarle nada a nadie.

**Material de base:** `docs/runbooks/00_START_HERE.md` §1, §3, §5, §6;
`docs/manual/MANUAL_SCOPE.md` §0, §1.2, §5 (N-2).

---

## 1 · Qué es Catalaxia

Un sistema que toma estados financieros de dos fuentes —**SEC/EDGAR** (EE. UU.,
XBRL) y **CNV** (Argentina, HTML)—, los normaliza a un modelo común y calcula
ratios, dejando registro de dónde salió cada número.

**Hay dos pipelines, y no comparten etapas:**

```
SEC   S00 → S01 → S02 → S03 → S04 → ratios      (un esquema, un camino)
CNV   TRAMO A (engine, con gate, sin EEFF)
      TRAMO B (legacy, el que produjo los datos, sin registro)
      TRAMO C (adaptador canónico, en el worktree)
```

![Figura 1 · Arquitectura del sistema](images/arquitectura_sistema.png)

Este manual **no documenta cómo debería funcionar el sistema. Documenta cómo
funciona el código que hay hoy.** Donde el software no alcanza para operar de
forma determinística, dice `SOFTWARE GAP` y no inventa una solución.

---

## 2 · El hecho que parte el alcance en dos

El repositorio principal llega a la **migración 033**. El worktree
`catalaxia-cnvmig` (rama `feat/cnv-canonical`) tiene tres más y, con ellas,
cinco scripts que el repo principal **no tiene**:

| artefacto | repo principal | worktree |
|---|---|---|
| `s00_smoke` … `s04_normalize`, `ratio_engine`, `ratio_defs`, `c3_cnv_fetch` | **sí** | sí |
| `job5_v2_extract_eeff` (extracción CNV legacy) | **sí** | sí |
| `c4_cnv_adapter`, `c4_cnv_semantica` | **no** | sí |
| `d1_metr5y_market`, `d2_metr5y_model`, `d3_metr5y_provenance` | **no** | sí |
| `h1_tikr_metr_homologacion` | **no** | sí |
| migraciones `034/035/036` (`entity_id` CNV, `measurement_date`, `econ_key`) | **no** | sí |

![Figura 2 · Estilos de pipeline y flujos — la partición del alcance](images/estilos_pipeline_flujos.png)

**Consecuencia:** 4 de los 17 capítulos obligatorios **no son ejecutables desde
el repo principal** — Economic Facts, Financial Model, el tramo canónico de
CNV y la homologación TIKR. No es una opinión sobre prioridades: es que los
archivos no están ahí. La decisión de cómo documentarlo es **D-1**, y ninguno
de estos manuales la resuelve: la marca y sigue.

---

## 3 · Qué es parte del E2E y qué no

![Figura 3 · Vista esquemática del pipeline E2E](images/pipeline_diagrama1.png)

### SEC — un solo camino, oficial

| STAGE_ID | script |
|---|---|
| `S00_bootstrap` | `scripts/engine/s00_smoke.py` |
| `S01_identity` | `scripts/engine/s01_identity.py` |
| `S02_fetch` | `scripts/engine/s02_fetch_ypf.py` |
| `S03_parse` | `scripts/engine/s03_parse_ypf.py` |
| `S04_normalize` | `scripts/engine/s04_normalize.py` |
| después | `scripts/engine/ratio_engine.py` |

### CNV — tres caminos, y el que produjo los datos NO es el oficial

| camino | script | estado real |
|---|---|---|
| **A · engine** | `scripts/engine/c3_cnv_fetch.py` | instrumentado, con gates y ledger — **pero solo baja `VISOR` y `EMPRESA_PAGE`**. No descarga estados financieros (`L-7`, `SG-01`) |
| **B · legacy** | `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` | **el que produjo todos los datos CNV que existen.** Sin ledger, sin SHA, descarta en silencio (`CNV-EX-001`, `L-6`). Escribe en `data/screener.db` |
| **C · canónico** | `scripts/engine/c4_cnv_adapter.py` | en el worktree, sin mergear (D-1) |

### El resto — la regla de los 374

`scripts/engine/` tiene 60 archivos; el repo entero, cientos. La mayoría son
auditorías puntuales, bancos de prueba de defectos concretos (`f0NN_*`,
`audit_f0NN_*`, `mut_*`) y adversarios **que no son parte del E2E** (regla N-2).
Regla: **si el script no aparece en las tablas de arriba ni en
`docs/manual/MANUAL_COMMAND_CATALOG.md`, no se corre como parte de un
pipeline.**

**Scripts peligrosos por nombre — no ejecutar nunca sin leer el archivo:**

- `scripts/engine/mut_f054_f055.py` — hace `DELETE FROM parsed.facts`
- `scripts/engine/reparse_universo.py` — reprocesa todo el universo
- `scripts/pipeline/fix_*.py` — parches históricos de una sola vez

---

## 4 · Seguridad de producción — leer antes de correr algo

**Hay dos bases PostgreSQL en esta máquina y se parecen.**

| puerto | contenedor | base | qué es |
|---|---|---|---|
| **5432** | `catalaxia-db` | `catalaxia` | **PRODUCCIÓN. NUNCA escribir.** |
| **5433** | `catalaxia-engine-dev` | `catalaxia`, `cnvmig`, … | desarrollo / fixtures |

El código tiene un guard real, **`EXT-010`**, en `engine/config.py`: si
`ENGINE_DB_PORT=5432` y no está `ENGINE_ALLOW_PROD=1`, `load_settings()`
lanza `RuntimeError` y el proceso muere **antes de conectar**.

**Verificación obligatoria antes de cada E2E:**

```bash
python -c "from engine.config import load_settings; s=load_settings(); print(s.describe())"
```

Salida esperada: `catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False`.
**Si `prod=True` o el puerto no es 5433: ABORTAR** (`RECOVERY_PROCEDURES.md`,
caso 20).

Además, `data/screener.db` es un artefacto que varios scripts abren. Se anota
su huella antes y se compara al terminar (`stat -c '%y %s' data/screener.db`).

---

## 5 · Cómo se lee este manual

- **Comando exacto** significa exacto: se copia y se pega, desde la raíz del
  repo.
- **Tres rótulos, y solo tres**, nunca para tapar:
  `NOT_IMPLEMENTED` · `DECISION_REQUIRED` · `KNOWN_LIMITATION`. Y el estado
  común de diagnóstico de los pilotos: `PASS` / `PASS_WITH_WARNINGS` /
  `BLOCKED` / `NOT_READY`.
- **Estados de etapa** (`engine/states.py`): `PLANNED READY RUNNING VALIDATING
  FAILED FIXING RERUNNING PASSED CHECKPOINTED CERTIFIED`. **No existen
  `QUARANTINED`, `SKIPPED` ni `RECOVERED`** (`L-2`). Gates: `PASS WARNING
  BLOCK`.
- **`SOFTWARE GAP`** = el software no tiene el mecanismo; no hay workaround
  porque no hay mecanismo que documentar. **`RUNBOOK GAP`** = el mecanismo
  existe pero no está documentado de forma usable por un operador nuevo.
- **`docs/runbooks/` no se reescribe** (regla N-6): cada parte cita su archivo
  fuente exacto. Los apéndices son de consulta, no de lectura lineal.
- **La regla de oro de auditoría:** nunca asumir que si el dato no está en la
  tabla entonces no ocurrió; primero determinar base, puerto, `run_id`, etapa y
  snapshot.

---

## 6 · El mapa del manual

| Parte | capítulos del alcance | rótulo | fuente principal |
|---|---|---|---|
| **I** · Cómo usar este manual | Cap. 0 (prefacio) | — | `00_START_HERE.md` |
| **II** · Preparación del entorno | Cap. 1 | `KNOWN_LIMITATION` + bloqueado por C-1 | `01_COMMON_OPERATIONS.md` |
| **III** · Piloto YPF | Caps. 2–5 (SEC E2E) | ejecutable | `02_SEC_EDGAR_E2E_RUNBOOK.md` |
| **IV** · Parser (S03) | Cap. 4 | ejecutable | ídem (S03) |
| **V** · Normalización (S04) | Cap. 5 | ejecutable | ídem (S04) |
| **VI** · Economic Facts + Financial Model | Caps. 6–7 | `NOT_IMPLEMENTED` + D-1 | `06_PROVENANCE.md` §4; worktree |
| **VII** · Ratio Engine | Cap. 8 | ejecutable | `05_RATIO_REFERENCE.md` |
| **VIII** · Market | Cap. 9 | `KNOWN_LIMITATION` (L-5) | `04_MARKET_DATA_E2E.md` |
| **IX** · CNV | Cap. 10 | `PARCIAL` + D-1 (tramo C) | `03_CNV_E2E_RUNBOOK.md` |
| **X** · Provenance | Cap. 11 | ejecutable | `06_PROVENANCE.md` |
| **XI** · Idempotencia | Cap. 14 | ejecutable (SEC); C-5 (CNV) | `GOLDEN_RUNS.md` §1 |
| **XII** · Validación | Cap. 12 | ejecutable | `01_COMMON_OPERATIONS.md` §5 |
| **XIII** · Certificación | Cap. 16 (+13, gate agregado L-4) | ejecutable (con matices) | `07_CERTIFICATION.md` |
| **XIV** · Homologación TIKR | Cap. 17 | `NOT_IMPLEMENTED` + D-4 | `METR_TIKR_2025_REPORT.md` |
| **XV** · Troubleshooting | Cap. 15 | `PARCIAL`: catálogo sí, árbol por escribir | `RECOVERY_PROCEDURES.md`, `FALLBACK_MATRIX.md`, `ERROR_CATALOG.md` |
| **XVI** · Golden Run | apéndice Golden Runs | ejecutable | `GOLDEN_RUNS.md`, `METROGAS_GOLDEN_RUN_REPORT.md` |
| **XVII** · Estado real | síntesis | medición | las Partes II–XVI |
| **XVIII** · Qué falta | cierre | decisiones + gaps | `RUNBOOK_READINESS_REPORT.md`, `MANUAL_SCOPE.md` |
| **XIX** · Anexo B | diagramas de referencia | material visual oficial | `docs/diagramas/` |
| **XX** · Anexo C | plantillas de diagramas (Mermaid) | material visual editable | `docs/diagramas/plantillas/` |
| **XXI** · Anexo D | biblioteca oficial de diagramas (v2.0) | material visual oficial | `docs/diagramas/` (capturas) |

![Figura 4 · Vista general de diagramas del proyecto](images/diagramas_vista_general.png)

---

## 7 · Orden de lectura según lo que necesitás

1. **Entender el sistema** → Parte I, después XIV (homologación) y XVII
   (estado real).
2. **Correr el E2E de SEC** → Parte II, III (YPF) o IV/V (etapas) → XVI
   (golden run).
3. **Operar market o CNV** → Parte VIII o IX, siempre tras la II.
4. **Diagnosticar un número** → Parte X (provenance) → XV (troubleshooting).
5. **Certificar una corrida** → XII (validación) → XIII (certificación) →
   XVI (golden run).
6. **Decidir el cierre del proyecto** → XVII → XVIII.

---

## GATE de la Parte I

**Lectura obligatoria previa, sin verificaciones ejecutables.** Quien arranca
por un capítulo sin saber cuál de los tres caminos CNV es legacy, o sin ver
`prod=False`, está en condiciones de hacer dos cosas a la vez: malentender los
datos y escribir en producción. El manual asume que esta parte se leyó dos
veces: una al empezar y otra antes de tocar algún comando después de un
tiempo.

---

*Ningún comando de esta parte es ejecutable por sí mismo; todos se desarrollan
en las Partes II y siguientes. Si un capítulo parece contradecir esta parte,
esta parte está más vieja.*