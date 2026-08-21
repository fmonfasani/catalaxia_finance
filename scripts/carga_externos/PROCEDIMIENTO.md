# Procedimiento de carga de datos externos (investing.com)

**Objetivo:** cargar de forma **homogénea y una sola vez** los ratios y estados de resultados
(EERR) de investing.com de las 56 empresas `byma_only`, para después reconciliarlos contra
nuestros datos CNV. Este doc es la **fuente de verdad**. No improvisar formato.

---

## 1. Dónde se guarda todo

| Qué | Base de datos | Tabla |
|---|---|---|
| Ratios headline | `data/screener.db` | `ratios_externos` |
| EERR trimestral | `data/screener.db` | `eerr_externos` |

> Correr **siempre desde la raíz del repo** (`catalaxia-cedears-prod/`) para que el path
> relativo `data/screener.db` resuelva bien. El loader también lo resuelve solo.

### Esquema `ratios_externos` (1 fila por ticker)
| Columna | Tipo | Unidad / convención |
|---|---|---|
| `ticker` | TEXT (PK) | debe existir en `screener.ticker` |
| `per` | REAL | múltiplo (P/E Ratio) |
| `p_book` | REAL | múltiplo (Price/Book) |
| `debt_equity` | REAL | **porcentaje** (45.35 = 45,35%) |
| `roe` | REAL | **porcentaje** (14.66 = 14,66%) |
| `div_yield` | REAL | **porcentaje** |
| `ebitda` | REAL | **millones ARS** (si investing dice "B" → ×1000) |
| `fair_value` | REAL | valor (precio objetivo) |
| `fv_upside` | REAL | **porcentaje** |
| `source` | TEXT | `investing.com` (o `investing.com|USD` si reporta en USD) |
| `loaded_at` | TEXT | ISO timestamp (lo pone el loader) |

### Esquema `eerr_externos` (formato largo: 1 fila por ticker × período × concepto)
| Columna | Tipo | Unidad / convención |
|---|---|---|
| `ticker` | TEXT (PK) | debe existir en `screener.ticker` |
| `period_end` | TEXT (PK) | fin de trimestre `YYYY-MM-DD` |
| `concepto` | TEXT (PK) | uno de: `Revenue`, `GrossProfit`, `OperatingIncome`, `EBITDA`, `NetIncome` |
| `valor` | REAL | **millones**, moneda nativa |
| `periodo_tipo` | TEXT | `Q_standalone` (investing muestra trimestres standalone, NO acumulados) |
| `source` | TEXT | `investing.com` |
| `loaded_at` | TEXT | ISO timestamp |

---

## 2. Cómo cargar (procedimiento)

1. **Copiar** `template_carga.py` a un archivo nuevo, ej. `carga_2026-07-14.py`.
2. **Completar** el bloque `RATIOS` (una tupla por empresa) y/o `EERR` (un dict por empresa),
   respetando unidades del punto 1.
3. **Correr:** `python scripts/carga_externos/carga_2026-07-14.py`
4. El script imprime el status de cada carga y la **cobertura** (cuántas de 56 van y cuáles faltan).
5. Es **idempotente**: si un dato salió mal, se corrige y se vuelve a correr (pisa por PK, no duplica).

### De dónde sale cada dato en investing
- **Ratios** → pestaña `Ratios` (usar columna **Company**, no Industry) o `Financial Summary → Key Ratios`.
- **EERR** → pestaña `Income Statement` → botón **Quarterly** (¡no Annual!).
  - `Revenue` = *Total Revenues* · `GrossProfit` = *Gross Profit* · `OperatingIncome` = *Operating Income*
  - `EBITDA` = *EBITDA* · `NetIncome` = *Net Income* (el de abajo, después de minoritario).

---

## 3. Reglas de calidad (para datos homogéneos)

- **Ticker debe existir en `screener`** — el loader lo valida (`strict=True`). Si no existe, devuelve ERROR.
- **Celda vacía `-`** → usar `None` (el loader la saltea; no cargar 0 por "vacío").
- **Unidades EBITDA**: investing mezcla "B" y "M". Convertir todo a **millones** (B → ×1000).
- **Trimestres standalone**: no convertir ni acumular. Cargar como los muestra investing.
- **Casos especiales de mapeo** (¡ojo!):
  - `BOLT` en pantalla de investing = **Boldt real** → cargar como **`BOLT_2`**.
  - `PATA` en pantalla = **Importadora Patagonia real** → cargar como **`PATA_2`**.
  - Financieras (bancos): `BYMA`, `BHIP`, `BPAT`, `VALO`, `SUPV` → `ebitda = 0` (no reportan).
  - Empresas que reportan en **USD** (ej. `ADGO`): `source='investing.com|USD'` y anotar aparte.

---

## 4. Estado y control

Ver cobertura en cualquier momento:
```
python scripts/carga_externos/loader.py
```

Al 2026-07-14:
- **Ratios cargados: 15/56.** Faltan (41):
  `BOLT_2 BPAT CADO CAPX CARC CELU CGPA2 COME COUR CTIO CVH DGCE DOME ECOG EDSH FERR GARO
   GBAN GCDI HARG HAVA INTR INVJ LEDE LONG METR MIRG MOLA MORI OEST PATA_2 POLL RAGH REGE
   RICH ROSE SAMI SEMI TGNO4 TRAN TXAR`
- **EERR cargados: 4/56** (A3, GRIM, AGRO, FIPL). Faltan 52.

**Prioridad sugerida** (para validar sectores confiables primero): Energía →
`TGNO4, METR, TRAN` (DGCU2 ya validó limpio), después el resto.

---

## 5. División de tareas

- **Agente operativo:** parsea los bloques de investing y carga vía `template_carga.py`.
- **Análisis (este agente):** cuando los datos estén cargados, reconcilia `eerr_externos`
  contra `cnv_estados_v2` (des-acumulando YTD→standalone con `fiscal_calendar`) y marca en cada
  empresa **dónde diverge** (operativo vs abajo de la línea). No cargar datos manualmente en el análisis.
