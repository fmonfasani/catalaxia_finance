# Plan de Extracción

> Estado: propuesta. Escrito el 2026-08-21 con mediciones sobre la base real.
> Complementa `docs/07-homologacion-cnv.md`, que cubre la parte de Transform.

## Por qué

Nos enfocamos meses en Transform —homologar, validar, corregir— y funcionó: el
pipeline pasó de no tener ninguna medida a tener nueve capas con número. Pero
Transform solo puede trabajar con lo que Extract le entrega.

El principio que ordena todo lo que sigue:

> **La extracción no baja números: baja hechos con su contexto.**
> Todo lo que se descarte en Extract es una pregunta que Transform no va a
> poder responder.

El caso que lo prueba: `ratios` guardaba el TTM sin declarar hasta qué cierre
llegaba. Con eso, trece comparaciones entre ADR resultaron inválidas —
comparaban el ejercicio 2024 de EDGAR contra el 2025 de la CNV y el desacuerdo
parecía un error de dato. El período **estaba** en `facts`; se perdió al agregar.

---

## Lo que YA existe (medido, no supuesto)

Antes de proponer nada conviene saber qué hay. Medido el 2026-08-21:

| Pieza | Estado |
|---|---|
| Crudo de EDGAR guardado | **8.643 JSON** en `data/raw/companyfacts/` |
| Índice de presentaciones | **8.020 JSON** en `data/raw/submissions/` — sin usar |
| Extracción de 6-K | `cnv/scripts/cnv_auto.py` — escrita, apenas corrida (68 filas) |
| Detección de escala y período | dentro de `cnv_auto.py` |
| Validación de identidad contable | dentro de `cnv_auto.py` |
| Descarga de companyfacts | `sec_edgar/scripts/construir_base.py` |

`cnv_auto.py` merece una nota: ya resuelve descubrimiento por `index.json` con
caché, conversión HTML/PDF a texto, detección de escala, detección de período y
validación de identidades. Es casi todo lo que reconstruimos a mano en Transform.
No está enchufado al pipeline.

Y `data/raw/submissions/` es justo el insumo que hace falta para saber cuándo
presentó cada empresa. Está bajado y nadie lo consulta.

---

## Los tres problemas reales

### 1. El caché es por empresa, no por fecha

`construir_base.py`, línea 230:

```python
ya = {r[0] for r in con.execute(
    "SELECT cik FROM empresas WHERE fecha_facts IS NOT NULL")}
...
stats["skip"] += 1; continue
```

Una vez bajada, una empresa **nunca se vuelve a bajar**. Todas se bajaron el
2026-06-26 y quedaron congeladas.

El efecto depende del formulario:

| | Formulario | Frecuencia | Atraso máximo |
|---|---|---|---|
| S&P 500 | 10-Q | trimestral | 3 meses |
| ADR | **20-F** | **anual** | **12 meses** |

Medido contra EDGAR el 2026-08-21:

```
        último 20-F en EDGAR    tenemos hasta
BBAR    2026-04-09              2024-12-31
LOMA    2026-04-28              2024-12-31
SUPV    2026-04-08              2024-12-31
TGS     2026-04-22              2024-12-31
PAM     2026-04-09              2024-12-31
CEPU    2026-04-22              2024-12-31
```

Todos presentaron el ejercicio 2025 en abril de 2026. Bajamos en junio y aun así
tenemos 2024: el caché los saltó desde una descarga anterior.

### 2. Los 6-K se ignoran

Las emisoras extranjeras presentan **20-F anual** y **6-K para los intermedios**
— el equivalente al 10-Q. Todos los ADR tienen 6-K de los últimos días (CEPU del
2026-08-19, IRSA del 2026-08-21).

Sin ellos, un ADR tiene **un dato al año** mientras el S&P 500 tiene cuatro. Es
lo que impide armar un TTM del lado de EDGAR.

### 3. Diez ADR con el dato bajado y sin asociar

```
CAAP  CRES  GGALB  TGSU2  PAMP  IRSA  TECO2  SUPVB  YPFLUZ  YPFD
```

Sus `facts` existen bajo su CIK; `screener` guarda el CUIT y nunca se cruzaron.
**No es un problema de descarga: es de identidad**, y se arregla sin red.

---

## La pieza que faltaba: la expectativa

Auditar sin expectativa produce ruido. Una medición ingenua sobre las 572
empresas daba *"500 sin datos de la CNV"* — y está bien que no los tengan: son
compañías de Estados Unidos.

> **Un hueco solo es un hueco contra lo que DEBERÍA estar.**

| Grupo | n | Fuentes obligatorias | Períodos/año |
|---|---|---|---|
| `sp500` | 499 | EDGAR | 4 |
| `byma_only` | 56 | CNV | 4 |
| `adr` | 17 | **CNV y EDGAR** | 4 |

Con esa referencia, la cobertura real:

```
sp500        499 de 499 completas
byma_only     56 de  56 completas
adr            6 de  17 completas    ← 10 sin EDGAR, 1 sin CNV
```

De 500 falsos huecos a **11 reales**.

Está implementada en `scripts/tickets/screener/_expectativa.py`.

**Una trampa que costó encontrar:** la tabla `ratios` mezcla dos fuentes bajo el
mismo techo — hechos de EDGAR y precios de yfinance, distinguidos solo por
`grupo` (`'adr_arg'`/`'sp500'` contra `'byma_yf'`). Comprobar EDGAR por ticker
daba que 54 de las 56 BYMA-only "tienen datos de EDGAR": eran filas de yfinance.
**La comprobación va por CIK y nunca por ticker** — el ticker además colisiona
entre mercados (INTR es un papel de BYMA y también un ADR brasilero).

---

## Los dos pipelines

La diferencia no es de tamaño sino de **pregunta**.

### Auditor general — mensual

No busca huecos: mide el estado completo y lo compara contra el mes anterior.

| Dimensión | Qué mide |
|---|---|
| Cobertura | cada empresa tiene las fuentes que le corresponden |
| Completitud | los períodos esperados según su calendario fiscal |
| Frescura | distribución de antigüedad, no un promedio |
| Consistencia | las nueve capas de `tablero.py` |
| Trazabilidad | qué hechos no tienen procedencia |
| **Deriva** | **qué cambió desde la auditoría anterior** |

La última es la que lo hace mensual y no una foto. Guarda cada corrida en una
tabla `auditoria` y responde *¿mejoré o empeoré?*. Sin eso se vuelve al problema
de fondo: arreglar sin saber si se avanza.

**Termina con un diagnóstico clasificado y una pregunta, no con una descarga:**

| Clase | Qué significa | Qué se hace |
|---|---|---|
| `no_presentado` | la empresa no lo presentó | nada, es correcto |
| `en_crudo_sin_parsear` | está bajado, no procesado | reprocesar, **sin red** |
| `no_asociado` | bajado, sin cruzar con la entidad | arreglar identidad |
| `no_descargado` | existe en EDGAR y no lo tenemos | descarga quirúrgica |
| `descarga_fallo` | se intentó y falló | reintentar |
| `sin_determinar` | no sabemos | **preguntar** |

Esa clasificación convierte "faltan datos" en una lista de acciones con costo
distinto. Hoy, de los 11 huecos reales, **10 son `no_asociado`** — cinco minutos,
no una noche de descargas.

### Actualizador — diario

Supone que la base está bien. Solo pregunta *¿hay algo nuevo desde ayer?*

```
para cada entidad:
    leer data/raw/submissions/<cik>.json        ← ya está bajado
    si hay presentación posterior a la última ingesta:
        bajar SOLO esa
        reprocesar SOLO lo afectado
    certificar que no rompió nada
```

Corre en minutos. Y arranca con lo que ya hay en disco, así que el primer día
dice quién está atrasado **sin tocar la red**.

---

## Lo que falta escribir

| | Pieza | Estado |
|---|---|---|
| 1 | Expectativa por empresa | **hecha** (`_expectativa.py`) |
| 2 | Asociar el CIK de los 10 ADR | falta — gratis, sin red |
| 3 | Caducidad por presentación | falta — el insumo está bajado |
| 4 | Registro de descargas (`ingesta_log`) | falta |
| 5 | Completitud de períodos | falta |
| 6 | Enchufar `cnv_auto.py` (los 6-K) | falta enchufar, no escribir |
| 7 | Auditor mensual | falta |
| 8 | Actualizador diario | falta |

### El orden, y por qué

**2 primero**: cierra la única brecha real de cobertura y no cuesta nada.

**3 después**: arregla el congelamiento y evita que vuelva. Con el índice ya
bajado, es leer un JSON y comparar dos fechas.

**4 antes que 7**: sin registro de descargas, el auditor no puede distinguir
"no existe" de "falló la bajada" — y esa distinción es la mitad de su valor.

**6 al final del bloque de extracción**: los 6-K multiplican por cuatro la
granularidad de los ADR, pero conviene hacerlo cuando el registro ya exista para
poder medir qué aportaron.

---

## El registro de descargas

Una fila **por descarga**, no por empresa. Hoy `fecha_facts` es una sola marca
que se pisa, y por eso no se puede responder *"¿cuándo bajé esto y qué obtuve?"*.

```sql
CREATE TABLE ingesta_log (
    fuente         TEXT,   -- sec_edgar | cnv_aif2 | dolarito | yfinance
    entidad        TEXT,   -- cik o cuit
    url            TEXT,
    solicitado_at  TEXT,
    respuesta      INTEGER,-- 200 / 404 / 429 / timeout
    bytes          INTEGER,
    hash           TEXT,   -- sha256 del contenido
    filas_nuevas   INTEGER
);
```

`hash` permite saber si una descarga trajo algo distinto de la anterior sin
reprocesarla. `respuesta` distingue un 404 —el dato no existe— de un 429 —nos
limitaron y hay que reintentar—, que hoy se ven igual: como un dato ausente.

---

## La huella en el hecho crudo

`facts` guarda `period_start`, `period_end`, `fy`, `fp`, `form`, `filed`. Le
faltan cuatro cosas que hoy se descartan:

| Campo | Para qué |
|---|---|
| `accession` | volver al documento exacto que originó el hecho |
| `unidad` | USD, ARS, shares, pure |
| `decimales` | el atributo XBRL: cuánta precisión declara el emisor |
| `es_restatement` | si corrige una presentación anterior |

**`decimales`** distingue un número redondeado a millones de uno exacto. Sin él,
no se puede saber si una diferencia del 2% es un error o redondeo declarado.

**`es_restatement`** es la bitemporalidad: la misma empresa, el mismo período,
dos valores presentados en fechas distintas. Sin esa marca, una corrección
posterior parece una contradicción.

> Estos dos campos cambian el esquema de `facts`, que tiene **4,6 millones de
> filas**. Conviene hacerlo con el crudo guardado, para poder reconstruir en vez
> de migrar.
