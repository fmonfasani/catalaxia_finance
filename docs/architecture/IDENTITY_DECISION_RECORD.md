# IDENTITY — DECISION RECORD

Autor: **CIAA** · 2026-08-25 · Ciclo 3
Acompaña a `IDENTITY_ARCHITECTURE_V1.md`
Estado: **PROPUESTO — ninguna decisión aceptada.** El auditor/arquitecto propone; el
propietario del proyecto decide.

---

## Decisiones tomadas en el diseño

Estas están resueltas dentro del contrato porque **no resolverlas haría el diseño
incoherente**. Se registran con su alternativa descartada para que sean revisables.

### D-I-A · La aserción es un objeto de primera clase

**Decisión.** El vínculo entre dos identificadores es una fila en `identity.assertion` con
método, fuente, evidencia, autor y fecha — no un par de columnas.

**Alternativa descartada.** Poblar `identity.entities.cuit`, que es el arreglo mínimo que
cerraría F-011 nominalmente.

**Por qué.** Poblar la columna responde *"¿cuál es el CUIT?"* pero no *"¿quién dijo que es
ese?"*, que es literalmente el criterio de éxito del ciclo. El puente actual —13 filas en
`dim_entity`— falla exactamente por eso: los datos probablemente son correctos y aun así no
son demostrables. Repetir la estructura reproduciría el problema con mejor apariencia.

---

### D-I-B · `entity_key` opaco, no derivado de identificador

**Decisión.** ULID opaco. `CIK:0000904851` se conserva como `LEGACY_ENTITY_ID` durante la
transición.

**Alternativa descartada.** Mantener `CIK:xxx` y agregar `CUIT:xxx` para entidades sin CIK.

**Por qué.** Una clave con semántica hereda los errores de aquello que la nombra. Ya hay
precedente: los 4 conflictos OPEN muestran que un catálogo legacy atribuía a YPF el CIK
`1104659`. Si esa clave hubiera sido primaria, corregirla habría exigido migrar todas las FK.
Además `CIK:xxx` deja sin clave al 88 % del universo CNV. Un esquema mixto
`CIK:xxx`/`CUIT:xxx` empeora el problema: la clave pasaría a depender de qué fuente
descubrió la entidad primero.

---

### D-I-C · El CIK legacy se descarta; el CUIT legacy se conserva como candidato

**Decisión.** Asimetría deliberada por campo.

**Por qué.** No son simétricos en evidencia:

```
CIK legacy    existe una fuente superior (registro SEC) Y el legacy ya falló (4 conflictos)
CUIT legacy   NO existe otra fuente en todo el sistema
```

Descartar el CUIT perdería la única información que lo contiene. Aceptarlo como autoritativo
confiaría en la misma fuente que ya se equivocó con la identidad de YPF. Entra como
candidato `REVIEW_REQUIRED`: se conserva sin afirmarse.

---

### D-I-D · `TICKER` y `YF_SYMBOL` nunca son autoritativos

**Decisión.** Sólo `CIK`, `CUIT`, `ISIN` y `LEI` pueden fundar aserciones `AUTHORITATIVE`.

**Por qué.** Un ticker liberado se reasigna. El pipeline legacy ya sufrió esa colisión
—`COUR` resolvió a Coursera en vez de a la emisora argentina— y el bug estuvo un mes
invisible. El modelo actual **ya lo hace bien** (`TICKER/US=YPF` vs `TICKER/BYMA=YPFD`); v1
lo codifica como regla en vez de dejarlo como práctica.

---

### D-I-E · Un `REJECTED` se persiste

**Decisión.** El rechazo es conocimiento y se guarda con fundamento.

**Por qué.** Sin persistir el rechazo, `C1-R-005` (TGM vs TGNO4/TGSU2) volvería a proponerse
en cada corrida y alguien terminaría aceptándolo por fatiga. Que un match fue evaluado y
descartado es información tan valiosa como el match confirmado.

---

## Decisiones abiertas — requieren al propietario

### D-I-01 · Formato de `entity_key`

| Opción | A favor | En contra |
|---|---|---|
| **ULID** *(sugerida)* | opaco + ordenable temporalmente | menos estándar que UUID |
| UUIDv4 | estándar universal | sin orden; peor para debugging |
| Secuencial con prefijo | legible | acopla al orden de inserción |

**Reversible.** Cualquier identificador opaco satisface el contrato.

---

### D-I-02 · ¿Qué hace autoritativo a un CUIT? — **la decisión de mayor impacto**

| Opción | Consecuencia |
|---|---|
| **Estricta** — sólo constancia AFIP o documento regulatorio | Los 74 CUIT legacy quedan como candidatos indefinidamente. Fase 4 requiere trabajo documental por empresa. Máxima solidez. |
| **Intermedia** — aceptar el CUIT declarado en la portada de EEFF publicados en CNV | Resuelve la mayoría automáticamente. El emisor se auto-declara ante el regulador: es evidencia regulatoria genuina. |
| **Permisiva** — aceptar el CUIT legacy si no hay conflicto | Cierra F-011 rápido. Confía en la fuente que ya falló con YPF. |

**Observación del auditor, sin elegir:** la intermedia tiene una propiedad que la permisiva
no: la evidencia es **citable** (documento, página) y por lo tanto verificable por un tercero.
Es la diferencia entre *"es cierto"* y *"podemos demostrar que es cierto"*, que es la
distinción que todo este diseño intenta preservar.

**Impacto:** define el esfuerzo de la Fase 4 y la fecha en que el bridge SEC↔CNV queda
demostrable.

---

### D-I-03 · ¿Dónde vive Identity? — **acoplada a F-001**

| Opción | Consecuencia |
|---|---|
| Sólo en 5433; Market consume por artefacto explícito | Mantiene el aislamiento. Market necesita un contrato de sincronización. |
| Replicada a 5432 | Habilita joins locales. Duplica la verdad: hay que decidir quién manda. |
| Market migra a 5433 | Solución de fondo. Resuelve F-001 de paso. Mayor esfuerzo. |

**Bloqueante para la Fase 3.** No debería decidirse aisladamente de F-001.

---

### D-I-04 · ¿Incorporar ISIN/LEI como puente de nivel 3?

Un ISIN o LEI compartido entre el registro SEC y el registro argentino permitiría bridges
`AUTO_MATCH` sin intervención humana. Exige incorporar una fuente nueva (GLEIF es pública y
gratuita; ISIN depende de la agencia numeradora).

**Trade-off:** costo de integración contra reducción de la cola manual de la Fase 4.

---

### D-I-05 · ¿Qué se hace aguas abajo con `ACCEPTED_AMBIGUOUS`?

Los grupos como `C1-R-002` (Central Vuelta de Obligado, 3 CUITs observados, ninguno con
perfil propio) son ambigüedad **genuinamente irresoluble** con las fuentes disponibles.

Opciones: publicar marcada · excluir del screener · publicar como grupo con N identificadores.

**No es una decisión de identidad sino de producto**, pero el modelo debe soportar la que se
elija.

---

### D-I-06 · Umbral de `AUTO_MATCH` para reglas derivadas

El sufijo `.BA` de Yahoo es determinista y está documentado. ¿Alcanza para `AUTO_MATCH`, o
toda regla derivada exige confirmación?

**Consideración:** hoy `YF_SYMBOL=YPFD.BA` depende de `TICKER/BYMA=YPFD`, que a su vez es una
confirmación humana con contraste documental **pendiente**. La cadena completa es más débil
que su eslabón más visible — y eso hoy no está registrado en ningún lado. v1 lo hace
explícito mediante provenance derivada.

---

# CICLO 3B — CIERRE DE D-I-02 Y D-I-03

2026-08-25. Ambas se cierran **con recomendación explícita**, fundada en verificación
empírica hecha para este cierre. No se implementó nada.

## Hallazgo que invalida el planteo original de D-I-02

En el ciclo 3 propuse como opción intermedia *"aceptar el CUIT declarado en la portada de
EEFF publicados en CNV"*. **Verifiqué esa hipótesis y es falsa.**

Inspección del RAW de CNV (25 VISOR + EMPRESA_PAGE de CEPU):

```
Únicas propiedades estructuradas con CUIT en el VISOR:
   ODBCUITAuditor         x15    ej: 20-20493014-8
   ODBCUITEstudioAuditor  x15    ej: 30-70818586-4

¿33650305499 (el emisor) como valor de <propiedad>?   NO
```

**CNV no declara estructuralmente el CUIT del emisor.** Los únicos CUIT publicados como campo
son los del **auditor** y su **estudio** — otras entidades. El del emisor aparece en el HTML
sólo porque *nosotros pedimos la página por ese CUIT*: es el parámetro de la request
reflejado en un `<input type="hidden" name="cuit">`.

Usarlo sería **circular**: probaríamos que el CUIT es el CUIT porque lo usamos para buscarlo.
Y hay un riesgo peor: un parser ingenuo que tomara *"el CUIT del documento"* le atribuiría al
emisor **el CUIT de su auditor**.

## Hallazgo que resuelve D-I-02

El **20-F ante la SEC sí declara el CUIT**, en un bloque de identificación estructurado.
Verificado en el RAW de YPF:

```
data/raw/edgar_pilot_ypf/filings/000119312525067155/d866694d20f.htm

   Legal form of the Company: Corporation (sociedad anónima)
   Country of incorporation: Argentina
   Fiscal identification number in Argentina: 30-54668997-9     <- el CUIT
   Commission file number at the SEC: 1-12102
```

- **Autodeclaración del emisor** bajo responsabilidad ante la SEC.
- **Un solo documento atestigua ambos identificadores**: el filing porta el CIK (accession
  `0001193125-25-067155`) y declara el CUIT en su cuerpo. No correlaciona dos fuentes:
  **afirma la equivalencia**.
- **Inmutable, direccionable, citable y mecanizable.**

## La cobertura es completa por necesidad lógica

Los 13 bridges del sistema son **todos `grupo='adr'`**: CRES · LOMA · VIST · TGSU2 · PAMP ·
IRSA · GGAL · SUPV · BBAR · TECO2 · CEPU · YPFD · EDN.

No es coincidencia: una entidad sólo puede tener **ambos** identificadores si es argentina
**y** está registrada en la SEC — *foreign private issuer* — **presenta 20-F**. Los conjuntos
*"necesita bridge"* y *"presenta 20-F"* son el mismo por construcción.

**Corolario:** toda entidad que necesita bridge tiene, por definición, el documento que lo
demuestra. No hay cola manual irreducible.

---

# D-I-02 · CUIT AUTHORITATIVE EVIDENCE

## 1 · Alternativas

| | Alternativa | Fuente |
|---|---|---|
| **A** | Constancia AFIP | padrón oficial |
| **B** | **20-F / 6-K ante la SEC** | autodeclaración del emisor |
| **C** | Portal CNV | *eliminada: la fuente no contiene el dato* |
| **D** | Catálogo legacy | `dim_entity` |
| **E** | Sin CUIT autoritativo | no se declara el bridge |

**C se elimina por evidencia, no por preferencia.**

## 2-3 · Ventajas y desventajas

| | Ventajas | Desventajas |
|---|---|---|
| **A** | Registro absoluto; cubre entidades sin CIK | Sin API estable; gestión manual; **no establece el vínculo con el CIK** |
| **B** | Ambos IDs en **un documento**; inmutable; citable; mecanizable; **RAW ya descargado** | Sólo *cross-listed*; depende del parseo del bloque |
| **D** | Costo cero | Sin autor ni evidencia; **ya falló con el CIK de YPF** (4 conflictos OPEN) |
| **E** | Máxima honestidad epistémica | Bloquea la capa canónica indefinidamente |

## 4 · Impacto sobre SEC

**B es neutro-positivo.** No cambia el pipeline: **reutiliza RAW existente** (16 filings 20-F
sólo de YPF). Requiere un extractor del bloque — acotado, sin red, sin tocar S03.

## 5 · Impacto sobre CNV

**B libera a CNV de una responsabilidad que no puede cumplir**: verificado que no tiene el
dato estructurado. Exigírselo lo obligaría a parsear PDFs con riesgo de tomar el CUIT del
auditor. CNV sigue usando CUIT como identificador **nativo de su dominio** (fetch, scope), y
la afirmación de equivalencia se resuelve fuera. Separación limpia.

## 6 · Impacto sobre Market

**Ninguno directo** — no maneja CUIT. Se beneficia indirectamente: sus instrumentos quedan
colgados de una entidad con identidad demostrable en vez de un `entity_id` entero legacy.

## 7 · Impacto sobre provenance

```
A  method=REGISTRY            evidence="constancia PDF"        citable, NO automatizable
B  method=REGULATORY_DOCUMENT source=SEC:0001193125-25-067155
   evidence="Fiscal identification number in Argentina: 30-54668997-9"
                                                               citable Y automatizable
D  method=LEGACY_IMPORT       confidence=WEAK                  trazable, NO probatorio
```

**B es la única que produce evidencia citable y verificable por un tercero sin intervención
humana.**

## 8 · Impacto sobre 700+ entidades

```
7.998  entidades SEC        sin CUIT y sin necesitarlo    -> no aplica
   13  CIK + CUIT           TODAS presentan 20-F          -> B las resuelve al 100 %
   61  sólo CUIT (legacy)   sin CIK                       -> no hay bridge que demostrar
  ~56  byma_only (CNV)      sin CIK                       -> ídem
```

**B resuelve el 100 % de los casos donde existe un bridge.**

## 9 · Impacto sobre legacy migration

El CUIT legacy pasa de *"única fuente existente"* a *"candidato a contrastar contra un
documento que ya tenemos"*. Fase 2 se simplifica; Fase 4 se resuelve por extracción, no por
gestión. Si el 20-F contradice al legacy, **gana el 20-F** y el legacy queda como conflicto
— igual que ya se hizo con los CIK.

## 10 · Impacto sobre reproducibility

**B es la única plenamente reproducible**: dada la accession, cualquier tercero baja el mismo
documento inmutable y extrae el mismo valor. A depende de gestión puntual; D no es
reproducible.

## 11 · Riesgo de falsos matches

```
A  ~0     pero no establece el vínculo con el CIK
B  ~0     el emisor declara ambos en el mismo documento; no hay inferencia
C  ALTO   riesgo VERIFICADO de tomar ODBCUITAuditor como CUIT del emisor
D  MEDIO  sin evidencia; ya produjo 4 CIK equivocados
```

**C —la opción que yo mismo había sugerido— tiene el riesgo más alto, y es concreto, no
hipotético.**

## 12 · Complejidad

```
A  ALTA         sin API; gestión por entidad
B  BAJA-MEDIA   extractor de bloque regular sobre RAW existente
D  TRIVIAL      copiar
```

## 13 · Rollback

**B es reversible sin pérdida**: las aserciones se marcan `superseded_by` si aparece
evidencia mejor. El RAW no se toca; los identificadores se cierran con `valid_to`, no se
borran. Rollback = invalidar `method=REGULATORY_DOCUMENT/source=SEC` y volver los 13 a
`REVIEW_REQUIRED`.

---

## Preguntas específicas

**¿Qué fuentes pueden establecer un CUIT?** 20-F/6-K · AFIP · registro CNV (observación) ·
legacy · prospectos.

**¿AUTHORITATIVE?** Sólo **AFIP** (registro) y **20-F/6-K** (autodeclaración regulatoria).

**¿SUPPORTING?** CNV `EMPRESA_PAGE` (confirma que el CUIT existe y tiene perfil, **no a quién
pertenece**) · legacy · razón social · ISIN/LEI. **Nunca fundan un bridge solas.**

**¿Contradicción entre fuentes?** Precedencia `AFIP > 20-F > CNV observado > legacy`. La
perdedora **no se descarta**: se registra como `conflict` OPEN con ambos candidatos —
doctrina `EXT-NEW-012` ya vigente para CIK, extendida a CUIT. Si contradicen dos
autoritativas: `REVIEW_REQUIRED` obligatorio, sin resolución automática.

**¿Sin evidencia?** CUIT con `is_authoritative=false`, `confidence=WEAK`, `conflict` abierto.
**Usable para operar dentro del dominio CNV** (fetch, scope), **no para fundar un bridge ni
publicarse como identidad canónica.** La distinción entre *operar con* y *afirmar que* es
central.

**¿CUIT históricos?** Se cierran con `valid_to`, nunca se borran. Un hecho fechado en su
vigencia sigue siendo correcto.

**¿Absorbidas / cambio de razón social?**
- *Razón social*: la entidad **no cambia**. Se actualiza `preferred_name`; CUIT y CIK
  persisten. Posible porque `entity_key` es opaco.
- *Absorción*: la absorbida pasa a `MERGED` con `merged_into_key`; su CUIT se cierra en la
  fecha efectiva. **No se reasigna a la absorbente**: los hechos históricos le siguen
  perteneciendo.

**¿Entidades sin CUIT?** Válidas — Apple. Sin conflicto ni review. **La ausencia de un
identificador no es un defecto: es información.**

---

# D-I-03 · IDENTITY OWNERSHIP / STORAGE

## 1 · Alternativas

**A** centralizado en el PostgreSQL del engine (5433) · **B** base PostgreSQL independiente ·
**C** servicio con API · **D** distribuido por workstream (statu quo).

## 2-3 · Ventajas y desventajas

| | Ventajas | Desventajas |
|---|---|---|
| **A** | **FK reales** con SEC y CNV; ya existe y está poblado; cero infraestructura nueva | Market queda fuera (5432): sin FK |
| **B** | Independencia de ciclo de vida | **Pierde las FK que A ya tiene**; SEC/CNV dependerían de una base externa |
| **C** | Desacople total | Máxima complejidad; **imposible imponer integridad referencial por FK** |
| **D** | Cero trabajo | **Es el estado que produjo F-011** |

## 4-6 · Impacto por workstream

**SEC** — A es su statu quo mejorado: `identity` ya convive con `parsed` en 5433. B y C lo
obligarían a salir de su base para resolver identidad, metiendo dependencia de red en el
camino crítico del parseo.

**CNV** — A es lo natural: su `entity_key` **ya** referencia `identity.entities`. A convierte
esa convención en **FK**. B/C romperían un acoplamiento hoy sano.

**Market** — el caso difícil bajo cualquier opción, porque vive en 5432:
- **A1** — permanece en 5432 y consume identidad por **artefacto explícito y versionado**.
  Sin FK, pero con contrato declarado y auditable: cualitativamente distinto del join
  implícito actual.
- **A2** — migra a 5433. Gana FK real y **resuelve F-001 de paso**.

## 7 · Provenance

A y B equivalentes (misma tabla de aserciones). C degrada: habría que versionar respuestas de
API para reproducibilidad. **D es la peor: hoy la provenance del bridge no existe.**

## 8 · 700+ entidades

Ninguna opción tiene problema de escala: 8.000 entidades y ~25.000 identificadores es trivial
para PostgreSQL. **La escala no es criterio de decisión acá** — conviene decirlo para no usar
un argumento falso.

## 9 · Legacy migration

A permite ejecutar **Fases 0-2 sin tocar Market**, que es la parte de mayor fricción. La
Fase 3 es donde A1 vs A2 se vuelve determinante.

## 10 · Reproducibility

A: snapshot de una sola base. C: exige versionar la API — mucho más difícil de reproducir a
fecha pasada. D: hoy irreproducible (el bridge depende de un SQLite fuera del esquema).

## 11 · Falsos matches

Lo determinan los **constraints**, no la ubicación. A y B pueden imponer el índice único que
hace imposible el error del enunciado. **C no puede.** D es el estado que ya lo permitió.

## 12 · Complejidad

```
A1  BAJA     tablas + FK en base existente
A2  MEDIA    A1 + migración de Market  (pero resuelve F-001)
B   MEDIA    base nueva; SEC/CNV pierden FK
C   ALTA     servicio, API, versionado, auth
D   NULA     y deja el problema intacto
```

## 13 · Rollback

A1: drop del esquema; nada lo referencia hasta la Fase 3. A2: rollback de migración de
Market, riesgo mayor. C: complejo por acoplamiento de clientes.

---

# RECOMMENDATION

## D-I-02 → **Opción B: el 20-F es la fuente autoritativa del bridge CIK↔CUIT**

```
AUTHORITATIVE   AFIP (registro)          — para el CUIT en sí
                20-F / 6-K ante la SEC   — para el CUIT Y su vínculo con el CIK
SUPPORTING      CNV EMPRESA_PAGE · legacy · ISIN/LEI · razón social
NUNCA FUNDA     nombre · ticker · fuzzy · ausencia de alternativas
```

1. **Única fuente que atestigua ambos identificadores en un mismo documento.** No
   correlaciona: declara.
2. **Cobertura del 100 % de los casos que importan**, por necesidad lógica.
3. **El RAW ya está descargado**: sin red nueva, sin gestión manual.
4. **Reproducible por un tercero** con sólo la accession.
5. **Elimina la opción de mayor riesgo** — la que yo mismo sugerí — cuyo peligro quedó
   verificado.

**Lo que no resuelve, declarado:** el CUIT de entidades **sin CIK** (~117). No hay bridge que
demostrar ahí; su CUIT queda `WEAK` hasta que exista fuente AFIP. **No bloquea la capa
canónica**, porque no participan de ningún cruce SEC↔CNV.

## D-I-03 → **Opción A1 ahora, A2 como objetivo**

1. **Es donde ya está y donde ya funciona.** A1 convierte en FK una convención existente.
2. **FK reales para SEC y CNV** — lo que hace estructuralmente imposible el error del
   enunciado. C no puede ofrecerlo.
3. **Desbloquea Fases 0-2 sin tocar Market**, la parte de mayor fricción.
4. **No usa la escala como excusa**: el volumen es trivial en cualquier opción; se decide por
   integridad referencial.

**A2 queda como objetivo, no requisito inmediato** — resolvería F-001 de paso, pero **no debe
decidirse dentro de D-I-03**: es una decisión de Market con impacto operativo propio.

**Condición explícita de A1:** el artefacto de sincronización debe ser **versionado, firmado
y auditable**. Un export sin contrato reproduciría el problema en otro formato.

---

## Estado de cierre

| Decisión | Estado | ¿Falta información? |
|---|---|---|
| **D-I-02** | **CERRADA con recomendación (B)** | **No** |
| **D-I-03** | **CERRADA con recomendación (A1)**; A2 diferida a Market | **No** |

Ambas requieren únicamente ratificación del propietario. Siguen abiertas D-I-01 (reversible),
D-I-04 (optimización), D-I-05 (producto) y D-I-06 (umbral). **Ninguna bloquea la Fase 0.**

## Verificación pendiente antes de la Fase 4

El extractor del bloque de identificación debe validarse contra **los 13 emisores**, no sólo
contra YPF. La regularidad se verificó en 2 filings de **1** emisor; **asumir que los otros
12 tienen el mismo formato sería exactamente el tipo de inferencia que este diseño prohíbe.**

Si algún emisor no declara el CUIT en su 20-F, ese caso cae a `REVIEW_REQUIRED` y requiere
AFIP. **La recomendación no depende de que los 13 funcionen**: depende de que el método sea
autoritativo cuando aplica.

### Intento de cierre de esta brecha — resultado negativo, documentado

Se buscó RAW de 20-F de los otros 12 emisores para ampliar la validación. Resultado:

```
data/raw/edgar_pilot_ypf/     16 filings 20-F        SOLO YPF  (CIK 0000904851)
data/raw/companyfacts/        557 JSON               companyfacts, NO documentos
otros 11 emisores del bridge  0 documentos 20-F

único hallazgo adicional:
  data/raw/cnv/LOMA_000171137526000032_pr-20f.htm.txt     1.557 bytes
  -> fragmento de portada, no el 20-F completo (el de YPF pesa MB)
  -> contiene "Commission File Number: 001-38262" y la razón social
  -> NO permite confirmar la línea del CUIT
```

**La brecha sigue abierta.** El fragmento de Loma Negra muestra que el encabezado incluye el
`Commission File Number` —parte del mismo bloque de identificación—, lo que es indicio débil
de que la estructura generaliza, pero **1.557 bytes de portada no son prueba** de que la
línea *"Fiscal identification number in Argentina"* esté presente.

**Qué falta exactamente para cerrarla:** descargar de EDGAR el 20-F completo más reciente de
los 12 emisores restantes (CRES, LOMA, VIST, TGSU2, PAMP, IRSA, GGAL, SUPV, BBAR, TECO2,
CEPU, EDN) y verificar la presencia y el formato de esa línea. Es trabajo de descarga
acotado, sin decisiones pendientes.

Se registra el intento fallido en vez de omitirlo: **una verificación que no se pudo hacer no
es lo mismo que una que dio positivo**, y la diferencia debe quedar escrita.

---

# CICLO 3C — VALIDACIÓN EMPÍRICA DEL 20-F

Ejecutada 2026-08-25. Se descargaron 20-F completos de EDGAR para **3 emisores distintos de
YPF** y se buscó el CUIT **dentro del propio documento**, sin inferirlo por nombre, ni desde
Market, ni desde CNV, ni desde el legacy.

## Conclusión

# NO GENERALIZA

**La recomendación de D-I-02 emitida en el ciclo 3B queda REABIERTA.** Estaba fundada en
`n=1` (YPF) y la validación con `n=4` la refuta.

## Selección de emisores

Elegidos con diversidad deliberada de **sector** y de **agente de presentación** —que es lo
que suele determinar el formato del documento—, no por conveniencia:

```
CEPU    energía   agente 0001292814
GGAL    banco     autopresentado (0001114700)
TGSU2   gas       agente 0001140361
```

## Resultados

| issuer | CIK | CUIT hallado | 20-F encontrado | patrón | resultado | evidencia |
|---|---|---|---|---|---|---|
| **YPF** *(ciclo 3B)* | 0000904851 | **30-54668997-9** | Sí | **Bloque de identificación explícito** | **VERIFIED** | `0001193125-25-067155` · `d866694d20f.htm` |
| **CEPU** | 0001717161 | — | Sí · 6.215.545 B | Sin bloque | **NO_FOUND** | `0001292814-26-002446` · `cepuform20f_2025.htm` · sha `5705186b94b7de94…` |
| **GGAL** | 0001114700 | 2, **de terceros** | Sí · 12.864.140 B | Sin bloque | **AMBIGUOUS** | `0001114700-26-000038` · `ggal-20251231.htm` · sha `f94cc20395c88208…` |
| **TGSU2** | 0000931427 | — | Sí · 10.551.022 B | Sin bloque | **NO_FOUND** | `0001140361-26-016167` · `ef20060824_20f.htm` · sha `12a1c95fda107c50…` |

**Cobertura del método: 1 de 4 (25 %).**

## Control de falsos negativos

Antes de declarar `NO_FOUND` se descartó que el patrón de búsqueda fuera demasiado estrecho.
Se buscó, sobre el texto plano completo:

1. El bloque de identificación con **cualquier redacción** (`Fiscal identification`,
   `Country of incorporation`, `Legal form of`, `Commission file number`).
2. **Cualquier** número de 11 dígitos con **dígito verificador de CUIT válido**.
3. El CUIT que el legacy atribuye a cada emisor — sólo para contrastar presencia, nunca como
   evidencia.

```
CEPU    'Fiscal identification'         ausente
        'Country of incorporation'      ausente
        'Legal form of'                 ausente
        CUIT con dígito verificador OK  0 en 6,2 MB
        CUIT legacy 33650305499         NO aparece, en ningún formato

GGAL    'Fiscal identification'         ausente
        CUIT con dígito verificador OK  2, ambos de TERCEROS
        CUIT legacy 30704962807         NO aparece, en ningún formato

TGSU2   'Fiscal identification'         ausente
        CUIT con dígito verificador OK  0 en 10,6 MB
        CUIT legacy 30657862068         NO aparece, en ningún formato
```

Los `NO_FOUND` **no son artefacto de la búsqueda**: en CEPU y TGSU2 no existe un solo número
con estructura de CUIT válida en documentos de 6 y 10 MB.

## El caso GGAL confirma un modo de falla ya conocido

Los dos CUIT hallados en el 20-F de GGAL pertenecen a **proveedores de servicios**
mencionados en el texto:

```
30-68233570-6   AdeA                     — depósito de documentación contable
30-68250405-2   Iron Mountain Argentina  — custodia de archivos de una entidad absorbida
```

**Ninguno es el CUIT de GGAL.** Su CUIT legacy (`30704962807`) no figura en el documento.

Es exactamente el mismo modo de falla que el `ODBCUITAuditor` hallado en el VISOR de CNV:
**los documentos contienen CUIT de terceros**, y un extractor que tomara *"el CUIT del
documento"* se lo atribuiría al emisor. **Dos fuentes independientes, la misma trampa.**

Refuerza una regla del diseño: nunca extraer *"un CUIT"*, sino *"el CUIT declarado por el
emisor en un bloque de identificación etiquetado"*. Si el bloque no existe, el resultado es
`NO_FOUND` — no el número más cercano.

## Reproducción

```
1. https://data.sec.gov/submissions/CIK{cik}.json   -> localizar form='20-F'
2. https://www.sec.gov/Archives/edgar/data/{cik_sin_ceros}/{accession_sin_guiones}/{primary_doc}
3. Verificar sha256 contra la tabla de arriba
4. Buscar etiqueta de identificador fiscal + validar dígito verificador del CUIT
```
User-Agent requerido por la SEC. Documentos descargados al scratchpad del auditor,
**nunca a `data/raw/`**.

## Qué significa para D-I-02

**El 20-F sigue siendo autoritativo cuando declara el CUIT** — la evidencia de YPF es
genuina y no queda invalidada. Lo que se refuta es la **generalidad**: declarar el CUIT en el
20-F **no es práctica estándar**, es una particularidad del estilo de presentación de YPF.

Consecuencias sobre el análisis del ciclo 3B:

- **§8 "cobertura del 100 % por necesidad lógica" queda INVALIDADO.** El argumento era: tener
  bridge ⇔ presentar 20-F. Sigue siendo cierto que todos presentan 20-F, pero **presentar
  20-F no implica declarar el CUIT en él**. El razonamiento saltaba de "tiene el documento" a
  "el documento tiene el dato", y ese paso es falso.
- **La cola manual sí existe.** Se estimó en cero; la medición dice ~75 % de los casos.
- **La opción A (AFIP) vuelve al centro**, porque es la única con cobertura para los 12
  emisores restantes.

## Estado revisado de D-I-02

| | |
|---|---|
| **Estado** | **REABIERTA** — la recomendación de 3B no se sostiene con `n=4` |
| **Lo que sí se sostiene** | El 20-F es autoritativo **cuando declara el CUIT** (YPF: VERIFIED) |
| **Lo que se refuta** | Que sea un método de cobertura general |
| **Cobertura medida** | 1 de 4 (25 %) |

**Recomendación revisada, en dos niveles:**

```
NIVEL 1   20-F con bloque de identificación declarado
          -> AUTHORITATIVE · AUTO_MATCH · reproducible
          -> cobertura medida: 25 %

NIVEL 2   resto de los emisores
          -> requiere AFIP (constancia) o prospecto de emisión
          -> AUTHORITATIVE pero NO automatizable
          -> cola manual real: ~9 de 13 emisores
```

Esto **no invalida D-I-03** (A1, Identity centralizado en 5433), que es independiente de qué
fuente establezca el CUIT.

## Información adicional que falta para cerrar D-I-02

1. **Verificar los 9 emisores restantes** (CRES, VIST, PAMP, IRSA, SUPV, BBAR, TECO2, EDN,
   LOMA) para medir la cobertura real del Nivel 1. Con `n=4` la cobertura es 25 %, pero el
   intervalo es amplio.
2. **Determinar la viabilidad de AFIP como fuente**: si existe consulta pública reproducible
   del padrón, o si requiere gestión por entidad. **Es la variable que decide el costo real
   de la Fase 4.**
3. **Evaluar el prospecto de emisión (F-1/424B)** como fuente alternativa: suele contener el
   bloque de identificación societaria con más detalle que el 20-F anual.

**No se convierte evidencia insuficiente en PASS.** Con lo medido, el método del 20-F cubre
una minoría de los casos y no puede sostener por sí solo el bridge SEC↔CNV.

## Nota sobre este ciclo

Es la tercera vez en esta auditoría que una hipótesis propia se refuta al verificarla, y la
más consecuente: **cerré D-I-02 con una recomendación fundada en un solo emisor.** La
instrucción de validar empíricamente era correcta y el resultado justifica el ciclo.

La lección aplica al diseño mismo: `n=1` no es evidencia de regularidad, y un documento que
contiene un dato no implica que ese dato esté declarado como tal.

---

# CICLO 3D — FUENTE AUTORITATIVA PARA CUIT

Ejecutado 2026-08-25 tras la reapertura de D-I-02 en el ciclo 3C. Dos líneas investigadas:
**AFIP** y **filings societarios de la SEC** (F-1 / 424B / F-6).

## 1 · AFIP ASSESSMENT

Reconocimiento deliberadamente mínimo: **una consulta por endpoint, sin reintentos, sin
barrido**. El objetivo fue determinar viabilidad para un documento de arquitectura, no
obtener datos ni construir un scraper.

| # | Pregunta | Respuesta verificada |
|---|---|---|
| 1 | ¿Existe consulta pública? | **Sí** — `seti.afip.gob.ar/padron-puc-constancia-internet` responde HTTP 200 |
| 2 | ¿Qué datos devuelve? | Constancia de inscripción: razón social, CUIT, domicilio fiscal, impuestos, actividades |
| 3 | ¿Consultable por CUIT? | **Sí** — el formulario tiene campo `cuit` |
| 4 | ¿Consultable por razón social? | **No** en la constancia; hay que conocer el CUIT de antemano |
| 5 | ¿Fuente reproducible entidad → CUIT? | **No.** Resuelve CUIT → datos, no nombre → CUIT. **Es la dirección opuesta a la que el bridge necesita** |
| 6 | ¿Existe API? | **No pública.** `soa.afip.gob.ar/sr-padron/v1` y `/v2` devuelven **HTTP 404** |
| 7 | ¿Endpoint público? | Sólo el formulario web HTML |
| 8 | ¿Captcha / sesión / token? | **Captcha: 37 apariciones** en el HTML del formulario; 3 referencias a `token` |
| 9 | ¿Permite automatización? | **No.** El captcha es señal técnica explícita de intención de impedirla |
| 10 | ¿Qué provenance conserva? | PDF de constancia con fecha y CUIT — citable, pero obtenido a mano |
| 11 | ¿Cobertura esperable? | **100 % de las entidades argentinas** — es el padrón oficial |
| 12 | ¿Qué no resuelve? | El sentido nombre → CUIT; y **no conoce el CIK**, por lo que no establece el bridge por sí sola |

### Sobre `robots.txt` y la cuestión del permiso

```
www.afip.gob.ar/robots.txt    HTTP 404
seti.afip.gob.ar/robots.txt   HTTP 404
soa.afip.gob.ar/robots.txt    HTTP 404
```

**AFIP no publica política de crawling.** Se hace explícito porque la ausencia de prohibición
**no es autorización**. La instrucción del ciclo —*"no asumir que AFIP permite scraping
simplemente porque una página sea accesible"*— es correcta, y la única señal técnica
disponible (captcha) apunta en dirección contraria.

### Límite declarado de este assessment

Se verificaron **señales técnicas**, no términos legales. No se leyeron los Términos y
Condiciones de AFIP ni se evaluaron sus web services autenticados (`ws_sr_padron_a4/a5`), que
requieren clave fiscal y CUIT registrado — una **decisión organizacional**, no un problema
técnico. **Queda pendiente y no se infiere.**

### Clasificación

**AFIP = AUTHORITATIVE, NO AUTOMATIZABLE.** Máxima autoridad y cobertura total, pero acceso
manual por entidad y en la dirección inversa a la que el bridge requiere.

---

## 2 · SEC FILING ASSESSMENT

### Inventario

```
CEPU   417 filings   6-K:343 · 20-F:9 · F-1/A:3 · F-1 · 424B4 · F-6:2 · 8-A12B
GGAL   778 filings   6-K:673 · 20-F:25 · 424B2:3 · 424B3:2 · F-3 · F-6 · POS AM
TGSU2  777 filings   6-K:671 · 20-F:25 · F-6:1        (sin F-1/424B en el índice)
```

TGSU2 cotiza desde 1994: sus estatutos de registro anteceden al índice electrónico.

### Resultado

| Emisor | Documento | Bytes | CUIT válidos | Resultado |
|---|---|---|---|---|
| CEPU | **F-1** (prospecto de IPO, 2018) | 4.540.422 | **0** | NO_FOUND |
| CEPU | **424B4** (prospecto final, 2018) | 4.505.802 | **0** | NO_FOUND |
| GGAL | **424B2** (suplemento, 2025) | 630.977 | **0** | NO_FOUND |
| TGSU2 | **F-6** (registro de ADR, 2017) | 58.010 | **0** | NO_FOUND |

**Cero CUIT del emisor en 9,7 MB de documentación societaria.**

Las menciones de "CUIT" en el F-1 de CEPU son **definitorias, no declarativas**:

```
"CUIT, CUIL, CDI or CIE tax identification numbers or Documento Nacional Identidad..."
```

Es un glosario, no una autodeclaración.

### Falso positivo detectado en el propio método

La búsqueda por subcadena `CUIT` matcheó dentro de **"Cir·cuit"**:

```
"cuit Court of Appeals affirmed the so-called pari passu injunctions..."
   ^^^^  fragmento de "Circuit Court of Appeals"
```

Se registra porque es una lección aplicable al extractor: **buscar la etiqueta como subcadena
produce falsos positivos**. Debe exigirse límite de palabra y proximidad a un valor con
dígito verificador válido — que es justamente lo que impidió que este caso se convirtiera en
un hallazgo.

### Clasificación por documento

| Documento | Clasificación | Fundamento |
|---|---|---|
| **20-F con bloque de identificación** | **AUTHORITATIVE** | YPF: declara CUIT y CIK en el mismo documento |
| 20-F sin bloque | **UNUSABLE** para CUIT | CEPU, TGSU2: 0 CUIT en 6–10 MB |
| F-1 / 424B | **UNUSABLE** para CUIT | 0 en 9 MB de prospectos |
| F-6 | **UNUSABLE** | Lo presenta el banco depositario, no el emisor |
| 6-K con EEFF adjuntos | **NO EVALUADO** | 343–673 por emisor; podrían traer portada con CUIT |

---

## 3 · COVERAGE MATRIX

| Fuente | Autoridad | Automatizable | Cobertura medida | Establece CIK↔CUIT | Clasificación |
|---|---|---|---|---|---|
| **20-F con bloque** | Alta | **Sí** | **1 de 4 (25 %)** | **Sí, en un solo documento** | **AUTHORITATIVE** |
| **AFIP constancia** | **Máxima** | **No** (captcha) | 100 % potencial | **No** (no conoce el CIK) | **AUTHORITATIVE** |
| F-1 / 424B / F-6 | Alta | Sí | **0 de 3** | No | **UNUSABLE** |
| 6-K con EEFF | Media | Sí | **no medida** | Probablemente no | **DISCOVERY_ONLY** |
| CNV `EMPRESA_PAGE` | Baja | Sí | 100 % del universo CNV | No | **DISCOVERY_ONLY** |
| CNV VISOR | — | — | 0 (sólo CUIT de auditores) | No | **UNUSABLE** |
| Legacy `dim_entity` | Nula | Sí | 13 bridges | Afirma sin evidencia | **CORROBORATING** |
| ISIN / LEI (GLEIF) | Alta | Sí | **no evaluada** | Potencialmente sí | **NO EVALUADA** |

### El hallazgo estructural

**No existe fuente única que sea simultáneamente autoritativa, automatizable y de cobertura
amplia.**

```
20-F   automatizable + establece el bridge   pero cobertura 25 %
AFIP   autoritativa + cobertura 100 %        pero NO automatizable ni establece el bridge
```

Las dos propiedades que el bridge necesita —**autoridad** y **cobertura**— están repartidas
entre fuentes distintas y ninguna las reúne.

---

## 4 · RECOMMENDED EVIDENCE HIERARCHY

```
NIVEL 1 · AUTHORITATIVE — automatizable
   20-F con bloque de identificación declarado
   -> AUTO_MATCH · evidencia: accession + cita textual
   -> cobertura medida: 25 %

NIVEL 2 · AUTHORITATIVE — manual
   Constancia AFIP (PDF a mano, confirma el CUIT)
   + CIK de la fuente de registro SEC
   -> el bridge lo AFIRMA UNA PERSONA apoyada en dos documentos autoritativos
   -> VERIFIED · evidencia: PDF + fecha + quién lo obtuvo
   -> cobertura: 100 %, con costo por entidad

NIVEL 3 · CORROBORATING — nunca funda; refuerza o contradice
   legacy dim_entity · CNV EMPRESA_PAGE · razón social

NIVEL 4 · DISCOVERY_ONLY — genera candidatos a revisión, jamás publica
   6-K con EEFF · búsqueda por nombre

NUNCA FUNDA UN BRIDGE
   nombre · ticker · fuzzy · ausencia de alternativas · CUIT de terceros
```

### Estrategia multi-fuente con `REVIEW_REQUIRED`

No se fuerza una fuente única porque **no existe**:

```
para cada emisor con CIK y CUIT candidato:

   ¿su 20-F declara el CUIT en bloque de identificación?
       SI  -> AUTO_MATCH                    (Nivel 1)
       NO  -> ¿el CUIT legacy coincide con una constancia AFIP obtenida a mano?
                 SI  -> VERIFIED            (Nivel 2, decisión humana con 2 documentos)
                 NO  -> ¿se contradicen?
                           SI -> CONFLICT OPEN con ambos candidatos
                           NO -> REVIEW_REQUIRED, evidencia insuficiente
```

**El CUIT sin bridge demostrado sigue siendo usable dentro del dominio CNV** (fetch, scope).
Lo que no puede es publicarse como identidad canónica ni fundar un cruce SEC↔CNV. La
distinción entre *operar con* y *afirmar que* se mantiene.

---

## 5 · REMAINING GAPS

**G1 · Cobertura real del Nivel 1 sin medir.** Verificados 4 de 13. Faltan 9: CRES, VIST,
PAMP, IRSA, SUPV, BBAR, TECO2, EDN, LOMA. Con `n=4` el intervalo es amplio y **no se
extrapola**.

**G2 · Términos de uso de AFIP no leídos.** Se verificaron señales técnicas, no términos
legales. Requisito previo a cualquier acceso sistemático.

**G3 · Web services autenticados de AFIP no evaluados.** `ws_sr_padron_a4/a5` exigen clave
fiscal y CUIT registrado: **decisión organizacional**, no técnica. Podrían convertir el
Nivel 2 en automatizable. No se asume ni se descarta.

**G4 · ISIN / LEI sin evaluar.** GLEIF es público y gratuito. Un LEI presente en ambos
registros sería puente de Nivel 1 automatizable. **Es la vía no explorada con mayor
potencial.**

**G5 · 6-K con EEFF adjuntos.** 343–673 por emisor. Si los EEFF argentinos adjuntos traen
portada con CUIT, podrían ser Nivel 1. No medido por volumen.

---

## 6 · UPDATED D-I-02 RECOMMENDATION

**Estrategia de dos niveles, no fuente única.** Se abandona la búsqueda de una fuente
universal porque la evidencia muestra que no existe.

```
AUTHORITATIVE   20-F con bloque declarado            automatizable · 25 % medido
                Constancia AFIP + CIK de registro    manual · 100 % · afirmada por persona
CORROBORATING   legacy · CNV EMPRESA_PAGE · razón social
DISCOVERY_ONLY  6-K con EEFF · búsqueda por nombre
UNUSABLE        F-1 · 424B · F-6 · CNV VISOR · nombre · ticker · fuzzy
```

**Consecuencia operativa honesta:** el bridge SEC↔CNV **no es completamente automatizable con
las fuentes conocidas**. Aproximadamente **9 de 13 emisores requieren decisión humana apoyada
en constancia AFIP**. Es trabajo acotado —13 entidades, no 8.000— pero es manual y debe
planificarse como tal, no descubrirse a mitad de la Fase 4.

**Antes de ejecutar conviene cerrar G4 (LEI/GLEIF)**: es la única vía identificada que podría
elevar la cobertura automatizable, y evaluarla cuesta menos que resolver 9 entidades a mano.

### Estado de D-I-02

| | |
|---|---|
| **Estado** | **CERRADA con estrategia multi-fuente**; se descarta la fuente única |
| **Cobertura automatizable medida** | 25 % (1 de 4) |
| **Cobertura total alcanzable** | 100 %, con ~75 % de intervención manual |
| **Bloqueante para Fases 0-3** | **No** |
| **Bloqueante para Fase 4** | **Sí**, hasta decidir sobre G3 y G4 |

**D-I-03 (A1) no se ve afectada**: es independiente de qué fuente establezca el CUIT.

### Nota de método

Tres ciclos consecutivos corrigieron la misma recomendación a medida que crecía la evidencia:
de *"CNV declara el CUIT"* (falso) a *"el 20-F lo declara universalmente"* (falso, 25 %) a
*"no existe fuente única; se requiere estrategia multi-fuente con revisión humana acotada"*.

Cada corrección vino de verificar, no de razonar. **La conclusión actual es la primera que no
se apoya en una generalización desde un único caso** — y aun así declara explícitamente que
G1 sigue sin medir.

---

# G4 — LEI / GLEIF ASSESSMENT

Ejecutado 2026-08-25. Muestra real sobre 4 emisores, no documentación conceptual.

## Conclusión

# CORROBORATING_ONLY

GLEIF **no puede establecer `CIK ↔ CUIT` por sí solo**: la cadena tiene una arista rota.
Pero su valor práctico es alto y específico — **reemplaza la consulta manual a AFIP**.

---

## 1 · GLEIF ASSESSMENT

### Qué entrega, verificado sobre registros reales

| Campo solicitado | ¿Presente? | Valor observado (YPF) |
|---|---|---|
| legal entity name | **Sí** | `YPF Sociedad Anonima` |
| legal address | **Sí** | Buenos Aires, AR |
| headquarters | **Sí** | campo `headquartersAddress` |
| **registration authority** | **Sí** | `RA000009` |
| **registration number** | **Sí** | **`30-54668997-9`** |
| legal jurisdiction | **Sí** | `AR` |
| entity status | **Sí** | `ACTIVE` |
| parent information | **Sí** | endpoints `/direct-parent`, `/ultimate-parent` |
| dates | **Sí** | `lastUpdateDate: 2026-04-29`, `registration.status: ISSUED` |
| legal form | **Sí** | `F0A6` (ELF code) |
| **CIK** | **NO** | ausente del registro |

### ¿Contiene el CUIT? — Sí, y está verificado que lo es

El ciclo prohíbe asumir `registrationNumber = CUIT`. Se verificó **qué autoridad** emite ese
número consultando el catálogo de Registration Authorities de GLEIF:

```
RA000009  ->  http://www.afip.gob.ar/sitio/externos/                       = AFIP
RA000010  ->  argentina.gob.ar/justicia/registro-nacional-sociedades       = Registro Nacional de Sociedades
RA999999  ->  (sin sitio)                                                  = sin autoridad declarada
```

**`RA000009` es AFIP.** Su número de registro **es** el CUIT, por definición del registro.
No es una coincidencia de formato: es el identificador que AFIP asigna.

## 2 · SAMPLE EVIDENCE MATRIX

| issuer | CIK | LEI | legal name (GLEIF) | reg. authority | registration number | CUIT legacy | ¿coincide? | relación probada | confidence |
|---|---|---|---|---|---|---|---|---|---|
| **YPF** | 0000904851 | `5493003N7447U18U5U53` | YPF Sociedad Anonima | **RA000009 · AFIP** | **30-54668997-9** | 30546689979 | **SÍ** | LEI→CUIT **probada**; CIK→LEI **no** | **ALTA** para LEI→CUIT |
| **CEPU** | 0001717161 | `2549005JLIWQ6B7VNR38` | CENTRAL PUERTO S A | **RA000009 · AFIP** | **33-65030549-9** | 33650305499 | **SÍ** | ídem | **ALTA** para LEI→CUIT |
| **TGSU2** | 0000931427 | `5299002TRC7IFQYSW596` | Transportadora de Gas del Sur S.A. | **RA000010 · RNS** | **30-65786206-8** | 30657862068 | **SÍ** | ídem | **ALTA** para LEI→CUIT |
| **GGAL** | 0001114700 | `5299008H3AXIXV5G3C23` | Grupo Financiero Galicia S.A. | `RA999999` (ninguna) | **None** | 30704962807 | — | **NO_FOUND** | — |

**Cobertura de LEI→CUIT: 3 de 4 (75 %).**

Los tres CUIT hallados **coinciden exactamente** con el catálogo legacy. Es la primera
corroboración independiente que recibe ese catálogo desde una autoridad real.

## 3 · DEMOSTRACIÓN DE CADA ARISTA

El ciclo exige demostrar `CIK → LEI`, `LEI → legal entity`, `legal entity → CUIT` por
separado, con evidencia independiente.

### Arista `LEI → legal entity → CUIT` — **PROBADA**

```
LEI 5493003N7447U18U5U53
  -> entity.legalName      = "YPF Sociedad Anonima"
  -> entity.registeredAt   = RA000009  (= AFIP, verificado en el catálogo de RAs)
  -> entity.registeredAs   = 30-54668997-9
evidencia: api.gleif.org/api/v1/lei-records/5493003N7447U18U5U53
```
Autoridad: **alta**. GLEIF es el registro global oficial del ISO 17442 y declara
explícitamente qué autoridad emitió el número.

### Arista `CIK → LEI` — **NO PROBADA**

Se buscó evidencia independiente por **cuatro vías, todas negativas**:

```
1. campo `lei` de la SEC submissions API   -> None en los 4 emisores
                                              (el campo EXISTE en el esquema, está vacío)
2. LEI dentro de los filings descargados   -> 0 apariciones
                                              (20-F, F-1, 424B4, 424B2, F-6)
3. ISIN de GLEIF dentro de los filings      -> 0 apariciones
                                              (20 ISIN por emisor, ninguno en los documentos)
4. CUSIP derivado del ISIN                  -> 0 apariciones
                                              (US9842451000 -> 984245100)
```

**La única conexión disponible entre el CIK y el LEI es la coincidencia de nombre**, que este
diseño prohíbe explícitamente como fundamento de identidad.

### Consecuencia

```
CIK  --?-->  LEI  --[AFIP]-->  CUIT
      ^
      arista sin evidencia independiente
```

**GLEIF no cierra el bridge.** Aporta el extremo argentino con autoridad real, pero no puede
conectarlo con el extremo estadounidense sin una decisión humana.

## 4 · AUTOMATION FEASIBILITY

| Dimensión | Evaluación |
|---|---|
| Disponibilidad pública | **Sí** — `api.gleif.org/api/v1`, sin registro ni credenciales |
| API | **Sí**, REST + JSON:API. Endpoints `/lei-records`, `/registration-authorities`, `/isins`, `/direct-parent` |
| Autenticación | **No requerida** |
| Rate limits | **No se observaron headers de límite** en la sonda. GLEIF documenta uso razonable; **no verificado bajo carga** |
| Reproducibilidad | **Alta** — dado un LEI, el registro es direccionable y estable |
| Estabilidad | Alta. `lastUpdateDate` permite detectar cambios; los LEI no se reasignan |
| Provenance | **Excelente**: LEI + `registeredAt` + `registeredAs` + fecha de actualización, todo citable |
| Cobertura | 4 de 4 emisores tienen LEI; **3 de 4** con CUIT |
| Costo | **Cero** |
| Automatizable | **Sí, completamente** — para la arista LEI→CUIT |

## 5 · AUTHORITY LEVEL

| Arista | Clasificación | Fundamento |
|---|---|---|
| `LEI → CUIT` (vía RA000009/RA000010) | **AUTHORITATIVE** | El registro declara que AFIP emitió ese número |
| `LEI → legal name / jurisdicción / estado` | **AUTHORITATIVE** | Registro oficial ISO 17442 |
| `CIK → LEI` | **UNUSABLE** | Sin evidencia independiente; sólo por nombre |
| **GLEIF como bridge CIK↔CUIT** | **CORROBORATING_ONLY** | Aporta un extremo con autoridad, no la unión |

## 6 · ¿REDUCE LA COLA MANUAL DE ~9/13?

**No la elimina, pero transforma su naturaleza y baja mucho su costo.**

```
ANTES (ciclo 3D)
   por cada emisor sin CUIT en el 20-F:
      1. una persona entra al portal de AFIP
      2. resuelve un captcha
      3. descarga el PDF de constancia
      4. compara contra el legacy
      5. afirma el bridge
   -> ~9 emisores, trabajo manual completo

DESPUES (con GLEIF)
   1. GLEIF devuelve el CUIT registrado en AFIP     AUTOMATICO
   2. una persona confirma que la entidad AR de GLEIF
      es la misma que el CIK de la SEC               MANUAL, pero acotado
   -> la persona ya no BUSCA el dato: sólo CONFIRMA una correspondencia
```

**El paso humano sigue existiendo** —porque la arista `CIK → LEI` no tiene evidencia
independiente— pero pasa de *"conseguir el dato sorteando un captcha"* a *"confirmar que
`YPF SOCIEDAD ANONIMA` (SEC, CIK 0000904851) y `YPF Sociedad Anonima` (GLEIF, AR, CUIT
30-54668997-9 en AFIP) son la misma entidad"*, con dos registros oficiales a la vista.

**Y aporta algo que antes no existía: corroboración independiente del legacy.** Los 3 CUIT
coinciden exactamente con `dim_entity`. Eso no convierte al legacy en autoritativo, pero
eleva la confianza de `WEAK` a `STRONG` en esos casos, y hace que la confirmación humana sea
una ratificación en vez de una investigación.

## 7 · COMPARACIÓN CONTRA LAS OTRAS FUENTES

| | Autoridad | Automatizable | Cobertura | ¿Establece CIK↔CUIT? | Costo |
|---|---|---|---|---|---|
| **20-F con bloque** | Alta | **Sí** | 25 % (1/4) | **Sí, solo** | 0 |
| **GLEIF** | **Alta (AFIP)** | **Sí** | **75 % (3/4)** | **No** — falta CIK→LEI | **0** |
| AFIP constancia | Máxima | **No** (captcha) | 100 % | No | manual |
| CNV VISOR | — | Sí | 0 % | No | 0 |
| F-1 / 424B / F-6 | Alta | Sí | **0 %** | No | 0 |
| legacy `dim_entity` | Nula | Sí | 13 bridges | Afirma sin evidencia | 0 |

**GLEIF es la mejor relación autoridad/cobertura/costo de todas las fuentes evaluadas** —
triplica la cobertura del 20-F, es gratuita y automatizable— **pero no cierra el bridge.**

Y es estrictamente superior a AFIP como fuente del CUIT: entrega **el mismo hecho** (el CUIT
registrado en AFIP) **sin captcha, por API y con provenance citable**.

## 8 · UPDATED EVIDENCE HIERARCHY

```
NIVEL 1 · AUTHORITATIVE — automatizable, cierra el bridge solo
   20-F con bloque de identificación declarado
   -> AUTO_MATCH · cobertura medida 25 %

NIVEL 2 · AUTHORITATIVE — automatizable, NO cierra el bridge
   GLEIF: LEI -> registeredAt(RA000009=AFIP) -> registeredAs = CUIT
   -> establece el CUIT con autoridad real, sin intervención
   -> cobertura medida 75 %
   -> requiere confirmación humana de la arista CIK->LEI

NIVEL 3 · AUTHORITATIVE — manual
   Constancia AFIP (sólo si GLEIF no tiene el registro, p. ej. GGAL)

NIVEL 4 · CORROBORATING
   legacy dim_entity · CNV EMPRESA_PAGE · razón social

NIVEL 5 · DISCOVERY_ONLY
   búsqueda por nombre en GLEIF · 6-K con EEFF

NUNCA FUNDA UN BRIDGE
   nombre · ticker · fuzzy · LEI asumido por nombre · CUIT de terceros
```

### Flujo recomendado, actualizado

```
para cada emisor con CIK:

  1. ¿su 20-F declara el CUIT?            SI -> AUTO_MATCH        (25 %)
  2. ¿GLEIF tiene LEI con registeredAs
     bajo RA000009/RA000010?              SI -> CUIT establecido con autoridad
                                                + confirmación humana de CIK->LEI
                                                -> VERIFIED                (75 %)
  3. ¿ninguna de las dos?                      -> constancia AFIP manual   (GGAL)
  4. ¿contradicción entre fuentes?             -> CONFLICT OPEN
```

## RECOMMENDATION PARA D-I-02

**Incorporar GLEIF como Nivel 2.** Es la mejor fuente disponible para el CUIT y su costo de
integración es mínimo: API pública, sin credenciales, sin captcha, gratuita.

**Pero no resuelve D-I-02 por sí sola**, y decirlo importa: la arista `CIK → LEI` **no tiene
evidencia independiente** en ninguna de las cuatro vías probadas. Conectar ambos extremos por
nombre sería exactamente lo que este diseño prohíbe.

**Cola manual revisada:**

```
antes de G4     ~9 de 13 emisores, con búsqueda manual completa
después de G4   ~9 de 13 emisores, pero sólo confirmación de correspondencia
                 + 1 de 13 (GGAL) requiere AFIP porque GLEIF no tiene su registro
```

**El número de intervenciones humanas no baja; baja el trabajo por intervención**, y cada una
pasa a estar respaldada por dos registros oficiales en vez de por un catálogo legacy sin
autor.

### Gap que G4 no cierra

**G4-a · La arista `CIK → LEI` sigue sin fuente.** Vías no exploradas: el archivo
`LEI-CIK mapping` que publican algunos proveedores; los formularios `SC 13G/13D` (que a veces
declaran LEI); o los XBRL `dei:` de filings recientes. **No evaluadas** — no se infieren.

### Clasificación final

# CORROBORATING_ONLY

No `USEFUL_BRIDGE`, porque no cierra `CIK ↔ CUIT`.
No `DISCOVERY_ONLY`, porque lo que aporta es autoritativo, no un mero candidato.
No `UNUSABLE`, porque triplica la cobertura del CUIT y elimina el captcha de AFIP.

**Es corroboración de máxima calidad sobre uno de los dos extremos del puente.**

---

# G5 — CIK ↔ LEI PRIMARY-SOURCE ASSESSMENT

Ejecutado 2026-08-25. Objetivo único: determinar si existe evidencia **primaria y
reproducible** de `CIK → LEI`. Sólo fuentes SEC/XBRL. No se buscaron soluciones de terceros
ni se construyó ningún mapping.

## Conclusión

# CIK_LEI_PRIMARY_BRIDGE = NOT_AVAILABLE

**Ninguna fuente primaria de la SEC declara el LEI del emisor.** Verificado en cinco vías
independientes sobre 4 emisores, con 0 hallazgos.

---

## 1 · XBRL DEI — el elemento no existe

Inspección de **155 archivos** del paquete XBRL de YPF (instancias, esquemas, linkbases,
inline XBRL de 20-F de varios ejercicios):

```
elementos dei: distintos hallados : 42
relacionados con identidad        : 17
```

Los 17 disponibles:

```
dei:EntityCentralIndexKey            <- el CIK, presente
dei:EntityRegistrantName
dei:EntityFileNumber
dei:EntityIncorporationStateCountryCode
dei:EntityFilerCategory · EntityCurrentReportingStatus · EntityShellCompany
dei:EntityAddress* (5 variantes) · EntityCommonStockSharesOutstanding
dei:EntityEmergingGrowthCompany · EntityInteractiveDataCurrent
dei:EntityVoluntaryFilers · EntityWellKnownSeasonedIssuer
dei:EntityAddressesAddressTypeAxis
```

**Ninguno es un identificador LEI.** La taxonomía DEI que usan estos filings no contempla el
elemento. No es que esté vacío: **no existe**.

## 2 · Inline XBRL — LEI literal ausente

```
LEI 5493003N7447U18U5U53 (YPF, según GLEIF)
   buscado literalmente en 155 archivos -> 0 apariciones
```

### Falso positivo detectado en el propio método

Mi patrón `dei:.*LEI` con `re.I` produjo 6 coincidencias aparentes que resultaron espurias:
el `.*` codicioso saltó desde `dei:AmendmentFlag` hasta encontrar la subcadena `lei` en otra
palabra del texto, cientos de caracteres después.

Se registra por la misma razón que el falso positivo de *"Cir·cuit"* en el ciclo 3D: **los
patrones laxos sobre etiquetas de identificador generan hallazgos fantasma**, y un extractor
que los aceptara produciría bridges inventados. Ambos casos refuerzan la misma regla de
diseño — exigir límite de palabra y validación estructural del valor.

## 3 · SC 13D / SC 13G / SC TO-T / SC 14D9

Revisados los 4 filings más recientes de cada emisor:

| Emisor | Filings del tipo | Revisados | LEI del emisor | Etiquetas LEI | Candidatos ISO 17442 |
|---|---|---|---|---|---|
| YPF | 19 | 4 | **0** | 0 | 0 |
| CEPU | 6 | 4 | **0** | 0 | 0 |
| GGAL | 16 | 4 | **0** | 0 | 0 |
| TGSU2 | 17 | 4 | **0** | 0 | 0 |

**16 documentos, cero LEI.** Ni siquiera aparecen cadenas con formato ISO 17442 (20
alfanuméricos) que pudieran ser candidatos.

**Advertencia de método que resultó innecesaria pero se deja registrada:** un SC 13D/13G lo
presenta un **inversor** sobre un emisor. Cualquier LEI hallado allí sería, por defecto, del
*filer*, no del *issuer* — y la consigna prohíbe aceptar LEI de terceros. No hubo que aplicar
el filtro porque no hubo hallazgos.

## 4 · Campo `lei` de la SEC submissions API — vacío para todos

El campo **existe en el esquema** de `data.sec.gov/submissions/CIK*.json`:

```
campos escalares: cik · entityType · sic · ownerOrg · name · ein · lei · description ...
```

Muestra de los 4 emisores:

```
YPF     lei = None      ein = 521612271
CEPU    lei = None      ein = 000000000
GGAL    lei = None      ein = 000000000
TGSU2   lei = None      ein = 000000000
```

**Control fuera de la muestra**, para distinguir *"no lo tienen estos emisores"* de *"la SEC
no lo publica"*:

```
Apple Inc.          lei = None
MICROSOFT CORP      lei = None
JPMORGAN CHASE      lei = None
BP PLC              lei = None
TotalEnergies SE    lei = None
Vale S.A.           lei = None
                    -> poblados: 0 / 6
```

**El hallazgo es general, no específico de los emisores argentinos: la API pública de
submissions de la SEC no publica LEI para ningún emisor**, incluidos los mayores de EE.UU. y
extranjeros. El campo está declarado y sistemáticamente vacío.

## 5 · Otros filings (verificado en ciclos previos)

```
20-F     4 emisores    0 LEI      (ciclos 3C/3D)
F-1      CEPU          0 LEI
424B4    CEPU          0 LEI
424B2    GGAL          0 LEI
F-6      TGSU2         0 LEI
```

---

## MATRIZ DE ARISTAS

| source | document | filing | CIK | LEI | evidence location | issuer | confidence | resultado |
|---|---|---|---|---|---|---|---|---|
| XBRL DEI | instancias + inline | 20-F múltiples | 0000904851 | — | 42 elementos `dei:`, ninguno LEI | YPF | — | **NOT_FOUND** |
| Inline XBRL | 155 archivos | paquete completo | 0000904851 | — | 0 apariciones literales | YPF | — | **NOT_FOUND** |
| SC 13G/A | `ypf-slim13ga4_0213.htm` | 2017-02-14 | 0000904851 | — | sin etiquetas ni candidatos | YPF | — | **NOT_FOUND** |
| SC 13G/A | `cp-sc13ga_123121.htm` | 2022-02-09 | 0001717161 | — | ídem | CEPU | — | **NOT_FOUND** |
| SC 13G | `tm2430684d1_sc13g.htm` | 2024-12-10 | 0001114700 | — | ídem | GGAL | — | **NOT_FOUND** |
| SC 14D9 | `tgs.htm` | 2017-01-13 | 0000931427 | — | ídem | TGSU2 | — | **NOT_FOUND** |
| submissions API | campo `lei` | — | los 4 | `None` | esquema poblado, valor vacío | los 4 | — | **NOT_FOUND** |

**Ningún `VERIFIED`. Ningún `AMBIGUOUS`. Cuatro emisores en `NOT_FOUND`.**

---

## RESPUESTAS

**A · ¿Existe `CIK → LEI` verificable desde fuente primaria?**
**No.** Cinco vías independientes, cero hallazgos. La SEC no publica el LEI del emisor en
ninguno de sus canales primarios evaluados.

**B · ¿Qué cobertura tiene en los 4 emisores?**
**0 de 4 (0 %).** Y el control sugiere que la cobertura sería 0 % también fuera de la
muestra: el campo `lei` está vacío para 6 de 6 emisores de control.

**C · ¿Reduce realmente el trabajo manual?**
**No, para el bridge.** La arista sigue requiriendo decisión humana.
**Sí, para el CUIT** — pero eso ya lo aportaba G4 y es independiente de esta arista.

**D · ¿Puede formar parte de Identity v1?**
**Sí, pero no como arista de bridge.** El LEI entra como:
- `identifier(id_type='LEI', id_namespace='GLEIF')` de la entidad — legítimo y autoritativo;
- **fuente autoritativa del CUIT** vía `registeredAt=RA000009` (AFIP);
- **nunca** como prueba de que un CIK y un CUIT son la misma entidad.

**E · ¿O el LEI queda únicamente como corroboración del CUIT?**
**Sí.** Se confirma la clasificación de G4: **CORROBORATING_ONLY**. G5 no la mejora; la
cierra. La esperanza de que el LEI cerrara el puente queda descartada con evidencia, no por
falta de búsqueda.

---

## CONSECUENCIA PARA D-I-02

La jerarquía de G4 **no cambia**, pero ahora tiene un límite demostrado en lugar de un hueco
por explorar:

```
NIVEL 1  20-F con bloque declarado    AUTHORITATIVE · automatizable · cierra el bridge · 25 %
NIVEL 2  GLEIF -> CUIT (vía AFIP)     AUTHORITATIVE · automatizable · NO cierra el bridge · 75 %
NIVEL 3  Constancia AFIP manual       AUTHORITATIVE · sólo si GLEIF no tiene registro
NIVEL 4  CORROBORATING                legacy · CNV EMPRESA_PAGE
NUNCA    nombre · ticker · fuzzy · LEI atribuido por nombre
```

**La arista `CIK → LEI` no tiene fuente primaria y la decisión humana en el Nivel 2 es
estructural, no una carencia temporal.** No se elimina incorporando otra fuente: es
consecuencia de que los dos registros —SEC y GLEIF/AFIP— **no se referencian entre sí**.

Esto **cierra G4-a** (el gap que G4 había dejado abierto) con resultado negativo, y confirma
que el diseño de Identity v1 debe contemplar `VERIFIED` por decisión humana como un estado
permanente y de primera clase — no como un paso transitorio hasta encontrar la fuente que
falta.

**No se buscaron mappings de terceros ni se inventó ninguno**, conforme a la consigna.

## Los dos casos de prueba, bajo la recomendación

```
YPF          CIK 0000904851 · CUIT 30546689979 · Market entity 72
             bridge: 20-F accession 0001193125-25-067155  -> VERIFICADO en el RAW

Central Puerto  CIK 0001717161 · CUIT 33650305499 · Market entity 70
             bridge: pendiente de extraer su propio 20-F  -> NO verificado aún
```

**No se asume que el bridge de CEPU sea válido porque coincida con el legacy.** Requiere su
propio documento, igual que YPF. Es precisamente el CUIT que el enunciado del ciclo 3
atribuyó por error a YPF: la mejor demostración de por qué cada bridge exige su propia
evidencia.


---
---

# CICLO 4 — IMPLEMENTACIÓN DE IDENTITY V1

**Fecha:** 2026-08-25 · **Rol:** implementador (no auditor)
**Veredicto:** `IDENTITY_V1 = CHECKPOINTED`

Documentos de este ciclo:
- `docs/architecture/IDENTITY_V1_SCHEMA.md`
- `docs/architecture/IDENTITY_V1_IMPLEMENTATION.md`
- `docs/architecture/IDENTITY_V1_MIGRATION_PLAN.md`
- `docs/review/IDENTITY_V1_TEST_REPORT.md`

---

## D-I-04 — El backfill de las ~8.000 entidades queda ABIERTO

**Estado: NO DECIDIDO.** Es la única decisión que bloquea la Fase 2.

El backfill tal como está diseñado produciría del orden de 8.000
`REVIEW_REQUIRED` por el puente CIK↔LEI, que G5 demostró que no tiene fuente
primaria. Ninguna persona procesa 8.000 reviews.

Recomendación registrada (opción A para el universo US, C para los argentinos):
el LEI solo tiene valor operativo en Catalaxia como puente hacia el CUIT, y el
CUIT solo aplica a emisores argentinos. Abrir 8.000 reviews por un identificador
que no se usa sería teatro de rigor. Detalle en `IDENTITY_V1_MIGRATION_PLAN.md`
§ Fase 2.

---

## Lo que el ciclo 4 confirmó de los ciclos anteriores

**G5 se confirma en la implementación, no solo en el análisis.** El puente
CIK↔LEI de los 4 emisores del piloto está registrado como `HUMAN_DECISION` /
`confidence = STRONG`, y `ck_authoritative_metodo` impide que se declare
`AUTHORITATIVE`. El sistema no puede fingir que una fuente publica ese par
aunque alguien quiera hacerlo.

**3C se confirma en los datos.** De los 4 emisores del piloto, solo YPF tiene un
20-F materializado en `parsed.pre_xbrl_filings` (18 filings, CIK 0000904851). Los
otros 3 tomaron el CIK de `SEC_REGISTRY`. La cobertura del 20-F sigue siendo el
cuello de botella medido en 3C.

**G4 se confirma emisor por emisor.** GLEIF publicó CUIT utilizable para 3 de 4:
YPF (`RA000009`), CEPU (`RA000009`), TGSU2 (`RA000010`). GGAL quedó sin CUIT
(`RA999999`, `registeredAs = null`) y con review abierta. **3/4 de cobertura, no
4/4** — y el que falta se ve, no se rellena.

---

## Lo que el ciclo 4 corrigió de mis propias conclusiones

**Un CIK ya asignado produce `REJECTED`, no `REVIEW_REQUIRED`.** El diseño del
ciclo 3 preveía `REVIEW_REQUIRED` para "CIK conflictivo". La implementación
distingue dos casos que el diseño mezclaba:

| Caso | Resultado | Por qué |
|---|---|---|
| El identificador ya es autoritativo **de otra entidad** | `REJECTED` + conflict | No hay ambigüedad: hay una atribución falsa. Aceptarlo violaría `ux_identifier_autoritativo_unico` |
| La entidad ya tiene **otro valor** del mismo tipo, y el propuesto está libre | `REVIEW_REQUIRED` + conflict + review | Ahí sí hay dos candidatos y hay que elegir |

El primero es más fuerte que lo diseñado. Es el que protege contra el error
histórico (CUIT de Central Puerto atribuido a YPF).

**`ROW(NEW.*) IS DISTINCT FROM ROW(OLD.*)` no alcanza para la inmutabilidad.**
La primera versión del trigger dejaba pasar un `UPDATE` que cambiara
`superseded_by` **y además** otra columna en la misma sentencia. Se corrigió a
comparación explícita de las 17 columnas. El schema se re-aplicó (`DROP SCHEMA`
+ re-migrar) porque estaba vacío.

**El banco adversario encontró un bug que ningún test unitario habría
encontrado.** Ver F-014: `market_instruments.ticker_canonico` repite el ticker
local en la fila del ADR, y el piloto estaba escribiendo `US/YPFD` para un
instrumento de NYSE. Solo aparece al confrontar el modelo con los datos reales
de Market. CEPU y GGAL enmascaran el problema porque su ticker local y su ticker
de NYSE coinciden.

---

## La respuesta a la pregunta del ciclo 3, ahora ejecutable

> ¿Cómo sabe Catalaxia que el CIK X, el CUIT Y y el instrumento Z representan la
> misma entidad económica?

```sql
SELECT * FROM identity_v1.v_entity_resolution;
SELECT * FROM identity_v1.assertion WHERE entity_key = '…';
```

Cada eslabón devuelve `source_id`, `source_record`, `evidence` (cita textual) y
`resolved_by`. Los eslabones que no tienen respaldo devuelven `REVIEW_REQUIRED`
con el motivo escrito. La respuesta **no** depende de SQLite legacy, de joins
implícitos, de nombres, de coincidencia de ticker ni de conocimiento humano no
registrado — y cuando depende de una persona, esa persona está nombrada en la
fila.
