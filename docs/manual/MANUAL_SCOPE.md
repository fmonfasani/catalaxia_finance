# MANUAL_SCOPE — alcance de `CATALAXIA_OPERATIONS_MANUAL.md`

**Paso 2. No es el manual, no corrige código, no resuelve gaps.**
Define qué entra, qué no, qué se documenta, qué queda como `KNOWN_LIMITATION` y
qué necesita certificarse **antes** de poder escribirse como procedimiento.

Todo lo que sigue se verificó contra el repositorio y contra la base. La regla
que gobierna el alcance es una: **un procedimiento sólo se documenta como
procedimiento si alguien lo puede ejecutar hoy y verificar el resultado.** Lo
demás entra al manual, pero rotulado.

---

## 0 · El hecho que parte el alcance en dos

El repositorio principal llega a la **migración 033**. El worktree
`catalaxia-cnvmig`, rama `feat/cnv-canonical`, tiene tres más:

| migración | qué agrega | dónde vive |
|---|---|---|
| `034_cnv_canonical_entity_id` | `entity_id` para fuentes no-SEC | **sólo worktree** |
| `035_measurement_date` | fecha de medición (IAS 29) | **sólo worktree** |
| `036_economic_identity` | **`econ_key`** | **sólo worktree** |

Y con ellas, cinco scripts:

| script | repo principal | worktree |
|---|---|---|
| `s00_smoke` … `s04_normalize`, `ratio_engine`, `ratio_defs`, `c3_cnv_fetch` | **sí** | sí |
| `job5_v2_extract_eeff` (extracción CNV legacy) | **sí** | sí |
| `c4_cnv_adapter`, `c4_cnv_semantica` | **no** | sí |
| `d1_metr5y_market`, `d2_metr5y_model`, `d3_metr5y_provenance` | **no** | sí |
| `h1_tikr_metr_homologacion` | **no** | sí |

**Consecuencia directa:** de los 17 capítulos obligatorios, **4 no son
ejecutables desde el repositorio principal** — Economic Facts, Financial Model,
el tramo canónico de CNV y la homologación TIKR. No es una opinión sobre
prioridades: es que los archivos no están ahí.

Esto obliga a una decisión de alcance que **no tomo yo** (§6, D-1): el manual
documenta un sistema que hoy vive en dos ramas.

---

## 1 · Qué ENTRA

### 1.1 Los 17 capítulos obligatorios, con su estado real

| # | capítulo | fuente hoy | ejecutable | qué se documenta |
|---|---|---|---|---|
| 1 | Preparación del entorno | `00_START_HERE` §2, `01_COMMON_OPERATIONS` §1-3 | **parcial** | verificación de entorno, variables, migraciones. La **creación** del entorno queda bloqueada (§4, C-1) |
| 2 | Identidad | `02_SEC_EDGAR_E2E_RUNBOOK` §S01, `s01_identity.py` | **sí** | procedimiento completo con gate |
| 3 | SEC / EDGAR | `02_SEC_EDGAR_E2E_RUNBOOK` (407 líneas) + anexo ADR | **sí** | descubrimiento, descarga, verificación SHA |
| 4 | S00 → S04 | ídem, 5 secciones con gate por etapa | **sí** | el núcleo del manual |
| 5 | Normalización | `02_…` §S04, `s04_normalize.py --dry-run` | **sí** | incluido el modo dry-run y los checks C-S04-005..009 |
| 6 | **Economic Facts** | migración 036, worktree | **NO** | se documenta el concepto y el procedimiento **en rama**; ver C-2 |
| 7 | **Financial Model** | `d2_metr5y_model.py`, worktree | **NO** | ídem. Además **no está persistido**: hoy se arma en memoria |
| 8 | Ratios | `05_RATIO_REFERENCE` (153 líneas), `ratio_engine.py` | **sí** | catálogo, `NOT_CALCULABLE`, salvedades de unidad y período |
| 9 | Market | `04_MARKET_DATA_E2E` (117 líneas), `scripts/market/` | **parcial** | esquema, descarga, calidad. El enlace instrumento→entidad es `KNOWN_LIMITATION` |
| 10 | CNV | `03_CNV_E2E_RUNBOOK` (315 líneas), tres tramos | **parcial** | tramos A y B ejecutables; el C es del worktree |
| 11 | Provenance | `06_PROVENANCE` (132 líneas) — ya trae el recorrido inverso **para SEC y para CNV** | **sí** | la cadena tabla por tabla, las dos identidades, qué NO tiene provenance |
| 12 | Validación | `01_COMMON_OPERATIONS` §5, `07_CERTIFICATION` §2 | **sí** | cómo leer un gate, criterios por etapa |
| 13 | Gates | `07_CERTIFICATION` §2-3, `GOLDEN_RUNS` | **sí** | criterios por etapa y de corrida completa |
| 14 | Idempotencia | `GOLDEN_RUNS` §1 (S03 `hash_out`) | **sí** para SEC | para CNV, el procedimiento vive en el worktree |
| 15 | Troubleshooting | `ERROR_CATALOG` (9 códigos), `FALLBACK_MATRIX`, `RECOVERY_PROCEDURES` | **parcial** | el catálogo entra; el árbol de diagnóstico hay que **escribirlo** (§5) |
| 16 | Certificación | `07_CERTIFICATION` (111 líneas) | **sí** | máquina de estados real, con los estados que **no** existen declarados |
| 17 | **Homologación TIKR** | `h1_tikr_metr_homologacion.py`, worktree | **NO** | método y criterios sí; el procedimiento, en rama |

### 1.2 Los tres pilotos

| piloto | fuente / taxonomía | datos | golden run | entra como |
|---|---|---|---|---|
| **YPF** CIK `0000904851` | SEC / IFRS + `srt` | 47.930 hechos, 9 × 20-F | **sí, 7 gates** | **recorrido pedagógico completo** — es el único con todo verificado |
| **KO** CIK `0000021344` | SEC / us-gaap puro | 45.113 hechos, 17 × 10-K (2009-2025) | **NO** | **demostración de generalización** — pero ver C-3: hay que correrlo antes |
| **METR** CUIT `30657863676` | CNV / EEFF HTML | 4.648 hechos, 60 documentos | parcial (Tramo A) + demo 5Y completo | **cambio de fuente** — aporta NIL, escala variable, perímetro, USD MEP, Golden Run y homologación |

### 1.3 Lo transversal que entra

- El **guard de producción**: 5432 nunca se escribe, verificado.
- Las **8 bases de 5433** y para qué sirve cada una (hoy documentadas 2).
- El **catálogo de comandos** con argumentos verificados contra `argparse`.
- Las **decisiones arquitectónicas de CNV** con su evidencia: `econ_key` sin
  `value` ni `es_nil`; no inferir supersesión por ordinal; la CNV entra al
  registry como tercera taxonomía.
- La **regla de FX** (MEP de la última rueda ≤ cierre, para stocks y flujos) y
  por qué.
- La **regla de oro de auditoría**: nunca asumir que si el dato no está en la
  tabla entonces no ocurrió; primero determinar base, puerto, `run_id`, etapa y
  snapshot.

---

## 2 · Qué NO entra

| # | qué | por qué |
|---|---|---|
| N-1 | Corregir código, mergear el worktree, arreglar `docker-compose.yml` o `requirements.txt` | el encargo lo excluye explícitamente. Los gaps se **documentan**, no se resuelven |
| N-2 | Documentar los 374 scripts del repo | ~12 son entry points oficiales. El resto se menciona como "no clasificado" y se deja fuera |
| N-3 | Las 7 entidades SEC ingestadas sin documentar (Galicia, Macro, TGS, Central Puerto, Microsoft, NVIDIA, Apple) | se mencionan como evidencia de que el pipeline generaliza; no se documenta un recorrido para cada una |
| N-4 | Deployment: `catalaxia-api`, `catalaxia-nginx`, `catalaxia-pipeline` | el manual es de **operación del pipeline de datos**, no de despliegue del producto |
| N-5 | El screener y el dashboard | son consumidores del pipeline, no etapas |
| N-6 | Reescribir `docs/runbooks/` desde cero | 3.055 líneas ya verificadas. Ver D-2 |
| N-7 | Tutorial de XBRL, IFRS, US-GAAP o IAS 29 | teoría mínima y suficiente, referida al caso concreto, no un tratado |
| N-8 | Benchmarks distintos de TIKR | sólo hay uno y es de METR |
| N-9 | Ejecutar los pilotos como parte de este trabajo | escribir el manual no es correr el sistema. La excepción obligada es KO (C-3) |

---

## 3 · Qué se DOCUMENTARÁ, y en qué forma

Cada operación del manual lleva la misma ficha, sin excepción:

```
Objetivo
Prerrequisitos
Comando            ← literal, copiable, con el prefijo ENGINE_DB_NAME/PORT
Parámetros         ← verificados contra el argparse del script
Qué hace
Resultado esperado ← el valor concreto, no "debería funcionar"
Verificación       ← el comando o SQL que lo comprueba
Gate               ← PASS / WARNING / BLOCK, con su señal en consola
Si falla           ← código de error y qué hacer
```

Y tres rótulos, usados sólo donde corresponde y nunca para tapar:

| rótulo | cuándo |
|---|---|
| `NOT_IMPLEMENTED` | el procedimiento no existe en el software |
| `DECISION_REQUIRED` | hace falta una decisión humana antes de poder escribirlo |
| `KNOWN_LIMITATION` | existe, funciona, y tiene un límite conocido que el operador debe saber |

Además, para cada etapa, la sección **"qué ocurrió realmente"** que pediste:
usuario ejecuta → sistema hace → resultado → decisión → control. Es lo que
convierte el manual en algo que enseña y no sólo en algo que se copia.

---

## 4 · Qué necesita CERTIFICACIÓN antes de documentarse como procedimiento

Ésta es la lista corta y dura. **Nada de acá se puede escribir como
procedimiento hasta que alguien lo corra y verifique.**

| id | qué | por qué bloquea | qué haría falta |
|---|---|---|---|
| **C-1** | **Creación del entorno** | `docker-compose.yml` declara `catalaxia-db`, `catalaxia-pipeline`, `catalaxia-api` y `catalaxia-nginx`, pero **no `catalaxia-engine-dev`** — que es la base @5433 contra la que corren *todos* los comandos del runbook. Y `requirements.txt` tiene 3 líneas del servicio API, mientras el engine importa `sqlalchemy`, `psycopg`, `lxml`, `requests`, `openpyxl`, `yfinance` y `pytest` | correr una instalación desde cero en una máquina limpia y anotar qué hace falta. Sin esto el capítulo 1 **no puede** ser autosuficiente |
| **C-2** | **Economic Facts y Financial Model** (caps. 6 y 7) | migraciones 034/035/036 y `d2_metr5y_model.py` sólo existen en el worktree. Un operador que clone el repo principal no los tiene | decidir D-1, y si se documenta "en rama", certificar el procedimiento de checkout del worktree |
| **C-3** | **Piloto KO** | 45.113 hechos y 17 filings cargados, **cero golden run**. No hay resultado esperado, ni gate, ni evidencia de que el E2E se haya corrido | correr S00→S04 + ratios con `--cik 0000021344` y certificar los 7 gates, igual que YPF. Es un sprint |
| **C-4** | **Tramo C de CNV y homologación TIKR** (caps. 10 parcial, 17) | mismo motivo que C-2 | ídem |
| **C-5** | **Idempotencia de CNV** | está demostrada para el adapter del worktree (0 insertados / 4.648 reusados, mismo digest) y para el demo METR. Para `job5` la matriz dice "alta" sin procedimiento | escribir y correr el procedimiento de idempotencia de `job5` |
| **C-6** | **E2E de Market** | 9 de los 11 scripts de `scripts/market/` no están documentados; el runbook cubre esquema, descarga y calidad | correr el E2E de Market y anotar comandos y gates de los 9 restantes |

**Regla de escritura mientras no estén certificados:** el capítulo se escribe
igual, con el contexto y las decisiones, pero el bloque de procedimiento dice
`DECISION_REQUIRED` o `NOT_IMPLEMENTED` y **no inventa comandos**.

---

## 5 · Qué queda como `KNOWN_LIMITATION`

Cosas que funcionan, tienen un límite conocido, y el operador debe saberlas.
**Se documentan, no se arreglan.**

| id | limitación | impacto operativo |
|---|---|---|
| **L-1** | **No hay `--resume` en ningún script** | una corrida interrumpida se vuelve a correr entera |
| **L-2** | **No existe el estado `QUARANTINED`** (`SG-08`) | no hay dónde apartar un dato sospechoso; o entra o no entra |
| **L-3** | **No hay rollback documentado** | hay `market_snapshots` (577 filas) para Market y nada para SEC ni CNV |
| **L-4** | **No hay gate agregado con exit code** | el gate se lee a ojo en la consola, etapa por etapa |
| **L-5** | **Market: enlace instrumento → entidad roto** | la matriz de readiness lo marca `provenance ROTA`; 15 de 584 instrumentos enlazados. Bloquea valuación generalizada |
| **L-6** | **`job5` no deja ledger ni SHA256** y descarta documentos en silencio (`CNV-EX-001`) | es el camino que produjo **todos** los datos CNV existentes |
| **L-7** | **El camino CNV oficial no descarga estados financieros** | `c3_cnv_fetch.py` sólo baja páginas de visor y de empresa (`artifact_kind` ∈ {`VISOR`, `EMPRESA_PAGE`}) |
| **L-8** | **La CNV no publica CapEx** | el formulario da el flujo de efectivo en 3 renglones agregados. Sin CapEx no hay FCF: caen 7 ratios. El PDF adjunto está referenciado con GUID y hash, y **no se descarga** |
| **L-9** | **226 de 286 documentos de METR son cáscaras** | HTTP 200 ≠ documento financiero válido |
| **L-10** | **Perímetro y entidad informante no son computables** desde el formulario CNV | `TipoBalance` rotula igual consolidado y separado; en producción hay un caso que publica una filial colombiana como Longvie individual |
| **L-11** | **El Financial Model no está persistido** | se arma en memoria; no hay tabla que auditar |
| **L-12** | **`ratio_engine.py` es SEC-first** | toma `--cik` e itera `ciks_del_universo()`, aunque la arquitectura declara que debe consumir el Financial Model |
| **L-13** | **Serie multi-año en ARS no es comparable consigo misma** | IAS 29: cada ejercicio en el poder adquisitivo de su cierre. `valor_comparativo` existe en el esquema y está vacío en las 4.648 filas |
| **L-14** | **9 códigos de error para 374 scripts** | la cobertura del catálogo es mínima |
| **L-15** | **5 tests en rojo hoy** | 3 por drift de datos en `catalaxia` (lote M23: 601 filas contra 591) y 2 son guardas de sprints de auditoría que detectaron un cambio posterior legítimo en `ratio_defs.py` |
| **L-16** | **Sólo 9 de 7.998 entidades tienen hechos** | el límite del producto es la ingesta, no el cálculo |

---

## 6 · Decisiones requeridas antes de escribir

Cuatro. Ninguna es mía y las cuatro cambian el manual.

| id | decisión | opciones | consecuencia |
|---|---|---|---|
| **D-1** | **¿El manual documenta el repo principal, el worktree, o los dos?** | (a) sólo principal → caps. 6, 7, 17 y el tramo C de CNV quedan `NOT_IMPLEMENTED`; (b) los dos, con el checkout del worktree como paso documentado; (c) mergear primero — pero eso es corregir código, y está fuera de alcance | es **la** decisión de alcance |
| **D-2** | **¿El manual reemplaza `docs/runbooks/` o lo absorbe?** | (a) absorber: el manual es el único documento y los runbooks se retiran; (b) envolver: el manual referencia los runbooks — rompe la autosuficiencia que pediste | 3.055 líneas ya verificadas están en juego |
| **D-3** | **¿KO se certifica o se cambia de piloto?** | (a) correr el E2E de KO y certificarlo (un sprint); (b) usar otra de las 7 entidades ya ingestadas — mismo problema; (c) documentar KO como `DECISION_REQUIRED` sin resultados esperados — la Parte IV pierde su función | KO es obligatorio por encargo |
| **D-4** | **¿Cuál es el set canónico de estados de homologación?** | el del encargo (`METHODOLOGY_DIFFERENCE`, `DATE_DIFFERENCE`) o el implementado (12 estados, sin esos dos) | afecta el capítulo 17 y el CSV ya generado |

---

## 7 · Criterio de aceptación del manual

El manual está terminado cuando un operador externo, con **sólo el manual**,
puede:

1. verificar el entorno y saber contra qué base está corriendo;
2. ejecutar S00→S04 + ratios para YPF y llegar a los 7 gates en `PASS`;
3. repetir lo mismo para KO cambiando un parámetro, y saber qué esperar;
4. ejecutar el tramo CNV que corresponda según D-1, para METR;
5. recorrer la provenance de un número cualquiera hasta el SHA256 del documento;
6. demostrar idempotencia comparando dos corridas;
7. leer un gate y decidir si avanza;
8. diagnosticar un resultado incorrecto siguiendo el árbol;
9. distinguir benchmark de ground truth al comparar contra TIKR;
10. no escribir en producción ni una sola vez.

De los diez, **el 3 y el 8 no se pueden cumplir hoy** (C-3 y §5). El 4 depende
de D-1.

---

## 8 · Los 10 puntos más importantes

1. **El manual no arranca de cero.** Ya hay 3.055 líneas de runbooks verificados
   —7 documentos y 8 apéndices— escritos con la regla correcta. El trabajo es
   reorganizar y completar, no redactar de nuevo. **D-2 decide qué pasa con
   ellos.**

2. **El sistema vive en dos ramas y eso parte el alcance.** `econ_key`,
   `measurement_date`, el Financial Model, el adaptador CNV y la homologación
   TIKR existen **sólo en el worktree**. Cuatro de los 17 capítulos obligatorios
   no son ejecutables desde el repo principal. **D-1 es la decisión central.**

3. **El entorno no se puede recrear siguiendo el repo.**
   `docker-compose.yml` no declara `catalaxia-engine-dev` —la base contra la que
   corre todo— y `requirements.txt` no cubre las dependencias del engine. El
   capítulo 1 no puede ser autosuficiente hasta resolverlo (**C-1**).

4. **KO tiene los datos y no tiene recorrido.** 45.113 hechos y 17 filings 10-K
   cargados, cero golden run. Es obligatorio por encargo y **hay que correrlo
   antes de poder documentarlo** (**C-3**). Es un sprint, no un párrafo.

5. **YPF es el único piloto completo.** 7 gates con exit code y señal en
   consola, más la prueba de idempotencia de S03. Es el recorrido pedagógico y
   el patrón que los otros dos tienen que imitar.

6. **METR es el capítulo más rico y ya está hecho.** Aporta lo que ningún otro:
   NIL declarado, escala variable por ejercicio, perímetro declarado vs
   evidenciado, USD MEP, provenance E2E verificada (289 celdas, 0 rotos) y
   homologación externa con 327 comparaciones.

7. **Provenance está mejor de lo que parecía.** `06_PROVENANCE.md` ya trae el
   recorrido inverso para SEC **y** para CNV, más "qué NO tiene provenance". No
   hay que inventarlo; hay que integrarlo.

8. **16 `KNOWN_LIMITATION` que el manual debe decir en voz alta**, no esconder.
   Las cuatro que más duelen: no hay `--resume`, no hay rollback, el enlace
   instrumento→entidad de Market está roto, y la CNV no publica CapEx —lo que
   tumba 7 ratios y cuya fuente (el PDF adjunto) está referenciada con GUID y
   hash y no se descarga.

9. **Documentar no es arreglar, y el alcance lo prohíbe.** Los 11 BLOCKER del
   inventario entran al manual **como rótulos** (`NOT_IMPLEMENTED`,
   `DECISION_REQUIRED`, `KNOWN_LIMITATION`), no como tareas. El manual honesto
   sobre sus límites vale más que uno que finge un happy path.

10. **Dos de los diez criterios de aceptación no se pueden cumplir hoy**: correr
    KO con resultados esperados (C-3) y diagnosticar un fallo siguiendo un árbol
    que todavía no existe. Conviene saberlo antes de empezar a escribir, no
    después.

---

*Insumo: `MANUAL_KNOWLEDGE_INVENTORY.csv` (64 ítems) y su lectura en
`MANUAL_KNOWLEDGE_INVENTORY.md`. Nada de este documento modifica código,
producción, `screener.db` ni ninguna base.*
