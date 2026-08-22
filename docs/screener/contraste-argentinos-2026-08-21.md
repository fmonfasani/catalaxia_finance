# Contraste de los 73 papeles argentinos contra una fuente externa

Qué tan cerca estamos de los datos publicados. 1.125 comparaciones sobre
`byma_only` + `adr`, contra los datos de investing.com que ya estaban cargados
en la base. Detalle fila por fila en
`data/contraste/contraste_argentinos_vs_investing.csv`.

## Resultado crudo

| bloque | comparaciones | dentro de ±5% |
|---|---|---|
| ratios (PER, PriceBook, ROE) | 59 | 9 (15%) |
| balance (Activo, Pasivo, PN, Caja…) | 190 | 85 (45%) |
| estado de resultados | 876 | 117 (13%) |

Leído así parece un desastre. No lo es: la mayor parte tiene una sola causa, y
es corregible.

## La causa: NIC 29, no error de dato

El desvío **deriva con la antigüedad del período**, que es la firma de la
reexpresión por inflación:

| balance, mediana nuestro/investing | |
|---|---|
| 2024 | ×0,760 |
| 2025 | ×1,000 |
| 2026 | ×1,000 |

Y el número cierra exacto contra el IPC que ya está en `data/ipc_nacional.csv`:

    IPC 2025-12 / IPC 2024-12  =  10.123,67 / 7.695,76  =  1,3155
    1 / 1,3155                 =  0,7602        observado: 0,760

**Investing reexpresa cada período al poder adquisitivo del último balance;
nosotros guardamos cada período como fue presentado.** No hay un dato malo: hay
dos convenciones distintas. Sobre el período más reciente —donde no hay nada que
reexpresar— coincidimos **exacto**: Activo, Pasivo, Patrimonio, Caja,
AssetsCurrent y LiabilitiesCurrent dan ×1,000000 con desvío menor al 0,002%.

El factor de escala también es limpio y sistemático: investing publica en
millones de ARS, nosotros en unidades (×1.000.000 en 81 de 190 pares, el resto
explicado por lo de arriba).

## Lo que NO explica la inflación

Tres cosas quedan fuera y son las que valen la pena mirar:

**1. Las líneas de resultado, incluso ya normalizadas.** Con el balance clavado
en ×1,000, el estado de resultados no lo está: `OperatingIncome` mediana ×0,886
y `GrossProfit` ×0,968 contra `NetIncome` ×0,997 y `Revenue` ×1,000. Que el
resultado operativo se desvíe 11% mientras la facturación y el resultado neto
coinciden apunta a criterio de armado —qué entra en costo de ventas y qué en
gastos operativos—, no a escala.

**2. Los ratios publicados, que es lo que ve el usuario.** Con precio y balance
correctos, siguen sin coincidir:

| | pares | dentro de ±15% | desvío mediano |
|---|---|---|---|
| PriceBook | 22 | 13 (59%) | 11% |
| PER | 11 | 2 (18%) | 42% |
| ROE | 26 | 3 (12%) | 71% |

Los peores: CVH PER 14,7 contra nuestro 60,1; VALO 13,8 contra 50,7; TXAR 11,9
contra 36,0; LOMA ROE 3,4% contra nuestro 21,5%; SUPV −7,8% contra +13,6%
(**distinto signo**). Si el balance coincide y el ratio no, el problema está en
el armado del ratio: qué EPS, de qué ventana, contra qué precio.

**3. TXAR es el control que prueba que el método sirve.** 9 de 9 trimestres de
facturación en ×1,000 exacto. Cuando las convenciones se alinean, coincidimos
perfecto.

## Lo que hay que hacer

1. **Reexpresar antes de comparar.** El coeficiente ya está calculado en
   `ipc_nacional.csv` (`coef_deflacion_a_ultimo`). Sin eso, cualquier contraste
   contra una fuente argentina mide inflación, no calidad.
2. **Revisar el armado de PER y ROE**, que fallan con el balance correcto
   debajo. Empezar por SUPV, donde el signo del ROE no coincide.
3. **Decidir el criterio de `OperatingIncome`** y dejarlo escrito.

## Cobertura, que es la limitación real

Los datos externos que hay en la base cubren poco: `ratios_externos` 27 papeles,
`eerr_externos` 29, `investing_estados` 10, todos de julio 2026. De los 73
argentinos, **44 no tienen contra qué contrastarse**. Y `investing_comparacion`,
la tabla donde esto debería vivir, está **vacía**: el cruce nunca se llenó.
