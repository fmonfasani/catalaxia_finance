# IDENTITY_CUIT_ASSERTION_AUDIT

**Fecha:** 2026-09-01 · **Rol:** Auditor de sólo lectura
**Alcance:** semántica de las assertions vigentes sobre CUIT y quién puede
producir `VERIFIED`.
**No se modificó código, base, statuses, assertions ni migraciones.**

---

## 0. Resumen — y una corrección a un informe propio

La estructura que el incidente CNV expuso como sospechosa **no es un defecto: es
el modelo funcionando como su contrato lo declara.** El discriminador de
autoridad no es `assertion.status`, sino **`identifier.is_authoritative`**, y
está escrito en el contrato y forzado por un trigger.

**Se retira la observación §7.4 del `CNV_NEGATIVE_PILOT_20_INCIDENT_REPORT.md`**,
que sugería que un `VERIFIED` producido por `proc:gleif_fetch` podía contradecir
el principio G5. No lo contradice: G5 rige sobre el **puente CIK↔LEI**, no sobre
el identificador CUIT, y la base tiene un CHECK que enumera explícitamente las
cuatro fuentes admisibles para un CUIT `VERIFIED`.

Quedan **dos hallazgos reales**, ambos menores y ninguno de corrupción.

---

## 1. Evidencia observada

### 1.1 · Dos vocabularios de estado, independientes

Forzados por CHECK en la base:

```sql
identifier_status_check :  ACTIVE | RETIRED | DISPUTED
assertion_status_check  :  UNRESOLVED | CANDIDATE | REVIEW_REQUIRED | VERIFIED | REJECTED
```

**No existen `CONFLICT`, `WITHDRAWN` ni `SUPERSEDED`.** La supersesión se expresa
con `valid_to` + `superseded_by`, no con un estado.

### 1.2 · Población de CUIT vigentes

```
is_auth | ident.status | assert.status | method   | resolved_by                    |  n
--------|--------------|---------------|----------|--------------------------------|----
 false  | ACTIVE       | CANDIDATE     | REGISTRY | proc:legacy_import             |  44
 false  | ACTIVE       | CANDIDATE     | REGISTRY | proc:backfill_cik@286e08d2ff58 |   9
 true   | ACTIVE       | VERIFIED      | REGISTRY | proc:gleif_fetch               |   3
```

**Correlación perfecta:** los 3 `is_authoritative = true` son exactamente los 3
`VERIFIED`. Los 53 restantes son candidatos no autoritativos.

### 1.3 · El caso concreto — YPF (patrón idéntico en CEPU y TGS)

```
ident_id | ident.status | is_auth | assert | method   | resolved_by        | confianza      | vigencia
       3 | DISPUTED     | true    | VERIF. | REGISTRY | proc:gleif_fetch   | AUTHORITATIVE  | cerrada 2026-08-26
     105 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     116 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     124 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     132 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     154 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     158 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     162 | ACTIVE       | false   | CAND.  | REGISTRY | proc:legacy_import | WEAK           | vigente
     214 | ACTIVE       | TRUE    | VERIF. | REGISTRY | proc:gleif_fetch   | AUTHORITATIVE  | vigente
```

**GGAL:** 7 filas, todas `is_authoritative = false`, `CANDIDATE`, `WEAK`.
**Ninguna autoritativa** — por eso CNV la bloquea.

### 1.4 · El contrato encontrado

| dónde | qué dice |
|---|---|
| `IDENTITY_ARCHITECTURE_V1.md` §Regla de autoridad | «Sólo los identificadores marcados `is_authoritative` pueden fundar una aserción `AUTHORITATIVE`» |
| `IDENTITY_V1_SCHEMA.md` invariante 14 | «Un identificador autoritativo exige assertion `VERIFIED`» — trigger `tg_identifier_autoritativo`, **verificado presente** |
| `IDENTITY_V1_SCHEMA.md` invariante 1 | «No hay `VERIFIED` sin evidencia, fuente y autor» — `ck_verified_exige_evidencia` |
| `IDENTITY_V1_SCHEMA.md` §7 | «No inventa el CUIT. Si GLEIF no lo publica (**GGAL: `RA999999`, `registeredAs = null`**), queda `REVIEW_REQUIRED`» |
| `IDENTITY_V1_SCHEMA.md` §7 | «No cierra la arista **CIK↔LEI** sola. No existe fuente primaria (G5); el puente se registra como `HUMAN_DECISION`, nunca `AUTHORITATIVE`» |

### 1.5 · El CHECK que responde quién puede producir un CUIT `VERIFIED`

```sql
ck_cuit_exige_evidencia_estructurada:
  NOT (left_ref LIKE 'CUIT:%' AND status='VERIFIED')
  OR CASE source_id
       WHEN 'GLEIF'   THEN registeredAt IN ('RA000009','RA000010')
                        AND registeredAs <> ''
       WHEN 'SEC_20F' THEN accession <> '' AND seccion <> ''
       WHEN 'AFIP'    THEN constancia <> ''
       WHEN 'HUMAN'   THEN reviewer <> '' AND decision_ref <> ''
       ELSE false
     END
```

**Cuatro fuentes admisibles, cada una con su evidencia estructurada obligatoria.**
`ELSE false`: cualquier otra fuente **no puede** producir un CUIT `VERIFIED`.

> El constraint está declarado `NOT VALID`: rige para filas nuevas, pero las
> preexistentes no fueron validadas al crearlo. Ver §5.2.

---

## 2. Comportamiento actual

### 2.1 · Cómo el sistema determina autoridad — dos implementaciones distintas

**S04** (`s04_normalize.py::resolver_entidad`) usa el mecanismo del contrato:

```sql
WHERE id_type='CIK' AND id_namespace='SEC' AND id_value=:v
  AND is_authoritative AND valid_to IS NULL
```

**CNV** (`c3_cnv_fetch.py:68`) **no lo usa**:

```sql
max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)  AS cuit_status
```

Sin filtrar por `is_authoritative`, y decidiendo por el **máximo alfabético** del
texto del estado. Con el vocabulario forzado por CHECK:

```
CANDIDATE < REJECTED < REVIEW_REQUIRED < UNRESOLVED < VERIFIED
```

`VERIFIED` es el máximo alfabético de los cinco, así que `max()` devuelve
`VERIFIED` si alguna fila lo es. **El resultado coincide hoy con el mecanismo
correcto** —los 3 autoritativos son los 3 verificados— pero por coincidencia
lexicográfica, no por la regla del contrato.

### 2.2 · Clasificación de los casos con múltiples assertions vigentes

| caso | clasificación | fundamento |
|---|---|---|
| Coexistencia de N candidatos `is_authoritative=false` con 1 autoritativo | **A · intencional según contrato** | el modelo separa reclamos de autoridad; la «Regla de autoridad» lo declara |
| **7–8 candidatos casi idénticos del mismo proceso**, creados a las 10:06:35, 10:06:37, 10:06:48, 10:08:05, 12:42:05, 12:42:17, 12:42:19 | **B · acumulación histórica** | mismo `entity_key`, mismo CUIT, mismo `method`, mismo `resolved_by`. **8 grupos duplicados medidos** |
| Fila `DISPUTED` con `valid_to` cerrado (2026-08-26) | **A · intencional** | supersesión correcta vía `valid_to` |
| Conflicto real (dos autoritativos vigentes para el mismo CUIT) | **no existe** | **0 CUIT con más de 1 autoritativo** |

### 2.3 · Quién produjo los `VERIFIED`

**De CUIT** — los 3, sin excepción:

```
method = REGISTRY · source = GLEIF · resolved_by = proc:gleif_fetch
confidence = AUTHORITATIVE
HUMAN_DECISION: 0
```

**Del puente CIK↔LEI** — comparación pedida:

```
SAME_ENTITY | HUMAN_DECISION | VERIFIED | Federico | 3
```

**Los dos casos son distintos por diseño**, no por inconsistencia:

| | CUIT | puente CIK↔LEI |
|---|---|---|
| ¿existe fuente primaria? | **sí** — GLEIF publica `registeredAs` | **no** (G5) |
| método admisible | REGISTRY / REGULATORY_DOCUMENT / HUMAN | **sólo** `HUMAN_DECISION` |
| confianza resultante | `AUTHORITATIVE` | `STRONG`, nunca `AUTHORITATIVE` |
| quién lo produjo hoy | `proc:gleif_fetch` | **Federico**, persona |

---

## 3. Respuestas a las preguntas

### Q1 · ¿Está permitido tener múltiples assertions vigentes para el mismo CUIT?

**Sí, y es intencional.** El modelo distingue *reclamos* (`is_authoritative=false`)
de la *fuente de registro* (`is_authoritative=true`). Conservar los candidatos es
lo que permite auditar de dónde salió cada afirmación sin borrar el pasado.

### Q2 · ¿Cómo se determina la autoridad?

Por **`identifier.is_authoritative`**, no por `assertion.status`.

Está declarado en `IDENTITY_ARCHITECTURE_V1.md` («Regla de autoridad») y forzado
por el trigger `tg_identifier_autoritativo`, que implementa el invariante 14: un
identificador autoritativo **exige** una assertion `VERIFIED`.

La implicación es de una sola dirección: **autoritativo ⇒ VERIFIED**. Lo inverso
no está garantizado por el modelo, aunque hoy se cumpla.

### Q3 · Si no está permitido, ¿por qué existen?

No aplica a la coexistencia, que sí está permitida. **Sí aplica a la
duplicación**: 8 grupos con `(entity_key, CUIT, method, resolved_by)` repetidos.
`proc:legacy_import` creó 7 filas casi idénticas en momentos distintos.
**Es acumulación por falta de idempotencia**, no diseño. Ver §5.1.

### Q4 · ¿Puede un proceso automático producir `VERIFIED`?

**Sí, y el contrato lo contempla explícitamente.**
`ck_cuit_exige_evidencia_estructurada` admite `GLEIF`, `SEC_20F`, `AFIP` y
`HUMAN`, cada una con evidencia estructurada obligatoria. Los 3 CUIT
`VERIFIED` cumplen la rama `GLEIF`: `registeredAt ∈ {RA000009, RA000010}` y
`registeredAs` no vacío.

No es un proceso «auto-ratificándose»: es un proceso **transcribiendo lo que una
fuente primaria publica**, con la cita guardada.

### Q5 · ¿Es `HUMAN_DECISION` obligatoria para `VERIFIED`?

**No para el CUIT.** Es una de cuatro fuentes admisibles.

**Sí para el puente CIK↔LEI**, y por una razón declarada: ninguna fuente primaria
lo publica (G5). Por eso `ck_politica_estructural_cik_lei` restringe el `source_id`
de un CIK a `SEC_REGISTRY | SEC_20F | HUMAN` y el de un LEI a `GLEIF | HUMAN`.

**Confundir ambos casos fue el error de mi observación anterior.**

### Q6 · ¿La elegibilidad CNV debe expresarse como `EXISTS(status='VERIFIED')`?

**No. Debe expresarse como `is_authoritative`.**

`EXISTS(status='VERIFIED')` sería mejor que `max()` —explícito en vez de
lexicográfico— pero seguiría usando el eje equivocado. El contrato define la
autoridad en `is_authoritative`, el trigger la fuerza, y **S04 ya la usa**. CNV
es el único consumidor que no.

La consulta que corresponde:

```sql
WHERE i.id_type = 'CUIT'
  AND i.valid_to IS NULL
  AND i.is_authoritative
  AND i.status = 'ACTIVE'
```

Con `identifier.status = 'ACTIVE'` además: una fila `DISPUTED` o `RETIRED` no
debería habilitar una descarga aunque fuera autoritativa. **Hoy CNV no mira
ninguno de los dos campos.**

### Q7 · ¿Qué debe ocurrir con cada estado?

Los estados que el modelo realmente tiene:

**`identifier.status`** — sobre la vigencia del identificador:

| estado | qué significa | ¿habilita CNV? |
|---|---|---|
| `ACTIVE` | vigente | **sí**, si además es autoritativo |
| `RETIRED` | dado de baja | no |
| `DISPUTED` | en disputa | **no** — hoy CNV no lo consulta |

**`assertion.status`** — sobre la afirmación:

| estado | qué significa | ¿habilita CNV? |
|---|---|---|
| `VERIFIED` | evidencia estructurada verificada | sí, vía el identificador autoritativo |
| `CANDIDATE` | reclamo registrado, sin promover | no |
| `REVIEW_REQUIRED` | necesita decisión humana | no |
| `UNRESOLVED` | sin resolver | no |
| `REJECTED` | descartada con motivo | no |

**`CONFLICT`, `WITHDRAWN` y `SUPERSEDED` no existen** en ninguno de los dos
vocabularios. La supersesión se expresa con `valid_to` + `superseded_by`.

---

## 4. Hipótesis — señaladas como tales

1. **Los 7 candidatos por CUIT provienen de re-corridas de `legacy_import`.** Los
   timestamps agrupados en dos tandas (10:06–10:08 y 12:42) lo sugieren. *No
   verificado*: haría falta cruzar con `engine.runs`.
2. **El `DISPUTED` con `valid_to` del 2026-08-26 fue la resolución de un
   conflicto de esa fecha.** *No verificado*: no se leyó `superseded_by` ni la
   tabla de conflictos.

---

## 5. Defectos confirmados

### 5.1 · La importación de candidatos no es idempotente

**8 grupos** `(entity_key, CUIT, method, resolved_by)` con más de una fila
vigente. Cada corrida del importador agrega un candidato en vez de reconocer que
ya existe.

No corrompe —los candidatos no son autoritativos y no habilitan nada— pero
**infla el modelo y vuelve engañosa cualquier consulta que cuente filas en vez de
CUIT distintos**. Es exactamente lo que hizo fracasar el piloto CNV: pedir 20
filas y recibir 3 CUIT.

### 5.2 · `ck_cuit_exige_evidencia_estructurada` está `NOT VALID`

Rige para filas nuevas; las preexistentes no se validaron al crear el constraint.
**No se verificó** si las 3 filas `VERIFIED` actuales satisfacen la rama `GLEIF`
—requeriría leer `source_facts`, que este ciclo no pidió—. Queda como
**limitación de evidencia**, no como defecto.

### 5.3 · CNV no usa el mecanismo de autoridad del modelo

Ya descrito en §2.1 y Q6. Hoy el resultado coincide, pero **la coincidencia no
está garantizada por ninguna restricción**: el modelo garantiza
«autoritativo ⇒ VERIFIED», no «VERIFIED ⇒ autoritativo».

Basta una assertion `VERIFIED` sobre un identificador **no** autoritativo para
que CNV habilite una descarga que el modelo no autoriza. **Hoy no existe ese
caso; nada impide que exista mañana.**

---

## 6. Decisiones de diseño pendientes

Ninguna se toma acá.

| # | decisión | quién |
|---|---|---|
| D1 | ¿CNV pasa a `is_authoritative AND status='ACTIVE'`? Requiere actualizar el contrato de CNV, que hoy declara la regla en términos de `assertion.status` | producto + arquitectura |
| D2 | ¿Los candidatos duplicados se consolidan? ¿Se hace idempotente el importador, se supersedan los sobrantes, o se aceptan como registro histórico? | producto |
| D3 | ¿Se valida `ck_cuit_exige_evidencia_estructurada` sobre las filas existentes? | arquitectura |
| D4 | ¿Se agrega el invariante recíproco —«`VERIFIED` sobre un identificador ⇒ ese identificador es autoritativo»— o se acepta la asimetría? | arquitectura |

---

## 7. Estado de la base

**Sin cambios.** Esta auditoría fue exclusivamente de lectura: `SELECT` sobre
`identity_v1`, `pg_constraint`, `pg_trigger` e `information_schema`. No se
ejecutó ningún fetch, no se creó ninguna base, no se modificó ningún status ni
assertion, no se generó ninguna migración.

---

## 8. Conclusión

**El modelo de identidad es más riguroso de lo que el incidente sugería.** La
autoridad tiene un mecanismo declarado (`is_authoritative`), forzado por trigger,
con vocabularios acotados por CHECK y evidencia estructurada obligatoria por
fuente.

Lo que falla no es el modelo: es **un consumidor que no lo usa** (CNV, §5.3) y
**un importador que no es idempotente** (§5.1). Ninguno de los dos produce dato
incorrecto hoy.

Y la observación que yo había levantado sobre `proc:gleif_fetch` era incorrecta:
un proceso transcribiendo GLEIF con la cita guardada es precisamente lo que el
contrato prescribe para un CUIT.
