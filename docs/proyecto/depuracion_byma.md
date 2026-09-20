# Depuración de las 56 byma_only — registro de particularidades

Cruzamos cada empresa contra datos externos (income statement, balance, cash flow, ratios,
en millones de ARS) para detectar y documentar los problemas de datos de cada una.
Fuente externa del usuario: tipo investing.com ("BYMAm").

## Convenciones de estado
- ✅ **OK** — el dato mapea limpio contra la fuente externa.
- ⚠️ **Parcial** — algunos ratios sí, otros no (con el motivo).
- ❌ **Roto** — necesita tratamiento especial.

## Problemas transversales detectados (afectan a varias)
1. **Financieras** (bancos/bolsa): balance con custodia/garantías + deuda financiera ≈ 0.
   Los tags genéricos (Assets, Deuda) no aplican → ratios de activo/apalancamiento no confiables.
   El flag `es_financiera` está **incompleto** (solo BHIP, BPAT, VALO; falta BYMA).
2. **Consolidado vs Individual** — la fuente externa suele ser consolidada; nuestra extracción
   puede ser individual (o mezclada) → NetIncome/otros difieren.
3. **Reexpresión por inflación** — cada balance reexpresa los períodos anteriores; distinta
   fecha de reexpresión = distinto valor para el mismo trimestre viejo.
4. **Último trimestre faltante** — para varias, la base llega 1 trimestre atrás de la fuente.
5. **EBITDA/operativo confiable, NetIncome NO** (transversal, no solo financieras): en el muestreo,
   EBITDA coincide con la fuente externa, pero el NetIncome difiere → **ROE/PER/margen neto no confiables**.
   Causa: (a) ambigüedad de línea de resultado (`NetIncome` vs `ResultadoIntegral` — el externo se
   parece más al Integral), y (b) reexpresión por inflación (los períodos viejos difieren más).
6. **La fuente externa también tiene glitches** (ej. GRIM: 2025-09 y 2025-12 duplicados).

---

## Registro por empresa

| Ticker | Estado | Particularidades | Acción pendiente |
|---|:-:|---|---|
| **BYMA** | ❌ | **Financiera (bolsa)** no flagueada. De 12 ratios, **solo ROE confiable** (26,4% vs 27,0%). Roto: Revenue subvaluado (180k vs 269k)→márgenes inflados; Assets subvaluado (custodia ~942k)→ROA inflado; EBITDA sobrevaluado (224k vs 173k); Deuda mal clasificada (real=0); PER 13,7 vs 11,0; FCF/CE 13,7% vs 23,7%. NetIncome: último trim coincide, viejos difieren (consolidado/individual o reexpresión). Falta 2026-03. Payout/DivYield pendiente. | Tratamiento de financiera aparte; no usar ratios salvo ROE. |

| **A3** | ❌ | **Cambió el ejercicio** (marcadores anuales en Jun/Jul/Dic) → mi TTM no computa, ROE/PER/EBITDA **en blanco**. Equity 7/9 coincide, Assets 3/9, NI 3/10. Falta 2025-12 (salta a 2026-03). | Resolver calendario fiscal a mano; sin TTM confiable. |
| **GRIM** | ⚠️ | **EBITDA ✅** (45,4k≈45,3k) pero **NetIncome 0/10** → ROE 13,4% vs 5,9% ext, PER 6,7 vs 16,7. Externo ≈ mi ResultadoIntegral (16,2k) no mi NetIncome (14,9k). Equity 6/10, Assets 6/10. Ext tiene dup 2025-09/12. | Definir línea de resultado + reexpresión. Operativo OK. |
| **AGRO** | ⚠️ | **EBITDA ✅** (12,4k≈12,7k), **NetIncome 2/10** → ROE 5,0% vs 8,8%. Equity 7/10, Assets 6/10. | Ídem GRIM. Operativo OK. |
| **FIPL** | ⚠️ | **EBITDA ✅** (-5,0k≈-5,1k), **NetIncome 0/10**, Equity 4/10, Assets 4/10. ROE -22,8% vs -19,7%. | Ídem. Operativo OK; balance flojo. |

<!-- Ir agregando una fila por empresa a medida que el usuario pasa los datos. -->

### Detalle BYMA (2025-12-31, millones ARS)
| | mi base | externo | match |
|---|--:|--:|:-:|
| Equity | 653.984 | 654.090 | ✅ |
| Assets | 1.606.777 | 2.549.375 | ❌ (excluye custodia ~942.598) |
| Liabilities | 952.793 | 1.895.286 | ❌ (idem, ~942.493) |
| Deuda financiera | ~914.776 | **0** | ❌ (confunde pasivo operativo) |
| ROE | 26,4% | 25,5% | ✅ |
| PER | ~13,7 | 10,99 | ⚠️ revisar |
