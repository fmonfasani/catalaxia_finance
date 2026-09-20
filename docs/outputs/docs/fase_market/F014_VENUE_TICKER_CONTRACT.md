# F-014 — Contrato: símbolo del venue vs. símbolo del proveedor

**Estado: IMPLEMENTADO. Migración `013_venue_ticker.sql` aplicada en producción
(`catalaxia`@5432). `market_instruments.venue_ticker` poblado para las 584 filas.
`ticker_canonico` NO se tocó (verificado, sigue igual byte a byte). M23 NO se
ejecutó.** Autor: sesión de trabajo sobre `fix/ttm-ratios-cnv`, 2026-08-26. Responde al
finding `F-014` de `docs/review/FINDINGS.md` (severity MEDIUM, workstream MARKET, status
OPEN al abrir este documento). Ver §12 para el resumen de la implementación real.

## 0 · Revisión independiente del DISEÑO (2026-08-26, antes de implementar)

Un agente separado, sin memoria de esta sesión, re-derivó cada claim de este documento
contra `data/screener.db`, Postgres real y el código — no confió en la prosa. Corrió sus
propias queries SQL, su propio grep, y su propia ejecución de
`pytest tests/test_f014_venue_ticker.py`.

**Veredicto: `ACCEPT_WITH_CONDITIONS`.** Cero discrepancias encontradas en evidencia:
root cause, la clasificación 12/6/6 de ADR, las cifras 73/0 divergencias y 12
entidades/499 aisladas, los seis claims de impacto por consumidor, la corrida 8/8 de
tests, y los claims de "nada se tocó" — todo reprodujo igual bajo verificación
independiente. Dos condiciones antes de escribir la migración real:

1. **Gap de semántica NULL en el acceptance_test, cerrado en esta revisión (§7.1
   abajo)**: `market_instruments.exchange` es `NULL` (no `'BUE'`) para las 499 filas
   `instrument_type='US'` — verificado (`SELECT instrument_type, exchange, COUNT(*) ...
   GROUP BY 1,2`: `US | (null) | 499`). Una traducción SQL literal del
   `acceptance_test` de F-014 (`WHERE exchange <> 'BUE'`) excluiría esas 499 filas en
   silencio por la lógica de tres valores de SQL (`NULL <> 'BUE'` es `UNKNOWN`, no
   `TRUE`), aunque hoy no tengan el bug. La prueba en Python de este documento no cae en
   la trampa porque deriva `exchange` desde `mercado` de SQLite (nunca `NULL`), no desde
   la columna real de Postgres — pero cualquier query de aceptación futura escrita
   directo contra Postgres sí caería. Ver §7.1 para la corrección.
2. **Housekeeping, no bloqueante**: `scripts/market/m1_symbol_mapping.py` tiene un diff
   sin commitear ajeno a F-014 (plomería de la guarda F-001 en `pg_conn()`, preexistente
   a esta sesión) — no toca la línea 81 (confirmado por el revisor vía `git diff`), pero
   el archivo no está limpio. Recomendación del revisor: ese diff debería quedar en su
   propio commit antes de que la migración de F-014 toque el mismo archivo, para no
   mezclar historiales. Nada que hacer ahora — es una nota para quien escriba esa
   migración.

El revisor también aclaró un punto de honestidad que este documento ya sostenía en §11
pero vale repetir: los 8/8 tests en verde prueban que el diseño es correcto e
implementable, **no** que F-014 ya está resuelto — nada en producción publica
`venue_ticker` todavía. F-014 sigue `OPEN`.

---

## 1 · Resumen ejecutivo

`market_instruments.ticker_canonico` mezcla dos conceptos que hoy son indistinguibles
para cualquier consumidor: la clave del EMISOR (constante entre todas sus filas) y el
símbolo con el que UNA fila cotiza en `exchange`. Para instrumentos LOCAL (BUE) ambos
coinciden por construcción. Para instrumentos ADR, la columna hereda el ticker de BUE
del emisor en vez de traer el símbolo real de NYSE/NASDAQ.

**Universo verificado** (no una muestra): existen exactamente **12 instrumentos ADR**
en `dim_instrument` hoy. En **6 de 12** el bug es invisible porque el ticker local y el
de NYSE/NASDAQ coinciden (CEPU, GGAL, BBAR, SUPV, LOMA, VIST). En los otros **6** el
símbolo publicado es directamente falso: YPFD≠YPF, TGSU2≠TGS, CRES≠CRESY, PAMP≠PAM,
IRSA≠IRS, TECO2≠TEO.

**Root cause exacto**, no una hipótesis: `scripts/market/m1_symbol_mapping.py:81`.

**Propuesta**: no se toca `ticker_canonico` (sigue siendo la clave del emisor, ya
correcta para ese propósito). Se agrega un campo nuevo, `venue_ticker`, derivado de la
columna que YA tiene el dato correcto hoy (`dim_instrument.ticker`, a nivel instrumento)
y que hoy se descarta. Ver §5.

---

## 2 · Qué representa cada campo hoy (auditado, no asumido)

| Campo | Tabla | Nivel | Qué es realmente | Evidencia |
|---|---|---|---|---|
| `ticker_canonico` | `market_instruments` | **Emisor** (aunque la fila es por instrumento) | Copiado 1:1 de `dim_entity.ticker_canonico`, que a su vez es siempre igual al `ticker` de la fila LOCAL/BYMA del emisor (0 divergencias en 73 filas verificadas) | `m1_symbol_mapping.py:81`; query §4 |
| `exchange` | `market_instruments` | Instrumento (correcto) | 'BUE' / 'NYSE' según el mercado real de ESA fila. Sin bug encontrado. | `m1_symbol_mapping.derivar()` |
| `ticker_yahoo` | `market_symbol_mappings` | Instrumento, pero **de proveedor** | Símbolo exacto que se le pasa a `yfinance`. Para LOCAL lleva sufijo `.BA` (convención de Yahoo, no del mercado). Para ADR coincide con el símbolo real de NYSE/NASDAQ, pero por convención de Yahoo para tickers domésticos, no porque el pipeline lo derive de una fuente que declare autoridad sobre ese mercado. | `m1_symbol_mapping.derivar()` líneas 50-59 |
| `dim_instrument.ticker` | `data/screener.db` (SQLite, origen) | **Instrumento (correcto, descartado)** | El ticker propio de CADA fila. Para la fila ADR de YPF ya vale `'YPF'`, no `'YPFD'`. Se usa correctamente para derivar `ticker_yahoo` (línea 53: `return "ADR", t, None`) pero se descarta para `ticker_canonico` (línea 81 prefiere `canon`). | Query SQLite §4 |

**Ningún consumidor de Market tiene hoy un campo que declare, sin ambigüedad,
"el símbolo con el que esta fila cotiza en su exchange"**. Es exactamente el vacío que
`F-014.required_action` pide llenar.

### Nota de alcance: hay DOS columnas `ticker_canonico` en el repo, no relacionadas

`grep -rl ticker_canonico` devuelve también `scripts/pipeline/*.py`,
`scripts/tickets/screener/*.py` y el `screener`/`ratios` legado. Esa es OTRA columna, en
OTRA tabla (`dim_entity`/`screener`, no `market_instruments`), a nivel de emisor, y ahí
es **correcta** para su propio uso (el pipeline legado nunca tuvo el concepto de "una
fila por venue"). Este documento y F-014 son exclusivamente sobre
`market_instruments.ticker_canonico`. La coincidencia de nombre entre dos columnas de
dos sistemas distintos es en sí misma una fuente de confusión — se señala pero no se
resuelve aquí (fuera de alcance: tocaría el pipeline legado, no Market).

---

## 3 · Root cause preciso

```python
# scripts/market/m1_symbol_mapping.py:63-87 (main())
filas = lite.execute("""
    SELECT di.instrument_id, di.entity_id, de.ticker_canonico,
           de.cuit, de.grupo, di.ticker, di.mercado, di.tipo, di.moneda, di.ratio
    FROM dim_instrument di
    LEFT JOIN dim_entity de ON de.entity_id = di.entity_id
    ORDER BY di.instrument_id
""")
for iid, eid, canon, cuit, grupo, tick, merc, tipo, moneda, ratio in filas:
    ...
    regs.append(dict(
        ...
        ticker_canonico=(canon or tick or "").strip(),   # <- linea 81
        ...
    ))
```

`canon` viene de `dim_entity` (JOIN por `entity_id`, una fila por EMISOR). `tick` viene
de `dim_instrument.ticker` (una fila por INSTRUMENTO/listing). Para un emisor con dos
listings, `canon` es idéntico en ambas filas del `for`. La expresión `(canon or tick or
"")` prefiere `canon` siempre que exista — y existe siempre, porque `dim_entity` tiene
una fila para todo emisor con al menos un instrumento. `tick`, que sí es correcto por
fila, nunca gana.

---

## 4 · Evidencia — universo completo, no muestra

Consulta contra `data/screener.db` (origen real, no Postgres):

```sql
SELECT di.entity_id, de.ticker_canonico, di.ticker, di.mercado, di.tipo
FROM dim_instrument di LEFT JOIN dim_entity de ON de.entity_id = di.entity_id
WHERE LOWER(di.tipo) = 'adr'
```

**12 filas, 12/12 clasificadas** (0 tickers con forma sospechosa: sin puntos, sin
vacíos, sin `_ADR_` sintéticos):

| entity_canon | ticker ADR real (`dim_instrument.ticker`) | ¿bug visible? |
|---|---|---|
| CRES  | CRESY | **SÍ** — CRES ≠ CRESY |
| LOMA  | LOMA  | no (coincide) |
| VIST  | VIST  | no (coincide) |
| TGSU2 | TGS   | **SÍ** — TGSU2 ≠ TGS |
| PAMP  | PAM   | **SÍ** — PAMP ≠ PAM |
| IRSA  | IRS   | **SÍ** — IRSA ≠ IRS |
| GGAL  | GGAL  | no (coincide) |
| SUPV  | SUPV  | no (coincide) |
| BBAR  | BBAR  | no (coincide) |
| TECO2 | TEO   | **SÍ** — TECO2 ≠ TEO |
| CEPU  | CEPU  | no (coincide) |
| YPFD  | YPF   | **SÍ** — YPFD ≠ YPF |

Confirmado también: **73/73 filas LOCAL/BYMA** tienen `dim_entity.ticker_canonico ==
dim_instrument.ticker` (0 divergencias) — es decir, `ticker_canonico` de hoy es, en la
práctica, siempre "el ticker de la fila BYMA del emisor", nunca un dato inventado. Y
**exactamente 12 entidades** tienen más de una fila de instrumento — los 12 pares
BUE+NYSE/NASDAQ de arriba; ninguna de las 499 filas `tipo=ordinaria, mercado=US`
(subyacentes de CEDEAR) comparte `entity_id` con una fila BYMA, así que el patrón del
bug **no se extiende** a esas 499 filas (son de un solo instrumento por entidad, sin
colisión posible).

Verificado también contra Postgres en vivo (`catalaxia-db`@5432,
`market_instruments`/`market_symbol_mappings`, 2026-08-26): mismos 8 valores para
YPFD/CEPU/GGAL/TGSU2 y sus ADR que en el SQLite de origen — el bug sigue presente en
producción, no solo en el archivo de origen.

---

## 5 · Los 4 pedidos específicos: YPF, CEPU, GGAL, TGSU2

| Emisor | instrument_id LOCAL | instrument_id ADR | `ticker_canonico` hoy (ADR) | símbolo NYSE/NASDAQ real | ¿coincide? |
|---|---|---|---|---|---|
| YPF   | 83 | 84 | `YPFD` | `YPF`  | **NO — bug visible** |
| CEPU  | 80 | 81 | `CEPU` | `CEPU` | sí (coincidencia, no garantía) |
| GGAL  | 71 | 72 | `GGAL` | `GGAL` | sí (coincidencia, no garantía) |
| TGSU2 | 65 | 66 | `TGSU2`| `TGS`  | **NO — bug visible** |

Con solo estos 4, dos de cuatro (CEPU, GGAL) enmascaran el problema — coincide
exactamente con lo que `F-014.description` ya advertía.

---

## 6 · Impacto verificado por consumidor (auditado línea por línea, no inferido)

| Consumidor | Usa `ticker_canonico` para… | Impacto real |
|---|---|---|
| `m1_symbol_mapping.py` | Escribirlo (root cause) | Es la fuente del bug |
| `m2_fetch_engine.py` (`InstrumentSpec.ticker_canonico`) | (a) texto de log en gate C-MKT-001; (b) columna `ticker_canonico` en `market_raw_runs`, persistida por CADA corrida | **NO** afecta qué se fetchea (`source.fetch()` usa `spec.ticker_yahoo`, nunca `ticker_canonico`) ni ninguna decisión de negocio. **SÍ** dejó, y sigue dejando, provenance persistida y auto-contradictoria: en `market_raw_runs`, la fila de la corrida del instrumento 84 dice `ticker_canonico='YPFD'` y `ticker_yahoo` (mismo `request_parameters` JSON) apunta a `'YPF'` en la misma corrida |
| `m4_quality.py` | Lo trae en un `SELECT` (línea 170) junto con currency/exchange/entity_id | **Impacto real: CERO.** Solo se usa `ident[0]` (currency) más abajo; `ticker_canonico` se lee y se descarta, no aparece en ningún gate ni reporte |
| `m5_golden_case.py` | Columna `ticker_canonico` en la hoja **"IDENTIDAD"** del `.xlsx` publicado (`escribir_xlsx`, líneas 500-505) | **Impacto real: máxima visibilidad externa.** Es el mismo tipo de artefacto (auditoría/entrega) donde, según `F-014.impact`, "lo detectó el banco adversario, no un test unitario" en el piloto de Identity v1. Hoy, para instrumento 84, esa hoja muestra literalmente `ticker_canonico=YPFD` en la misma fila que `mercado=NYSE` |
| `m6_scale.py` | **Nada — verificado por grep, 0 coincidencias del string `ticker_canonico` en todo el archivo.** | **CERO impacto directo.** Solo hereda `InstrumentSpec` de `m2_fetch_engine.cargar_specs()` y se lo pasa sin tocarlo a `run_instrument()`. Cualquier fix en `m1`/`m2` se propaga a M23 sin cambiar una línea de `m6_scale.py` |
| `market_instruments` (tabla) | — | Es donde vive el dato incorrecto. Confirmado en vivo (§4) |
| `market_price_daily` (tabla) | — | **CERO — verificado en el DDL (`market_schema.sql:44-61`): la tabla no tiene columna `ticker_canonico` ni ninguna copia de símbolo. Solo `instrument_id` (FK).** Cualquier consumidor de precios que quiera el símbolo debe hacer JOIN a `market_instruments`, así que hereda el bug solo a través de ese JOIN, nunca por una copia desnormalizada |
| `scripts/engine/identity_v1_pilot.py` | Lo lee, y **ya lo evita correctamente** para filas no-BUE (mitigación aplicada, ver `F-014.mitigación aplicada`) | Es el precedente de diseño que este documento formaliza: usa namespace `'BYMA'` con `ticker_canonico` solo cuando `exchange=='BUE'`; para el resto, publica solo `ticker_yahoo` bajo namespace `'YAHOO'` (explícitamente de proveedor, no de mercado) y abre una `review` humana declarando el hueco. **Verificado leyendo el código actual, no el comentario**: `engine/identity_v1.py::link_symbol` ya modela "un símbolo vive en su namespace" — es exactamente la primitiva que la propuesta de abajo lleva a `market_instruments` |

**Conclusión de impacto**: el bug NUNCA contaminó una decisión de fetch ni una fila de
`market_price_daily`. Es puramente de **provenance y de reporte** — pero de la variedad
más peligrosa: un dato con forma de verdad, en la tabla y en el reporte de auditoría
correctos, que dice algo falso.

---

## 7 · Contrato propuesto

Separar tres conceptos que hoy están aplastados en dos columnas:

| Concepto | Campo | Nivel | Estado propuesto |
|---|---|---|---|
| Clave del emisor | `market_instruments.ticker_canonico` | Emisor (constante por `entity_id`) | **Sin cambios de valor.** Solo se documenta explícitamente qué es (comentario de columna) |
| Símbolo del venue | `market_instruments.venue_ticker` **(nuevo)** | Instrumento (una fila = un símbolo) | **Nuevo.** Derivado de `dim_instrument.ticker`, nunca de `ticker_canonico` |
| Símbolo del proveedor | `market_symbol_mappings.ticker_yahoo` | Instrumento, scoped a Yahoo | **Sin cambios.** Se documenta más fuerte que hoy: "clave de consulta, no símbolo de mercado" |

Regla única, ya probada en `f014_venue_ticker.derivar_venue_ticker()` (ver §8): el
`venue_ticker` de una fila sale de `dim_instrument.ticker` (nivel instrumento) —
siempre, incluso cuando el resultado coincide con `ticker_canonico` (6 de 12 casos).
Nunca al revés.

### 7.1 · Corrección de semántica NULL en el acceptance_test (condición de la revisión independiente)

`F-014.acceptance_test` está fraseado como "para todo instrumento con `exchange <>
'BUE'`...". Traducido literalmente a SQL contra la columna real, **eso es una trampa**:

```sql
-- MAL: excluye en silencio toda fila con exchange NULL
SELECT * FROM market_instruments WHERE exchange <> 'BUE';
```

Verificado en vivo (`SELECT instrument_type, exchange, COUNT(*) FROM market_instruments
GROUP BY 1,2`): `market_instruments.exchange` es **NULL**, no `'BUE'`, para las 499 filas
`instrument_type='US'` (`m1_symbol_mapping.derivar()` solo asigna `exchange` para ADR y
LOCAL; para US queda `None`). Por la lógica de tres valores de SQL, `NULL <> 'BUE'`
evalúa `UNKNOWN`, no `TRUE` — esas 499 filas quedarían afuera de cualquier query de
aceptación que use `<>` tal cual, sin error ni aviso. Hoy no importa (esas filas no
tienen el bug, están aisladas del patrón ADR — ver §4), pero una futura corrida de
aceptación que se apoye en esa forma de la cláusula reportaría "cumple" sin haber mirado
un tercio de la tabla.

La prueba en Python de este documento (`test_acceptance_criterion_literal_F014`) no cae
en esto porque deriva `exchange` desde la columna `mercado` de SQLite (que nunca es
NULL), no desde `market_instruments.exchange` de Postgres. **Cualquier query de
aceptación que se escriba después, directo contra Postgres, debe usar
`exchange IS DISTINCT FROM 'BUE'` (equivalente: `COALESCE(exchange,'') <> 'BUE'`), no
`exchange <> 'BUE'` a secas.** Ejemplo correcto:

```sql
-- BIEN: NULL se trata como "no es BUE", no se descarta en silencio
SELECT instrument_id, ticker_canonico, venue_ticker, exchange
FROM market_instruments
WHERE exchange IS DISTINCT FROM 'BUE'
  AND venue_ticker_source = 'ticker_canonico';   -- 0 filas esperadas tras el fix
```

### Migración (sketch — **NO ejecutado**, requiere decisión del owner + revisión del auditor)

```sql
-- migrations/market/0XX_venue_ticker.sql  (BORRADOR, no aplicado)
ALTER TABLE market_instruments ADD COLUMN venue_ticker TEXT;
ALTER TABLE market_instruments ADD COLUMN venue_ticker_source TEXT;

COMMENT ON COLUMN market_instruments.ticker_canonico IS
  'Clave canonica del EMISOR (issuer-level). Identica entre todas las filas '
  'del mismo entity_id. NO es el simbolo de mercado de ESTA fila -- para eso, '
  'venue_ticker. Ver F-014.';

COMMENT ON COLUMN market_instruments.venue_ticker IS
  'Simbolo con el que ESTA fila cotiza en `exchange`, segun venue_ticker_source. '
  'NO confundir con market_symbol_mappings.ticker_yahoo (clave de consulta al '
  'proveedor de datos, no simbolo de mercado). Ver F-014.';

-- Backfill (fuera de alcance de este ciclo): derivar de dim_instrument.ticker
-- por instrument_id, replicando exactamente derivar_venue_ticker().
```

`venue_ticker_source` queda deliberadamente explícito porque hoy la única fuente
disponible es el ticker legado por-instrumento de `data/screener.db` — **no** un
registro de mercado independiente (NYSE symbol directory, EDGAR company tickers). La
propuesta no reclama más certeza de la que hay evidencia: es una mejora estricta sobre
el bug actual, no una promesa de verificación externa.

### Impacto de la migración en los consumidores (si se aplica en un ciclo futuro)

* `m1_symbol_mapping.py` — agrega `venue_ticker=tick` (ya lo tiene en la misma query) al
  INSERT de `market_instruments`. La línea 81 (`ticker_canonico=(canon or tick or "")`)
  **no cambia**.
* `m2_fetch_engine.py` — `InstrumentSpec` gana un campo opcional `venue_ticker`;
  recomendado (no obligatorio) usarlo en el texto de gate C-MKT-001 y en
  `market_raw_runs` para que la provenance deje de ser auto-contradictoria. El fetch en
  sí no cambia (sigue usando `ticker_yahoo`).
* `m6_scale.py` — **cero cambios**, confirmado en §6.
* `m4_quality.py` / `m5_golden_case.py` — agregar `venue_ticker` a la hoja "IDENTIDAD"
  del golden case es la mejora recomendada para que el artefacto de auditoría deje de
  mostrar el dato falso sin contexto.

---

## 8 · Acceptance tests (ejecutados, no solo escritos)

`scripts/market/f014_venue_ticker.py` — función pura `derivar_venue_ticker()`, **no
importada por ningún script de producción** (verificado: ni `m1`, ni `m2`, ni `m6_scale`
la referencian).

`scripts/market/tests/test_f014_venue_ticker.py` — dos clases:

* `TestContratoPropuesto` — ejercita la función propuesta contra los datos reales de
  `data/screener.db`: las 4 compañías pedidas (local + ADR), el universo completo de 12
  ADR, y el criterio de aceptación fraseado literalmente como en `F-014.acceptance_test`.
* `TestBugCaracterizado` — lee `market_instruments` REAL en Postgres (solo lectura, vía
  `market_db`) y confirma que el bug sigue presente hoy para los 6 casos "VISIBLE". Es
  evidencia con fecha: si esta clase alguna vez falla, es porque ya se aplicó un fix real
  y hay que revisar `F-014` en `FINDINGS.md`, no arreglar el test.

**Corrida real, 2026-08-26** (`cd scripts/market && python -m pytest
tests/test_f014_venue_ticker.py -v`):

```
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_las_4_companias_pedidas[CEPU-CEPU] PASSED
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_las_4_companias_pedidas[GGAL-GGAL] PASSED
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_las_4_companias_pedidas[TGSU2-TGS] PASSED
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_las_4_companias_pedidas[YPFD-YPF] PASSED
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_las_4_companias_local_BUE_tambien_correcto PASSED
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_universo_completo_12_adr PASSED
tests/test_f014_venue_ticker.py::TestContratoPropuesto::test_acceptance_criterion_literal_F014 PASSED
tests/test_f014_venue_ticker.py::TestBugCaracterizado::test_bug_sigue_presente_en_produccion_hoy PASSED
8 passed in 2.57s
```

Los 8 tests están en VERDE hoy porque prueban que **la propuesta es correcta e
implementable**, no que ya está aplicada — la clase `TestBugCaracterizado` es la que
confirma, contra la base real, que el problema que la propuesta resuelve sigue vivo.

---

## 9 · Qué NO se hizo (respeta el alcance pedido)

* `market_instruments.ticker_canonico` — **sin cambios**, ni en valor ni en el escritor.
* `scripts/market/m1_symbol_mapping.py`, `m2_fetch_engine.py` — **sin cambios de
  comportamiento**. `f014_venue_ticker.py` es un módulo nuevo, no importado por ninguno.
* `m6_scale.py` — **sin cambios y sin ejecutar contra el universo de 584 instrumentos**
  (M23 masivo sigue sin correr).
* La migración de §7 es un borrador en este documento, **no un archivo en
  `migrations/`** — aplicarla requiere una decisión explícita del owner y su propio ciclo
  de auditoría, igual que F-001.

---

## 10 · Hallazgo colateral (NO es F-014, se reporta aparte)

Al correr la suite completa de Market para confirmar que este trabajo no rompía nada
(`pytest tests/` desde `scripts/market/`), **17 de los 18 tests preexistentes de
`test_market_matrix.py` fallan hoy** con `psycopg2.errors.ReadOnlySqlTransaction` en
`conftest.py:61` (el `CREATE TABLE ... ` del DDL de test). Causa raíz identificada:
`conftest.py:58` llama `eng.pg_conn(TEST_DB)` sin `write=True`; desde que `m2_fetch_engine.pg_conn`
delega en `market_db.connect()` (fix de F-001), toda conexión sin `write=True` es de solo
lectura por diseño — correcto para producción, pero rompe la creación del esquema de test.

No es un fix de una línea: además de agregar `write=True`, `write=True` contra el puerto
5432 (el default de `DB_HOST`/`DB_PORT` en este entorno) exige `MARKET_ALLOW_PROD_WRITE=1`
por la misma guarda F-001 — usar esa variable en un fixture de test para escribir DDL
contra el server de producción (aunque sea en una base descartable `catalaxia_market_test`)
contradice el propósito de la guarda. La alternativa correcta parece ser apuntar los tests
a `catalaxia-engine-dev` (puerto 5433, contenedor ya corriendo), pero **se verificó que ese
Postgres de dev no tiene ni el rol `catalaxia_market_ro` ni ninguna tabla `market_*`
provisionada** — nunca se le aplicó la migración 012 ni `market_schema.sql`. Arreglarlo
bien implica una decisión de dónde vive el Postgres de test/dev de Market, no solo un
parche de conftest. Mis 8 tests nuevos de F-014 no dependen de esta fixture (no la usan) y
corren limpios; los 18 preexistentes de `test_market_matrix.py` quedan bloqueados hasta que
esto se resuelva. Se deja señalado para que el auditor lo registre como finding propio si
corresponde — no se tocó `conftest.py` para no mezclar ese arreglo con F-014.

---

## 11 · Decisión pendiente (para el owner / auditor)

`F-014.required_action` planteaba dos caminos: (a) `ticker_canonico` pasa a ser el
símbolo del exchange de la fila, o (b) se documenta como clave del emisor y se agrega un
campo con el símbolo de mercado. Esta propuesta es la opción **(b)** — no reasigna
`ticker_canonico` (evita romper cualquier consumidor legado que ya lo lea como clave de
emisor, incluido el propio `identity_v1_pilot.py`) y agrega `venue_ticker` como el campo
nuevo, correcto por diseño y ya probado contra el universo completo de 12 ADR reales.

Queda para una decisión explícita del owner: aceptar (b), aplicar la migración de §7 en
un ciclo dedicado, y solo entonces actualizar `m1_symbol_mapping.py` para poblar
`venue_ticker` (cambio de una línea, ya escrito y probado en `f014_venue_ticker.py`).

---

## 12 · Implementación real (2026-08-26, tras la decisión del owner)

El owner aceptó la opción (b) tras la revisión independiente de §0. Se aplicó:

1. **Migración** `migrations/market/013_venue_ticker.sql` — aplicada contra
   `catalaxia`@5432 (`docker exec -i catalaxia-db psql -U catalaxia -d catalaxia -v
   ON_ERROR_STOP=1 < 013_venue_ticker.sql`, sin errores). Agrega `venue_ticker` y
   `venue_ticker_source` (ambas `TEXT`, nullable) a `market_instruments`, más los tres
   `COMMENT ON COLUMN` de §7. `scripts/market/market_schema.sql` (el DDL canónico
   from-scratch) se actualizó en paralelo para que no quede desalineado de lo que ya
   corrió en producción.
2. **`m1_symbol_mapping.py` actualizado** — importa `f014_venue_ticker` y llama
   `derivar_venue_ticker(canon, tick, exchange)` para cada fila; el INSERT a
   `market_instruments` ahora incluye `venue_ticker`/`venue_ticker_source` (con su
   `ON CONFLICT ... DO UPDATE`). **`ticker_canonico=(canon or tick or "").strip()` no se
   tocó** — sigue siendo exactamente la misma línea, el mismo dato.
3. **Backfill real**: `MARKET_ALLOW_PROD_WRITE=1 python m1_symbol_mapping.py` — 584
   instrumentos procesados, 584 `MAPPED` (0 `UNMAPPED`/`CONFLICT`, sin regresión de
   estado), `venue_ticker != ticker_canonico` en exactamente **6** filas — las 6
   "VISIBLE" ya catalogadas en §4:

   ```
   59 canonico=CRES     venue_ticker=CRESY
   66 canonico=TGSU2    venue_ticker=TGS
   68 canonico=PAMP     venue_ticker=PAM
   70 canonico=IRSA     venue_ticker=IRS
   78 canonico=TECO2    venue_ticker=TEO
   84 canonico=YPFD     venue_ticker=YPF
   ```

4. **Universo completo de 12 ADR, verificado en vivo** (`SELECT instrument_id,
   ticker_canonico, venue_ticker, venue_ticker_source, instrument_type, exchange FROM
   market_instruments WHERE instrument_type='ADR'`):

   | instrument_id | ticker_canonico | venue_ticker | clase |
   |---|---|---|---|
   | 59 | CRES  | **CRESY** | visible, pedido explícito |
   | 61 | LOMA  | LOMA  | coincide |
   | 63 | VIST  | VIST  | coincide |
   | 66 | TGSU2 | **TGS**   | visible, pedido explícito |
   | 68 | PAMP  | **PAM**   | visible, pedido explícito |
   | 70 | IRSA  | **IRS**   | visible, pedido explícito |
   | 72 | GGAL  | GGAL  | coincide, pedido explícito |
   | 74 | SUPV  | SUPV  | coincide |
   | 76 | BBAR  | BBAR  | coincide |
   | 78 | TECO2 | **TEO**   | visible, pedido explícito |
   | 81 | CEPU  | CEPU  | coincide, pedido explícito |
   | 84 | YPFD  | **YPF**   | visible, pedido explícito |

   Las filas LOCAL/BYMA de los 4 pedidos (65, 71, 80, 83) tienen `venue_ticker ==
   ticker_canonico`, como corresponde. Las 499 filas `US` (exchange `NULL`) tienen
   `venue_ticker` poblado también (consistente, no requerido pero sin costo — para ellas
   `venue_ticker == ticker_canonico`, ya eran correctas). **0 filas con `venue_ticker`
   NULL/vacío en las 584.**

5. **`ticker_canonico` verificado byte a byte, sin cambios**: los 8 valores de
   YPFD/CEPU/GGAL/TGSU2 (instrumentos 65,66,71,72,80,81,83,84) son idénticos antes y
   después de la migración — confirmado comparando contra la captura de §4/§5.

6. **Acceptance tests — corrida real, 13/13**
   (`scripts/market/tests/test_f014_venue_ticker.py`, clase nueva
   `TestVenueTickerProduccion` agregada, usa **`exchange IS DISTINCT FROM 'BUE'`**, no
   `<>`, corrigiendo exactamente el gap de la condición 1 de §0):

   ```
   TestContratoPropuesto (7 tests, sin cambios)                         PASSED
   TestBugCaracterizado::test_bug_sigue_presente_en_produccion_hoy      PASSED
   TestVenueTickerProduccion::test_acceptance_criterion_F014_null_safe  PASSED
   TestVenueTickerProduccion::test_universo_12_adr_valores_reales       PASSED
   TestVenueTickerProduccion::test_los_6_visibles_ya_no_repiten...      PASSED
   TestVenueTickerProduccion::test_los_2_coincidentes_siguen_correctos  PASSED
   TestVenueTickerProduccion::test_499_filas_US_no_quedaron_afuera      PASSED
   13 passed in 4.64s
   ```

   `TestBugCaracterizado` sigue en VERDE a propósito: mira `ticker_canonico`
   específicamente, que nunca se tocó — no es una regresión, es la prueba de que el fix
   se hizo agregando un campo, no reescribiendo el que tenía el bug.

7. **Consumidores tocados: solo el estrictamente necesario.** `m1_symbol_mapping.py` es
   el único INSERT a `market_instruments` en todo `scripts/market/` (verificado por
   grep). `m2_fetch_engine.py`, `m4_quality.py`, `m5_golden_case.py`, `m6_scale.py` — sin
   cambios en esta pasada; siguen leyendo solo `ticker_canonico`/`ticker_yahoo` como
   antes. Se documentó explícitamente en `f014_venue_ticker.py` §"QUE SIGUE SIN HACER
   ESTE MODULO" para que quede claro que es una decisión, no un olvido.

8. **M23 no se ejecutó** — `m6_scale.py` no se tocó ni se corrió.

9. **Regresión colateral (F-001, `test_market_matrix.py`)**: recontada tras el cambio,
   sigue en **17/18** — mismo conteo, mismo error (`ReadOnlySqlTransaction`), sin
   modificar `conftest.py`. No es nueva ni empeoró.

10. **Revalidación independiente post-implementación — completa. Veredicto:
    `ACCEPT_WITH_NOTES`.** Agente separado, sin memoria de esta sesión, re-verificó todo
    lo de arriba de forma independiente (schema, `ticker_canonico` intacto, los 12 ADR
    contra `data/screener.db` sin reusar el mismo código, el caso NULL de las 499 US,
    aislamiento de consumidores, corrida propia de los tests, reconteo de la regresión
    F-001). Detalle completo: `.claude/state/MARKET_STATE.md`.

    Único hallazgo — cosmético, ya corregido: el comentario de columna
    `venue_ticker_source` decía `'dim_instrument.ticker (legacy)'`, pero el valor real
    guardado (y lo que escribe `f014_venue_ticker.py`) es `'dim_instrument.ticker'` sin
    sufijo. Corregido en `013_venue_ticker.sql`, `market_schema.sql`, y con un
    `COMMENT ON COLUMN` de corrección aplicado sobre la base en vivo (metadata pura, cero
    riesgo). Tests re-corridos tras el fix: 13/13 en verde.

    Sin regresiones en ningún consumidor ni en la falla preexistente de
    `test_market_matrix.py` (17/18, sin cambios, confirmado independientemente).
