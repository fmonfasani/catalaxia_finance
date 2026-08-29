# IDENTITY V1 — ESQUEMA

**Estado:** aplicado en `catalaxia-engine-dev` (127.0.0.1:5433), schema `identity_v1`
**Migración:** `migrations/engine/008_identity_v1.sql`
**Fecha:** 2026-08-25
**Convive con:** el schema `identity` existente (seeding SEC), que no se modificó ni se leyó en escritura.

---

## 1. Las siete tablas

| Tabla | Qué es | Cardinalidad conceptual |
|---|---|---|
| `source` | Catálogo de fuentes y su **nivel de autoridad por tipo de identificador** | 8 filas (semilla) |
| `entity` | El emisor económico. Clave opaca (ULID) | 1 por emisor |
| `assertion` | **El objeto central.** Una afirmación con autor, fuente y cita | N por entidad |
| `identifier` | Cómo cada fuente nombra a la entidad | N por entidad |
| `instrument` | Lo que se opera (la entidad emite, el instrumento cotiza) | N por entidad |
| `instrument_symbol` | Símbolo del instrumento **dentro de un namespace** | N por instrumento |
| `review` | Cola de resolución humana | N por entidad |
| `conflict` | Ambigüedad explícita, nunca resuelta en silencio | N |

---

## 2. La decisión que sostiene todo el diseño

`assertion` no es una columna de auditoría al costado de `identifier`. Es la tabla
de la que `identifier` **depende con FK NOT NULL**:

```sql
identifier.assertion_id  BIGINT NOT NULL REFERENCES identity_v1.assertion(assertion_id)
```

Consecuencia directa: **no existe forma de escribir un identificador sin escribir
antes quién lo afirmó, con qué fuente y con qué cita.** No hay ruta alternativa,
no hay `DEFAULT`, no hay nullable. La procedencia no es un adorno que se puede
omitir cuando hay apuro: es un prerrequisito de escritura.

---

## 3. La autoridad es propiedad de la FUENTE, no del dato

```sql
source (source_id, authority_level, authoritative_for TEXT[])
```

`authority_level` ∈ `AUTHORITATIVE | CORROBORATING | DISCOVERY_ONLY | UNUSABLE`
`authoritative_for` = para **qué tipos de identificador** esa fuente establece identidad.

Semilla aplicada (cada nivel viene de un ciclo de verificación, no de la documentación del proveedor):

| `source_id` | Nivel | Autoritativa para | Por qué |
|---|---|---|---|
| `SEC_REGISTRY` | AUTHORITATIVE | `CIK` | Es el registro que asigna el CIK. **No publica LEI** (G5: 0/6 en el control) |
| `SEC_20F` | AUTHORITATIVE | `CIK`, `CUIT` | Solo cuando declara bloque de identificación. Cobertura medida: **1/4** (ciclo 3C) |
| `GLEIF` | AUTHORITATIVE | `LEI`, `CUIT` | Solo si `registeredAt` ∈ {RA000009 AFIP, RA000010 IGJ/RNS}. **No establece CIK** (G4/G5) |
| `AFIP` | AUTHORITATIVE | `CUIT` | Máxima autoridad. **No automatizable**: captcha (ciclo 3D) |
| `CNV_PORTAL` | DISCOVERY_ONLY | — | **No declara el CUIT del emisor**, solo el del auditor (ciclo 3D) |
| `LEGACY_DIM_ENTITY` | CORROBORATING | — | Sin autor ni evidencia. Ya falló con el CIK de YPF |
| `HUMAN` | AUTHORITATIVE | — | Capacidad **permanente**, no transitoria (G5) |
| `DERIVED_RULE` | DISCOVERY_ONLY | — | p.ej. el sufijo `.BA` de Yahoo. Nunca establece identidad |

Esto es lo que impide el error de categoría más caro: tomar a GLEIF como
autoridad sobre el CIK porque es "una fuente seria".

---

## 4. Las 14 garantías de integridad

Numeradas como aparecen en la migración. Las marcadas ✔ tienen test explícito.

| # | Garantía | Mecanismo | Test |
|---|---|---|---|
| 1 | No hay `VERIFIED` sin evidencia, fuente y autor | `ck_verified_exige_evidencia` | ✔ 12, adv G |
| 2 | Una decisión humana declara quién y por qué | `ck_humano_exige_autor` | ✔ 10 |
| 3 | Una regla derivada o un import legacy **nunca** son AUTHORITATIVE | `ck_authoritative_metodo` | ✔ adv G |
| 4 | Un puente necesita sus dos extremos | `ck_bridge_dos_extremos` | ✔ 7 |
| 5 | El ticker nunca es identidad jurídica | `ck_ticker_no_autoritativo` | ✔ 8, 12 |
| 6 | **Un identificador autoritativo vigente no puede designar dos entidades** | `ux_identifier_autoritativo_unico` | ✔ 2, 12, adv A |
| 7 | Una entidad no puede tener dos CUIT (o dos CIK) autoritativos vigentes | `ux_entity_un_autoritativo_por_tipo` | ✔ 5, adv B |
| 8 | Un ADR/CEDEAR sin ratio no entra (errores de factor N silenciosos) | `ck_ratio_obligatorio` | — |
| 9 | Un símbolo vigente pertenece a un solo instrumento **dentro de su namespace** | `ux_symbol_vigente` | ✔ 9, adv E |
| 10 | No se cierra una review sin revisor, decisión y motivo | `ck_cierre_exige_reviewer` | ✔ 10 |
| 11 | Un conflicto o está OPEN, o tiene assertion de resolución | `ck_conflict_resolucion` | — |
| 12 | **Las assertions históricas son inmutables** | `tg_assertion_inmutable` | ✔ 11, adv F |
| 13 | No se borra provenance de una assertion vigente | `tg_no_borrar_vigente` | ✔ 11, adv F |
| 14 | Un identificador autoritativo exige assertion `VERIFIED` | `tg_identifier_autoritativo` | ✔ 12 |

Encadenando **1 + 14** se obtiene la garantía dura del sistema:

> No existe en `identity_v1` un identificador autoritativo sin una cita textual
> reproducible por un tercero y sin un responsable nombrado.

### El detalle del trigger 12

La primera versión comparaba `ROW(NEW.*) IS DISTINCT FROM ROW(OLD.*)` con una
excepción para `superseded_by`. Eso dejaba pasar un `UPDATE` que cambiara
`superseded_by` **y además** otra columna en la misma sentencia. La versión
aplicada compara las 17 columnas explícitamente, de modo que en una fila
histórica el único campo mutable es `superseded_by`.

---

## 5. `entity_key`: por qué es opaco

```sql
entity_key TEXT PRIMARY KEY CHECK (entity_key ~ '^E[0-9A-HJKMNP-TV-Z]{26}$')  -- 'E' + ULID
```

Si la clave se derivara del CIK (como hace el sistema actual: `entity_id = 'CIK:0000904851'`),
corregir un CIK mal atribuido obligaría a reescribir cada FK del sistema. La
clave opaca convierte esa corrección en **una assertion nueva**, no en una
migración. `fetch_raw.cnv_presentation.entity_key = 'CIK:0001717161'` es el
acoplamiento que esta decisión existe para deshacer.

---

## 6. Namespaces: `TICKER/US` ≠ `TICKER/BYMA`

Los identificadores llevan `id_namespace` y la unicidad se evalúa **por
namespace**. `TGS` en `YAHOO` y `TGS` en `US` son dos identificadores distintos
y pueden colgar de instrumentos distintos; dos instrumentos no pueden compartir
`YAHOO/TGS` vigente. Es el caso COUR (Coursera) modelado, no parcheado.

---

## 7. Lo que el esquema NO hace

- **No inventa el CUIT.** Si GLEIF no lo publica (GGAL: `RA999999`,
  `registeredAs = null`), queda `REVIEW_REQUIRED` con el motivo escrito.
- **No cierra la arista CIK↔LEI sola.** No existe fuente primaria (G5); el
  puente se registra como `HUMAN_DECISION` con `confidence = STRONG`, nunca
  `AUTHORITATIVE`. El sistema no finge que una fuente lo publica.
- **No toca** el parser SEC, el fetcher de Market ni el de CNV.

---

## 8. Qué estado de entidad puede poseer identidad autoritativa (F-035)

Los estados que el modelo realmente tiene son cuatro (`entity_entity_status_check`).
`REVIEW_REQUIRED`, `CONFLICT` y `REJECTED` **no son estados de entidad**: son estados de
`assertion` y de `conflict`. No se inventan estados de entidad que el modelo no define.

| `entity_status` | ¿puede recibir un identificador AUTORITATIVO nuevo? | Fundamento |
|---|---|---|
| `ACTIVE` | **sí** | es la entidad operativa |
| `PROVISIONAL` | **sí** | existe sin identidad establecida; adquirir un identificador autoritativo es justamente su transición esperada |
| `MERGED` | **no** | su identidad ya migró a `merged_into_key`. Dejarla adquirir identidad nueva la devuelve a la vida por la puerta de atrás, y esa evidencia queda invisible para cualquier consulta que filtre por `ACTIVE` |
| `DISSOLVED` | **no** | dejó de existir. Conserva los identificadores históricos; no adquiere nuevos |

### Dos guardas, no una

1. **Sobre `identifier`** — un identificador autoritativo exige que su entidad esté en
   `ACTIVE` o `PROVISIONAL`. Cubre el INSERT y el UPDATE que active `is_authoritative`.
2. **Sobre `entity`** — una entidad con identificadores autoritativos vigentes **no puede
   pasar a `MERGED`/`DISSOLVED`** sin retirarlos o migrarlos primero. Sin esta segunda
   guarda se llega al mismo estado incoherente por el otro lado: primero se cargan los
   identificadores y después se fusiona.

Ambas son **triggers**, no `CHECK`: la condición depende de otra tabla. Y por eso mismo
resisten la escritura directa — que es como se descubrió F-035.
