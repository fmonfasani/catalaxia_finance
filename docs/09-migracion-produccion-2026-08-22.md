# Migración a producción — 2026-08-22

Qué se aplicó, qué se midió y qué quedó afuera. Todo lo de acá se verificó
contra el servidor; lo que no se midió está dicho como no medido.

---

## Punto de partida

Producción llevaba **seis semanas sin escrituras** (última: 2026-07-09) y
ninguna migración aplicada:

```
columnas en screener        45      (003 la lleva a 56)
columnas tipo_balance        0      (002 no había corrido)
tabla cnv_doc_meta           0      (01_schema tampoco)
PK cnv_estados_norm          (cuit, concepto, period_end, fecha_reexpresion)
```

**La PK vieja era el problema central.** Sin `tipo_balance`, hace colisionar el
balance INDIVIDUAL con el CONSOLIDADO. Eso explicaba el número que no cerraba:
producción tenía 84.316 filas de `cnv_estados_norm` y local 106.421. No era
desactualización — la clave no admitía las dos.

Cuatro de once endpoints devolvían HTTP 500.

---

## Lo aplicado, en orden

El orden importa: sin la 002, subir las filas que faltaban no sirve porque la
clave las rechaza en silencio.

### 1 · Migración 002 — ampliar la PK

```
antes:  PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion)
ahora:  PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
```

En `cnv_estados_norm` y `cnv_estados_v2`. Aditiva: ampliar una clave solo puede
admitir más filas. Filas intactas, API en 200.

### 2 · Los datos

| tabla | antes | después |
|---|---:|---:|
| `cnv_estados_norm` | 84.316 | **106.421** |
| `cnv_estados_v2` | 81.695 | **102.323** |
| `ratios_cnv` | 0 | **72** |

Las 20.628 de `cnv_estados_v2` son las que la clave vieja rechazaba.

Verificado contra local: 72 empresas, misma suma de valores (8,396×10¹⁹), mismo
rango 2011-03-31 a 2026-04-30.

### 3 · Migración 003 + fijar los campos de la API

Las 11 columnas IAMC → MEP. **Se fijaron los campos en la API ANTES** de aplicar
la migración, así nunca hubo una ventana devolviendo 56 campos.

```
columnas en la tabla        56
campos en la respuesta      45
```

Es la salida (a) de las tres que documenta `003_screener_iamc_mep.sql`.

### 4 · Migración 004 — las tablas que la API consultaba y no existían

`silver_norm`, `validaciones`, `certificacion_nueva`, `dolarito_cotizaciones`
y la vista `mep_actual`.

---

## Resultado

**18 de 20 tablas idénticas a local. 10 de 11 endpoints en 200** (antes, 7).

```
/v1/ratios          500 -> 200
/v1/validaciones    500 -> 200
/v1/certificacion   500 -> 200
/v1/mep             500 -> 200      devuelve MEP 1.526,26
```

Las 11 columnas nuevas, pobladas para BYMA:

```
ALUA   precio 968,50   máx 1.170   mín 600   dif −17,22% / +61,42%   USD 0,63
MIRG   precio 17.200   máx 28.250  mín 14.600  dif −39,12% / +17,81%  USD 11,24
```

Verificado a mano: 968,5 ÷ 1.529,66 = 0,633.

---

## Los tres errores que costaron tiempo, y qué dejaron

### El upsert que no coincidió con ninguna fila

`84.316 + 106.421 = 190.737`. Producción quedó con las dos versiones.

Causa: las filas viejas tenían `fecha_reexpresion = ''` y las nuevas traían la
fecha. Distinta clave, cero conflictos, duplicado completo — **y el COMMIT no
protestó**.

Antes de borrar se verificó que el discriminador separara limpio: de las 106.421
filas nuevas, **cero** tienen ese campo vacío. Por eso el sincronizador ahora
compara el conteo final contra el local en cada tabla.

### Las 35 huérfanas

Un solo documento: BOLT_2 al 2018-10-31, con Activo 3,17 mientras Caja 263,01 y
Resultado Bruto 950,84. La identidad no cierra (Activo 3,17 contra Pasivo+PN
625,49). No existe en local — BOLT_2 tiene otros 30 períodos. Balance corrupto
que local ya había descartado; borrarlo alineó producción.

### `/v1/ratios` fallaba por dos razones, no una

Crear `silver_norm` no alcanzó: seguía dando 500 con `KeyError: 0`.

```python
cursor = conn.cursor(cursor_factory=RealDictCursor)
...
total = cursor.fetchone()[0]        # dict, no tupla
```

`RealDictCursor` devuelve diccionario; la clave del `COUNT(*)` es `count`.
Habría fallado igual con la tabla presente.

---

## Por qué NO se usó `migrate_sqlite_to_pg.py`

Hace TRUNCATE + INSERT + swap sobre `screener`, y ya está medido que ese
reemplazo **vacía 12 columnas que la API sirve** — `ccl`, `precio_ars`,
`precio_usd`, `precio_fuente`, `cusip`, `dr_level`, `cedear_ratio`,
`div_adr_12m`, `div_yield_adr` y tres más.

Y lo peligroso: **la guarda de filas no lo detecta. Entran 572 y salen 572.**

En su lugar: `scripts/deploy/sincronizar_a_produccion.py`, que hace DELETE +
INSERT dentro de una transacción y verifica el conteo final contra el local.

---

## Lo que quedó afuera, y por qué

### `facts` — 1.389 filas

Producción tiene 4.605.617, que es exactamente `facts_pre_redescarga` local. Su
último `filed` es 2026-07-01; local llega a 2026-08-11. **Producción tiene la
versión anterior a la re-descarga.** Son 4,6 millones de filas: no se subió con
el método de hoy sin decisión previa.

### Las 734 correcciones de escala

`valor_corregido ≠ valor` en 4 empresas: `_ADR_0580`, PATA_2, **CVH** y
**GCLA** — las mismas que daban ratios absurdos (CVH: ROE 26.736).

**Se subió `valor` sin corregir, a propósito.** Producción no tiene dónde
guardar la corrección aparte, y transformar datos en silencio durante una
migración es como se pierde el rastro de qué es qué. Necesitan su propia
migración, igual que se hizo con `facts_xbrl`.

Nota metodológica: **las identidades contables no pueden validar estas
correcciones.** Una corrección de escala multiplica todos los conceptos del
período por el mismo factor, así que Activo = Pasivo + PN se cumple igual en
unidades que en miles. Es invariante. Verificado: 94 ok / 0 mal con y sin
corregir.

### Las 11 columnas solo cubren BYMA

46-56 de 56. Las 516 de sp500 y adr están vacías porque `s9_guards_yfinance.py`
es específico de BYMA (colisión de tickers, conversión MEP). Extenderlas es
trabajo nuevo, no migración.

### La API todavía no sirve las 11 columnas

Deliberado. Se fijaron los campos en 45 para que la migración no cambiara el
contrato público. Publicarlas es agregar los nombres a esa lista — decisión del
dueño de la API.

### `screener_hist` no existe en ningún lado

`/v2/screener/hist/{ticker}` es el único endpoint que sigue en 500. Ningún
script genera esa tabla. Es una función que falta, no un dato desactualizado.

### `ultimo_periodo` de sp500 guarda la fecha de extracción

Las 499 dicen `2026-07-09`, que coincide con `precios.fecha` y
`empresas.fecha_facts`. No es un cierre de balance. BYMA y ADR sí traen cierres
reales. **No se corrigió.**

---

## Respaldos

```
/root/backups_catalaxia/pre_migracion_20260822-140444.sql.gz   2,0 MB
/root/backups_catalaxia/main.py.20260822-*.bak
```

Cada migración trae su marcha atrás escrita en el encabezado.

---

## Estado de las capas al cierre

```
0 IDENTIDAD   100,0%
1 INGESTA     100,0%
2 TIEMPO       98,2%
3 UNIDAD       97,9%   1.721 sin respuesta
4 MONEDA       98,8%   845 sin MEP para su fecha
5 PERIMETRO    96,1%
6 COHERENCIA   91,9%   121 documentos se contradicen
7 DERIVADO     82,1%
8 PUBLICADO    86,9%   497 de 572 con PER
```

---

# Segunda tanda — mismo día

## `facts`: no eran 4,6 millones de filas, eran 3 empresas

Comparando `max(filed)` por CIK: **606 iguales, 3 con local más nuevo, 0 con
producción más nueva.**

```
TAP   (Molson Coors)    2026-02-18 -> 2026-08-06
CAH   (Cardinal Health) 2026-02-05 -> 2026-08-11
FISV  (Fiserv)          2026-05-06 -> 2026-08-07
```

Se sincronizaron esos 3 CIK, 25.407 filas. No la tabla entera.

## La re-descarga había perdido historia

Después de sincronizar, producción quedó con **1.483 filas más** que local.
Comparar por `max(filed)` no dice nada de las cantidades.

Local `facts` tenía 14.386 filas de Citigroup; `facts_pre_redescarga`, 14.994 —
**con la misma fecha de presentación**. Perdidas 608, ganadas 0.

Medido sobre los 10 CIK afectados:

```
filas perdidas               1.483
con period_end > 2020-08-23      0
period_end más alto perdido      2020-08-21
```

La re-descarga corrió con ventana `historia=6a (desde 2020-08-23)` y borró todo
lo anterior. El corte cae **dos días** después del dato más nuevo que se perdió.

Afectadas: C (608), VALE (469), PBR (395), y 7 más con 1-2 filas.

Pega justo donde duele: CAGR de 5 años y ROE de 5 años necesitan esa historia.

**Producción tenía la versión completa; local la había perdido.** Se reparó
local desde `facts_pre_redescarga` — 1.483 filas restauradas. Las dos bases
quedaron en 4.605.967.

> Nota: `n_live_tup` de `pg_stat_user_tables` es una **estimación**. Decía
> 4.603.445 cuando el `count(*)` daba 4.605.967. Para comparar conteos, `count`.

## Seis empresas publicaban el precio de otra empresa

`screener` en producción tenía el guard de moneda de s9 sin aplicar:

| ticker | producción | correcto | qué era el precio malo |
|---|---|---|---|
| AGRO | USD 10 | ARS 40,20 | Adecoagro |
| CELU | USD 0,75 | ARS 266,50 | Celularity |
| COUR | USD 5,67 | ARS 3.400 | Coursera |
| HAVA | USD 10,10 | ARS 5.260 | — |
| INTR | USD 5,71 | ARS 295 | Inter&Co (ADR brasileño) |
| BOLT | null | ARS 46,40 | — |

HAVA publicaba **PER 92,05** calculado sobre el precio equivocado. El correcto
es 32,24.

Se actualizaron 44 columnas de `screener` por `cuit`, preservando las 12 que
solo viven en producción — las mismas 12 que la migración 003 advierte que
`migrate_sqlite_to_pg.py` vacía. Verificado después: `precio_ars` 568 filas,
`cusip` 13 filas, intactas.

## Error del proceso: se borraron 50 precios legítimos

Al limpiar `precios` se usó el filtro `cik LIKE 'BYMA-%'` creyendo que esos CIK
sintéticos eran todos de la colisión de tickers. **No lo eran**: 50 de esas 56
filas eran precios legítimos en pesos (`BYMA-VALO` a 653,50 ARS, entre otros).
Producción cayó de 679 a 623.

Se restauró `precios` completo desde local (672 filas, 48 tickers con dos
filas). Verificado: 672 = 672, 48 = 48.

La lección es la de siempre en este proyecto: **el prefijo de un identificador
no es una clasificación**. Lo que distinguía las filas malas era la moneda (USD
en una empresa que cotiza en pesos), no el formato del CIK.

## Estado al cierre

```
tabla                  local    producción
cnv_estados_norm     106.421     106.421   =
cnv_estados_v2       102.323     102.323   =
facts              4.605.967   4.605.967   =
precios                  672         672   =
ratios                   609         609   =
ratios_cnv                72          72   =
screener                 572         572   =
silver_norm            1.147       1.147   =
```

API: 10 de 11 endpoints en 200, 45 campos por fila.
