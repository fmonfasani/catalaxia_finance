# CATALAXIA — INTEGRATION REVIEW

Auditor: **CIAA** · Ciclo **AUDIT-02** · 2026-08-25 · Baseline `444ee1a`

Documento de entrada. Detalle en `SEC_REVIEW.md`, `MARKET_REVIEW.md`, `CNV_REVIEW.md`,
`CROSS_WORKSTREAM_REVIEW.md`; findings en `FINDINGS.md`; dictamen en `REVIEW_GATE.md`.

---

## DICTAMEN

**NOT_READY para la Canonical Economic Layer.**

Emitido **con** evidencia, no por ausencia de ella: las tres precondiciones de integración
se verificaron y las tres dieron negativo.

---

## Resumen del ciclo

| | AUDIT-01 | AUDIT-02 |
|---|---|---|
| Workstreams auditados | 2 de 3 | **3 de 3** |
| Level 2 transversal | no ejecutable | **ejecutada** |
| Gates BLOCK | 1 (CNV) | **0** |
| Findings abiertos | 6 | 12 (+1 superado) |
| Afirmaciones verificadas | 13 | 22 |
| Afirmaciones refutadas | 1 | 1 |
| Correcciones del auditor | 2 | 3 |

El programa **mejoró de forma sustantiva**. El BLOCK de CNV se levantó, SEC entró y pasó,
Market se sostuvo. Que haya más findings no indica deterioro: indica que por primera vez se
pudo mirar las tres capas juntas, y la integración expone problemas que las auditorías
individuales no podían ver.

---

## Lo que mejoró, verificado

**SEC pasó de no-auditable a PASS.** Los cuatro conteos son exactos contra la base
(146.028 / 67.084 / 23.478 / 369), el gate cierra 9/9, y la cadena
EXPECTED→DISCOVERED→SELECTED→PARSED→PERSISTED no pierde nada: 27 esperados, 27 procesados,
0 rechazados, 0 errores de parseo. `link_relations` pasó de **0 a 146.028** — la pérdida
silenciosa de linkbases, que era el riesgo material de la etapa, quedó cerrada.

**CNV corrigió el falso PASS que motivó el BLOCK.** Verificado por simulación: cerrar
`C1-R-001` ahora produce **FAIL**. El control detecta lo que existe para detectar.

**La canonicalización de CNV está bien hecha.** Reimplementé sus dos regex sin importar el
módulo: 74/75 pares convergen, y **0 de 75 archivos RAW fueron reescritos** — el riesgo mayor
del fix quedó descartado empíricamente.

---

## Lo que la integración expuso

**La identidad no es canónica.** Es el hallazgo central. El puente CIK↔CUIT↔instrumento
*existe en los datos y es correcto*, pero atraviesa tres sistemas sin integridad referencial:

```
identity.entities @5433     7998 entidades · CUIT poblado en 0
identity.identifiers        CIK · TICKER · YF_SYMBOL   (no existe el tipo CUIT)
market_instruments @5432    entity_id=72 entero · SIN foreign key
dim_entity @ SQLite         la única fila que ata cuit=30546689979 a cik=0000904851
```

Preguntarle al modelo canónico el CUIT de una entidad devuelve NULL en las 7998. Una capa
económica se construye exactamente sobre esa junta.

**Market quedó separado.** Vive en otro servidor: ningún join SQL puede cruzarlo con
SEC/CNV. Y su script de escalamiento a 584 instrumentos ya está escrito, importando el motor
de M22 y heredando su destino de escritura por defecto —la base que el engine protege— sin
guarda alguna.

---

## Conducta de los workstreams

Merece registro, porque el auditor debe reportar lo que se sostiene igual que lo que falla.

**Los tres declararon sus propias limitaciones** en vez de presentarlas resueltas:

- SEC documentó que su comparación de determinismo se hizo contra stdout, no contra dos
  snapshots simultáneos, porque `parsed.*` es replace-all.
- CNV escribió en la evidencia del propio gate: *"escrituras RAW nuevas=75 de todos modos;
  eso ya NO es lo que este check mide"*. Esa franqueza es lo que permitió adjudicar F-004
  como decisión de diseño legítima en vez de como arreglo dudoso.
- Market documentó el riesgo de `catalaxia@5432` **él mismo**, antes de que el auditor lo
  encontrara.

**Ninguna capa corrige datos en silencio.** Market marcó como no benigno un cambio de volumen
del 0,002 %; CNV rechaza relaciones no declaradas; SEC clasifica 18 filings como `PRE_XBRL`
en vez de descartarlos. El sesgo hacia el flag antes que hacia el arreglo automático es la
propiedad correcta y se sostiene en las tres.

---

## Método y correcciones propias

Se recalculó en vez de leer, y donde hizo falta validar una implementación **se reimplementó
la especificación** en lugar de importar el módulo del worker — así se verificaron los
fingerprints de Market (AUDIT-01) y la canonicalización de CNV (AUDIT-02).

**Tres sospechas propias resultaron infundadas en este ciclo** y se descartaron antes de
emitir finding: el desfase horario de los artefactos de S03 (era UTC vs local UTC−3), el
`ON CONFLICT` aparentemente sin constraint (existe el índice único `ux_checkpoints_reuse`), y
`EMPRESA_PAGE` sin converger bajo canonicalización (era un cambio de contenido genuino —
CNV publicó una presentación nueva entre capturas — y terminó siendo la mejor prueba
disponible de que la canonicalización no enmascara sustancia).

En AUDIT-01 hubo dos correcciones equivalentes. Se registran porque un auditor que oculta sus
errores no es auditable.

---

## Estado del programa

```
SEC      S03 CHECKPOINTED · gate PASS 9/9 · READY_FOR_S04     PASS_WITH_WARNINGS
CNV      C3 run6 PASS 10/10 · BLOCK levantado                 PASS_WITH_WARNINGS
MARKET   M22 intacto · M23 con código, sin ejecución          PASS_WITH_WARNINGS
CROSS    3 precondiciones verificadas, 3 negativas            NOT_READY
```

Las cuatro condiciones para habilitar la capa canónica (F-011, F-001, F-013, F-012) son
**decisiones arquitectónicas, no trabajo de ingeniería mayor**. El auditor no las toma.
