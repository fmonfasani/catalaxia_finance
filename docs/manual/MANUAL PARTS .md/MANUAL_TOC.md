# MANUAL_TOC — índice definitivo de CATALAXIA_OPERATIONS_MANUAL.md

**Fecha:** 2026-09-04 · **Paso 3 de la secuencia.** Insumos leídos por completo:
`docs/manual/MANUAL_KNOWLEDGE_INVENTORY.md` (+ csv, Paso 1) y
`docs/manual/MANUAL_SCOPE.md` (Paso 2) — este último apareció en el
repositorio **durante** la redacción de este índice; una primera versión se
escribió sin él y se descartó porque el alcance real que define (17
capítulos obligatorios, la partición por worktree, los rótulos canónicos) no
coincidía con una estructura inventada de cero. Esta es la versión alineada
a Paso 2. También se leyó `docs/runbooks/` completo (9 documentos + 8
apéndices, 3.055 líneas).

Este documento es **solo el índice**. No contiene procedimientos ni
comandos completos con su ficha — eso es Paso 4, no autorizado todavía. No
se modificó código.

---

## 0. Reglas que este índice hereda de `MANUAL_SCOPE.md` y no reinventa

1. **17 capítulos obligatorios** (§1.1 de `MANUAL_SCOPE.md`). Este índice
   usa esa numeración como columna vertebral — no una propia. Cap. 0 (abajo)
   es la única adición, y es explícitamente un prefacio, no un capítulo
   obligatorio.
2. **Tres rótulos, y solo esos tres**, aplicados por capítulo:
   `NOT_IMPLEMENTED` (el procedimiento no existe en el software),
   `DECISION_REQUIRED` (hace falta una decisión humana antes de poder
   escribirlo) y `KNOWN_LIMITATION` (existe, funciona, tiene un límite
   conocido). Un capítulo puede llevar más de uno.
3. **Los tres pilotos se integran adentro de los 17 capítulos**, no al
   costado. Donde un capítulo tiene contenido ejecutable en los tres, el
   índice lo dice explícitamente en el campo *piloto relacionado*.
4. **Este índice no resuelve D-1, D-2, D-3 ni D-4.** Los cuatro siguen
   abiertos (`MANUAL_SCOPE.md` §6) y varios capítulos de abajo dependen de
   ellos. Se marca la dependencia; no se elige por nadie.
5. **`docs/runbooks/` no se reescribe** (regla N-6). Cada capítulo cita el
   archivo fuente exacto del que parte.

---

## 1. Los tres pilotos, y qué aportan a CADA capítulo (no solo a los "suyos")

```
YPF   (CIK 0000904851, SEC, IFRS+srt, 7 gates)   → aprendizaje completo SEC
KO    (CIK 0000021344, SEC, us-gaap puro)        → generalización SEC/US-GAAP — SIN golden run: hay que correrlo (C-3)
METR  (CUIT 30657863676, CNV, EEFF HTML)         → generalización de FUENTE — parcial, worktree para el tramo canónico
```

La integración no es "cada piloto tiene su capítulo": YPF y KO conviven
dentro de los capítulos 2 a 5, 8, 11, 14 (SEC); METR es el piloto de los
capítulos 9 (parcial), 10, 17. Los capítulos 12, 13, 15, 16 son mecanismo
puro y se ejercitan con cualquiera de los tres — el índice indica cuál usa
cada uno como ejemplo de referencia.

---

## 2. Índice de los 17 capítulos

### Cap. 0 · Cómo usar este manual *(prefacio — no es uno de los 17)*
- **Rótulo:** ninguno.
- **Objetivo:** orientar antes de tocar un comando: los dos pipelines, que
  no comparten etapas, y los dos hechos que parten el alcance en dos (la
  partición por worktree, y qué scripts de los 374 del repo **no** son
  parte del E2E).
- **Qué aprenderá el operador:** el mapa `SEC: S00→S04→ratios` /
  `CNV: 3 tramos`; los ~12 entry points oficiales vs. el resto; los
  scripts peligrosos por nombre que no debe correr sin leer
  (`mut_f054_f055.py`, `reparse_universo.py`, `scripts/pipeline/fix_*.py`).
- **Comandos involucrados:** ninguno.
- **Verificaciones:** ninguna ejecutable — lectura obligatoria previa.
- **Piloto relacionado:** ninguno (los tres se presentan aquí por primera
  vez, en la tabla comparativa de la §1.2 de `MANUAL_SCOPE.md`).
- **Anexos relacionados:** ninguno.
- **Fuente:** `docs/runbooks/00_START_HERE.md` §1, §3, §5, §6;
  `MANUAL_SCOPE.md` §0, §1.2.

---

### Cap. 1 · Preparación del entorno — **`KNOWN_LIMITATION` + bloqueado por `C-1`**
- **Objetivo:** verificar (no crear) un entorno correcto antes de cada E2E.
- **Qué aprenderá el operador:** verificación de Docker, destino del
  engine, esquemas, producción intacta y huella de `screener.db`; variables
  de entorno; cómo aplicar migraciones.
- **Lo que este capítulo NO puede prometer todavía:** la instalación desde
  cero. `docker-compose.yml` no declara `catalaxia-engine-dev` (la base
  contra la que corre todo) y `requirements.txt` no cubre las dependencias
  del engine (`sqlalchemy`, `psycopg`, `lxml`, `requests`, `openpyxl`,
  `yfinance`, `pytest`). **`C-1`**: hasta que alguien corra una instalación
  limpia y anote qué hace falta, el capítulo no puede ser autosuficiente —
  se escribe con lo verificable (verificación de un entorno YA instalado) y
  el bloque de creación queda `DECISION_REQUIRED`.
- **Comandos involucrados:** verificación de Docker/Python; aplicación de
  migraciones; `python -c "from engine.config import load_settings; ..."`.
- **Verificaciones:** las 5 de `01_COMMON_OPERATIONS.md` §1 (Docker,
  destino, esquemas, producción intacta, huella de `screener.db`).
- **Piloto relacionado:** ninguno (precondición de los tres).
- **Anexos relacionados:** `DATABASE_REFERENCE.md`.
- **Fuente:** `docs/runbooks/00_START_HERE.md` §2, §4;
  `01_COMMON_OPERATIONS.md` §1-§3. Gap: `MANUAL_SCOPE.md` `C-1`.

---

### Cap. 2 · Identidad — **ejecutable**
- **Objetivo:** sembrar y resolver identidad de emisores en `identity_v1`
  antes de que cualquier etapa posterior pueda inventar una entidad.
- **Qué aprenderá el operador:** qué hace S01; que `C-S01-004` está clavado
  a YPF (verifica explícitamente que esa entidad exista) — y qué implica
  eso al correr S01 sobre una base donde KO todavía no fue sembrado.
- **Comandos involucrados:** `s01_identity.py` (sin argumentos).
- **Verificaciones:** `C-S01-001..004`; idempotencia (`identifiers
  nuevos=0` en la segunda corrida).
- **Piloto relacionado:** **YPF** (caso verificado por `C-S01-004`); **KO**
  hereda la misma identidad sembrada — no requiere una segunda corrida de
  S01, pero el capítulo debe decirlo explícitamente, no darlo por sabido.
- **Anexos relacionados:** `ERROR_CATALOG.md` §S01; `CHECKPOINT_CATALOG.md`.
- **Fuente:** `docs/runbooks/02_SEC_EDGAR_E2E_RUNBOOK.md` (S01).

---

### Cap. 3 · SEC / EDGAR — descubrimiento, descarga, verificación SHA — **ejecutable**
- **Objetivo:** traer de EDGAR los artefactos de un emisor con registro
  íntegro por descarga.
- **Qué aprenderá el operador:** los argumentos reales de S02 (`--cik`,
  `--forms`, `--max-filings`); el fallback automático (3 reintentos,
  backoff 2/5/10s, solo en 429/500/502/503/504); la cortesía obligatoria
  con SEC (`C-S02-004`); cómo leer `fetch_raw.download_log`; para un
  emisor con ADR (YPF), el anexo de tres objetos (emisor / instrumento /
  datos de mercado) **antes** de calcular nada.
- **Comandos involucrados:** `s02_fetch_ypf.py --cik <cik>`.
- **Verificaciones:** `C-S02-001..005`; `rows_failed = 0`; idempotencia por
  conjunto `(accession_number, sha256)`.
- **Piloto relacionado:** **YPF** (recorrido completo, incluido el anexo
  ADR) → **KO** (mismo comando, `--cik 0000021344`; **requiere haber
  ejecutado C-3** — ver Cap. 8 y la nota de la Parte III original). KO no
  tiene ADR: es el contraste que prueba que el anexo aplica condicionalmente,
  no siempre.
- **Anexos relacionados:** `02A_SEC_EDGAR_ADR_ANNEX.md` completo;
  `ERROR_CATALOG.md` §S02; `RECOVERY_PROCEDURES.md` casos 8-10, 19.
- **Fuente:** `docs/runbooks/02_SEC_EDGAR_E2E_RUNBOOK.md` (S02);
  `02A_SEC_EDGAR_ADR_ANNEX.md` completo (407 + líneas del anexo).

---

### Cap. 4 · S00 → S04 — el núcleo, gate por etapa — **ejecutable**
- **Objetivo:** el capítulo más largo y más importante: bootstrap, parseo
  con checkpoint real, y el orden `S00→S01→S02→S03→S04` como cadena que se
  corta si la etapa anterior no dio `PASS`.
- **Qué aprenderá el operador:** S00 (migraciones + guard de producción,
  sin argumentos); S03 (`hash_out` `hashout-v2`, el único checkpoint real
  del sistema, sensible al contenido e insensible al orden); a demostrar
  idempotencia con sus propias manos, no a leerlo como afirmación.
- **Comandos involucrados:** `s00_smoke.py`; `s03_parse_ypf.py --cik <cik>
  --min-xbrl <n>`.
- **Verificaciones:** `C-S00-001/002`; `C-S03-001..009` (009 no
  bloqueante); segunda corrida de S03 con el mismo `hash_out` y checkpoint
  reutilizado.
- **Piloto relacionado:** **YPF** — el caso que prueba que la idempotencia
  funciona, con su procedimiento de verificación ya escrito
  (`appendices/GOLDEN_RUNS.md` §1). **KO** repite exactamente este
  procedimiento cambiando `--cik`: es la primera vez que el pipeline SEC se
  ejercita fuera de su golden case, y este capítulo debe registrar si algo
  se rompe al hacerlo (**C-3**).
- **Anexos relacionados:** `CHECKPOINT_CATALOG.md` §1; `ERROR_CATALOG.md`
  (`C-S03-002`, `C-S03-006`, `ENG-TIMEOUT-001`); `GOLDEN_RUNS.md` §1.
- **Fuente:** `docs/runbooks/02_SEC_EDGAR_E2E_RUNBOOK.md` (S00, S03,
  "Orden de ejecución").

---

### Cap. 5 · Normalización — **ejecutable**
- **Objetivo:** llevar `parsed.facts` a `derived.fact` resolviendo unidad,
  desempate y pertenencia — con `--dry-run` primero, siempre.
- **Qué aprenderá el operador:** por qué la primera corrida es siempre
  `--dry-run`; que ver `SKIP` en `C-S04-005..009` en ese modo es lo
  esperado; a verificar con un digest que una segunda corrida no duplica
  hechos vigentes.
- **Comandos involucrados:** `s04_normalize.py --dry-run`,
  `s04_normalize.py`.
- **Verificaciones:** `C-S04-001` (recalcula el `hash_out` de S03 e
  iguala); `C-S04-002` (ningún CIK con hechos de más de una corrida);
  `C-S04-004` (todo CIK resuelve a una entidad); digest de `derived.fact`
  idéntico antes/después.
- **Piloto relacionado:** **YPF**, repetido para **KO** (mismo
  procedimiento, `--cik` distinto).
- **Anexos relacionados:** `ERROR_CATALOG.md` (`C-S04-001/002/004`);
  `RECOVERY_PROCEDURES.md` caso 18.
- **Fuente:** `docs/runbooks/02_SEC_EDGAR_E2E_RUNBOOK.md` (S04).

---

### Cap. 6 · Economic Facts — **`NOT_IMPLEMENTED` en el repo principal + `DECISION_REQUIRED` (D-1)**
- **Objetivo:** documentar el concepto de `econ_key` (el hecho económico,
  independiente del documento que lo declaró) y su procedimiento — con la
  salvedad de que el mecanismo vive en la migración `036_economic_identity`,
  **solo en el worktree** `catalaxia-cnvmig`.
- **Qué aprenderá el operador:** la diferencia entre `fact_key` (la
  ocurrencia, sí disponible en el repo principal) y `econ_key` (el hecho
  económico, no); que varias ocurrencias pueden compartir `econ_key` sin
  ser un duplicado; que `econ_key` es NULL para SEC en el ciclo actual —
  alcance, no omisión.
- **Comandos involucrados:** **ninguno ejecutable desde el repo
  principal.** Referencia únicamente, contingente a D-1.
- **Verificaciones:** N/A hasta D-1.
- **Piloto relacionado:** **METR** es el único con `econ_key` poblado (vía
  el adaptador del worktree) — el ejemplo, si D-1 habilita documentarlo, es
  necesariamente CNV, no SEC.
- **Anexos relacionados:** ninguno nuevo.
- **Fuente:** `docs/runbooks/06_PROVENANCE.md` §4 (lo que sí se puede decir
  desde el repo principal); `MANUAL_SCOPE.md` §0, §1.1 fila 6, `C-2`, `D-1`.

---

### Cap. 7 · Financial Model — **`NOT_IMPLEMENTED` en el repo principal + `DECISION_REQUIRED` (D-1) + `KNOWN_LIMITATION` (L-11, L-12)**
- **Objetivo:** documentar la frontera arquitectónica *Source Adapter →
  Canonical Model → **Financial Model** → Ratio Engine*, con la salvedad de
  que el Financial Model **no está persistido** (se arma en memoria) y el
  script que lo implementa (`d2_metr5y_model.py`) vive solo en el worktree.
- **Qué aprenderá el operador:** que `ratio_engine.py`, pese a la
  arquitectura declarada, **sigue siendo SEC-first** (toma `--cik` e itera
  `ciks_del_universo()`) — es una contradicción medida, no una opinión
  (`ARQ-03` del inventario), y el operador debe saber que el Ratio Engine
  no consume hoy lo que la arquitectura dice que debería consumir.
- **Comandos involucrados:** **ninguno ejecutable desde el repo
  principal.**
- **Verificaciones:** N/A hasta D-1. Si se documenta "en rama": comparar
  `ratio_engine.py` contra `d2_metr5y_model.py` explícitamente.
- **Piloto relacionado:** **METR** (el Financial Model se construyó y
  probó ahí, en el worktree).
- **Anexos relacionados:** ninguno nuevo.
- **Fuente:** `MANUAL_SCOPE.md` §1.1 fila 7, `C-2`, `D-1`, `L-11`, `L-12`;
  `docs/manual/MANUAL_KNOWLEDGE_INVENTORY.md` §5 (`ARQ-03`).

---

### Cap. 8 · Ratios — **ejecutable**
- **Objetivo:** calcular y persistir ratios, entendiendo con precisión qué
  persiste el pipeline y qué no.
- **Qué aprenderá el operador:** que `derived.ratio` solo tiene **cuatro**
  `canonical_id` (`eps`, `pe`, `pb`, `ev_sales`); que los 14 ratios
  contables de `ratio_defs.py` **no se persisten** — los consume solo
  `matriz_producto.py`, un script de análisis, no una etapa del pipeline;
  cómo se elige el tag de cada concepto (`ratio_defs.CONCEPTOS`, lista
  ordenada, el primero presente gana y queda en la provenance); la
  salvedad de perímetro no idéntico entre `Borrowings` (IFRS) y
  `LongTermDebt` (US-GAAP), declarada por el propio código; los ratios que
  la CNV publica ella misma (prefijo `CNV_`) como control cruzado, nunca
  como sustituto.
- **Comandos involucrados:** `ratio_engine.py --cik <cik>` (sin persistir),
  luego `--persist`.
- **Verificaciones:** estado por `(cik, canonical_id)`
  (`CALCULADO`/`NOT_CALCULABLE`); comparación contra `CNV_*` para METR.
- **Piloto relacionado:** **los tres, lado a lado** — es el capítulo donde
  se ve si la elección de tag generaliza de verdad: YPF (ifrs-full) vs. KO
  (us-gaap puro) vs. METR (códigos CNV, sin XBRL). Incluye la regla del
  precio para valuación (YPF con ADR, KO sin ADR — el contraste directo del
  Cap. 3) y la regla de FX MEP.
- **Anexos relacionados:** `02A_SEC_EDGAR_ADR_ANNEX.md` §4;
  `FALLBACK_MATRIX.md`.
- **Fuente:** `docs/runbooks/05_RATIO_REFERENCE.md` completo (153 líneas).

---

### Cap. 9 · Market — **`KNOWN_LIMITATION` (L-5, L-3 parcial)**
- **Objetivo:** instalar el esquema de mercado en el orden correcto,
  descargar precios, y entender el límite estructural que hoy bloquea la
  valuación generalizada.
- **Qué aprenderá el operador:** los dos mecanismos de instalación y la
  trampa de orden documentada (F-051: las migraciones de `market/` se
  saltan en silencio si corren antes del schema); **`market_instruments
  .entity_id` es un entero legacy**, no el `entity_id` namespaced del
  engine — dos espacios de identificadores sin tabla puente (`L-5`),
  causa estructural de que `derived.ratio` tenga 36 filas / 9 emisores
  sobre 584 instrumentos.
- **Comandos involucrados:** `m19_apply_schema.py`, `s00_smoke.py`,
  `m2_fetch_engine.py --limit --instruments`, `m4_quality.py`,
  `m5_golden_case.py`.
- **Verificaciones:** las tres migraciones de `market/` presentes en
  `engine.schema_migrations`; conteo de instrumentos namespaced (`entity_id
  ~ '^(CIK|CUIT|LEI):'`) — hoy, prácticamente ninguno.
- **Piloto relacionado:** **YPF** (ADR + local) y **KO** (US simple) tienen
  precio disponible pero con el mismo límite de enlace; **METR** no tiene
  instrumento resuelto en absoluto.
- **Anexos relacionados:** `FALLBACK_MATRIX.md`.
- **Fuente:** `docs/runbooks/04_MARKET_DATA_E2E.md` completo (117 líneas);
  `MANUAL_SCOPE.md` `L-5`, `C-6` (9 de 11 scripts de `scripts/market/` sin
  documentar).

---

### Cap. 10 · CNV — **`PARCIAL`: tramos A y B ejecutables; tramo C `DECISION_REQUIRED` (D-1)**
- **Objetivo:** operar los tres tramos que sí existen, con sus límites
  reales — y ser explícito en que **no existe hoy un E2E de CNV de punta a
  punta desde el repo principal**.
- **Qué aprenderá el operador:** el mapa de los tres tramos (A
  instrumentado con gates pero sin EEFF; B legacy, el que produjo todos
  los datos, sin gate ni ledger; C canónico, en worktree); `--cuit` vs.
  `--cik` (exactamente uno); por qué `C-C3-008` (doble hash) nunca se
  ejercita (`hash_cnv` NULL en el 100% de las filas — verificarlo, no
  creerlo); los dos caminos de descarte silencioso y permanente del
  extractor legacy; que el tramo B **modifica `data/screener.db`** y hay
  que anotar su huella antes/después.
- **Comandos involucrados:** `c3_cnv_fetch.py --cuit 30657863676` (Tramo
  A); `job5_v2_extract_eeff.py`, `s0_normalizar_cnv.py` (Tramo B);
  referencia de `c4_cnv_adapter.py --persist` (Tramo C, no ejecutable hoy).
- **Verificaciones:** `C-C3-001..010` (Tramo A); reconciliación manual de
  cobertura whitelist↔disco↔DONE↔con-filas (Tramo B, sin gate
  estructurado).
- **Piloto relacionado:** **METR** — único piloto de este capítulo.
- **Anexos relacionados:** `ERROR_CATALOG.md` §C3, `CNV-EX-001/002`;
  `CHECKPOINT_CATALOG.md`.
- **Fuente:** `docs/runbooks/03_CNV_E2E_RUNBOOK.md` completo (315 líneas);
  `MANUAL_SCOPE.md` §1.1 fila 10, `L-6`, `L-7`, `L-9`, `L-10`.

---

### Cap. 11 · Provenance — **ejecutable**
- **Objetivo:** recorrer `RESULTADO → FÓRMULA → INSUMO → FACT → CONCEPTO →
  CONTEXTO → DOCUMENTO → RAW → SHA256` hacia atrás, para SEC y para CNV.
- **Qué aprenderá el operador:** la tabla de 9 eslabones con su clave
  exacta; las dos consultas encadenadas y la verificación final con
  `sha256sum`; para CNV, los dos campos no opcionales
  (`measurement_date` bajo IAS 29, y el perímetro
  `CONSOLIDADO`/`INDIVIDUAL` codificado en `context_id`); `fact_key`
  (la ocurrencia) vs. `econ_key` (el hecho económico, Cap. 6) y su
  serialización canónica normativa; qué NO tiene provenance hoy (mapa
  honesto, incluye Market por `L-5`).
- **Comandos involucrados:** las consultas SQL de `06_PROVENANCE.md` §2-§3;
  `sha256sum`; el script de reconstrucción de `fact_key` a mano (§5).
- **Verificaciones:** el hash reconstruido coincide con el almacenado;
  reproducir una fila de `METR_FY2024_PROVENANCE.csv` a mano.
- **Piloto relacionado:** **YPF/KO** para el recorrido SEC; **METR** para
  el recorrido CNV — el capítulo que ya está más completo de lo que
  parecía (`06_PROVENANCE.md` trae los dos caminos, no hay que inventar
  nada, solo integrar).
- **Anexos relacionados:** `DATABASE_REFERENCE.md`.
- **Fuente:** `docs/runbooks/06_PROVENANCE.md` completo (132 líneas).

---

### Cap. 12 · Validación — **ejecutable**
- **Objetivo:** que el operador sepa leer un gate y decidir si avanza, sin
  interpretación.
- **Qué aprenderá el operador:** cómo leer `PASS`/`WARNING`/`BLOCK`; los
  criterios de una etapa certificada (gate `PASS`, `report` válido,
  `expected == parsed + rejected`, `checks` no vacío — "terminó sin
  excepción nunca es `PASS`").
- **Comandos involucrados:** consulta agregada a `engine.stage_runs` por
  `run_id`.
- **Verificaciones:** las 4 condiciones de etapa certificada, aplicadas a
  cualquier `run_id`.
- **Piloto relacionado:** transversal — mecanismo único, usado en los tres.
- **Anexos relacionados:** `LOG_CATALOG.md`.
- **Fuente:** `docs/runbooks/01_COMMON_OPERATIONS.md` §5;
  `07_CERTIFICATION.md` §2.

---

### Cap. 13 · Gates — **ejecutable, con `KNOWN_LIMITATION` (`L-4`)**
- **Objetivo:** los criterios de gate por etapa y de corrida completa, y la
  limitación de que no hay un gate agregado con exit code.
- **Qué aprenderá el operador:** que el gate se lee a ojo en la consola,
  etapa por etapa — no hay script único que lo agregue (**`GAT-02`/`L-4`**,
  también citado como `FAL-06` en el inventario); los criterios de
  `appendices/GOLDEN_RUNS.md` como referencia de qué esperar.
- **Comandos involucrados:** las consultas de gate por etapa, repetidas
  manualmente.
- **Verificaciones:** todas las etapas en `PASS` para una corrida
  completa.
- **Piloto relacionado:** transversal.
- **Anexos relacionados:** `GOLDEN_RUNS.md`.
- **Fuente:** `docs/runbooks/07_CERTIFICATION.md` §2-§3; `MANUAL_SCOPE.md`
  `L-4`.

---

### Cap. 14 · Idempotencia — **ejecutable para SEC; CNV depende del worktree**
- **Objetivo:** demostrar, no afirmar, que una segunda corrida no duplica
  ni contamina.
- **Qué aprenderá el operador:** el procedimiento de S03 (`hash_out`
  idéntico + checkpoint reutilizado) como la prueba fuerte del sistema;
  para CNV, que la idempotencia está demostrada para el adaptador del
  worktree (0 insertados / 4.648 reusados, mismo digest) y para el demo
  METR, pero que para `job5` (Tramo B) la matriz solo dice "alta" **sin
  procedimiento escrito** (**`C-5`**).
- **Comandos involucrados:** re-correr S03; el digest de `derived.fact`
  post-S04.
- **Verificaciones:** mismo `hash_out`; mismo digest; 0 filas nuevas
  vigentes.
- **Piloto relacionado:** **YPF** (demostrado) → **KO** (a repetir, parte
  de C-3) para SEC; **METR** solo hasta donde el worktree lo permite.
- **Anexos relacionados:** `CHECKPOINT_CATALOG.md`.
- **Fuente:** `docs/runbooks/appendices/GOLDEN_RUNS.md` §1;
  `02_SEC_EDGAR_E2E_RUNBOOK.md` (S03, S04); `MANUAL_SCOPE.md` `C-5`.

---

### Cap. 15 · Troubleshooting — **`PARCIAL`: catálogo sí, árbol de diagnóstico por escribir**
- **Objetivo:** dar respuesta operativa a incidentes reales, y un
  procedimiento reproducible para "¿por qué este documento no tiene
  datos?".
- **Qué aprenderá el operador:** los códigos de error con y sin código en
  el software; las cinco reglas que un fallback no puede romper; los 20
  casos de recuperación; el caso obligatorio completo — documento CNV
  #3277363, METR 30/09/2024 CONSOLIDADO, con sus 10 preguntas respondidas
  (9 de 10: la validez del SHA no es determinable, `L-6`) — como
  **calibración** antes de generalizar el árbol a cualquier documento.
- **Comandos involucrados:** el script de diagnóstico completo de
  `GOLDEN_RUNS.md` §3; su generalización parametrizada por GUID/CUIT (a
  escribir).
- **Verificaciones:** reproducir exactamente la salida documentada del
  caso METR antes de confiar en la generalización para un caso nuevo.
- **Piloto relacionado:** **METR** — único con el caso de diagnóstico
  completo; el árbol generalizado queda disponible para cualquier emisor
  CNV futuro.
- **Anexos relacionados:** `ERROR_CATALOG.md`, `FALLBACK_MATRIX.md`,
  `RECOVERY_PROCEDURES.md` completos.
- **Fuente:** `docs/runbooks/03_CNV_E2E_RUNBOOK.md` ("Diagnóstico documento
  por documento"); `appendices/GOLDEN_RUNS.md` §3; los tres apéndices
  completos. Gap: `MANUAL_SCOPE.md` §1.1 fila 15 ("hay que escribirlo").

---

### Cap. 16 · Certificación — **ejecutable**
- **Objetivo:** la máquina de estados real y los criterios completos de
  certificación de una corrida.
- **Qué aprenderá el operador:** la cadena real de `engine/states.py`; qué
  estados pedidos **no existen** (`QUARANTINED`, `RECOVERED` — `L-2`); los
  6 criterios de corrida completa; qué evidencia mínima archivar; qué NO
  habilita a certificar.
- **Comandos involucrados:** ninguno nuevo — síntesis de los Caps. 4, 5,
  11, 12, 13, 14.
- **Verificaciones:** las 6 de `07_CERTIFICATION.md` §3, aplicadas a YPF
  (completo hoy), KO (una vez cumplido C-3) y METR (con la salvedad de
  origen worktree explícita, `07_CERTIFICATION.md` §5).
- **Piloto relacionado:** **los tres**, en una tabla comparativa final.
- **Anexos relacionados:** `GOLDEN_RUNS.md` completo.
- **Fuente:** `docs/runbooks/07_CERTIFICATION.md` completo (111 líneas).

---

### Cap. 17 · Homologación TIKR — **`NOT_IMPLEMENTED` en el repo principal**
- **Objetivo:** documentar el método y los criterios de homologación
  externa contra TIKR — con la salvedad de que el procedimiento
  (`h1_tikr_metr_homologacion.py`) vive solo en el worktree.
- **Qué aprenderá el operador:** que TIKR es **benchmark secundario**, no
  autoridad primaria; el set de estados de homologación **implementado**
  (`DIFFERENT_DEFINITION`, `PERIOD_MISMATCH`, `CURRENCY_MISMATCH`,
  `UNIT_MISMATCH`, `PERIMETER_MISMATCH`, `SOURCE_MISMATCH`, `TIKR_ONLY`,
  `CATALAXIA_ONLY`, `CATALAXIA_MISSING`, `TIKR_MISSING`, `ANOMALY`,
  `UNRESOLVED` — 12 estados) contra el que pedía un encargo anterior
  (`METHODOLOGY_DIFFERENCE`, `DATE_DIFFERENCE` — no implementados,
  **`D-4`** sin resolver); la diferencia MEP vs. mayorista entre Catalaxia
  y TIKR, medida (0,0-0,3% en general, 85% de brecha en 2021) y **no** un
  error.
- **Comandos involucrados:** **ninguno ejecutable desde el repo
  principal.**
- **Verificaciones:** N/A hasta que se resuelva D-1. Si se documenta "en
  rama": las 327 comparaciones ya hechas para METR como caso de
  referencia.
- **Piloto relacionado:** **METR** — único piloto con homologación externa
  (327 comparaciones).
- **Anexos relacionados:** ninguno nuevo.
- **Fuente:** `MANUAL_SCOPE.md` §1.1 fila 17, `C-4`, `D-4`;
  `docs/manual/MANUAL_KNOWLEDGE_INVENTORY.md` §5 (`TIKR-03`), §2 (`DEC-04`).

---

## 3. Apéndices de referencia (consulta, no lectura lineal)

No son parte de los 17 obligatorios, pero `MANUAL_SCOPE.md` §1.3 los incluye
como transversal y la regla N-6 prohíbe reescribirlos. El manual los cita,
no los duplica.

| apéndice | qué cubre | capítulos que lo citan |
|---|---|---|
| `COMMAND_REFERENCE.md` | catálogo de comandos, argumentos contra `argparse` | 0, 1, todos los ejecutables. Gap: `CMD-02`, `CMD-03` |
| `DATABASE_REFERENCE.md` | los dos PostgreSQL, SQLite, esquemas, tablas `market_*`, consultas de diagnóstico | 1, 9, 11. Gap: `OPS-01`/`FAL-07` (8 bases en 5433, documentadas 2) |
| `CHECKPOINT_CATALOG.md` | el único checkpoint real (S03); los demás son aparentes o no existen | 4, 14 |
| `ERROR_CATALOG.md` | 9 códigos con check en el código + etiquetas de runbook | 2, 3, 4, 5, 10, 15. Gap: `L-14` (9 códigos para 374 scripts) |
| `FALLBACK_MATRIX.md` | qué fallback existe de verdad y las 5 reglas que no puede romper | 3, 8, 9, 15 |
| `RECOVERY_PROCEDURES.md` | 20 casos de incidente real | 15 |
| `LOG_CATALOG.md` | dónde se registra qué; los 3 huecos que importan | 12 |
| `GOLDEN_RUNS.md` | casos de referencia YPF (completo) y METR (parcial + demo); **KO por agregar** | 4, 13, 14, 16 |

---

## 4. Mapa de decisiones, certificaciones y limitaciones → capítulo

Trazabilidad completa contra `MANUAL_SCOPE.md` §4-§6, para que nada quede
sin capítulo asignado.

### Decisiones (`D-1`…`D-4`) — ninguna se resuelve en este índice

| id | decisión | capítulos afectados |
|---|---|---|
| **D-1** | ¿repo principal, worktree, o los dos? | **6, 7, 10 (tramo C), 17** — los cuatro quedan `NOT_IMPLEMENTED` en la opción (a); documentables "en rama" en la (b) |
| **D-2** | ¿el manual absorbe `docs/runbooks/` o lo envuelve? | estructural — afecta si este índice termina siendo el único documento o una capa sobre los 9+8 existentes. **No se decide acá** (ver §5 de este documento) |
| **D-3** | ¿KO se certifica o se cambia de piloto? | **2, 3, 4, 5, 8, 11, 14, 16** — todos los que incluyen a KO como segundo piloto SEC |
| **D-4** | ¿set de homologación del encargo o el implementado? | **17** |

### Certificaciones pendientes (`C-1`…`C-6`) — precondición de escritura

| id | qué | capítulo |
|---|---|---|
| **C-1** | creación del entorno desde cero | **1** |
| **C-2** | Economic Facts / Financial Model | **6, 7** |
| **C-3** | correr y certificar KO | **2, 3, 4, 5, 8, 11, 14, 16** (excepción autorizada a la regla general de no ejecutar pilotos) |
| **C-4** | Tramo C de CNV / homologación TIKR | **10 (tramo C), 17** |
| **C-5** | idempotencia de `job5` (Tramo B) | **14** |
| **C-6** | E2E de Market, 9 scripts sin documentar | **9** |

### Limitaciones conocidas (`L-1`…`L-16`) — se documentan, no se arreglan

| id | dónde aparece primero | capítulo |
|---|---|---|
| L-1 (sin `--resume`) | cualquier etapa interrumpida | 4, 5, 15 |
| L-2 (`QUARANTINED` no existe) | vocabulario de estados | 16 |
| L-3 (sin rollback) | fuera de Market | 15 |
| L-4 (sin gate agregado) | lectura manual del gate | 13 |
| L-5 (enlace instrumento↔entidad roto) | valuación | 9, 11 |
| L-6 (`job5` sin ledger/SHA, descarta en silencio) | extracción CNV | 10, 15 |
| L-7 (CNV oficial no baja EEFF) | Tramo A | 10 |
| L-8 (CNV no publica CapEx) | FCF, 7 ratios caen | 8, 10 |
| L-9 (226/286 documentos METR son cáscaras) | diagnóstico | 10, 15 |
| L-10 (perímetro no computable desde el formulario) | identidad económica | 6, 11 |
| L-11 (Financial Model no persistido) | arquitectura | 7 |
| L-12 (`ratio_engine.py` SEC-first) | contradicción arquitectónica | 7, 8 |
| L-13 (serie ARS no comparable sin deflactar, IAS 29) | ratios multianuales | 8 |
| L-14 (9 códigos de error para 374 scripts) | cobertura del catálogo | apéndice `ERROR_CATALOG.md` |
| L-15 (5 tests en rojo) | estado del repo | 0 (mención), no un capítulo propio |
| L-16 (9 de 7.998 entidades con hechos) | alcance real del universo | 0, 8 |

---

## 5. Lo que este índice deja explícitamente sin resolver

No corresponde decidirlo al diseñar un índice — son las mismas cuatro
decisiones que `MANUAL_SCOPE.md` §6 ya identificó, ahora con su impacto en
la estructura de capítulos hecho explícito arriba:

1. **D-2 en particular condiciona la forma física de este manual.** Si se
   decide "absorber", los 17 capítulos de arriba son el contenido final y
   `docs/runbooks/` se retira. Si se decide "envolver", los 17 capítulos son
   una capa de navegación e integración (con los tres pilotos tejidos
   adentro) sobre los 9+8 documentos existentes, que se mantienen intactos.
   **Este índice está escrito de forma que sirve para las dos** — cada
   capítulo cita su fuente exacta, lo cual funciona tanto si esa fuente se
   fusiona adentro como si queda referenciada.
2. **C-3 (KO) es la única excepción autorizada a "no ejecutar pilotos como
   parte de este trabajo" (N-9).** Afecta a 8 de los 17 capítulos. Conviene
   resolverla antes de escribir cualquiera de ellos, no capítulo por
   capítulo.
3. **Los cuatro capítulos partidos por el worktree (6, 7, 10-C, 17)
   representan 4 de 17 — menos de un cuarto, pero incluyen piezas
   centrales de la arquitectura declarada** (Financial Model) y del
   diferencial competitivo (homologación TIKR). Publicar el manual sin
   ellos, aunque sea con los rótulos correctos, es una decisión de
   producto, no solo de documentación.

---

## 6. Correspondencia capítulo → Parte del manual

La serie `MANUAL_PART_*.md` está escrita completa (**Partes I–XVIII**). Este
índice es la columna vertebral; cada Parte es la redacción de su capítulo o
grupo de capítulos. Mapa:

| capítulo del alcance | Parte | archivo | rótulo |
|---|---|---|---|
| Cap. 0 (prefacio) | I | `MANUAL_PART_I.md` | — |
| Cap. 1 · Preparación del entorno | II | `MANUAL_PART_II.md` | `KNOWN_LIMITATION` + C-1 |
| Caps. 2–5 · Identidad / SEC / S00–S04 / Normalización | III, IV, V | `MANUAL_PART_III/IV/V.md` | ejecutable |
| Caps. 6–7 · Economic Facts / Financial Model | VI | `MANUAL_PART_VI.md` | `NOT_IMPLEMENTED` + D-1 |
| Cap. 8 · Ratios | VII | `MANUAL_PART_VII.md` | ejecutable |
| Cap. 9 · Market | VIII | `MANUAL_PART_VIII.md` | `KNOWN_LIMITATION` (L-5) |
| Cap. 10 · CNV | IX | `MANUAL_PART_IX.md` | `PARCIAL` + D-1 (tramo C) |
| Cap. 11 · Provenance | X | `MANUAL_PART_X.md` | ejecutable |
| Cap. 14 · Idempotencia | XI | `MANUAL_PART_XI.md` | ejecutable (SEC); C-5 (CNV) |
| Cap. 12 · Validación | XII | `MANUAL_PART_XII.md` | ejecutable |
| Caps. 16 (+13 gates) · Certificación | XIII | `MANUAL_PART_XIII.md` | ejecutable (L-4) |
| Cap. 17 · Homologación TIKR | XIV | `MANUAL_PART_XIV.md` | `NOT_IMPLEMENTED` + D-4 |
| Cap. 15 · Troubleshooting | XV | `MANUAL_PART_XV.md` | `PARCIAL`: catálogo sí, árbol por escribir |
| Apéndice Golden Runs | XVI | `MANUAL_PART_XVI.md` | ejecutable |
| Síntesis · Estado real | XVII | `MANUAL_PART_XVII.md` | medición |
| Cierre · Qué falta | XVIII | `MANUAL_PART_XVIII.md` | decisiones + gaps |

> **Nota de vigencia (2026-09-04).** Este índice se escribió como Paso 3 de la
> secuencia, antes de las Partes. Los rótulos de arriba son los que cada Parte
> declara en su cabecera; si un rótulo del índice difiere de la cabecera de la
> Parte, manda la Parte (fue escrita sobre más evidencia). La Parte XVII es el
> estado real a esa fecha; la XVIII el cierre en abierto.
