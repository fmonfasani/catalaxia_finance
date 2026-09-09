# F12 — Architecture Decision

MODO: READ-ONLY. Ningún código, config, DB ni Git tocado. Este documento
decide arquitectura; no la implementa.

## Decision

El **runtime productivo objetivo** de Catalaxia/BYMAStocks es el
**pipeline engine** (`S00_bootstrap → S01_identity → S02_fetch →
S03_parse → S04_normalize → ratio_engine → C10 → C11 → C12`),
containerizado, con scheduler propio, para **todo dato que se presente
como validado, certificado o publicado**.

El **pipeline screener/legacy** (`run_all.py`/`run_update.py` +
`job5_v2_extract_eeff.py` + SQLite `screener.db`) **continúa operando**
para BYMA/CNV mientras el gap CNV E2E (`SG-01`, `docs/runbooks/
00_START_HERE.md` §3) no esté resuelto por una fase separada — pero pasa a
estar explícitamente clasificado como **LEGACY, fuera del runtime
objetivo**, y su salida no debe seguir presentándose como equivalente a la
del pipeline certificado.

Es la opción **C (híbrido con frontera explícita)** de las tres planteadas
en `23_F12_DECISION.md` D1 — resuelta con evidencia, no elegida a priori.

## Context

`23_F12_RUNTIME_CRON_VPS_AUDIT.md` dejó D1-D4 documentadas pero sin
decidir. La auditoría independiente posterior (F12-1 a F12-6) confirmó los
gaps de infraestructura del intento de cron-VPS. Esta sesión, al inspeccionar
qué pipeline es realmente el destino de ese intento, encontró algo más
grave que un gap de dependencias: **el intento de cron-VPS apunta al
pipeline legacy, que nunca pasa por C10/C11/C12**, mientras que el pipeline
que sí lo hace (el que F5-F13 endurecieron durante meses) no tiene ningún
camino de despliegue. Sin resolver esto primero, cualquier arreglo de
`requirements.txt`/`REPO_URL`/`.env` solo produciría un cron-VPS más
confiable... del pipeline equivocado. F12 necesita decidir cuál es el
runtime objetivo antes de que F14+ (o "OpenCode") arregle la infraestructura
del que no corresponde.

## Alternatives considered

### Windows Task Scheduler (mantener tal cual)
El único mecanismo con evidencia de estar correctamente definido en código
hoy (`setup_scheduler.ps1`, 4 tareas). **Contras**: atado a una máquina
física/VM concreta, sin contenedor, sin aislamiento, sin capacidad de
recuperación ante pérdida de esa máquina, no resuelve el problema de fondo
(el pipeline que programa nunca pasa por C10/C11/C12).

### VPS cron (tal como lo define `setup_vps.sh` hoy)
Correcto en el papel (5 líneas cron bien formadas, apunta al modo correcto
de `run_update.py`). **Contras**: apunta al pipeline legacy (mismo problema
de fondo que arriba); además, con evidencia de código, la imagen que
ejecutaría esos cron jobs no puede ni importar sus dependencias (F12-1),
tiene `REPO_URL` equivocado (F12-2), paths inconsistentes con `DEPLOY.md`
(F12-3), y usa el script de sync que vacía columnas productivas (§2.4 del
documento 25).

### Docker scheduler/runtime nativo (cron dentro de contenedor, imagen propia)
Aísla el runtime, reproducible, versionado junto al código. Es el mecanismo
que `setup_vps.sh`/`docker-compose.yml` ya intentan para el pipeline
legacy. **Contras** si se aplica ingenuamente: hereda el mismo problema de
fondo si simplemente se "arregla" para seguir corriendo `run_update.py`
sin pasar por C10/C11/C12.

### Híbrido con frontera explícita (SELECCIONADA)
Contenedor + cron para el pipeline **engine** (S00→C12) como runtime
objetivo — resuelve el problema de fondo, no solo el de infraestructura.
El pipeline legacy sigue vivo (Windows Task Scheduler o su propio cron,
sin decidir aquí cuál — ver "Legacy boundary") pero *etiquetado*: cualquier
endpoint/artefacto que sirva sus datos debe decir explícitamente que no
pasaron por C10/C11/C12, en vez de mezclarse en silencio con lo que sí
pasó. **Contra**: requiere trabajo real de integración (encadenar C10-C12
al orquestador, decidir requirements/imagen del engine) que hoy no existe
en ningún lado — no es "solo arreglar `requirements.txt`".

## Selected architecture

Híbrido con frontera explícita. Justificación con evidencia:

1. El harness exige *"PUBLICACIÓN requiere VALIDACIÓN + CERTIFICACIÓN"*.
   Elegir "legacy endurecido" (Opción A de `23_F12_DECISION.md`) como
   runtime objetivo violaría esa regla de forma permanente y por diseño:
   el pipeline legacy no tiene, ni tuvo nunca, C10/C11/C12 en su cadena
   [VERIFICADO POR CÓDIGO, documento 25 §2.2].
2. Elegir "motor puro" (Opción B) e intentar apagar el legacy hoy
   descartaría el único camino que hoy produce datos CNV/BYMA reales — el
   engine no tiene un E2E de CNV ejecutable (`SG-01`, gap conocido, no
   trivial, fuera del alcance de F12). Apagarlo violaría la regla "no
   eliminar/fusionar/reemplazar componentes por nombre o duplicación
   aparente" del harness sin evidencia de que el reemplazo funcione.
3. El híbrido no inventa nada nuevo: es la Opción C que `23_F12_DECISION.md`
   ya había dejado planteada como una posibilidad. Esta decisión la
   resuelve con la evidencia adicional de que la alternativa "sólo
   arreglar el cron legacy" (lo que un lector superficial de F12-1..F12-6
   podría asumir que hay que hacer) sería resolver el síntoma equivocado.

## Runtime topology

```
FUENTES (SEC/EDGAR, CNV, yfinance, INDEC)
   │
   ├─ SEC/EDGAR ─────────────────────────────► INGESTA (S00→S02, RAW inmutable)
   │                                                │
   │                                                ▼
   │                                            PARSED (S03, guardado F13)
   │                                                │
   │                                                ▼
   │                                            NORMALIZED (S04, provenance)
   │                                                │
   │                                                ▼
   │                                       FACTS / MODEL / RATIOS (ratio_engine)
   │                                                │
   │                                                ▼
   │                                           PROVENANCE (source_fact_ids)
   │                                                │
   │                                                ▼
   │                                              C10 VALIDACIÓN
   │                                                │
   │                                                ▼
   │                                              C11 CERTIFICACIÓN
   │                                                │
   │                                                ▼
   │                                    C12 PUBLICACIÓN (publisher.py, staging.*)
   │
   └─ CNV/BYMA ──► [LEGACY: job5_v2_extract_eeff.py → screener.db → sincronizar_a_produccion.py]
                        (NO pasa por C10/C11/C12 — declarado, no oculto)
                        │
                        ▼
                   tablas PG `screener`/`screener_hist`/`silver_norm` ──► api/main.py
```

## Execution chain

```
OBJETIVO (engine, SEC):
  cron (VPS, contenedor propio "catalaxia-engine")
     ↓
  entrypoint ÚNICO NUEVO (no existe hoy — ver Acceptance criteria):
     envuelve a e2e_orchestrator.py (S00→S04) y ENCADENA c10_evaluate.py
     → c11_certificar.py → publisher.py, abortando la cadena si cualquier
     eslabón no da PASS/CERTIFICADA
     ↓
  S00 → S01 → S02 → S03 → S04   (ya existe, ya orquestado por
                                   e2e_orchestrator.py)
     ↓
  C10 (ya existe, invocación manual hoy)
     ↓
  C11 (ya existe, invocación manual hoy)
     ↓
  C12 / publisher.py (ya existe, invocación manual hoy)
     ↓
  staging.* → API (requiere que api/main.py aprenda a leer de aquí, o que
               C12 escriba también a las tablas que la API ya sirve —
               decisión de integración, NO se resuelve en este documento,
               queda como criterio de aceptación explícito)

HOY (legacy, sigue vivo, fuera del runtime objetivo):
  Windows Task Scheduler (evidencia de código, no de ejecución)
     ↓
  run_update.py / run_all.py (entrypoints ya existen)
     ↓
  s0→s8 internos del screener (no relacionados con S00-S04 del engine)
     ↓
  screener.db (SQLite)
     ↓
  sincronizar_a_produccion.py (manual) → tablas PG `screener`/`silver_norm`
     ↓
  api/main.py (ya existe, ya sirve esto)
```

## Data/control boundaries

| Componente | Capa primaria | Plano | Qué hace | Qué NO hace |
|---|---|---|---|---|
| S00-S02 | RAW / IDENTIDAD | DATOS+CONTROL | ingesta + identidad, RAW inmutable | no parsea |
| S03 | PARSED | DATOS+CONTROL | parse XBRL, guarda F13 (`decidir_reemplazo`) | no normaliza, no calcula ratios |
| S04 | NORMALIZED | DATOS | upsert por `fact_key`, provenance | no borra parsed/derived |
| ratio_engine | RATIOS | DATOS | calcula ratios sobre `derived.fact` | no valida |
| C10 | VALIDACIÓN | CONTROL | solo lectura, invariantes (`NO_DANGLING` incl.) | no escribe, no certifica |
| C11 | CERTIFICACIÓN | CONTROL | veredicto único por run, `engine.certifications` | no publica |
| publisher.py (C12) | PUBLICACIÓN | CONTROL+DATOS | swap atómico a `staging.*`, exige C10 PASS + C11 CERTIFICADA | no calcula, no certifica |
| e2e_orchestrator.py | EJECUCIÓN | EJECUCIÓN | encadena S00-S04 bajo un `run_id` | **no** encadena C10-C12 (gap a cerrar) |
| run_update.py / run_all.py | EJECUCIÓN (legacy) | EJECUCIÓN | ingesta+cálculo del screener 571 empresas | no pasa por C10/C11/C12 |
| api/main.py | PUBLICACIÓN (consumidor) | DATOS | sirve `screener`/`silver_norm`/etc. | no distingue certificado de no-certificado hoy (gap) |

## Security boundaries

| Componente | Secreto que recibe | Mecanismo |
|---|---|---|
| `db` (Postgres) | `POSTGRES_PASSWORD` | env de compose, interpolado desde `.env` del host |
| `pipeline`/`migrate` | `DB_PASSWORD`/`POSTGRES_PASSWORD` | env de compose |
| `api` | **hoy: ninguno** (`API_KEY`/`API_CORS_ORIGINS` no llegan — doble gap, documento 25 §11) | objetivo: `environment:` explícito en `docker-compose.yml` o `env_file: .env`, nunca hardcodeado en la imagen |
| Fuentes externas (SEC/CNV/yfinance/INDEC) | ninguno (TLS por certificado público) | `REQUESTS_VERIFY` fail-closed por script, ya correcto en el camino productivo (documento 25 §2.5) |
| Contenedor `pipeline` (engine, objetivo) | mismas credenciales DB que hoy, más ninguna credencial externa nueva | a definir junto con el entrypoint nuevo |

Ningún secreto debe quedar en el `Dockerfile`/imagen — todos vía variable de
entorno inyectada en runtime, ya sea `environment:` o `env_file:`. Ninguna
IP literal ni `usuario@ip` en el repo (regla R2, ya verificada PASS en la
auditoría F13 previa sobre el código productivo).

## Legacy boundary

**Queda fuera del runtime objetivo** (no se borra, no se toca):

- `scripts/tickets/screener/{run_all,run_update,setup_scheduler}.py/.ps1`
- `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py` y el resto de
  `scripts/tickets/cnv/scripts/*` (incluidas las ~37 exploraciones con
  `verify=False` hardcodeado — quedan fuera, no se ejecutan en el runtime
  objetivo, no se editan)
- `data/screener.db`, `scripts/deploy/{sincronizar_a_produccion,
  migrate_sqlite_to_pg}.py`
- `scripts/engine/c4_cnv_adapter.py` (worktree `catalaxia-cnvmig`, no
  mergeado) — candidato natural para cerrar `SG-01` en una fase futura,
  pero esa decisión no se toma aquí.
- Los ~60 scripts de `scripts/engine/` que no son S00-S04/C3/C10/C11/C12
  (auditorías puntuales, `f0NN_*`, `mut_*`, adversarios) — ya excluidos por
  el propio runbook.

"Queda fuera" significa: no forma parte de la cadena que un cron/scheduler
del runtime objetivo dispara, y su salida no debe presentarse como
certificada. Sigue siendo el único productor de datos CNV/BYMA reales hasta
que una fase futura cierre `SG-01`; apagarlo hoy sin reemplazo funcional
dejaría sin dato a 56+13 empresas del screener — eso sí sería una regresión
de producto, no una decisión de arquitectura.

## Failure model

| Escenario | Comportamiento definido (objetivo) | Evidencia hoy |
|---|---|---|
| Fallo S00 | `run_scope` cierra run+stage ABORTED (F10) | [VERIFICADO POR TEST, F10, 35/36] |
| Fallo S01/S02 | idem, `stage_id` propagado (F10, 6 call-sites) | [VERIFICADO POR TEST] |
| Fallo S03 | guarda F13: sin reemplazo, `parsed.*` previo intacto, `C-S03-010` BLOCK | [VERIFICADO POR TEST+EJECUCIÓN, F13, 16/16 + 2 E2E reales] |
| Fallo S04 | upsert por `fact_key`, nunca borra; provenance íntegra | [VERIFICADO POR CÓDIGO, F13 §4] |
| C10 BLOCK | cadena se detiene, no llega a C11; hoy requiere intervención manual porque no hay entrypoint que lo encadene | [VERIFICADO POR CÓDIGO — el gap del entrypoint es el punto débil] |
| C11 NEGADA | `publisher.py` rehúsa publicar (`gate_decide`) | [VERIFICADO POR TEST, F10 test G/H] |
| C12 BLOCK | swap no ocurre, target previo intacto | [VERIFICADO POR CÓDIGO, `publisher.py` diseño transaccional] |
| Pérdida de contenedor | objetivo: `restart: unless-stopped` (ya así en `api`/`db`/`nginx`; falta agregarlo si se crea el contenedor engine) | [VERIFICADO POR CÓDIGO para los 3 existentes] |
| Reinicio VPS | objetivo: `db` con volumen persistente (`pgdata`, ya así); cron re-arma solo si el VPS levanta docker+cron al boot — no verificado | [NO DETERMINABLE sin VPS real] |
| Scheduler duplicado | objetivo: lock/idempotencia — S00-S04 ya son idempotentes por `run_scope`+checkpoints; **no hay lock explícito contra dos cron corriendo en paralelo** — gap a definir en implementación | [NO DETERMINABLE hoy; ningún mecanismo de lock encontrado en `setup_vps.sh` ni en el engine] |
| Fallo DB | `pg_isready` wait en `setup_vps.sh` paso 5; guard `EXT-010` contra escribir el puerto equivocado | [VERIFICADO POR CÓDIGO] |
| Fallo de red (fuente externa) | `REQUESTS_VERIFY` fail-closed; CNV incremental difiere con backoff y registra `cnv_last_status.json` (pipeline legacy, no engine) | [VERIFICADO POR CÓDIGO, documento 25 §2.5 y `docs/screener/OPERACION.md` §3] |
| Datos parciales | S03 F13 exactamente cubre este caso (0 filings / filing faltante / degradado a 0 hechos) | [VERIFICADO POR TEST, F13] |

## Acceptance criteria

Validados contra el código real, no copiados genéricamente. Marcados
`(NUEVO)` los que hoy no existen en ningún lado y `(YA EXISTE)` los que ya
están implementados y solo requieren integrarse/conectarse.

- [ ] `(NUEVO)` Existe un entrypoint único que encadena `e2e_orchestrator.py`
      (S00→S04) → `c10_evaluate.py` → `c11_certificar.py` → `publisher.py`,
      abortando si cualquier eslabón no da PASS/CERTIFICADA/ALLOW.
- [ ] `(NUEVO)` Ese entrypoint corre dentro de un contenedor con las
      dependencias reales del pipeline engine (`sqlalchemy`, `psycopg2`,
      NO `yfinance`/`requests` si el engine no los usa — verificar contra
      imports reales de S00-S04, C10-C12 antes de fijar el lockfile).
- [ ] `(NUEVO)` El contenedor engine tiene su propio cron (no reutiliza
      ciegamente el cron del pipeline legacy) con horario a definir por
      negocio (fuera de alcance de F12).
- [ ] `(NUEVO)` Existe algún mecanismo de lock/idempotencia contra dos
      corridas cron superpuestas del mismo pipeline (hoy no existe).
- [ ] `(YA EXISTE, requiere fix)` `requirements.txt` del contenedor
      `pipeline` legacy incluye `yfinance`/`requests`/`pandas` — O BIEN se
      usa `backend/requirements.txt` — O BIEN se decide formalmente que el
      pipeline legacy no se containeriza y sigue en Windows Task Scheduler
      (elegir UNA, no dejar ambigüedad D2).
- [ ] `(YA EXISTE, requiere fix)` `setup_vps.sh`: `REPO_URL` coincide con
      el remote real (`https://github.com/fmonfasani/catalaxia_finance.git`).
- [ ] `(YA EXISTE, requiere fix)` `setup_vps.sh`/`DEPLOY.md` usan el mismo
      `PROJECT_DIR`.
- [ ] `(YA EXISTE, requiere fix)` `setup_vps.sh` paso 6 usa
      `sincronizar_a_produccion.py` (upsert/reemplazo transaccional), NO
      `migrate_sqlite_to_pg.py` (vacía 12 columnas productivas sin que la
      guarda de conteo lo detecte).
- [ ] `(NUEVO)` `docker-compose.yml`, servicio `api`: `API_KEY` y
      `API_CORS_ORIGINS` llegan al contenedor (`environment:` explícito o
      `env_file:`), Y `setup_vps.sh` las escribe en `.env`.
- [ ] `(NUEVO)` `docker-compose.yml`, servicio `api`: `healthcheck:`
      apuntando al `/health` que `api/main.py` ya expone.
- [ ] `(YA EXISTE)` API fail-closed sin `API_KEY` (F11, verificado 15/15).
- [ ] `(YA EXISTE)` Producción no usa bypass TLS: `REQUESTS_VERIFY`
      fail-closed en todo el camino productivo verificado (job5, dolares,
      dgce). Los ~37 `verify=False` hardcodeados quedan fuera del runtime
      (legacy boundary) — criterio: NO deben ejecutarse desde ningún
      entrypoint del runtime objetivo ni del legacy operativo.
- [ ] `(NUEVO)` Alguna forma de distinguir, en la salida servida por la
      API o en el propio dato, qué proviene del pipeline certificado
      (engine) y qué del legacy — mínimo: un campo/flag de origen. Decisión
      de diseño de datos, no se resuelve en este documento.
- [ ] `(YA EXISTE)` `run_id`/`stage_id` se conservan a través de todo
      S00-S04 (F5-F10, verificado por test).
- [ ] `(YA EXISTE)` C10 bloquea cuando corresponde (`NO_DANGLING`, F13
      verificado por ejecución real).
- [ ] `(YA EXISTE)` C11 no certifica sin C10 PASS (verificado por test,
      F10 test G).
- [ ] `(YA EXISTE)` C12 no publica sin C11 CERTIFICADA (verificado por
      test, F10 test H, `gate_decide`).
- [ ] `(YA EXISTE)` Fallo deja estado recuperable: ABORTED en run+stage
      (F10), guarda de no-reemplazo en S03 (F13).
- [ ] `(NUEVO)` `scripts/backup.sh`: al menos una prueba de restore
      documentada y ejecutada una vez (hoy solo hay comando manual sin
      evidencia de haberse probado).
- [ ] `(NUEVO)` Ejecución E2E reproducible **dentro del contenedor
      objetivo** (hoy la reproducibilidad de F13 está demostrada en
      venv local/DEV, no en Docker — ver documento 25 §4).
- [ ] `(NUEVO)` Rollback probado: al menos un caso real de C12
      BLOCK/rollback ejecutado end-to-end en el runtime objetivo
      containerizado (hoy probado solo a nivel de test unitario/DEV local,
      F10 test I/J).

## Certification evidence

Para que F12 pase de `NO DETERMINABLE`/`DEFINIDO` a `CERTIFICADO`, deberá
presentarse, como mínimo:

1. Los 20 criterios de aceptación de arriba, cada uno con su clasificación
   `[VERIFICADO POR CÓDIGO/TEST/EJECUCIÓN]` — ninguno aceptado por
   afirmación sin evidencia.
2. Al menos una corrida E2E real (S00→C12) dentro del contenedor objetivo,
   contra DEV (puerto 5433), con `run_id` documentado, igual que exige el
   patrón que F13 ya estableció para S00-S04.
3. Confirmación de que el pipeline legacy sigue operando sin regresión
   (571 empresas, sin caída de cobertura) — el runtime objetivo no debe
   romper lo que hoy funciona.
4. Evidencia de ejecución real en VPS (no solo en DEV local) — hoy
   completamente ausente (documento 25 §4, fila "Ejecución real en VPS").
5. Confirmación explícita de que ningún dato servido por la API pública
   se presenta como certificado sin haber pasado por C10/C11/C12 — el
   hallazgo central de este documento (§2.3 del documento 25) debe quedar
   cerrado, no solo documentado.

---

# F12 DEFINICIÓN
---------------
**RUNTIME OBJETIVO:** pipeline engine (S00→S04→C10→C11→C12), contenedor
Linux dedicado, cron propio — VPS.
**SCHEDULER:** cron dentro del contenedor engine (objetivo, nuevo);
Windows Task Scheduler se mantiene para el pipeline legacy (sin cambios).
**ENTRYPOINT:** nuevo, a implementar — envuelve `e2e_orchestrator.py` +
`c10_evaluate.py` + `c11_certificar.py` + `publisher.py` en una sola
cadena con abort-on-fail.
**DATABASE:** PostgreSQL (`catalaxia`, DEV 5433 / PROD 5432, guard
EXT-010) para el runtime objetivo; SQLite `screener.db` se mantiene para
el legacy, puente vía `sincronizar_a_produccion.py` (nunca
`migrate_sqlite_to_pg.py`).
**CONTAINERS:** `pipeline` (nuevo lockfile de dependencias, específico del
engine, NO reutilizar ciegamente `requirements.txt` ni
`backend/requirements.txt` sin verificar), `api` (ya correcto en
dependencias, requiere fix de env de secretos + healthcheck), `db`, `nginx`
(sin cambios).
**SECRET MANAGEMENT:** variables de entorno inyectadas en runtime
(`environment:`/`env_file:`), nunca en imagen; `API_KEY`/
`API_CORS_ORIGINS` deben resolverse en dos lugares hoy rotos
(`setup_vps.sh` + `docker-compose.yml`).
**LEGACY STATUS:** pipeline screener/CNV se mantiene operando, sin
tocar, fuera del runtime objetivo, hasta que una fase futura resuelva
`SG-01`; su salida debe distinguirse de la certificada.

**F12 STATUS:**
- DEFINICIÓN: **PASS**
- IMPLEMENTACIÓN: PENDIENTE
- VERIFICACIÓN: PENDIENTE
- CERTIFICACIÓN: PENDIENTE

**NEXT AGENT:**
OpenCode

**NEXT TASK:**
IMPLEMENTAR EXACTAMENTE LA ARQUITECTURA DEFINIDA EN
`26_F12_ARCHITECTURE_DECISION.md`
