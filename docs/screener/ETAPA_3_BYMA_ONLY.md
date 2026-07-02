# Etapa 3 — BYMA-only (cotizan solo en Argentina)

> 56 empresas que cotizan **solo en BYMA**, sin presentación en SEC. No hay EDGAR para
> ellas → se cubren con **yfinance** y **CNV**. Ver [00_VISION_GENERAL.md](00_VISION_GENERAL.md)
> y la lista en [LISTA_56_CNV.md](LISTA_56_CNV.md).

## Qué hicimos

### 3.1 — yfinance (base fundamental)
[`cargar_byma_yfinance.py`](../../scripts/tickets/cnv/scripts/cargar_byma_yfinance.py) baja
income/balance/cashflow (**~160 tags** por papel, ticker `.BA`) a la **misma** `facts`:
- Guarda **todos** los tags: ~25 mapeados a concepto canónico (los lee el motor de
  ratios) + el resto crudo (`concepto=NULL`) para el futuro.
- `cik` = `BYMA-{ticker}` (ej. `BYMA-ALUA`), `taxonomia='yfinance'`, `grupo='byma_yf'`.
- CapEx/Dividends vienen negativos en yfinance → se guardan en valor absoluto.
- Cache crudo re-parseable en `data/raw/yfinance/{ticker}.json`.
- Descarga con delay + retry ante 429 (yfinance no tiene límite oficial).

### 3.2 — CNV (estados contables locales)
Vía el pipeline de jobs (subset), se extrajeron los **estados contables NIIF/NIC 29** de
las 56 desde CNV aif2 (plantilla estandarizada por código de 7 dígitos). Ver
[ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md).

## Por qué

- **No tienen EDGAR** → yfinance es la única API de fundamentales lista para consumir.
- yfinance para BYMA **ya viene ajustado por NIC 29** (no nominal); el último año es
  confiable, el penúltimo suele estar "sucio" por reexpresión (problema de *vintage*).
- **CNV** aporta lo que yfinance no: el detalle por código, los **ratios pre-calculados
  oficiales** (ROE, ROA, liquidez, solvencia...) y la serie histórica larga (~15 años),
  con **auto-validación** por identidad contable (Activo = Pasivo + PN).

## Datos que produce
- `facts` (grupo `byma_yf`, taxonomía `yfinance`) → alimenta `ratios`/`precios`.
- `cnv_estados` (extracción CNV) → conceptos + ratios CNV.

## Qué falta / limitaciones
- **Normalización de clave (deuda técnica)**: la extracción CNV nueva guardó `cik`=CUIT
  y `ticker`=nombre, mientras que yfinance usa `cik`=`BYMA-{ticker}`. **No joinean**.
  Hay que mapear CUIT→ticker→`BYMA-{ticker}` y deduplicar contra la extracción CNV vieja
  (que sí usaba `BYMA-{ticker}`). Detalle en [ETAPA_4](ETAPA_4_CNV_PIPELINE.md#deuda-técnica-clave).
- **Bancos** (ej. Banco Hipotecario) tienen poca cobertura CNV (plantilla financiera) →
  se completan con yfinance.
- **DGCE** (CUIT 33657865279): no está en el registro AutoComplete de CNV → sin data CNV,
  solo yfinance.
- **Errores de dato conocidos en `empresas.csv`**: `PATA` tiene el CUIT de Banco Patagonia
  y `BOLT` el de B-Gaming (razón social CNV distinta del ticker). Verificar la identidad
  real si se los usa. Se agregaron manualmente al subset (70 → 72).
- **Payout / dividendos**: `payout=0` puede ser genuino o dato faltante → verificar contra
  la serie `.dividends` de yfinance y `cnv_dividendos`.

## Archivos clave
- Loader yfinance: [`cargar_byma_yfinance.py`](../../scripts/tickets/cnv/scripts/cargar_byma_yfinance.py)
- Lista de las 56: [LISTA_56_CNV.md](LISTA_56_CNV.md)
- Comparación 13 ratios CNV vs yfinance (ejemplo ALUA): [`comparar_13_ratios.py`](../../scripts/tickets/cnv/scripts/comparar_13_ratios.py)
