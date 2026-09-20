# FINGERPRINT REPORT — Market Data

Dos fingerprints por rueda, ambos derivables de columnas persistidas:

* **business_hash** = `instrument_id | trading_date | O H L C | volumen | dividendos | splits` (8 digitos significativos). Es el que gobierna la deteccion de cambios.
* **full_hash** = business + `Adj Close` a 5 digitos significativos. Es lo que se persiste en `market_price_daily.source_hash`.

`Adj Close` queda FUERA del business_hash porque la fuente lo recalcula en cada corrida con ruido float relativo ~1e-6. Incluirlo hacia que la serie entera apareciera CHANGED en cada corrida — la causa exacta del bug que bloqueaba esta fase. La comparacion correcta es `business_hash(actual)` vs `business_hash(reconstruido desde la base)`, nunca contra `source_hash`.

| instrument_id | ticker | ruedas | full_hash reconstruido | mismatch | batch_hash |
|---|---|---|---|---|---|
| 83 | YPFD.BA | 6634 | 6634/6634 | 0 | 192aa57329485470… |
| 84 | YPF | 8345 | 8345/8345 | 0 | 4be3bce56c3bd829… |

## 83 — YPFD.BA

batch_hash (SHA256 de los business_hash ordenados): `192aa57329485470b2e91ba7e520bb478649519d5e9e832389036ea354a9a833`

Muestra de las ultimas 5 ruedas:

| rueda | close | adj_close | business_hash | full_hash |
|---|---|---|---|---|
| 2026-08-18 | 7990.0 | 7990.0 | 94ed1c26f2cd53dd… | 3b7812691c25e96a… |
| 2026-08-19 | 7905.0 | 7905.0 | 1c9c5e9650bbcf46… | 2fa18b4d37074d48… |
| 2026-08-20 | 8045.0 | 8045.0 | 58478c93ad603587… | cea7d10f779ec567… |
| 2026-08-21 | 8150.0 | 8150.0 | 73b5b0fa4b1a3da0… | 631b2d79beecb93b… |
| 2026-08-24 | 8175.0 | 8175.0 | e051168571047352… | be662ff6b9e607b4… |

Reconstruccion 100%: releer la fila desde PostgreSQL y recalcular produce exactamente el hash almacenado.

## 84 — YPF

batch_hash (SHA256 de los business_hash ordenados): `4be3bce56c3bd82981477b2c836cd457c19ecb98ce8d869224ae72db35525333`

Muestra de las ultimas 5 ruedas:

| rueda | close | adj_close | business_hash | full_hash |
|---|---|---|---|---|
| 2026-08-18 | 50.68 | 50.68 | cc2a64c24cb05389… | b0215e7ec13de23e… |
| 2026-08-19 | 50.060001 | 50.060001 | 83c06ba5c0293b0d… | 6504a6e27952ff85… |
| 2026-08-20 | 50.919998 | 50.919998 | 833c13ec28f01b2e… | af09eb4fda198589… |
| 2026-08-21 | 51.18 | 51.18 | bee760043cc27abb… | 0aae1b2aca14e5c8… |
| 2026-08-24 | 51.279999 | 51.279999 | 5e03960978ae36da… | f49e02cce9f97977… |

Reconstruccion 100%: releer la fila desde PostgreSQL y recalcular produce exactamente el hash almacenado.
