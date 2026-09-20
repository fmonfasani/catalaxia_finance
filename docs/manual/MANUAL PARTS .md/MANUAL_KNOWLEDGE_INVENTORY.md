# Inventario del conocimiento — insumo del Manual Operativo

**Paso 1 de la secuencia. No es el manual y no contiene procedimientos.**
Es el relevamiento de qué conocimiento existe hoy, dónde está, si está
certificado y qué falta.

**64 ítems · 19 categorías · 34 certificados · 13 parciales · 17 sin certificar ·
11 BLOCKER · 9 IMPORTANT.**

Cada fila se verificó contra el repositorio o contra la base. Lo que no se pudo
verificar dice `NO_VERIFICADO`. Datos estructurados en
`MANUAL_KNOWLEDGE_INVENTORY.csv`.

---

## 1 · La buena noticia: ya existe un runbook

El manual no arranca de cero. `docs/runbooks/` tiene **7 documentos + 8
apéndices**, escritos explícitamente para "una persona que no conoce el proyecto
y que no va a preguntarle nada a nadie", y con la regla correcta ya adoptada:
*documenta cómo funciona el código que hay hoy, no cómo debería funcionar*.

| documento | qué cubre |
|---|---|
| `00_START_HERE.md` | qué es Catalaxia, prerequisitos, los tres caminos CNV, el puerto que no se toca |
| `01_COMMON_OPERATIONS.md` | operaciones frecuentes |
| `02_SEC_EDGAR_E2E_RUNBOOK.md` | S00→S04 + ratios, parametrizado por `--cik` |
| `02A_SEC_EDGAR_ADR_ANNEX.md` | anexo ADR |
| `03_CNV_E2E_RUNBOOK.md` | CNV, incluido el diagnóstico de documentos |
| `04_MARKET_DATA_E2E.md` | market |
| `05_RATIO_REFERENCE.md` | ratios |
| `06_PROVENANCE.md` | cadena de provenance |
| `07_CERTIFICATION.md` | certificación |
| `appendices/` | COMMAND_REFERENCE, DATABASE_REFERENCE, ERROR_CATALOG (9 códigos), CHECKPOINT_CATALOG (15), GOLDEN_RUNS, FALLBACK_MATRIX, RECOVERY_PROCEDURES, LOG_CATALOG |

Y existe una **matriz de readiness** (`outputs/runbook/RUNBOOK_READINESS_MATRIX.csv`,
19 componentes) que ya clasificó el estado real:

| estado | n |
|---|---:|
| `READY` | 4 |
| `PARTIAL` | 8 |
| `SOFTWARE_GAP` | 5 |
| `RUNBOOK_GAP` | 2 |

**Consecuencia para el plan:** el manual propuesto no es un documento nuevo sino
una **reorganización y ampliación** de lo que ya está, más los tres pilotos como
hilo conductor. Eso cambia el esfuerzo y conviene decidirlo antes de escribir.

---

## 2 · Los tres pilotos: qué hay realmente

Verificado en `derived.fact` de la base `catalaxia` @5433, no supuesto.

| | YPF | KO | METR |
|---|---|---|---|
| identificador | CIK `0000904851` | CIK `0000021344` | CUIT `30657863676` |
| fuente | SEC/EDGAR | SEC/EDGAR | CNV |
| formulario | 20-F | **10-K** | EEFF (HTML) |
| taxonomía | IFRS + accesorios `srt`/`us-gaap` | **us-gaap puro** | códigos CNV |
| hechos en el canónico | **47.930** | **45.113** | 4.648 (fixture) |
| filings / documentos | 9 | **17** (2009–2025) | 60 con datos, 226 cáscaras |
| golden run documentado | **sí**, completo, con 7 gates | **NO** | parcial (Tramo A) |
| resultados esperados | sí | **NO** | sí (demo 5Y) |
| provenance E2E verificada | manual | **no** | **sí**, 289 celdas, 0 rotos |
| homologación externa | no | no | **sí** (TIKR, 327 comparaciones) |

**El hallazgo que más condiciona el plan: KO tiene los datos pero no tiene
recorrido.** 45.113 hechos y 17 filings 10-K están cargados —es la segunda
entidad con mejor cobertura del sistema— pero no hay ningún runbook, golden run,
resultado esperado ni evidencia de que el E2E se haya corrido para KO. El
runbook SEC es paramétrico por `--cik`, así que **mecánicamente** corre; lo que
falta es la certificación.

Además hay **7 entidades SEC más** ya ingestadas (Galicia, Macro, TGS, Central
Puerto, Microsoft, NVIDIA, Apple), ninguna documentada. Y `identity.entities`
tiene **7.998 entidades** de las cuales sólo **9 tienen hechos** — el cuello de
botella conocido: el límite del producto es la ingesta, no el cálculo.

### Qué aporta cada piloto al manual

- **YPF** — el recorrido pedagógico completo. Es el único con los 7 gates
  documentados y la prueba de idempotencia (`hash_out` idéntico en la segunda
  corrida de S03).
- **KO** — la demostración de generalización: misma arquitectura, otra
  taxonomía. **Hay que construirlo**, no documentarlo.
- **METR** — el cambio de fuente. Aporta lo que ningún otro tiene: NIL
  declarado, escala variable por ejercicio (`ars@1e3` en 2021, `ars@1e6`
  después), perímetro declarado vs evidenciado, USD MEP, Golden Run y
  homologación externa.

---

## 3 · Los 11 BLOCKER

Ordenados por lo que impedirían al operador externo.

| id | qué falta | por qué bloquea |
|---|---|---|
| **PRE-01** | `docker-compose.yml` **no declara `catalaxia-engine-dev`** | es la base contra la que corren *todos* los comandos del runbook (5433). Declara `catalaxia-db`, `catalaxia-pipeline`, `catalaxia-api` y `catalaxia-nginx`, pero no ésa. Un operador no puede recrear el entorno |
| **PRE-02** | `requirements.txt` no cubre el engine | tiene 3 líneas (`fastapi`, `uvicorn`, `psycopg2-binary`) y es del servicio API. El engine importa además `sqlalchemy`, `psycopg`, `lxml`, `requests`, `openpyxl`, `yfinance` y `pytest`, sin declarar en ningún archivo |
| **FAL-02** | no hay procedimiento de instalación desde cero | falta el `git clone`, las dependencias reales y el contenedor de desarrollo |
| **PIL-KO-01 / FAL-01** | KO sin golden run | la Parte IV del plan no se puede escribir sin correr el E2E de KO y certificar sus resultados |
| **OPS-02** | el adaptador canónico CNV vive en un worktree sin mergear | no existe un E2E CNV ejecutable desde el repo principal (`SOFTWARE GAP SG-01`) |
| **ERR-02** | `RECOVERY_PROCEDURES.md` **abre con la sección "Lo que no existe"** | no hay `--resume` en ningún script, no hay quarantine, no hay rollback |
| **ERR-04 / FAL-03** | no existe árbol de diagnóstico | es exactamente lo que piden las Partes VI y VII del plan |
| **GAT-02** | no hay script único de gate/certificación | hoy el gate se lee a ojo en la consola; no hay exit code agregado |
| **PRV-03** | Market: enlace instrumento → entidad **roto** | la matriz lo marca `provenance ROTA`; 15 de 584 instrumentos enlazados. Bloquea valuación generalizada |

## 4 · Los 9 IMPORTANT

| id | qué |
|---|---|
| PRE-04 | `DOLARITO_AUTH_CLIENT` está documentado en el docstring del script, en ningún runbook. **La CNV no requiere autenticación** — verificado |
| CMD-02 | de 374 scripts, ~12 son entry points oficiales; el resto no está clasificado |
| CMD-03 | 9 de los 11 scripts de `scripts/market/` no están documentados |
| OPS-01 / FAL-07 | hay **8 bases en 5433** y `DATABASE_REFERENCE.md` documenta 2 |
| OPS-04 | hay `market_snapshots` (577 filas) pero ninguna maquinaria de snapshot para SEC ni CNV, y ningún rollback |
| FAL-04 | E2E de Market parcialmente documentado |
| FAL-05 | no hay verificación E2E de provenance para SEC (para CNV sí: `d3_metr5y_provenance.py`) |
| FAL-06 | no hay gate con exit code |
| AUD-01 | la lección "nunca asumir que si no está en la tabla no ocurrió" existe en la práctica, no escrita |

---

## 5 · Las 3 contradicciones encontradas

1. **`ARQ-03`** — la arquitectura declara *Source Adapter → Canonical Model →
   Financial Model → Ratio Engine*, pero `ratio_engine.py` sigue siendo
   SEC-first: toma `--cik` e itera `ciks_del_universo()`. La frontera existe en
   `d2_metr5y_model.py` (que sí es agnóstico de fuente) pero **el Financial
   Model no está persistido**: hoy se arma en memoria y no hay tabla.

2. **`TIKR-03`** — el plan del manual pide los estados
   `METHODOLOGY_DIFFERENCE` y `DATE_DIFFERENCE`, que **no están** en el set de
   12 implementado. El set actual usa `DIFFERENT_DEFINITION`,
   `PERIOD_MISMATCH`, `CURRENCY_MISMATCH`, `UNIT_MISMATCH`,
   `PERIMETER_MISMATCH`, `SOURCE_MISMATCH`, `TIKR_ONLY`, `CATALAXIA_ONLY`,
   `CATALAXIA_MISSING`, `TIKR_MISSING`, `ANOMALY`, `UNRESOLVED`. **Hay que
   decidir cuál set es el canónico** antes de escribir la Parte X.

3. **`DEC-04`** — Catalaxia usa MEP y TIKR usa mayorista. No es una
   contradicción interna sino una diferencia medida (0,0–0,3 % de ajuste al
   mayorista, brecha del 85 % en 2021), y está documentada. Se anota para que el
   manual no la presente como error.

---

## 6 · Qué está sólido y se puede reusar tal cual

- **Los gates de SEC** — 7 etapas con exit code y señal en consola verificable.
- **La prueba de idempotencia de S03** — `hash_out` idéntico y checkpoint
  reusado. Es el único procedimiento de idempotencia que está escrito como
  procedimiento y no como concepto.
- **El guard de producción** — 5432 nunca se escribe; verificado en cada sprint,
  producción tiene sólo el esquema `public`.
- **La guarda de pertenencia** (`ratio_inputs.INVARIANTE_PERTENENCIA`) — todo
  `source_fact_id` resuelve al mismo emisor, filing y concepto.
- **El catálogo de comandos** — argumentos verificados contra el `argparse` de
  cada script, no de memoria.
- **Las decisiones arquitectónicas de CNV** — `econ_key` sin `value` ni
  `es_nil`; no inferir supersesión por ordinal; CNV entra al registry como
  tercera taxonomía sin motor aparte (780 resoluciones SEC, 0 cambiadas).
- **585 tests** en el worktree. Hoy fallan 5: 3 por drift de datos en la base
  `catalaxia` (lote M23, 601 filas contra 591 esperadas) y 2 son guardas de
  sprints de auditoría que detectaron —correctamente— un cambio posterior en
  `ratio_defs.py`.

---

## 7 · Decisiones que hacen falta antes del paso 2

Cuatro, y ninguna la puedo tomar yo:

1. **¿KO se construye o se reemplaza?** No tiene golden run. Construirlo
   significa correr el E2E completo y certificarlo — un sprint en sí mismo. La
   alternativa es usar como segundo piloto una de las otras 7 entidades SEC ya
   ingestadas, con el mismo problema.

2. **¿El manual reemplaza `docs/runbooks/` o lo envuelve?** Hay 7 documentos +
   8 apéndices que ya funcionan. Reescribirlos desde cero pierde trabajo
   verificado; envolverlos rompe la regla de autosuficiencia del plan.

3. **¿Los BLOCKER se documentan o se arreglan?** `PRE-01`, `PRE-02` y `FAL-02`
   son de instalación: sin ellos el manual **no puede** ser autosuficiente, y
   arreglarlos es tocar `docker-compose.yml` y `requirements.txt`.

4. **¿Cuál es el set canónico de estados de homologación?** El del plan o el
   implementado (§5.2).

---

## 8 · Qué NO hice

No escribí el manual, no diseñé el índice, no corregí ningún gap y no toqué
producción, `screener.db`, SEC, Identity, Market ni el ratio engine. Este paso
es sólo el inventario.

| archivo | contenido |
|---|---|
| `MANUAL_KNOWLEDGE_INVENTORY.csv` | 64 ítems × 11 columnas |
| `MANUAL_KNOWLEDGE_INVENTORY.md` | esta lectura |

Generador: `scripts/engine/g1_manual_inventory.py` (worktree, sólo lectura).
