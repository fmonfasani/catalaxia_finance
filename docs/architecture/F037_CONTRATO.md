# F-037 — CONTRATO: INTEGRIDAD DE EVIDENCIA PARA IDENTIFICADORES AUTORITATIVOS

**Fecha:** 2026-08-28 · **Escrito antes de modificar nada.**

---

## 1. AS-IS — reproducido con `catalaxia_engine`, el rol operativo

```
A1  SEC_20F           + evidence libre, source_facts NULL   -> ACEPTADO
A2  AFIP              + evidence libre, source_facts NULL   -> ACEPTADO
A3  GLEIF             + evidence libre, source_facts NULL   -> RECHAZADO (F-036)
A4  SEC_REGISTRY      + CUIT autoritativo                   -> ACEPTADO
A5  LEGACY_DIM_ENTITY + CUIT autoritativo                   -> ACEPTADO
A6  el ataque completo: BMA adquiere un CUIT autoritativo con evidencia arbitraria
```

**F-037 es más ancho de lo que decía el finding.** No es sólo que falte `source_facts` para
`SEC_20F`. A4 y A5 muestran algo peor:

- `SEC_REGISTRY` tiene `authoritative_for = {CIK}` — **no** incluye CUIT — y aun así pudo
  afirmar un CUIT autoritativo.
- `LEGACY_DIM_ENTITY` es `CORROBORATING` — no es autoritativa para nada — y también pudo.

**La matriz fuente × tipo de identificador vive sólo en Python** (`source_authority()`). La
base guarda `identity_v1.source.authoritative_for` y no la usa para nada.

## 2. Inventario de política (estado real)

| `source_id` | nivel | `authoritative_for` |
|---|---|---|
| `AFIP` | AUTHORITATIVE | `{CUIT}` |
| `GLEIF` | AUTHORITATIVE | `{LEI, CUIT}` |
| `SEC_20F` | AUTHORITATIVE | `{CIK, CUIT}` |
| `SEC_REGISTRY` | AUTHORITATIVE | `{CIK}` |
| `HUMAN` | AUTHORITATIVE | `{}` — ratifica, no publica registros |
| `LEGACY_DIM_ENTITY`, `MARKET_CATALOG` | CORROBORATING | `{}` |
| `CNV_PORTAL`, `DERIVED_RULE` | DISCOVERY_ONLY | `{}` |

**Sólo tres fuentes pueden producir CUIT:** `AFIP`, `GLEIF`, `SEC_20F`.

CUIT en la base hoy: 3 de `GLEIF` (autoritativos, retirados) + 44 de `LEGACY` (no
autoritativos). Filas históricas que la regla nueva afecta: **3** — las mismas assertions
`GLEIF VERIFIED` sin `source_facts` que ya cubre el `NOT VALID` de F-036.

## 3. TO-BE — la regla general

> Una assertion que **establece** un identificador (`status='VERIFIED'`) sólo es válida si la
> fuente es autoritativa **para ese tipo de identificador**, y si declara la evidencia de
> forma **estructurada**, con los campos mínimos que su propia clase de fuente exige.

Dos mecanismos, porque son dos preguntas distintas:

1. **¿Puede esta fuente establecer este tipo?** → depende de `identity_v1.source`, otra
   tabla ⇒ **trigger**. Es general: aplica a CIK, CUIT, LEI, no sólo a CUIT.
2. **¿Declaró la evidencia mínima?** → depende sólo de la fila ⇒ **CHECK**.

La base valida **la estructura declarada de la evidencia, nunca la verdad externa del
documento**. No sabe si el 20-F dice lo que la assertion afirma; sí puede exigir que la
assertion diga *en qué accession y en qué sección* lo dice, para que un tercero lo abra.

## 4. Matriz `source_id` × `identifier_type` × evidencia

| Fuente | Autoridad | Puede establecer | `source_facts` | Campos mínimos | ¿Validable en DB? |
|---|---|---|---|---|---|
| `GLEIF` | AUTHORITATIVE | LEI, CUIT | **obligatorio** para CUIT | `registeredAt ∈ {RA000009, RA000010}`, `registeredAs` no vacío | sí |
| `SEC_20F` | AUTHORITATIVE | CIK, CUIT | **obligatorio** para CUIT | `accession` no vacío, `seccion` no vacío | sí (estructura) |
| `AFIP` | AUTHORITATIVE | CUIT | **obligatorio** | `constancia` no vacío | sí (estructura) |
| `SEC_REGISTRY` | AUTHORITATIVE | CIK | no aplica a CUIT | — | sí — **no puede** establecer CUIT |
| `HUMAN` | AUTHORITATIVE | ninguno por registro | ratifica vía `HUMAN_DECISION` | `reviewer`, `decision_ref` | sí |
| `LEGACY_DIM_ENTITY`, `MARKET_CATALOG` | CORROBORATING | **ninguno** | — | — | sí — sólo `CANDIDATE` |
| `CNV_PORTAL`, `DERIVED_RULE` | DISCOVERY_ONLY | **ninguno** | — | — | sí — sólo `CANDIDATE` |

## 5. Invariantes

1. Ninguna assertion `VERIFIED` establece un identificador de un tipo para el que su fuente
   no es autoritativa.
2. Una fuente `CORROBORATING` o `DISCOVERY_ONLY` **nunca** produce una assertion `VERIFIED`
   que establezca identidad.
3. Todo CUIT establecido declara `source_facts` con los campos mínimos de su fuente.
4. La ratificación humana (`HUMAN_DECISION`) sigue siendo posible, y declara quién y con qué.
5. `evidence` sigue siendo prosa para un humano; **nunca** sustituye a `source_facts`.
6. F-032, F-034, F-035, F-036 y F-024 intactos.

## 6. Ataques que deben fallar

A1–A6 de la reproducción, más: `source_facts` incompleto, `registeredAt` inválido, promoción
de CANDIDATE sin evidencia, cambio de `source_id` posterior, y modificación de `source_facts`
o `is_authoritative` por UPDATE.

## 7. Casos legítimos que deben seguir funcionando

- `SEC_REGISTRY` estableciendo **CIK** (es su tipo) — el CIK de BMA y los 7 del piloto.
- `GLEIF` estableciendo **LEI**.
- `GLEIF` estableciendo **CUIT** con `registeredAt`/`registeredAs` — vía `link_cuit_desde_gleif`.
- `LEGACY_DIM_ENTITY` proponiendo CUIT como **CANDIDATE** (44 filas).
- `MARKET_CATALOG` proponiendo instrumentos como CANDIDATE.
- La ratificación humana de un bridge.

## 8. Datos históricos

Las **3** assertions `GLEIF VERIFIED` sin `source_facts` son inmutables
(`tg_assertion_inmutable`) y **no se reescriben**. El CHECK nuevo se agrega `NOT VALID` por
la misma razón que en F-036: no toca lo existente, valida todo INSERT/UPDATE futuro.

El trigger de autoridad, en cambio, **sí puede ser total**: se verificó que ninguna fila
existente lo viola (los CUIT autoritativos vigentes son 0; los 3 de GLEIF están retirados y
GLEIF sí es autoritativa para CUIT).
