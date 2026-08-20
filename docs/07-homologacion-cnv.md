# 07 — Homologación CNV: perímetro contable y vintage

> Rama `fix/homologacion-cnv` · Relevado y medido el 2026-08-20 sobre
> `data/screener.db` (821 MB) y una copia `screener.db.test`.
> Todas las cifras de este documento salen de ejecuciones reales, no de estimaciones.

Este documento cubre cuatro defectos encontrados en la cadena CNV, su causa raíz y
lo que se corrigió. Los cuatro tenían el mismo síntoma —ratios que no cuadran contra
referencias externas— y tres causas distintas.

---

## 7.1 El defecto de fondo: la PK de `cnv_estados_v2` no tenía el perímetro

**Es la causa raíz de la que cuelgan las demás.** La tabla se creaba así:

```sql
PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion)
```

Y `fecha_reexpresion` estaba **vacía en el 100 % de las filas**. Así que la clave
efectiva era `(cuit, concepto, period_end)` — sin distinguir individual de
consolidado. Combinado con `INSERT OR IGNORE`, el mecanismo era:

1. Una empresa presenta dos documentos para el mismo período: individual y
   consolidado. Ambos son ricos.
2. El extractor procesa uno primero y escribe sus conceptos.
3. Procesa el segundo e intenta escribir los suyos. **`INSERT OR IGNORE` descarta en
   silencio** todo lo que colisiona.
4. Solo sobreviven los conceptos que el primero no tenía.

### La prueba

Documentos de HAVA (Havanna Holding), analizados en crudo:

| Documento | Período | KB | Códigos | Con valor | Conceptos en la base |
|---|---|---|---|---|---|
| `72ffdd64` | 2022-06 (solo consolidado) | 141 | 79 | 68 | **47** |
| `04cfdb86` | 2024-12 (consolidado) | 147 | **84** | **72** | **16** |
| `4cd5732e` | 2024-12 (individual) | 147 | 86 | 51 | 34 |

El consolidado de 2024-12 era **el documento más rico de los tres** y fue el que menos
aportó. No se perdió nada al parsear: se perdió al escribir.

### Consecuencias

- **La extracción era no determinista.** El contenido dependía del orden de la
  whitelist. Correr el job con otro orden cambiaba los ratios publicados.
- **293 documentos de 2.145 (13,7 %) quedaban mutilados** — 225 consolidados y 68
  individuales. Los peores conservaban **un solo concepto de 51**.
- Explica el cero solapamiento entre perímetros: no es que se repartieran el trabajo,
  es que uno bloqueaba al otro.

### El arreglo

```sql
PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
```

Más una columna `tipo_balance` poblada desde el HTML (ver 7.2).

### Resultado medido (re-extracción offline, 2.457 documentos, 0 errores)

| | Antes | Después | Delta |
|---|---|---|---|
| Filas | 81.695 | **102.323** | **+20.628 (+25 %)** |
| Documentos con datos | 2.145 | 2.350 | +205 |
| Conceptos por documento (media) | 38,1 | **43,5** | +5,4 |

Los 205 documentos nuevos no aportaban **ni una fila** antes: quedaban totalmente
bloqueados.

Caso HAVA 2024-12-31, después del arreglo: CONSOLIDADO **50 conceptos** (antes 16),
INDIVIDUAL 34. Los dos perímetros conviven y elegir entre ellos pasa a ser una
decisión explícita.

---

## 7.2 La CNV declara el perímetro y no lo estábamos leyendo

Dentro del HTML de `publicview aif2` hay campos estructurados que se estaban
descartando:

```html
<propiedad id="TipoBalance" claveinformativa="TipoBalance">Consolidado</propiedad>
```

Cobertura verificada sobre los 2.145 documentos: **100 %, sin un solo vacío.**

| Campo | Cobertura | Valores |
|---|---|---|
| `TipoBalance` | 100 % | 1.081 INDIVIDUAL · 1.064 CONSOLIDADO |
| `NormasContablesAplicadas` | 100 % | NIIF 2.138 · NCP 7 |
| `Moneda` | 100 % | 7 (2.138) · 36 (6) · 113 (1) |
| `FechaCierre` | 100 % | ISO con timezone |

**Ojo con el dominio sucio:** la CNV escribe el mismo valor de dos formas —
`Individual` (657) e `INDIVIDUAL` (424), `Consolidado` (641) y `CONSOLIDADO` (423).
Sin normalizar, un `GROUP BY` devuelve cuatro categorías donde hay dos.

`job8_doc_meta.py` extrae los cuatro campos a la tabla `cnv_doc_meta` y normaliza a
mayúsculas. Es offline: no toca la red.

### El campo que NO sirve

Existe otro campo, `TipoDeDocumento`, con valores `Balance Subsidiaria` (205) y
`Balance Consolidado` (68). **No aplica**: pertenece a otra familia de documentos y
está ausente en el 100 % de los 2.145 que alimentan el screener. Buscar ahí fue un
callejón sin salida; queda documentado para que nadie lo repita.

---

## 7.3 Por qué las holdings mezclaban perímetros

**HAVA** (Havanna Holding S.A.) y **GARO** (Garovaglio y Zorraquin S.A.) concentraban
85 de los 141 ratios contaminados. La causa no es técnica sino contable:

| Concepto | ¿De qué perímetro salía? |
|---|---|
| `Revenue`, `COGS`, `GrossProfit`, `Inventory` | **Siempre CONSOLIDADO** (17-18 casos, cero individual) |
| `NetIncome`, `Equity`, `Assets` | **Casi siempre INDIVIDUAL** (17 vs 1) |

**Una holding no vende nada por sí misma.** Su estado individual no tiene ingresos
operativos, ni costo de ventas, ni inventario — esas partidas solo existen
consolidadas, donde entran las filiales. Pero su balance individual sí tiene activos
y patrimonio (participaciones).

Por eso el `MargenNeto` de HAVA dividía el `NetIncome` de la holding (resultado por
participación) entre el `Revenue` de todo el grupo. No es un margen: es un número sin
significado económico.

Y por eso `ROE` y `ROA` casi no aparecían entre los contaminados (4 y 3 casos): ahí
numerador y denominador venían ambos del individual.

### La regla de selección — dos intentos fallidos antes del bueno

1. ~~«Consolidado siempre»~~ — medido: **destruye el 73 %** de los conceptos en los
   casos mixtos (conserva 3.431 de 12.627).
2. ~~«El más completo»~~ — en HAVA elegiría el **individual** (32-38 conceptos frente
   a 16), que es **justo el perímetro equivocado para una holding**. Habría empeorado
   las cosas pareciendo mejorarlas.
3. **La correcta**: preferir el perímetro que contenga `Revenue`, porque es el que
   refleja la actividad económica real. Para holdings da consolidado. Y **agotar ese
   documento**, no picotearlo.

El punto 2 solo se descartó porque se midió antes de aplicarlo. Es el argumento a
favor de los *dry runs*.

---

## 7.4 Vintage de reexpresión: derivado, no extraído

`fecha_reexpresion` estaba vacía en el 100 % de v2 y de `cnv_estados_norm`. Las 404
filas de la v1 que parecían tenerla son un **falso positivo**: vienen de fuentes SEC
(`cnv-6k`, `cnv-adr`, `cnv-ir`), 280 son formularios `Dividend`, y su valor cae un día
antes o después del `period_end` — es fecha de documento, no vintage NIC 29.

Tampoco está en el texto de los HTML: de 400 muestreados, **1 menciona «reexpresión»**
y es una nota de política contable.

**Pero es derivable al 100 %.** Bajo NIC 29 / RT 6, los estados se expresan en moneda
de poder adquisitivo de la fecha de cierre del período presentado. Verificado: cada
documento de v2 aporta **un único** `period_end` (2.145 documentos, todos con `n=1`).
Por lo tanto:

```
vintage_reexpresion = period_end
```

No es una extracción: es una regla contable.

### Lo que activa

La maquinaria ya estaba escrita y dormida porque la columna estaba vacía:

| Dónde | Qué hace |
|---|---|
| `s0`, PK de `cnv_estados_norm` | Incluye `fecha_reexpresion` — colapsaba al ser siempre NULL |
| `s0`, gate de consistencia | Avisa de «posible vintage de reexpresion distinto» — nunca disparaba |
| `s4`, `get_valor` | `ORDER BY fecha_reexpresion DESC LIMIT 1` — no ordenaba nada |
| `s4`, `get_payout_facts` | Ídem |

### La consecuencia de negocio

Una serie en pesos mezcla, por construcción, tantos vintages como períodos tenga. Los
70 tickers de v2 tienen **todos** más de uno; el máximo observado es **34 vintages en
una sola serie**. Es lo que el `CAGR_flag` venía denunciando como `vintage_mixto`.

Para publicar series comparables hay que reexpresar a un vintage común con el IPC.
`job_vintage_homogenea.py` lo hace: **99,78 % de cobertura** (81.517 de 81.695). Fuera
de rango quedan 178 filas anteriores a dic-2016, que es donde arranca
`data/ipc_nacional.csv`.

Ejemplo del efecto (TXAR, patrimonio, cierres de diciembre):

| | 2018-12-31 | 2025-12-31 | Variación |
|---|---|---|---|
| Pesos nominales | 97.177.005.000 | 6.812.761.000.000 | **+6.911 %** |
| Moneda constante (may-2026) | 6.123.181.704.995 | 7.813.012.228.886 | **+28 %** |

Lo que publica hoy el screener es el +6.911 %. El cambio económico real es +28 %.

---

## 7.5 Las filas BYMA son la punta fresca, no un duplicado viejo

`cnv_estados_norm` tenía 4.098 filas con `source_type='BYMA'` que no existen en v2. La
tentación era descartarlas al migrar. **Medido: en los 46 tickers presentes en ambas
vías, BYMA es más reciente en los 46. Sin una sola excepción.**

| Ticker | Último BYMA | Último CUIT | Retraso si se descartan |
|---|---|---|---|
| BOLT | 2026-04-30 | 2025-07-31 | **3 trimestres** |
| POLL, OEST, MORI | 2026-03-31 | 2025-09-30 | 2 trimestres |
| TXAR, TRAN, MIRG, MOLI | 2026-03-31 | 2025-12-31 | 1 trimestre |

Además **DGCE solo existe por la vía BYMA**: descartarla borraba una empresa entera.

**La regla:** unión, no reemplazo. v2 como base histórica (unidades corregidas) más las
filas BYMA para la punta reciente. No colisionan en ninguna clave: 81.695 + 4.098 =
85.793 exacto.

---

## 7.6 Trampas operativas encontradas

Cosas que costaron tiempo y conviene dejar escritas:

- **`job5_v2` sin `--codigos` no reproduce los datos.** La whitelist por defecto es
  `whitelist_eeff.csv` (32.778 filas) y solo cubre **630 de los 2.145** documentos
  reales. La que corresponde es `whitelist_eeff_codigos.csv` (2.457 filas), que cubre
  **2.144 de 2.145**.
- **`--max` es tope de peticiones de red, no de documentos.** `--max 0` corta en la
  primera iteración aunque todo esté en caché.
- Se añadió **`--offline`**: procesa solo HTML ya guardados y no toca la red. Es lo que
  hace falta cada vez que cambia el parser o la PK.
- Se añadió **`SCREENER_DB`** como variable de entorno en `job5_v2` y `s0`, para poder
  correr contra una copia sin tocar producción.
- **El `ticker` de `cnv_estados_v2` no está normalizado**: trae la razón social
  (`"BANCO BBVA ARGENTINA S A"` en vez de `BBAR`). Cualquier unión debe hacerse por
  **CUIT**, resolviendo el símbolo con el mapeo de `s0`.

---

## 7.7 Pendientes conocidos

- **`Unidad desconocida: 1.106`** en la re-extracción completa (frente a 279 en la
  parcial). El job asigna factor 1 a esos casos; un factor mal puesto es un error de
  tres órdenes de magnitud. **Revisar antes de llevar a producción.**
- **`Identidad>5 %: 11`** — once documentos donde Activo ≠ Pasivo + Patrimonio.
  Candidatos a cuarentena.
- **659 filas (0,81 %) con `period_end` que no cae a fin de mes** (`2018-07-04`,
  `2022-12-25`, `2025-06-09`). No son cierres contables; conviene aislarlas.
- **`tipo_balance` vacío en las 4.098 filas BYMA**: no pasan por `cnv_doc_meta`.
- **La regla de selección de perímetro todavía no está en `s2`.** Mientras no esté,
  `s2` elegirá arbitrariamente entre los dos valores que ahora existen — el mismo
  problema cambiado de sitio.

---

## 7.8 Cierre de los tres pendientes (2026-08-20)

### Unidades desconocidas: 1.030 → 0

Las «unidades desconocidas» eran **todas `$` a secas** — el valor más frecuente
(1.030 de 2.350 documentos), que significa pesos sin escalar. Caían en el
`return None` de `factor_unidad()`, aunque el llamador les asignaba factor 1 igual.

**Ningún dato estaba mal.** Lo que estaba mal era el flag: 1.030 falsas alarmas
tapando cualquier caso real. Si mañana aparece un `Miles de U$S`, con el flag así no
se veía.

Reparto verificado tras el arreglo: factor 1 → 1.030 · factor 1.000 → 962 ·
factor 1.000.000 → 358. **Desconocidas: 0.**

### Regla de perímetro en `s2`

Implementada en `perimetro_preferido()`: por cada `(cuit, period_end)` se elige un
perímetro —el que contenga `Revenue`; a igualdad, el más completo— y se usan solo sus
conceptos. `get_valor_historico()` lo resuelve **por período**, de modo que una serie
puede cambiar de perímetro a lo largo del tiempo (aceptable) pero nunca mezclarlos
dentro del mismo período (inaceptable).

Resultado sobre los 72 tickers: **330 valores idénticos, 38 cambian, 27 aparecen**
(por las filas recuperadas en `job5_v2`), 1 desaparece. 17 tickers afectados, ninguno
perdido ni ganado.

**Validación independiente** contra `CNV_roe` —el ROE que la propia empresa declara
ante la CNV—: de los 6 ROE que cambiaron, **5 quedaron más cerca del auto-reporte** y
1 más lejos. El caso más claro es CVH, que pasa de +0,0142 a **-0,0127** cuando la
empresa declara **-0,01**: el signo estaba invertido.

### Gate de identidad contable (A = P + PN)

Implementado en `s0`: se calcula el desvío por `(cuit, period_end, tipo_balance)` y se
marca en la columna `identidad_desvio_pct` todo lo que supere el 5 %.

**10 estados fuera de tolerancia, 353 filas marcadas.** Los peores:

| CUIT | Período | Perímetro | Desvío |
|---|---|---|---|
| 30704962807 | 2021-12-31 | INDIVIDUAL | 50,4 % |
| 30500833781 (LONG) | 2020-09-30 | INDIVIDUAL | 36,5 % |
| 30617442937 | 2024-03-31 | INDIVIDUAL | 35,8 % |
| 30708544082 (HAVA) | 2025-09-30 | CONSOLIDADO | 33,8 % |

**LONG concentra 6 de los 10.** Su serie individual salta ~100× entre 2020-03
(Assets 2,2e+07) y 2020-06 (2,1e+09) **con la misma unidad declarada (`$`)**, y los
fallos de identidad caen exactamente en esa transición. No se repara: hacerlo exigiría
inventar un factor de escala. Se marca y `s2` puede excluirlo.

Antes y después de esa ventana la identidad cierra al 0,0 %, así que el problema está
acotado a 2019-12 / 2020-12.

---

## 7.9 Validación end-to-end del pipeline (2026-08-20)

### Aislamiento: `SCREENER_DB` en los 11 scripts

Al validar se descubrió por accidente —escribiendo sin querer en producción— que
`SCREENER_DB` estaba solo en los scripts que se habían ido tocando. **`s3`, `s5`,
`s6`, `s7` y `s9` apuntaban siempre a `data/screener.db`.**

Correr el pipeline con la variable puesta ejecutaba una parte sobre la copia y otra
sobre la base real. La lección quedó escrita en el comentario de cada script:

> Debe estar en TODOS los scripts del pipeline: si uno solo no lo respeta, escribe en
> la base real aunque el resto corra sobre la copia.

Hoy los 11 la respetan: `s0` `s2` `s3` `s4` `s5` `s6` `s7` `s8` `s9` +
`job5_v2_extract_eeff` y `job8_doc_meta`.

### Precondiciones entre etapas

El pipeline **ya era idempotente** (`s0`, `s2`, `s4` hacen DROP+CREATE; `s6`-`s9`
usan `ALTER TABLE ADD COLUMN` + `UPDATE`). Lo que no tenía era **precondiciones
verificadas**: `s8` lee `fuente_fund`, que crea `s6`, y no lo comprobaba. Si faltaba,
el error era `IndexError: No item with that key` — que no dice qué falta ni qué hacer.

`_precondiciones.py` lo convierte en una instrucción:

```
ERROR: a `screener` le faltan columnas: fuente_fund, sector, es_financiera
Las crea s6_ajustes. Corré esa etapa primero.
```

**No se buscó independencia de orden**, y sería un error hacerlo: el orden es
información sobre cómo se construyen los datos. Lo que estaba mal era que fuese
implícito.

### Resultado de la corrida completa sobre la copia

Estructura **idéntica** a producción: 572 filas, 44 columnas, mismos tres grupos
(499 sp500 · 56 byma_only · 17 adr). Ninguna columna de más ni de menos.

| | Cantidad |
|---|---|
| Ratios idénticos | **4.694 (98 %)** |
| Cambian de valor | 49 |
| Aparecen (antes `null`) | 2 |
| Desaparecen | 48 |
| Papeles afectados | 58 de 572 |

**Los 49 cambios de valor son correcciones de la mezcla de perímetros.** Los mayores:

| Ticker | Ratio | Antes | Después |
|---|---|---|---|
| CVH | EPS | +157,06 | **−206,93** (de ganancia a pérdida) |
| CTIO | ROE | −0,0014 | −0,0100 (7×) |
| CTIO | PriceBook | 0,99 | 7,16 |
| MIRG | MargenNeto | 4,31 % | 0,46 % |

Validados contra `CNV_roe` (auto-reporte de la empresa): **5 de 6 quedaron más cerca**.

### Los 48 que «desaparecen» no son una pérdida

**46 de los 48 son del S&P 500**, que no pasa por CNV. La causa es otra: en la corrida
accidental sobre producción **`s8_calidad` falló** mientras `s6`, `s7` y `s9`
completaron. Producción quedó **sin la fase de calidad aplicada**:

| | `payout_status` con valor |
|---|---|
| Producción | **73 / 572** |
| Rama | **572 / 572** |

`s8.apply_no_significativo()` anula ratios sin significado — un ROE o un P/B con
patrimonio negativo es una división sin sentido. Los afectados lo confirman: AZO
(−3.539 M), BA (−3.908 M), CAH (−3.213 M), DELL (−1.482 M). `flag_no_significativo`
sube de 70 a 78: ocho papeles más correctamente marcados.

Los 2 restantes sí son la regla de perímetro: `CVH` y `SUPV` pierden el PER porque su
`EPS_diluido` solo existe en un perímetro distinto del elegido. **Queda sin dato en
vez de mezclarse**, que es exactamente lo buscado.

### Pendiente en producción

Producción está hoy **sin la fase de calidad**: publica ROE y P/B de empresas con
patrimonio negativo. Conviene correr `s8_calidad` allí, independientemente de lo que
se decida con esta rama.

---

## 7.10 Migración a PostgreSQL: por qué no se ejecutó (2026-08-20)

`migrate_sqlite_to_pg.py` hace **`TRUNCATE TABLE ... CASCADE` y después `INSERT`**.
Si el `INSERT` falla —por ejemplo, porque el esquema de destino no tiene una columna
nueva—, la tabla ya está vacía. Y el fallback fila-por-fila tenía un
`except Exception: pass` que lo silenciaba: podía migrar 400 de 572 filas y reportarlo
como éxito.

### El simulacro (solo lectura, sin conectar a PostgreSQL)

Se comparó el esquema real del SQLite contra `sql/init/01_schema.sql`, usando el
`TABLES_ORDER` y el `COLUMN_MAPPING` reales del script. De 19 tablas:

| | |
|---|---|
| Compatibles | 16 |
| Se saltean (no existen en local) | 1 (`iamc_precios`) |
| **Bloqueantes** | **2** |

- **`screener`**: faltaban en PostgreSQL las **11 columnas de la migración MEP**
  (`precio_usd_calc_mep_dolarito`, `valor_mep_dolarito`, `fecha_mep_dolarito`,
  `max_52w_ars_yfinance`, `min_52w_*`, `dif_*_52w_pct`, `pct_ruedas_operadas`,
  `guard_motivo`).
- **`ratios_cnv`**: el `COLUMN_MAPPING` tenía la clave `"margenneto"` en minúsculas y
  la columna real se llama `MargenNeto`, así que **el mapeo nunca se aplicaba**. Y de
  `DeudaEBITDA` y `FCFYield` no había entrada.

**Qué habría pasado:** `TRUNCATE` borra las 572 filas de `screener` → el `INSERT` falla
por las 11 columnas → el fallback rechaza las 572 en silencio → **la API devuelve cero
empresas**.

### Lo que se corrigió (sin tocar PostgreSQL)

1. **`sql/init/01_schema.sql`**: +11 columnas en `screener`.
2. **`COLUMN_MAPPING`**: claves con el nombre exacto de SQLite, y las que faltaban.
3. **Precondición antes del `TRUNCATE`**: lee `information_schema.columns` del destino
   y **aborta esa tabla sin destruirla** si falta alguna columna o la tabla no existe.
4. **El fallback ya no silencia**: cuenta las filas rechazadas, muestra los tres
   primeros errores y **sale con código 1** si algo quedó incompleto.

Re-simulacro tras los arreglos: **0 bloqueantes**.

### Recomendación pendiente

`TRUNCATE + INSERT` sin transacción envolvente es frágil para una tabla que sirve una
API en vivo. El patrón habitual es **cargar a una tabla temporal y hacer un swap
atómico** (`ALTER TABLE ... RENAME`): si algo falla, la tabla vieja sigue sirviendo y
nadie se entera. No se implementó porque cambia el diseño de la migración, no es un
arreglo puntual.

### Aclaración sobre las dos «producciones»

Durante la sesión se usó «producción» para dos cosas distintas:

| | Qué es | ¿Se tocó? |
|---|---|---|
| `data/screener.db` | SQLite local | **Sí**: migración MEP y `s8_calidad` |
| `api.catalaxia.webshooks.com` | El **PostgreSQL** que sirve la API | **No** |

La API sigue sirviendo el esquema anterior (con `ccl`, `precio_fuente`,
`precio_dif_iamc`; sin los campos MEP). Verificado el 2026-08-20: HTTP 200, 572
empresas, 45 campos.

---

## 7.11 Serie diaria de precios (`s3b_precios_historicos.py`)

`s3_precios` guarda **una foto por ticker** y solo baja los que **aún no están**
(`NOT EXISTS`): no tiene modo refresco. Para actualizar hay que vaciar la tabla, y eso
es destructivo — al hacerlo se borran también los 499 precios del S&P 500, que `s3` no
repone porque su universo es solo el subset CNV (`mapa_entidades WHERE es_primario=1`).

`s3b` resuelve el problema de raíz: guarda **los hechos** (la serie diaria) en vez de la
foto, y la foto pasa a ser derivable. Es la misma idea del vintage: conservar el dato
crudo y derivar lo demás.

### La tabla

```sql
CREATE TABLE precios_diarios (
    ticker TEXT, fecha TEXT,          -- una fila por (ticker, rueda)
    open, high, low, close, adj_close, volume,
    currency,                          -- ARS o USD, separadas
    ticker_yf,                         -- que simbolo se consulto
    fuente, ingested_at,               -- trazabilidad
    PRIMARY KEY (ticker, fecha)
);
```

### Resultado de la primera carga (9-jul → 20-ago 2026)

| Grupo | Ruedas | Tickers |
|---|---|---|
| sp500 | 14.624 | **499 / 499** |
| byma_only | 1.557 | 53 / 56 |
| adr | 457 | 16 / 17 |
| **Total** | **16.638** | **568 / 572** |

Sin serie: `BOLT_2`, `DGCE`, `PATA_2`, `YPFLUZ` — sin símbolo válido en yfinance o sin
operar.

**Integridad**: 0 duplicados · 0 `high < low` · 0 `close` fuera de `[low, high]` ·
0 volumen negativo · 4 `close` nulos (ruedas sin operaciones). Densidad consistente,
~560 papeles por rueda, sin huecos.

### Incremental de verdad

Cada ticker arranca desde el día siguiente al último que ya tiene. Verificado: la
segunda corrida bajó **0 ruedas**. No hace falta vaciar nada.

### Qué habilita

- **Precio en USD día a día**, con el MEP de *ese* día. Hoy los 56 locales usan un
  único MEP para todos.
- **PER histórico** de cualquier fecha: precio de ese día ÷ EPS del período vigente.
- **Backtests sin sesgo de anticipación** — la pieza que faltaba del modelo bitemporal.

### Pendiente

`s4` sigue leyendo de `precios` (la foto), así que **el S&P 500 del screener sigue con
el precio del 9 de julio** pese a tener serie hasta hoy. Derivar `precios` del último
cierre de `precios_diarios` cierra el círculo y elimina de paso el problema del refresco
destructivo.
