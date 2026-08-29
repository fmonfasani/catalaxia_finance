# SYSTEM_HOMOLOGATION_BLOCKERS

**Auditoría de homologación · 2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
Hallazgos nuevos de esta auditoría. **Ninguno fue corregido** — se registran y se detiene.

---

## F-045 — `BLOCK` · La autoridad por tipo de identificador es eludible desde el rol de aplicación

**El más grave. Es la garantía central del modelo.**

### Qué se probó

El esquema declara (`IDENTITY_V1_SCHEMA.md` §3): *«La autoridad es propiedad de la
FUENTE, no del dato»*, materializada en `tg_fuente_autoritativa_para_el_tipo`.

Con el rol **`catalaxia_engine`** — el que corre en producción, no admin — sobre una
entidad limpia, dentro de una transacción revertida:

| ataque | resultado |
|---|---|
| **A1** CUIT autoritativo desde `LEGACY_DIM_ENTITY` (CORROBORATING), assertion **sin `left_ref`** | **ENTRÓ** |
| **B1** assertion que declara `CIK:SEC:…` reutilizada para establecer un **CUIT** autoritativo | **ENTRÓ** |
| **C1** (control) mismo caso **con** `left_ref='CUIT:…'` | rechazado correctamente |

### La causa

```sql
IF NEW.status <> 'VERIFIED' OR NEW.subject_type <> 'ENTITY_IDENTIFIER'
   OR NEW.left_ref IS NULL THEN
    RETURN NEW;          -- <-- sin left_ref, no verifica nada
END IF;
tipo := split_part(NEW.left_ref, ':', 1);
```

Dos huecos, ambos alcanzables por la aplicación:

1. **`left_ref` es nullable.** Una assertion `ENTITY_IDENTIFIER` sin `left_ref`
   atraviesa el trigger sin ser evaluada.
2. **Nada liga `assertion.left_ref` con `identifier.(id_type,…)`.** El trigger vive
   en `assertion`, donde el tipo es una *declaración*; el tipo real se decide al
   insertar en `identifier`, donde nadie lo vuelve a mirar.

B1 es literalmente una de las rutas que el encargo pide impedir: **transformar un
CIK en un CUIT**. Hoy se puede, con dos INSERT y sin privilegios especiales.

### Estado real: sano, pero por Python

- identificadores cuyo `id_type` no coincide con el `left_ref` de su assertion: **0**
- CUIT autoritativos desde fuente no autoritativa: **0**

La barrera efectiva es `engine/identity_v1.py`, que siempre construye `left_ref`
con `ref(id_type, id_namespace, id_value)`. Cualquier ruta que escriba sin pasar
por ahí queda fuera de control — y **ya ocurrió** (F-046).

Contradice la instrucción que el propio proyecto fijó en el ciclo 4C: *«No permitir
que Python sea la única barrera si la garantía puede expresarse mediante constraint,
trigger o mecanismo equivalente de DB.»*

---

## F-046 — `PASS_WITH_NOTES` · Seis assertions reales ya eludieron esa garantía

Consecuencia observada de F-045, no hipótesis:

```
assertion_id 1387..1392 · source_id=SEC_REGISTRY · proc:f041_reafirmacion@c7816d47085d
2026-08-28 · CIK 0001717161, 0001114700, 0000931427, 0000320193, 0000789019, 0001045810
left_ref = NULL   ·   las 6 sostienen identificadores AUTORITATIVOS vigentes
```

Son **las 6 re-afirmaciones del ciclo 9** (F-041). El script escribió la assertion
con SQL directo y omitió `left_ref`, de modo que **atravesaron el trigger sin ser
verificadas**.

**Sin daño material:** la fuente es `SEC_REGISTRY`, autoritativa para `CIK`; con
`left_ref` habrían pasado igual. Lo que falla es que el sistema no lo notó, y la
auditoría independiente de ese ciclo tampoco — sólo verificaba `source_facts`.

Es la evidencia de que F-045 no es teórico.

---

## F-044 — `PASS_WITH_NOTES` · La tabla `source` no tiene ninguna protección

`identity_v1.source` es la raíz de confianza: define qué fuente puede establecer qué
tipo. A diferencia de `assertion` (trigger de inmutabilidad + prohibición de DELETE),
**no tiene trigger, ni historial, ni assertion que respalde un cambio de política**.

Probado con rol admin, revertido:

```sql
UPDATE identity_v1.source SET authority_level='AUTHORITATIVE',
       authoritative_for=ARRAY['CUIT'] WHERE source_id='LEGACY_DIM_ENTITY';
-- ACEPTADO, sin dejar rastro
```

Con eso, las 53 propuestas `CANDIDATE` de CUIT legacy pasarían a ser promovibles
legítimamente.

**Alcance acotado:** `catalaxia_engine` tiene sólo `SELECT` sobre `source`; el rol de
aplicación no llega. El agujero es del owner, que es por donde corren las migraciones.
Es asimétrico: lo que depende de la política está más protegido que la política misma.

---

## F-043 — `PASS_WITH_NOTES` · Market tipifica «sin datos» como fallo técnico

`market_raw_runs.status` admite `EMPTY` por CHECK. **Nunca se emite.**

```python
# scripts/market/m2_fetch_engine.py:229
_cerrar_log(cur, run_id, "FAILED", 0, error=("EMPTY", "sin filas"))
```

Los 7 instrumentos «fallidos» de M23 (`DGCE.BA SATS CAAP.BA VIST.BA GGALB.BA
SUPVB.BA YPFLUZ.BA`) tienen los tres `error_type='EMPTY'`, `row_count=0`,
`sha256 NULL`: la fuente respondió y no trajo filas. Se registran como `FAILED`.

**Consecuencia mecánica:** `m6_scale.ya_exitosos()` filtra por `status='SUCCESS'`,
así que **los 7 se re-piden en toda corrida futura del mismo stage**, sin posibilidad
de éxito si la ausencia es real.

Es exactamente la distinción que la homologación exige y que el sistema no hace:
*falta de cobertura de la fuente* registrada como *defecto del sistema*.

**No verificado en esta auditoría** si la ausencia es real (requeriría ejecutar Market,
fuera de alcance). Nota adicional: `instrument_id=480` (SATS) tiene `exchange` vacío.

---

## F-047 — `PASS_WITH_NOTES` · Bridges `CANDIDATE` conviven vigentes con su ratificación

```
 96 CANDIDATE WEAK proc:identity_v1_pilot  CIK:0000904851 <-> LEI:5493003N…  vigente
342 VERIFIED  STRONG Federico              CIK:0000904851 <-> LEI:5493003N…  vigente
```

Ídem CEPU (98/343) y TGS (101/344). Al ratificar, la propuesta automática no se
superseded: quedan **dos assertions vigentes para el mismo par**.

No hay daño hoy — todo consumidor auditado filtra por `status='VERIFIED'`. Pero un
consumidor que cuente bridges vigentes sin filtrar ve 7 donde hay 3 ratificados y 4
propuestos, uno de los cuales (GGAL, #100) **no debe** ratificarse.

---

## Resumen

| finding | severidad | alcance | ¿bloquea homologación? |
|---|---|---|---|
| **F-045** | **alta** | rol de aplicación | **Sí — Identity V1 y todo lo que dependa de él** |
| F-046 | media | 6 filas reales | No — sin daño material, es evidencia de F-045 |
| F-044 | media | sólo owner | No — acota, pero debe cerrarse con F-045 |
| F-043 | media | Market | No — deuda de tipificación, con costo operativo |
| F-047 | baja | Identity | No — higiene de supersession |

**Ninguno fue corregido.** Registrados y detenido, según el encargo.
