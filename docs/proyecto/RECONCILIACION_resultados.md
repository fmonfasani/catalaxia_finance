# Resultados de la reconciliación EERR (2026-07-14)

Metodología: ver [RECONCILIACION_metodo.md](RECONCILIACION_metodo.md).
Comparación de los **últimos 4 trimestres comunes**, tolerancia 10%, `eerr_externos` (investing,
standalone) vs `cnv_estados_v2` (nuestro, YTD des-acumulado con `fiscal_calendar`).

## Hallazgo central
En las empresas con extracción sana, **el trimestre más reciente matchea casi exacto**
(mismo vintage de pesos). Los trimestres viejos divergen por **reexpresión inflacionaria**
(cada balance reexpresa el pasado). Ejemplos:
- DGCU2 25-12: 87.251 (mío) vs 87.251 (ext) — idéntico.
- METR 25-12: 318.663 (mío) vs 318.663 (ext) — idéntico.

## Veredictos (20 empresas con EERR)

| Sector | Ticker | Veredicto | Nota |
|---|---|---|---|
| Energía | **DGCU2** | ✅ CONFIABLE | último trim exacto |
| Energía | **METR** | ✅ CONFIABLE (borderline) | último trim exacto; OI/NI 2-3/4 |
| Energía | TGNO4 | ❌ ESTRUCT | investing sin Revenue/OI; EBITDA no cierra |
| Energía | TRAN | ❌ ESTRUCT | Revenue ~70% del externo, 25-06 roto |
| RealEstate_Agro | **AGRO** | ✅ CONFIABLE | 3/4 en toda la cascada |
| Consumo | GRIM | ⚠️ REVISAR | Rev 3/4, abajo diverge |
| Consumo | MOLI | ⚠️ REVISAR | Rev/GP/NI ok, EBITDA 0/4 |
| Consumo | BOLT_2 | 🔧 CORRUPTO | escalas mezcladas + fiscal atípico |
| Consumo | PATA_2 | 🔧 CORRUPTO | des-acum da negativos |
| Financiero | BHIP | 🏦 FIN:NI-ok | solo NetIncome; 2/4 |
| Financiero | VALO | 🏦 FIN:NI-ok | solo NetIncome; 2/4 |
| Infra_Utilities | AUSO | ❌ ESTRUCT | operativo no cierra |
| Materiales | ALUA | ⚠️ REVISAR | Rev 3/4, resto no |
| Otros | A3 | 🔧 CORRUPTO | des-acum negativa + cambio de ejercicio |
| Otros | BYMA | ❌ ESTRUCT | operativo 0/4 (revisar mapeo/unidades) |
| Otros | CECO2 | ⚠️ REVISAR | Rev 3/4 |
| Otros | ECOG | ⚠️ REVISAR | solo 8 períodos; operativo 0/4 |
| Otros | FIPL | 🔧 CORRUPTO | escalas mezcladas |
| Otros | GCLA | 🔧 CORRUPTO | escalas de 10³ a 10¹⁵ + fecha 2024-11-08 |
| Otros | RIGO | ⚠️ REVISAR | fiscal atípico (ago/nov) |

## Lectura
- ✅ **Confiables: 3** (DGCU2, METR, AGRO).
- 🔧 **Corruptos por extracción: 5** (GCLA, A3, FIPL, BOLT_2, PATA_2) — **máxima prioridad de fix**:
  no es problema de método sino de datos crudos mal parseados (unidades/vintage/fechas).
- ❌ **Estructural: 4** (TRAN, TGNO4, AUSO, BYMA) — revisar mapeo de entidad y unidades.
- 🏦 **Financieras: 2** (BHIP, VALO) — solo NetIncome evaluable.
- ⚠️ **Revisar: 6** (GRIM, MOLI, CECO2, RIGO, ALUA, ECOG).

## Próximos pasos sugeridos
1. **Corruptos**: auditar la extracción cruda de esas 5 en `cnv_estados_v2` (buscar filas con
   escala/fecha anómala; ej. GCLA 2024-11-08 y el valor 5,17e15). Definir contrato de unidades.
2. **Estructural**: revisar CUIT/mapeo (BYMA, TRAN) y `fy_end_month`.
3. Recién con los datos sanos, correr los fixes de pipeline (`s4_ensamblar.py`, `s8_calidad.py`).
