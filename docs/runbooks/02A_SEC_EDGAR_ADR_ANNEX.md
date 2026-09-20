# 02A · ANEXO ADR

Un ADR no es una empresa. Es un **instrumento** que representa acciones de una
empresa extranjera. Mezclar los dos objetos es el error más común y produce
ratios silenciosamente incorrectos: un P/E calculado con el precio del ADR y el
EPS de la acción ordinaria está mal por el factor del ratio DR/ORD.

Este anexo separa **tres objetos distintos** y dice qué guarda el sistema de
cada uno.

---

## 1 · Los tres objetos

```
EMISOR (issuer)              INSTRUMENTO ADR                  DATOS DE MERCADO
─────────────────            ────────────────                 ────────────────
quién publica los EEFF       qué se negocia en NYSE           qué precio tuvo
identidad: CIK / CUIT        identidad: ticker + exchange     serie temporal
un emisor                    puede tener varios instrumentos  por instrumento
20-F, 6-K                    F-6, ratio DR/ORD, depositario   moneda del venue
```

**Regla que no se negocia:** un hecho contable pertenece al **emisor**; un
precio pertenece al **instrumento**. Un ratio que combina los dos tiene que
declarar de qué instrumento salió el precio.

---

## 2 · Qué guarda el sistema

### Emisor

| dato | dónde |
|---|---|
| identidad canónica | `identity_v1.entity` (`entity_key` ULID), `identity_v1.identifier` |
| CIK | `identifier` con `id_type='CIK'`, `id_namespace='SEC'` |
| CUIT | `identifier` con `id_type='CUIT'`, `id_namespace='AFIP'` |
| hechos contables | `parsed.facts` / `derived.fact`, con `entity_id` namespaced (`CIK:0000904851`) |

### Instrumento

Tabla **`market_instruments`**:

```
instrument_id, entity_id, ticker_canonico, instrument_type, exchange,
country, currency, security_type, ratio_adr, source, active,
first_trade_date, venue_ticker, venue_ticker_source
```

Distribución real observada:

| `security_type` | `instrument_type` | n | con `ratio_adr` | moneda |
|---|---|---:|---:|---|
| `ordinaria` | `US` | 499 | 0 | USD |
| `ordinaria` | `LOCAL` | 73 | 0 | ARS |
| **`adr`** | **`ADR`** | **12** | **12** | USD |

Los 12 ADR, con su ratio real:

| `ticker_canonico` | `venue_ticker` | `exchange` | `ratio_adr` |
|---|---|---|---:|
| CRES | CRESY | NYSE | 10 |
| LOMA | LOMA | NYSE | 5 |
| VIST | VIST | NYSE | 1 |
| TGSU2 | TGS | NYSE | 5 |
| PAMP | PAM | NYSE | 25 |
| IRSA | IRS | NYSE | 10 |

Consultalos:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT ticker_canonico, venue_ticker, exchange, currency, ratio_adr \
     FROM market_instruments WHERE security_type='adr' ORDER BY ticker_canonico"
```

**`ticker_canonico` ≠ `venue_ticker`.** El primero es el ticker local (BYMA);
el segundo, el símbolo en el venue extranjero. Para pedir precio a un proveedor
se usa `venue_ticker`, no `ticker_canonico`. Confundirlos trae el precio de
otra empresa — el modo de falla que ya se documentó con las colisiones de
tickers BYMA/EEUU.

### Datos de mercado

| tabla | filas observadas | qué contiene |
|---|---:|---|
| `market_price_daily` | 4.799.938 | serie diaria por instrumento |
| `market_corporate_actions` | 51.917 | splits y dividendos |
| `market_symbol_mappings` | 584 | ticker por proveedor |
| `market_data_quality` | 8.322 | chequeos de calidad |
| `market_fetch_log` | 601 | corridas de descarga |
| `market_snapshots`, `market_raw_files`, `market_raw_runs`, `market_data_changes` | — | trazabilidad de las corridas |

---

## 3 · El enlace emisor ↔ instrumento — leer antes de calcular nada

**`market_instruments.entity_id` es un entero legacy** (`58`, `59`, `60`…),
**no** el `entity_id` namespaced que usa el engine (`CIK:0000904851`,
`CUIT:30657863676`).

Son **dos espacios de identificadores distintos**. No se pueden unir con un
`JOIN` directo:

```sql
-- ESTO NO FUNCIONA
SELECT * FROM derived.fact d
  JOIN market_instruments m ON m.entity_id = d.entity_id   -- '58' vs 'CIK:0000904851'
```

**`SOFTWARE GAP SG-10`.** Sin ese enlace resuelto, ningún ratio que combine
contabilidad y mercado (P/E, P/B, EV/Sales) puede construirse de forma
trazable para un emisor arbitrario. Es la causa estructural de que
`derived.ratio` tenga sólo 36 filas.

Verificá el estado del enlace en tu instalación:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT count(*) instrumentos, \
          count(*) FILTER (WHERE entity_id ~ '^(CIK|CUIT|LEI):') namespaced \
     FROM market_instruments"
```

---

## 4 · La aritmética del ADR

Cuando el enlace exista, la regla es ésta y hay que dejarla explícita en la
provenance de cada celda:

```
precio_ADR  =  precio_ordinaria_local  ×  ratio_adr  ÷  FX(local→USD)
EPS_ADR     =  EPS_ordinaria           ×  ratio_adr
```

De donde:

```
P/E(ADR)  =  precio_ADR / EPS_ADR  =  P/E(ordinaria)   ← el ratio se cancela
P/B(ADR)  =  igual: se cancela
```

**Los múltiplos por acción son invariantes al ratio DR/ORD**, siempre que
numerador y denominador correspondan **al mismo instrumento**. El error
aparece cuando se mezcla: precio del ADR con EPS de la ordinaria da un P/E
inflado exactamente por `ratio_adr` (25× en PAMP, 10× en CRES e IRSA).

**Market cap y EV NO se cancelan.** Ahí hay que usar el total de acciones
ordinarias del emisor y su precio local, o convertir todo consistentemente. No
se calcula desde el ADR sin el total de ADS emitidos, que el sistema no tiene.

---

## 5 · Formularios SEC de un emisor extranjero

| formulario | qué es | quién lo presenta |
|---|---|---|
| **20-F** | informe anual de emisor privado extranjero | el **emisor** |
| **6-K** | información periódica/eventual | el **emisor** |
| **F-6** | registración del programa de ADR | el **depositario** |

Los que llevan datos contables son **20-F** y **6-K**. El **F-6 no tiene
estados financieros**: describe el programa de ADR. Parsearlo buscando hechos
no devuelve nada, y eso es correcto, no una falla.

Los formularios que S02 descarga se controlan con `--forms`.

**`RUNBOOK GAP RG-03`.** El sistema no registra el **depositario** (BNY Mellon,
Citi, JPMorgan, Deutsche Bank) en ninguna tabla. Si se necesita para operar, es
un campo nuevo en `market_instruments`.

---

## 6 · Checklist antes de publicar un ratio de un emisor con ADR

1. ¿De qué **instrumento** salió el precio? (`market_instruments.instrument_id`)
2. ¿En qué **moneda** está? (`currency`)
3. ¿El denominador contable es del **mismo emisor**? (`entity_id` del engine)
4. ¿Se aplicó `ratio_adr` **una sola vez**, o cero veces si se cancela?
5. ¿La provenance nombra los dos objetos por separado?

Si no podés responder las cinco, el ratio va a **`NOT_CALCULABLE`**. Ver
`05_RATIO_REFERENCE.md`.
