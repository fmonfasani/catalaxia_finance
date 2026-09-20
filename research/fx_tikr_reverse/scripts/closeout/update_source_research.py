from pathlib import Path
import csv
from datetime import date

ROOT = Path("Perplexity")

DOSSIER = ROOT / "SOURCE_DOSSIER.md"
METHODS = ROOT / "SOURCE_METHODS.md"
GAPS = ROOT / "SOURCE_GAPS.md"
MATRIX = ROOT / "SOURCE_MATRIX.csv"
TIMELINE = ROOT / "SOURCE_TIMELINE.csv"

MARKER = "<!-- FX_REVERSE_UPDATE_2026_09_15 -->"

# ============================================================
# 1. SOURCE DOSSIER
# ============================================================

DOSSIER_UPDATE = f"""
{MARKER}

# Actualización documental — 2026-09-15

## Nueva evidencia sobre S&P Capital IQ / Currency Conversion

La documentación de S&P Capital IQ identifica explícitamente el
parámetro **Currency Conversion Mode (Parameter 8)**.

Se documentan dos modalidades:

### Historical (H)

Utiliza el historical spot exchange rate correspondiente a las
fechas de fin de período.

### Current (C)

Utiliza el foreign exchange spot rate más reciente disponible y
lo aplica a los períodos históricos.

### Alcance de la evidencia

Esta documentación demuestra que el ecosistema S&P Capital IQ
dispone de una configuración explícita para controlar la
conversión histórica de monedas.

**No demuestra por sí sola qué modalidad concreta utiliza TIKR
para Argentina.**

Por lo tanto:

| Afirmación | Estado |
|---|---|
| Capital IQ documenta CCM=H | VERIFIED |
| Capital IQ documenta CCM=C | VERIFIED |
| TIKR está relacionado con S&P Capital IQ | EVIDENCIA CONTEXTUAL |
| TIKR utiliza CCM=H | NO DETERMINABLE |
| TIKR utiliza CCM=C | NO DETERMINABLE |
| TIKR utiliza A3500 | NO DETERMINABLE |
| TIKR utiliza MEP | NO DETERMINABLE |
| TIKR utiliza CCL | NO DETERMINABLE |

## Proveedores FX adicionales

Se incorporan como evidencia documental:

- S&P Global Platts — USD.ARS.
- Bloomberg / Bloomberg Barclays — referencias WMR.
- S&P DJI — WMR FX rates.
- IMF Article IV Argentina 2026 — tabla de CCL, Official y
  Forward rate.

Estas fuentes sirven para ampliar el universo de candidatos y
contrastar metodologías, pero no constituyen evidencia directa de
la metodología propietaria de TIKR.

## Estado TIKR

El estado documental correcto es:

**PARTIALLY_VERIFIED**

porque existe evidencia sobre mecanismos de conversión de moneda
del ecosistema S&P, pero no evidencia pública suficiente para
determinar la configuración específica utilizada por TIKR en
Argentina.

"""

# ============================================================
# 2. SOURCE METHODS
# ============================================================

METHODS_UPDATE = f"""
{MARKER}

# Actualización — Currency Conversion Mode de S&P Capital IQ

## Parameter 8 — Currency Conversion Mode

La documentación de S&P Capital IQ define dos modalidades
relevantes:

### CCM = H — Historical

La conversión utiliza el historical spot exchange rate
correspondiente a la fecha de cierre/período histórico.

Conceptualmente:

```text
USD_value(period_t)
    =
ARS_value(period_t)
/
FX_spot(period_t)