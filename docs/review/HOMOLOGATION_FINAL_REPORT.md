# HOMOLOGATION_FINAL_REPORT — Catalaxia

**Fecha:** 2026-08-28 · **Rol:** auditor de homologación, independiente del implementador
**Instancias:** `catalaxia-engine-dev` 127.0.0.1:5433 (Identity/SEC/CNV/Market) ·
`catalaxia-db` 127.0.0.1:5432 (producción, sólo lectura)

**Método:** reconstrucción desde PostgreSQL, `data/raw` y artefactos. No se importó
código de implementación ni se reutilizaron resultados de los tests del implementador.
Toda prueba mutacional —incluido el DDL, que en PostgreSQL es transaccional— corrió en
transacciones revertidas.

**Nada fue modificado.**

---

# DICTAMEN: **HOMOLOGATED_WITH_NOTES**

---

## 1. Alcance homologado

| capa | evidencia reconstruida |
|---|---|
| **Identity V1** | 525 entidades (513 `ACTIVE` + 8 `MERGED` + 4 `PROVISIONAL`) · 614 assertions · 574 identifiers vigentes, 520 autoritativos · 0 duplicados · 0 huérfanos · 0 contaminación de tipo |
| **Garantías de identidad** | 20/20 ataques rechazados, cada uno por la garantía que declara; 6 garantías críticas demostradas **por mutación** |
| **SEC S03** | 27 filings = **18 PRE_XBRL + 9 con XBRL**; los 9 parseados. 67.084 facts · 23.478 contexts · 369 units · 13.412 concepts. **44 units `DIVIDED`, 0 sin `numerator`/`denominator`** · 0 facts sin `source_hash` |
| **SEC S04** | 47.930 facts derivados · 1.180 conflictos registrados · **0 `fact_key` duplicados** · **0 sin `source_fact_ids`** · 47.930 con checkpoint de entrada |
| **Determinismo / hash** | 5/5 tablas con digest idéntico en dos pasadas; detecta un cambio de `value_numeric` e **ignora** `updated_at` |
| **Lifecycle** | **0 corridas `RUNNING`** sobre 241 · **0 checkpoints ligados a corrida ≠ OK** |
| **Market M23** | 591 filas / 584 instrumentos / 577 SUCCESS · 577/577 con `sha256` · 0 `run_id` duplicados · **60/60 hashes coinciden con el disco** · 598 `history.csv` + 598 `meta.json` = **1.196 artefactos** |
| **Backfill CIK** | 513 CIK autoritativos · **CUIT autoritativos: 3**, los tres ratificados por persona · **0 bridges automáticos** |
| **Aislamiento** | Market no escribe en 5432; `catalaxia_engine` **no tiene acceso** a las tablas de Market |

## 2. Alcance NO homologado

| | motivo | tipo |
|---|---|---|
| **CNV a escala** | 3 empresas de 512 elegibles en Market. La brecha **es G5**: ninguna fuente publica el puente CIK↔LEI | limitación de cobertura |
| **Los 56 emisores BYMA** | sin CIK no hay ancla; su CUIT legacy es `CORROBORATING` y nunca llega a autoritativo | limitación de producto |
| **Cobertura EDGAR completa** | sólo se auditó el CIK piloto (27 filings) | alcance no auditado |
| **Semántica de `ticker_canonico`** | mitigada con `venue_ticker`, no corregida | deuda |

---

## 3. Garantías verificadas, con su evidencia

| # | garantía | mecanismo | demostrada por |
|---|---|---|---|
| 1 | tipos de identificador | `ck_formato_identificador` | A2 (CIK como CUIT rechazado) |
| 2 | unicidad autoritativa | `ux_identifier_autoritativo_unico` | A15, A16 · **mutación: reaparecen** |
| 3 | coherencia assertion↔identifier | `tg_identifier_coherente_con_assertion` | A4, A6, A7, A8 · **mutación: reaparecen** |
| 4 | autoridad de fuente | `tg_fuente_autoritativa_para_el_tipo` + `ck_politica_estructural_cik_lei` | A1, A2, A3, A5 · **mutación con política adulterada** |
| 5 | evidencia estructurada | `ck_cuit_exige_evidencia_estructurada` | **mutación: `LEGACY → CUIT` entra sin él** |
| 6 | inmutabilidad | `tg_assertion_inmutable` | A13, C3 · **mutación: reaparecen** |
| 7 | lifecycle de entidad | `tg_identidad_exige_entidad_viva` | C1 · **mutación: `MERGED` adquiere identidad sin él** |
| 8 | `CANDIDATE` no ancla | `tg_identifier_autoritativo` | A9 |
| 9 | `VERIFIED` exige evidencia | `ck_verified_exige_evidencia` | 0 assertions VERIFIED incompletas |
| 10 | `HUMAN_DECISION` la firma una persona | `ck_humano_no_es_proceso` | 0 firmadas por proceso |
| 11 | retiro | permitido por diseño | verificado: retirar siempre funciona |
| 12 | supersede | `superseded_by` + `valid_to` | 6 cadenas completas |
| 13 | conflictos | `conflict` | 1 registrado (BMA), no resuelto en silencio |
| 14 | bridges | `ck_authoritative_metodo` | 3 `VERIFIED` por `HUMAN_DECISION`, 0 mal formados |
| 15 | aislamiento de roles | GRANTs de columna | A10–A14 · `engine` sin acceso a Market |
| 16 | lifecycle de corridas | `run_scope()` | 0 `RUNNING` sobre 241 |
| 17 | checkpoints | FK a `runs` | 0 en corrida ≠ OK |
| 18 | hash de contenido | `hashout` v2 | detecta semántico, ignora `updated_at` |
| 19 | determinismo | `hashout` ordena antes de agregar | 5/5 idénticos |
| 20 | idempotencia | resolución por candidatos (F-032) | 0 duplicados sobre 513 |

---

## 4. Identity → CNV: corrección y cobertura

El encargo afirma *«YPF/TGSU2: identidad resuelve pero actualmente 0 presentaciones
fetcheadas»*. **La base dice otra cosa:**

| | CUIT | bridge | GUIDs únicos | corridas | estado |
|---|---|---|---|---|---|
| YPF | 30546689979 | Federico | **4.919** | 2 | cargada |
| TGSU2 | 30657862068 | Federico | **2.385** | 1 | cargada |
| CEPU | 33650305499 | Federico | **1.861** | 5 | cargada |
| **GGAL** | — | sin ratificar | 0 | 0 | **bloqueado, correcto** |
| **BMA** | — | sin CUIT demostrable | 0 | 0 | **bloqueado, correcto** |

Y **«CEPU → 9.305 presentaciones»** confunde filas con presentaciones:
`fetch_raw.cnv_presentation` tiene `UNIQUE (run_id, guid)` — es RAW inmutable
**versionado por corrida**. 1.861 × 5 corridas = 9.305 filas. Contar filas ahí
sobreestima la cobertura por el número de corridas.

Se corrige por el mismo principio que el encargo aplica a M23: **no declarar algo que
los artefactos desmienten**.

GGAL y BMA no son fallos: son la prueba de que el sistema **se detiene** cuando no hay
identidad demostrada. Si el CUIT saliera de `dim_entity`, ambos habrían fetcheado.

---

## 5. Riesgos residuales

1. **Administrativo (F-044).** El owner puede `ALTER TABLE … DROP CONSTRAINT`. Ninguna
   garantía en PostgreSQL sobrevive a su owner. Lo que cambió es la naturaleza del acto:
   adulterar `identity_v1.source` era un `UPDATE` de datos —invisible en un diff de
   schema, plausible como mantenimiento—; quitar el CHECK es DDL. **No alcanzable por el
   rol operativo.**

2. **Acoplamiento en `ck_cuit_exige_evidencia_estructurada`.** Ese constraint hace dos
   trabajos: exige evidencia **y** enumera qué fuentes establecen CUIT. Modificarlo
   pensando sólo en la evidencia tocaría también la política. Demostrado por mutación.

3. **Operativo (F-043).** Los 7 instrumentos `EMPTY` se re-piden en cada corrida de
   Market. 7 requests inútiles; sin pérdida ni corrupción.

4. **Deuda histórica (F-041, F-046).** 7 assertions que cumplen el contrato de su
   momento pero no los posteriores. No reproducibles: ningún rol puede modificarlas y
   F-045 impide casos nuevos.

---

## 6. Nota de método

En la primera pasada del banco, **tres mutaciones salieron «sin efecto»**. No se
aceptaron: se investigó por qué.

- `ck_politica_estructural_cik_lei` y `ck_cuit_exige_evidencia_estructurada` sólo actúan
  **con la política adulterada**, y el banco corría con política intacta, donde corta
  antes el trigger.
- El ataque de lifecycle estaba **mal construido**: reusaba la assertion de YPF, así que
  lo detenía `misma_entidad` antes de llegar al trigger de lifecycle.

Rehechas en el escenario correcto, las tres son concluyentes. Sin ese rehacer, este
informe habría declarado tres garantías verificadas sin evidencia real — que es
exactamente lo que el encargo prohíbe.

---

## 7. Decisión final

**HOMOLOGATED_WITH_NOTES.**

El sistema es seguro y operativo dentro del alcance definido. No existe camino
reproducible de corrupción alcanzable por el rol operativo, y las garantías críticas
están demostradas por su ausencia, no sólo por tests en verde.

Lo que impide un `HOMOLOGATED` liso no es un defecto de integridad: es **F-043**, donde
el sistema tipifica una falta de cobertura como fallo técnico — la misma distinción que
esta homologación tuvo que hacer para no bloquear por cosas que no lo merecen.

**Este ciclo termina acá.** No se corrigió nada y no se abre otro workstream.

---

### Estado de la base al cerrar

```
entidades 525 · assertions 614 · identifiers vigentes 574 · CIK 513 · CUIT 3
reviews OPEN 11 · conflicts 1 · bridges VERIFIED 3 · corridas RUNNING 0
```
