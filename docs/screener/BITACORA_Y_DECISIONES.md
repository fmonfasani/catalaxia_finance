# Bitácora y decisiones — recap para agentes

> **Para qué sirve este archivo:** que un agente (o dev) que lea el repo entienda
> **por qué** existe cada cosa, no solo qué hace. Cuenta el recorrido de la
> construcción del screener y las decisiones de fondo. Leélo **después** de
> `COMIENZA_AQUI.md` y `../../scripts/tickets/README.md`.
>
> **Fecha del grueso del trabajo:** 24–26 de junio de 2026.

---

## 1. Qué se construyó (en una frase)

Un **screener financiero** que baja estados financieros oficiales de **SEC
EDGAR**, calcula ~35 ratios por empresa con metodología validada, los deja en
una **base de datos** (`data/screener.db`) consultable con SQL, unificando
empresas **US-GAAP e IFRS** y marcando dónde no confiar. Hoy: **553 empresas**
(S&P 500 + ADRs ARG/BRA/LatAm), sobre un catálogo de 8.021.

---

## 2. El recorrido (por qué se hizo cada cosa, en orden)

### Punto de partida: validar que EDGAR sirve
Existía un pipeline (`scripts/tickets/01`–`05`) que comparaba ratios de **SEC
EDGAR** contra una planilla cargada a mano desde **Investing.com** (99 tickers,
`Tickets.xlsx`). La pregunta de fondo: *¿se puede reemplazar Investing (frágil,
scraping fallido) por EDGAR (oficial, gratis)?*

### Diagnóstico: sí, pero había 10 bugs
Se hizo ingeniería inversa de cada divergencia >10% (ver
`DIAGNOSTICO_INVESTING_vs_EDGAR.md`). Hallazgo: **EDGAR-GAAP reproduce Investing**
(error mediano ~1% en PER/EPS/margen). Las divergencias grandes eran **bugs
nuestros o diferencias de método conocidas**, no de Investing. Se arreglaron 10:
el más grave fue **deduplicar la serie anual por `end` y no por `fy`** (el `fy`
de XBRL es el año del *filing*, y un 10-K trae varios años con el mismo `fy`).
Resultado: divergencias >10% de **107 → 39**.

### De 99 a 8.021: dimensionar el universo
Se midió por muestreo cuántas empresas hay en EDGAR y su composición:
**~8.021 empresas con ticker**, ~82% US-GAAP, ~4% IFRS, el resto fondos/ETF.
El **S&P 500 está 100% en EDGAR** → es el universo ideal (large caps, ~19 años de
historia, máxima confiabilidad).

### El fix IFRS: desbloquear los ADRs latinoamericanos
Los ADRs argentinos y brasileros reportan casi todos en **IFRS** (`ifrs-full`),
y el pipeline solo conocía nombres us-gaap → salían vacíos. Se construyó un
**mapeo canónico** (NetIncome ← `NetIncomeLoss` **o** `ProfitLoss`, etc.) con los
tags IFRS descubiertos empíricamente sobre ADRs reales. Sin esto, casi toda la
plaza argentina quedaba afuera. Ver `ESPEC_TAGS_RATIOS.md` §7.

### La base de datos: 5 capas
Se construyó en bloques (ver `../../scripts/tickets/README.md`):
1. **catálogo** (`construir_catalogo.py`) — las 8.021 con sector/país/tamaño.
2. **facts** (`construir_base.py`) — todos los tags de companyfacts, GAAP+IFRS
   unificados, series temporales.
3. **ratios** (`calcular_ratios_base.py`) — ~28 ratios fundamentales.
4. **precios + valuación** (`precios_y_valuacion.py`) — PER, P/B, EV/EBITDA con FX.
5. **flags de calidad** (`flags_calidad.py`) — el cinturón de seguridad.

---

## 3. Decisiones de fondo (el "por qué" que un agente debe respetar)

| Decisión | Por qué |
|----------|---------|
| **EDGAR, no Investing** | Investing es scraping frágil; EDGAR es oficial, gratis y validamos que coincide (~1%). |
| **Nunca estimar** | si falta un componente, el ratio es **NULL**. Un NULL honesto > un número inventado. |
| **Dedup por `end`, no por `fy`** | el `fy` de XBRL es del filing, no del período → colapsaba años. **Bug de mayor impacto oculto.** |
| **TTM rodante (estrategia B generalizada al Q1)** | el "último año fiscal" no es un TTM; con un trimestre no recurrente diverge (caso MRK). |
| **ROE con equity promedio** | como Investing; el equity puntual da ruido en empresas con recompras. |
| **EBITDA con D&A comprensivo + amort. de intangibles** | el tag estrecho `Depreciation` subestima el EBITDA de empresas adquisitivas. |
| **eps_ttm ≠ eps_annual** | Investing muestra EPS **anual** pero su PER usa **TTM**; son dos números distintos. |
| **Valuación con MARKET CAP (USD), no precio×acciones** | evita el lío del "ratio del ADR" + acciones ordinarias. yfinance da el market cap en USD para US y ADRs por igual. |
| **FX para IFRS en moneda local** | ratios puros (margen, ROE) no la necesitan; los de valuación sí. **ARS se marca con flag** por la inflación. |
| **Flags, no borrar** | el dato outlier se conserva pero se marca (`ni_fy`, `roe_ns`, `fx`, `mktcap_rev`). Para screening confiable: `WHERE flags IS NULL`. |
| **SQLite ahora, Postgres después** | cero setup; migrable con `pgloader`. Esquema con tipos limpios. |
| **Raw cache = fuente de verdad** | `data/raw/*.json` se baja una vez; la base se reconstruye sin red. El raw es lo caro (rate limit SEC). |
| **6 años primero** | base chica y rápida; alcanza para ratios + CAGR 5 años. Fase 2: historia completa re-parseando el raw. |
| **Por bloques, sin paralelo** | SEC limita a 10 req/s **compartido** → no correr dos descargas a la vez. Prioridad: S&P500 → ADR ARG → ADR BRA → LatAm → resto US. |
| **`data/` fuera de git** | pesa GBs y es regenerable; GitHub rechaza >100 MB. Es dato, no documento. |

---

## 4. Estado actual y qué falta

**Hecho:** 553 empresas con ratios + valuación + flags (S&P 500 + ADRs
ARG/BRA/LatAm), GAAP+IFRS unificados, validado contra Investing (PER mediana
1,3%, ROE 0,4%).

**Pendiente:**
1. **Validar la valuación del universo nuevo** contra Investing (medir confianza).
2. **Cola larga US** (~7.458) vía el `companyfacts.zip` masivo de SEC (un
   download, sin rate limit).
3. **Fase 2: historia completa** (re-parsear el raw sin el filtro de 6 años).
4. **Expandir conceptos** (`InterestExpense`, `IncomeTaxExpenseBenefit`) → cobertura
   de intereses + ROIC.
5. **Capa de export/dashboard** — replicar `Seguimiento_original.xlsx` desde la base.

---

## 5. Mapa del repo (dónde mirar qué)

```
scripts/tickets/
├── 01–05_*.py           pipeline de VALIDACIÓN (origen, vs Investing)
├── 06,07_*.py           solapas de cálculo/estadísticas (trabajo previo)
├── construir_catalogo.py  Bloque 0+1: catálogo + metadata
├── construir_base.py      Bloque 2: facts (GAAP+IFRS) ← el fix IFRS vive acá
├── calcular_ratios_base.py  ratios fundamentales
├── precios_y_valuacion.py   PER, P/B, EV/EBITDA + FX
├── flags_calidad.py         flags de calidad
└── README.md            ← guía operativa (LEER PRIMERO si tocás código)

docs/screener/
├── COMIENZA_AQUI.md     puerta de entrada
├── GUIA_SEC_EDGAR_PARA_DEVS.md  de cero: dominio + API + §13 el sistema
├── ESPEC_TAGS_RATIOS.md  tags + ratios; §7 = mapeo GAAP↔IFRS implementado
├── DIAGNOSTICO_INVESTING_vs_EDGAR.md  la validación + los 10 fixes
├── BITACORA_Y_DECISIONES.md  ← este archivo
└── FUENTES_DATOS_ACCIONES_ARGENTINA_BYMA.md  (con la corrección: ADRs ARG en EDGAR)

docs/calculos-financieros/  investigación previa (fórmulas + código de referencia)

data/                     gitignoreado: raw cache + screener.db (regenerable)
```

---

## 6. Trampas que un agente debe conocer

- **Dos pipelines coexisten:** `01`–`05` (validación contra Investing, sobre
  `Tickets.xlsx`) y los scripts de base de datos (el screener a escala). No
  confundirlos.
- **`data/` no está en git** — si no existe, hay que reconstruirla corriendo los
  bloques (ver `scripts/tickets/README.md` §2). El raw cache evita re-bajar de SEC.
- **Rate limit de SEC (10 req/s) es compartido** — nunca dos descargas SEC en
  paralelo, o te bloquean.
- **IFRS reporta en moneda local** (ARS/BRL) — cuidado con cualquier ratio que
  mezcle precio (USD) con dato per-share (local). Usar market cap + FX.
- **Los flags importan** — no rankear sin filtrar `flags IS NULL` para análisis
  serio; los outliers (ROE 398%, etc.) son reales pero no interpretables.
- **Git tuvo una desincronización** (jun 2026) que ya se resolvió: trabajo de la
  web (scripts 06/07) + trabajo de la sesión (base de datos) se mergearon en el
  commit `8a86ec2`. Todo está en `main`.
