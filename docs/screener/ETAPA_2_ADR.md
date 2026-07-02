# Etapa 2 — ADR argentinos

> Empresas argentinas con ADR en NYSE/Nasdaq. Doble naturaleza: presentan en **SEC**
> (20-F, en USD/consolidado) **y** en **CNV** (entidad local, en ARS con NIC 29).
> Ver [00_VISION_GENERAL.md](00_VISION_GENERAL.md).

## Qué hicimos

1. **Vía EDGAR** (principal): los ADR que presentan 20-F entran por el pipeline de la
   [Etapa 1](ETAPA_1_EDGAR.md) como grupo `edgar`/`adr` → `facts`, `ratios`, `precios`.
2. **Vía CNV** (paralelo): en el pipeline de jobs (subset), se identificaron y extrajeron
   las **entidades locales** de los ADR. Se armó la lista de ADR por nombre en
   [`build_subset.py`](../../scripts/tickets/cnv/jobs/build_subset.py) (`ADR_PATRONES`),
   cruzando contra el universo CNV (`empresas_556.csv`).

### ADR identificados en CNV (17, dentro del subset)
YPF, Grupo Financiero Galicia (+ Banco Galicia), Banco Macro, BBVA Argentina, Grupo
Supervielle (+ Banco), Pampa Energía, TGS, Central Puerto, Cresud, IRSA, Loma Negra,
Telecom Argentina, Ternium Argentina (ex-Siderar), Vista Energy, Aeropuertos Argentina
2000 (Corp. América). Edenor y Transener entran vía el listado BYMA por CUIT.

Notas de matching (aprendidas en el proceso):
- Los nombres comerciales no coinciden con la razón social CNV: **Edenor** = "Empresa
  Distribuidora y Comercializadora Norte SA"; **Transener** = "Cia. de Transporte de
  Energía Eléctrica"; **Corp. América** = "Aeropuertos Argentina 2000 S.A.".
- `["pampa"]` traía ruido (Banco de la Pampa, etc.) → se ajustó a `["pampa","energia"]`.
- **Bioceres** no existe en el registro CNV.

## Por qué

- **EDGAR** da la versión consolidada auditada en USD (comparable con US).
- **CNV** da la versión local: **NIC 29 (ajuste por inflación)**, RECPAM, y los ratios
  pre-calculados que exige la CNV. Sirve para (a) cross-validar EDGAR y (b) tener el
  detalle local que el 20-F resume.
- Tener ambas permite detectar diferencias de criterio (moneda, consolidación, reexpresión).

## Datos que produce
- EDGAR: en `facts`/`ratios`/`precios` (grupo `adr`).
- CNV: en `cnv_estados` (extracción nueva → `cik`=CUIT, ver deuda técnica abajo).

## Qué falta / limitaciones
- **Cruce EDGAR-ADR ↔ CNV sin hacer**: no hay tabla de mapeo `SEC-CIK ↔ CUIT ↔ ticker`.
  Es lo que impide comparar automáticamente la versión SEC vs la versión CNV del mismo ADR.
- **Bancos**: Galicia/Macro/BBVA/Supervielle usan la **plantilla financiera de CNV**
  (sin los códigos de 7 dígitos) → su extracción CNV es parcial/vacía. Para esos, el
  dato confiable es EDGAR o yfinance (ver [ETAPA_4](ETAPA_4_CNV_PIPELINE.md)).
- **Normalización de clave** pendiente (misma deuda técnica que BYMA-only).
- Falta decidir, por ratio, **qué fuente manda** cuando EDGAR y CNV difieren
  (recomendación: EDGAR para lo consolidado/USD, CNV para lo local/ARS-NIC29).

## Archivos clave
- Armado del subset ADR: [`build_subset.py`](../../scripts/tickets/cnv/jobs/build_subset.py)
- Extracción CNV: [jobs/](../../scripts/tickets/cnv/jobs/) (job5/job6)
