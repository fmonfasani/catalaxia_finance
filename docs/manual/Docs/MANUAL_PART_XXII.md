# ANEXO E · ARQUITECTURA DE LAS 12 CAPAS — EXPLICACIÓN OPERACIONAL

Explicación profunda y operacional de las 12 capas de la arquitectura de Catalaxia.
Base: el manual operativo v2.0 (Partes II–XVIII), los runbooks y el estado real
medido del sistema.

**Regla de lectura de este anexo.** Cada capa se explica en dos niveles, siempre
separados:

- **[HOY]** — lo que existe en el repositorio principal y está medido; se cita el
  artefacto real (script, tabla, gate, defecto).
- **[OBJETIVO]** — el diseño recomendado cuando la capa todavía no está completa o
  vive en el worktree. Todo lo que es aspiración se marca como tal y no se vende
  como si estuviera andando.

**Nota de decisiones abiertas.** Varias capas dependen de **D-1** (repo principal
vs. worktree `catalaxia-cnvmig` para Economic Facts, Financial Model, tramo C de CNV
y homologación TIKR), **D-3** (certificar KO o cambiar piloto), **D-4** (vocabulario
de homologación) y de las certificaciones **C-1…C-6**. Este anexo no las resuelve:
las marca y sigue.

---

## 1. FUENTES

### Objetivo
Obtener y preservar la **evidencia original** (documentos y datos) desde los
proveedores regulatorios y de mercado, sin interpretarla todavía.

### ¿Qué es?
La capa que decide **qué se va a bajar, de dónde, cómo y con qué controles**. No
almacena datos económicos: almacena documentos y series crudas. Separa tres
universos: **SEC/EDGAR**, **CNV** y **Market**.

### ¿Qué problema resuelve?
Sin una capa de fuentes explícita, cada consumidor baja los datos por su cuenta:
se mezclan versiones, se rompe la reproducibilidad y no hay forma de auditar qué se
vio. Esta capa establece el **contrato de ingesta**: todo dato que entra al sistema
sale de un proveedor identificado, con su get etiqueta (proveedor, documento,
fecha, hash).

### ¿Cómo funciona?
Dos modos de obtención:

1. **Discovery**: identificar qué documentos existen (filings de una entidad, EEFF
   de la CNV, instrumentos del mercado).
2. **Download + hash**: bajar el archivo, calcular el hash, guardarlo inmutable en
   RAW y registrar el metadato.

La regla operativa del sistema es que esta capa **nunca normaliza**: el dato se
guarda tal cual se obtuvo.

### Flujo interno
```
proveedor → discovery → [nuevo documento?] → download → SHA256 → [RAW] → registro en ledger de ingesta
```

### Objetos / subetapas

#### SEC / EDGAR
- **Qué es:** la fuente regulatoria de EE. UU. Provee firmas presentadas en XBRL
  (10-K, 10-Q, 20-F) más el dataset agregado *companyfacts* (JSON) y el índice de
  submissions por CIK.
- **Qué hace:** expone filings por entidad y por formulario, con toda la taxonomía
  XBRL (facts + contexts + units) en un solo archivo para los documentos estándar.
- **Entrada:** un CIK (identidad de emisor ante la SEC).
- **Salida:** archivos (XML ZIP del filing completo, JSON de companyfacts) con su
  hash.
- **Cómo funciona:** descarga directa de EDGAR con `User-Agent` identificado
  (requisito de la SEC), respetando las límites de rate. Scripts reales: `S01
  (identity)` para el CIK y `S02_fetch_ypf` para la descarga.
- **Validaciones:** HTTP 200, tamaño > 0, paridad de hash tras la descarga,
  conteo de hechos esperados para el formulario.
- **DoD:** el archivo original está en RAW, íntegro, con hash y metadato de
  descarga registrado.

#### CNV
- **Qué es:** la fuente regulatoria argentina. Provee **estados contables (EEFF)**
  de emisores listados, en HTML, por ejercicio y trimestre.
- **Qué hace:** a diferencia de EDGAR, no entrega XBRL estructurado: entrega
  páginas HTML que hay que interpretar. Implica un esfuerzo de parsing mayor y la
  existencia de un **mapa semántico** local (qué página, qué período, qué
  perímetro).
- **Entrada:** CUIT del emisor + período.
- **Salida:** páginas HTML de EEFF con hash, más los metadatos del documento
  (período, estado: `DONE`, `con_filas`, `PROCESSED_OK`, `REJECTED`,
  `FAILED_FINAL` — hay 286 documentos en whitelist, 56 `DONE`).
- **Cómo funciona hoy:** tres tramos separados — **A** (`c3_cnv_fetch`, con gates
  y ledger, pero solo baja `VISOR` y `EMPRESA_PAGE`, **no los EEFF**: `L-7`,
  `SG-01`); **B** (`job5_v2_extract_eeff`, legacy, **el que produjo todos los datos
  CNV existentes**, sin ledger ni SHA, escribe en `data/screener.db`, descarta en
  silencio `CNV-EX-001`/`L-6`); **C** (`c4_cnv_adapter`, canónico, **en el
  worktree**, pendiente D-1).
- **Validaciones:** pertenencia a la whitelist (286), no duplicado, formato de
  página (transición 2018–2019: `ATTACHMENT_ONLY` 197, `OTHER_FORM` 29 — la cota
  de 60 documentos es la frontera de formato).
- **DoD de la fuente CNV:** cada EEFF de la whitelist tiene su documento descargado,
  íntegro, con hash (`hash_cnv` — **hoy NULL en 4.005/4.005, `SG-02`**) y su estado
  registrado.

#### MARKET
- **Qué es:** la fuente de mercado: precios, acciones corporativas, FX y benchmarks
  (yfinance u homólogo, más el feed de TIKR para homologación).
- **Qué hace:** mantener series actualizadas de precios (4.799.938 filas, 584
  instrumentos), 51.917 acciones corporativas y 8.322 filas de calidad, con 601
  filas de fetch auditadas en el log.
- **Entrada:** ticker + mercado/venue.
- **Salida:** filas `market_*` (precio, fecha, eventos) con su log de fetch.
- **Cómo funciona:** jobs de fetch con actualización incremental; orden de
  migraciones **F-051**: `m19_apply_schema` antes que `s00_smoke`, o las tablas se
  omiten en silencio.
- **Validaciones:** filas cronológicamente coherentes, sin huecos bruscos, calidad
  de datos (8.322 filas).
- **DoD:** series completas para el universo de instrumentos, con log de fetch y
  calidad registrada.

### Dependencias
No depende de ninguna otra capa. Es el punto más externo. Depende de los
proveedores (disponibilidad de la SEC, la CNV y el feed de mercado).

### Errores y edge cases
- Rate limits / bloqueo por User-Agent (SEC).
- Cambios de URL o formato de página (CNV 2018–2019).
- Documentos que existen pero no descargan (permisos, JS).
- Duplicados por re-pull: mitigar con hash + dedup por (proveedor, documento).
- Interrupciones: el ledger de ingesta debe poder reanudar (idempotencia de
  fetch). [HOY: el tramo B CNV descarta en silencio — defecto `L-6`.]

### Definition of Done de la capa
La capa FUENTES está terminada cuando: **todo el universo declarado de documentos
y series (SEC, CNV, Market) está descargado, íntegro (verificado por hash), con su
metadato de ingesta registrado y reproducible con un solo comando, sin duplicados y
sin descartes silenciosos.** [HOY: no se cumple — falta el tramo C CNV y el
`hash_cnv` (`SG-02`).]

### ¿Qué habilita la siguiente capa?
Le da a IDENTIDAD y RAW la evidencia para decir: *"qué documento de qué entidad
corresponde a qué período"*.

---

## 2. IDENTIDAD

### Objetivo
Determinar **inequívocamente qué entidad económica e instrumento** se está
procesando, antes de interpretar cualquier dato.

### ¿Qué es?
Un diccionario de entidades (empresas) e instrumentos (tickers/ISIN) con
identificadores canónicos vinculados a los proveedores (CIK para SEC, CUIT para
CNV, ticker/ISIN para mercado) y a un ID interno (`entity_id`).

### ¿Qué problema resuelve?
El problema del **homónimo y del alias**: una misma compañía aparece como
"MetroGas", "METROGAS S.A.", "Metrogas", con CUIT X; otra figura con CJK distinto.
Si la identidad no se resuelve antes, mezclamos empresas o duplicamos datos.

### ¿Cómo funciona?
Construcción de registros de identidad con reglas de matching y **normalización
del nombre legal** (reglas de lenguaje aplicadas al nombre declarado por CADA
fuente), consolidación de alias y validación por humano o por regla de
autoridad (`is_authoritative`).

### Flujo interno
```
(wild card por fuente) → candidatos → matching (CIK/CUIT, nombre, ticker) → unificación → entity_id canónico
```

### Objetos / subetapas

#### CIK / CUIT
- **Qué es:** CIK — identificador de la SEC (nueve o diez dígitos). CUIT — clave
  única de Argentina (11 dígitos). Ambos son **identificadores de proveedor**, no
  la identidad canónica.
- **Qué hace:** vincular la aparición del emisor en la fuente.
- **Entrada:** el documento/serie que llega de la fuente.
- **Salida:** una entrada de identidad (`entity_id` + `identifiers` con
  `CIK:`/`CUIT:`).
- **Cómo funciona:** backfill por CIK (S01) y asignación de CUIT en CNV. Guardado
  de la TUPLA fuente→ID.
- **Validaciones:** unicidad del par (fuente, identificador), formato del número.
- **DoD:** todo documento entrante tiene su identidad de proveedor resuelta.

#### ENTITY
- **Qué es:** la entidad económica canónica (la empresa, no el papel).
- **Qué hace:** ser el sujeto de todos los hechos económicos; unir las apariciones
  de la empresa en las distintas fuentes.
- **Entrada:** CIK/CUIT + nombre legal declarado + ticker.
- **Salida:** `entity_id` canónico, nombre normalizado, perímetro, estado.
- **Cómo funciona:** el Identity Resolver consolida: reglas de matching, validación
  y unificación (diagrama oficial "Identidad de una empresa").
- **Validaciones:** no crear duplicados; si hay homónimos, se separan por
  país/mercado/identificadores.
- **DoD:** cada entidad tiene `entity_id` único y sus identificadores de fuente.

#### INSTRUMENTO
- **Qué es:** el vehículo cotizante (el papel), distinto de la empresa.
- **Qué hace:** conectar entidad con mercado: ticker (y su venue), ISIN, moneda de
  cotización, tipo (equity, ADR).
- **Entrada:** altas desde Market (tickers) y desde SEC (el emisor).
- **Salida:** registro de instrumento con `entity_id` de su emisor.
- **Cómo funciona:** dentro de la capa Market se resuelven los tickers por
  venue/mercado. **Ojo [HOY]:** `market_instruments.entity_id` es **integer legacy**
  que no respeta el esquema con namespace (`CIK:`/`CUIT:`) — **SG-10**. Los
  instrumentos quedan vinculados al emisor solo cuando el identificador se
  normalizó.
- **Validaciones:** un ticker→una entidad por venue; si el mismo ticker cotiza en
  dos venues se guardan los dos instrumentos, no se pisan.
- **DoD:** todo instrumento del universo Market tiene su emisor resuelto.

### Dependencias
Depende de FUENTES (de dónde salen los CIK/CUIT/tickers) y de MARKET (para
instrumentos). Es prerrequisito de RAW y NORMALIZED: no se puede etiquetar un dato
sin saber a qué entidad pertenece.

### Errores y edge cases
- **Cambio de ticker** (una empresa que cambia su símbolo). Regla: el ticker es un
  **alias temporal** del instrumento; el `entity_id` no cambia. Se registra el
  historial de tickers.
- **Mismatches**: CUIT de empresa matriz vs. operativa; perímetro `individual` vs
  `consolidado`.
- **CNV**: `9 de 7.998` entidades con hechos en `engine` [L-16] — la identidad
  financiera real está distribuida; hay mucha identidad declarada sin hechos.
- **Falta de autoridad**: cuando dos fuentes dicen cosas distintas, manda la
  fuente de mayor jerarquía (principio: fuentes primarias > secundarias >
  benchmarks).

### Definition of Done de la capa
"Sabemos exactamente a qué entidad e instrumento pertenece cada dato" cuando:
toda entidad del universo tiene `entity_id` canónico con identificadores de
proveedor validados; todo instrumento tiene emisor resuelto; y no existen dos
`entity_id` para la misma empresa (verificable por auditoría de duplicados).

### ¿Qué habilita la siguiente capa?
RAW puede etiquetar cada descarga con su entidad/instrumento y, más adelante, los
hechos económicos saben a quién pertenecen.

---

## 3. RAW

### Objetivo
Preservar la **evidencia original sin modificarla**: una copia íntegra,
versionada y reproducible de todo lo que se descargó.

### ¿Qué es?
Un almacenamiento inmutable de los archivos tal como vinieron de la fuente, con su
hash (SHA256) y su metadato. Es la "caja fuerte" de la auditoría.

### ¿Qué problema resuelve?
El problema del **estándar de oro de auditoría**: si el sistema no guarda el
original, ningún número posterior puede demostrarse contra su documento. RAW es lo
que permite repetir un procesamiento años después con el mismo insumo y verificar
que el resultado es el mismo (reproducibilidad).

### ¿Cómo funciona?
Solo escritura. Una vez depositado un archivo, no se edita: se versiona. La
identidad del archivo es su hash; el metadato (`documento`, `entidad`, `período`,
`proveedor`) vive en las tablas de ingesta, no dentro del archivo.

### Flujo interno
```
download → [hash SHA256] → store inmutable → registrar metadato (documento→hash) → [verificación de integridad]
```

### Objetos / subetapas

#### DESCARGA
- **Qué es:** el acto de bajar (o recibir) el archivo.
- **Qué hace:** transferir + primera verificación de integridad.
- **Entrada:** URL/discovery de la fuente + identidad.
- **Salida:** archivo en disco + metadato de descarga (fecha, fuente, tamaño).
- **Cómo funciona:** por job de ingesta (S02, c3/c4 CNV, fetch de Market) con
  reanudación e idempotencia.
- **Validaciones:** HTTP no-2xx → abort; el archivo debe existir y no estar
  vacío.
- **DoD:** la descarga quedó registrada en el ledger y el archivo apunta a su copia
  inmutable.

#### RAW (almacenamiento)
- **Qué es:** el directorio/storage inmutable (HTML, JSON, PDF, …).
- **Qué hace:** guardar el archivo **tal cual se descargó**.
- **Entrada:** bytes originales.
- **Salida:** copia inmutable (nunca más manipulada).
- **Cómo funciona:** convención de ruta por (fuente, entidad, documento, período) y
  hash; jamás se sobrescribe una ruta.
- **Validaciones:** si el archivo ya existe, se compara hash para decidir si es un
  duplicado o una nueva versión.
- **DoD:** el archivo está en la ruta canónica con su hash.

#### SHA256
- **Qué es:** la huella digital del archivo.
- **Qué hace:** dar identidad e integridad: dos descargas del mismo archivo dan el
  mismo hash; un byte cambiado, otro hash.
- **Entrada:** bytes del archivo.
- **Salida:** hash de 64 caracteres registrado junto al metadato.
- **Cómo funciona:** cálculo local tras la descarga y verificación (re-hash) en la
  lectura.
- **Validaciones:** hash coincide al descargar; el re-hash al procesar coincide con
  el registrado.
- **DoD:** el hash registrado es verificado de nuevo en cada relectura.

#### Versionado y duplicados
- **Qué es:** el manejo deliberado de "mismo documento, dos veces" (re-pull) y de
  "documento corregido".
- **Qué hace:** si el archivo ya existe con el mismo hash → se ignora (dedup); si
  tiene hash distinto → se registra como nueva versión con su propio hash, **sin
  pisar la anterior**.
- **DoD:** el histórico de versiones es íntegro y consultable.

### Dependencias
Depende de FUENTES (obtención) e IDENTIDAD (etiqueta el documento). No depende de
PARSED: RAW existe aunque nadie lo parsea todavía.

### Errores y edge cases
- **CNV [HOY]:** el tramo legacy no calcula ni registra `hash_cnv` (`SG-02` en
  4.005/4.005). Es el hueco más grave de integridad de todo el sistema: los
  archivos que en teoría alimentan `parsed.facts` no tienen huella verificable.
- **Archivos gigantes** (ZIP completos de EDGAR): hash incremental (streaming).
- **Codificación/encoding** raro en HTML CNV: montar a utf-8-normalizado con
  warning, jamás reescribir el RAW.
- **Duplicados de re-pull:** resolver por hash, no por nombre de archivo.

### Definition of Done de la capa
"Tenemos una copia íntegra y reproducible de la evidencia original" cuando: **todo
documento declarado en FUENTES está en RAW con SHA256 registrado y verificado, y
un reprocesamiento de la fuente cae sobre los mismos archivos (mismos hashes) sin
crear duplicados.** [HOY: no se cumple en CNV por `SG-02`.]

### ¿Qué habilita la siguiente capa?
Le da a PARSED el insumo **verificado**: el parser puede citar "procesé el archivo
X (hash Y)".

---

## 4. PARSED

### Objetivo
Transformar documentos RAW en **estructuras procesables por software** (datos
extraídos), sin interpretarlos económicamente todavía.

### ¿Qué es?
La capa que "rompe" el documento: convierte el XBRL/HTML/JSON en **facts** con su
contexto y su unidad, y los guarda en `parsed.facts` manteniendo la estructura de
origen.

### ¿Qué problema resuelve?
El problema de la **heterogeneidad bruta**: los datos crudos no se pueden ofrecer
tal cual; hay que extraerlos y estructurarlos para que las capas siguientes los
consuman. PARSED separa el *"qué dijo el documento"* del *"qué significa"*.

### ¿Cómo funciona?
Interpretación sintáctica (no semántica por línea de documento): línea

```
documento RAW → taxonomía → [fact, context, unit] → parsed.facts
```

### Flujo interno
```
RAW (con hash) → validación de formato → extracción → conformar facts → guardar en parsed.facts (idempotente)
```

### Objetos / subetapas

#### FACTS
- **Qué es:** cada dato concreto declarado en el documento (un valor con su
  concepto).
- **Qué representa:** una ocurrencia: "la Revenue del período 2024 fue 45.754
  millones USD".
- **Entrada:** el dato del documento (para XBRL: el `<fact>`).
- **Salida:** fila en `parsed.facts`.
- **Cómo funciona:** el parser lee el documento y materializa cada hecho con su
  `fact_key`. Tipos reportados por CNV: unidades reales como `ars@1e6` (1.120),
  `ars@1e3` (915), `pure` (576), `ars-por-accion` (111), `ars@1e0` (73).
- **Validaciones:** el fact no se pierde ni se duplica; doble pasada del parser
  sobre el mismo documento debe dar el mismo conjunto de facts.
- **DoD:** el set de facts del documento es completo y estable frente a
  re-ejecución (idempotencia del parser S03).

#### CONTEXTS
- **Qué es:** el "marco" de un fact en XBRL: la combinación de entidad, período,
  dimensiones, segmento y consolización que califica al valor.
- **Qué hace:** responder "¿a qué período, entidad, segmento y nivel de
  consolidación pertenece este valor?".
- **Detalles que modela:**
  - **período:** instant (un momento) o duration (un lapso).
  - **fecha:** `start`/`end` (duration) o `instant` (snapshot).
  - **dimensiones:** ejes extra (segmento, moneda de reporte, etc.).
  - **entidad:** el emisor que reporta.
  - **segmento / consolidación:** p. ej. "MetroGas Distribution" vs. consolidado
    (en METR el perímetro INDIVIDUAL es el segmento).
- **Entrada:** del documento XBRL (`<context>`).
- **Salida:** filas de contexto vinculadas a los facts.
- **Validaciones:** las fechas del contexto son consistentes (start ≤ end); el
  contexto citado por cada fact existe.
- **DoD:** cada fact apunta a un contexto resuelto y completo.

#### UNITS
- **Qué es:** la descripción de la unidad de medida del fact.
- **Qué hace:** definir cómo es el número: moneda (USD, ARS), acciones, `pure`,
  o unit-by-unit con escala (`ars@1e6` = millones de ARS).
- **Entrada:** declaración de unidad del documento.
- **Salida:** referencia de unidad en cada fact.
- **Validaciones:** codificar unidades conocidas; las desconocidas se marcan para
  auditoría (no se cuelan en los cálculos).
- **DoD:** la unidad de todo fact está identificable y su escala es recuperable.

#### QNAME
- **Qué es:** el nombre cualificado del concepto (prefijo + nombre) contra una
  taxonomía (p. ej. `us-gaap:Revenues`).
- **Qué hace:** relacionar el concepto con la taxonomía de origen: "este fact es
  el concepto X de la taxonomía Y de la fuente Z".
- **Entrada:** del documento (el `concept` del fact).
- **Salida:** fact etiquetado con su qname y, cuando existe, con su mapeo a la
  taxonomía común.
- **Validaciones:** el qname pertenece a una taxonomía conocida; los conceptos sin
  reconocer se listan (conteo por filing).
- **DoD:** cada fact tiene su qname resuelto y a qué taxonomía pertenece.

### Dependencias
Depende de RAW (documento íntegro) y, para CNV, de IDENTIDAD (a quién pertenece el
documento). No depende de NORMALIZED: el parser no normaliza.

### Errores y edge cases
- **CXBRL vs CNV HTML:** en CNV no hay qname/unit declarados: el parser arma
  unidades y períodos con la lectura de las plantillas (más riesgo; los conteos de
  unidades CNV mostrados arriba son evidencia de que la lectura funciona pero con
  ruido).
- **Duplicados de parsing:** el mismo filing parseado dos veces no debe duplicar
  facts (idempotencia). [HOY: en SEC la reglamentación es re-parsear por
  `run_id`/`snapshot`; "Paso 2 · S03 idempotencia" en la Parte IV.]
- **`is_custom` [HOY]:** bug P0 que contamina la distinción entre conceptos
  estándar y extensiones de la empresa (Parte IV §3).
- **Contexts duplicados** dentro del mismo XBRL (ocurre en filings mal armados).

### Definition of Done de la capa
El documento fue correctamente parseado cuando: **todos los facts extraídos por
taxonomía y por filing coinciden con el documento RAW (re-parsear da el mismo
resultado), cada fact tiene su contexto y unidad resueltos, y no hay descartes
silenciosos.**

### ¿Qué habilita la siguiente capa?
Le da a NORMALIZED los **datos extraídos** con su significado técnico: unidades,
períodos, qnames — todavía no comparables entre empresas ni entre fuentes.

---

## 5. NORMALIZED

### Objetivo
Convertir los datos extraídos en **información técnicamente comparable**: mismas
unidades, mismas monedas, mismos períodos, mismo perímetro.

### ¿Qué es?
El puente entre la sintaxis (PARSED) y el sentido común (ECONOMIC FACTS). Toma el
`parsed.facts` y produce `normalized.facts` con reglas uniformes: escala, moneda,
período y perímetro.

### ¿Qué problema resuelve?
El problema de la **comparabilidad**: la Revenue de YPF viene en millones de USD,
la de METROGAS en miles/ARS; un período puede ser FY, Q o YTD; un número puede ser
instant o duration. Si no se normaliza, ningún ratio ni ninguna comparación tiene
sentido.

### ¿Cómo funciona?
Mapeo de cada fact a un "vehículo" normalizado:
- **Escala y unidad** al estándar del modelo (p. ej. millones de la moneda base).
- **Moneda** a la moneda canónica de la entidad (ARS para CNV, USD para SEC) con
  `fx.rate` para lo que cruza.
- **Período** a un intervalo canónico (año fiscal de la entidad, trimestre, YTD).
- **Perímetro** a individual/consolidado declarado explícitamente.

### Flujo interno
```
parsed.facts → resolver unidad/escala → convertir moneda (fx) → mapear período → fijar perímetro → normalized.facts
```

### Objetos / subetapas

#### UNIDADES / ESCALAS
- **Qué es:** llevar todo número a una unidad de referencia clara.
- **Qué hace:** despejar la escala reportada (`ars@1e6` → millones), evitar
  mezclar millones con unidades.
- **Entrada:** unidad y escala declaradas (o inferidas en CNV).
- **Salida:** todo fact con unidad/divisor explícito en el modelo.
- **Validaciones:** conversión reversible (se puede volver al valor original);
  conteos de unidades por fuente (los 1.120 `ars@1e6` de METR no pueden sumarse a
  las 915 `ars@1e3` sin convertir).
- **DoD:** ningún cálculo posterior depende de una escala "de memoria".

#### MONEDA
- **Qué es:** uniformar la moneda de reporte.
- **Qué hace:** los facts en moneda extranjera se convierten a la moneda canónica
  con tipo de cambio de la fecha correspondiente.
- **Entrada:** fact + `fx.rate` con fecha.
- **Salida:** valor en moneda canónica, con el tipo de cambio usado registrado.
- **Validaciones:** el fx está dentro de un rango razonable (control de outliers);
  nunca convertir "en seco" un número sin su fecha.
- **DoD:** todo fact monetario tiene moneda canónica y fx identificado.

#### PERÍODO
- **Qué es:** interpretar y estandarizar el marco temporal.
- **Qué hace:** clasificar cada fact como **instant** o **duration** y mapear su
  fecha al ejercicio fiscal de la entidad (año, trimestre, YTD).
- **Entrada:** contexto del fact (fechas, instant/duration).
- **Salida:** período canónico *(end, duration?, FY/Q/YTD)*.
- **Validaciones:** fechas reales (no futuras), duration = start..end coherente,
  alineación con el ejercicio fiscal declarado.
- **DoD:** no hay fact sin período canónico resuelto.

#### PERÍMETRO
- **Qué es:** fijar si el número es de la entidad individual o del consolidado.
- **Qué hace:** evitar sumar peras con manzanas (individual METROGAS vs. completo).
- **Entrada:** contexto/segmento.
- **Salida:** perímetro explícito en cada fact.
- **Validaciones:** coherencia con el registro de identidad del emisor.
- **DoD:** el perímetro de cada fact está explícito y correcto.

### Dependencias
Depende de PARSED (datos extraídos), de IDENTIDAD (cuyo perímetro) y de MARKET/FX
(para conversión de moneda de la fuente).

### Errores y edge cases
- **Escalas mezcladas** dentro de un mismo filing (METR cambia `ars@1e6` a `ars@1e3`
  entre formularios): la normalización debe ser **por filing/contexto**, no
  global.
- **Instant vs duration**: un número "tipo balance" (stock) no es comparable con
  uno "tipo flujo" (flow) sin la etiqueta correcta.
- **YTD vs trimestral**: sumar Q1+Q2+Q3 mientras el filing reporta YTD Q3 es
  doble conteo.
- **Cambios de moneda de reporte** en el historial de la empresa.

### Diferencia PARSED vs NORMALIZED (regla de oro)
PARSED responde **"qué dice el documento"**; NORMALIZED responde **"cómo lo decimos
todos juntos"**. El parser jamás cambia un número; el normalizador sí (escala,
moneda) pero SIEMPRE registrando la transformación. **No se deben mezclar**: si el
parser normaliza, se pierde la evidencia del valor original; si el normalizador
parsea, se rompe la comparabilidad de los cálculos.

### Definition of Done de la capa
Un dato está suficientemente normalizado cuando: **está expresado en la unidad,
moneda, período y perímetro canónicos del modelo, su transformación es reversible
y registrada, y es directamente comparable con otro dato normalizado de otra
empresa/fuente.**

### ¿Qué habilita la siguiente capa?
Le da a ECONOMIC FACTS los **datos comparables**: el dato puede ahora pasar a
significar algo económico sin ambigüedades de escala/time.

---

## 6. ECONOMIC FACTS

### Objetivo
Representar el **hecho económico**, independientemente de cómo aparezca en el
documento técnico.

### ¿Qué es?
La capa que responde la pregunta del negocio: **"¿qué pasó, económicamente?"**. Un
hecho económico es un dato con identidad económica canónica (`econ_key`), fecha
económica (`measurement_date`), entidad, período y perímetro — derivado de uno o
más facts técnicos.

### ¿Qué problema resuelve?
El **mismo número, miles de formas**: un mismo concepto aparece en US-GAAP, en
IFRS, en distintos filings, con distintos qnames, re-expresados por inflación (IAS
29), con segmentos distintos. Sin una identidad económica canónica, el sistema no
puede juntarlos sin duplicar ni explicarlos sin contradicciones. `economic_facts` y
las migraciones `034/035/036` (`economic_facts`, `measurement_date`, `econ_key`)
son el corazón de esta capa (hoy en el worktree, D-1).

### ¿Cómo funciona?
Dos claves + una fecha:

### Flujo interno
```
normalized.facts → resolver conceptos → asignar econ_key → fijar measurement_date → deduplicar → economic_facts
```

### Objetos / subetapas

#### FACT KEY
- **Qué es:** la **identidad de la ocurrencia documental**: *"este fact, de este
  filing, de esta empresa, este contexto"*.
- **Qué hace:** ser el eslabón fino con PARSED: qué línea exacta del documento
  original originó el hecho.
- **Entrada:** el par (filing, fact) del parsing.
- **Salida:** un identificador estable para auditoría fina.
- **DoD:** dado un fact_key, se puede volver al documento y al valor original.

#### ECON KEY
- **Qué es:** la **identidad económica normalizada** del concepto: el "concepto
  canónico" del modelo (p. ej. `revenue_consolidated_ttm`, `net_income_annual`,
  `equity_instant`), agnóstico de la fuente y del régimen contable.
- **Qué hace:** decir "esto ES Revenue", sin importar si vino de US-GAAP, IFRS o
  CNV.
- **Entrada:** qname + reglas de mapeo (semántica).
- **Salida:** cada fact técnico candidato etiquetado con un `econ_key`.
- **Validaciones:** el mapeo se audita (una regla mal puesta contamina todos los
  ratios de abajo); los conceptos sin mapear quedan en estado "por mapear" y NO
  entran a cálculos.
- **DoD:** el mapeo qname→econ_key está versionado y auditable.

#### MEASUREMENT DATE
- **Qué es:** la **fecha económica** a la que corresponde el hecho (no la fecha de
  envío del documento).
- **Qué hace:** alinear todos los datos: dos filings de períodos distintos no se
  comparan por su fecha de publicación sino por su `measurement_date`.
- **Entrada:** contexto del fact (instant/duration con sus fechas).
- **Salida:** fecha económica canónica (p. ej. cierre de ejercicio).
- **Validaciones:** sin fecha económica, el hecho no entra a series.
- **DoD:** todo `economic_fact` tiene `measurement_date` resuelta.

### Dependencias
Depende de NORMALIZED (dato comparable) y de IDENTIDAD (a qué entidad). También de
las migraciones del worktree (`034–036`).

### Errores y edge cases
- **Misma cosa, varios filings**: duplicado se resuelve por (entidad, `econ_key`,
  `measurement_date`, perímetro, moneda) — y se conserva la lista de facts que lo
  alimentan (provenance).
- **Re-expresados por IAS 29**: los números de períodos comparativos vienen
  reexpresados a moneda de cierre (factor 1.3155 en METR FY2025). El `econ_key` es
  el mismo; la **versión del dato** cambia y se registra.
- **Concepto sin mapear**: se marca, no se inventa.
- **`is_custom` [HOY]** (parte IV): sin corregir, el mapeo está contaminado para
  conceptos de la empresa.

### Definition of Done de la capa
Un fact técnico está correctamente convertido en hecho económico cuando: **existe
un `economic_fact` con `econ_key` canónico, `measurement_date` resuelta, entidad y
perímetro correctos, deduplicado contra equivalentes, y con su `fact_key` de
origen conservado.**

### ¿Qué habilita la siguiente capa?
Le da a FINANCIAL MODEL los **hechos económicos homogéneos** para armar series
(tiempo, TTM, stocks/flows).

---

## 7. FINANCIAL MODEL

### Objetivo
Construir **series financieras coherentes** a partir de los Economic Facts: un
modelo cronológico por entidad donde cada concepto tiene su serie histórica bien
formada (FY, Q, YTD, TTM/LTM, stocks y flows).

### ¿Qué es?
La capa que responde "¿cómo se ve el estado de resultados/balance/flujo de esta
empresa a lo largo del tiempo, con períodos alineados?" — antes de calcular
métricas. Vive en el worktree con Financial Model (`034–036`), pendiente D-1.

### ¿Qué problema resuelve?
El problema del **doble conteo y del desfase de períodos**: los filings reportan
en distintos formatos (alguna YTD acumulada, otra trimestral, otra anual). Sin
series construidas con reglas, TTM y ratios se calculan mal.

### ¿Cómo funciona?

- **FY (fiscal year):** el ejercicio de la entidad (no necesariamente el año
  calendario).
- **Q (quarter):** trimestres del ejercicio.
- **YTD (year-to-date):** acumulado del año a la fecha del documento.
- **TTM / LTM (trailing/last twelve months):** los últimos doce meses, construidos
  combinando el año vigente y el anterior.

### Flujo interno (ejemplo: Revenue TTM)
```
FY Q3 [YTD Q3 reportado] + FY anterior [YTD Q3 anterior] − (si hace falta) → Revenue TTM
```

### Objetos / subetapas

#### FY / QUARTER / YTD
- **Qué es:** los períodos canónicos del modelo.
- **Qué hace:** normalizar a un solo "reloj" por entidad: ejercicio fiscal, sus
  trimestres y los YTD parciales.
- **Cómo funciona:** a partir del `measurement_date` y del identitario fiscal de la
  entidad, cada `economic_fact` ca en su celda (ejercicio, trimestre, periodo).
- **Validaciones:** alineación temporal: Q3 ≤ Q2 ≤ Q1 del mismo ejercicio; YTD(t)
  ≥ YTD(t−1).
- **DoD:** todo fact está en una celda del modelo y las celdas son monótonas.

#### INSTANT / DURATION
- **Qué es:** la naturaleza temporal del número.
- **Qué hace:** mantener separados **stocks** (balances: instantáneo al cierre) de
  **flows** (resultados: acumulan en el período).
  - instant: ejemplo *Equity (Total)* al 31/12.
  - duration: ejemplo *Revenue del trimestre*.
- **Cómo funciona:** los stocks se comparan en el cierre; los flows se suman por
  período. Nunca se mezclan.
- **Validaciones:** un flow nunca se "salda" en un instant y viceversa.
- **DoD:** etiqueta temporal explícita y consistente en toda la serie.

#### TTM / LTM y construcción de series
- **Qué es:** la serie de "últimos doce meses".
- **Qué hace:** dá un nivel anual comparable aun mid-periodos.
- **Cómo funciona (Revenue TTM):**
  1. Tomo Revenue del año vigente hasta el trimestre más reciente (YTD o suma de
     Qs).
  2. Tomo Revenue del año anterior en el mismo tramo.
  3. ⟹ TTM = YTD vigente + (FY anterior − YTD anterior).
  Si la fuente reporta exclusivamente YTD, no hay que sumar Qs (evita doble
  conteo). Si reporta Qs individuales, TTM = Q1+Q2+Q3+Q4 del tramo correspondiente.
- **Validaciones:** identidad de TTM = siempre 12 meses; chequeo contra el periodo
  del cierre anual.
- **DoD:** la serie TTM es continua para todo trimestre con datos.

### Dependencias
Depende de ECONOMIC FACTS (hechos homogéneos) y de IDENTIDAD (ejercicio fiscal de
la entidad, perímetro de cada serie).

### Errores y edge cases
- **Doble conteo YTD:** sumar Q1+Q2+Q3 cuando el filing ya reporta YTD Q3 → la
  regla es "YTD llega como YTD": dado que venga, se usa directo.
- **Cambio de ejercicio fiscal** (la entidad cambia su cierre): versionar las
  series y no mezclar.
- **Períodos no calendario:** el TTM se calcula sobre el ejercicio fiscal, no el
  año de enero.
- **Datos faltantes en el medio (filing perdido):** la serie debe señalar el hueco
  (`GAP`) y no "inventar" el trimestre.
- **Individual vs consolidado:** no combinar en una misma serie el perímetro
  INDIVIDUAL (segmento) con el consolidado.

### Definition of Done de la capa
El Financial Model está suficientemente construido cuando: **para cada entidad y
econ_key existe una serie homogénea (FY/Q/YTD, instant/duration, perímetro
consistente) con TTM/LTM derivables sin doble conteo y con huecos señalan.**

### ¿Qué habilita la siguiente capa?
Le da a RATIOS **series listas**: el ratio ya no piensa "de qué período", solo
"con qué fórmula".

---

## 8. RATIOS

### Objetivo
Transformar series financieras en **métricas analíticas** (ratios) matemática y
económicamente válidas.

### ¿Qué es?
La capa que define los **contratos de cálculo**: cada ratio es una especificación
formal (fórmula, inputs, frecuencia, unidad, validaciones) que se ejecuta contra el
Financial Model. Persistencia: `derived.ratio` (con `ratio_id`, `value`, `status`,
`metadata` e `inputs`).

### ¿Qué problema resuelve?
Convertir los datos en **respuestas**: "¿está cara o barata? ¿qué tan rentable?"
sin que cada análisis reinvente la fórmula. Además, centraliza el tratamiento de
los casos límite.

### ¿Cómo funciona?
```
series del Financial Model + inputs de Market → contrato de cálculo (ratio_defs) → ejecución → derived.ratio (value, status, metadata)
```

### Objetos / subetapas

#### P/E / EPS
- **Fórmula:** P/E = Price ÷ EPS; EPS = NetIncome de los últimos 12 meses ÷
  Shares (promedio o de cierre, según definición).
- **Inputs:** Price (Market, en ARS/USD según convención), Net Income (econ_key de
  la serie), Shares.
- **Período/Unidad:** TTM/instant; EPS en la moneda del precio.
- **Dependencias:** Market + Financial Model.
- **Bordes:** EPS = 0 → `NOT_CALCULABLE`; EPS negativo → se publica (P/E negativo
  significa pérdida, no error) con metadata; denominador inválido → `NOT_CALCULABLE`.

#### P/B / P/S
- P/B = Price ÷ Book value per share (Equity ÷ Shares, instant).
- P/S = Price ÷ Sales per share (Revenue TTM ÷ Shares).
- **Lógica idéntica** al P/E.

#### ROE / ROA
- ROE = Net Income ÷ Average Equity (o Equity de cierre, según contrato).
- ROA = Net Income ÷ Average Assets.
- **Bordes:** Equity/Assets = 0 o negativos → `NOT_CALCULABLE` o flag; los ratios
  negativos (patrimonio negativo) se marcan como anomalía.

#### LIQUIDEZ / DEUDA
- Current Ratio = Current Assets ÷ Current Liabilities; Deuda/Patrimonio,
  Cobertura de intereses = EBIT ÷ Intereses.
- **Bordes:** denominador cero → `NOT_CALCULABLE`; pasivos muy grandes se
  mantienen con su valor.

#### EV / EBITDA
- **Fórmula:** EV = Market Cap + Deuda total − Caja; EV/EBITDA.
- **Inputs:** Market Cap (Market), Deuda neta (Financial Model), EBITDA (serie).
- **Bordes:** EBITDA = 0 o negativo → `NOT_CALCULABLE`/flag.

### Diferencia clave
- **dato financiero** = el hecho (Revenue, Equity).
- **métrica calculada** = el resultado del contrato (P/E = 12,4).
- **ratio** = la métrica **más su metadata** (fórmula/versión, inputs, período,
  unidad, status): el ratio es self-describing.

### Dependencias
Depende de FINANCIAL MODEL (series) y de MARKET (precios, acciones). Depende de
que la normalización de unidades/monedas sea correcta: un P/E con precio en ARS y
EPS en USD es un error de unidades.

### Errores y edge cases
- **Falta de inputs:** la regla es `NOT_CALCULABLE`, nunca un 0 fabricado ni un
  promedio "a ojo". [En la homologación TIKR, 43,4% de las métricas quedaron
  `CATALAXIA_MISSING_INPUT`: falta insumo, no calidad.]
- **Cero como producto válido** (renta cero) vs. **cero como denom suspenso**:
  dos tratamientos distintos.
- **Negativos:** se publican con status (p. ej. P/E negativo), salvo que el
  contrato diga lo contrario.
- **[HOY]** `derived.ratio` tiene 36 filas / 9 emisores sobre 584 instrumentos;
  solo 4 métricas canónicas persisten (`eps`, `pe`, `pb`, `ev_sales`); las 14
  contables no se persisten todavía (`SG-03`).

### Definition of Done de la capa
Un ratio es válido cuando: **el contrato (fórmula, inputs, período, unidad) está
definido y versionado, se ejecutó contra el modelo y Market, el resultado respetó
las reglas de bordes, y `derived.ratio` quedó con `value`, `status` y `metadata`
(incluidos los inputs usados).** Probar siempre con casos de referencia (YPF, KO,
METR).

### ¿Qué habilita la siguiente capa?
Le da a PROVENANCE el **extremo final del rastro** y a VALIDACIÓN el objeto que
auditar.

---

## 9. PROVENANCE

### Objetivo
Permitir **reconstruir el origen completo de cualquier número publicado**, en un
solo "¿de dónde salió?"

### ¿Qué es?
La cadena de linaje que enlaza cada salida con su origen:

```
RATIO → FORMULA → INPUT → FACT → FILING / RAW → SHA256
```

También los metadatos de transformación (reglas aplicadas, versión de la regla,
fecha). Existe como capa real (Parte X · `06_PROVENANCE.md`), con límites
conocidos.

### ¿Qué problema resuelve?
La **auditabilidad**: para Catalaxia, la confianza es el producto. Un número sin
origen no es un número: es una opinión.

### ¿Cómo funciona?
Cada etapa persistente apunta al origen de la anterior por id y versión:
- `derived.ratio` guarda `ratio_id`, `value`, `status`, `metadata` e **`inputs`
  (identificadores de los facts/series)**.
- Los inputs apuntan a `economic_facts` (o `normalized.facts` donde no hay
  economy), con su `fact_key`.
- El `fact_key` apunta al filing/documento; el documento apunta al RAW y su hash.

### Flujo interno
```
derived.ratio.inputs → economic_facts.fact_key → parsed.facts.metadata (filing) → RAW (hash) + reglas/versión de cada transformación
```

### Objetos / subetapas

#### RATIO (el extremo)
- Qué es: el número publicado con su identidad y status.
- Qué hace: exponer el punto de partida del rastro.

#### FÓRMULA / CONTRATO (versión)
- Qué es: la especificación del cálculo (con su versión).
- Qué hace: responder "¿con qué regla se calculó este número?" (ratio_defs
  versionado).

#### INPUT
- Qué es: cada serie/fact que alimentó el cálculo.
- Qué hace: dar el valor crudo y su identidad.

#### FACT / FILING / RAW / SHA256
- Qué es: el eslabón documental.
- Qué hace: llevar hasta el archivo original con su huella de integridad.

### Dependencias
Depende de todas las capas anteriores: sin fact_key bien armado ni filing con
hash, el rastro se corta. **[HOY:** en CNV el tramo legacy no tiene ledger ni
`hash_cnv` (`SG-02`), y `9 de 7.998` entidades tienen hechos en engine (`L-16`) —
la trazabilidad completa solo existe donde la identidad y el hash existen.]

### Errores y edge cases
- Rastros que se cortan: se exponen como "sin origen" y **no se publican como
  trazables**.
- Cambio de reglas: el "contaminado" versionado es obligatorio (si la fórmula de
  un ratio cambia, los números viejos deben saber bajo qué versión se hicieron).
- Re-procesos: la cadena debe apuntar al re-run exacto (`run_id`), no al
  "última vez que corrió todo".

### Definition of Done de la capa
Un dato es completamente trazable cuando, dado su id publicado, **se puede
recorrer ratio → fórmula → inputs → facts → filing → RAW → hash → versión de cada
transformación sin cortes, y cada paso está documentado con su versión y su
`run_id`.**

### ¿Qué habilita la siguiente capa?
Le da a VALIDACIÓN **el material que validar** (lineage consistente) y a
CERTIFICACIÓN **la evidencia** para decidir PASS/BLOCK.

---

## 10. VALIDACIÓN

### Objetivo
**Demostrar** que el sistema produjo datos coherentes (no solo que "corrió").

### ¿Qué es?
El conjunto de checks técnicos, estructurales, financieros, matemáticos y de
negocio que comparan lo esperado contra lo publicado. Produce evidencia; no decide
estados (eso lo hace CERTIFICACIÓN).

### ¿Qué problema resuelve?
El riesgo de que un dato **parezca** correcto y no lo sea (doble conteo, unidades
cruzadas, huecos temporales, rastros rotos).

### ¿Cómo funciona?

- **COMPLETITUD:** expected → published. Para cada celda del modelo (entidad,
  período, concepto) comparo qué debía existir frente a qué existe; los faltantes
  se listan.
- **UNIDADES:** consistencia de unidades en cada cálculo (P/E con precio y EPS en
  la misma moneda), y entre períodos de una misma serie.
- **PERÍODOS:** alineación temporal: no mezclar Q con FY, YTD con TTM, instant con
  duration en el mismo análisis.
- **PROVENANCE:** el character existe y es consistente (no hay fact_key sin
  filing, no hay ratio sin inputs).
- **IDEMPOTENCIA:** **re-ejecutar el procesamiento no debe cambiar los
  resultados** (ni duplicar). Medible corriendo dos veces y comparando.

### Flujo interno
```
dataset esperado (modelo) vs dataset publicado → ejecutar checks → reporte de validación (evidencia)
```

### Objetos / subetapas
- **Checks técnicos** (tipos, nulos, encodings) — los más baratos.
- **Estructurales** (claves, filas por filing, esquema).
- **Financieros** (sumas de sub-partidas = totales, coherencia de partidas).
- **Matemáticos** (unidades/equivalencias, porcentajes dentro de rango).
- **De negocio** (perímetro, contabilidad de la entidad, homologación externa
  p. ej. TIKR).

### Dependencias
Depende de PROVENANCE (para auditar el rastro) y del modelo esperado (definido por
los contratos). Depende de que las corridas sean rastreables (`run_id`).

### Errores y edge cases
- **Falsa completitud:** llenar huecos con inventos "para pasar el check": se
  prohibe explícitamente.
- **F-038 [HOY]:** 3 tests pre-existentes fallan; se conocen, se declaran y no se
  esconden.
- **Idempotencia no garantizada:** [HOY] S00/S02 y el `is_custom` (P0) aún no
  garantizan re-ejecución sin duplicados (Parte XI).
- **Homologación externa como oracle:** TIKR es referencia, no verdad absoluta;
  las diferencias se explican (definición, perímetro, inputs).

### Definition of Done de la capa
Un dataset pasó VALIDACIÓN cuando: **todos los checks de la batería pasaron o sus
excepciones están listadas y justificadas, la completitud está calculada sobre el
modelo esperado, las unidades/períodos/provenance están coherentes y la
re-ejecución no produce cambios (idempotencia verificada).**

### ¿Qué habilita la siguiente capa?
Le da a CERTIFICACIÓN **la evidencia** (sin validación no hay certificación
posible).

---

## 11. CERTIFICACIÓN

### Objetivo
Decidir, con la evidencia de VALIDACIÓN, si la información puede pasar a
publicación — y registrarlo.

### ¿Qué es?
La capa que **consume** validación y emite un **estado** por dato/dataset:
`PASS`, `PASS_WITH_WARNINGS`, `BLOCKED`. Es el "último portero".

### ¿Qué problema resuelve?
Que la decisión de publicar sea **objetiva y rastreable**, no la opinión del día.

### ¿Cómo funciona?
Reglas de gates (el engine ya tiene estados y gates `PASS / WARNING / BLOCK`).
El certificador aplica las reglas a la evidencia de validación y escribe el
resultado de certificación con su `run_id`.

### Flujo interno
```
evidencia de VALIDACIÓN → reglas de gate → estado (PASS / PASS_WITH_WARNINGS / BLOCKED) → registro de certificación
```

### Objetos / subetapas

#### PASS
- **Qué es:** todas las validaciones superadas sin advertencias relevantes.
- **Qué produce:** autorización plena.

#### PASS_WITH_WARNINGS
- **Qué es:** hay advertencias conocidas y explicadas que no invalidan el dato.
- **Qué produce:** publicación permitida con las advertencias **visibles y
  guardadas**.

#### BLOCKED
- **Qué es:** hay un error o inconsistencia bloqueante.
- **Qué produce:** prohibición de publicar hasta corregir y reprocesar.

### Diferencia warning vs error
- **Warning (advertencia):** se conoce, se explica, no rompe la coherencia (una
  revisión manual dice "ok, es esperable").
- **Error:** rompe la producción del dato: no se publica hasta que se re-procesa.

### ¿Quién determina? / ¿cómo queda registrado?
- Determinan las **reglas del gate** (no una persona: el resultado es reproducible
  con el mismo insumo).
- Queda en el **registro de certificación** (tabla/ledger con `run_id`, estado,
  versión de reglas y evidencia adjunta).

### Matriz de certificación

| Estado | Significado | ¿Publicable? | Acción |
|---|---|---|---|
| **PASS** | Todas las validaciones superadas, sin advertencias | Sí, sin restricción | Publicar + registrar evidencia |
| **PASS WITH WARNINGS** | Validaciones con advertencias conocidas y explicadas | Sí, con advertencias visibles | Publicar marcado; revisar advertencias |
| **BLOCKED** | Error o inconsistencia bloqueante | No | Corregir, reprocesar, re-certificar |

### Dependencias
Depende de VALIDACIÓN (evidencia) y de que existan las **certificaciones
pendientes**: C-1 (entorno desde cero), C-2 (Economic Facts/Financial Model), C-3
(KO), C-4 (tramo C CNV/homologación), C-5 (idempotencia job5), C-6 (Market E2E).
[HOY: no existe un *gate agregado* que certifique un dataset completo de una vez
(`L-4`).]

### Errores y edge cases
- **Warning repetido** que se normaliza: no grite; se documenta y se deja de
  marcar como excepción.
- **Certificación sin evidencia:** prohibido (no hay certificación por confianza).
- **Dato viejísimo que se certifica con reglas nuevas:** se certifica bajo la
  versión de reglas de su corrida.

### Definition of Done de la capa
Una información puede pasar oficialmente a publicación cuando: **existe un estado
de certificación objetivamente derivado de la evidencia de validación, con reglas
versionadas, y registrado con su `run_id`.** Si es `BLOCKED`, la publicación está
prohibida.

### ¿Qué habilita la siguiente capa?
Le da a PUBLICACIÓN **el permiso**: el pub solo acepta datos con certificación
válida.

---

## 12. PUBLICACIÓN

### Objetivo
Exponer **únicamente** información que atravesó correctamente las capas
anteriores y está certificada.

### ¿Qué es?
La capa de salida: los habilitadores para que el usuario final consulte, filtre y
reciba los datos: DATABASE (PostgreSQL y/o `screener.db`), API, SCREENER
(dashboard) y REPORTES (Excel/PDF).

### ¿Qué problema resuelve?
El **desacople consumo vs. producción**: el usuario que consulta no puede
depender nunca de re-correr el ETL ni de re-leer las fuentes. PUBLICACIÓN sirve
datos ya certificados.

### ¿Cómo funciona?
Creación de **vistas/dataset de publicación** (solo datos PASS /
PASS_WITH_WARNINGS), con la trazabilidad adjunta. El screener consulta esas
vistas; los reportes salen de ellas.

### Flujo interno
```
datos certificados → dataset de publicación → API/screener/reportes (con provenance accesible)
```

### Objetos / subetapas

#### DATABASE
- **Qué es:** la fuente de verdad de publicación (tablas `derived.ratio`,
  vistas, `market_*`, `economic_facts`, `financial_model` en producción).
- **Qué hace:** persistir únicamente datos certificados y sus metadatos.
- **Validaciones:** no se inyecta a producción nada sin certificación.

#### API
- **Qué es:** la capa de servicio (contrato REST, p. ej. FastAPI).
- **Qué hace:** exponer los datos por contrato (entidad, período, métrica) con
  metadata de trazabilidad, control de acceso y versionado.
- **Validaciones / DoD:** cada respuesta lleva su provenance accesible.

#### SCREENER
- **Qué es:** el dashboard del usuario final (el encargo del cliente:
  "implementación de dashboard para Catalaxia").
- **Qué hace:** consultar el API/vistas para filtrar por entidad, calidad,
  ratios, series; mostrar el estado (PASS/BLOCK) y la trazabilidad de cada dato.
- **DoD:** para cada número mostrado, existe un "ver origen".

#### REPORTES
- **Qué es:** exportaciones Excel/PDF.
- **Qué hace:** materializar cortes del dataset de publicación con su metadata.
- **DoD:** cada reporte incluye origen y versión de los datos.

### ¿Por qué PUBLICACIÓN debe estar desacoplada de las fuentes?
Porque el **dispendio de publicación puede servir, comparar y certificar** sin
tocar nunca el pipeline. Si la publicación re-lee la fuente, una caída de la SEC
rompe el dashboard y se pierde la separación "dato publicado vs. dato nuevo".
Regla operativa: **el pub nunca escribe en las tablas de ingesta y nunca se corre
como pipeline de fuentes** (regla N-2 / la regla de los 374).

### Dependencias
Depende de CERTIFICACIÓN (permiso), de PROVENANCE (trazabilidad mostrable) y de
las capas de presentación (API/dashboard) que en general están EN DESARROLLO.

### Errores y edge cases
- **Publicar data sin certificar** (hoy hay datos CNV publicados por el tramo
  legacy sin ledger ni certificación: son `KNOWN_LIMITATION`, ver Parte XVII).
- **Versionado del pub:** cuando cambia la regla, el pub sirve la versión nueva
  con su metadata, no "borra" la anterior.
- **Reportes con "unidades de memoria":** los reportes deben llevar la unidad
  explícita del dato (reusa la metadata de NORMALIZED).

### Definition of Done de la capa
Un dato está oficialmente disponible para el usuario final cuando: **está en el
dataset de publicación, con estado certificado (PASS o PASS_WITH_WARNINGS), días
accesible por API/screener/reporte Y su trazabilidad completa es consultable sin
re-correr nada.**

### ¿Qué habilita la siguiente capa?
No hay capa siguiente: PUBLICACIÓN es el borde. Habilita el **negocio** (decisiones
del inversor/analista) y el **feedback** que vuelve a FUENTES (nuevos datos,
errores detectados, recálculos).

---

## DIFERENCIAS CRÍTICAS ENTRE CAPAS

1. **FUENTES vs RAW:** FUENTES *obtiene* y descubre documentos; RAW *preserva*
   los bytes descargados. La fuente está afuera; el RAW está adentro y es
   inmutable. Fuente sin RAW = se perdió la evidencia.
2. **RAW vs PARSED:** RAW es *el documento*; PARSED es *la extracción
   estructurada* del documento. Un fact nunca reemplaza al archivo: señala hacia
   él.
3. **PARSED vs NORMALIZED:** PARSED respeta el valor reportado (unidades,
   períodos tal cual); NORMALIZED **adapta** el valor a unidades/moneda/período
   canónicos, **registrando el cambio**. Jamás se mezclan responsabilidades.
4. **NORMALIZED vs ECONOMIC FACTS:** NORMALIZED hace el dato *comparable*;
   ECONOMIC FACTS le da *identidad económica canónica* (`econ_key`) y resuelve el
   mismo concepto entre fuentes. NORMALIZED es sintaxis uniforme; ECON es
   semántica de negocio.
5. **FACT KEY vs ECON KEY:** FACT KEY identifica la *ocurrencia documental* (este
   fact de este filing); ECON KEY identifica el *concepto económico* (Revenue).
   Un ECON KEY puede agrupar muchos FACT KEYs; un FACT KEY pertenece a un solo
   documento.
6. **ECONOMIC FACTS vs FINANCIAL MODEL:** ECON define *hechos individuales
   homogéneos*; FINANCIAL MODEL arma *series temporales* (FY/Q/YTD/TTM,
   stocks/flows). Un hecho es una foto; el modelo es la película.
7. **FINANCIAL MODEL vs RATIOS:** el modelo produce *la serie*; RATIOS la *usa
   con un contrato*. El modelo no calcula métricas; los ratios no arman series.
8. **VALIDACIÓN vs CERTIFICACIÓN:** VALIDACIÓN *produce evidencia* (checks);
   CERTIFICACIÓN *decide el estado* (PASS/WARN/BLOCK) con esa evidencia. La
   validación nunca etiqueta; la certificación nunca inventa checks.
9. **PROVENANCE vs VALIDACIÓN:** PROVENANCE *registra el origen* de cada dato;
   VALIDACIÓN *verifica* que esos registros sean coherentes y completos. Uno
   construye el rastro; el otro lo audita.
10. **CERTIFICACIÓN vs PUBLICACIÓN:** CERTIFICACIÓN *autoriza*; PUBLICACIÓN
    *sirve*. Un dato certificado puede no publicarse nunca; un dato publicado sin
    certificación es un incidente.

---

## ROADMAP DE IMPLEMENTACIÓN

### Principios del roadmap
- **Vertical slices, no capas globales:** se construye UN recorrido completo y
  funcional (empresa→número publicado) antes de ensanchar.
- **MVP = un número certificado y publicado** de un piloto.
- **Quick wins:** idempotencia de las etapas (S00/S02, `is_custom`), `hash_cnv`
  para CNV, persistencia de los 14 ratios contables, certificación KO.
- **Bloqueantes de todo:** IDENTIDAD + RAW con hash + parsers estables. Sin eso,
  nada de abajo es auditable.

### FASE 1 — Fundación
- Existir primero: **IDENTIDAD** (entity_id + CIK/CUIT), **RAW** con SHA256 p/hoy
  también CNV (`hash_cnv`), **PARSED** estable e idempotente (S03; fix `is_custom`
  P0), **NORMALIZED** básico.
- Orden lógico: identidad → RAW → parser de la fuente de referencia (SEC) →
  normalizador.
- Criterio de salida: un filing YPF se parsea y normaliza de forma estable,
  re-ejecutable e idéntica.

### FASE 2 — Primer pipeline completo
- Construir el recorrido mínimo de un dato: **FUENTE (SEC/YPF) → RAW → PARSED →
  NORMALIZED → ECONOMIC FACTS → FINANCIAL MODEL → VALIDACIÓN → PUBLICACIÓN** con un
  solo ratio (P/E de YPF o KO).
- Incluye resolver D-1 (merge del worktree para ECON/FINMODEL o bucket equivalente).
- Criterio de salida: **un número certificado, publicado y trazable de punta a
  punta,** reproducible con un comando.

### FASE 3 — Escalabilidad
- Más empresas, más filings, más períodos, más fuentes (integrar CNV tramo C
  canónico), más ratios (persistir las 14 contables; contratos nuevos).
- Automatizar la normalización de unidades/periodos para no hacerla a mano por
  filing; alinear homologación TIKR (subir coincidencia de inputs).

### FASE 4 — Certificación y Provenance avanzada
- Completar registro de linaje por `run_id`, versionado de reglas, gates agregados
  (C-2…C-6), matrices de validación por capa y el "gate agregado" (L-4).

### FASE 5 — Producción
- Automatización (jobs programados con reanudación), monitoreo/observabilidad
  (logs, métricas, alertas), recuperación ante errores y reprocessing, versionado
  de todo el pipeline, performance (volúmenes Market/CNV) y seguridad (accesos,
  permisos por entorno 5432/5433 + guard EXT-010).

---

## MATRIZ DE MADUREZ

| Capa | Objetivo | Entrada | Salida | Dependencias | Complejidad | Criterio de terminado | Estado |
|---|---|---|---|---|---|---|---|
| 1 FUENTES | Obtener evidencia original | proveedores | documentos + metadato | — | Alta (3 fuentes) | todo el universo descargado con hash y sin descartes silenciosos | FUNCIONAL (parcial: tramo C CNV y `hash_cnv`) |
| 2 IDENTIDAD | Saber a qué entidad/instrumento pertenece todo | CIK/CUIT/tickers | entity_id canónico | FUENTES | Media | entity_id único y vinculado por instrumento, sin duplicados | FUNCIONAL (parcial: `SG-10`, L-16) |
| 3 RAW | Preservar evidencia íntegra | download | archivo + SHA256 | FUENTES, IDENTIDAD | Baja | hash registrado y verificable para todo documento | FUNCIONAL (SEC) / A DETERMINAR (CNV `SG-02`) |
| 4 PARSED | Estructurar documentos | RAW | facts+context+units | RAW | Alta | re-parsear = mismo resultado | VALIDADO (SEC) / EN DESARROLLO (CNV) |
| 5 NORMALIZED | Datos comparables | PARSED | normalized.facts | PARSED, IDENTIDAD, MARKET/FX | Alta | unidad/moneda/período/perímetro canónicos verificables | VALIDADO (SEC) / EN DESARROLLO (CNV) |
| 6 ECONOMIC FACTS | Hecho económico canónico | NORMALIZED | economic_facts (econ_key, measurement_date) | NORMALIZED | Alta | hechos dedup y mapeados a econ_key | EN DESARROLLO (worktree, D-1) |
| 7 FINANCIAL MODEL | Series coherentes | ECON FACTS | series FY/Q/YTD/TTM | ECON FACTS | Alta | series sin doble conteo y con TTM derivable | EN DESARROLLO (worktree, D-1) |
| 8 RATIOS | Métricas analíticas | FIN MODEL + MARKET | derived.ratio | 7, MARKET | Media | contrato versionado; bordes tratados; status+metadata | FUNCIONAL (parcial: SG-03) |
| 9 PROVENANCE | Reconstruir el origen | todas las capas | rastro ratio→...→hash | 1..8 | Media | cadena íntegra y con versión/run_id | FUNCIONAL (parcial CNV) |
| 10 VALIDACIÓN | Demostrar coherencia | modelo esperado + lodes actual | evidencia (checks) | PROVENANCE | Media | checks + excepciones justificadas + idempotencia | EN DESARROLLO (F-038; P0 abiertos) |
| 11 CERTIFICACIÓN | Decidir estado | evidencia de validación | estado PASS/WARN/BLOCK + registro | VALIDACIÓN | Media | estado objetivo y registrado por reglas | EN DESARROLLO (C-1..C-6, L-4) |
| 12 PUBLICACIÓN | Exponer solo lo certificado | datos certificados | DB/API/screener/reportes | CERTIFICACIÓN, PROVENANCE | Media | dato disponible, trazable y desacoplado | EN DESARROLLO (dashboard en construcción) |

> **Estado:** tomado del estado real medido en el manual; donde no hay evidencia, "A
> determinar". No se afirma nada sin medición.

---

## EJEMPLO END-TO-END

**Coca-Cola (KO) → Revenue → FY2025 → TTM → EBITDA → EV/EBITDA**, paso a paso:

1. **FUENTE** — SEC/EDGAR entrega 10-K de KO (FY2025) y 10-Q (Q1–Q3 2025). Se
   crea: *documento + metadato de ingesta*. Validación: HTTP 200, tamaño, hash.
2. **IDENTIDAD** — el CIK `0000021344` resuelve a KO; se crea/consolida
   `entity_id` de KO. *Salida: identidad de proveedor vinculada.*
3. **RAW** — el 10-K se guarda inmutable con **SHA256**. *Salida: archivo inmutable
   + hash.* Validación: re-hash coincidente.
4. **PARSED** — el parser extrae facts: `us-gaap:Revenues` (context: duration,
   FY2025) en `parsed.facts`, junto a context (instants del balance, durations del
   resultado) y units (USD). *Salida: facts estructurados.* Validación: paridad
   frente a re-parseo.
5. **NORMALIZED** — Revenue FY2025 pasa a unidad canónica y moneda canónica (USD),
   período FY2025, perímetro consolidado. *Salida: `normalized.facts` comparables.*
6. **ECONOMIC FACT** — el fact se mapea a `econ_key = revenue_consolidated` con
   `measurement_date` = cierre FY2025. *Salida: hecho económico dedup.*
7. **FINANCIAL MODEL** — se construye la serie: FY2025, los Q y los YTD. Con YTD
   Q3 2025 y FY2024:
   > **Revenue TTM (Q3 2025) = YTD2025_Q3 + FY2024 − YTD2024_Q3**
   Validación: sin doble conteo, 12 meses exactos.
8. **RATIO** — contrato EV/EBITDA: EV = Market Cap + Deuda total − Caja; EBITDA de
   la serie. *Salida: `derived.ratio` con status + metadata (inputs con id), por
   ej. EV/EBITDA = 18,2.*
9. **PROVENANCE** — el ratio guarda inputs→economic_facts→parsed.facts→filing→RAW→
   hash + versión de fórmula. *El "P/E = 12,4" se puede reconstruir entero.*
10. **VALIDACIÓN** — completitud (las 12 celdas esperadas), unidades (Price en USD
    = EPS en USD), períodos (TTM consistente), provenance (raster íntegro),
    idempotencia (re-correr = mismos valores). *Salida: evidencia.*
11. **CERTIFICACIÓN** — con la evidencia: estado `PASS_WITH_WARNINGS` (si hay
    advertencia explicada) o `PASS`, registrado con `run_id`. *Salida: permiso.*
12. **PUBLICACIÓN** — el dato entra al dataset de publicación; queda en la DB, el
    API lo sirve y el dashboard muestra el número con su "ver origen". *Salida:
    número oficial para el usuario final.*

---

## ARQUITECTURA CONCEPTUAL FINAL

```
 FUENTES ──► IDENTIDAD
    │           │
    ▼           ▼
  RAW ──(hash)──────────────► PROVENANCE (linaje de todo hacia abajo)
  │                              ▲
  ▼                              │
 PARSED (facts+context+units)    │
  ▼                              │
 NORMALIZED (unidades/fx/período/perímetro) │
  ▼                              │
 ECONOMIC FACTS (econ_key+measurement_date) │
  ▼                              │
 FINANCIAL MODEL (series FY/Q/YTD/TTM)      │
  ▼                              │
 RATIOS (contratos → derived.ratio) │
  ▼                              │
 VALIDACIÓN (checks) ──► PROVENANCE (audita el rastro)
  ▼
 CERTIFICACIÓN (PASS / WARN / BLOCK)
  ▼
 PUBLICACIÓN (DB · API · SCREENER · REPORTES)

 EVIDENCIA → DATOS → INFORMACIÓN ECONÓMICA → DECISIONES
```

---

## ORDEN RECOMENDADO DE IMPLEMENTACIÓN (para un dev nuevo)

1. IDENTIDAD (entity_id + CIK/CUIT + instrumentos) — todo depende de "a quién".
2. RAW con SHA256 (incl. `hash_cnv`) — todo se audita contra el original.
3. PARSED estable e idempotente + fix `is_custom` — sin parser no hay nada.
4. NORMALIZED básica — unidad/moneda/período/perímetro.
5. Un **vertical slice** completo: YPF o KO, un solo ratio publicado y trazable.
6. ECONOMIC FACTS + FINANCIAL MODEL (merge del worktree / D-1).
7. VALIDACIÓN + CERTIFICACIÓN del slice.
8. Escalar: CNV tramo C, más empresas/períodos/ratios, homologación TIKR.
9. PUBLICACIÓN (API → dashboard) y luego monitoreo/producción.

---

## QUÉ ES CRÍTICO PARA QUE CATALAXIA SEA CONFIABLE

1. **RAW + hash disciplina total** (reparar `SG-02`). Sin esto, no hay auditoría.
2. **IDENTIDAD sin duplicados** (entity_id canónico) y correcto vínculo de
   instrumentos (`SG-10`).
3. **Separación estricta PARSED vs NORMALIZED** y normalización verificable de
   unidades/moneda/período.
4. **Idempotencia verificada** (re-ejecución = mismo resultado; P0: S00/S02,
   `is_custom`; C-5).
5. **Provenance completa por `run_id` + versionado de reglas**.
6. **Certificación regida por reglas, no por persona** (con registros).
7. **Validación con oráculos externos** (TIKR) explicando diferencias, no
   escondiéndolas.
8. **Publicación desacoplada de fuentes** (el pub nunca re-lee supply).

## QUÉ PUEDE ESPERAR PARA EL MVP

- Ratios **sin** homologación externa completa (TIKR puede esperar al Fase 3).
- Financial Model **solo** las series necesarias para los ratios del MVP.
- Provisiones de treasury: FX manual de pocas pares pre-scale.
- CERTIFICACIÓN con PASSO/warnings básico, sin el gate agregado fino (L-4) — pero
  con el estado registrado.
- Monitoreo inicial mínimo (logs + conteos), sin observabilidad avanzada (llega en
  Fase 5).
- **Lo que NO espera el MVP:** indentidad duplicada, RAW sin hash, parsing no
  idempotente o publikación de datos no certificado.