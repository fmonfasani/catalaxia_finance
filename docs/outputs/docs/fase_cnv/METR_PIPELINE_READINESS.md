# METROGAS — diagnóstico de readiness del pipeline CNV

**2026-09-02** · un solo emisor · **solo lectura, sin ejecutar el pipeline**

---

# VEREDICTO

```
IDENTIFICACIÓN ................... SÍ
CNV DISCOVERY .................... SÍ    121 presentaciones
DOCUMENTO FINANCIERO ............. SÍ    56 GUIDs · 56/56 con RAW en disco
DATOS NORMALIZADOS ............... SÍ    2.747 filas
PERÍODOS ......................... 30    2018-12-31 .. 2026-03-31
CONCEPTOS ........................ 51    (39 de los 40 buscados; falta CapEx)
RATIOS CNV DISPONIBLES ........... 12 / 12
RATIOS PROPIOS CALCULABLES ....... 30 / 42
RATIOS DE VALORACIÓN CALCULABLES .. 6 / 8
MARKET DATA ...................... SÍ    6.637 velas desde 2000-01-03
PIPELINE COMPLETO DISPONIBLE ..... SÍ    con dos salvedades (§9, §11)
```

**METROGAS puede recorrer el pipeline CNV completo hoy, sin escribir código.**

---

## 1 · Identificación

| dato | valor | fuente exacta |
|---|---|---|
| Razón social | **Metrogas S.A.** | `dim_entity.nombre` · `empresas_556.csv` |
| Ticker BYMA | **METR** | `dim_entity.ticker_canonico` |
| **CUIT** | **30657863676** | `dim_entity.cuit` · `mapa_entidades.cuit` |
| **ID CNV** | **249** | `empresas_556.csv`, columna 3 |
| URL CNV | `https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30657863676` | `empresas_556.csv` |
| entity_id interno | 38 | `dim_entity.entity_id` |
| instrumento_id | 38 | `instrumentos.instrumento_id` |
| clave BYMA | `BYMA-METR` | `mapa_entidades.cik_byma` |
| Cierre fiscal | mes **12** | `dim_entity.fy_end_month` |
| Moneda funcional | ARS | `dim_entity.moneda_funcional` |
| Sector · financiera | Energía · `es_financiera=0` | `screener` |
| CIK | **ninguno** (no tiene ADR) | `dim_entity.cik = NULL` |
| Nivel de validación | `verificado-externo` · balance_ok=1 · cascade_ok=1 | `entity_validacion` |

**No está en `identity_v1`** (0 filas). La identidad de METR vive sólo en el modelo legacy.

---

## 2 · ¿Está en el padrón CNV?

# ENCONTRADA: **SÍ**

```
empresas_556.csv     ,Metrogas S.A.,249,30657863676,https://www.cnv.gov.ar/...
cnv_documents        1.681 documentos
cnv_filings            121 presentaciones
cnv_estados          2.846 filas
cnv_estados_v2       2.697 filas   ← 56 GUIDs distintos
cnv_estados_norm     2.747 filas
cnv_reextract        1.108 filas
cnv_dividendos           0          ← METR no paga dividendos
```

Aparece además en `empresas.csv`, `empresas_subset.csv`, `entidades_clasificadas.csv`
y `guid_formtype.csv`.

---

## 3 · Discovery de documentos

`cnv_filings` (121 filas) con columnas
`cuit · ticker · norma · tipo_balance · periodicidad · fecha_cierre · source_file · parsed_at`.

```
periodicidad     T (trimestral)  85
                 A (anual)       33
                 S (semestral)    3
norma            NIIF (todas)
tipo_balance     CONSOLIDADO e INDIVIDUAL, ambos, en cada cierre
source_file      30657863676_Metrogas_S_A.html
```

### El documento correcto para el pipeline, y por qué

**No hay UN documento: hay 56 GUIDs**, uno por presentación de estados contables.
Para un FY completo el criterio es:

```
fecha_cierre  = 2025-12-31        ← cierra en diciembre (fy_end_month=12)
periodicidad  = A                 ← anual, no T ni S
tipo_balance  = CONSOLIDADO       ← perímetro del grupo que cotiza
norma         = NIIF
```

Se elige **CONSOLIDADO** porque es el perímetro del grupo económico que cotiza en
BYMA. La presentación INDIVIDUAL existe y se conserva; **no se descarta, se
declara** — y en METR las diferencias son materiales (Revenue +26,9 %, CFO +76,7 %).

---

## 4 · Datos normalizados

# EXISTE: **SÍ**

```
cnv_estados_norm     2.747 filas · 51 conceptos · 30 períodos
rango                2018-12-31 .. 2026-03-31   (8 años)
por perímetro        CONSOLIDADO 1.300 filas / 27 períodos
                     INDIVIDUAL  1.397 filas / 29 períodos
                     (vacío)        50 filas /  1 período
cnv_estados_v2       2.697 filas · 56 GUIDs
ratios_cnv           SÍ — ver la advertencia de abajo
```

### Cobertura por concepto — consolidado

**39 de los 40 buscados están presentes.** Los 27 períodos son la serie completa
consolidada 2018-12-31 → 2025-12-31.

| concepto | períodos | | concepto | períodos |
|---|---:|---|---|---:|
| Revenue | 27 | | Equity | 27 |
| COGS | 27 | | DebtCurrent | 27 |
| GrossProfit | 27 | | DebtNonCurrent | 27 |
| OperatingIncome | 27 | | Receivables | 27 |
| EBIT | 27 | | Payables | 27 |
| **EBITDA** | **27** | | PPE | 27 |
| DA | 25 | | Intangibles | 27 |
| NetIncome | 27 | | CF_Operativo | 27 |
| PretaxIncome | 27 | | CF_Inversion | 27 |
| IncomeTax | 27 | | CF_Financiacion | 27 |
| Assets | 27 | | CashFlowNeto | 27 |
| AssetsCurrent | 27 | | EPS_basico | 27 |
| AssetsNonCurrent | 27 | | EPS_diluido | 25 |
| Cash | 27 | | RECPAM | 26 |
| Liabilities | 27 | | Capital | 27 |
| LiabilitiesCurrent | 27 | | WorkingCapital | 27 |
| LiabilitiesNonCurrent | 27 | | InterestExpense | 27 |
| **Inventory** | **14** ⚠ | | IngresosFinancieros | 27 |
| | | | ResultadoIntegral | 27 |

**Faltantes:**
- **`CapEx` — NO EXISTE.** `CF_Inversion` no lo aísla. Bloquea 9 ratios.
- **`Inventory` — se corta en 2022-09-30** (14 de 27 períodos). Bloquea quick ratio en FY2025. *Consistente: la propia CNV publica `prueba_acida = liquidez`, o sea que METR no maneja inventarios.*

### ⚠ Advertencia sobre `ratios_cnv`

La fila de METR existe pero **tiene un defecto de período**:

```
ultimo_periodo   2026-03-31          ← un TRIMESTRE, no un FY
MargenNeto       0.4641              vs  CNV_margen_neto 0.08
provenance       NetIncome=131.412 M [decum 2025-06-30..2026-03-31]   ← TTM
                 Revenue=283.136 M                                     ← trimestral
```

Cruza un resultado TTM des-acumulado con un ingreso trimestral. Y la tabla
**no tiene columna de perímetro**: `PRIMARY KEY (cuit)`, una fila por empresa.

---

## 5 · Historia disponible

**30 períodos.** Mezcla trimestres y cierres anuales:

```
2026-03-31  2025-12-31  2025-09-30  2025-06-30  2025-03-31  2024-12-31
2024-09-30  2024-06-30  2024-03-31  2023-12-31  2023-09-30  2023-06-30
2023-03-31  2022-12-31  2022-09-30  2022-06-30  2022-03-31  2021-12-31
2021-09-30  2021-06-30  2021-03-31  2020-12-31  2020-09-30  2020-06-30
2020-03-31  2019-12-31  2019-09-30  2019-06-30  2019-03-31  2018-12-31
```

| ventana | disponible |
|---|---|
| **Anual (cierres de diciembre)** | **SÍ — 8: 2018 a 2025** |
| **Trimestral** | **SÍ — 22** |
| Semestral | 3 presentaciones marcadas `S` |
| **TTM / LTM** | **NO como dato**. Se deriva: `recompute_ttm.py` des-acumula, y así lo hizo `ratios_cnv` |

Ojo: `tipo` en `cnv_estados_norm` es `A` = **acumulado** (YTD), no «anual». En un
cierre de diciembre, acumulado = ejercicio completo.

---

## 6 · Ratios oficiales de CNV

**Los 12 existen para METR.**

| ratio | períodos | FY2025 cons. | FY2025 indiv. |
|---|---:|---:|---:|
| CNV_roe | 30 | 0,15 | 0,15 |
| CNV_roa | 30 | 0,10 | 0,10 |
| CNV_margen_neto | 30 | 0,11 | 0,14 |
| CNV_liquidez | 30 | 1,34 | 1,22 |
| CNV_solvencia | 30 | 2,23 | 2,41 |
| CNV_endeudamiento | 30 | 0,45 | 0,41 |
| CNV_apalancamiento | 30 | 1,45 | 1,41 |
| CNV_deuda_fin_ebitda | 30 | 0,56 | 0,61 |
| CNV_ebitda_costos_fin | 30 | −4,89 | −5,27 |
| CNV_cobertura_intereses | **10** | −3,74 | −3,92 |
| CNV_prueba_acida | **10** | 1,34 | 1,22 |
| CNV_rotacion_activos | **10** | 0,88 | 0,71 |

---

## 7 · Scripts que intervienen

| etapa | archivo | entrada | salida | ejecutable solo |
|---|---|---|---|---|
| **DISCOVERY** | `cnv/jobs/job1_universo.py` | padrón CNV | `empresas*.csv` | sí, sin args |
| **FETCH** | `cnv/jobs/job2_download.py` | `empresas*.csv` | `datos/html_descargados/{cuit}_*.html` | **sí — `--empresas`** |
| **DISCOVERY** | `cnv/jobs/job3_formtype.py` | HTML de empresa | `guid_formtype.csv` | sí, `--debug` |
| **DISCOVERY** | `cnv/jobs/job4_clasificar.py` | formtypes | clasificación EEFF | sí, sin args |
| **PARSE / RAW** | `cnv/jobs/job5_v2_extract_eeff.py` | GUIDs | `eeff/eeff_html/{guid}.html` + `cnv_estados_v2` | **sí — `--cuits`** |
| PARSE | `cnv/jobs/job6_v2_reparse_div.py` | GUIDs dividendos | `cnv_dividendos` | sí |
| AUXILIAR | `cnv/jobs/job7_validar.py` | `cnv_estados_v2` | validación | sí, `--tol`, `--purge` |
| AUXILIAR | `cnv/jobs/job8_doc_meta.py` | documentos | `cnv_doc_meta.tipo_balance` | sí, sin args |
| **NORMALIZE** | `screener/s0_normalizar_cnv.py` | `cnv_estados_v2` + `cnv_doc_meta` | **`cnv_estados_norm`** | sí (`build`) |
| NORMALIZE | `screener/s1_bimoneda.py` | `cnv_estados_norm` | `valor_usd`, `mep_valor` | sí, `--corregir` |
| **RATIO** | `screener/s2_ratios_cnv.py` | `cnv_estados_norm` | `ratios_cnv` | sí (`build`) |
| **MARKET** | `screener/s3_precios.py` · `s3b_precios_historicos.py` · `s3c_refrescar_precios.py` | yfinance | `precios`, `precios_diarios` | sí |
| RATIO | `screener/s4_ensamblar.py` | `ratios_cnv` + precios | `screener` | sí (`build`) |
| RATIO | `screener/s7c_cagr.py` · `s8_calidad.py` · `s9_guards_yfinance.py` | `screener` | `screener_gold` | sí |
| AUXILIAR | `_perimetro.py` | — | regla de perímetro | módulo |
| AUXILIAR | `_ttm.py` · `metadata/recompute_ttm.py` | `cnv_estados_norm` | TTM des-acumulado | sí |
| AUXILIAR | `metadata/build_fiscal_calendar.py` | — | `fiscal_calendar` | sí |
| ORQUESTA | `screener/run_all.py` | — | todo | sí, `--with-cnv-fresh` |

---

## 8 · Pipeline real — orden extraído de `run_all.py`

```
PASO 01  job1_universo.py          padrón CNV        → empresas*.csv
PASO 02  job2_download.py          empresas.csv      → html_descargados/{cuit}_*.html
PASO 03  job3_formtype.py          HTML empresa      → guid_formtype.csv
PASO 04  job4_clasificar.py        formtypes         → clasificación EEFF
PASO 05  job5_v2_extract_eeff.py   GUIDs             → eeff_html/{guid}.html + cnv_estados_v2
PASO 06  job6_v2_reparse_div.py    GUIDs dividendos  → cnv_dividendos
PASO 07  job7_validar.py           cnv_estados_v2    → validación
PASO 07b job8_doc_meta.py          documentos        → cnv_doc_meta (tipo_balance)
─────────────────────────────────────────────────────────────────────────
PASO 08  s0_normalizar_cnv.py      cnv_estados_v2    → cnv_estados_norm
PASO 09  s1_bimoneda.py --corregir cnv_estados_norm  → valor_usd, mep_valor
PASO 10  s2_ratios_cnv.py          cnv_estados_norm  → ratios_cnv
PASO 11  s3_precios.py             yfinance          → precios
PASO 11b s3b_precios_historicos.py yfinance          → precios_diarios
PASO 11c s3c_refrescar_precios.py  precios_diarios   → precios
PASO 12  s4_ensamblar.py           ratios_cnv+precios→ screener
PASO 13  s7c_cagr.py               screener          → CAGR en USD
PASO 14  s8_calidad.py             screener          → payout/EV/margen
PASO 15  s9_guards_yfinance.py     screener          → guards + USD via MEP
```

Los jobs 1–8 corren desde `scripts/tickets/cnv/jobs/`; s0–s9 desde
`scripts/tickets/screener/`. `run_all.py` los invoca como módulos con `build` o
`main` según el caso — **`argv=[]` es obligatorio** en los que tienen argparse.

---

## 9 · ¿Podemos hacer el fetch original?

# SÍ

```
script      scripts/tickets/cnv/jobs/job2_download.py
argumentos  --empresas <csv>   --max N   --rango i j   --sleep s
endpoint    https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}
RAW         scripts/tickets/cnv/datos/html_descargados/{cuit}_{slug}.html
formato     HTML
conducta    resume-safe: saltea lo que ya está en disco
```

**Y ya está descargado:**

```
30657863676_Metrogas_S_A.html    2.083.534 bytes    2026-07-09
```

**Salvedad 1:** los jobs **no tienen `argparse`** — parsean `sys.argv` a mano. Para
correr sólo METR hay que pasarle un CSV de una fila con el formato de
`empresas_subset.csv`: `ticker,empresa,id,cuit,url_empresa,grupo`.

---

## 10 · ¿Podemos extraer el documento?

# SÍ

```
script      scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py
argumentos  --cuits <csv>  --codigos  --whitelist  --offline  --rango  --max  --sleep
formato     HTML de estados contables (uno por GUID)
RAW         scripts/tickets/cnv/eeff/eeff_html/{guid}.html
salida      cnv_estados_v2
conducta    resume-safe: saltea GUIDs cuyo HTML ya está guardado
```

**El RAW de METR está completo: 56 GUIDs, 56/56 con su HTML en disco.**

Eso significa que **el pipeline se puede recorrer entero en modo `--offline`**, sin
depender de que la CNV esté arriba.

`job5_v2` normaliza además la unidad de medida (el cambio *MILES → Millones* que
rompió la serie hacia 2021-2022) y captura `UnidadMedida` y `fecha_reexpresion`
como provenance.

Los datos actuales de METR en `cnv_estados_norm` los produjo **exactamente esta
cadena**: `job5_v2` → `cnv_estados_v2` → `s0_normalizar_cnv` → `cnv_estados_norm`,
con `job8_doc_meta` aportando el `tipo_balance` desde
`<propiedad claveinformativa="TipoBalance">`.

---

## 11 · ¿Podemos normalizar?

# SÍ

```
script    scripts/tickets/screener/s0_normalizar_cnv.py   (entry: build)
entrada   cnv_estados_v2  WHERE fuente='cnv-aif2'
          LEFT JOIN cnv_doc_meta m ON m.accn = e.accn      ← el tipo_balance
salida    cnv_estados_norm
```

Campos que produce, verificados en la tabla:

```
cuit · ticker · concepto · period_end · tipo · valor · valor_comparativo
fecha_reexpresion · form · escala · accn · fuente · source_type
tipo_balance · perimetro_mixto · identidad_desvio_pct
escala_origen · escala_revisar
valor_usd · mep_valor · mep_fecha · usd_desvio · usd_clase
coherencia_falla · valor_corregido · correccion_factor · correccion_motivo
```

| pieza | dónde | METR FY2025 |
|---|---|---|
| mapping de conceptos | `job5_v2` (del documento) + `s0` (canónicos) | 51 conceptos |
| escala | `unidad_factor` de `cnv_estados_v2` | **1.000.000** |
| moneda | `dim_entity.moneda_funcional` | **ARS** |
| `fecha_reexpresion` | capturada por `job5_v2` | 2025-12-31 |
| RECPAM | concepto extraído | 4.113 M · 26 períodos |
| `valor_usd` / `mep_valor` | `s1_bimoneda.py --corregir` | vía MEP dolarito |

**Salvedad 2:** `s0` depende de `cnv_doc_meta` para el `tipo_balance`. Si esa
tabla falta, cae a `cnv_estados_v2.tipo_balance`, y si tampoco está escribe `''` —
**y la capa de perímetro queda en cero sin avisar.** El propio código lo advierte.

---

## 12 · Ratios calculables con los datos de METR

**42 intentados · 30 calculables (71 %) · 12 no.**

| familia | calculables | valores FY2025 consolidado |
|---|---|---|
| **CRECIMIENTO** | 5/6 | Revenue +31,59 % · EBITDA +36,72 % · EBIT +35,04 % · NetIncome −15,42 % · EPS −15,39 % |
| **MÁRGENES** | 5/6 | Gross 38,21 % · EBITDA 21,09 % · EBIT 16,13 % · Operating 16,13 % · Net 10,88 % |
| **RETORNOS** | 5/6 | ROE 13,80 % (prom. 16,66 %) · ROA 9,53 % · **ROIC 13,73 %** · ROCE 17,18 % |
| **LEVERAGE** | 6/7 | D/E 0,1505 · Liab/Eq 0,4475 · **D/EBITDA 0,5632** · NetD/EBITDA 0,1107 · IntCov 3,7377 · CFO/Debt 0,6160 |
| **LIQUIDEZ** | 2/3 | Current 1,3362 · Cash 0,4693 |
| **CASH FLOW** | 1/3 | CFO/Revenue 7,31 % |
| **VALUACIÓN** | 6/8 | **P/E 11,0944** · P/B 1,5094 · P/S 1,1908 · **EV/Revenue 1,2141 · EV/EBIT 7,5286 · EV/EBITDA 5,7577** |
| **DIVIDENDOS** | 0/3 | — |

### Los 12 no calculables — tres causas, no doce

| causa | ratios bloqueados |
|---|---|
| **falta `CapEx`** (9) | FCF · FCF Margin · FCF Growth · FCF on CE · FCF/Debt · FCF/Net Income · P/FCF · FCF Yield · FCF/EV |
| **`Inventory` sin dato desde 2022-09-30** (1) | Quick Ratio |
| **sin dividendos en CNV** (2) | Payout · Dividend Yield · Dividend/FCF |

**Nota importante:** a diferencia de KO, acá **EV/EBITDA, Debt/EBITDA y ROIC SÍ
salen**, porque CNV publica `EBITDA` como concepto y `DebtCurrent`/`DebtNonCurrent`
como partidas separadas. Del lado SEC eso estaba bloqueado.

---

## 13 · Market data

# SÍ

```
instrument_id     38
ticker            METR · venue METR · exchange BUE · moneda ARS
velas diarias     6.637
rango             2000-01-03 .. 2026-08-27
último cierre     2.350,00 ARS
enlace a entidad  identity_v1.instrument → 0   ← NO ligado
```

Legacy `instrumentos`: `instrumento_id 38`, tipo `ordinaria_ar`, `fuente_precio
iamc/yfinance`, precio 1.923,00.

**Ratios de valoración habilitados combinando CNV + Market: 6** — P/E, P/B, P/S,
EV/Revenue, EV/EBIT, EV/EBITDA. Faltan P/FCF y FCF Yield, por CapEx.

**Salvedad:** el instrumento **no está ligado a la entidad** en `identity_v1`, así
que el motor canónico se negaría a atribuirle el precio. En el pipeline legacy no
es un bloqueo — se une por ticker.

Acciones: CNV **no publica el conteo**. `Capital = 569.000.000` funciona como
divisor y se valida con la identidad del EPS (`NetIncome individual / Capital =
229,62`, exacto), pero **es una inferencia, no un dato**.

---

## 14 · Contraste con los ratios oficiales de CNV · FY2025 consolidado

| ratio | CNV | propio | dif abs | dif rel | causa |
|---|---:|---:|---:|---:|---|
| CNV_margen_neto | 0,1100 | 0,1088 | −0,0012 | −1,1 % | **MATCH** |
| CNV_liquidez | 1,3400 | 1,3362 | −0,0038 | −0,3 % | **MATCH** |
| CNV_solvencia | 2,2300 | 2,2348 | +0,0048 | +0,2 % | **MATCH** |
| CNV_endeudamiento | 0,4500 | 0,4475 | −0,0025 | −0,6 % | **MATCH** |
| CNV_apalancamiento | 1,4500 | 1,4475 | −0,0025 | −0,2 % | **MATCH** |
| CNV_deuda_fin_ebitda | 0,5600 | 0,5632 | +0,0032 | +0,6 % | **MATCH** |
| CNV_rotacion_activos | 0,8800 | 0,8757 | −0,0043 | −0,5 % | **MATCH** |
| CNV_roa | 0,1000 | 0,0953 | −0,0047 | −4,7 % | **REDONDEO** — CNV publica 2 decimales |
| CNV_cobertura_intereses | −3,7400 | 3,7377 | — | — | **SIGNO** — CNV arrastra el signo del costo financiero |
| CNV_ebitda_costos_fin | −4,8900 | 4,8874 | — | — | **SIGNO** — ídem |
| CNV_prueba_acida | 1,3400 | N/D | — | — | **INPUT FALTANTE** — sin `Inventory` |
| **CNV_roe** | **0,1500** | **0,1380** | **−0,0120** | **−8,0 %** | **DISCREPANCIA ABIERTA** |

**7 MATCH · 1 redondeo · 2 diferencias de signo · 1 input faltante · 1 abierta.**

### La discrepancia abierta

`CNV_roe = 0,15`. Probamos tres denominadores y **ninguno cierra**:

```
NetIncome / Equity cierre        132.483 / 960.345 = 0,1380
NetIncome / Equity promedio                        = 0,1666
NI atribuible / Equity propietarios 130.656/958.465 = 0,1363
```

No se fuerza una explicación. **El denominador que usa la CNV no es ninguno de
los tres**, y con dos decimales de publicación no se puede inferir.

---

## 15 · Trazabilidad alcanzable

| eslabón | ¿existe para METR? | cómo |
|---|---|---|
| ratio | **sí** | calculado; fórmula explícita |
| fórmula | **sí** | declarada por ratio |
| input | **sí** | concepto + valor |
| concepto normalizado | **sí** | `cnv_estados_norm.concepto` |
| escala y reexpresión | **sí** | `escala=1000000`, `fecha_reexpresion` |
| perímetro | **sí** | `tipo_balance` = CONSOLIDADO / INDIVIDUAL |
| dato extraído | **sí** | `cnv_estados_v2` con el mismo `accn` |
| **documento** | **sí** | `eeff/eeff_html/{guid}.html` — **56/56 en disco** |
| presentación CNV | **sí** | `accn` = GUID · `form` · `fuente=cnv-aif2` |
| **hash del documento** | **NO** | ninguna tabla CNV guarda sha256 |
| entidad canónica | **NO** | METR no está en `identity_v1` |

**La cadena llega hasta el archivo. Lo que falta es el hash** — se llega a *qué
documento*, no a *qué archivo con qué huella*. Es la diferencia real con el
estándar SEC, donde `parsed.facts.source_hash` existe.

---

## 16 · Qué falta para ejecutar el pipeline completo

**Nada bloqueante.** Tres cosas a tener presentes antes de correr:

**1 · Los jobs no aceptan un CUIT suelto.** Hay que armar un CSV de una fila con
el formato de `empresas_subset.csv` y pasarlo por `--empresas` (job2) y `--cuits`
(job5_v2).

**2 · `s0` depende de `cnv_doc_meta`.** Correr `job8_doc_meta.py` antes, o el
`tipo_balance` queda vacío y la capa de perímetro se apaga en silencio.

**3 · `s2_ratios_cnv` hace `DROP TABLE` y tiene `PRIMARY KEY (cuit)`.** Correrlo
reconstruye la tabla entera para las 72 empresas y **conserva un solo perímetro
por empresa**. Es el punto que el diagnóstico multi-scope identificó.

Y dos límites del dato, no del pipeline: **sin `CapEx` no hay FCF** (9 ratios), y
**sin dividendos no hay payout** (3 ratios).
