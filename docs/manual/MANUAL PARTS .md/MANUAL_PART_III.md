# PARTE III — PILOTO YPF

Este capítulo camina el primer piloto del sistema (aprendizaje completo SEC)
con cifras reales: identidad, preparación, y descarga de RAW para **YPF
S.A.**, CIK `0000904851`, formularios **20-F / 20-F/A**. El parser (S03) y la
normalización (S04) tienen su propia Parte (IV y V); ratios y provenance no
entran en este capítulo.

Cada comando de este capítulo fue ejecutado y su salida verificada contra la
base `catalaxia` (5433 · dev) el **2026-09-04**, o está citado de un
`engine.stage_runs.report` ya persistido de una corrida certificada anterior
con su `run_id` exacto, para que cualquiera pueda reconsultarlo. **Ningún
número de este capítulo es hipotético** — fuente primaria: `docs/manual/
ANNEX_YPF.md`.

Dos advertencias antes de empezar, porque marcan todo lo que sigue:

1. **El Golden Run de YPF es una composición, no una corrida E2E de una sola
   sesión.** S00 es de una fecha, S01 de otra, S02–S03–S04 encadenados entre
   sí en una tercera. Cada etapa busca *"la última corrida con gate PASS"* de
   la anterior, y eso es correcto en este diseño; pero **no existe hoy una
   corrida end-to-end de hoy para YPF** y no hay que presentarla como si
   existiera.
2. **Dos de los tres comandos de este capítulo no son idempotentes.**
   S00 y S02 fallan en la segunda corrida con la misma configuración. Las
   fichas lo dicen donde te lo vas a encontrar, con el defecto exacto, no al
   final.

---

## Paso 1 — S00 · bootstrap

**OBJETIVO**
Verificar que el entorno está correcto y preparar la ejecución (migraciones +
guard de producción).

**PREREQUISITOS**
Parte II, Paso 12 con GATE `PASS` (los cinco comandos de sólo lectura dan lo
esperado).

**COMANDO**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```

**QUÉ HACE**
Aplica las migraciones pendientes sobre la base indicada y dispara el guard de
producción: si `ENGINE_DB_PORT=5432`, no llega a conectarse (`EXT-010`).

**RESULTADO ESPERADO**
`gate = PASS`, exit `0`. Corrida certificada de referencia:
`run_id=a48addfb714841bfb43e537c969ac31d` (2026-09-02), `checks 2/2`, gate
`PASS`.

**VERIFICACIÓN**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT stage_id, gate_status, rows_expected, rows_parsed, rows_rejected \
     FROM engine.stage_runs WHERE run_id='a48addfb714841bfb43e537c969ac31d'"
```

**SI FALLA**

*`psycopg2.errors.UniqueViolation: duplicate key value violates unique
constraint "ux_checkpoints_reuse"`:*

**`KNOWN_LIMITATION`** — **S00 no es idempotente.** En la primera corrida
inserta un checkpoint en `engine.checkpoints` **sin `ON CONFLICT`**, y hay un
índice único sobre `(stage_id, input_hash, code_version, contract_version)`.
Como `input_hash` es el SHA-256 de `settings.describe()`, con la misma base y
el mismo modo siempre da el mismo valor: la segunda corrida choca contra la
primera. Verificado en vivo el 2026-09-04 — exit `1`, corrida `ABORTED`. **No
es una pérdida de datos: es un defecto de idempotencia (hallazgo H-1).** No
borres el checkpoint: registrá el `run_id`, el error y la etapa, y tratálo
como bug. El runbook actual (`02_SEC_EDGAR_E2E_RUNBOOK.md`) afirma lo
contrario; la realidad documentada aquí lo corrige.

*Otro error:* si la base es nueva y no tiene esquema, Paso 12 de la Parte II
("Si falta el esquema: aplicar migraciones").

---

## Paso 2 — S01 · Identity

**OBJETIVO**
Sembrar y resolver la identidad de YPF en `identity_v1` **antes** de que
cualquier etapa posterior pueda inventar una entidad.

**PREREQUISITOS**
Paso 1.

**COMANDO**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s01_identity.py
```

**QUÉ HACE**
Recorre el seed (entidades, identificadores, símbolos yahoo), los vínculos
BYMA / `.BA`, y las resoluciones manuales. Verifica `C-S01-001..004`, que
incluyen chequear que YPF exista como entidad.

**RESULTADO ESPERADO**
`legal_name = YPF SOCIEDAD ANONIMA`, `entity_id = CIK:0000904851`,
`gate = PASS`, exit `0`. Corrida verificada en vivo el 2026-09-04,
`run_id=c87b9bbdcc5044bca8987dfec66a1b48`:

```
[seed] entidades nuevas=11 identificadores nuevos=31 yf_symbols nuevos=20
[links] BYMA nuevos=0 YF .BA nuevos=0 conflictos legacy=4
[manual] resoluciones aplicadas: identifiers nuevos=0 yf nuevos=0 problemas=0
gate = PASS   (checks 4/4, rejected 0)
```

La identidad canónica (esquema `identity_v1`, consulta directa):

```
E01M0X99C8F87H9TH9N39H2D1NW | YPF SOCIEDAD ANONIMA | 0000904851 | 30546689979
```

Los identificadores vigentes de YPF: CIK `0000904851` (SEC), ticker `YPFD`
(BYMA), ticker `YPF` (US), `yf_symbol` `YPF` y `YPFD.BA`.

**VERIFICACIÓN**
```sql
SELECT e.entity_key, e.preferred_name,
       (SELECT id_value FROM identity_v1.identifier i
         WHERE i.entity_id=e.entity_id AND i.id_type='CIK'
           AND i.status='ACTIVE' AND i.valid_to IS NULL LIMIT 1) AS cik,
       (SELECT id_value FROM identity_v1.identifier i
         WHERE i.entity_id=e.entity_id AND i.id_type='CUIT'
           AND i.status='ACTIVE' AND i.valid_to IS NULL LIMIT 1) AS cuit
  FROM identity_v1.entity e WHERE e.preferred_name='YPF SOCIEDAD ANONIMA';
```
Debe devolver una fila con `cik=0000904851` y `cuit=30546689979`.

**SI FALLA**

**`KNOWN_LIMITATION`** — **S01 es específico de YPF.** El check
`C-S01-004` está clavado a esta emisora: verifica explícitamente que la
entidad `YPF SOCIEDAD ANONIMA` exista. Con YPF funciona; con otro emisor no
se comporta igual (lo demostró KO). **No es un fallo de este piloto, pero un
operador debe saberlo** antes de generalizar el mismo comando a CIK
distintos: el flujo S01 todavía no es multi-emisor.

**`KNOWN_LIMITATION`** — el bloque JSON de identidad que imprime el script
reporta `cuit: null` para YPF — aunque el CUIT `30546689979` sí existe en
`identity_v1.identifier` con estado `VERIFIED` (hallazgo H-4). No es un dato
faltante: el script reporta contra el esquema **legacy** `identity.entities`
y no contra `identity_v1`. La consulta de VERIFICACIÓN de arriba es la forma
de mirar la capa canónica.

---

## Paso 3 — Backfill CIK · sólo cuando haga falta

**OBJETIVO**
Resolver el binding `CIK → entity` cuando Identity no lo tenga poblado.

**PREREQUISITOS**
Paso 2 **no es suficiente** — este paso es bajo demanda.

**COMANDO**
```bash
python backfill_cik.py --aplicar
```

**QUÉ HACE**
Completa el enlace que S01 no produjo. **No es parte de la corrida normal de
YPF**: en este piloto S01 ya deja la identidad resuelta (Paso 2). Fue
necesario para el segundo piloto (KO) antes de que S04 pudiera continuar.

**RESULTADO ESPERADO**
No aplica a YPF en estado actual — no hay que correrlo.

**SI FALLA** / **uso correcto:**
Si una etapa posterior se queja, por ejemplo, con *"CIK sin entidad"* en S04:
registrá el incidente y usá este paso. **Tratálo como una dependencia conocida
hasta que S01 sea genérica** (`DECISION_REQUIRED` — misma familia que la
decisión D-3): cada uso de `backfill_cik.py` documenta que el flujo S01
todavía no es multi-emisor.

---

## Paso 4 — S02 · RAW

**OBJETIVO**
Descubrir los filings de YPF contra el índice de EDGAR y traer los artefactos
a `data/raw/` con registro íntegro (fecha, fuente, SHA256).

**PREREQUISITOS**
Paso 2. (Un CIK sin identidad sembrada no corresponde a RAW.)

**COMANDO**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py --cik 0000904851
```

Antes de copiar: `python scripts/engine/s02_fetch_ypf.py --help`. Este script
fue parametrizado (`--cik`, `--forms`, `--max-filings`); no uses sintaxis
recordada sin verificarla contra `--help`.

**QUÉ HACE**
Descubre contra `submissions` + `companyfacts` de EDGAR (no contra una lista
fija), descarga los artefactos de cada filing, verifica el SHA256 contra
disco, y registra todo en `fetch_raw.download_log` y en
`data/raw/engine/CIK0000904851/`.

**RESULTADO ESPERADO**
`rows_failed = 0`, `gate = PASS`, exit `0`. Corrida certificada de referencia
— `run_id=33d234463f4341af9ad4931c67a3c561` (2026-08-23):

```json
"gate": {"status": "PASS"},
"coverage": {"parsed": 171, "expected": 171, "rejected": 0},
"integrity": {
  "hash_in":  "63c720619a9ba899a9ed510b222ecedf563e5fcfc7445d4924fffe5785e1017e",
  "hash_out": "07866cae52eaf73bff4e1b5da31e8a108c71b1604baf7b1d3462ed70804b6d29"
}
```

Los 5 checks (`C-S02-001..005`) en `PASS`: conciliación 171/171, SHA256
re-verificado contra disco sin mismatches, vinculación
entidad→cik→fuente→accession sin violaciones, cortesía SEC dentro del mínimo,
y consumo exclusivo de la identidad sembrada por S01.

**VERIFICACIÓN**
```sql
SELECT request_kind, count(*) AS filas,
       count(*) FILTER (WHERE http_status>=400) AS con_error
  FROM fetch_raw.download_log WHERE cik='0000904851' GROUP BY 1 ORDER BY 1;
```
En el entorno de referencia: **927 filas, 0 con error HTTP** — la cobertura
crece entre corridas (el ledger es un registro de eventos, no un estado).

**SI FALLA**

- *`rows_failed > 0` o algún check en rojo:* el fallback automático de S02
  reintenta 3 veces con backoff 2/5/10s, **sólo** ante 429/500/502/503/504.
  Un 4xx que no es 429 no se reintenta: es un problema a diagnosticar, no una
  red caída. Revisá `fetch_raw.download_log`: la fila con error deja la
  evidencia.
- *`duplicate key value violates unique constraint "ux_checkpoints_reuse"`:*

**`KNOWN_LIMITATION`** — **S02 no es idempotente, y además pierde el report
de la corrida cuando falla.** Mismo defecto que S00: el `INSERT` de
checkpoint es incondicional (hallazgo H-2, reproducido en vivo el 2026-09-04
con `input_hash=63c720...` — el mismo de la corrida certificada del 23/08).
El matiz importante: **el trabajo de fetch sí se persistió** antes de llegar
al `INSERT` que falla — `fetch_raw.download_log` pasó de 740 a 927 filas
durante esa misma corrida fallida (187 artefactos nuevos, extendiendo la
cobertura a 2002-2013). **Los datos quedan bien; el `report` y el checkpoint
de esa corrida se pierden**, porque el `INSERT` que falla está en la misma
transacción que el `UPDATE` del report, y al revertirse se cae el report
pero no el fetch (que ya había hecho commit). **No vuelvas a descargar ni
borres RAW para "arreglarlo"**: registrá el incidente como bug de
idempotencia.

**Regla** — no volver a descargar un RAW que ya tiene hash válido. S02
re-descarga y re-verifica; si el artefacto existe con su SHA, no se repite.

---

## Resumen de la Parte III

| paso | comando | corrida de referencia | gate | estado |
|---|---|---|---|---|
| 1 · S00 | `s00_smoke.py` | `a48addfb…` (2026-09-02) | PASS 2/2 | ⚠️ 1ª corrida PASS; **2ª corrida falla** (`ux_checkpoints_reuse`, H-1) |
| 2 · S01 | `s01_identity.py` | `c87b9bbd…` (2026-09-04) | PASS 4/4 | ✅ reproducible; C-S01-004 fijado a YPF; `cuit: null` en el reporte (H-4) |
| 3 · backfill | `backfill_cik.py --aplicar` | — | — | 🚨 sólo bajo demanda (KO); documentar cada uso hasta generalizar S01 |
| 4 · S02 | `s02_fetch_ypf.py --cik 0000904851` | `33d23446…` (2026-08-23) | PASS 5/5 | ⚠️ 1ª corrida PASS; **2ª corrida falla y pierde el report** (H-2) |

**GATE de la Parte III:** los tres comandos que se ejecutan (S00, S01, S02)
deben dar `PASS` en su primera corrida sobre la base de trabajo. Los dos
defectos de idempotencia (S00 y S02) **no impiden operar**, pero **impiden
declarar la etapa idempotente** y están documentados, no ocultos.

**Lo que sigue de este piloto:** el parser (S03, Parte IV — 27/27 filings,
67.084 facts parseados, `hashout-v2`) y la normalización (S04, Parte V —
67.084 → 47.930 hechos normalizados sin pérdida).

**`DECISION_REQUIRED`** — esta Parte se verificó contra la base `catalaxia`
(5433 · dev), que es la de trabajo. El plan maestro recomienda bases aisladas
(`ypfgolden`, `kogolden`, …) para corridas defensivas; formalizar cuándo usar
una u otra es parte del procedimiento de Golden Run (Parte XVI), no de este
capítulo.

---

*Los comandos de este capítulo fueron ejecutados y sus salidas verificadas
(2026-09-04) o citadas de `engine.stage_runs.report` persistidos con su
`run_id` exacto. Ninguna operación de este capítulo escribe en producción
(5432); todo corre contra 5433 · dev. Los dos defectos reportados no fueron
corregidos: se documentan, como pide el encargo.*