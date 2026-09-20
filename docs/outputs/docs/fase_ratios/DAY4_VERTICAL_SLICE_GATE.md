# DAY 4 — VERTICAL SLICE · GATE

**2026-09-01** · `catalaxia_engine@127.0.0.1:5433/catalaxia` · FAST · **prod=False** · sin commits
Producto: [`CATALAXIA_RATIO_PRODUCT.md`](CATALAXIA_RATIO_PRODUCT.md) · Demo: [`CATALAXIA_DEMO.md`](CATALAXIA_DEMO.md)

---

# CATALAXIA_VERTICAL_SLICE_GATE = **PASS_WITH_WARNINGS**
# CATALAXIA_COMMERCIAL_READINESS = **READY_FOR_PILOT**

Un piloto acotado: prospectos que valoren **auditabilidad** sobre cobertura, con
las ocho empresas y los cuatro ratios sobre la mesa desde el minuto uno. No un
lanzamiento general.

---

## 1. Dataset demo

Los cinco priorizados, más los tres que completan el universo con fundamentals.

| emisor | identity | fundamentals | market | ratios |
|---|---|---|---|---|
| **AAPL** | CIK `VERIFIED` · 2 instrumentos | 2.085 facts · 2 filings · 2025-09-27 | 23.038 precios | **4/4** |
| **MSFT** | CIK `VERIFIED` · 2 instrumentos | 3.460 · 2 · 2026-06-30 | 20.386 | **4/4** |
| **NVDA** | CIK `VERIFIED` · 2 instrumentos | 2.505 · 2 · 2026-01-25 | 13.884 | **4/4** |
| **YPF** | CIK `VERIFIED` · 2 instrumentos | 47.930 · **9** · 2025-12-31 | 14.985 | 3/4 |
| **TGS** | CIK `VERIFIED` · 4 instrumentos | 7.301 · 2 · 2025-12-31 | 29.266 | **4/4** |
| CEPU | CIK `VERIFIED` | 2025-12-31 | sí | 3/4 |
| GGAL | CIK `VERIFIED` | 2025-12-31 | sí | 2/4 |
| BMA | CIK `VERIFIED` · **sin instrumento ligado** | 2025-12-31 | sin enlace | 1/4 |

Los cinco priorizados tienen los cuatro eslabones. **Ningún dato inventado**:
las celdas que faltan están persistidas como `NOT_CALCULABLE` con su motivo.

---

## 2. Ratios del slice

| ratio | versión | ventana | base | cobertura |
|---|---|---|---|---|
| `eps` | `eps_v1` | `FY` | AVERAGE | **8/8** |
| `pb` | `pb_v1` | `PIT` | CLOSING | 6/8 |
| `pe` | `pe_v1` | **`FY`** | n/a | 6/8 |
| `ev_sales` | `ev_sales_v1` | `FY` | n/a | 5/8 |

**32 filas vigentes · 25 `CALCULADO` · 7 `NOT_CALCULABLE` con motivo.**

`F1` de la homologación verifica que **ninguna fila dice `TTM`**. No se inventó
P/E TTM: el P/E es FY y la columna `window` lo declara.

### Una decisión de producto que sí hubo que tomar

**D9 — P/B usa el patrimonio de la CONTROLADORA**, no el total. El accionista
compra la participación de la controladora; incluir minoritarios abarata el
múltiplo de holdings y bancos sin que el comprador tenga derecho sobre esa
parte. Era estrictamente necesaria para el slice y queda registrada en la
provenance de cada celda (`EquityAttributableToOwnersOfParent`). Las otras 11
decisiones siguen abiertas.

---

## 3. Provenance

Demostrada en los tres niveles que el encargo pide:

| nivel | caso | resultado |
|---|---|---|
| fundamental | AAPL `ingresos` | tag elegido + cadena consultada + 8 `source_fact_ids` + 2 archivos + 2 hashes |
| EPS | AAPL, TGS | fact reportado con su accession y hash |
| EV/Sales | AAPL | cadena completa, 4 insumos contables + precio + 2 derivados |

Cadena verificada extremo a extremo:

```
display value → ratio record → inputs → derived.fact → source_fact_ids
             → parsed.facts → filing (accession) → RAW (source_file + sha256)
```

Controles independientes: **D1** 0 insumos sin cadena · **D2** 0 punteros
huérfanos · **D3** 0 hashes que no coincidan con `parsed.facts`.

---

## 4. Superficie de consulta

`scripts/engine/ratio_api.py` — CLI que devuelve JSON, sólo lectura.

```bash
--ticker AAPL                          # todos los ratios
--cik 0000904851 --ratio pe            # uno
--ticker AAPL --fundamental ingresos   # un concepto contable
--ticker AAPL --ratio ev_sales --provenance
--universo                             # el slice entero
--window FY  --status NOT_CALCULABLE   # filtros
```

Resuelve `ticker → entidad` por el enlace de instrumento, nunca por nombre; si
un ticker resuelve a más de una entidad devuelve `IDENTIDAD_NO_RESUELTA` en vez
de elegir.

---

## 5. Información de calidad

Toda celda lleva, sin excepción: `status`, `period_end`, `window`,
`denominator_basis`, `currency`, `formula_version`, `formula`,
`provenance_status`, `motivo`, `publicable`.

`provenance_status` se **recalcula al servir**, no se guarda: se recorre cada
insumo contable y se verifica cadena completa, hashes presentes y
`parsed_cik == cik`.

**Nunca se devuelve `ratio = value` a secas.**

---

## 6. Caso negativo

Dos familias, distinguibles por el motivo:

**Falta un dato** — CEPU / `ev_sales`:
```
"sin fact para el concepto 'deuda_financiera' en 2025-12-31;
 candidatos consultados: ['Borrowings', 'DebtLongtermAndShorttermCombinedAmount',
 'LongTermDebt']"
```

**Una regla financiera** — YPF / `pe`, con `provenance_status: COMPLETA`:
```
"REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin valor por
 decision financiera, no por falta de dato: el EPS esta y su provenance tambien"
```

Y un tercero, de identidad — BMA: *«la entidad no tiene instrumento ligado en
`identity_v1.instrument`: atribuirle un precio sería un join por ticker.»*

El contrato de la tabla lo hace estructural: `ck_ratio_valor_vs_status` impide
que exista un `NOT_CALCULABLE` con valor **o sin motivo**. `NOT_CALCULABLE` no
es 0 y no es error — es una respuesta.

---

## 7. Cross-entity safety

```
$ python -m pytest tests/test_f061_ownership.py -q
6 passed in 1.47s
```

**El control no se modificó.** Y sobre los datos reales, verificado por el
auditor independiente:

```
E1 · ningún insumo proviene de otro emisor            0
E2 · el entity_key de cada fila es el de identity_v1  0 discrepan
E3 · F-061 sobre los punteros de derived.fact         0 violaciones (135.077)
```

---

## 8. Idempotencia

```
1ª corrida   INSERTADO 24 · SIN_CAMBIO 8
2ª corrida   SIN_CAMBIO 32
```

Sin duplicados: `F4` verifica **0 identidades vigentes repetidas**.

Y el ciclo de vida, sobre AAPL `ev_sales`:

```
value       formula_version   valid_from             valid_to
11.29879    ev_sales_v1       2026-09-01 23:14:36    2026-09-01 23:20:14
11.29879    ev_sales_v1       2026-09-01 23:20:14    VIGENTE
```

Mismo valor, misma versión de fórmula. La primera fila se cerró cuando cambió
el **esquema de provenance** (`prov_v1` → `prov_v2`, al descubrirse que el 47 %
de los hechos se apoya en más de un archivo). **El `valid_to` de la cerrada es
exactamente el `valid_from` de la vigente**: sin hueco y sin solapamiento.
Ninguna fila se reescribió.

---

## 9. Regresión

```
$ python -m pytest tests/ -q -k "not f061_rojo"

passed    291
failed      3
skipped     1
xfailed     1
            ────
total     296        en 129,04 s
```

Los 3 son los **históricos de F-038** (`test_la_corrida_esta_registrada`,
`test_el_hash_de_la_base_es_el_del_artefacto_en_disco`,
`test_market_no_escribe_en_produccion`): afirman conteos fijos de un lote de
Market que volvió a correr. **No se tocaron, y no se alteró Market.**

---

## 10. Homologación independiente

`scripts/engine/homologacion_slice.py` — no importa `ratio_engine`, ni
`ratio_api`, ni `ratio_defs`, ni `engine.*`. Habla con PostgreSQL por `psql` y
reescribe las fórmulas desde el contrato.

```
25/25 valores publicados reproducidos a mano
peor desvío relativo   1,59e-7
tolerancia declarada   1,0e-6
13/13 controles OK
```

El desvío es exactamente el redondeo a seis decimales que el motor aplica al
persistir. Comparación por ratio en `HOMOLOGACION_SLICE.json`.

| | manual | Catalaxia | dif. relativa |
|---|---:|---:|---:|
| AAPL `eps` | 7,490000000000 | 7,49 | **0** |
| AAPL `pb` | 63,029741618375 | 63,029742 | 6,05e-9 |
| AAPL `ev_sales` | 11,298790465103 | 11,29879 | 4,12e-8 |
| TGS `pb` | 2,191237349113 | 2,191237 | **1,59e-7** ← el peor |

---

## 11. Dictamen

# CATALAXIA_VERTICAL_SLICE_GATE = **PASS_WITH_WARNINGS**

### BLOCKERS

**Ninguno.** No queda defecto que impida demostrar el slice.

### WARNINGS

| # | |
|---|---|
| **W1** | **No hay TTM.** Todos los ratios de flujo son `FY`. El P/E no es comparable contra una fuente que publique TTM. Está declarado en `window` y verificado por `F1`, pero es la brecha más visible frente a cualquier competidor. |
| **W2** | **Cuatro ratios de los 17 prioritarios.** Faltan ROE, ROIC, márgenes, deuda, liquidez, FCF, dividendos. |
| **W3** | **Ningún ratio con EBITDA**, y no lo habrá hasta resolver D3: 12 candidatos de D&A con semánticas distintas. Bloquea 4 ratios del contrato. |
| **W4** | **Ocho emisores.** El límite es la ingesta de fundamentals (8 CIK con facts, contra 513 en identidad y 584 instrumentos con precio), no el cálculo. |
| **W5** | **Los bancos quedan casi vacíos.** GGAL 2/4 y BMA 1/4: no publican `Revenue` bajo ninguno de los 5 tags. Es el modelo contable del sector, no un defecto — pero un piloto con un banco como prospecto vería una pantalla pobre. |
| **W6** | **Las superficies legacy siguen publicando otros números.** El screener HTML y la API v2 sirven ratios sin procedencia verificable. Coexisten con esto y pueden discrepar. |
| **W7** | **Los 3 fallos de F-038 siguen abiertos.** Preexistentes, de Market, ajenos a este ciclo. |
| **W8** | **11 decisiones de producto abiertas** (D1–D12 menos D9, resuelta acá). |

### DEMO_READY

- los 4 ratios sobre 8 emisores, 32 celdas persistidas
- cadena de procedencia navegable hasta el archivo con hash
- CLI reproducible con contrato JSON estable
- los dos casos de `NOT_CALCULABLE`, con motivos distinguibles
- aislamiento entre entidades, con mutación causal que lo demuestra
- idempotencia con ciclo de vida `valid_from`/`valid_to` visible
- homologación independiente, 25/25 a 1,59e-7
- guion de 5 min 30 s con las preguntas difíciles preparadas

### NOT_READY

- **TTM** — bloquea la comparabilidad de todo ratio de flujo
- ROE, ROIC, márgenes, deuda, liquidez, FCF, dividendos
- cobertura más allá de 8 emisores
- cualquier afirmación de paridad con TIKR
- exposición al usuario final: hoy es CLI, no hay UI ni endpoint HTTP
- series históricas: sólo el último ejercicio de cada emisor

---

# CATALAXIA_COMMERCIAL_READINESS = **READY_FOR_PILOT**

**Por qué READY_FOR_PILOT y no NOT_READY.** Hay una estructura comercial real,
no una simulación: un contrato de datos con versión de fórmula, persistencia con
ciclo de vida, procedencia verificable hasta el documento, aislamiento entre
entidades demostrado por mutación, y una homologación independiente que
reproduce el 100 % de los valores. Un prospecto puede tomar cualquier número de
la pantalla y llegar al archivo de la SEC. Eso es demostrable hoy.

**Por qué piloto y no lanzamiento.** Ocho empresas y cuatro ratios no sostienen
un producto general. El piloto sirve a prospectos que valoren **auditabilidad
sobre cobertura** —un comité de inversión, un compliance, un fondo que necesita
justificar de dónde salió un múltiplo— y debe presentarse con las ocho empresas
y los cuatro ratios explícitos desde el minuto uno.

**Lo que no se debe decir en ese piloto:** que hay paridad con TIKR, que el P/E
es TTM, que la cobertura de ratios está completa, o que las superficies legacy
tienen el mismo respaldo. Ninguna de las tres es cierta, y las tres están
escritas en el documento de producto para que nadie las diga por omisión.

**Lo que falta para dejar de ser piloto**, en orden: TTM, después la ingesta de
fundamentals a escala, después los ratios que dependen de decisiones de
producto.

---

### Anexo · comandos

```bash
python scripts/engine/ratio_engine.py                    # 4 ratios × 8 emisores
python scripts/engine/ratio_engine.py --persist          # INSERTADO 24 · SIN_CAMBIO 8
python scripts/engine/ratio_engine.py --persist          # SIN_CAMBIO 32
python scripts/engine/ratio_api.py --ticker AAPL --ratio ev_sales --provenance
python scripts/engine/ratio_api.py --ticker YPFD --ratio pe        # regla EPS<=0
python scripts/engine/ratio_api.py --ticker CEPU --ratio ev_sales  # dato faltante
python scripts/engine/homologacion_slice.py              # 13/13 · 25/25 · 1,59e-7
python -m pytest tests/test_f061_ownership.py -q         # 6 passed
python -m pytest tests/ -q -k "not f061_rojo"            # 291/3/1/1
```
