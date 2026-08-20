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
