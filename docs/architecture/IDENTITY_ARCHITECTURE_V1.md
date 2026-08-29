# IDENTITY ARCHITECTURE v1 — contrato de identidad de Catalaxia

Autor: **CIAA** (Principal Integration Architect) · 2026-08-25 · Ciclo 3
Estado: **DISEÑO — no implementado.** Ningún código, schema, migración ni DB fue modificado.
Baseline de referencia: `catalaxia-baseline-2026-08-25` / `444ee1a`

**Criterio de éxito.** Al terminar, Catalaxia debe poder responder sin ambigüedad:

> *¿Cómo sabe Catalaxia que el CIK X, el CUIT Y y el instrumento Z son la misma entidad económica?*

y la respuesta no puede depender de SQLite legacy, joins implícitos, nombres, coincidencia
de ticker, ni conocimiento humano no registrado.

---

## 0 · Advertencia previa: el enunciado de este ciclo contiene un error de identidad

La especificación de esta tarea afirma, para el caso de referencia:

```
YPF
   SEC    : CIK 0000904851
   CNV    : CUIT 33650305499
   Market : entity_id 72
```

**El CUIT es incorrecto.** Verificado contra los datos:

```
CUIT 33650305499  ->  CIK 0001717161  ->  CENTRAL PUERTO S.A.   (CEPU, entity 70)
CUIT 30546689979  ->  CIK 0000904851  ->  YPF S.A.              (YPFD, entity 72)
```

`33650305499` es el CUIT de **Central Puerto**, la empresa que se usó en la corrida de
prueba de C3. El CIK y el `entity_id 72` sí corresponden a YPF.

Se documenta acá y no en una nota al pie porque **es la mejor justificación disponible de
este diseño**: el error se produjo en la propia especificación, por asociación mental entre
"el CUIT que estábamos usando" y "el caso de referencia". Es exactamente la clase de
`coincidencia accidental` y `conocimiento humano no registrado` que Identity v1 debe hacer
imposible.

**Bajo Identity v1, este error se detecta automáticamente**: afirmar
`CIK:0000904851 ↔ CUIT 33650305499` requiere una aserción con evidencia autoritativa, y no
existe ninguna. La aserción sería rechazada en escritura, no descubierta meses después.

---

## 1 · Problema actual

### 1.1 Lo que ya funciona (y no debe rehacerse)

El modelo existente es **mejor de lo que el finding F-011 sugería**. Medido:

```
identity.entities      entity_id · legal_name · country · cik · cuit · cnv_id · id_source
identity.identifiers   entity_id · id_type · id_value · marketplace · source
                       status · discovered_at · retired_at
identity.identifier_reviews  candidate_values(jsonb) · detected_by_run · reason
                             status · resolved_entity_id · resolved_at · resolved_note
```

Uso real:

```
YF_SYMBOL / yahoo   10.414 ACTIVE
TICKER    / US      10.403 ACTIVE
CIK       / SEC      7.998 ACTIVE
TICKER    / BYMA        11 ACTIVE
```

**El ticker ya NO se trata como identidad.** YPF tiene `TICKER=YPF` en marketplace `US` y
`TICKER=YPFD` en marketplace `BYMA`: mismo emisor, distinto identificador por plaza. El
namespace ya está modelado. La provenance por identificador también (`source`), y la vigencia
también (`status`, `retired_at`).

Ya existe además un flujo de ambigüedad con 4 conflictos abiertos y una doctrina de
precedencia (`EXT-NEW-012: gana la fuente de registro`), y un precedente de resolución
manual con autor y razón epistemica (`engine_identity_resolutions.csv`).

**Identity v1 es una extensión, no un greenfield.**

### 1.2 Las cuatro brechas reales

**B1 · No existe el tipo `CUIT` ni el marketplace `CNV`.**
`identity.entities.cuit` está poblado en **0 de 7.998**. La asociación CUIT↔CIK vive
únicamente en `fetch_raw.cnv_download_log` (columnas `entity_key` + `cuit`, un log de
descargas) y en el SQLite legacy.

**B2 · `entity_key` es CIK-derivado.**
El formato es `CIK:0000904851`. Una entidad argentina sin CIK **no tiene clave posible**.
Esto no es un detalle de formato: es una barrera estructural para el 88 % del universo CNV.

**B3 · No existe capa de Instrumento en el engine.**
Market la tiene (`market_instruments`, con `instrument_type`, `exchange`, `currency`,
`ratio_adr`), pero vive en **otra base** (5432), con `entity_id` **entero** y **sin foreign
key**, referenciando una tabla (`dim_entity`) que sólo existe en SQLite.

**B4 · No existe registro de la aserción del puente.**
Ninguna tabla responde *"¿quién dijo que este CIK corresponde a este CUIT?"*. El puente es
un par de columnas en una fila, sin fuente, sin método, sin confianza, sin fecha.

### 1.3 La magnitud real del puente

```
dim_entity legacy (SQLite)      573 entidades
   con CUIT                      74   (12 %)
   con CIK                      512   (89 %)
   con AMBOS                     13   ( 2 %)   <- TODO el puente CIK<->CUIT del sistema
   CUIT duplicados                0
   CIK duplicados                 0
```

**El puente entre SEC y CNV en todo Catalaxia son 13 filas de un archivo SQLite** que no
está en PostgreSQL, no tiene FK que lo respalde y no registra quién lo afirmó.

### 1.4 El legacy se contradice a sí mismo

No es "el legacy" en singular: son varios catálogos que **discrepan entre ellos**.

```
acciones_argentinas_usa.csv   YPF -> CIK 1104659
dim_entity                    YPF -> CIK 0000904851
SEC company_tickers           YPF -> CIK 0000904851     <- fuente de registro
```

El engine ya resolvió esto correctamente (`EXT-NEW-012`: gana la fuente de registro) y dejó
`identity.identifier_reviews` con 4 conflictos OPEN: **YPF, GGAL, BMA, CRESY** — exactamente
los cuatro CIKs que `RISK_REGISTER` R-16 marca como podridos.

Conclusión que el diseño debe absorber: **la confianza en el legacy debe declararse por
catálogo y por campo, no en bloque.**

---

## 2 · Modelo conceptual

Cuatro conceptos, deliberadamente separados. La regla es que ninguno puede sustituir a otro.

```
                          ┌──────────────────┐
                          │      ENTITY      │   el emisor económico
                          │  (quién emite)   │   ~ persona jurídica
                          └────────┬─────────┘
                    ┌──────────────┼──────────────┐
                    │              │              │
          ┌─────────▼──────┐ ┌─────▼────────┐ ┌───▼────────────┐
          │   IDENTIFIER   │ │  INSTRUMENT  │ │  ASSERTION     │
          │ cómo la nombra │ │ qué se opera │ │ quién afirma   │
          │  cada fuente   │ │  en el mercado│ │ que dos IDs    │
          └────────────────┘ └──────┬───────┘ │ son la misma   │
                                    │         │    entidad     │
                             ┌──────▼──────┐  └────────────────┘
                             │   LISTING   │
                             │ dónde cotiza│
                             └─────────────┘
```

**ENTITY** — el emisor. No tiene nombre canónico "verdadero": tiene un nombre preferido y
un historial. No se identifica por su nombre.

**IDENTIFIER** — cómo una fuente concreta nombra a esa entidad. `CIK 0000904851` es cómo la
SEC llama a YPF; `CUIT 30546689979` es cómo la AFIP/CNV la llama. **Ninguno es "la"
identidad**: los dos son nombres en namespaces distintos.

**INSTRUMENT** — lo que se opera. YPF tiene al menos dos: la acción local en BYMA y el ADR
en NYSE. Distinta moneda, distinto mercado, distinto precio, **mismo emisor**.

**ASSERTION** — el objeto que hoy no existe y que es el corazón de v1. Afirmar que
`CIK 0000904851` y `CUIT 30546689979` son la misma entidad **es un hecho con autor,
evidencia, método y fecha**, no una propiedad intrínseca del dato.

### Por qué la aserción es un objeto de primera clase

Porque la pregunta del criterio de éxito —*"¿cómo sabe Catalaxia…?"*— sólo tiene respuesta si
alguien la escribió. Un `JOIN` no sabe nada; sólo ejecuta. Si el vínculo vive como par de
columnas, la respuesta es "porque alguien lo puso ahí", que es precisamente la respuesta
prohibida.

---

## 3 · Modelo lógico

```
identity.entity                    la entidad económica
   entity_key            PK        opaco, estable, NO derivado de ningún identificador
   preferred_name                  nombre de display; NUNCA clave
   country
   entity_status                   ACTIVE | MERGED | DISSOLVED | PROVISIONAL
   merged_into_key       FK -> entity.entity_key     (si MERGED)
   created_at · updated_at

identity.identifier                cómo cada fuente la nombra
   identifier_id         PK
   entity_key            FK -> entity
   id_type                         CIK | CUIT | TICKER | YF_SYMBOL | CNV_ENTITY_ID | ISIN | LEI
   id_namespace                    SEC | AFIP | CNV | BYMA | US | YAHOO
   id_value
   is_authoritative      bool      ¿es la fuente de registro de ese id_type?
   valid_from · valid_to           historial; NULL en valid_to = vigente
   status                          ACTIVE | RETIRED | DISPUTED
   assertion_id          FK -> assertion    quién afirmó este vínculo

identity.instrument                lo que se opera
   instrument_key        PK        opaco
   entity_key            FK -> entity      NOT NULL
   instrument_type                 EQUITY | ADR | CEDEAR | BOND
   exchange                        BUE | NYSE | NASDAQ
   currency                        ARS | USD
   ratio_underlying                nº de acciones subyacentes por unidad (ADR/CEDEAR)
   valid_from · valid_to
   status

identity.instrument_symbol         cómo cada fuente nombra al instrumento
   instrument_key        FK -> instrument
   id_namespace                    YAHOO | BYMA | US
   symbol                          YPFD.BA · YPF
   valid_from · valid_to

identity.assertion                 EL OBJETO CENTRAL DE v1
   assertion_id          PK
   subject_type                    ENTITY_IDENTIFIER | ENTITY_MERGE | ENTITY_INSTRUMENT
   left_ref · right_ref            los dos extremos afirmados
   method                          REGISTRY | REGULATORY_DOCUMENT | CROSS_REFERENCE
                                   | HUMAN_DECISION | DERIVED_RULE
   confidence                      AUTHORITATIVE | STRONG | WEAK | DISPUTED
   source                          identificador estable de la fuente
   source_record                   puntero a la fila/documento concreto
   evidence                        cita textual o hash del documento
   asserted_by                     quién (persona o proceso)
   asserted_at
   state                           AUTO_MATCH | VERIFIED | REVIEW_REQUIRED | REJECTED
   superseded_by         FK -> assertion

identity.conflict                  ambigüedad explícita, nunca resuelta en silencio
   conflict_id           PK
   id_type · id_value · id_namespace
   candidate_entity_keys jsonb     las entidades en disputa
   detected_by_run
   reason
   state                           OPEN | RESOLVED | ACCEPTED_AMBIGUOUS
   resolution_assertion_id FK -> assertion
```

### Compatibilidad con lo existente

`identity.identifiers` actual ya cubre `id_type`, `marketplace`, `source`, `status`,
`discovered_at`, `retired_at`. La migración a `identity.identifier` es **aditiva**:
`marketplace → id_namespace`, y se agregan `is_authoritative`, `valid_from`, `assertion_id`.
`identity.identifier_reviews` es el ancestro directo de `identity.conflict`.

---

## 4 · Entidades y relaciones

```
entity 1 ──── N identifier          una entidad, muchos nombres
entity 1 ──── N instrument          una entidad, muchos instrumentos
instrument 1 ─ N instrument_symbol  un instrumento, muchos símbolos por fuente
assertion 1 ── N identifier         una aserción respalda uno o más vínculos
entity N ──── 1 entity              merge: merged_into_key
conflict N ─── 1 assertion          la resolución del conflicto es una aserción
```

**Cardinalidades que el diseño prohíbe explícitamente:**

- Un `identifier` **autoritativo** vigente no puede apuntar a dos `entity` distintas.
  (Un CIK identifica a un emisor y sólo uno.)
- Un `instrument` no puede existir sin `entity`.
- Un `identifier` no puede existir sin `assertion` que lo respalde.

**Cardinalidades que el diseño sí permite, porque la realidad las tiene:**

- Una entidad con **varios CUIT observados** — sucede (revisión `C1-R-002`: Central Vuelta
  de Obligado con 3 CUITs). Se modela como varios `identifier` de tipo CUIT, ninguno
  `is_authoritative`, y un `conflict` abierto.
- Una entidad **sin CIK** — el 88 % del universo CNV.
- Un identificador **retirado** que fue válido en el pasado (ticker histórico).

---

## 5 · Identifier namespaces

Un identificador **sin namespace no significa nada**. `YPF` es a la vez ticker en NYSE y
símbolo Yahoo; `YPFD` es ticker BYMA. Sin namespace son colisiones esperando ocurrir — que
es exactamente lo que produjo el bug `COUR → Coursera` en el pipeline legacy.

| id_type | namespace | Autoritativo | Fuente de registro | Formato |
|---|---|---|---|---|
| `CIK` | `SEC` | **Sí** | SEC EDGAR company_tickers | 10 dígitos con ceros |
| `CUIT` | `AFIP` | **Sí** | Constancia AFIP | 11 dígitos, dígito verificador |
| `CNV_ENTITY_ID` | `CNV` | No | Portal CNV | según CNV |
| `TICKER` | `US` | No | SEC / exchange | alfanumérico |
| `TICKER` | `BYMA` | No | BYMA | alfanumérico |
| `YF_SYMBOL` | `YAHOO` | No | derivado por regla | con sufijo `.BA` si BYMA |
| `ISIN` | `ISO` | **Sí** | agencia numeradora | ISO 6166 |
| `LEI` | `GLEIF` | **Sí** | GLEIF | ISO 17442 |

**Regla de autoridad.** Sólo los identificadores marcados `is_authoritative` pueden fundar
una aserción `AUTHORITATIVE`. `TICKER` y `YF_SYMBOL` **nunca** son autoritativos: son
etiquetas de mercado, mutables y reutilizables. Un ticker liberado puede reasignarse a otra
empresa; un CIK no.

**Nota sobre `CUIT`:** su dígito verificador permite validación sintáctica, lo que le da una
propiedad que el CIK no tiene: se puede detectar un CUIT malformado sin consultar la fuente.
Eso lo hace apto para un check barato de primera línea, **pero un CUIT sintácticamente
válido no prueba pertenencia** — sólo descarta errores de tipeo.

---

## 6 · Entity key strategy

### El problema con la clave actual

`CIK:0000904851` incrusta un identificador en la clave. Consecuencias:

- Una entidad **sin CIK no tiene clave** (88 % del universo CNV).
- Si el CIK resulta equivocado —y ya pasó: los 4 conflictos OPEN— **la clave primaria queda
  contaminada** y corregirla exige migrar todas las FK.
- Sugiere que la SEC es la autoridad universal de identidad, lo que es falso para una
  empresa argentina sin emisión en EE.UU.

### Decisión: clave opaca

```
entity_key := "E" + <ULID>
por ejemplo   E01J9ZQK7X8M2N4P6R8T0V2W4Y
```

**Opaca, estable, sin semántica.** No se deriva de ningún identificador, por lo tanto:
sobrevive a la corrección de cualquier identificador, existe para entidades sin CIK y no
privilegia a ninguna fuente.

Se elige ULID sobre UUIDv4 por ser ordenable temporalmente (facilita debugging y particionado)
conservando opacidad. **Es una decisión reversible**: cualquier identificador opaco sirve.

### Coexistencia durante la transición

`entity_key` es nuevo; `entity_id` (`CIK:xxx`) se conserva como **alias legacy** en
`identity.identifier` con `id_type='LEGACY_ENTITY_ID'`, para que nada que hoy lo referencie
se rompa y para que la migración sea auditable. Se retira cuando ningún consumidor lo use.

---

## 7 · Instrument strategy

**La entidad emite; el instrumento se opera.** Confundirlos es el error que hace que un
screener muestre dos precios para "la misma empresa" sin poder explicar por qué difieren.

YPF, correctamente modelado:

```
entity  E01J9…  YPF S.A.
   ├── instrument  I_ypfd_bue   EQUITY  BUE   ARS   ratio=1
   │      └── symbol  YAHOO:YPFD.BA · BYMA:YPFD
   └── instrument  I_ypf_nyse   ADR     NYSE  USD   ratio=1
          └── symbol  YAHOO:YPF · US:YPF
```

Market **ya modela esto bien**: sus instrumentos 83 y 84 comparten `entity_id=72` con
`ratio_adr=1.0`. La brecha no es conceptual sino de ubicación e integridad: viven en otra
base, con clave entera y sin FK.

**`ratio_underlying` es obligatorio para ADR/CEDEAR** y no puede omitirse: sin él, comparar
el precio del ADR con el de la acción local produce un error silencioso de factor N. Es el
mismo tipo de defecto que el `MarketCapUSD` que contenía pesos.

**Regla de moneda.** La moneda es propiedad del **instrumento**, no de la entidad. Una
entidad puede tener moneda funcional USD y un instrumento que cotiza en ARS — es el caso de
YPF y no es una inconsistencia. Cualquier conversión debe ser explícita, nombrada y con su
fuente de tipo de cambio declarada.

---

## 8 · Source identity strategy

Cada workstream mantiene su identidad nativa. **Identity v1 no le pide a nadie que cambie
su clave interna**: le pide que la declare.

```
SEC     nativo: CIK              -> identifier(CIK, SEC, is_authoritative=true)
        filing identity: accession_number -> pertenece al dominio SEC, NO a identity;
        se relaciona con entity vía el CIK del filing

CNV     nativo: CUIT + CNV_ENTITY_ID
        presentación (GUID)      -> dominio CNV; se relaciona vía CUIT
        CNV declara relaciones CONTROLADA/VINCULADA entre emisores:
           NO son identidad, son estructura societaria -> identity.relation (futuro)

MARKET  nativo: instrument       -> identity.instrument + instrument_symbol
        Yahoo symbol             -> instrument_symbol(YAHOO)
        BYMA ticker              -> instrument_symbol(BYMA)
```

**Distinción crítica que v1 debe preservar:** una relación `CONTROLADA` entre dos emisores
CNV **no** los convierte en la misma entidad. Son dos entidades con un vínculo societario.
Fusionarlas destruiría el perímetro contable. Esto merece su propio objeto
(`identity.relation`), fuera del alcance de v1 pero reservado en el modelo.

---

## 9 · Bridge SEC / CNV / Market

### La pregunta que hay que poder responder

> *¿Cómo sabe Catalaxia que CIK 0000904851, CUIT 30546689979 y el instrumento YPFD.BA son la
> misma entidad económica?*

**Respuesta bajo v1:** porque existe una fila en `identity.assertion` que lo afirma, con
método, fuente, evidencia, autor y fecha. Y si no existe, **Catalaxia no lo sabe** — y debe
decirlo en vez de inferirlo.

### Jerarquía de evidencia para un bridge

| Nivel | Método | Ejemplo | Confianza | Estado inicial |
|---|---|---|---|---|
| 1 | `REGISTRY` | La SEC publica el CUIT en el 20-F; AFIP publica el CIK | `AUTHORITATIVE` | `AUTO_MATCH` |
| 2 | `REGULATORY_DOCUMENT` | El propio 20-F/EEFF declara ambos identificadores en portada | `AUTHORITATIVE` | `AUTO_MATCH` |
| 3 | `CROSS_REFERENCE` | ISIN o LEI compartido entre ambos registros | `STRONG` | `AUTO_MATCH` |
| 4 | `HUMAN_DECISION` | Persona con acceso a la constancia, dejando cita | `STRONG` | `VERIFIED` |
| 5 | `DERIVED_RULE` | Regla determinista y documentada (p. ej. sufijo `.BA`) | `WEAK` | `REVIEW_REQUIRED` |

**Inadmisible como fundamento de bridge, en cualquier nivel:**
coincidencia de nombre · similitud de nombre (fuzzy) · coincidencia de ticker ·
proximidad de sector o país · que "no haya otro candidato".

La revisión `C1-R-005` de CNV ya aplica este criterio correctamente: rechazó vincular
*Transportadora de Gas del Mercosur* con TGNO4/TGSU2 pese a la semejanza de nombre, porque
los CUIT no coinciden. **Esa decisión es el estándar** y v1 la codifica.

### Lo que cada bridge exige

```
assertion
   left  : identifier(CIK,  SEC,  0000904851)
   right : identifier(CUIT, AFIP, 30546689979)
   method / confidence / source / source_record / evidence / asserted_by / asserted_at
   state
```

**Sin `evidence` no hay bridge.** Un bridge sin evidencia no se guarda como bridge débil:
**no se guarda**. Se guarda como `conflict` en estado `OPEN`.

### El caso Market

Market no aporta identidad: aporta **instrumentos**. Su vínculo con la entidad se establece
por el símbolo, y el símbolo **no es autoritativo**. Por lo tanto:

```
instrument_symbol(YAHOO, 'YPFD.BA')  ->  instrument I_ypfd_bue  ->  entity E01J9…
```

requiere una aserción de nivel 4 o 5. Hoy existe exactamente ese precedente, y es correcto:

```
engine_identity_resolutions.csv
  TICKER,YPFD,BYMA,CIK:0000904851,
  "Confirmacion humana 2026-08-23 (instruccion del propietario del proyecto):
   YPF cotiza en BYMA bajo el ticker YPFD;
   pendiente contraste documental cuando entre fuente BYMA", federico
```

Tiene autor, fecha, método y **declara su propia provisionalidad**. Bajo v1 se registra como
`HUMAN_DECISION` / `STRONG` / `VERIFIED`, con una nota de re-verificación pendiente. Es el
modelo a seguir, no una deuda.

---

## 10 · YPF walkthrough

Con los datos **verificados**, no con los del enunciado.

### Estado bajo v1

```
entity  E01J9ZQK7X8M2N4P6R8T0V2W4Y
        preferred_name : YPF S.A.
        country        : AR
        status         : ACTIVE

identifiers
   CIK          SEC    0000904851     authoritative  ACTIVE   <- a1
   CUIT         AFIP   30546689979    authoritative  ACTIVE   <- a2   (NO 33650305499)
   TICKER       US     YPF                           ACTIVE   <- a3
   TICKER       BYMA   YPFD                          ACTIVE   <- a4
   YF_SYMBOL    YAHOO  YPF                           ACTIVE   <- a5
   YF_SYMBOL    YAHOO  YPFD.BA                       ACTIVE   <- a6
   LEGACY_ENTITY_ID —  CIK:0000904851                ACTIVE   (alias de transición)
   LEGACY_ENTITY_ID —  72                            ACTIVE   (alias Market)

instruments
   I_ypfd_bue   EQUITY  BUE   ARS  ratio=1   symbols: YAHOO:YPFD.BA · BYMA:YPFD
   I_ypf_nyse   ADR     NYSE  USD  ratio=1   symbols: YAHOO:YPF     · US:YPF
```

### Las aserciones que lo sostienen

```
a1  CIK 0000904851
    method REGISTRY · confidence AUTHORITATIVE · state AUTO_MATCH
    source sec_company_tickers:company_tickers_2026-08-23.json
    evidence "YPF SOCIEDAD ANONIMA -> CIK 0000904851"

a2  CUIT 30546689979                        <-- NO EXISTE HOY
    method ? · confidence ? · state REVIEW_REQUIRED
    El único origen es dim_entity (SQLite legacy), SIN autor ni evidencia.
    Bajo v1 NO califica como AUTHORITATIVE: entra como conflicto abierto
    hasta contrastar contra el 20-F o una constancia AFIP.

a4  TICKER YPFD / BYMA
    method HUMAN_DECISION · confidence STRONG · state VERIFIED
    asserted_by federico · 2026-08-23
    evidence "instrucción del propietario; pendiente contraste documental"

a6  YF_SYMBOL YPFD.BA
    method DERIVED_RULE · confidence WEAK
    evidence "yf_rule_byma_suffix:v1 aplicado sobre TICKER/BYMA=YPFD"
    Derivado de a4: si a4 cae, a6 cae con él.
```

### Lo que este walkthrough revela

**Hoy, el vínculo CIK↔CUIT de YPF no es demostrable.** Existe en `dim_entity`, pero sin
autor, sin evidencia y sin método. Bajo v1 **no sería un bridge**: sería un
`REVIEW_REQUIRED`.

Eso **no significa que sea incorrecto** — probablemente es correcto. Significa que hoy
Catalaxia no puede demostrarlo, y v1 obliga a distinguir *"es cierto"* de *"podemos
demostrar que es cierto"*.

Y el conflicto abierto refuerza el punto: `identity.identifier_reviews` registra que un
catálogo legacy afirmaba `YPF → CIK 1104659`, contradiciendo a la fuente de registro. **El
legacy ya se equivocó una vez con la identidad de YPF.** Aceptar su CUIT sin contraste sería
confiar en la misma fuente que ya falló.

---

## 11 · Apple walkthrough

El caso simple, para mostrar que v1 no impone fricción donde no hace falta.

```
entity  E01J9…APPL
        preferred_name : Apple Inc. · country US · ACTIVE

identifiers
   CIK        SEC    0000320193   authoritative  ACTIVE
   TICKER     US     AAPL                        ACTIVE
   YF_SYMBOL  YAHOO  AAPL                        ACTIVE

instruments
   I_aapl_nasdaq  EQUITY  NASDAQ  USD  ratio=1
                  symbols: YAHOO:AAPL · US:AAPL
```

**Sin CUIT, sin bridge, sin review.** Apple no tiene presencia CNV, así que no hay puente que
demostrar. Toda su identidad proviene de una única fuente de registro y todas sus aserciones
son `REGISTRY / AUTHORITATIVE / AUTO_MATCH`.

**Lección de diseño:** el 93 % del universo (7.998 entidades SEC) se resuelve automáticamente
sin intervención humana. El costo de v1 se concentra donde hay ambigüedad real: el cruce
argentino. Un diseño que impusiera revisión manual universal sería inaplicable a 8.000
entidades — v1 no lo hace.

---

## 12 · Ambiguity / review workflow

### Taxonomía de estados

| Estado | Significado | Quién lo produce | ¿Publicable? |
|---|---|---|---|
| `AUTO_MATCH` | Fuente de registro o documento regulatorio | proceso | **Sí** |
| `VERIFIED` | Decisión humana con evidencia citada | persona | **Sí** |
| `REVIEW_REQUIRED` | Evidencia insuficiente o candidatos múltiples | proceso | **No** |
| `REJECTED` | Se evaluó y se determinó que **no** son la misma entidad | persona | **No** (y bloquea reintentos) |
| `ACCEPTED_AMBIGUOUS` | Ambigüedad real e irresoluble, aceptada explícitamente | persona | **Parcial**, marcado |

### Por qué `REJECTED` y `ACCEPTED_AMBIGUOUS` son necesarios

**`REJECTED`** impide que un candidato descartado vuelva a proponerse en cada corrida. Sin
él, `C1-R-005` (TGM vs TGNO4/TGSU2) reaparecería indefinidamente y alguien terminaría
aceptándolo por fatiga. Un rechazo es conocimiento, y debe persistirse como tal.

**`ACCEPTED_AMBIGUOUS`** existe porque hay ambigüedad **genuinamente irresoluble** con las
fuentes disponibles. `C1-R-002` es el caso: Central Vuelta de Obligado presenta 3 CUITs, los
tres devuelven una página genérica, ninguno tiene perfil propio. Forzar una resolución sería
inventar identidad. La decisión correcta —ya tomada por CNV— es **mantener el grupo con
3 identificadores observados** y no crear entidades.

v1 le da un estado a esa decisión para que sea auditable en vez de quedar en un campo de
texto.

### Flujo

```
identificador nuevo detectado
        │
        ├─ ¿fuente de registro?          -> AUTO_MATCH        -> publicable
        ├─ ¿documento regulatorio?       -> AUTO_MATCH        -> publicable
        ├─ ¿ISIN/LEI compartido?         -> AUTO_MATCH (STRONG)
        ├─ ¿regla derivada determinista? -> REVIEW_REQUIRED   -> cola humana
        └─ nada de lo anterior           -> conflict OPEN     -> cola humana
                                                │
                              ┌─────────────────┼──────────────────┐
                        VERIFIED            REJECTED        ACCEPTED_AMBIGUOUS
                     (con evidencia)   (con fundamento)   (con justificación)
```

**Regla dura:** un `conflict` en `OPEN` **nunca** se degrada a match automático por
antigüedad, por falta de alternativas ni por presión de completitud. La ausencia de decisión
no es una decisión.

---

## 13 · Legacy migration strategy

### Qué contiene realmente el legacy

```
dim_entity (SQLite screener.db)         573 filas
   entity_id · cuit · cik · ticker_canonico · nombre
   grupo · moneda_funcional · fy_end_month · es_financiera

   con CUIT       74  (12 %)
   con CIK       512  (89 %)
   con AMBOS      13  ( 2 %)   <- el bridge completo del sistema
   duplicados      0            <- internamente consistente

acciones_argentinas_usa.csv             CONTRADICE a dim_entity en al menos 4 CIKs
```

### Clasificación por campo

| Campo | Destino | Confianza inicial | Fundamento |
|---|---|---|---|
| `cik` | **Descartar** | — | La fuente de registro SEC ya lo provee y es superior. El legacy ya falló acá (4 conflictos). |
| `cuit` | **Migrar como candidato** | `REVIEW_REQUIRED` | Es información que **no existe en ninguna otra parte**. Valiosa, no confiable. |
| `ticker_canonico` | Migrar como identifier no autoritativo | `WEAK` | Sin namespace declarado; hay que inferir plaza. |
| `nombre` | Migrar como `preferred_name` inicial | — | Display, nunca clave. |
| `moneda_funcional` | Migrar a `entity` | `WEAK` | Verificable contra EEFF. |
| `fy_end_month` | Migrar a `entity` | `WEAK` | Verificable contra filings. |
| `es_financiera`, `grupo` | **No es identidad** | — | Clasificación → `identity.classification`. |

**El criterio es asimétrico a propósito:** el CIK legacy se descarta porque existe una fuente
mejor y el legacy ya demostró estar equivocado; el CUIT legacy se conserva porque es la única
fuente que lo tiene, pero **entra como candidato, no como hecho**.

### Cómo se evita la dependencia implícita

1. **Migración única y fechada.** Se copia una vez, con `source='legacy_dim_entity@<sha256>'`
   y la fecha. El sha del archivo queda registrado.
2. **Ninguna lectura en runtime.** Ningún proceso vuelve a abrir el SQLite. Si el archivo
   desaparece, nada se rompe.
3. **Provenance por identificador migrado.** Cada uno arrastra una aserción
   `method=LEGACY_IMPORT`, `confidence=WEAK`, `state=REVIEW_REQUIRED`, `evidence` con la fila
   original literal.
4. **Test de corte.** Un test de integración verifica que ningún módulo importe
   `screener.db`. Es la única garantía real de que la dependencia se cortó.

### El caso Market

`market_instruments.entity_id` (entero, sin FK, apuntando a `dim_entity`) **no se migra como
clave**: se conserva como `LEGACY_ENTITY_ID` y se reemplaza por `instrument_key`/`entity_key`.
Mientras Market siga en otra base física, el vínculo se materializa mediante un artefacto
explícito de sincronización, **nunca por join implícito** — que hoy además es imposible.

---

## 14 · Provenance

Todo vínculo responde seis preguntas. Si alguna queda sin respuesta, el vínculo **no es
publicable**.

| Pregunta | Campo |
|---|---|
| ¿Quién lo afirma? | `asserted_by` |
| ¿Con qué fundamento? | `method` |
| ¿De dónde salió? | `source` + `source_record` |
| ¿Qué dice exactamente? | `evidence` |
| ¿Cuánto vale? | `confidence` |
| ¿Cuándo? | `asserted_at` |

**`evidence` debe ser verificable por un tercero**: cita textual, número de página, o hash del
documento. *"Coincide el nombre"* no es evidencia. *"El 20-F de 2024, portada, declara
CUIT 30-54668997-9"* sí lo es.

### Provenance derivada

Cuando una aserción se apoya en otra (`YPFD.BA` deriva de `TICKER/BYMA=YPFD`), la dependencia
se registra. **Si la aserción base se invalida, las derivadas se marcan automáticamente para
revisión.** Sin esto, corregir un ticker dejaría símbolos huérfanos apuntando a la entidad
equivocada — el mismo mecanismo que produjo la colisión `COUR → Coursera`.

---

## 15 · Constraints / FKs

Restricciones que hacen **estructuralmente imposible** el defecto, en vez de confiar en que
el proceso se porte bien.

```sql
-- 1 · Ningún instrumento sin entidad
ALTER TABLE identity.instrument
  ADD CONSTRAINT fk_instrument_entity
  FOREIGN KEY (entity_key) REFERENCES identity.entity(entity_key);
ALTER TABLE identity.instrument ALTER COLUMN entity_key SET NOT NULL;

-- 2 · Ningún identificador huérfano
ALTER TABLE identity.identifier
  ADD CONSTRAINT fk_identifier_entity
  FOREIGN KEY (entity_key) REFERENCES identity.entity(entity_key);

-- 3 · Ningún identificador sin aserción que lo respalde
ALTER TABLE identity.identifier ALTER COLUMN assertion_id SET NOT NULL;
ALTER TABLE identity.identifier
  ADD CONSTRAINT fk_identifier_assertion
  FOREIGN KEY (assertion_id) REFERENCES identity.assertion(assertion_id);

-- 4 · Un identificador AUTORITATIVO vigente no puede apuntar a dos entidades
CREATE UNIQUE INDEX ux_identifier_authoritative
  ON identity.identifier (id_type, id_namespace, id_value)
  WHERE is_authoritative AND valid_to IS NULL;

-- 5 · Una entidad no puede tener dos identificadores autoritativos del mismo tipo
CREATE UNIQUE INDEX ux_entity_one_authoritative_per_type
  ON identity.identifier (entity_key, id_type, id_namespace)
  WHERE is_authoritative AND valid_to IS NULL;

-- 6 · Sólo estados publicables pueden sostener un identificador ACTIVE
ALTER TABLE identity.identifier ADD CONSTRAINT ck_identifier_publishable CHECK (
  status <> 'ACTIVE' OR assertion_id IN (
     SELECT assertion_id FROM identity.assertion
     WHERE state IN ('AUTO_MATCH','VERIFIED')));
  -- si el motor no admite subquery en CHECK -> trigger equivalente

-- 7 · Toda aserción publicable exige evidencia
ALTER TABLE identity.assertion ADD CONSTRAINT ck_assertion_evidence CHECK (
  state NOT IN ('AUTO_MATCH','VERIFIED')
  OR (evidence IS NOT NULL AND source IS NOT NULL AND asserted_by IS NOT NULL));

-- 8 · Un símbolo no puede pertenecer a dos instrumentos a la vez
CREATE UNIQUE INDEX ux_symbol_vigente
  ON identity.instrument_symbol (id_namespace, symbol)
  WHERE valid_to IS NULL;

-- 9 · ADR/CEDEAR exigen ratio
ALTER TABLE identity.instrument ADD CONSTRAINT ck_ratio_adr CHECK (
  instrument_type NOT IN ('ADR','CEDEAR') OR ratio_underlying IS NOT NULL);

-- 10 · Un conflicto OPEN no puede tener resolución, y uno resuelto debe tenerla
ALTER TABLE identity.conflict ADD CONSTRAINT ck_conflict_resolution CHECK (
  (state = 'OPEN' AND resolution_assertion_id IS NULL)
  OR (state <> 'OPEN' AND resolution_assertion_id IS NOT NULL));
```

**El constraint 4 es el que hace imposible el error del enunciado.** Intentar afirmar
`CUIT 33650305499 → YPF` cuando ya está afirmado `CUIT 33650305499 → Central Puerto` viola
el índice único y **la escritura falla**. No hay forma de que dos entidades compartan un CUIT
autoritativo vigente.

**El constraint 7 impide el falso PASS por ausencia de datos** — el mismo modo de falla que
`C-C3-007` (F-003/F-007): un estado publicable sin evidencia no es representable.

---

## 16 · Failure modes

| # | Modo de falla | Cómo lo previene v1 | Precedente real |
|---|---|---|---|
| 1 | Ticker reasignado a otra empresa | `TICKER` nunca autoritativo; `valid_to` cierra el período | `COUR → Coursera` |
| 2 | Mismo CUIT en dos entidades | Constraint 4 rechaza la escritura | **el error del enunciado** |
| 3 | Match por nombre parecido | `method` no admite similitud como fundamento | `C1-R-005` TGM vs TGNO4 |
| 4 | Identidad inventada para completar | Constraint 3 y 7: sin aserción con evidencia no hay identificador | `C1-R-001/002` |
| 5 | CIK legacy equivocado | Fuente de registro gana; legacy entra como `WEAK` | 4 conflictos OPEN |
| 6 | Instrumento sin emisor | Constraint 1 con `NOT NULL` | — |
| 7 | ADR comparado sin ratio | Constraint 9 | `MarketCapUSD` con pesos |
| 8 | Bridge sin autor | Constraint 7 | `dim_entity`: 13 filas sin autor |
| 9 | Conflicto que se degrada solo | `OPEN` nunca transiciona automáticamente | — |
| 10 | Corrección que deja derivados huérfanos | Provenance derivada marca dependientes | `YPFD.BA` depende de `YPFD` |
| 11 | Legacy como dependencia implícita | Import único + test de corte | `m1_symbol_mapping` lee SQLite |
| 12 | Fusión societaria tratada como identidad | `CONTROLADA/VINCULADA` → `relation`, no merge | CNV declara 78 relaciones |

---

## 17 · Reconciliation strategy

La identidad **no es estática**: las empresas se fusionan, cambian de razón social, emiten
nuevos instrumentos y retiran tickers. v1 necesita reconciliación periódica, no sólo carga
inicial.

**Reconciliación de fuente de registro.** Cada vez que se refresca `company_tickers` de la
SEC, se compara contra los identificadores vigentes. Un CIK que desapareció del registro se
marca `DISPUTED` (no se borra: puede ser un error transitorio del proveedor). Un CIK nuevo
para una entidad existente abre un conflicto.

**Cambio de razón social.** `preferred_name` se actualiza; el nombre anterior se conserva en
el historial. **La entidad no cambia**: es la misma persona jurídica con otro nombre. Esto es
posible precisamente porque la clave es opaca.

**Fusión.** Cuando A absorbe a B, B pasa a `entity_status=MERGED` con
`merged_into_key = A`. Los identificadores de B **no se borran**: se cierran con `valid_to`.
Un hecho económico histórico atribuido a B sigue siendo correcto para su fecha.

**Reconciliación de instrumentos.** Un símbolo que deja de existir en Yahoo se cierra con
`valid_to`, no se borra. La serie histórica de precios sigue siendo válida para su período.

**Cadencia sugerida:** registro SEC con cada refresco de catálogo; conflictos OPEN revisados
antes de cada gate de etapa; instrumentos con cada corrida de discovery de Market.

---

## 18 · Migration phases

Cinco fases, cada una con reversión posible. **Ninguna se implementa en este ciclo.**

**Fase 0 — Esquema, sin datos.** Crear `identity.entity`, `identifier`, `instrument`,
`instrument_symbol`, `assertion`, `conflict` con todos los constraints. Vacías. El esquema
actual sigue operando sin cambios. *Reversible: drop.*

**Fase 1 — Backfill SEC.** Migrar las 7.998 entidades desde la fuente de registro, generando
`entity_key` opaco y aserciones `REGISTRY/AUTHORITATIVE/AUTO_MATCH`. Conservar el
`entity_id` viejo como `LEGACY_ENTITY_ID`. *Verificación: 7.998 entidades, 7.998 CIK
autoritativos, 0 conflictos nuevos.*

**Fase 2 — Import legacy como candidatos.** Migrar los 74 CUIT de `dim_entity` como
identificadores `WEAK/REVIEW_REQUIRED`, con `evidence` = la fila original y `source` = sha256
del archivo. **Ningún CUIT queda autoritativo.** Los 13 bridges quedan como conflictos
abiertos a resolver. *Verificación: 74 CUIT candidatos, 0 autoritativos, 13 conflictos.*

**Fase 3 — Instrumentos.** Crear la capa de instrumento en el engine y poblarla desde
`market_instruments`, estableciendo FK real. Market pasa a consumir `instrument_key`.
*Verificación: 584 instrumentos, 0 sin entidad, 0 ADR sin ratio.*

**Fase 4 — Resolución de bridges.** Trabajar la cola de conflictos con evidencia
documental (20-F, EEFF, constancias). Cada resolución produce una aserción. *Verificación:
todo bridge publicable tiene `evidence`, `source` y `asserted_by`.*

**Fase 5 — Corte del legacy.** Test de integración que falla si algún módulo importa
`screener.db`. *Verificación: la suite pasa con el archivo renombrado.*

**Regla de corte entre fases:** ninguna fase avanza con conflictos `OPEN` que afecten a las
entidades que esa fase publica.

---

## 19 · Open decisions

Decisiones que **corresponden al arquitecto o al humano**, no al auditor. Se registran con
su trade-off, sin elegir.

**D-I-01 · Formato de `entity_key`.** ULID (ordenable, opaco) vs UUIDv4 (estándar, sin orden)
vs secuencial con prefijo (legible, acopla al orden de inserción). *Recomendación:* ULID.
*Reversible.*

**D-I-02 · ¿`CUIT` autoritativo sin constancia AFIP?** Estricto (sólo AFIP o documento
regulatorio) deja los 74 CUIT legacy como candidatos indefinidamente. Pragmático (aceptar el
CUIT declarado en EEFF publicados en CNV) resuelve la mayoría. *Impacto alto sobre el
esfuerzo de Fase 4.*

**D-I-03 · ¿Dónde vive Identity?** Sólo en 5433 con Market consumiendo por artefacto
explícito, o replicado. Depende de F-001. *Bloqueante para Fase 3.*

**D-I-04 · ¿ISIN/LEI como puente de nivel 3?** Resolvería bridges sin intervención humana,
pero exige incorporar una fuente nueva. *Costo vs cobertura.*

**D-I-05 · ¿Qué hacer con `ACCEPTED_AMBIGUOUS` aguas abajo?** ¿Se publica marcada, se excluye
del screener, o se agrupa? Afecta a los grupos de `C1-R-002`.

**D-I-06 · Umbral de `REVIEW_REQUIRED` para reglas derivadas.** El sufijo `.BA` es
determinista; ¿basta para `AUTO_MATCH` o siempre exige confirmación?

---

## 20 · Acceptance criteria

Identity v1 está implementado cuando **todo** lo siguiente es verificable por un tercero sin
conocimiento previo:

**AC-1 · La pregunta central tiene respuesta ejecutable.**
```sql
SELECT a.method, a.confidence, a.source, a.evidence, a.asserted_by, a.asserted_at, a.state
FROM identity.assertion a
JOIN identity.identifier i1 ON i1.assertion_id = a.assertion_id
JOIN identity.identifier i2 ON i2.entity_key   = i1.entity_key
WHERE i1.id_type='CIK' AND i1.id_value='0000904851'
  AND i2.id_type='CUIT';
```
Devuelve la evidencia, o **no devuelve nada** — y esa ausencia es la respuesta correcta
cuando el bridge no está demostrado.

**AC-2 · Ninguna respuesta depende del legacy.** Renombrar `screener.db` no rompe ninguna
consulta de identidad. Verificado por test.

**AC-3 · Ningún identificador publicable carece de evidencia.**
`SELECT COUNT(*) FROM identity.identifier i JOIN identity.assertion a USING(assertion_id)
WHERE i.status='ACTIVE' AND (a.evidence IS NULL OR a.asserted_by IS NULL)` = **0**.

**AC-4 · El error del enunciado es imposible.** Insertar
`CUIT 33650305499 → entidad YPF` como autoritativo **falla** por constraint mientras exista
`CUIT 33650305499 → Central Puerto`.

**AC-5 · Ningún instrumento huérfano.** 0 instrumentos sin `entity_key`; 0 ADR/CEDEAR sin
`ratio_underlying`.

**AC-6 · Ninguna entidad con dos identificadores autoritativos del mismo tipo vigentes.**

**AC-7 · Todo conflicto tiene estado explícito.** Ningún identificador `ACTIVE` proviene de
un conflicto `OPEN`.

**AC-8 · El ticker no es identidad.** Existe al menos una entidad con el mismo `TICKER` en
dos namespaces apuntando a instrumentos distintos, y al menos un ticker retirado con
`valid_to` poblado.

**AC-9 · Trazabilidad de derivados.** Invalidar `TICKER/BYMA=YPFD` marca automáticamente
`YF_SYMBOL=YPFD.BA` para revisión.

**AC-10 · Apple no requiere intervención.** Una entidad sólo-SEC se resuelve de punta a punta
sin cola de revisión.

---

## Alcance de este documento

**Diseño exclusivamente.** No se modificó código, `schema.prisma`, migraciones, base de
datos, pipelines ni STATE de ningún workstream. No se diseñaron Canonical Economic Facts,
ratios, S04 ni Market M23.

Los datos citados provienen de verificación read-only realizada en los ciclos AUDIT-01,
AUDIT-02 y este ciclo de diseño.
