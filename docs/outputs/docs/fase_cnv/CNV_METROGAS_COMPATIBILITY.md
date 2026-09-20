# CNV MetroGAS Compatibility

**2026-09-02** · evaluación de la propuesta contra el código y las tablas actuales
**Sin modificar nada. Sin ejecutar el pipeline. Sin correr `s2_ratios_cnv`.**

---

## 1. Executive conclusion

# COMPATIBLE CON CAMBIOS ESTRUCTURALES

Pero el veredicto se parte en dos, y la diferencia es lo importante:

| fases | veredicto | por qué |
|---|---|---|
| **A · B · C · E · F** — CNV → normalizado → market → contraste | **COMPATIBLE** | ya existen **y ya corrieron para METR**. 2.747 filas normalizadas, 56/56 documentos con RAW en disco, 6.637 velas de precio |
| **D** — set amplio de ratios | **COMPATIBLE CON CAMBIOS MENORES** | no existe implementación; `s2_ratios_cnv` produce 7+2 ratios de los 31 pedidos. Es código nuevo, sin cambio de esquema |
| **G** — alimentar el engine canónico | **NO COMPATIBLE hoy** | cuatro columnas `NOT NULL` de `parsed.facts`/`derived.fact` que un dato CNV **no puede satisfacer** |

**Traducido:** de las siete fases, cinco ya están hechas, una es un script nuevo,
y la séptima choca con el esquema. La propuesta es ejecutable de A a F **hoy y
sin escribir código** — salvo D.

---

## 2. Existing pipeline

Orden real, extraído de `run_all.py` (no inventado):

```
FASE A   job1_universo → job2_download → job3_formtype → job4_clasificar
FASE B   job5_v2_extract_eeff → job6_v2_reparse_div → job7_validar → job8_doc_meta
FASE C   s0_normalizar_cnv → s1_bimoneda
(D)      s2_ratios_cnv                      ← sólo 7+2 ratios
FASE E   s3_precios → s3b_precios_historicos → s3c_refrescar_precios
(post)   s4_ensamblar → s7c_cagr → s8_calidad → s9_guards_yfinance
```

---

## 3. Reusable components

| script | reutilizable sin cambios | filtra un emisor | destructivo |
|---|---|---|---|
| `job1_universo.py` | **sí** | no | no |
| `job2_download.py` | **sí** | **sí — `--empresas <csv>`** | no |
| `job3_formtype.py` | **sí** | no (`--debug`) | no |
| `job4_clasificar.py` | **sí** | no | no |
| `job5_v2_extract_eeff.py` | **sí** | **sí — `--cuits <csv>`, `--offline`** | no |
| `job6_v2_reparse_div.py` | sí | no | **sí (1)** |
| `job7_validar.py` | sí | no | `--purge` opcional |
| `job8_doc_meta.py` | **sí** | no | no |
| `s0_normalizar_cnv.py` | sí | **NO** | **`DROP TABLE cnv_estados_norm`** |
| `s1_bimoneda.py` | **sí** | **sí — `--ticker METR`** | **no, aditivo** |
| `s3_precios.py` | sí | no | no |
| `s3b_precios_historicos.py` | **sí** | **sí — `--grupo`, `--desde/--hasta`** | no |
| `s3c_refrescar_precios.py` | **sí** | `--dry-run` | no |
| `s2_ratios_cnv.py` | parcial | no | **`DROP TABLE ratios_cnv`** |
| `s4_ensamblar.py` | parcial | no | **`DROP TABLE screener`** |

**Ocho scripts corren sin tocar una línea.** Cuatro aceptan filtro por emisor.

---

## 4. Incompatibilities

### 4.1 · Tres scripts reconstruyen tablas enteras

```
s0_normalizar_cnv.py    DROP TABLE IF EXISTS cnv_estados_norm   (y mapa_entidades)
s2_ratios_cnv.py        DROP TABLE IF EXISTS ratios_cnv
s4_ensamblar.py         DROP TABLE IF EXISTS screener
```

**No se puede correr la fase C «sólo para METR».** `s0` reconstruye las 72
empresas. No es un bug —es un diseño de reconstrucción idempotente— pero rompe
la premisa de «un solo papel de punta a punta».

### 4.2 · Los jobs no tienen `argparse`

Parsean `sys.argv` a mano. `--cuits` y `--empresas` funcionan, pero hay que
pasarles un CSV con el formato exacto de `empresas_subset.csv`:
`ticker,empresa,id,cuit,url_empresa,grupo`.

### 4.3 · `ratios_cnv` no puede representar dos perímetros

```sql
CREATE TABLE ratios_cnv (cuit TEXT PRIMARY KEY, ...)
```

Una fila por empresa. METR tiene CONSOLIDADO **e** INDIVIDUAL. Sólo sobrevive uno
—el que elija `_perimetro.perimetro_preferido()`.

### 4.4 · La fila actual de METR en `ratios_cnv` tiene un defecto de ventana

```
ultimo_periodo   2026-03-31              ← un TRIMESTRE
MargenNeto       0.4641   vs  CNV 0.08
provenance       NetIncome [decum 2025-06-30..2026-03-31]  ← TTM
                 Revenue = 283.136 M                        ← trimestral
```

Cruza un resultado TTM con un ingreso trimestral. Va a reaparecer al correr la
fase D.

---

## 5. Available METR data

**Todo lo que las fases A, B y C producirían ya está materializado.**

| tabla | filas METR | contenido |
|---|---:|---|
| `cnv_documents` | 1.681 | documentos descubiertos |
| `cnv_filings` | 121 | presentaciones · `norma NIIF` · `tipo_balance` · `periodicidad` |
| `cnv_estados` | 2.846 | extracción v1 |
| `cnv_estados_v2` | 2.697 | extracción v2 · **56 GUIDs** |
| `cnv_estados_norm` | **2.747** | **51 conceptos · 30 períodos · 2018-12-31 .. 2026-03-31** |
| `cnv_reextract` | 1.108 | re-extracciones |
| `cnv_dividendos` | **0** | METR no paga dividendos |
| `ratios_cnv` | 1 | con el defecto de §4.4 |
| **RAW en disco** | **56/56** | `eeff/eeff_html/{guid}.html` |
| página de empresa | 1 | `30657863676_Metrogas_S_A.html` · 2.083.534 bytes |
| `market_price_daily` | **6.637** | instrumento 38 · 2000-01-03 .. 2026-08-27 · último 2.350,00 ARS |

Perímetros: CONSOLIDADO 1.300 filas / 27 períodos · INDIVIDUAL 1.397 / 29.

**Consecuencia directa:** las fases A, B y C **no necesitan ejecutarse**. Y como
`s0` es destructivo, ejecutarlas tiene más riesgo que beneficio.

---

## 6. Ratio coverage

**42 evaluados · 30 calculables (71 %) · 12 no.** FY2025, perímetro CONSOLIDADO.

| Ratio | Calculable | Input(s) | Fuente | Definición | Observación |
|---|:-:|---|---|---|---|
| Revenue Growth | **SÍ** | Revenue FY/FY-1 | CNV | (Rev₁/Rev₀)−1 | +31,59 % |
| EBITDA Growth | **SÍ** | EBITDA FY/FY-1 | CNV | ídem | +36,72 % |
| EBIT Growth | **SÍ** | EBIT FY/FY-1 | CNV | ídem | +35,04 % |
| Net Income Growth | **SÍ** | NetIncome | CNV | ídem | −15,42 % |
| EPS Growth | **SÍ** | EPS_basico | CNV | ídem | −15,39 % |
| FCF Growth | **NO** | — | — | — | **falta CapEx** |
| Gross Margin | **SÍ** | GrossProfit, Revenue | CNV | GP/Rev | 38,21 % |
| EBITDA Margin | **SÍ** | EBITDA, Revenue | CNV | reportado/Rev | 21,09 % |
| EBIT Margin | **SÍ** | EBIT, Revenue | CNV | EBIT/Rev | 16,13 % |
| Operating Margin | **SÍ** | OperatingIncome, Revenue | CNV | OI/Rev | 16,13 % |
| Net Margin | **SÍ** | NetIncome, Revenue | CNV | NI/Rev | 10,88 % · **CNV 0,11** |
| FCF Margin | **NO** | — | — | — | **falta CapEx** |
| ROE | **SÍ** | NetIncome, Equity | CNV | NI/Eq cierre | 13,80 % · **CNV 0,15 ⚠** |
| ROE promedio | **SÍ** | + Equity FY-1 | CNV | NI/prom(Eq) | 16,66 % |
| ROA | **SÍ** | NetIncome, Assets | CNV | NI/Assets | 9,53 % · **CNV 0,10** |
| **ROIC** | **SÍ** | EBIT, IncomeTax, PretaxIncome, Debt, Equity, Cash | CNV | NOPAT/(D+E−C) | **13,73 %** |
| ROCE | **SÍ** | EBIT, Assets, LiabCurrent | CNV | EBIT/(A−PC) | 17,18 % |
| FCF on CE | **NO** | — | — | — | **falta CapEx** |
| Debt/Equity | **SÍ** | DebtCur+DebtNC, Equity | CNV | D/E | 0,1505 |
| Liabilities/Equity | **SÍ** | Liabilities, Equity | CNV | L/E | 0,4475 · **CNV 0,45** |
| **Debt/EBITDA** | **SÍ** | Debt, EBITDA | CNV | D/EBITDA | **0,5632 · CNV 0,56** |
| Net Debt/EBITDA | **SÍ** | Debt, Cash, EBITDA | CNV | (D−C)/EBITDA | 0,1107 |
| Interest Coverage | **SÍ** | EBIT, InterestExpense | CNV | EBIT/\|Int\| | 3,7377 · **CNV −3,74** |
| CFO/Debt | **SÍ** | CF_Operativo, Debt | CNV | CFO/D | 0,6160 |
| FCF/Debt | **NO** | — | — | — | **falta CapEx** |
| Current Ratio | **SÍ** | AC, PC | CNV | AC/PC | 1,3362 · **CNV 1,34** |
| Quick Ratio | **NO** | Inventory | CNV | (AC−Inv)/PC | **Inventory se corta en 2022-09-30** |
| Cash Ratio | **SÍ** | Cash, PC | CNV | Cash/PC | 0,4693 |
| CFO/Revenue | **SÍ** | CF_Operativo, Revenue | CNV | CFO/Rev | 7,31 % |
| FCF | **NO** | CapEx | — | CFO−CapEx | **`CF_Inversion` no lo aísla** |
| FCF/Net Income | **NO** | — | — | — | **falta CapEx** |
| P/E | **SÍ** | precio, EPS_basico | CNV + Market | P/EPS | **11,0944** |
| P/B | **SÍ** | precio, Equity, Capital | CNV + Market | P/(Eq/Cap) | 1,5094 |
| P/S | **SÍ** | precio, Capital, Revenue | CNV + Market | MC/Rev | 1,1908 |
| P/FCF | **NO** | — | — | — | **falta CapEx** |
| **EV/Revenue** | **SÍ** | MC, Debt, Cash, Revenue | CNV + Market | EV/Rev | **1,2141** |
| **EV/EBIT** | **SÍ** | + EBIT | CNV + Market | EV/EBIT | **7,5286** |
| **EV/EBITDA** | **SÍ** | + EBITDA | CNV + Market | EV/EBITDA | **5,7577** |
| FCF Yield | **NO** | — | — | — | **falta CapEx** |
| Payout | **NO** | dividendos | — | Div/NI | **0 filas en `cnv_dividendos`** |
| Dividend Yield | **NO** | DPS | — | DPS/precio | ídem |
| Dividend/FCF | **NO** | — | — | — | ídem |

### Los 12 no calculables: **tres causas, no doce**

```
falta CapEx ..................... 9 ratios
Inventory sin dato desde 2022 ... 1
sin dividendos .................. 3   (uno solapa con CapEx)
```

**Nota frente a KO:** `EV/EBITDA`, `Debt/EBITDA` y `ROIC` **sí salen acá** y en
Coca-Cola no. CNV publica `EBITDA` como concepto y separa
`DebtCurrent`/`DebtNonCurrent`; el XBRL de KO no daba un total de deuda.

---

## 7. Market data compatibility

**COMPATIBLE.** El dato existe en las dos superficies:

```
canónica   market_price_daily · instrument_id 38 · METR/BUE/ARS
           6.637 velas · 2000-01-03 .. 2026-08-27 · último 2.350,00
legacy     instrumentos · instrumento_id 38 · fuente iamc/yfinance · 1.923,00
```

Habilita **6 ratios de valoración**: P/E, P/B, P/S, EV/Revenue, EV/EBIT, EV/EBITDA.

**Dos salvedades:**

1. `identity_v1.instrument` para `MKT:38` → **0 filas.** El instrumento no está
   ligado a la entidad. El motor canónico se negaría a atribuir el precio; el
   legacy une por ticker.
2. **CNV no publica el conteo de acciones.** `Capital = 569.000.000` sirve de
   divisor y se valida con la identidad del EPS (`NI individual / Capital =
   229,62`, exacto), pero **es una inferencia**. P/B, P/S y market cap la heredan.

---

## 8. Provenance compatibility

| eslabón | CNV (METR) | SEC (KO) |
|---|---|---|
| ratio → fórmula → inputs | sí | sí |
| concepto normalizado | `cnv_estados_norm.concepto` | `derived.fact.tag` |
| escala / reexpresión | **sí** — `escala`, `fecha_reexpresion` | no aplica |
| perímetro | **sí** — `tipo_balance` | no aplica |
| dato extraído | `cnv_estados_v2` (mismo `accn`) | `parsed.facts` |
| documento | **`eeff/eeff_html/{guid}.html` — 56/56** | `data/raw/engine/CIK…` |
| presentación | `accn` (GUID) · `form` · `fuente=cnv-aif2` | `accession_number` |
| **hash del archivo** | **NO EXISTE** | `parsed.facts.source_hash` |
| entidad canónica | **NO** — METR fuera de `identity_v1` | `entity_key` |

**La cadena llega al archivo pero no al hash.** Se puede decir *de qué documento*
salió el dato, no *de qué archivo con qué huella*.

---

## 9. Canonical Engine compatibility

# NO COMPATIBLE HOY

Cuatro columnas `NOT NULL` que un dato CNV **no puede satisfacer**:

| tabla | columna | por qué bloquea a METR |
|---|---|---|
| `parsed.facts` | **`cik`** NOT NULL | **METR no tiene CIK** — no tiene ADR, no presenta ante la SEC |
| `parsed.facts` | **`source_hash`** NOT NULL | ninguna tabla CNV guarda sha256 |
| `parsed.facts` · `derived.fact` | **`qname`** NOT NULL | es el *qualified name* XBRL. CNV tiene `concepto`, no qname |
| `derived.fact` | **`context_id`** NOT NULL | es el id del contexto XBRL. **No existe en CNV** |
| `derived.fact` | **`entity_key`** NOT NULL | METR no está en `identity_v1` (0 filas) |
| `derived.fact` | `fact_key ~ '^[0-9a-f]{64}$'` | exige sha256 |
| `derived.fact` | `ck_fact_tiene_origen` | exige `source_fact_ids` que resuelvan a `parsed.facts` |
| `derived.fact` | guarda F-061 | exige que cada puntero coincida en `cik`, `accession_number` y `qname` |

**No son detalles de configuración.** El esquema está afirmando que un hecho
proviene de un filing XBRL: `cik`, `qname`, `context_id` y `source_hash` son
propiedades del modelo XBRL, no del modelo CNV.

Y no hay puente: `parsed.facts.source_kind` sólo contiene `XBRL_INSTANCE`,
`XBRL_PACKAGE_ZIP`, `XBRL_PACKAGE_ZIP_INLINE`. **Cero namespaces CNV en
`derived.fact`. Cero filas de METR en `parsed.facts`.**

---

## 10. Gaps

### Falta de datos
- **`CapEx`** — no existe como concepto; `CF_Inversion` no lo aísla. **Bloquea 9 ratios.**
- **`Inventory`** — sólo hasta 2022-09-30. Bloquea quick ratio. *(La CNV lo confirma: publica `prueba_acida = liquidez`.)*
- **dividendos** — 0 filas. Bloquea 3 ratios.
- **conteo de acciones** — CNV no lo publica; se infiere de `Capital`.
- **hash del documento** — ninguna tabla CNV lo guarda.

### Falta de integración
- METR **no está en `identity_v1`** (0 filas, con cualquier estado).
- El instrumento `MKT:38` **no está ligado** a ninguna entidad.
- **No existe C4/C5**: ningún camino CNV → `parsed.facts` → `derived.fact`.
- `ratios_cnv` no lleva perímetro ni se conecta con `derived.ratio`.

### Diferencias de definición
- `CNV_roe = 0,15` **no se reproduce** con ninguno de los tres denominadores probados (0,1380 / 0,1666 / 0,1363). **Discrepancia abierta.**
- Las coberturas de la CNV vienen **con signo negativo** (arrastra el del costo financiero); en magnitud coinciden al cuarto decimal.
- `CNV_roa` difiere 4,7 % — atribuible al redondeo a 2 decimales de la CNV.
- CONSOLIDADO vs INDIVIDUAL: hasta **76,7 % de diferencia** en el mismo período.

### Problemas de implementación
- `s0`, `s2` y `s4` hacen `DROP TABLE`: no hay modo «un emisor».
- Los jobs no tienen `argparse`.
- `ratios_cnv` con `PRIMARY KEY (cuit)`: un solo perímetro.
- La fila actual de METR mezcla ventana TTM con trimestral (§4.4).

---

## 11. Minimum implementation required

**Para llegar de CNV a ratios completos y reproducibles (fases A–F):**

> **Un script de cálculo de ratios que lea `cnv_estados_norm` filtrando por
> `(cuit, period_end, tipo_balance)` y emita a un CSV, sin tocar la base.**

Nada más. Ni migración, ni cambio de esquema, ni tocar el pipeline existente. Los
30 ratios de §6 salen de datos que ya están materializados.

**Para llegar al engine canónico (fase G)** — otro orden de magnitud:

1. **Promover METR a `identity_v1`** con evidencia admitida (AFIP o HUMAN; no
   GLEIF ni SEC_20F, que no aplican).
2. **Ligar `MKT:38`** a esa entidad.
3. **Decidir el modelo de hechos no-XBRL**: o se relajan `cik`, `qname` y
   `context_id` a NULL-able —lo que debilita las garantías que protegen a los
   513 emisores SEC—, o se crea una vía paralela (`parsed.cnv_facts`) con su
   propio contrato.
4. **Agregar sha256** a la capa CNV, para que la provenance llegue al archivo.
5. **Escribir C4/C5**: el parser HTML canónico y su normalización.

Los pasos 3 y 5 son proyecto, no cambio.

---

## 12. Recommended execution order

**Hoy, sin escribir código y sin riesgo — lectura pura:**

```
1.  verificar cnv_estados_norm de METR      SELECT, ya validado: 2.747 filas
2.  s1_bimoneda.py --ticker METR --dry-run  ADITIVO y filtrable
3.  s3c_refrescar_precios.py --dry-run      no destructivo
4.  contraste vs los 12 ratios CNV          ya hecho: 7 MATCH · 1 redondeo
                                             2 signo · 1 N/D · 1 abierta
```

**Con un script nuevo (fase D):**

```
5.  calcular los 30 ratios por (cuit, period_end, tipo_balance) → CSV
6.  repetir para los 27 períodos consolidados y los 29 individuales
7.  contrastar cada uno contra su ratio CNV DEL MISMO PERÍMETRO
```

**NO ejecutar todavía:**

```
s0_normalizar_cnv.py     DROP TABLE cnv_estados_norm — reconstruye las 72
s2_ratios_cnv.py         DROP TABLE ratios_cnv
s4_ensamblar.py          DROP TABLE screener — alimenta la API y la página
job5_v2 / job2           innecesarios: el RAW está completo (56/56)
```

---

## Respuestas directas

**1 · ¿Qué ya existe exactamente?** Las fases A, B, C y E completas, **y ya
corrieron para METR**: 2.747 filas normalizadas, 56/56 documentos con RAW,
6.637 velas de precio.

**2 · ¿Qué se reutiliza sin modificaciones?** Ocho scripts. Cuatro filtran por
emisor: `job2 --empresas`, `job5_v2 --cuits`, `s1_bimoneda --ticker`,
`s3b --grupo`.

**3 · ¿Qué es incompatible con el flujo canónico?** Toda la cadena SQLite:
`cnv_estados_norm` no tiene `cik`, `qname`, `context_id` ni `source_hash`, que
son `NOT NULL` del lado canónico.

**4 · ¿Qué datos de METR existen y dónde?** §5.

**5 · ¿Qué ratios se pueden calcular?** **30 de 42.**

**6 · ¿Cuáles requieren datos inexistentes?** 12, por tres causas: CapEx (9),
Inventory post-2022 (1), dividendos (3).

**7 · ¿Diferencias entre el modelo CNV y el EDGAR?** EDGAR: XBRL tipado, `cik`,
`qname`, `context_id`, hash por archivo, un parser para 513 emisores. CNV: HTML,
`cuit`, `concepto`, GUID, sin hash, **más** escala, reexpresión IAS 29, RECPAM y
perímetro — 14 columnas de corrección que el XBRL nunca necesitó.

**8 · ¿Se puede reproducir el pipeline KO con METR?** **Conceptualmente sí, y en
varios aspectos mejor**: METR tiene 30 períodos contra 17 de KO, EBITDA reportado
en vez de construido, deuda desagregada, y 12 ratios oficiales del regulador para
contrastar. **Lo que no se puede reproducir es el destino**: KO terminó en
`derived.fact` con hash; METR termina en SQLite sin hash.

**9 · ¿Qué se puede hacer hoy sin código?** Los pasos 1–4 de §12. Todo lectura.

**10 · ¿Mínimo cambio?** Para A–F: **un script de ratios que no escriba en la
base.** Para G: identidad + decisión sobre hechos no-XBRL + C4/C5.
