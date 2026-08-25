# Auditoría de precios Yahoo Finance — YPF

## Conclusión ejecutiva

Sí, Yahoo Finance entrega OHLC diario para el ADR de YPF (`YPF`, NYSE, USD): **Open, High, Low y Close**. La consulta máxima devolvió **8,344 ruedas**, desde **1993-06-29** hasta **2026-08-21**. También incluye `Adj Close`, `Volume`, `Dividends` y `Stock Splits`.

El ticker canónico del screener es `YPFD`, pero el símbolo consultado en Yahoo es `YPF`. Esta relación debe conservarse explícitamente; cambiar o mezclar ambos identificadores rompe el lineage.

## Situación actual del proyecto

La tabla local `precios_diarios` contiene 32 filas para YPF/YPFD, desde 2026-07-09 hasta 2026-08-21. El inicio local no representa el máximo de Yahoo: surge del default `--desde 2026-07-09` del script actual. Por lo tanto, el backfill máximo puede ampliar la serie hasta 1993-06-29.

## Campos históricos

- `Date`: fecha de la rueda en la zona horaria del mercado.
- `Open`: apertura.
- `High`: máximo intradiario.
- `Low`: mínimo intradiario.
- `Close`: cierre sin ajuste retrospectivo.
- `Adj Close`: cierre ajustado por distribuciones/eventos según Yahoo.
- `Volume`: volumen negociado.
- `Dividends`: dividendo con fecha ex-dividendo.
- `Stock Splits`: factor de split informado.

Se observaron 58 ruedas con dividendos y 0 eventos de split en la serie descargada. La ausencia de splits en Yahoo no debe sustituir una verificación corporativa si se certifican ratios por acción.

## Universo de variables Yahoo

El snapshot contiene 170 campos de `info`, 20 campos de `fast_info`, 29 campos de metadata histórica y ocho columnas de historia/acciones. El diccionario tiene 234 filas y conserva valor de muestra, tipo, categoría, definición, semántica temporal y advertencia de estabilidad.

Los objetos tienen funciones diferentes:

- `history`: serie por fecha; fuente adecuada para OHLC, volumen y acciones corporativas.
- `fast_info`: snapshot liviano del mercado actual y rangos móviles.
- `info`: snapshot amplio de mercado, perfil, ratios Yahoo y estimaciones. Sus campos no forman un contrato estable.
- `history_metadata`: identidad del mercado, zona horaria, rangos válidos y sesión de la consulta.

## Flujo recomendado: historia máxima hasta precio actual

1. Identidad: `ticker_canonico=YPFD`, `ticker_yahoo=YPF`, mercado NYSE, moneda USD.
2. Backfill inicial: descargar `period=max`, `interval=1d`, `auto_adjust=False`, `actions=True`.
3. Guardar RAW o snapshot de respuesta antes de transformar.
4. Persistir una fila por `(ticker_canonico, fecha)` con OHLC, adjusted close, volumen, dividendos y splits.
5. Actualización incremental: consultar desde el día posterior al último almacenado hasta mañana; hacer UPSERT con log, no reemplazar la historia.
6. Mantener `Close` y `Adj Close`; nunca sustituir silenciosamente uno por otro.
7. Derivar la foto actual desde la última rueda completa y contrastarla con `fast_info.lastPrice`.
8. Registrar `fetched_at`, versión de yfinance, moneda, exchange y símbolo Yahoo.
9. Ejecutar checks OHLC, duplicados, NULL, moneda, staleness y discontinuidades.
10. Separar precio regular, pre/post market e intradiario. Esta auditoría certifica la ruta diaria regular, no ticks en tiempo real.

## Riesgos y límites

- Yahoo Finance es una fuente externa no contractual; los campos pueden cambiar.
- El precio actual puede ser intradiario, mientras el último `Close` es de una rueda completada.
- `Adj Close` es retrospectivo y puede cambiar si Yahoo corrige acciones corporativas.
- `Volume` corresponde al instrumento Yahoo (ADR), no al volumen de la acción local de BYMA.
- Los máximos/mínimos de `fast_info` son móviles de 52 semanas; no son máximos/mínimos históricos.
- Las opciones y estimaciones externas tienen calendarios y disponibilidad variables.
- No mezclar el ADR `YPF` en USD con `YPFD.BA`/mercado local en ARS. Son series distintas.

## Entregables

- `YPF_OHLC_MAX.csv`: serie diaria máxima.
- `YPF_YAHOO_DATA_DICTIONARY.csv`: diccionario completo del snapshot.
- `YPF_YAHOO_RAW_SNAPSHOT.json`: valores crudos de info, fast_info y metadata.
- `YPF_CORPORATE_ACTIONS.csv`: dividendos y splits.
- `YPF_OHLC_ANNUAL_COVERAGE.csv`: cobertura anual.
- `YPF_PRICE_QUALITY_CHECKS.csv`: controles de calidad.
- `YPF_PRICE_AUDIT_SUMMARY.json`: resumen reproducible.
