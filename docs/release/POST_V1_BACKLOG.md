# POST-V1 BACKLOG — Catalaxia

**Emitido:** 2026-08-28, al cerrar `CATALAXIA V1.0 — HOMOLOGATED_WITH_NOTES`
**Nada de esto se implementó.** Es el registro de lo que queda, priorizado.

---

## P0 — Operación

### F-043 · clasificación `EMPTY` vs `FAILED`

`market_raw_runs.status` admite `EMPTY` por CHECK y el código **nunca lo emite**:
`m2_fetch_engine.py:229` escribe `FAILED` y manda `"EMPTY"` al log.

**Qué cuesta hoy:** `m6_scale.ya_exitosos()` filtra por `SUCCESS`, así que los 7
instrumentos se re-piden en **toda** corrida futura del mismo stage, sin posibilidad de
éxito si la ausencia es real.

**Qué falta decidir, no sólo programar:** el sistema no distingue una ausencia
*transitoria* (la fuente no respondió) de una *permanente* (el símbolo no existe). Sin
esa distinción no se puede decidir si reintentar es correcto. Emitir `EMPTY` es la
mitad; la otra mitad es qué debe hacer `--resume` con ese estado.

Los 7: `DGCE.BA · SATS · CAAP.BA · VIST.BA · GGALB.BA · SUPVB.BA · YPFLUZ.BA`.
Sin pérdida ni corrupción: 0 filas declarando datos, 0 precios, 0 RAW.

### Nota operativa · `instrument_id=480` (SATS) sin `exchange`

Detectado durante la homologación. Dato incompleto en `market_instruments`, sin
impacto verificado.

---

## P1 — Cobertura

- **CNV completo.** Hoy 3 empresas de 512 elegibles en Market. La brecha **es G5** y no
  se cierra con código: cada CUIT exige una ratificación humana.
- **Emisores argentinos con CIK.** Cola de **9 ADR** pendientes de ratificación
  (13 con CIK − 3 ratificados − GGAL excluido).
- **BYMA (56 emisores).** Bloqueado estructuralmente: sin CIK no hay ancla, el CUIT
  legacy es `CORROBORATING`, y buscar el LEI por razón social es la inferencia que
  F-024 mostró que no se puede hacer. **Requiere una decisión de producto sobre qué
  evidencia se acepta**, o conectar AFIP (autoritativa, con captcha).
- **Universo EDGAR completo.** La cobertura de `parsed` frente a EDGAR no fue auditada.

---

## P2 — Identidad

- **GGAL.** Tiene bridge `CANDIDATE` (#100) y no ratificado. GLEIF devuelve
  `RA999999` / `registeredAs = null`: **no hay CUIT publicable**. Requiere otra fuente.
- **BMA.** CIK correctamente tipado (F-024). GLEIF devuelve **dos LEI** para la razón
  social; elegir por domicilio sería inferencia. `review` abierta.
- **Bridges nuevos.** Sólo cuando exista evidencia de ambos extremos por separado, con
  motivo escrito y firma de persona. No automatizable — es G5.
- **F-041 / F-046 (opcional).** Re-afirmar las 7 assertions con `left_ref` y
  `source_facts`. No aporta seguridad: es higiene. Requiere autorización explícita para
  volver sobre F-041.
- **F-047 (documental).** El modelo no distingue «supersedido» de «confirmado». Un
  consumidor futuro que cuente bridges vigentes sin filtrar por `status` vería 7 donde
  hay 3 establecidos. Todos los consumidores actuales filtran.

---

## P3 — Escala

- **Backfill argentino.** Depende de P1/P2: sin CUIT no hay ancla para CNV.
- **Automatización de la cola de ratificación.** Automatizable el *dossier* (reunir
  evidencia de ambos extremos), **nunca la decisión**.
- **Cobertura adicional de Market** más allá de los 584 instrumentos.

---

## Deuda de diseño registrada (sin prioridad asignada)

**`ck_cuit_exige_evidencia_estructurada` hace dos trabajos:** exige evidencia
estructurada **y** enumera qué fuentes pueden establecer un CUIT. Modificarlo pensando
sólo en la evidencia tocaría también la política de fuente. Demostrado por mutación en
el ciclo de F-044.

Además, ese CHECK no condiciona por `subject_type`: hoy no falla sólo porque ningún
bridge tiene `left_ref` de tipo `CUIT`. `ck_politica_estructural_cik_lei` sí lo
condiciona, precisamente porque los 3 bridges `VERIFIED` tienen `left_ref='CIK:SEC:…'`
y habrían quedado atrapados.

**`identity_v1.source` sigue sin trigger de inmutabilidad ni historial** (F-044). Ya no
es la única barrera —las garantías estructurales no la consultan— pero sigue siendo la
única tabla de `identity_v1` sin protección propia.
