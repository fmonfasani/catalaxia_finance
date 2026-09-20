# F-060 — determinación semántica

**Fecha:** 2026-09-01 · **Rol:** Orquestador de homologación, Fase 1
**Estado del finding: SIGUE ABIERTO.** Este documento no lo cierra.
**No se modificó código, schema ni datos.**

> **Ejecución interrumpida por concurrencia.** Otro agente está corriendo
> `CREATE DATABASE "adversario_ratios_mut" TEMPLATE "catalaxia"` en ciclo sobre
> la misma base. Ese comando bloquea toda conexión nueva a la plantilla. La regla
> del encargo —«si hay otro agente trabajando sobre la misma DB, detectarlo y
> detenerse antes de escribir»— se aplicó. Los pasos 2, 4 y 5 de la Fase 1
> (reproducción, fix, banco adversario, mutación, auditoría) **quedan pendientes**.
>
> Lo que sigue es el paso 3 —la determinación semántica—, que se resolvió leyendo
> la especificación XBRL y el parser, sin tocar la base.

---

## 1. La pregunta

¿`scheme` e `identifier` forman parte de la identidad semántica de un contexto
XBRL?

## 2. La respuesta: **sí, inequívocamente**

No es una decisión de conveniencia técnica. XBRL 2.1 define un contexto por tres
componentes:

```xml
<xbrli:context id="C_2025">
  <xbrli:entity>                                   <-- QUIÉN
    <xbrli:identifier scheme="http://www.sec.gov/CIK">0000904851</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>...</xbrli:period>                 <-- CUÁNDO
  <xbrli:segment>/<xbrli:scenario>...              <-- EN QUÉ DIMENSIÓN
</xbrli:context>
```

Dos contextos son equivalentes sólo si sus tres componentes lo son. **La entidad
es parte de la definición**, no un atributo accesorio.

El sistema lo captura correctamente —`engine/xbrlparse.py:494-497` lee
`scheme` e `identifier` del elemento `entity`— y los persiste en
`parsed.contexts`. **Lo que no hace es usarlos al comparar.**

El propio contrato ya lo dice: `S04_CONTRACT.md` §1 define el hecho canónico como
uno por **«(entidad, filing, concepto, período, unidad)»**. La entidad encabeza
la clave.

## 3. Pero el riesgo declarado en F-060 **no es alcanzable**

Ésta es la corrección importante, y contradice lo que yo mismo afirmé en
`FINAL_HOMOLOGATION_REPORT.md` §6.

F-060 describía el riesgo como *«colapsaría hechos de dos entidades en uno»*. Ese
escenario **no puede ocurrir**, por dos hechos verificables en el código:

**a. `context_id` es el atributo `id` del XML.**

```python
# engine/xbrlparse.py:491
ctx = ParsedContext(context_id=el.get("id") or "")
```

XML exige que `id` sea único dentro de un documento. Un filing que declare
contextos de dos entidades distintas les da, necesariamente, **`context_id`
distintos**.

**b. La deduplicación agrupa por `(accession_number, context_id)`.**

Dos contextos de entidades distintas nunca caen en el mismo grupo, porque su
`context_id` difiere. **Nunca se comparan entre sí, y por lo tanto nunca se
colapsan.**

**c. El parser ya detecta el id repetido dentro de un documento.**

```python
# engine/xbrlparse.py:744-745
if ctx.context_id in result.contexts:
    result.add_error("CONTEXT_DUPLICATE_ID", f"id repetido {ctx.context_id}", ...)
```

## 4. Cuál es el riesgo real, entonces

Dos filas con el mismo `(accession, context_id)` provienen de las **dos
representaciones del mismo filing** —el inline `.htm` y la instancia
`_htm.xml`— y designan **el mismo contexto**.

Si su `scheme` o su `identifier` difirieran, no serían dos entidades: sería una
**discrepancia de parseo entre las dos representaciones**. Hoy esa discrepancia
**pasaría inadvertida**, porque la comparación no mira esos campos.

| | F-060 como estaba declarado | F-060 en realidad |
|---|---|---|
| qué pasaría | se colapsan hechos de dos entidades | no se detecta una discrepancia de parseo en el campo entidad |
| gravedad | dato financiero incorrecto, silencioso | control ausente sobre un campo que no varía en la práctica |
| alcanzable | **no** | sí, pero requiere un bug de parseo |

## 5. Consecuencia sobre el dictamen de homologación

`FINAL_HOMOLOGATION_REPORT.md` §6 clasificó F-060 como **«el único camino
identificado capaz de producir un dato incorrecto sin detección»**, y lo usó como
blocker **B4** para justificar `NOT_READY`.

**Esa afirmación era incorrecta y queda retirada.** El camino no es alcanzable
por construcción.

Lo que **no** cambia: el dictamen `NOT_READY` seguía en pie por B1 (la superficie
que se mostraría no es la auditada) y B2 (provenance no verificable en Market
0 % y CNV 8,3 %). Ninguno de los dos depende de F-060.

## 6. Corrección propuesta — NO aplicada

Sigue valiendo la pena, por dos razones que ya no son «evitar un dato
incorrecto»:

1. **Alinear la implementación con el contrato**, que declara la entidad como
   parte de la clave canónica.
2. **Convertir una discrepancia de parseo en un fallo visible** en lugar de un
   silencio.

Fix mínimo: agregar `scheme` e `identifier` a la tupla comparada en
`contextos_deduplicados()` y en el control `C-S04-003` de `s04_normalize.py`.

**Impacto esperado: nulo sobre los datos actuales.** La medición previa dio
`0` grupos `(accession, context_id)` con `scheme`/`identifier` divergentes, de
modo que incluirlos no reclasifica ningún contexto. Eso **debe re-verificarse**
antes de aplicar: la medición se tomó antes de que el otro workstream siguiera
ingiriendo.

## 7. Clasificación propuesta

```
F-060 = ACCEPTED_RISK / DOCUMENTED
```

**No `CLOSED`**, porque el fix no se aplicó ni se verificó.
**No `OPEN_BLOCKER`**, porque el camino a dato incorrecto no es alcanzable.

Para llevarlo a `CLOSED` hacen falta los pasos que la concurrencia impidió:
aplicar el fix, re-verificar que el impacto sobre los datos es nulo, actualizar
`S04_CONTRACT.md`, convertir el test `xfail(strict=True)` en test normal, y
pasar el banco adversario y la auditoría independiente.

## 8. Lo que queda pendiente de la Fase 1

| paso | estado |
|---|---|
| 1 · leer gate, finding, contratos, tests | **hecho** |
| 2 · reproducir con contextos construidos | **bloqueado por concurrencia** |
| 3 · determinar semántica | **hecho** — sí forman parte |
| 4 · fix + contrato + test + adversario + mutación + auditoría | **bloqueado** |
| 5 · (no aplica: sí forman parte) | — |
| 6 · no borrar provenance histórica | respetado: no se escribió nada |
| 7 · cerrar sólo con evidencia suficiente | **no se cierra** |
