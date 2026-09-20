# HOMOLOGATION_FINAL_GATE — Catalaxia

**2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
Reproducible: `python scripts/engine/homologacion_final.py`
Evidencia: `docs/review/HOMOLOGATION_FINAL_REPORT.md` ·
`docs/review/HOMOLOGATION_FINDINGS.md` ·
`outputs/docs/homologacion/homologacion_final.json`

---

# DICTAMEN: **HOMOLOGATED_WITH_NOTES**

No existe ningún camino reproducible de corrupción alcanzable por el rol operativo.
Las garantías críticas están demostradas y **mutadas**. Lo que queda son limitaciones
de cobertura, deuda histórica documentada y un riesgo administrativo acotado —
ninguno compromete la integridad del sistema operativo.

---

## Fase K — Las 17 preguntas

| | pregunta | respuesta | garantía que lo impide |
|---|---|---|---|
| 1 | ¿`catalaxia_engine` puede introducir identidad incorrecta? | **NO** | `tg_fuente_autoritativa_para_el_tipo` |
| 2 | ¿puede convertir un CIK en CUIT? | **NO** | `tg_identifier_coherente(left_ref_coincide)` |
| 3 | ¿una fuente no autorizada puede establecer un identificador? | **NO** | trigger + `ck_politica_estructural_cik_lei` + `ck_cuit_exige_evidencia_estructurada` |
| 4 | ¿una assertion puede contradecir el identifier que sostiene? | **NO** | `tg_identifier_coherente` (4 variantes) |
| 5 | ¿`MERGED`/`DISSOLVED` puede adquirir identidad? | **NO** | `tg_identidad_exige_entidad_viva` |
| 6 | ¿puede eliminarse provenance con el rol operativo? | **NO** | GRANT de columna + `tg_no_borrar_assertion` |
| 7 | ¿una corrida puede quedar `RUNNING` indefinidamente? | **NO** | `run_scope()`; **0 RUNNING** sobre 241 |
| 8 | ¿un checkpoint puede quedar en corrida no-OK? | **NO** | **0** checkpoints ligados a corrida ≠ OK |
| 9 | ¿`hash_out` detecta cambios semánticos? | **SÍ** | alterar 1 `value_numeric` cambia el digest; `updated_at` no |
| 10 | ¿S03/S04 son deterministas? | **SÍ** | 5/5 tablas, hash idéntico en dos pasadas |
| 11 | ¿el backfill es idempotente? | **SÍ** | 0 CIK duplicados; 525 = 513 + 12 |
| 12 | ¿Market tiene provenance suficiente? | **SÍ** | 577/577 SUCCESS con `sha256`; 0 `run_id` duplicados |
| 13 | ¿M23 ocurrió y sus artefactos son íntegros? | **SÍ** | 591 filas / 584 instrumentos; **60/60** hashes coinciden con disco |
| 14 | ¿Identity → CNV funciona donde existe CUIT? | **SÍ** | 3/3 con CUIT ratificado tienen presentaciones cargadas |
| 15 | ¿evita consultar CNV sin bridge `VERIFIED`? | **SÍ** | GGAL y BMA bloqueados antes de consultar |
| 16 | ¿las limitaciones de cobertura están bien tipificadas? | **NO del todo** | **F-043**: `EMPTY` existe en el CHECK y nunca se emite |
| 17 | ¿existe algún camino de corrupción por `catalaxia_engine`? | **NO** | 20/20 ataques rechazados, `BYPASS = 0` |

**Sólo la 16 no da la respuesta deseada, y es una tipificación, no una corrupción.**

---

## Adversarial final — `BYPASS = 0`

20 ataques con el rol operativo, 6 más con owner y política adulterada, todos desde
entidad limpia y en transacción revertida.

| barrera | ataques que detiene |
|---|---|
| `tg_fuente_autoritativa_para_el_tipo` | A1, A2, A3, A5 |
| `tg_identifier_coherente_con_assertion` | A4, A6, A7, A8 |
| `tg_identifier_autoritativo` | A9 |
| GRANT de columna | A10–A14, C2, C3 |
| `ux_identifier_autoritativo_unico` | A15, A16 |
| `tg_identidad_exige_entidad_viva` | C1 |
| `ck_politica_estructural_cik_lei` | A1, A2, A5 *con política adulterada* |
| `ck_cuit_exige_evidencia_estructurada` | A3 *con política adulterada* |

**C2 merece una nota**: el ataque «matar una entidad que sostiene identidad» lo detiene
el **GRANT**, no `tg_no_matar_entidad_con_identidad` — `catalaxia_engine` no puede
actualizar `entity_status`. La barrera de trigger existe y es la segunda; desde el rol
operativo nunca llega a ejercitarse. Doble cobertura, declarada.

---

## Mutación — cada garantía demostrada por su ausencia

| garantía eliminada | ataques que reaparecen |
|---|---|
| `tg_identifier_coherente_con_assertion` (F-045) | **A4, A6, A7, A8** |
| `ux_identifier_autoritativo_unico` | **A15, A16** |
| `tg_assertion_inmutable` (F-042) | **A13, C3** |
| `ck_politica_estructural_cik_lei` (F-044)* | **`LEGACY → CIK` entra** |
| `ck_cuit_exige_evidencia_estructurada` (F-036/037)* | **`LEGACY → CUIT` entra** |
| `tg_identidad_exige_entidad_viva` (lifecycle)** | **`MERGED` adquiere identidad** |

\* rehechas con la política adulterada, que es el único escenario donde actúan.
\*\* rehecha con el ataque bien construido (misma entidad, `MERGED`).

En la primera pasada las tres salieron «sin efecto». **No se aceptaron como PASS**: se
rehicieron en el escenario correcto y sólo entonces resultaron concluyentes.

---

## Clasificación de lo que queda (fase J)

| | tipo | por qué no bloquea |
|---|---|---|
| **F-043** `EMPTY` nunca emitido | **limitación de cobertura + defecto operativo** | 0 filas `FAILED` con datos, 0 precios, 0 RAW. Cuesta 7 requests inútiles por corrida; no corrompe |
| **F-041** 1 assertion sin `source_facts` | **deuda histórica** | no reproducible: ningún rol puede modificarla, y `SEC_REGISTRY`/`SEC_20F` son autoritativas para el tipo que sostiene |
| **F-046** 6 assertions sin `left_ref` | **deuda histórica** | 0 incoherencias de tipo; F-045 impide casos nuevos |
| **F-047** bridges `CANDIDATE` + `VERIFIED` | **cosmético** | 0 contradictorios; el código documenta que la ratificación es un acto nuevo |
| **F-014** `ticker_canonico` en ADR | **deuda + cobertura** | mitigado con `venue_ticker` 584/584; la semántica de origen sigue |
| **F-044** `DROP CONSTRAINT` por el owner | **riesgo administrativo** | no alcanzable por el rol operativo; es el límite de PostgreSQL, no un defecto |
| **56 BYMA sin CUIT** | **limitación de producto** | el sistema los deja afuera, que es lo correcto |
| **CNV 3 empresas** | **limitación de cobertura (G5)** | ninguna fuente publica el puente CIK↔LEI |

**Ninguno es defecto de integridad ni de garantía.**

---

## Por qué no es `HOMOLOGATED` liso

Por **F-043**, el único finding con estado `OPEN`: el sistema **tipifica una falta de
cobertura como fallo técnico**. No corrompe nada, pero es precisamente la distinción
que una homologación debe hacer bien, y hoy no la hace.

Y por la deuda histórica declarada (F-041, F-046) y el riesgo administrativo (F-044),
que no comprometen la operación pero existen.

## Por qué no es `BLOCKED`

Las tres condiciones de bloqueo se evaluaron y ninguna se cumple:

- **camino reproducible por el rol operativo**: `BYPASS = 0` en 20 ataques;
- **garantía crítica no demostrada**: las 6 críticas están demostradas **por mutación**;
- **corrupción o integridad no controlada**: 0 duplicados, 0 huérfanos, 0 contaminación
  de tipo, 0 entidades muertas con identidad, 0 provenance incompleta.
