# CATALAXIA — demo de 5 minutos

**Ocho pasos. Todo se ejecuta en vivo; ninguna salida está preparada.**
Requisitos: `catalaxia-engine-dev` arriba, `ENGINE_DB_*` apuntando a **5433**.

> **El punto de la demo no es la cantidad de ratios.** Son cuatro. El punto es
> que cada número se puede abrir hasta el archivo que la SEC publicó, y que lo
> que no se puede afirmar aparece dicho, no rellenado.

---

## Paso 0 · Verificar el entorno — 10 s

```bash
python -c "from engine.config import load_settings; print(load_settings().describe())"
```

```
catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False
```

**Decir:** «5433, no producción. Todo lo que sigue es sobre la base de trabajo.»

---

## Paso 1 · Elegir una empresa — 20 s

```bash
python scripts/engine/ratio_api.py --ticker AAPL
```

```json
{ "entity_key": "E01M13XBSM8ZWPXACZAG2H149JX",
  "nombre": "Apple Inc.", "cik": "0000320193", "ratios": [ ... ] }
```

**Decir:** «El ticker no es la identidad. `AAPL` se resolvió por el enlace del
instrumento a la entidad, y la entidad tiene un CIK con assertion `VERIFIED`.
Si el ticker resolviera a dos entidades, esto devolvería un error en vez de
elegir una.»

---

## Paso 2 · Mostrar un fundamental — 30 s

```bash
python scripts/engine/ratio_api.py --ticker AAPL --fundamental ingresos
```

```
tag_elegido      RevenueFromContractWithCustomerExcludingAssessedTax
value            416.161.000.000   USD
period_end       2025-09-27        window FY
cadena_evaluada  [Revenue, RevenueFromContractsWithCustomers,
                  RevenueFromContractWithCustomerExcludingAssessedTax,
                  RevenueFromContractWithCustomerIncludingAssessedTax, Revenues]
provenance_status COMPLETA
source_files     aapl-20250927.htm · aapl-20250927_htm.xml
source_hashes    e1076735f1c81bc9… · 274361a794f84b24…
```

**Decir:** «"Ingresos" no es un tag: es un **concepto** con cinco tags
candidatos en orden. Apple usa el tercero, un emisor IFRS usaría el primero. La
celda dice cuál se usó **y** cuáles se consultaron — así se puede verificar que
la búsqueda fue exhaustiva.»

---

## Paso 3 · Mostrar un ratio — 30 s

```bash
python scripts/engine/ratio_api.py --ticker AAPL --ratio ev_sales
```

```json
{ "canonical_id": "ev_sales", "value": 11.29879, "unit": "veces",
  "status": "CALCULADO", "period_end": "2025-09-27", "window": "FY",
  "currency": "USD", "formula_version": "ev_sales_v1",
  "provenance_status": "COMPLETA" }
```

**Decir:** «Ningún número viaja solo. Van con él la ventana, la moneda y la
versión de fórmula. **`window: FY`** — no es TTM, y lo dice. El estándar de la
industria es TTM; el motor todavía no sabe sumar cuatro trimestres, así que
publica FY con la etiqueta correcta en vez de TTM con la equivocada.»

---

## Paso 4 · Abrir la procedencia — 60 s

```bash
python scripts/engine/ratio_api.py --ticker AAPL --ratio ev_sales --provenance
```

```
ingresos    RevenueFromContractWithCustomerExcludingAssessedTax  416.161.000.000 USD
deuda       LongTermDebt                                          90.678.000.000 USD
efectivo    CashAndCashEquivalentsAtCarryingValue                 35.934.000.000 USD
acciones    CommonStockSharesOutstanding                          14.773.260.000
precio      314,579987 USD · instrumento 86 · 2026-08-27 · ratio_adr 1
derivado    market_cap        4.647.371.938.747,62
derivado    enterprise_value  4.702.115.938.747,62

evidencia   COMPLETA · parsed_cik 0000320193 · accession 0000320193-25-000079
            source_fact_ids [148013, 148327, 148938, 149030, ...]
            source_files    aapl-20250927.htm · aapl-20250927_htm.xml
            source_hashes   e1076735f1c81bc9… · 274361a794f84b24…
```

**Decir:** «Ésta es la cadena entera: valor → ratio → insumos → hecho normalizado
→ punteros → hecho parseado → archivo → hash. Ese `accession` es una URL de la
SEC. El hash es del archivo tal como se descargó.»

---

## Paso 5 · Demostrar la fórmula — 45 s

Con la calculadora, en vivo:

```
market_cap = 314,579987 / 1 × 14.773.260.000  = 4.647.371.938.747,62
EV         = 4.647.371.938.747,62 + 90.678.000.000 − 35.934.000.000
                                                = 4.702.115.938.747,62
EV/Sales   = 4.702.115.938.747,62 / 416.161.000.000 = 11,29879   ✓
```

Y la verificación independiente, que rehace las 25 celdas sin importar el motor:

```bash
python scripts/engine/homologacion_slice.py
```

```
25/25 valores reproducidos a mano · peor desvío relativo 1,59e-7
13/13 controles OK
```

**Decir:** «Ese auditor no importa una sola línea del motor. Habla con
PostgreSQL por `psql` y reescribe las fórmulas desde el contrato. Si el motor y
el auditor compartieran una función, compartirían también su error.»

---

## Paso 6 · Demostrar la fuente — 30 s

```bash
python scripts/engine/ratio_api.py --ticker TGSU2 --ratio pb --provenance
```

```
patrimonio  EquityAttributableToOwnersOfParent   3.127.862.637.000 ARS
            RAW: ef20060824_20f.htm  sha=3802f019cc86f53e
acciones    EntityCommonStockSharesOutstanding         752.761.058
precio      9.105,00 ARS
derivado    bvps                                         4.155,187
            9.105 / 4.155,187 = 2,191237  ✓
```

**Decir:** «Un emisor argentino, IFRS, en pesos, con el mismo nivel de detalle.
Y nótese `EquityAttributableToOwnersOfParent`: es el patrimonio **de la
controladora**, no el total. Para un holding la diferencia es material, y la
celda dice cuál se usó.»

---

## Paso 7 · Mostrar `NOT_CALCULABLE` — 60 s

Los dos casos, y son distintos.

### 7a · Falta un dato

```bash
python scripts/engine/ratio_api.py --ticker CEPU --ratio ev_sales
```

```json
{ "value": null, "status": "NOT_CALCULABLE",
  "motivo": "sin fact para el concepto 'deuda_financiera' en 2025-12-31;
             candidatos consultados: ['Borrowings',
             'DebtLongtermAndShorttermCombinedAmount', 'LongTermDebt']" }
```

### 7b · Una regla financiera

```bash
python scripts/engine/ratio_api.py --ticker YPFD --ratio pe
```

```json
{ "value": null, "status": "NOT_CALCULABLE", "provenance_status": "COMPLETA",
  "motivo": "REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin
             valor por decision financiera, no por falta de dato" }
```

**Decir:** «`NOT_CALCULABLE` **no es cero y no es un error**. Un cero diría que
Central Puerto no tiene deuda; eso sería inventar. En el segundo caso la
procedencia está **completa** —el EPS está, con su archivo— y aun así no se
publica el múltiplo: YPF cerró con pérdida y un P/E negativo se lee como
"barato" cuando significa lo contrario. Es la convención del IAMC.»

---

## Paso 8 · El sistema no mezcla entidades — 45 s

```bash
python -m pytest tests/test_f061_ownership.py -v
```

```
test_el_detector_encuentra_los_hechos_ajenos              PASSED
test_control_positivo_los_hechos_legitimos_no_se_marcan   PASSED
test_la_mutacion_sin_guarda_readmite_los_hechos_ajenos    PASSED
test_la_base_de_trabajo_cumple_hoy_el_invariante          PASSED
test_la_seleccion_rechaza_hechos_ajenos                   PASSED
test_los_modulos_de_ratios_usan_la_seleccion_canonica     PASSED
6 passed
```

**Decir:** «Hubo un hallazgo real, F-061: se clonaron el activo y el pasivo
corriente de Apple bajo el CIK de Galicia y el sistema publicó el ratio de
Apple como si fuera del banco argentino — el mismo número, dígito por dígito, y
nada lo delataba.

Ahora todo insumo debe demostrar, por su propia procedencia, que pertenece al
emisor: mismo emisor, mismo filing, mismo concepto. **La regla no menciona
ningún ticker ni ningún nombre.** Y el tercer test es el importante: le quita la
guarda al motor y la contaminación vuelve. Si no volviera, la protección la
estaría dando otra cosa y no la que decimos.

Sobre los datos reales: **0 violaciones en 135.077 punteros de procedencia.**»

---

## Cierre — 20 s

```bash
python scripts/engine/ratio_api.py --universo --ratio eps
```

**Decir:** «Ocho emisores, cuatro ratios, 25 celdas calculadas y 7 dichas como
no calculables con su motivo. No es paridad con TIKR y no lo vendemos así.

Lo que sí es: cada número auditable hasta el documento, y ningún hueco tapado
con un cero. Escalar la cobertura es un problema de ingesta. Escalar la
confianza, que es lo difícil, ya está resuelto.»

---

### Guion de tiempos

| paso | | seg |
|---|---|---:|
| 0 | entorno | 10 |
| 1 | elegir empresa | 20 |
| 2 | fundamental | 30 |
| 3 | ratio | 30 |
| 4 | procedencia | 60 |
| 5 | fórmula + homologación | 45 |
| 6 | fuente (emisor argentino) | 30 |
| 7 | los dos `NOT_CALCULABLE` | 60 |
| 8 | aislamiento entre entidades | 45 |
| | cierre | 20 |
| | **total** | **5 min 30 s** |

### Preguntas probables

**«¿Por qué sólo ocho empresas?»** — El límite es la ingesta de fundamentals, no
el cálculo. Hay 513 CIK en identidad y 584 instrumentos con precio; los
fundamentals normalizados llegan a ocho.

**«¿Por qué el P/E no es TTM?»** — Porque el motor no agrega períodos todavía.
Se publica FY con la etiqueta correcta. Es la decisión que hay que discutir
antes de comparar contra cualquier fuente externa.

**«¿Y ROE, márgenes, deuda?»** — Definidos en el contrato, no implementados.
Cuatro dependen de EBITDA, que no existe como tag XBRL: hay 12 candidatos de
amortización con semánticas distintas y esa decisión está abierta.

**«¿Esto reemplaza a TIKR?»** — No. TIKR publica cientos de métricas sobre miles
de empresas. Esto son cuatro sobre ocho, con procedencia verificable. Son
productos distintos.
