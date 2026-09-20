# DAY 3 — IMPLEMENTACIÓN DEL MOTOR CANÓNICO DE RATIOS

**Fecha: 2026-09-01** · `catalaxia_engine@127.0.0.1:5433/catalaxia` · mode FAST · **prod=False**
Sin commits. SEC/EDGAR, CNV, Market e Identity sin modificar.

---

# RATIO_ENGINE_DAY3_GATE = **PASS_WITH_WARNINGS**

F-061 cerrado con evidencia causal. `derived.ratio` en pie con la identidad del
contrato. EV/Sales calculado, persistido y probado en las diez familias. Los
*warnings* son límites declarados del alcance, no defectos abiertos.

---

## 1. F-061 — antes y después

### Antes

```
$ python -m pytest tests/test_f061_ownership.py -q
2 failed, 4 passed

AssertionError: la seleccion adopto hechos del emisor A bajo el cik de B:
{'CurrentLiabilities', 'CurrentAssets'}
AssertionError: estos modulos seleccionan de derived.fact sin verificar pertenencia:
['screener_demo.py', 'matriz_producto.py', 'e2e_producto.py', 'ratios_inventario.py']
```

### Después

```
$ python -m pytest tests/test_f061_ownership.py -v
6 passed in 1.51s

test_el_detector_encuentra_los_hechos_ajenos                    PASSED
test_control_positivo_los_hechos_legitimos_no_se_marcan         PASSED
test_la_mutacion_sin_guarda_readmite_los_hechos_ajenos          PASSED
test_la_base_de_trabajo_cumple_hoy_el_invariante                PASSED
test_la_seleccion_rechaza_hechos_ajenos                         PASSED
test_los_modulos_de_ratios_usan_la_seleccion_canonica           PASSED
```

### El fix

Un punto único: [`scripts/engine/ratio_inputs.py`](../../../scripts/engine/ratio_inputs.py).
Los cuatro módulos traían sus insumos con su propia copia de
`SELECT ... FROM derived.fact WHERE cik = :c`. Ahora declaran columnas y el
`WHERE` lo arma `sql_insumos()`, que incorpora la guarda:

```sql
   AND array_length(d.source_fact_ids, 1) > 0
   AND NOT EXISTS (
         SELECT 1 FROM unnest(d.source_fact_ids) AS gs(fid)
          LEFT JOIN parsed.facts gp ON gp.fact_id = gs.fid
          WHERE gp.fact_id IS NULL
             OR gp.cik <> d.cik
             OR gp.accession_number <> d.accession_number
             OR gp.qname <> d.qname)
```

No usa ticker, ni nombre, ni empresa hardcodeada, ni heurística, ni desempate:
usa la relación de provenance que la ingesta ya deja escrita.

### El ataque AAPL→GGAL, bloqueado en el motor

`test_cross_entity_un_fact_ajeno_no_entra_al_ratio` lo reproduce sobre el motor
real. La víctima es **CEPU**, el único emisor al que le falta exactamente un
concepto (`deuda_financiera`): se le inyecta un `Borrowings` con los punteros de
provenance de AAPL.

```
antes    NOT_CALCULABLE  · falta deuda_financiera
inyeccion: Borrowings con source_fact_ids de AAPL
despues  NOT_CALCULABLE  · falta deuda_financiera   ← el hecho ajeno NO entró
```

### La mutación — el vínculo causal

Dos tests, uno en cada nivel:

| test | qué hace | resultado |
|---|---|---|
| `test_la_mutacion_sin_guarda_readmite_los_hechos_ajenos` | quita la guarda de la consulta | los tags ajenos vuelven: `{Liabilities, CurrentAssets, CurrentLiabilities}` |
| `test_mutation_quitar_la_guarda_readmite_el_fact_ajeno` | quita la guarda del motor | CEPU pasa de `NOT_CALCULABLE` a **`CALCULADO`** con el dato de AAPL |

Si quitar la guarda **no** cambiara el resultado, la protección la estaría dando
otra condición y estos tests no probarían lo que dicen.

### Los 135.077 punteros

```sql
SELECT count(*) FILTER (WHERE puntero_huerfano) AS huerfanos,
       count(*) FILTER (WHERE cik_ajeno)        AS cik_ajeno,
       count(*) FILTER (WHERE filing_ajeno)     AS filing_ajeno,
       count(*) FILTER (WHERE concepto_ajeno)   AS concepto_ajeno
  FROM derived.v_fact_pertenencia;

 punteros | huerfanos | cik_ajeno | filing_ajeno | concepto_ajeno
   135077 |         0 |         0 |            0 |              0
```

**Cero violaciones.** Verificado por `test_la_base_de_trabajo_cumple_hoy_el_invariante`,
que además exige volumen (`> 100.000 punteros`) para que el control no pase por
vacío.

### Nota sobre el nombre de los tests

Los dos que estaban en rojo perdieron el prefijo `f061_rojo` al pasar a verde:
un test permanentemente verde llamado «rojo» es una trampa para quien lo lea
después. El selector `-k "not f061_rojo"` ya no excluye nada, que es exactamente
lo que se buscaba.

---

## 2. Archivos

| archivo | qué |
|---|---|
| `migrations/engine/032_f061_derived_ratio.sql` | **nuevo** — `derived.ratio` + vista `derived.v_fact_pertenencia` |
| `migrations/engine/033_ratio_inputs_solo_si_calculado.sql` | **nuevo** — corrige el alcance de una CHECK de la 032 |
| `scripts/engine/ratio_inputs.py` | **nuevo** — punto único de selección; invariante y guarda |
| `scripts/engine/ratio_engine.py` | **nuevo** — motor canónico; EV/Sales |
| `scripts/engine/screener_demo.py` | modificado — usa `sql_insumos` |
| `scripts/engine/matriz_producto.py` | modificado — ídem |
| `scripts/engine/e2e_producto.py` | modificado — ídem |
| `scripts/engine/ratios_inventario.py` | modificado — ídem |
| `tests/test_f061_ownership.py` | modificado — importa la regla del código vivo; los rojos en verde |
| `tests/test_ratio_engine_ev_sales.py` | **nuevo** — 25 tests, 10 familias |

**Regresión sobre los scripts, no sólo sobre los tests:** `screener_demo.py`
vuelve a correr y da los mismos números que antes del refactor (CEPU P/E
9.3925, AAPL P/B 63.0297, MSFT 28.0589…). El cambio no movió ningún resultado.

---

## 3. Migraciones

Aplicadas por el runner de `engine/db.py`, que es su único dueño (F-049):

```
aplicadas: ['engine/032_f061_derived_ratio.sql']
aplicadas: ['engine/033_ratio_inputs_solo_si_calculado.sql']
```

### Por qué hubo una 033

La 032 declaró `ck_ratio_inputs_no_vacio` sobre **todas** las filas. El primer
`--persist` la rompió en el acto:

```
CheckViolation: new row for relation "ratio" violates constraint "ck_ratio_inputs_no_vacio"
  cik 0001114700 · status NOT_CALCULABLE · inputs []
```

El choque era entre dos reglas del contrato, y las dos son correctas: **R7**
manda persistir el «no se pudo» (sin la fila, un hueco es indistinguible de un
emisor no procesado) y **R10** prohíbe un valor sin provenance. La 032 aplicaba
R10 a la fila entera en vez de al valor. La 033 corrige el alcance:

```sql
CHECK (status <> 'CALCULADO' OR jsonb_array_length(inputs) > 0)
```

No se editó la 032: ya estaba aplicada y el registro es del runner. Se corrigió
hacia adelante.

**El fallo dejó la base limpia**: `run_scope` cerró las dos corridas como
`ABORTED`, la transacción revirtió, y quedaron `0 RUNNING` y `0` filas. F-050
funcionando.

---

## 4. `derived.ratio`

```sql
ratio_key           text PRIMARY KEY
entity_key, cik, canonical_id, period_end, period_window, denominator_basis, currency
value, unit, status, motivo, publicable
formula_version, formula, inputs jsonb
input_checkpoint_id, run_id → engine.runs
calculated_at, valid_from, valid_to, created_at

UNIQUE (entity_key, canonical_id, period_end, period_window,
        denominator_basis, coalesce(currency,'-')) WHERE valid_to IS NULL
```

**Una sola tabla de ratios.** SQLite no participa: S1 no lee de S2/S3/S4.

### `period_window`, no `window`

`window` es palabra reservada en PostgreSQL —`CREATE TABLE t (window text)` es
un error de sintaxis, verificado— así que la columna se llama `period_window`.
Es la única desviación de nombre respecto del contrato, y es del motor, no de
criterio.

### Las CHECK que hacen trabajo

| constraint | qué impide |
|---|---|
| `ck_ratio_valor_vs_status` | un `CALCULADO` sin número, o un `NOT_CALCULABLE` con número o sin motivo |
| `ck_ratio_inputs_si_calculado` | un valor sin provenance |
| `ck_ratio_publicable` | publicar algo que no está calculado |
| `ck_ratio_window` | una ventana fuera de `FY / TTM / Q / YTD / PIT / FORWARD` |
| `ux_ratio_identidad_vigente` | **dos filas vigentes con la misma identidad** |

`test_la_identidad_vigente_es_unica_por_ventana` verifica que el índice rechaza
el duplicado, y `test_fy_y_ttm_conviven_y_no_se_pisan` que FY y TTM **sí**
coexisten como hechos distintos.

---

## 5. EV/Sales

```
canonical_id     ev_sales
formula_version  ev_sales_v1
formula          (market_cap + deuda_financiera - efectivo) / ingresos
                 market_cap = close / ratio_adr * acciones_en_circulacion
unit             veces
period_window    FY          ← declarado, no fingido
denominator_basis  n/a
```

Ningún tag aparece en el motor: los cuatro conceptos (`ingresos`,
`deuda_financiera`, `efectivo`, `acciones_circulacion`) se resuelven por las
cadenas de fallback de `ratio_defs.CONCEPTOS`. No se creó ningún financial fact.

### Por qué FY y no TTM

El motor no sabe sumar cuatro trimestres. El contrato dice que el canónico es
TTM; emitir FY **rotulado como TTM** sería exactamente el defecto que el
contrato viene a cerrar. Se emite FY y se dice que es FY:
`test_el_window_declarado_es_fy_y_no_dice_ser_ttm` lo fija.

### Resultado

```
CIK          entidad                              periodo      estado          valor
0000320193   Apple Inc.                           2025-09-27   CALCULADO     11.29879  USD
0000789019   MICROSOFT CORP                       2026-06-30   CALCULADO    11.362256  USD
0000904851   YPF SOCIEDAD ANONIMA                 2025-12-31   CALCULADO     1.599221  USD
0000931427   TRANSPORTADORA DE GAS DEL SUR S.A.   2025-12-31   CALCULADO     4.507306  ARS
0001045810   NVIDIA CORP                          2026-01-25   CALCULADO     25.64944  USD
0001114700   GRUPO FINANCIERO GALICIA S.A.        2025-12-31   NOT_CALCULABLE       -
0001347426   Macro Bank Inc.                      2025-12-31   NOT_CALCULABLE       -
0001717161   CENTRAL PUERTO S.A.                  2025-12-31   NOT_CALCULABLE       -
```

Los tres `NOT_CALCULABLE` son correctos y llevan su motivo: GGAL y BMA son
bancos y no publican ningún tag de la cadena de `ingresos`; CEPU no publica
ninguno de deuda financiera. **El hueco se persiste**, con la cadena de
candidatos que se consultó y con los insumos que sí se habían resuelto antes de
cortar.

---

## 6. Provenance

Cadena completa de AAPL, leída de la fila persistida:

```
1 RATIO       ev_sales = 11.29879 veces
1 ventana     FY · 2025-09-27 · USD
1 formula     ev_sales_v1 :: (market_cap + deuda_financiera - efectivo) / ingresos
2 ENTITY      E01M13XBSM8ZWPXACZAG2H149JX
3 ingresos    RevenueFromContractWithCustomerExcludingAssessedTax = 416.161.000.000
3 deuda       LongTermDebt                                        =  90.678.000.000
3 efectivo    CashAndCashEquivalentsAtCarryingValue               =  35.934.000.000
3 acciones    CommonStockSharesOutstanding                        =  14.773.260.000
3 precio      314.579987 USD · instrumento 86 · 2026-08-27 · ratio_adr 1
3 derivado    market_cap        = 4.647.371.938.747,62
3 derivado    enterprise_value  = 4.702.115.938.747,62
4 EVIDENCIA   COMPLETA · parsed_cik=0000320193 · sha=e1076735f1c81bc9…
5 RAW         aapl-20250927_htm.xml
6 RUN         290e4ba02f47469fb183d0923fde1dbd · chk e28d642bb2dee6bf…
```

Aritmética: `(4.647.371.938.747,62 + 90.678.000.000 − 35.934.000.000) /
416.161.000.000 = 11,29879`. `test_formula_correctness_ev_sales_se_reconstruye_a_mano`
la rehace desde los propios `inputs`.

### Un hallazgo del propio test: `prov_v1` era incompleta

`test_provenance_el_source_hash_existe_en_parsed` falló en la primera versión.
El motivo es real:

```
n_fuentes | filas de derived.fact
        1 | 46.919
        2 | 40.019
      3-10 |  1.851
```

**El 47 % de `derived.fact` se apoya en más de una fila de `parsed.facts`.**
Guardar sólo el primer `source_file`/`source_hash` dejaba fuera la mitad de la
evidencia. Corregido: la provenance guarda `source_files` y `source_hashes`
completos y deduplicados.

Como cambió **lo que la fila guarda** sin cambiar la fórmula, se introdujo
`PROVENANCE_SCHEMA = "prov_v2"`, que participa de `ratio_key`. El re-cálculo
produjo `REEMPLAZADO` en las 8: las viejas quedaron cerradas con `valid_to`,
ninguna se reescribió.

```
total 16 · vigentes 8 · cerradas 8
```

---

## 7. Tests

`tests/test_ratio_engine_ev_sales.py` — **25 tests, las 10 familias**.

| familia | tests | qué demuestra |
|---|---:|---|
| 1 formula correctness | 2 | el valor se rehace a mano desde sus insumos; ningún `CALCULADO` sin los cinco roles |
| 2 identity isolation | 2 | sin assertion `VERIFIED` no hay ratio; el `entity_key` es el de `identity_v1` |
| 3 cross-entity contamination | 3 | el hecho ajeno no entra; **0** insumos persistidos de otro emisor; **0** evidencias de otro CIK |
| 4 FY vs TTM identity | 3 | conviven; el índice rechaza el duplicado; el motor dice FY |
| 5 missing input | 3 | nombra el concepto **y** la cadena consultada; se persiste con provenance parcial |
| 6 zero denominator | 2 | ingresos 0 y negativos no dividen |
| 7 provenance completeness | 2 | cadena entera en todo `CALCULADO`; el hash citado existe en `parsed.facts` |
| 8 idempotency | 3 | la clave no cambia; persistir dos veces no duplica; un insumo distinto cierra y abre |
| 9 mutation | 2 | duplicar ingresos parte el ratio a la mitad; sin la guarda entra el ajeno |
| 10 persistence | 3 | lo leído es lo calculado; las CHECK se cumplen como datos; toda fila cita una corrida real |

### El ciclo que el encargo pide, medido

```
calcular  → persistir   8 INSERTADO
          → leer        test_persistence_lo_leido_es_lo_calculado  ✓
repetir   → persistir   8 SIN_CAMBIO,  filas: 8 → 8
mutar     → un insumo   REEMPLAZADO,   filas: n → n+1, vigentes 1
intercambiar por otra entidad → NOT_CALCULABLE  (no falla ruidosamente: se niega)
```

### Sobre cómo los tests tocan la base

Todo escenario adverso corre dentro de una transacción que **siempre** se
revierte. Verificado después: `derived.fact` 88.789, `parsed.facts` 135.077,
`identity_v1.identifier` 574, `0` schemas temporales, `0` facts de test,
`0 RUNNING`.

Fabricar un hecho que **pase** la guarda obliga a respetar su regla: se clona
una fila real del propio emisor y se cambian sólo `tag` y `value_numeric`
—`qname` participa de la guarda, `tag` no—. Es la única forma honesta de probar
las demás reglas sin desactivar la primera. Y en el camino las CHECK existentes
de `derived.fact` (`ck_fact_tiene_origen`, `fact_desempate_check`,
`fact_fact_key_check`) rechazaron tres intentos mal formados: el esquema se
defiende solo.

---

## 8. Regresión

```
$ python -m pytest tests/ -q -k "not f061_rojo"
3 failed, 291 passed, 1 skipped, 1 xfailed in 126.39s
```

De 265 tests a **296** (+6 F-061, +25 EV/Sales). Los 3 fallos son los
**preexistentes de F-038**, sin tocar como pide el encargo:

```
test_f038_traza_corrida.py::test_la_corrida_esta_registrada
test_f038_traza_corrida.py::test_el_hash_de_la_base_es_el_del_artefacto_en_disco
test_f038_traza_corrida.py::test_market_no_escribe_en_produccion
   AssertionError: assert 601 == 591
```

Afirman conteos fijos de un lote de Market (`smoke-real-2026-08-28`) que volvió
a correr desde que el test se escribió. **No se alteró Market para hacerlos
pasar**, ni se tocó el archivo.

---

## 9. Legacy

| | rol | estado |
|---|---|---|
| **S1** — `derived.ratio` + `ratio_engine.py` | **CANONICAL** | en pie, 1 ratio |
| S2 — `calcular_ratios_base.py` → `ratios` | **LEGACY / REFERENCE** | sin tocar |
| S3 — `f4_ratios.py` → `screener_gold` | **LEGACY / REFERENCE** | sin tocar, sigue sirviendo el HTML |
| S4 — `b5_metricas.py`, `s2_ratios_cnv.py` | **LEGACY / REFERENCE** | sin tocar, sigue sirviendo la API |

**Nada borrado.** Y el motor nuevo **no lee de ninguna superficie legacy**: sus
únicas fuentes son `derived.fact`, `parsed.facts`, `market_price_daily` e
`identity_v1`. No hay conexión que documentar porque no existe.

---

## 10. Dictamen

# RATIO_ENGINE_DAY3_GATE = **PASS_WITH_WARNINGS**

### BLOCKERS

**Ninguno.** No queda ningún defecto que impida seguir.

### WARNINGS

| # | warning |
|---|---|
| **W1** | **EV/Sales es FY, no TTM.** El canónico del contrato es TTM y el motor no lo soporta. Está declarado en la columna `period_window` y fijado por un test, así que no puede confundirse — pero un consumidor que espere TTM no lo tiene. |
| **W2** | **Cobertura 5 de 8 emisores.** GGAL y BMA no publican ingresos (son bancos); CEPU no publica deuda financiera. No es un defecto del motor: es el límite del dato, y queda persistido con su motivo. |
| **W3** | **La guarda protege contra hechos ajenos, no contra hechos propios y equivocados.** El ataque A2a —invertir el signo de `Equity`— sigue sin ser detectado por la capa de ratios. Le corresponde a los controles de identidad contable (T3 del contrato), no a F-061. |
| **W4** | **`prov_v1` era incompleta y estuvo persistida.** Ocho filas guardaron un solo `source_hash` cuando el 47 % de los hechos tiene varios. Corregido con `prov_v2`; las filas viejas quedaron cerradas, no borradas. |
| **W5** | **Los 3 fallos de F-038 siguen abiertos.** Preexistentes, de Market, ajenos a este ciclo. No se tocaron. |

### IMPLEMENTED

- guarda de pertenencia F-061 en el punto único `ratio_inputs.sql_insumos`
- los 4 módulos de la capa de ratios migrados
- `derived.ratio` con la identidad del contrato, 5 CHECK y el índice único
- vista `derived.v_fact_pertenencia` como objeto auditable de la base
- `ratio_engine.py` con `ev_sales` / `ev_sales_v1`
- versionado de fórmula **y** de esquema de provenance
- idempotencia por `ratio_key`, con cierre por `valid_to` en vez de UPDATE

### NOT_IMPLEMENTED

- **TTM** — el motor no agrega períodos. Bloquea el canónico de todos los ratios de flujo
- los otros 16 ratios prioritarios del contrato
- las 12 decisiones de producto (D1–D12) siguen abiertas; **D3 (cadena de D&A)** sigue bloqueando 4 ratios
- exposición de `derived.ratio` en la API o el screener

### TESTED

las 10 familias sobre EV/Sales (25 tests) · la guarda F-061 con mutación causal
en dos niveles (6 tests) · el invariante sobre los 135.077 punteros reales ·
idempotencia medida en dos corridas · regresión completa

### NOT_TESTED

- **TTM vs FY con datos reales de TTM**: `test_fy_y_ttm_conviven_y_no_se_pisan`
  inserta la fila TTM a mano porque el motor no la produce. Prueba el modelo de
  datos, no un cálculo TTM
- ningún otro ratio
- comportamiento con más de un instrumento en la misma moneda para una entidad
- concurrencia: dos corridas del motor simultáneas

**No se afirma homologación.** Este gate certifica que F-061 está cerrado con
evidencia y que un ratio recorre la cadena completa —cálculo, persistencia,
provenance, idempotencia, mutación— sobre la superficie canónica. Nada más.

---

### Anexo · comandos

```bash
python -c "from engine.db import apply_migrations, get_admin_engine; ..."   # 032, 033
python scripts/engine/ratio_engine.py                  # calcula, no escribe
python scripts/engine/ratio_engine.py --persist        # 8 INSERTADO
python scripts/engine/ratio_engine.py --persist        # 8 SIN_CAMBIO  (idempotencia)
python -m pytest tests/test_f061_ownership.py -v       # 6 passed
python -m pytest tests/test_ratio_engine_ev_sales.py -q # 25 passed
python -m pytest tests/ -q -k "not f061_rojo"          # 291 passed, 3 failed (F-038)
python scripts/engine/screener_demo.py                 # regresion: mismos numeros
```
