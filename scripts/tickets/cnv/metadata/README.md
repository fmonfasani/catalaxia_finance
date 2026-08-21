# Capa de metadata CNV + PER estilo IAMC (Camino B)

Arregla de raíz el PER de las acciones argentinas (only-BYMA). El problema no era
NIC-29: los datos de CNV son **acumulados YTD** y el pipeline tomaba un **período
interino** en vez del TTM. Para des-acumular bien hace falta el **fin de ejercicio
por empresa**, que **no se puede adivinar** (se probó: detector 2/5 vs verdad
conocida). Acá se saca de la **fuente autoritativa**: las páginas de entidad de la CNV.

## Flujo (reproducible)

```
1) fetch_cnv_pages.py       # (necesita red) baja las páginas de entidad que falten
                            #   a scripts/tickets/cnv/datos/html_descargados/ + ingest_log
2) build_fiscal_calendar.py # (sin red) parsea el cache -> cnv_filings, cnv_documents,
                            #   fiscal_calendar (FY-end por CUIT, autoritativo)
3) recompute_ttm.py         # (sin red) des-acumula con el FY, suma TTM, aplica gates
                            #   IAMC -> tabla per_ttm (paralela, no toca screener)
   recompute_ttm.py --test  # tests golden (GRIM debe dar TTM>0)
```

## Tablas que produce (en data/screener.db)

| Tabla | Qué |
|---|---|
| `cnv_filings` | 1 fila por presentación: norma, tipo balance, periodicidad (A/T), fecha_cierre, archivo fuente |
| `cnv_documents` | punteros `publicview` (docid) a los documentos — para la futura re-ingesta de los NÚMEROS |
| `fiscal_calendar` | FY-end por CUIT = mes del último cierre **anual**; `inconsistent=1` si cambió en el tiempo |
| `ingest_log` | auditoría de cada descarga: url, http_status, sha256, bytes, path, fetched_at |
| `per_ttm` | EPS/PER TTM estilo IAMC + `estado` (ok / perdida_real / per_fuera_rango / sin_precio / sin_fiscal_calendar / stale / gap_trimestres) |

## Método (IAMC — fuente: PDF "Análisis de Acciones")

- EPS = **suma de los últimos 4 resultados netos trimestrales (TTM)**, reportado (incluye RECPAM).
- Des-acumulación: `standalone(Q) = YTD(Q) − YTD(Q−1)`; `standalone(Q1) = YTD(Q1)`.
- **PER = MarketCap / NetIncome_TTM** (robusto). Nota: la columna `screener.MarketCapUSD`
  está mal nombrada — guarda el market cap en **ARS** (= shares × precio_ars). Fallback:
  `shares = mediana(NetIncome / EPS_basico)` entre períodos si falta el market cap.
- **Gates** (si falla → guion, nunca valor adivinado): frescura (≤15m), contigüidad de
  trimestres, escala vs Revenue, y **PER fuera de [1, 100] → guion** (cap de sanidad IAMC;
  >100 y <1 son implausibles). Validado: 0 divergencias >2,5× contra el PER del screener.

## Estado actual

- FY-end resuelto para 24/75 del universo desde el cache. **Faltan 33 byma_only** →
  correr `fetch_cnv_pages.py` (necesita red hacia cnv.gov.ar).
- `recompute_ttm` sobre lo disponible: 10 PER válidos, 0 falsos positivos, GRIM golden PASS.

## Pendiente (futuro)

- **B3**: re-ingesta de los NÚMEROS desde los `cnv_documents` (docids) para provenance
  end-to-end (hoy los números vienen de `cnv_estados_v2`, cuya procedencia es parcial).
- Bancos: IAMC tiene ratios específicos; hoy usan la lógica general.
- Limpieza de entity-resolution en `mapa_entidades` (`BOLT_2`, `_ADR_0084`…).
