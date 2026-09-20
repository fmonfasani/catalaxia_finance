# ANNEX_YPF — procedimiento completo de ejecución, YPF S.A.

**CIK `0000904851`** · **Fecha de esta verificación: 2026-09-04** · Piloto 1
de 3 (aprendizaje completo SEC). Insumo de Paso 4, no el manual. No se
modificó código.

**Método:** cada resultado de este anexo es real — verificado contra la
base `catalaxia` (`5433`, dev) el día de arriba, o citado de un
`engine.stage_runs.report` ya persistido de una corrida certificada
anterior (con su `run_id` exacto, para que cualquiera pueda reconsultarlo).
**Ningún número de este documento es hipotético.** Donde algo no salió como
el runbook lo describe, se dice — incluidos dos defectos reproducidos en
vivo durante esta misma verificación (§13).

---

## 0. Resumen de lo verificado hoy

| # | sección | verificado hoy | evidencia primaria |
|---|---|---|---|
| 1 | Identificación | sí, en vivo | `s01_identity.py`, `run_id=c87b9bbdcc5044bca8987dfec66a1b48` |
| 2-3 | Discovery / Filing | sí, consulta directa | `fetch_raw.download_log` |
| 4 | RAW | sí, en vivo (parcial — ver §13) | `s02_fetch_ypf.py`, mezcla de corrida `33d234463f4341af9ad4931c67a3c561` (2026-08-23, con report completo) + corrida de hoy (sin report, ver §13) |
| 5-7 | Parsing / Contextos / Facts | citado de corrida certificada | `run_id=d86bb4fe0cca4dd8a843a6069dc00c5b` (2026-08-31) |
| 8 | Normalización | citado de corrida certificada | `run_id=dc67d06fc5454b0984f4bb95e7ee565b` (2026-08-31) |
| 9 | Economic Facts | sí, en vivo | consulta directa — **no aplica a SEC hoy** |
| 10 | Ratios | sí, en vivo | `derived.ratio WHERE cik='0000904851'` |
| 11 | Provenance | sí, en vivo, con verificación de SHA256 contra disco | fact `Assets` 2025-12-31 |
| 12 | Gates | consolidado de todo lo anterior | — |
| 13 | Idempotencia | **intentada en vivo; dos defectos reales encontrados** | ver detalle |
| 14 | Certificación | evaluada contra `07_CERTIFICATION.md` §3 | — |

---

## 1. Identificación

**Comando:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s01_identity.py
```

**Corrida real de hoy** — `run_id=c87b9bbdcc5044bca8987dfec66a1b48`:

```
[seed] entidades nuevas=11 identificadores nuevos=31 yf_symbols nuevos=20
[links] BYMA nuevos=0 YF .BA nuevos=0 conflictos legacy=4
[manual] resoluciones aplicadas: identifiers nuevos=0 yf nuevos=0 problemas=0
{
  "present": true,
  "entity_id": "CIK:0000904851",
  "legal_name": "YPF SOCIEDAD ANONIMA",
  "cik": "0000904851",
  "identifiers": [
    {"id_type": "CIK", "id_value": "0000904851", "marketplace": "SEC", "status": "ACTIVE"},
    {"id_type": "TICKER", "id_value": "YPFD", "marketplace": "BYMA", "status": "ACTIVE"},
    {"id_type": "TICKER", "id_value": "YPF", "marketplace": "US", "status": "ACTIVE"},
    {"id_type": "YF_SYMBOL", "id_value": "YPF", "marketplace": "yahoo", "status": "ACTIVE"},
    {"id_type": "YF_SYMBOL", "id_value": "YPFD.BA", "marketplace": "yahoo", "status": "ACTIVE"}
  ]
}
--- conciliacion ---
checks_expected = 4
checks_pass     = 4
checks_rejected = 0 {}
gate            = PASS
```

**Resultado esperado:** `checks_pass = 4/4`, `gate = PASS`, exit `0`. ✅
**Obtenido:** idéntico. Exit code confirmado `0`.

**Identidad canónica** (`identity_v1`, consultada directo — nótese que
difiere del bloque de arriba, que reporta contra el esquema legacy
`identity.entities`; los dos coexisten):

```sql
SELECT e.entity_key, e.preferred_name, i_cik.id_value AS cik, i_cuit.id_value AS cuit
  FROM identity_v1.entity e ...
```
```
E01M0X99C8F87H9TH9N39H2D1NW | YPF SOCIEDAD ANONIMA | 0000904851 | 30546689979
```

**Nota:** el bloque JSON que imprime `s01_identity.py` reporta `cuit: null`
porque consulta el esquema **legacy** `identity.entities`, no
`identity_v1`. El CUIT (`30546689979`, con assertion `VERIFIED`) sí existe
en `identity_v1.identifier` — confirmado por consulta directa. Los dos
esquemas coexisten y no siempre coinciden en qué campos exponen.

---

## 2. Discovery

S02 descubre los filings de un CIK contra el índice de EDGAR
(`submissions` + `companyfacts`), no contra una lista fija. La evidencia de
qué se descubrió hoy vive en `fetch_raw.download_log`, desglosada por
`request_kind`:

```sql
SELECT request_kind, count(*), count(*) FILTER (WHERE http_status>=400)
  FROM fetch_raw.download_log WHERE cik='0000904851' GROUP BY 1;
```

| `request_kind` | filas | con error HTTP |
|---|---:|---:|
| `SUBMISSIONS` | 9 | 0 |
| `SUBMISSIONS_PAGE` | 9 | 0 |
| `COMPANYFACTS` | 9 | 0 |
| `FILING_INDEX` | 163 | 0 |
| `FILING_SUMMARY` | 42 | 0 |
| `DOC_HTM` | 418 | 0 |
| `XBRL_INSTANCE` | 20 | 0 |
| `XBRL_SCHEMA` | 42 | 0 |
| `XBRL_PACKAGE_ZIP` | 45 | 0 |
| `XBRL_OTHER` | 22 | 0 |
| `LINKBASE_CAL`/`_DEF`/`_LAB`/`_PRE` | 37 c/u (148) | 0 |
| **total** | **927** | **0** |

`SUBMISSIONS`/`SUBMISSIONS_PAGE`/`COMPANYFACTS` son estrictamente la capa
de *discovery*: 9 pasadas cada una (múltiples invocaciones acumuladas en
el ledger, que es un registro de eventos, no de estado — crecer es
correcto). **0 errores HTTP en las 927 filas.**

---

## 3. Filing

Filings **20-F**/**20-F/A** descubiertos para CIK `0000904851`, del índice
real (`fetch_raw.download_log`, 27 accessions con metadata completa de las
28 totales — la 28ª es una fila `accession_number IS NULL`, ligada al
`SUBMISSIONS` a nivel de CIK, no a un filing puntual):

| accession | forma | filed | período |
|---|---|---|---|
| `0001193125-26-126363` | 20-F | 2026-03-26 | 2025-12-31 |
| `0001193125-25-067155` | 20-F | 2025-03-28 | 2024-12-31 |
| `0001193125-24-114066` | 20-F | 2024-04-25 | 2023-12-31 |
| `0001193125-23-097822` | 20-F | 2023-04-11 | 2022-12-31 |
| `0001193125-22-111088` | 20-F | 2022-04-20 | 2021-12-31 |
| `0001193125-21-125294` | 20-F | 2021-04-22 | 2020-12-31 |
| `0001193125-20-119222` | 20-F | 2020-04-24 | 2019-12-31 |
| `0001193125-19-096821` | 20-F | 2019-04-04 | 2018-12-31 |
| `0001193125-18-127245` | 20-F | 2018-04-24 | 2017-12-31 |
| `0001193125-17-115552` | 20-F | 2017-04-07 | 2016-12-31 |
| `0001193125-16-507875` | 20-F | 2016-03-17 | 2015-12-31 |
| `0001193125-15-111986` | 20-F | 2015-03-30 | 2014-12-31 |
| `0001193125-14-119270` | 20-F | 2014-03-28 | 2013-12-31 |
| `0001193125-13-178160` | 20-F | 2013-04-26 | 2012-12-31 |
| `0001208646-12-000138` | 20-F | 2012-05-16 | 2011-12-31 |
| `0001208646-11-000183` | 20-F | 2011-04-12 | 2010-12-31 |
| `0001193125-10-149744` | 20-F | 2010-06-29 | 2009-12-31 |
| `0001193125-09-141626` | 20-F | 2009-06-30 | 2008-12-31 |
| `0000950103-08-002589` | 20-F/A | 2008-10-20 | 2007-12-31 |
| `0000950103-08-001022` | 20-F/A | 2008-04-16 | 2007-12-31 |
| `0000950103-08-001000` | 20-F | 2008-04-15 | 2007-12-31 |
| `0001193125-07-143924` | 20-F | 2007-06-27 | 2006-12-31 |
| `0001193125-06-147059` | 20-F | 2006-07-14 | 2005-12-31 |
| `0001193125-05-135966` | 20-F | 2005-06-30 | 2004-12-31 |
| `0001047469-04-022346` | 20-F | 2004-07-01 | 2003-12-31 |
| `0001125282-03-004056` | 20-F | 2003-06-27 | 2002-12-31 |
| `9999999997-02-037446` | 20-F | 2002-06-28 | 2001-12-31 |

**27 filings**, 2002 a 2026 (24 años de historia). Los últimos 9 (2017 en
adelante, más el paquete completo desde 2017) tienen XBRL; los anteriores
son era pre-XBRL (ver §5, `C-S03-005`).

---

## 4. RAW

**Comando:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py --cik 0000904851
```

**Última corrida con `report` completo y `gate=PASS`** —
`run_id=33d234463f4341af9ad4931c67a3c561` (2026-08-23):

```json
"gate": {"status": "PASS"},
"coverage": {"parsed": 171, "expected": 171, "rejected": 0},
"integrity": {
  "hash_in":  "63c720619a9ba899a9ed510b222ecedf563e5fcfc7445d4924fffe5785e1017e",
  "hash_out": "07866cae52eaf73bff4e1b5da31e8a108c71b1604baf7b1d3462ed70804b6d29"
}
```

Los 5 checks (`C-S02-001..005`) en `PASS`: conciliación 171/171, SHA256
re-verificado contra disco (171/171 sin mismatch), vinculación
entidad→cik→fuente→accession sin violaciones, cortesía SEC (intervalo
mínimo 0.343s ≥ `0.35*0.5`), S01 consumido en exclusiva (`CIK=0000904851`,
0 URLs con CIKs del catálogo legacy prohibido).

**Resultado esperado:** `rows_failed = 0`, `gate = PASS`. ✅ **Obtenido.**

**Estado hoy:** `fetch_raw.download_log` tiene **927** filas para este CIK
(no 171 — la cobertura creció entre corridas, ver §13 para lo que pasó en
la corrida de hoy mismo). **0 con `http_status >= 400`.**

---

## 5. Parsing

**Comando:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py --cik 0000904851
```

**Última corrida certificada** — `run_id=d86bb4fe0cca4dd8a843a6069dc00c5b`
(2026-08-31T22:31:25Z → 22:37:11Z, ~5m46s):

```json
"gate": {"status": "PASS"},
"input": {"rows": 187, "checkpoint_id": "S02:711c2d1a478845df98551663632728fb"},
"coverage": {"parsed": 27, "expected": 27, "rejected": 0,
             "by_reason": {"BAD_INPUT": 0, "REJECTED_FILING": 0}},
"integrity": {
  "hash_in":  "a5f05ee9e4e58a8882a9ee838077973243b9513fc4759f47b5ffe7d851855f04",
  "hash_out": "a05cb59cb412d49022238128bb6d0f10de8695b38e059f50dcdd777915ed70c4",
  "hash_spec": "hashout-v2"
}
```

Los 9 checks (`C-S03-001..009`) en `PASS`: **27/27 filings**, integridad
RAW verificada, provenance completa, cobertura XBRL, era pre-XBRL
declarada, 0 referencias colgantes, comparación contra `companyfacts`
generada, outputs escritos, performance sin bloquear.

**Resultado esperado:** `[hash_out] hashout-v2 = <64 hex>`, `filings_rejected = 0`,
`gate = PASS`. ✅ **Obtenido**, exit `0`.

---

## 6. Contextos

```sql
SELECT count(*) FROM parsed.contexts
 WHERE run_id IN (SELECT DISTINCT run_id FROM parsed.facts WHERE cik='0000904851');
```

**`23.478` contextos**, ligados a la corrida `d86bb4fe0cca4dd8a843a6069dc00c5b`
de §5. `C-S03-006` de esa misma corrida certificó **0 `context_refs`
colgantes** — todo contexto referenciado por un fact existe.

---

## 7. Facts

```sql
SELECT count(*) FROM parsed.facts WHERE cik='0000904851';
```

**`67.084` facts parseados** (`parsed.facts`), todos de la corrida
`d86bb4fe0cca4dd8a843a6069dc00c5b`. `C-S03-003` de esa corrida certificó
**0 violaciones de provenance** sobre este mismo conjunto (el número exacto
que cita el check, `facts=90398`, corresponde a un filing distinto ya
citado como ejemplo en el propio código del check — la cifra de `67.084`
es la medición directa sobre `cik='0000904851'` hecha en esta verificación,
no una cita de ese check).

---

## 8. Normalización

**Comando:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py
```

**Última corrida certificada, ligada exactamente al S03 de §5** —
`run_id=dc67d06fc5454b0984f4bb95e7ee565b` (2026-08-31T22:37:19Z → 22:39:02Z):

```json
"gate": {"status": "PASS"},
"input": {"rows": 67084, "stage": "S03_parse",
          "run_id": "d86bb4fe0cca4dd8a843a6069dc00c5b",
          "checkpoint_id": "d86bb4fe0cca4dd8-s03"},
"coverage": {
  "grupos": 47930, "emitidos": 47930,
  "desempates": {"UNICO": 29077, "IDENTICO": 18753, "POR_PRECISION": 100},
  "sin_unidad": 0, "sin_entidad": 0, "sin_contexto": 0, "unidad_no_resuelta": 0
},
"integrity": {
  "hash_in":  "f02684d9278252273b4a6cd843b60126772c5b0ed026b9b2bafd3cae1582597c",
  "hash_out": "a896b8251d1111f2bb84aae3791f7eee66a4833a33bdcc670ee0a52d67bf7811"
}
```

**67.084 facts → 47.930 hechos normalizados** (`grupos=emitidos=47930`,
sin pérdida). Desempate: 29.077 únicos, 18.753 idénticos entre
representaciones, 100 resueltos por precisión — **0 sin unidad, sin
entidad, sin contexto, o con unidad no resuelta**. Los 9 checks
(`C-S04-001..009`) en `PASS`.

**Resultado esperado:** en `--dry-run`, `C-S04-005..009` en `SKIP`; sin
`--dry-run`, `gate = PASS`. ✅ **Obtenido** en la corrida certificada.

**Estado hoy** (consulta directa, no depende de una corrida puntual):
```sql
SELECT count(*) FROM derived.fact WHERE cik='0000904851' AND valid_to IS NULL;
```
**`47.930`** — coincide exactamente con `emitidos` de la corrida de
referencia. No hay hechos vigentes de más ni de menos.

---

## 9. Economic Facts

```sql
SELECT count(*) FROM derived.fact WHERE cik='0000904851' AND econ_key IS NOT NULL;
```
**`0` de 47.930.**

**No es un error ni una omisión: es el alcance declarado.** `econ_key`
(migración `036_economic_identity`, definida como
`sha256(entity_id|qname|perimetro|period_kind|start|end|unit_measure|
measurement_date)`) es el identificador del **hecho económico**
independiente del documento — lo que distingue "esta ocurrencia" de "esto
que se está midiendo". Hoy solo se puebla para CNV, vía el adaptador
canónico que vive en el worktree `catalaxia-cnvmig` (no mergeado). Para
SEC, incluido YPF, el identificador de ocurrencia (`fact_key`) es el único
disponible — ver §11.

**Resultado esperado:** ninguno — esta sección documenta una ausencia
declarada, no un procedimiento ejecutable hoy para este piloto.

---

## 10. Ratios

**Comando:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851 --persist
```

**Estado real en `derived.ratio`** (consulta directa, filas vigentes):

| `canonical_id` | ventana | período | estado | valor | moneda | fórmula |
|---|---|---|---|---:|---|---|
| `eps` | FY | 2025-12-31 | CALCULADO | **-2.11** | USD | EPS básico reportado por el emisor |
| `pe` | FY | 2025-12-31 | **NOT_CALCULABLE** | — | USD | `(close / ratio_adr) / eps_basico` |
| `pb` | PIT | 2025-12-31 | CALCULADO | **1.835993** | USD | `(close/ratio_adr) / (patrimonio_controladora/acciones_circulacion)` |
| `ev_sales` | FY | 2025-12-31 | CALCULADO | **1.599221** | USD | `(market_cap + deuda_financiera - efectivo) / ingresos` |

**`pe` es `NOT_CALCULABLE` con motivo explícito**, no una casilla vacía:

> `REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin valor
> por decision financiera, no por falta de dato: el EPS esta y su
> provenance tambien`

**Resultado esperado:** una línea por `(CIK, ratio, ventana, período,
estado, valor)`, exit `0`. ✅ **Coincide con el estado persistido.**

**Guard de pertenencia (F-061), verificado en el propio código de
`ratio_engine.py`:** antes de calcular, corre
`violaciones_pertenencia(c)` y se niega (`exit 1`) si encuentra alguna.
Para YPF, esta verificación forma parte de cada corrida — no es un
chequeo aparte.

---

## 11. Provenance

Un hecho real, recorrido completo hacia atrás, con verificación de
SHA256 contra el archivo en disco — no una demostración simulada.

**Hecho elegido:** `Assets` (activo total), YPF, 2025-12-31, USD
29.439.000.000.

```sql
SELECT fact_key, tag, value_numeric, currency, report_period,
       accession_number, source_fact_ids[1]
  FROM derived.fact
 WHERE cik='0000904851' AND valid_to IS NULL AND tag='Assets'
   AND NOT is_dimensional
   AND COALESCE(instant_date::text,end_date::text)=report_period::text
 ORDER BY report_period DESC LIMIT 1;
```
```
fact_key = 7365a6c2b4d55fa9c48f88e8bf8485440a7e6bf6e66e9035a867e67e7b7f43a7
tag      = Assets
valor    = 29439000000 USD
período  = 2025-12-31
accession= 0001193125-26-126363
source_fact_ids[1] = 165389
```

```sql
SELECT fact_id, cik, accession_number, qname, context_id,
       source_file, source_path, source_hash
  FROM parsed.facts WHERE fact_id=165389;
```
```
fact_id       = 165389
qname         = https://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full#Assets
context_id    = PAsOn12_31_2025
source_file   = d95578d20f.htm
source_path   = CIK0000904851/filings/000119312526126363/
                0001193125-26-126363-xbrl.zip!d95578d20f.htm
source_hash   = 960c7a2e28de2028a26ca1ff73525b3b03ec333ebe2365ea261a07302f68d823
```

**Verificación final — SHA256 del archivo real dentro del ZIP, calculado
en esta sesión:**
```python
import zipfile, hashlib
with zipfile.ZipFile("data/raw/engine/CIK0000904851/filings/"
                      "000119312526126363/0001193125-26-126363-xbrl.zip") as zf:
    data = zf.read("d95578d20f.htm")
hashlib.sha256(data).hexdigest()
```
```
960c7a2e28de2028a26ca1ff73525b3b03ec333ebe2365ea261a07302f68d823
```

**Coincide, dígito por dígito, con `source_hash`.** La cadena completa
`derived.fact → parsed.facts → RAW → SHA256` cierra para este hecho.

**Resultado esperado:** el hash recalculado reproduce el `source_hash`
almacenado. ✅ **Obtenido.**

---

## 12. Gates — consolidado

| etapa | `run_id` de referencia | fecha | gate | checks |
|---|---|---|---|---|
| S00 | `a48addfb714841bfb43e537c969ac31d` | 2026-09-02 | **PASS** | 2/2 |
| S01 | `c87b9bbdcc5044bca8987dfec66a1b48` | 2026-09-04 (hoy) | **PASS** | 4/4 |
| S02 | `33d234463f4341af9ad4931c67a3c561` | 2026-08-23 | **PASS** | 5/5 |
| S03 | `d86bb4fe0cca4dd8a843a6069dc00c5b` | 2026-08-31 | **PASS** | 9/9 |
| S04 | `dc67d06fc5454b0984f4bb95e7ee565b` | 2026-08-31 | **PASS** | 9/9 |
| ratios | (estado persistido, §10) | — | 3 `CALCULADO` + 1 `NOT_CALCULABLE` con motivo | — |

**6/6 etapas en `PASS`, ninguna con un check bloqueante en rojo.** Nótese
que **no son de la misma corrida encadenada**: S00 es de una fecha, S01 de
hoy, S02 del 23/08, S03/S04 encadenados entre sí el 31/08. Esto es
correcto para el diseño del sistema (cada etapa busca "la última corrida
con gate PASS" de la anterior, no exige que todo el pipeline haya corrido
en una sola sesión) — pero significa que **"YPF está en verde" es una
composición de evidencias de fechas distintas, no una sola corrida
end-to-end de hoy**. Ver §13 para qué pasó al intentar refrescarlas todas
hoy mismo.

---

## 13. Idempotencia

Esta sección es la que menos salió como estaba escrito en el runbook.
**Se documenta exactamente lo que ocurrió, sin suavizarlo.**

### 13.1 · S00 — falla reproducible en la segunda corrida

```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```

**Resultado esperado** (según `02_SEC_EDGAR_E2E_RUNBOOK.md`): *"Demostrada:
la segunda corrida aplica 0 migraciones ... y vuelve a dar `PASS`."*

**Resultado real, obtenido hoy:**
```
psycopg2.errors.UniqueViolation: duplicate key value violates unique
constraint "ux_checkpoints_reuse"
DETAIL: Key (stage_id, input_hash, code_version, contract_version)=
(S00_bootstrap, 5e9be1c988db9025fa90868965984f8dc060c7539358949b0b6c9ca55fc31787,
s0-bootstrap-v1, engine-state-v1) already exists.
```
Exit code `1` (excepción no controlada; la corrida queda `ABORTED`).

**Causa, verificada leyendo `s00_smoke.py` línea por línea:** cuando el
gate da `PASS`, el script hace un `INSERT INTO engine.checkpoints (...)`
**incondicional**, sin `ON CONFLICT`. La restricción única
`ux_checkpoints_reuse` es sobre `(stage_id, input_hash, code_version,
contract_version)` — **no** sobre `checkpoint_id` (que sí es aleatorio
cada vez). Como `input_hash` es `sha256(settings.describe())`, con la
misma configuración da el mismo hash siempre, y la segunda vez la
inserción choca contra la primera. **No hay reuso de checkpoint: hay un
choque de clave.**

El último checkpoint que sí se guardó con éxito es de **2026-09-02**
(`checkpoint_id=61ce927b2eed43128fc4e184290de638`) — el mismo que cité
como referencia en §12. Cualquier corrida de `s00_smoke.py` desde entonces,
con la misma configuración, falla igual que la de hoy.

### 13.2 · S02 — el mismo defecto, con un matiz importante

```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py --cik 0000904851
```

**Resultado real:** el mismo patrón — `duplicate key value violates unique
constraint "ux_checkpoints_reuse"`, esta vez `stage_id=S02_fetch`, con
`input_hash=63c720619a9ba899a9ed510b222ecedf563e5fcfc7445d4924fffe5785e1017e`
— **el mismo `input_hash` que aparece como `hash_in` en el `report`
certificado del 23/08** (§4), confirmando que el choque es exactamente
contra ese checkpoint anterior.

**El matiz:** el trabajo real de la etapa **sí se ejecutó y sí persistió**
antes de llegar al `INSERT` que falla. `fetch_raw.download_log` para este
CIK pasó de 740 a **927** filas durante esta misma corrida — 187 artefactos
nuevos, extendiendo la cobertura a filings de 2002-2013 que antes no
estaban. **Los datos quedaron bien; el registro de la corrida (el
`report` y el checkpoint) se perdió** porque el `INSERT` que falla está en
la misma transacción que el `UPDATE` que guarda el `report` — al
revertirse la transacción, se pierde el `report`, pero el fetch de
artefactos, que ya había hecho `commit` antes, sobrevive.

### 13.3 · S03 — diseñado correctamente, verificado en el código; **no reverificado en vivo**

A diferencia de S00/S02, `s03_parse_ypf.py` **sí** protege el `INSERT`:

```sql
INSERT INTO engine.checkpoints (...) VALUES (...)
ON CONFLICT ON CONSTRAINT ux_checkpoints_reuse
  DO UPDATE SET checkpoint_id=EXCLUDED.checkpoint_id, run_id=EXCLUDED.run_id, ...
```
(`scripts/engine/s03_parse_ypf.py`, líneas 793-797 — con un comentario
explícito: *"re-corrida con mismo input+code+contract es un 'checkpoint
hit' por diseño"*).

**Se intentó verificarlo en vivo hoy** con
`s03_parse_ypf.py --cik 0000904851`. Dos invocaciones quedaron corriendo en
paralelo por un error operativo propio de esta sesión (un primer intento
alcanzó el timeout de la herramienta a los 3 minutos sin haber terminado,
y se relanzó una segunda vez en segundo plano sin confirmar que la primera
hubiera muerto). Con dos procesos escribiendo sobre el mismo CIK a la vez,
se decidió **terminarlos manualmente** (`kill -TERM`) en vez de dejarlos
competir contra el conjunto de datos certificado — el costo de un resultado
sucio superaba el valor de completar la demostración en esta sesión.

**Consecuencia:** §5 sigue respaldada por la corrida certificada del
31/08 (`hash_out=a05cb59c...`), que **no se tocó ni se invalidó** — se
verificó después de terminar los procesos que `derived.fact` para
`cik='0000904851'` sigue en 47.930 filas vigentes, igual que antes de
este intento. Pero **la propiedad de idempotencia de S03 queda respaldada
por lectura de código en esta verificación, no por una segunda corrida
en vivo**. El procedimiento documentado en
`appendices/GOLDEN_RUNS.md` (anotar el `hash_out`, re-correr, comparar)
sigue siendo válido — no se ejecutó de punta a punta hoy.

### 13.4 · Efecto colateral: corridas huérfanas

Los dos `kill -TERM` de §13.3 dejaron **2 corridas en `RUNNING`** en
`engine.runs` (`d3f94f7931be4f14b237280b7d820d91`,
`4213c4b981ae4e76839aeddc22dec45e`) — exactamente el escenario que
`s00_smoke.py` (`edb.corridas_huerfanas`) y `s04_normalize.py` (guard
`F-009`) están diseñados para detectar. No se intervino sobre esas filas:
`engine.runs` es un registro de eventos, no hay procedimiento de limpieza
documentado (`L-3`, sin rollback), y no correspondía inventar uno para
esta verificación.

### 13.5 · Lectura honesta

**Idempotencia demostrada:** S03 (por diseño de código; no re-ejecutada
hoy) y S04 (por versionado `valid_to`, verificado indirectamente: el conteo
de vigentes coincide exactamente con `emitidos` de la corrida certificada,
sin duplicados). **Idempotencia NO demostrada, y activamente refutada
hoy:** S00 y S02 — una segunda corrida con la misma configuración termina
en excepción, no en un `PASS` silencioso. El runbook actual afirma lo
contrario para las dos.

---

## 14. Certificación

Contra los 6 criterios de `docs/runbooks/07_CERTIFICATION.md` §3:

| # | criterio | YPF hoy |
|---|---|---|
| 1 | Todas las etapas con gate `PASS` | **Sí** — 6/6 (§12), pero de corridas en fechas distintas, no de una sesión única (ver §12, nota) |
| 2 | `engine.runs.status = 'OK'` | **No, sin matiz** — hay corridas `ABORTED` (los intentos de S00/S02 de hoy, §13.1-13.2) y `RUNNING` huérfanas (§13.4) generadas en esta misma verificación. Las corridas certificadas de referencia (S02 23/08, S03/S04 31/08) sí están `OK` |
| 3 | Idempotencia demostrada | **Parcial** — S04 sí (indirecto), S03 por diseño de código sin reverificación en vivo, **S00 y S02 refutada** (§13.5) |
| 4 | Provenance completa | **Verificada sobre una muestra de 1** (§11) — el hecho `Assets` 2025-12-31 cierra hasta SHA256. No se corrió una verificación exhaustiva de los 47.930 hechos |
| 5 | Producción intacta | **Sí** — `pg_namespace` de `catalaxia-db` (5432) devuelve únicamente `public`, verificado hoy |
| 6 | `screener.db` intacto | **No verificado en esta sesión** — ninguno de los comandos corridos hoy lo toca (S00-S04/ratio_engine son PostgreSQL puro), así que no hay razón para que haya cambiado, pero no se tomó una huella antes/después para confirmarlo |

**Veredicto de esta verificación: YPF sigue siendo el piloto con la
cadena más sólida de los tres** (S02→S03→S04 certificados y encadenados
entre sí, provenance verificable hasta SHA256, ratios calculados con
motivo explícito donde no aplican) — **con dos matices que no estaban
documentados antes de hoy**: S00 y S02 no son realmente idempotentes tal
como está el código (§13.1-13.2), y una corrida end-to-end de una sola
sesión, hoy, no se completó limpiamente (§13.3-13.4). Ninguno de los dos
invalida los datos ya certificados; los dos son defectos operativos reales
que un operador nuevo va a encontrar si sigue el runbook al pie de la
letra.

---

## 15. Hallazgos de esta verificación (no estaban documentados antes)

| # | hallazgo | severidad | evidencia |
|---|---|---|---|
| H-1 | `s00_smoke.py` no es idempotente: la segunda corrida exitosa con la misma configuración siempre falla con `UniqueViolation` sobre `ux_checkpoints_reuse` | media — no pierde datos, pero contradice la documentación y deja la corrida `ABORTED` | §13.1, traceback completo reproducido |
| H-2 | `s02_fetch_ypf.py` tiene el mismo defecto — y además, cuando falla, **pierde el `report` de una corrida cuyo trabajo de fetch sí se completó** (187 artefactos nuevos persistidos) | media-alta — el dato queda bien pero la auditoría de esa corrida específica se pierde | §13.2, conteo antes/después de `fetch_raw.download_log` |
| H-3 | `s03_parse_ypf.py` **sí** implementa el patrón correcto (`ON CONFLICT ... DO UPDATE`) que a H-1/H-2 les falta — es la referencia de cómo debería estar escrito el `INSERT` de checkpoint en las otras etapas | informativo | lectura directa de código, líneas 793-797 |
| H-4 | el bloque de identidad que imprime `s01_identity.py` reporta `cuit: null` para YPF aunque `identity_v1.identifier` sí tiene el CUIT `30546689979` con estado `VERIFIED` — reporta contra el esquema legacy, no contra `identity_v1` | baja — no es un dato faltante, es una fuente de lectura distinta a la que un operador esperaría | §1 |

Ninguno de los cuatro se corrigió en esta sesión — se documentan, como
pide el encargo, no se arreglan.
