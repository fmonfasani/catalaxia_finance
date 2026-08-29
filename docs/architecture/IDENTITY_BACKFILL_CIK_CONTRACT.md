# CONTRATO — BACKFILL DEL UNIVERSO CIK EN IDENTITY V1

**Fecha:** 2026-08-28 (ciclo 8, fase B) · **Escrito antes de modificar dato alguno.**

---

## 0. La regla central

> **Un CIK autoritativo permite anclar la entidad. Nada más.**
>
> No implica CUIT. No implica LEI. No autoriza a fusionar por nombre, ticker,
> domicilio ni similitud textual.

Todo lo demás en este contrato son consecuencias de esa frase.

---

## 1. Universo elegible

Entidades del legacy `dim_entity` con un **CIK que SEC declare como suyo**, y
sólo ellas. El número se **mide contra la base** (fase C); no se presupone 512
ni ningún otro.

**Explícitamente fuera:** los emisores BYMA sin CIK. No es una postergación de
conveniencia: sin CIK no hay ancla autoritativa, y el contrato no tiene forma de
darles una sin inferir. Se documentan en `BYMA_BLOCKED_DOSSIER.json` (fase J).

## 2. Qué significa «CIK autoritativo»

Un CIK es autoritativo cuando **SEC lo declara**, verificado contra un artefacto
primario ya materializado en `data/raw/`:

- `data/raw/catalogo_edgar/company_tickers*.json` — el catálogo oficial, o
- `data/raw/submissions/CIK<10digitos>.json` — el registro del emisor.

**El CIK que trae la fila legacy no es evidencia de nada.** Es un valor a
verificar. F-024 mostró por qué: `dim_entity#572` traía el CIK de Macro Bank en
la columna `cuit`. Lo que decide es lo que dice SEC, no lo que dice el legacy.

Un CIK que el legacy declara y SEC no reconoce → **clase D (inválido)**, no se
ancla nada.

## 3. Qué fuente puede producir cada identificador

| identificador | fuente autoritativa | qué pasa si la fuente no lo publica |
|---|---|---|
| `CIK` | `SEC_REGISTRY` (asigna el CIK) · `SEC_20F` | clase D, sin ancla |
| `LEI` | `GLEIF` | la entidad queda con CIK y sin LEI. No se busca por nombre |
| `CUIT` | `GLEIF` sólo si `registeredAt ∈ {RA000009 AFIP, RA000010 IGJ/RNS}` · `SEC_20F` con bloque de identificación · `AFIP` · `HUMAN` | `REVIEW_REQUIRED` con motivo escrito |

`LEGACY_DIM_ENTITY` es **`CORROBORATING`**: puede proponer, nunca establecer.
`CNV_PORTAL` y `DERIVED_RULE` son `DISCOVERY_ONLY`.

**Este backfill no convierte ninguna fuente en autoritativa, ni permanente ni
transitoriamente.**

## 4. Cuándo se reutiliza una entidad

Se reutiliza cuando **alguno** de los identificadores candidatos ya resuelve a
una entidad existente por la vía autoritativa (`resolver_por_candidatos`). Es la
corrección de F-032: anclar en un solo identificador —y encima en uno que la
política nunca deja llegar a autoritativo— era lo que producía tres copias de
cada emisora argentina.

Si dos identificadores candidatos resuelven a **entidades distintas**, no se
elige ninguna: se abre `CONFLICT` (§9).

## 5. Cuándo se crea una entidad

Sólo cuando ningún candidato resuelve y **hay un CIK autoritativo verificado
contra SEC**. La entidad nace anclada, con `entity_key` opaco (ULID).

Una entidad **nunca** se crea a partir de un CUIT legacy: ese camino es el que
F-032 cerró.

## 6. Cuándo se genera `REVIEW_REQUIRED`

- GLEIF publica un CUIT para el LEI, pero **nada demuestra que ese LEI
  corresponda al CIK** con el que la entidad está anclada (G5). Es el 100% de
  los casos medidos en el piloto.
- La entidad ya tiene un identificador autoritativo vigente de ese tipo y llega
  otro distinto (un segundo LEI, un segundo CUIT).
- GLEIF devuelve **más de un** LEI para la razón social (caso BMA, F-024).

## 7. Cuándo se genera `CONFLICT`

- Un CIK autoritativo vigente ya designa **otra** entidad.
- Dos candidatos de la misma fila resuelven a entidades distintas.
- El legacy declara en una columna un valor que pertenece a otro tipo (BMA).

Un conflicto **no se resuelve en silencio y no se resuelve solo.**

## 8. Cuándo se rechaza

- CIK con formato inválido o que SEC no reconoce.
- Un identificador autoritativo que ya pertenece a otra entidad
  (`ux_identifier_autoritativo_unico` lo rechaza en la base, no en Python).
- Un identificador autoritativo dirigido a una entidad `MERGED` o `DISSOLVED`
  (F-035).
- Una assertion `VERIFIED` sin evidencia, fuente o autor.

## 9. Qué puede quedar `CANDIDATE` y qué puede ser `VERIFIED`

| | `CANDIDATE` / `WEAK` | `VERIFIED` |
|---|---|---|
| CIK verificado contra SEC | | ✅ |
| LEI publicado por GLEIF | | ✅ |
| CUIT via GLEIF sin bridge ratificado | ✅ | ❌ |
| CUIT del legacy | ✅ (siempre) | ❌ (nunca) |
| bridge CIK↔LEI | ✅ propuesto | sólo por `HUMAN_DECISION` firmada |

**Este backfill no produce ni un solo `VERIFIED` de CUIT.** Los 3 que existen
son ratificaciones humanas del ciclo 6 y no se tocan.

## 10. Qué nunca puede inferirse

- identidad por **nombre** (F-024: dos LEI para «Banco Macro»);
- identidad por **ticker** (colisión COUR/Coursera);
- identidad por **domicilio** o similitud textual;
- el puente **CIK↔LEI** (G5: no existe fuente primaria);
- el puente **CIK↔CUIT**;
- un CUIT a partir de un CIK.

## 11. Idempotencia

N ejecuciones sobre el mismo insumo dejan el mismo estado:

- `entity`: delta 0 después de la primera;
- `identifier`: delta 0;
- `assertion`: delta 0 — una propuesta repetida del mismo hecho no crea una
  assertion nueva;
- `conflict` / `review`: delta 0.

Se compara **contenido**, no sólo conteos: hash del estado de identidad por
entidad (§13).

## 12. Reversibilidad

Cada corrida se identifica por su `run_id` y toda escritura queda ligada a él.
Revertir = retirar (`valid_to`) lo que esa corrida afirmó, **nunca** borrar:
las assertions son inmutables por trigger y la provenance no se borra.

El DRY-RUN es reversible por construcción: no escribe.

## 13. Provenance

Toda escritura lleva, sin excepción y por FK `NOT NULL`:

`assertion_id` · `source_id` · `source_record` · cita textual reproducible ·
`resolved_by` · `method` · `source_facts` (estructurado, F-036/F-037) ·
`run_id` · timestamps.

No existe ruta de escritura que omita alguno: `identifier.assertion_id` es
`NOT NULL` y el trigger 14 exige que un identificador autoritativo tenga
assertion `VERIFIED`.

## 14. Auditoría

Un tercero debe poder reconstruir el resultado **sin ejecutar el backfill y sin
importar su código**: desde `identity_v1` + los artefactos de `data/raw/` +
el inventario JSON de la fase C.

El auditor de la fase H reimplementa los controles; no llama a las funciones del
implementador.

## 15. Comportamiento ante crash

El backfill corre dentro de `run_scope()` (F-040, cerrada en la fase A de este
ciclo): un crash deja la corrida `ABORTED` con `finished_at`, nunca `RUNNING`.

Cada entidad se procesa en su propia transacción: un crash a mitad deja
persistido lo ya resuelto y nada a medias. La corrida siguiente reencuentra lo
escrito por idempotencia (§11) y sigue.

## 16. Lo que este backfill NO hace

No toca `dim_entity` · no toca `ticker_canonico` · no toca SEC, S03, S04 ni
Market · no ejecuta CNV · no ratifica nada · no procesa los 56 de BYMA · no
borra evidencia histórica.
