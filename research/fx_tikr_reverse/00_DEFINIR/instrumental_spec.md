# Especificación instrumental — REQ-FX-005
# Cada FX instrumental debe ser reproducible desde: instrumento + fecha + precio ARS +
# precio USD + settlement. Sin los 5, la celda es NULL + null_reason.

version: instrumental-v1.0.0

## 1. CCL por ADR (operable, 48hs / contado inmediato según plaza)

Fórmula (idéntica a `_dolar.py::ccl_yahoo`, VERIFICADO POR CÓDIGO):

```
CCL(adr, t) = P_ARS(local, t, settlement=S) × ratio(adr) / P_USD(adr, t, settlement=S)
```

| Campo | Exigencia |
|---|---|
| instrumento | par (local, adr, ratio). Inicial: GGAL.BA/GGAL×10, YPFD.BA/YPF×1, PAMP.BA/PAM×25 |
| fecha | observation_date del par; ambas patas MISMO día (tolerancia 0 días; si difieren → NULL + MISMATCHED_LEGS) |
| precio ARS | close ajustado o último operado, con vendor + timestamp + moneda declarada |
| precio USD | idem pata USD |
| settlement | declarado por pata (p.ej. BYMA 48hs vs NYSE T+1). Si el vendor no lo declara → settlement=UNDECLARED y la celda queda flaggeada NO_DECIDE (no vota en el veredicto primario) |
| timestamp intradiario | si las patas difieren > 20 min → flag STALE_LEGS (no decide) |

Agregación pre-registrada: mediana de los ADR disponibles ese día (robusta a outlier
de un ADR). N por día = nº de pares con las 5 piezas completas. Se reportan también
los 3 valores individuales en provenance (detalle por ADR).

## 2. MEP por bono (AL30 / GD30, mismo settlement)

```
MEP(bono, t) = P_ARS(bono ARS, t, S) / P_USD(bono USD, D, t, S)
```

Mismo settlement S en ambas patas (típicamente 48hs / MEP 48hs). Bonos iniciales:
AL30, GD30. Si el vendor publica "MEP AL30 24hs" vs "48hs", son DOS series distintas
y no se mezclan. Regla de patas y settlement idéntica a §1.

## 3. Schema mínimo `instrumental_quote` (una fila por pata)

```
instrumento | plaza | fecha | settlement | precio | moneda | vendor | timestamp_vendor |
raw_ref | raw_hash | downloaded_at
```

La fila FX reconstruida cita sus 2 (MEP) o 2 (CCL) quotes + fórmula + versión.

## 4. Settlement — tabla de decisión

| Caso | Tratamiento |
|---|---|
| Ambas patas declaran mismo S | OK, decide |
| Alguna pata UNDECLARED | flag UNDECLARED_SETTLEMENT, NO decide en primario (sí se reporta) |
| S distintos entre patas | NULL + SETTLEMENT_MISMATCH |
| Feriado en una plaza (falta una pata) | NULL + MISSING_LEG (no imputar, REQ-FX-006) |

## 5. Estado actual

Implementación: NO DETERMINABLE (stub `reconstruct_mep_ccl.py` pendiente de datos
auditables). Lo único VERIFICADO POR CÓDIGO hoy es la fórmula y el universo ADR
en `scripts/dolares/_dolar.py:11-28`.
