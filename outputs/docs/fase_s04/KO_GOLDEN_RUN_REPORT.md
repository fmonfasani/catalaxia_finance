# KO GOLDEN RUN — The Coca-Cola Company, CIK `0000021344`

**Veredicto: `PASS_WITH_WARNINGS`.**

El pipeline SEC corrió de punta a punta para un emisor US-GAAP **sin modificar
una sola línea del core**. Produjo 45.113 hechos canónicos que coinciden
**exactamente** con la referencia previa, con provenance verificada hasta el
SHA-256 del archivo en disco e idempotencia demostrada en S03 y S04.

Las advertencias son seis y ninguna se corrigió: se diagnosticaron y se reportan
acá, como pide el encargo.

| | |
|---|---|
| emisor | The Coca-Cola Company · CIK `0000021344` · `COCA COLA CO` |
| formulario | **10-K** (contra 20-F de YPF) |
| taxonomía | **us-gaap** pura + `srt` + `dei` |
| base | `kogolden` @ 5433 — creada para esto, aislada |
| commit | `57edebb1a0621a4dd4feb228639ae48e8d876966` |
| protecciones | `catalaxia` digest `63629c0f…`/133.902 intacto · `screener.db` 1.504.714.752 B · producción sólo `public` |

---

## 1 · Estado verificado ANTES de tocar nada

| qué | estado previo |
|---|---|
| KO en `catalaxia` | **ya presente**: 45.113 hechos, 17 filings, 90.398 `parsed.facts` |
| RAW de KO en disco | **presente**: 31 directorios de filing, 540 archivos, 276 MB, descargado 2026-09-02 |
| `download_log` de KO en `catalaxia` | 541 filas |
| golden run documentado | **ninguno** |

KO ya había pasado por el pipeline alguna vez; lo que nunca existió fue la
certificación. Por eso esta corrida se hizo **en una base nueva y vacía**, para
que los números salgan del pipeline y no de un arrastre.

**Decisión de aislamiento:** no se corrió contra `catalaxia` porque ahí vive el
digest SEC protegido (133.902 hechos / `63629c0f…`) que todos los sprints
anteriores verifican. Escribir ahí lo habría roto.

---

## 2 · Comandos ejecutados, en orden

```bash
# 0 · base aislada
docker exec catalaxia-engine-dev psql -U catalaxia -d postgres \
  -c "DROP DATABASE IF EXISTS kogolden;" -c "CREATE DATABASE kogolden OWNER catalaxia;"

ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python -c "
from engine.config import load_settings; from engine.db import *
apply_migrations(get_admin_engine(load_settings()))"

# 1 · pipeline SEC
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s01_identity.py
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py \
    --cik 0000021344 --forms 10-K,10-K/A
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py \
    --cik 0000021344
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run
                                                                    # ← BLOCK

# 2 · etapa que el pipeline documentado NO menciona
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/backfill_cik.py --inventario
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/backfill_cik.py --aplicar

ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py

# 3 · market (el ratio engine lo exige aunque no haya precios)
DB_NAME=kogolden DB_PORT=5433 python scripts/market/m19_apply_schema.py

# 4 · ratios
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py \
    --cik 0000021344

# 5 · idempotencia
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py --cik 0000021344
ENGINE_DB_NAME=kogolden ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py
```

**La única diferencia de parámetro respecto de YPF es `--forms 10-K,10-K/A`.**
El default es `20-F,20-F/A`, y el propio `--help` del script ya lo dice:
*«20-F para emisores extranjeros, 10-K para domesticos»*.

---

## 3 · Gates

| etapa | gate | exit | señal |
|---|---|---|---|
| migraciones | — | 0 | 32 aplicadas |
| S00 | **PASS** | 0 | `rows_expected = 2`, `rows_rejected = 0` |
| S01 | **PASS** | 0 | `checks_expected = 4`, `checks_pass = 4` |
| S02 | **PASS** | 0 | `rows_expected = 541`, `rows_ok = 536`, `rows_failed = 5` |
| S03 | **PASS** | 0 | `hash_out = 4a06a553…`, `filings_rejected = 0` → `READY_FOR_S04` |
| S04 dry (1º) | **BLOCK** | — | `C-S04-004 FAIL` |
| backfill | — | 0 | 512 entidades, 512 CIK autoritativos |
| S04 dry (2º) | **PASS** | 0 | `C-S04-005..009` en `SKIP` |
| S04 | **PASS** | 0 | 9/9 checks, `hash_out = b602b2d4…` |
| ratios | — | 0 | 4 ratios, 1 `CALCULADO` |

---

## 4 · Conteos

| etapa | KO | YPF (referencia) |
|---|---:|---:|
| `fetch_raw.download_log` | **541** | 927 |
| filings con XBRL | **17** | 9 |
| filings pre-XBRL | **14** | — |
| `parsed.facts` | **90.398** | 67.084 |
| `parsed.concepts` | **14.934** | — |
| `parsed.contexts` | **24.008** | — |
| `parsed.units` | **181** | — |
| `parsed.link_relations` | **201.765** | — |
| `derived.fact` vigentes | **45.113** | 47.930 |
| períodos | **17** (2009–2025) | 9 (2017–2025) |
| `qname` distintos | **12.061** | 8.221 |
| hechos dimensionales | **29.976** | 37.078 |
| unidades distintas | **13** | 62 |

**Los 45.113 coinciden exacto con los que `catalaxia` ya tenía.** Reproducción
independiente, en una base creada desde cero.

### Desempate

| criterio | KO | qué significa |
|---|---:|---|
| `IDENTICO` | 26.172 | el hecho aparece repetido con el mismo valor |
| `POR_PRECISION` | 12.746 | se resolvió por `decimals`/`precision` |
| `POR_FACT_ID` | **3.113** | **último recurso**: mismo hecho, valores distintos, sin precisión que discrimine |
| `UNICO` | 3.082 | aparece una sola vez |

Los 3.113 `POR_FACT_ID` son exactamente los **3.113 conflictos
`VALOR_SIN_DESEMPATE`** que S04 registró. No se descartan ni se ocultan: se
resuelven de forma determinista y se dejan escritos en
`derived.normalize_conflict`. YPF tiene 12.742 del mismo tipo, así que KO está
**mejor** en términos relativos.

---

## 5 · Taxonomía — la prueba de generalización

**Los 20 conceptos del registry resuelven para KO. 20 de 20.**

| concepto | tag us-gaap elegido | tag IFRS que usa YPF |
|---|---|---|
| `activo_total` | `Assets` | `Assets` |
| `activo_corriente` | `AssetsCurrent` | `CurrentAssets` |
| `pasivo_total` | `Liabilities` | `Liabilities` |
| `pasivo_corriente` | `LiabilitiesCurrent` | `CurrentLiabilities` |
| `patrimonio` | `StockholdersEquity` | `Equity` |
| `efectivo` | `CashAndCashEquivalentsAtCarryingValue` | `CashAndCashEquivalents` |
| `existencias` | `InventoryNet` | `Inventories` |
| `resultado_neto` | `ProfitLoss` | `ProfitLoss` |
| `ingresos` | `Revenues` | `Revenue` |
| `eps_basico` | `EarningsPerShareBasic` | `BasicEarningsLossPerShare` |

Esto es exactamente lo que el registry existe para hacer: `ratio_defs.CONCEPTOS`
declara, por concepto económico, la cadena de tags candidatos, y **el orden de la
lista es la regla de fallback**. Un emisor US-GAAP encuentra su tag y uno IFRS el
suyo, **sin una sola rama condicional por fuente**.

Namespaces observados en KO: `http://fasb.org/us-gaap/{2018-01-31…2025}`,
`http://fasb.org/srt/…`, `http://xbrl.sec.gov/dei/…` y el propio de la empresa,
`http://www.coca-colacompany.com/2024…`.

---

## 6 · Ratios

```
CIK         entidad         ratio     win  periodo     estado          valor  moneda
0000021344  COCA COLA CO    eps       FY   2025-12-31  CALCULADO        3.05  USD
0000021344  COCA COLA CO    pb        PIT  2025-12-31  NOT_CALCULABLE      -  -
0000021344  COCA COLA CO    pe        FY   2025-12-31  NOT_CALCULABLE      -  USD
0000021344  COCA COLA CO    ev_sales  FY   2025-12-31  NOT_CALCULABLE      -  -
```

`F-061 · punteros de provenance ajenos: 0`

| ratio | estado | motivo textual del engine |
|---|---|---|
| `eps` | **CALCULADO** = 3,05 USD | — |
| `pb` | `NOT_CALCULABLE` | «sin fact para el concepto `acciones_circulacion` en 2025-12-31» |
| `pe` | `NOT_CALCULABLE` | «la entidad no tiene instrumento ligado en `identity_v1.instrument`: atribuirle un precio sería un join por ticker» |
| `ev_sales` | `NOT_CALCULABLE` | «sin fact para el concepto `deuda_financiera` en 2025-12-31» |

Los tres `NOT_CALCULABLE` **tienen motivo explícito y ninguno se forzó**. El de
`pe` es el más importante: es la limitación conocida del enlace
instrumento→entidad de Market, no un problema de KO.

Verificación del EPS contra el hecho de origen: `EarningsPerShareBasic = 3.05`,
unidad `iso4217:USD/shares`, filing `0001628280-26-010047`. El diluido del mismo
filing es 3,04.

---

## 7 · Provenance — cadena completa

```
1. RATIO      eps = 3.05 USD  (FY 2025-12-31)
2. FACT       EarningsPerShareBasic = 3.05   iso4217:USD/shares
   qname      http://fasb.org/us-gaap/2025#EarningsPerShareBasic
   context    c-1
   fact_key   9aea8b2de8953c2cc996361f814b405d25f24e8b20cecd16a2773bd20d6b258e
3. PARSED     fact_id=93808   source_file=ko-20251231_htm.xml
   coherencia cik=True  accn=True  qname=True
4. DOWNLOAD   raw_path=CIK0000021344/filings/000162828026010047/ko-20251231_htm…
   sha256(db) 5428e5c422a5b88dd967793d3b04411d226272acdc3c040efe3d870bb5b56d31
5. RAW        ko-20251231_htm.xml
   sha256(disco) 5428e5c422a5b88dd967793d3b04411d226272acdc3c040efe3d870bb5b56d31
   COINCIDE: True
6. ORIGEN     https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/…
```

El hash de la base y el del archivo en disco coinciden. La guarda de pertenencia
de F-061 da **0 punteros ajenos**: todo `source_fact_id` de `derived.fact`
resuelve a una fila de `parsed.facts` del mismo emisor, filing y concepto.

---

## 8 · Idempotencia

| etapa | 1ª corrida | 2ª corrida | veredicto |
|---|---|---|---|
| **S03** | `hash_out = 4a06a553a2af1a39e89632d171a4faa280eb1be870825b1925cda0c175949e84` | **idéntico** | ✅ |
| **S04** | `hash_out = b602b2d483ca185b5eba52869fd41444f37e74e2d6d2e9149f2c2cf41ccd4766` | **idéntico** | ✅ |
| S04 · huella | `persistidos=45113 recomputados=45113 huella_igual=True` | idem | ✅ |
| **S00** | `PASS`, exit 0 | **`UniqueViolation`, exit 1** | ❌ ver W-1 |
| **S01** | `PASS`, exit 0 | **`UniqueViolation`, exit 1** | ❌ ver W-1 |

El `checkpoint_id` de S04 cambia entre corridas (`a406a51397fb492b-s04` →
`9c835199ee934b98-s04`) porque el `run_id` es nuevo, pero el contenido y su hash
son los mismos. Eso es idempotencia de resultado, que es la que importa.

---

## 9 · Errores encontrados

### E-1 · `S04` bloqueó: KO no existía en `identity_v1`

```
GATE BLOCK
   [FAIL] C-S04-004  CIK sin entidad en identity_v1: ['0000021344']
```

**Causa raíz:** `s01_identity.py` **está fijado a YPF**. No tiene `--cik` y sus
checks verifican literalmente:

```python
"detail": "entidad YPF CIK:0000904851 ausente"
if resolution["legal_name"] != "YPF SOCIEDAD ANONIMA":
```

S01 carga las 8.004 entidades del listado de SEC en `identity.entities` —KO
incluida— pero **deja `identity_v1.entity` vacío**, y `identity_v1` es lo que
S04 exige. `identity_v1_pilot.py` tampoco sirve: materializa una lista fija de
YPF, CEPU, GGAL y TGSU2.

**Cómo se resolvió, sin modificar código:** con
`scripts/engine/backfill_cik.py --aplicar`, que existe, está contratado en
`docs/architecture/IDENTITY_BACKFILL_CIK_CONTRACT.md` y pobló 512 entidades y
512 CIK autoritativos.

**El hallazgo real:** *`backfill_cik.py` es una etapa obligatoria del pipeline
SEC para cualquier emisor que no sea YPF, y no figura en ningún runbook.* El
pipeline documentado —S00→S04— está incompleto.

### E-2 · El ratio engine reventó sin el esquema de Market

```
psycopg2.errors.UndefinedTable: relation "market_price_daily" does not exist
```

`ratio_engine.py` consulta `market_price_daily` incondicionalmente, incluso para
ratios contables que no necesitan precio. Sobre una base sin Market instalado
**no degrada: aborta**. Se resolvió instalando el esquema con
`m19_apply_schema.py` (10 tablas, vacías).

**Segundo hallazgo dentro de éste:** `scripts/market/` usa **otras variables de
entorno** —`DB_HOST`, `DB_PORT`, `DB_NAME`— y no `ENGINE_DB_*`. Dos convenciones
distintas en el mismo repositorio, sin nada que lo advierta.

---

## 10 · Advertencias

### W-1 · S00 y S01 no son idempotentes

Las dos etapas insertan en `engine.checkpoints` **sin `ON CONFLICT`**, y hay un
índice único sobre `(stage_id, input_hash, code_version, contract_version)` donde
`input_hash` es el SHA-256 de `settings.describe()` — constante para una misma
base y modo. La segunda corrida siempre choca:

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique
constraint "ux_checkpoints_reuse"
DETAIL: Key (stage_id, input_hash, …)=(S01_identity, bf83a6d3…) already exists.
```

Exit `1`. **No es específico de KO**: afecta igual a YPF. La matriz de readiness
marca S00 como `READY`, y no lo es.

### W-2 · `is_custom` clasifica mal us-gaap, srt y dei

**Es el hallazgo más valioso de este piloto**, y sólo aparece con un emisor
US-GAAP.

En `derived.fact` de KO, **los 45.113 hechos tienen `is_custom = True`**. En YPF,
21.138 de 47.930 (44 %). La razón está en `scripts/engine/s03_parse_ypf.py:483`,
en el camino `INSTANCE_OBSERVED` (conceptos observados en la instancia, sin
esquema local):

```python
tax = qn.split("#")[0].rsplit("/", 1)[-1]          # último segmento del URI
...
not any(s in tax for s in STANDARD_HINTS)          # así se decide is_custom
```

Ese camino **duplica mal** la función `_taxonomy_of` de `engine/xbrlparse.py` en
vez de llamarla. Comprobado lado a lado:

| namespace | `_taxonomy_of` (correcta) | línea 483 | `is_custom` |
|---|---|---|---|
| `http://fasb.org/us-gaap/2024` | `us-gaap` | `2024` | **True** ✗ |
| `http://fasb.org/srt/2019-01-31` | `srt` | `2019-01-31` | **True** ✗ |
| `http://xbrl.sec.gov/dei/2025` | `dei` | `2025` | **True** ✗ |
| `http://xbrl.ifrs.org/taxonomy/2017-03-09/ifrs-full` | `ifrs-full` | `ifrs-full` | False ✓ |

**IFRS acierta por casualidad**: sus URIs terminan con el nombre de la taxonomía.
Los de FASB y SEC terminan con la **versión**. Tres de las cuatro taxonomías
estándar quedan marcadas como extensión propia de la empresa.

**No se corrigió**, por instrucción explícita. No afectó los ratios de esta
corrida porque el registry resuelve por `tag`, no por `is_custom`.

### W-3 · 5 descargas fallidas en S02

Todas HTTP `404` sobre `…-index-headers.html`, de filings de 2010 a 2014, y
todas con `critical = False`. El gate `C-S02-001` cuenta sólo las críticas, que
fueron 0, así que `PASS` es correcto. SEC dejó de servir ese artefacto para
accessions viejas.

### W-4 · 3.113 conflictos de normalización

`VALOR_SIN_DESEMPATE`: el mismo hecho aparece con valores distintos y sin
`precision` que discrimine. Se resuelven por `fact_id` de forma determinista y
quedan registrados. Es comportamiento de diseño, no una falla — y YPF tiene
12.742.

### W-5 · 3 de 4 ratios no calculables

Con motivo explícito cada uno (§6). El de `pe` es la limitación conocida del
enlace instrumento→entidad.

### W-6 · El backfill escribe artefactos en el repositorio

`backfill_cik.py` deja `outputs/docs/fase_identity/backfill_cik_inventory.json`
y `backfill_cik_apply.json`. Son salidas, no código, pero conviene saberlo.

---

## 11 · Diferencias respecto de YPF

| dimensión | YPF | KO | ¿cambió el core? |
|---|---|---|---|
| formulario | 20-F | **10-K** | no — `--forms` |
| taxonomía | IFRS + `srt`/`us-gaap` accesorios | **us-gaap puro** + `srt` + `dei` | **no** |
| filings XBRL | 9 | **17** | no |
| filings pre-XBRL | — | **14** (1994–2008) | no — S03 los clasifica `PRE_XBRL` |
| cobertura | 2017–2025 | **2009–2025** | no |
| unidades distintas | 62 | 13 | no |
| dimensionales | 37.078 (77 %) | 29.976 (66 %) | no |
| identidad | S01 la certifica | **S01 no la certifica**; hace falta `backfill_cik` | **no, pero falta una etapa** |
| `is_custom` | 44 % | **100 %** | no — W-2 |
| ratios calculados | — | 1 de 4 | no |

**Ninguna diferencia exigió tocar el core.** Se cambió un parámetro (`--forms`) y
se agregó una etapa que ya existía (`backfill_cik`).

---

## 12 · Validación y protecciones

| control | resultado |
|---|---|
| `catalaxia` digest SEC | `63629c0fc2ee76ad8038660c4815b443` / 133.902 — **intacto** |
| `screener.db` | 1.504.714.752 B · 2026-08-23 13:42:23 — **intacto** |
| producción 5432 | sólo esquema `public` — **intacta** |
| `ratio_engine.py` / `ratio_defs.py` | **sin modificar** |
| `s0*.py`, `engine/` | sin cambios de esta corrida (los 3 archivos con `M` son previos a la sesión) |
| guarda de pertenencia F-061 | 0 punteros ajenos |
| `C-S04-008` | `persistidos=45113 recomputados=45113 huella_igual=True` |
| RAW | inmutable; 4 archivos nuevos (submissions/companyfacts), 536 reusados como `SIN_CAMBIOS` |

---

## 13 · Conclusión

### `PASS_WITH_WARNINGS`

**Lo que quedó demostrado.** El pipeline SEC procesa un emisor US-GAAP de punta a
punta sin modificar el core. Los 20 conceptos del registry resuelven contra tags
us-gaap; el resultado —45.113 hechos, 17 filings, 12.061 qnames— reproduce
exactamente la referencia previa desde una base vacía; la provenance cierra hasta
el SHA-256 en disco; y S03 y S04 son idempotentes con hash idéntico.

**Lo que no está bien, y hay que decirlo.** El pipeline documentado está
incompleto: para cualquier emisor que no sea YPF hace falta `backfill_cik.py`,
que ningún runbook menciona, y sin él S04 bloquea. S01 no certifica la identidad
de nadie que no sea YPF. S00 y S01 no se pueden volver a correr sobre la misma
base. El ratio engine aborta si Market no está instalado, aunque el ratio no
necesite precio. Y `is_custom` marca como extensión propia a us-gaap, srt y dei
— un defecto que llevaba invisible todo el tiempo porque el único piloto era
IFRS.

**Ninguno de esos seis se corrigió.** El encargo pedía diagnosticar y reportar
antes de modificar, y eso es lo que hay acá.

**KO queda como segundo piloto real**, con comandos, conteos, gates, provenance e
idempotencia verificados y reproducibles.

---

### Backlog que sale de esta corrida

| # | prioridad | hallazgo |
|---|---|---|
| 1 | **P0** | `backfill_cik.py` es etapa obligatoria del pipeline SEC y no está documentada. Sin ella, S04 bloquea para todo emisor que no sea YPF |
| 2 | **P0** | `is_custom` clasifica mal us-gaap, srt y dei (`s03_parse_ypf.py:483` duplica mal `_taxonomy_of`) |
| 3 | **P1** | S00 y S01 no son idempotentes: `INSERT` sin `ON CONFLICT` contra `ux_checkpoints_reuse` |
| 4 | **P1** | `s01_identity.py` está fijado a YPF: no acepta `--cik` y sus checks nombran la entidad |
| 5 | **P2** | `ratio_engine.py` aborta sin el esquema Market en vez de degradar a `NOT_CALCULABLE` |
| 6 | **P2** | `scripts/market/` usa `DB_*` y el resto `ENGINE_DB_*`: dos convenciones sin advertencia |

*Ninguno implementado. Diagnóstico solamente.*
