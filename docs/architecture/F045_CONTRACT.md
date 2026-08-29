# CONTRATO — F-045 · COHERENCIA ASSERTION ↔ IDENTIFIER

**Fecha:** 2026-08-28 · **Escrito antes de modificar nada.**
**Alcance:** exclusivamente F-045/F-046. No toca SEC, S03, S04, Market, CNV, BYMA,
bridges, F-041 ni F-014.

---

## 0. El problema, en una frase

> La política *«la autoridad es propiedad de la fuente, por tipo de identificador»*
> se verifica en `assertion`, donde el tipo es una **declaración opcional**; el tipo
> real se decide en `identifier`, donde nadie lo vuelve a mirar.

Reproducido con el rol operativo `catalaxia_engine`, 6 bypass sobre 10 ataques
(`outputs/docs/homologacion/f045_bench.json`).

---

## 1. Las dos relaciones que el modelo debe garantizar

### 1.1 `assertion → identifier → id_type`

Hoy la relación es unidireccional y muda: `identifier.assertion_id` es
`NOT NULL REFERENCES assertion(assertion_id)`, y nada más. La assertion **no sabe**
qué identificador terminó sosteniendo.

El vínculo semántico ya existe pero es opcional: `assertion.left_ref`, con formato
canónico `ref(id_type, id_namespace, id_value) = 'TIPO:NAMESPACE:VALOR'`
(`engine/identity_v1.py:150`).

**El contrato lo vuelve obligatorio y verificado:**

> Cuando un `identifier` es **autoritativo y vigente**, su assertion debe declarar
> `left_ref` y ese `left_ref` debe ser **exactamente**
> `id_type || ':' || id_namespace || ':' || id_value`, y la assertion debe pertenecer
> a **la misma entidad**.

No es heurística de texto libre: es igualdad exacta contra un formato ya canónico y
ya usado por toda la capa de dominio (574/574 identificadores vigentes lo cumplen;
sólo 6 tienen `left_ref NULL`).

### 1.2 `assertion.source_id → source.authoritative_for`

> Una assertion que **establece** un identificador de tipo `T` sólo puede usar una
> fuente cuyo `authority_level = 'AUTHORITATIVE'` y cuyo `authoritative_for`
> contenga `T`.

Consecuencias explícitas:

- una assertion que establece **CUIT** no puede usar una fuente autoritativa sólo
  para **CIK** (`SEC_REGISTRY`);
- una assertion que establece **CIK** no puede usar una fuente autoritativa sólo
  para **CUIT/LEI** (`GLEIF`);
- `LEGACY_DIM_ENTITY` (`CORROBORATING`), `CNV_PORTAL` y `DERIVED_RULE`
  (`DISCOVERY_ONLY`) **no establecen ningún tipo**;
- `HUMAN_DECISION` queda exceptuada de la verificación *de fuente* — una persona no
  publica un registro, decide — pero **no** de la verificación de coherencia (§1.1).
  Eso ya lo gobiernan `ck_humano_exige_autor` y `ck_humano_no_es_proceso`.

### 1.3 `left_ref = NULL` no puede omitir la validación

Hoy el trigger sobre `assertion` hace `IF ... OR NEW.left_ref IS NULL THEN RETURN NEW`.
Ese `RETURN` temprano es el bypass A1/A2/A3/A5.

**No se vuelve `left_ref` NOT NULL en `assertion`**: la columna la comparten los
bridges (`IDENTIFIER_BRIDGE` usa `left_ref` + `right_ref`) y assertions que no
establecen identidad. Hacerla obligatoria rompería usos legítimos y exigiría
reescribir historia.

**La obligación se traslada al punto donde el tipo existe:** `identifier`.

---

## 2. Por qué la garantía va en `identifier` y no en `assertion`

| | `assertion` | `identifier` |
|---|---|---|
| ¿sabe el tipo? | sólo si `left_ref` está poblado | **siempre**: `id_type` es `NOT NULL` |
| ¿sabe si establece identidad? | no con certeza | **sí**: `is_authoritative` |
| ¿se puede omitir? | sí, dejando `left_ref` NULL | no |

Verificar en `assertion` es verificar una intención. Verificar en `identifier` es
verificar el hecho. **La garantía va donde el hecho ocurre.**

El trigger existente sobre `assertion` (`tg_fuente_autoritativa_para_el_tipo`) **no
se elimina**: sigue siendo útil como rechazo temprano y cubre bridges. Se le suma
—no se le sustituye— la verificación en el punto de uso.

---

## 3. Cambio de schema

**Ninguno.** No hace falta columna nueva ni FK adicional:

- el tipo ya está en `identifier.id_type`;
- el vínculo ya está en `identifier.assertion_id`;
- la declaración ya está en `assertion.left_ref` con formato canónico;
- la política ya está en `source.authoritative_for`.

Todo lo necesario existe. Lo que falta es **evaluarlo en el momento correcto**.

Se implementa como **trigger** (no `CHECK`): la condición depende de otras dos
tablas (`assertion`, `source`), y un `CHECK` no puede consultarlas.

---

## 4. Qué debe verificar el trigger

Sobre `identity_v1.identifier`, `BEFORE INSERT OR UPDATE`, cuando la fila resultante
es **autoritativa y vigente**:

1. la assertion referida tiene `subject_type = 'ENTITY_IDENTIFIER'`;
2. `assertion.left_ref IS NOT NULL`;
3. `assertion.left_ref = id_type || ':' || id_namespace || ':' || id_value`;
4. `assertion.entity_key = identifier.entity_key`;
5. salvo `method = 'HUMAN_DECISION'`: la fuente de la assertion es `AUTHORITATIVE`
   y su `authoritative_for` contiene `id_type`.

### Qué NO debe romper

- **Retirar** un identificador (`UPDATE ... SET valid_to = now()`) siempre se
  permite: si la fila deja de estar vigente, el trigger no valida. Sin esto, las 6
  filas históricas de F-046 quedarían imposibles de retirar.
- Los identificadores **no autoritativos** (`CANDIDATE`) no se validan: no
  establecen identidad. Los 53 CUIT candidatos siguen entrando.
- No se otorgan privilegios nuevos al rol operativo, ni se usa el owner como parte
  de la garantía.

---

## 5. Datos históricos fuera del constraint

Medido contra la base, no supuesto:

```
identificadores VIGENTES ...................................... 574
  ...cuya assertion tiene left_ref NULL ....................... 6     <-- F-046
  ...cuyo left_ref no coincide exactamente .................... 0
identificadores RETIRADOS (historicos) ......................... 9
  ...que no cumplirian ........................................ 0
```

Las **6** son las re-afirmaciones del ciclo 9 (assertions 1387–1392, F-041). Un
trigger no revisa filas existentes: quedan como están, y **no se reescriben**.

Reescribirlas exigiría re-afirmar otra vez sobre F-041, que este ciclo tiene
explícitamente prohibido tocar. Quedan documentadas en `docs/review/F046_FINDING.md`.

**Riesgo residual: nulo.** Su fuente es `SEC_REGISTRY`, autoritativa para `CIK`, que
es el tipo que sostienen; con `left_ref` habrían pasado igual. El defecto es de
procedimiento, no de contenido.

---

## 6. Idempotencia, inmutabilidad y supersede

- **Idempotencia:** el trigger es una verificación, no una escritura. No cambia lo
  que la capa de dominio produce; sólo rechaza lo que nunca debió entrar.
- **Inmutabilidad:** no toca `assertion`. `tg_assertion_inmutable` sigue intacto.
- **Supersede:** el mecanismo de F-041 (insertar assertion nueva → retirar
  identifier viejo → insertar identifier nuevo → encadenar) sigue funcionando,
  siempre que la assertion nueva declare `left_ref`. El paso «retirar» está
  explícitamente permitido (§4).
- **Sin ciclos:** el trigger sólo lee; no escribe en `assertion` ni en `identifier`.

---

## 7. Los ataques que deben quedar rechazados, y por qué garantía

| | ataque | garantía |
|---|---|---|
| A1 | `LEGACY_DIM_ENTITY` → CUIT | fuente no autoritativa para el tipo |
| A2 | `DERIVED_RULE` → CUIT | ídem |
| A3 | `CNV_PORTAL` → CUIT | ídem |
| A4 | assertion que declara CIK usada para CUIT | `left_ref` ≠ identificador |
| A5 | `left_ref` NULL | `left_ref` obligatorio |
| A6 | `left_ref` a otro valor/namespace | `left_ref` ≠ identificador |
| A9 | `SEC_REGISTRY` → CUIT | fuente no autoritativa para el tipo |
| A10 | `GLEIF` → CIK | ídem |
| A14 | assertion de otra entidad | `entity_key` ≠ |
| A7, A8, A13 | rutas por `UPDATE` | ya cerradas por GRANT de columna |

Un ataque rechazado por una barrera distinta de la que declara **no cuenta como
PASS**. Cada uno debe nombrar la garantía que lo detiene, y la mutación debe
demostrar que sin ella el ataque entra.
