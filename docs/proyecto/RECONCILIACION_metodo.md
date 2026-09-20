# Reconciliación EERR: nuestros datos (CNV) vs externos (investing.com)

**Fecha:** 2026-07-14
**Objetivo:** validar cuán confiables son nuestros estados de resultados derivados de la CNV,
comparándolos línea por línea contra una fuente externa independiente (investing.com), para
determinar **qué empresas / qué sectores son confiables** y **dónde exactamente rompe** cada uno.

---

## 1. Qué comparamos

| Lado | Tabla | Naturaleza |
|---|---|---|
| **Nuestro** | `cnv_estados_v2` | Valores **acumulados YTD** (desde inicio de ejercicio), reexpresados por inflación |
| **Externo** | `eerr_externos` | Valores **trimestrales standalone** (como los publica investing) |

Líneas a comparar (cascada del estado de resultados):
`Revenue` → `GrossProfit` → `OperatingIncome` → `EBITDA` → `NetIncome`

## 2. La transformación clave: des-acumular

Nuestro dato es **acumulado**; el externo es **standalone**. Para comparar manzanas con manzanas,
des-acumulamos el nuestro:

```
standalone(Q) = YTD(Q) − YTD(Q−1)          si Q no es el 1er trimestre fiscal
standalone(Q1) = YTD(Q1)                    el 1er trimestre fiscal ya es standalone
```

El **1er trimestre fiscal** se identifica con `fiscal_calendar.fy_end_month` (mes de cierre de
ejercicio de cada CUIT). Por eso las empresas con **ejercicio atípico** (BOLT_2, RIGO, MOLI…) son
sensibles: si el `fy_end_month` está mal, la resta cruza un borde de ejercicio y da basura
(ej. Revenue negativo) — eso mismo es un hallazgo (marca dato/ejercicio mal).

## 3. Criterio de match

- Una línea/período **coincide (OK)** si `|nuestro − externo| ≤ 8% · |externo| + 1`.
- La tolerancia del 8% absorbe las diferencias de **vintage por reexpresión inflacionaria**
  (cada balance reexpresa los períodos previos a pesos del momento; períodos recientes matchean
  mejor que los viejos).

## 4. Lógica de diagnóstico (dónde rompe = qué significa)

| Patrón observado | Interpretación |
|---|---|
| **Todo coincide** (Revenue→NetIncome) | ✅ Confiable |
| Operativo OK (Revenue/OI/EBITDA) pero **NetIncome NO** | ⚠️ Rompe **abajo de la línea**: RECPAM / resultados financieros / reexpresión. Operaciones sanas |
| **Revenue ya no coincide** | ❌ Problema **estructural**: extracción, mapeo de entidad, o ejercicio mal |
| Des-acumulación da **valores negativos imposibles** | ❌ `fy_end_month` incorrecto / dato inconsistente |

## 5. Salida

Por empresa: cantidad de períodos OK por línea + **veredicto**. Agrupado por **sector** para
declarar sectores confiables. Casos especiales anotados:
- **Financieras** (BHIP, VALO): sin EBITDA/GrossProfit reales → solo se evalúa NetIncome.
- **TGNO4**: investing no trae Revenue/OperatingIncome → solo EBITDA + NetIncome.
- **ECOG**: solo 8 períodos.

## 6. Qué NO hace esta reconciliación (alcance)

- No modifica `screener`, `cnv_estados_v2` ni ningún dato productivo (solo lee).
- No corrige los ratios todavía — primero **diagnostica**. Los fixes de pipeline
  (`s4_ensamblar.py`, `s8_calidad.py`) vienen después, con este mapa como guía.
- El resultado es un **mapa de confiabilidad**, no un recálculo.
