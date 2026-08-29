# HOMOLOGATION_FINDINGS — verificación individual

**2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
Cada finding se **verificó contra la base**. Ninguno se dio por cerrado por
haber sido mencionado antes.

Leyenda de tipo (fase J): **INT** integridad · **GAR** garantía · **OPE** operativo ·
**COB** cobertura · **DEU** deuda histórica · **ADM** riesgo administrativo · **COS** cosmético

---

| finding | tipo | estado verificado | evidencia reconstruida | expl. `engine` | expl. owner | impacto en datos | homologación |
|---|---|---|---|---|---|---|---|
| **F-009** lifecycle de corridas | OPE | **CLOSED** | `engine.runs`: **0 RUNNING** sobre 241 (ABORTED 132 · BLOCKED 48 · OK 61) | no | no | ninguno | no bloquea |
| **F-014** `ticker_canonico` / `venue_ticker` | COB+DEU | **MITIGADO** | 584/584 con `venue_ticker`; divergen **exactamente 6**, todos ADR en NYSE | no | no | ninguno | **nota** |
| **F-024** BMA | INT | **CLOSED** | `0001347426` figura como **CIK/SEC** autoritativo; **0 filas** como CUIT | no | no | corregido | no bloquea |
| **F-026** `numerator`/`denominator` | INT | **CLOSED** | 44 units `DIVIDED`, **0 sin num/den**; 436 facts con ambos | — | — | recuperado | no bloquea |
| **F-027** | — | **N/A** | sin rastro en base ni contratos; no reproducible | — | — | — | — |
| **F-028** `ANALYZE` en S03 | OPE | **CLOSED** | las 8 tablas de `parsed` con `last_analyze` = 2026-08-27 | no | no | ninguno | no bloquea |
| **F-029** hash content-based | GAR | **CLOSED** | `hashout` ordena los hashes de fila antes de agregar → insensible al orden; determinismo 5/5 | no | no | ninguno | no bloquea |
| **F-031** `run_scope` en S03 | OPE | **CLOSED** | 3 usos de `run_scope` en `s03_parse_ypf.py` | no | no | ninguno | no bloquea |
| **F-032** duplicación de entidades | INT | **CLOSED** | **0** CIK autoritativos duplicados; 525 = 513 CIK + 12 sin ancla | no | no | ninguno | no bloquea |
| **F-034** | INT | **CLOSED** | sin contradicciones detectadas en la reconstrucción | no | no | ninguno | no bloquea |
| **F-035** estado vs identidad | GAR | **CLOSED** | **0** entidades `MERGED`/`DISSOLVED` con identidad autoritativa; 8 MERGED, todas con destino válido | no | no | ninguno | no bloquea |
| **F-036/F-037** evidencia estructurada | GAR | **CLOSED** | `ck_cuit_exige_evidencia_estructurada` presente; mutación: sin él, `LEGACY → CUIT` **entra** | no | no | ninguno | no bloquea |
| **F-038** persistencia de M23 | OPE | **CLOSED** | 591 filas / 584 instrumentos / 577 SUCCESS, todas con `sha256`; **60/60** hashes coinciden con disco | no | no | ninguno | no bloquea |
| **F-040** lifecycle de C3 | OPE | **CLOSED** | 0 RUNNING; C3 sin `start_run`/`finish_run` manuales | no | no | ninguno | no bloquea |
| **F-041** `source_facts` histórico | DEU | **CLOSED_WITH_NOTES** | **1** CIK autoritativo sin `source_facts` (YPF, `SEC_20F`) | no | no | ninguno | **deuda aceptada** |
| **F-042** `source_facts` mutable | GAR | **CLOSED** | mutar y borrar rechazados por `tg_assertion_inmutable`; mutación: sin él, **A13 y C3 reaparecen** | no | no | ninguno | no bloquea |
| **F-043** `EMPTY` nunca emitido | COB+OPE | **OPEN** | `EMPTY` emitido **0** veces; 14 filas `FAILED` con `error_type='EMPTY'`; 0 con datos | no | no | **ninguno** | **nota** |
| **F-044** política mutable | GAR | **CLOSED_WITH_NOTES** | `ck_politica_estructural_cik_lei` **validado**; mutación con política adulterada: sin él, `LEGACY → CIK` **entra** | no | no | ninguno | no bloquea |
| **F-045** coherencia assertion↔identifier | GAR | **CLOSED** | mutación: sin el trigger, **A4, A6, A7, A8 reaparecen** | no | no | ninguno | no bloquea |
| **F-046** 6 assertions sin `left_ref` | DEU | **CLOSED_WITH_NOTES** | 6 filas; **0 incoherencias de tipo**; imposible crear nuevas | no | no | ninguno | **deuda aceptada** |
| **F-047** bridges `CANDIDATE` + `VERIFIED` | COS | **CLOSED_WITH_NOTES** | 3 pares; **0 bridges VERIFIED contradictorios**; **0 mal formados** | no | no | ninguno | **nota** |

---

## Dos premisas del encargo que no resistieron la verificación

El encargo pide *«verificar exclusivamente lo que realmente existe»*. Dos de sus
propios enunciados no coinciden con la base:

### 1. «YPF/TGSU2: identidad resuelve pero actualmente 0 presentaciones fetcheadas»

**Falso.** Ambas fueron fetcheadas:

```
CUIT           GUIDs únicos   corridas   entidad
30546689979         4919          2      YPF SOCIEDAD ANONIMA
30657862068         2385          1      TRANSPORTADORA DE GAS DEL SUR S.A.
33650305499         1861          5      CENTRAL PUERTO S.A.
```

### 2. «CEPU: 33650305499 → 9.305 presentaciones»

**9.305 es el conteo de filas, no de presentaciones.** `fetch_raw.cnv_presentation`
tiene `UNIQUE (run_id, guid)`: es RAW inmutable **versionado por corrida**. CEPU tiene
**1.861 presentaciones únicas** observadas en 5 corridas — 1.861 × 5 = 9.305.

Contar filas ahí sobreestima la cobertura en un factor igual al número de corridas.

Se corrigen aquí por el mismo principio que el encargo aplica a M23: *no volver a
declarar algo que los artefactos desmienten*.

---

## Findings nuevos de este ciclo

**Ninguno.**

Una observación de método, no un defecto del sistema: en la primera pasada del banco
adversario, **tres mutaciones salieron «sin efecto»** —`ck_politica_estructural_cik_lei`,
`ck_cuit_exige_evidencia_estructurada` y `tg_identidad_exige_entidad_viva`—. No era que
las garantías fueran inertes:

- las dos primeras sólo actúan **con la política adulterada**, y el banco corría con
  política intacta, donde corta antes el trigger;
- el ataque de lifecycle estaba **mal construido**: reusaba la assertion de YPF, así que
  lo atrapaba `misma_entidad` antes de llegar al trigger de lifecycle.

Rehechas en el escenario correcto, las tres son concluyentes: **CON la garantía →
rechazado; SIN la garantía → entra.** Sin ese rehacer, este informe habría declarado
tres garantías verificadas sin evidencia real.
