# Etapa 4 — Pipeline CNV (jobs)

> El trabajo grande reciente: descubrir y extraer los estados contables y dividendos de
> las ~556 entidades registradas en la CNV, de forma segmentada y resume-safe. Es la
> fuente local (ARS, NIC 29) para ADR y BYMA-only. Ver [00_VISION_GENERAL.md](00_VISION_GENERAL.md).
>
> Manual de ejecución paso a paso: [jobs/README.md](../../scripts/tickets/cnv/jobs/README.md).

## Qué hicimos

### El descubrimiento (la "mina 556")
La CNV expone en `aif2.cnv.gov.ar` los estados contables de **todas** las entidades
registradas (~556: cotizantes + ADR + emisoras de ON que no cotizan equity), con una
**plantilla estandarizada por códigos de 7 dígitos** (`1999999`=Activo, `3049999`=Net
Income, `3021800`=RECPAM...) más **ratios pre-calculados oficiales** (ROE, ROA, liquidez...).
Es data pública, estructurada, auto-validable (identidad contable) y sin cobertura de
analistas → "mina de oro".

Descubrimiento clave de eficiencia: la **company page** de cada empresa (1 request) ya
trae **todos** sus GUIDs agrupados por tipo de formulario en un acordeón. Parsear eso
**offline** reemplaza abrir 79.772 `publicview` uno por uno (~9 h) por segundos.

### Los jobs (ETL segmentado)
En [scripts/tickets/cnv/jobs/](../../scripts/tickets/cnv/jobs/), diseñados en pasos chicos,
secuenciales, resume-safe, con `--rango` (segmentar) y `--max` (tope de requests/corrida):

| Job | Qué | Costo |
|---|---|---|
| `job1_universo.py` (D1) | AutoComplete → `empresas_556.csv` | 1 req |
| `job2_download.py` (D2) | company pages → `html_descargados/` (`--empresas` para subset) | ~556 req |
| `job3_formtype.py` (D3) | **offline**: parseo del acordeón → `guid_formtype.csv` | 0 req |
| `job4_clasificar.py` (D4) | **offline**: whitelists EEFF/DIV + `tabla_maestra.csv` | 0 req |
| `build_subset.py` | subset prioritario (56 BYMA + 17 ADR) → `empresas_subset.csv` | 0 req |
| `job5_extract_eeff.py` (E) | publicview → parser por código → `cnv_estados` (`--cuits` scope) | rate-limited |
| `job6_extract_div.py` (E) | publicview → `cnv_dividendos` (`--solo dividendo`) | rate-limited |
| `job7_validar.py` | **offline**: identidad contable → `cnv_estados_suspect` (`--purge` selectivo) | 0 req |

**Diseño**: *Discovery* (barato, cacheable, offline) separado de *Extract* (rate-limited,
segmentable). Se paraleliza **entre** fuentes, nunca dentro de un host con rate limit.

### Parser validado
El parser de EEFF (`job5`, idéntico a [`extract_aif2_masivo.py`](../../scripts/tickets/cnv/scripts/extract_aif2_masivo.py))
lee la planilla por código y **valida la identidad contable** (Activo = Pasivo + PN).
En Ledesma dio 0.000 % de error → parser sano.

## Por qué
Para reconstruir ratios estilo GAAP de empresas **sin cobertura SEC** (BYMA-only) y tener
la versión local de los ADR, usando data oficial, estructurada y auto-validable.

## Resultados (subset, 2026-07)

```
job1_universo    555 empresas → empresas_556.csv
job2_download    559 company pages
job3_formtype    272.008 GUIDs clasificados
job4_clasificar  57.648 EEFF / 139.814 DIV (whitelists)
build_subset     72 empresas (70 + PATA/BOLT reales)
job5_extract     31.626/31.626 EEFF (100%) → 143.354 filas en cnv_estados
job6_extract     3.225/3.225 dividendos → cnv_dividendos
job7_validar     21 suspect → 11 basura purgados, 10 preservados (bancos)
Cobertura        124 empresas, mayoría 28-33 períodos (~15 años)
Identidad >5%    ~0,3% (solo bancos/plantilla vieja, marcados)
```

Aprendizajes de la corrida:
- **Latencia**: `www.cnv.gov.ar` (company pages) va lento (~32 s/req); `aif2` (publicview)
  va rápido (~0,3 s/req). Por eso el subset se extrajo en ~horas, no días.
- **Hit rate ~9 %**: cada "Estados Contables" son ~11 GUIDs (carátula, auditor, notas,
  anexos) y **solo 1** trae la planilla de códigos. El resto cae como `err` — es la
  estructura, no una falla.
- **Métrica de cobertura real** = `COUNT(DISTINCT period_end)` por empresa, no el hit rate.
- **Bancos**: usan la plantilla de entidades financieras (sin códigos de 7 dígitos) →
  extracción CNV parcial/vacía. Para esos, la fuente es EDGAR/yfinance.

## <a name="deuda-técnica-clave"></a>⚠️ DEUDA TÉCNICA: normalización de clave (BLOQUEANTE)

`job5` guardó las filas nuevas de `cnv_estados` con:
- `cik` = **CUIT** (11 dígitos) — porque `whitelist_eeff.csv` no tenía columna ticker.
- `ticker` = **nombre de empresa** (no el símbolo).

Esto choca con el resto de la base:

| Fuente | `cik` | `ticker` |
|---|---|---|
| yfinance / CNV viejo | `BYMA-ALUA` | `ALUA` |
| **CNV nuevo (job5)** | `30500010951` | `LEDESMA S.A.A.I.` |

**Consecuencias**: (1) las 56 BYMA pueden estar **duplicadas** (bajo `BYMA-X` viejo y
CUIT nuevo); (2) las filas nuevas **no joinean** con `empresas`/`facts`/`precios`.

**Qué hacer antes de calcular ratios CNV** (orden):
1. Diagnóstico: cuántas filas `BYMA-*` vs `CUIT` hay, y si las 56 están duplicadas.
2. `normalizar_cnv_estados.py` (a construir): mapear CUIT→ticker vía `empresas_subset.csv`,
   backfillear `cuit` en `empresas`, unificar clave (recomendado: **key por CUIT** +
   tabla de mapeo `cuit ↔ ticker ↔ cik`), deduplicar viejo/nuevo (preferir el nuevo:
   historial completo + identidad validada).
3. `calcular_ratios_cnv.py` (a construir): último período no-suspect por empresa → ratios
   (pre-calc CNV + fallback computado, CAGR) → tabla `ratios_cnv`.

## Qué falta / limitaciones
- **Normalización de clave** (arriba) — bloquea la capa de ratios.
- **Capa de ratios CNV** y **ensamblado del screener** (merge EDGAR + yfinance + CNV).
- **Parser bank-aware** (plantilla financiera).
- **Extracción full-556**: hoy solo el subset (70). El pipeline ya escala con `--rango`.
- **Dividendos texto libre**: `job6` guarda el HTML crudo y extrae candidatos por regex;
  Hechos Relevantes/Actas requieren parseo de texto posterior.

## Archivos clave
- Jobs + manual: [jobs/](../../scripts/tickets/cnv/jobs/) · [jobs/README.md](../../scripts/tickets/cnv/jobs/README.md)
- Parser masivo original: [`extract_aif2_masivo.py`](../../scripts/tickets/cnv/scripts/extract_aif2_masivo.py)
- Diseño del pipeline: [PIPELINE_CNV.md](PIPELINE_CNV.md)
