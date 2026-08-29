# F-041 — 7 CIK AUTORITATIVOS DE CICLOS ANTERIORES NO TIENEN EVIDENCIA ESTRUCTURADA

**Detectado:** 2026-08-28, ciclo 8 fase H, por la auditoría independiente del backfill
**Estado:** **registrado, no corregido** — corregirlo exige reescribir assertions
históricas, que son inmutables por trigger
**Severidad:** baja. No hay dato inventado; falta la forma estructurada de la evidencia.

---

## 1. El hallazgo

De los 513 CIK autoritativos vigentes, **7 tienen `assertion.source_facts = NULL`**:

| quién lo escribió | fuente | filas |
|---|---|---|
| `proc:sec_registry` | `SEC_REGISTRY` | 6 |
| `proc:s03_parse` | `SEC_20F` | 1 |

Los **505 que escribió el backfill de este ciclo tienen todos sus facts.** Las 7
son anteriores: se escribieron antes de F-036/F-037, cuando `source_facts` no
existía.

El control lo encontró porque lo medí sobre *todos* los CIK. Al separarlo —lo
que el backfill escribió vs. lo preexistente— el control del backfill pasa
limpio y las 7 quedan como lo que son: deuda de ciclos anteriores, no un defecto
introducido ahora.

## 2. Por qué la garantía no las alcanzó

F-037 generalizó la exigencia de evidencia estructurada, pero la materializó como
`ck_cuit_exige_evidencia_estructurada` — un CHECK **sobre CUIT**, con `NOT VALID`
para no reescribir filas históricas. El trigger general
`tg_fuente_autoritativa_para_el_tipo` verifica *qué fuente puede establecer qué
tipo*, no si trae `source_facts`.

Resultado: **el CIK nunca quedó cubierto por la exigencia de facts.** Y como el
CHECK del CUIT es `NOT VALID`, tampoco se revisó lo viejo.

No es una regresión. Es alcance que F-037 no cubrió, visible sólo cuando se
escriben 505 CIK nuevos al lado de 7 viejos y se los compara.

## 3. Lo que NO tiene de malo

Las 7 tienen provenance completa: `source_id`, `source_record`, cita textual,
`resolved_by`, `status='VERIFIED'`. Un auditor puede reconstruirlas. Lo que
falta es la representación **estructurada** de esa evidencia — el JSONB que
permite consultarla sin parsear texto libre.

Ninguna es un dato inventado, y ninguna viene de una fuente no autoritativa (la
auditoría verificó ambas cosas por separado y dieron OK).

## 4. Corrección propuesta (no aplicada)

No se puede hacer con un `UPDATE`: `tg_assertion_inmutable` lo impide, y con
razón. Las dos vías legítimas son:

1. **Re-afirmar**: emitir una assertion nueva con `source_facts` reconstruidos
   desde el mismo artefacto, y retirar (`valid_to`) la anterior. Conserva la
   historia y cumple la garantía. Es el camino que el modelo prevé.
2. **Aceptar la deuda y acotarla**: extender la exigencia de facts a `CIK` con un
   CHECK `NOT VALID`, de modo que toda escritura *futura* la cumpla y las 7
   queden explícitamente marcadas como anteriores al contrato.

La opción 2 es más barata y honesta; la 1 es más completa. La decisión es de
producto: si `source_facts` va a ser consultado programáticamente para CIK,
hace falta la 1.

## 5. Lo que este hallazgo dice del método

Una garantía escrita para un tipo de identificador no cubre a los demás sólo por
llamarse «general». F-037 se llamó *«evidencia estructurada general»* y su
materialización efectiva fue un CHECK sobre CUIT.

Es el mismo patrón que F-039 (dominio calibrado sobre una empresa) y que la
primera versión del constraint de F-038: **la garantía cubre el caso que la
motivó, no el invariante que declara.** Y en los tres casos lo reveló una
ejecución real sobre datos nuevos, no un test.
