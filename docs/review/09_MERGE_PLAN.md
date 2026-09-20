# 09 — Merge Plan (define, no ejecuta)

**FASE 2 — REINGENIERÍA, PASO 9.** Plan de convergencia a partir de 01–08 (07 define objetivo, 07A confirma D1–D10, 08 define deletes). Este paso DEFINE; NO implementa ni ejecuta (cero merges/deletes/archives/moves/cambios de código, DB, migraciones o producción). "Duplicado" ≠ "fusionable": cada merge exige las 14 demostraciones (§7 del encargo); sin evidencia → MERGE_PENDING_EVIDENCE. Tipos: SEMÁNTICO (bridge, implementaciones separadas) · IMPLEMENTACIÓN (core común con modos) · DATOS (store canónico; máximo riesgo, prohibido sin equivalencia).

## M1 — Identity V0 ↔ V1: MERGE SEMÁNTICO (bridge) → MERGE_CONDITIONAL

- Identificación: M1 · engine/identity.py + engine/identity_v1.py + c3_identity_link + backfills · C2 · DATOS (+CONTROL como consumidor).
- Problema: mismo concepto, dos autoridades sin bridge (05 G1).
- Tipo: SEMÁNTICO — qué significa: assertions de equivalencia v0↔v1 (solo lectura) + migración progresiva de lectores; qué NO significa: ni fusión de tablas, ni doble escritura, ni eliminación de ningún sistema.
- Queda en V0: entities/identifiers/reviews + s01 como writer. Queda en V1: entity/identifier/source + assertions/reviews/conflicts/instruments + writers actuales. Bridge: tabla/función de equivalencia por CIK/CUIT con provenance (assertion firmada por proceso, versionada). Migración: lectores nuevos al bridge; s03→sigue v0, s04/ratio→siguen v1 hasta R7.4-verificación. V0 desaparece solo por decisión posterior (no en este plan).
- Evidencia: semántica `[CÓDIGO]` (mismo concepto, 06 IDENTITY); funcional `[CÓDIGO]` (granularidad distinta); consumidores `[CÓDIGO]` (disjuntos). Equivalencia numérica: n/a (identidad, no magnitud).
- Evitar dos autoridades: durante la coexistencia la autoridad de escritura no cambia en ningún sistema; el bridge no escribe identidad (solo equivalencias).
- IDENTIDAD≠CLASIFICACIÓN conservada (ambos sistemas la separan).
- Sustituto resultante: capa de resolución unificada (lectura). Dependencias: R7.4; tests de resolución cruzada (extender test_cnv_identity_link). Impacto C2/DATOS. Riesgo R2 (doble autoridad temporal). Rollback R3 (bridge off, sistemas intactos). Verificación: resolución cruzada por CIK/CUIT + adversarial. C10: suite del bridge. C11: n/a. C12: n/a.
- Estado: **MERGE_CONDITIONAL** (condición: diseño bridge + tests verdes + ambos sistemas intactos).

## M2 — facts ↔ derived.fact: BRIDGE (NO merge de datos) → MERGE_CONDITIONAL (puente) + NO_MERGE (datos)

- Identificación: M2 · construir_base.facts + s04.derived.fact · C6 · DATOS.
- Problema: mismo hecho SEC en dos stores (05 G2). Tipo: SEMÁNTICO-puente de trazabilidad; explícitamente NO MERGE DE DATOS (07 D2-alt rechazada: distinta granularidad/store/provenance/consumidores; equivalencia no demostrada).
- Bridge: mapear `source_fact_ids` ↔ filas `facts` (solo lectura, documentado por muestreo). Sin sincronización (no hay qué sincronizar: granularidades distintas). `fact_financials` fuera de alcance (dominio CNV-legacy; su archive vive en 08-D2/A4).
- Evidencia: semántica `[CÓDIGO]`; granularidad/store/consumidores `[CÓDIGO]` (06 RATIOS); equivalencia de contenido `[NO DETERMINABLE]` (por eso no hay merge de datos).
- Sustituto: ninguno (cada dominio conserva su store). Dependencias: R7.5; identidad estable (puente usa entity_key/CIK). Riesgo R1 (solo lectura). Rollback R1. Verificación: muestreo cruzado CIK/período documentado. C10/C11/C12: n/a.
- Estado: **MERGE_CONDITIONAL** (puente; condición: muestreo + R7.5) y **NO_MERGE** (datos; hasta equivalencia demostrada, que el plan no prevé).

## M3 — UPDATE / ALL / SCREENER: MERGE DE IMPLEMENTACIÓN (core + modos) → MERGE_CONDITIONAL

- Identificación: M3 · run_update + run_all + run_screener + s0..s9 + jobs · C7 · EJECUCIÓN+CONTROL.
- Problema: mismo output nominal por 3 caminos con divergencia real (subset-72/incremental vs universo/flags vs phases-import; rebuild omite s9) (05 G3, 04 §14).
- Tipo: IMPLEMENTACIÓN — core rebuild parametrizable con modos (incremental-subset | full-universe | phases-import; s9 opcional; CNV=subprocess|pre-extraído; EDGAR=incremental|full; IPC mensual como prerrequisito). NO "pipeline único" que elimine capacidades (§10 del encargo).
- Entry points sobreviven como fachadas hasta equivalencia funcional demostrada (matriz de modos).
- Evidencia: orden/inputs/outputs `[CÓDIGO]` (run_update:589-656; run_all; run_screener); logs `[EJECUCIÓN]` (quarterly); equivalencia funcional `[NO DETERMINABLE]` (no comparada) → por eso condicional, no aprobado.
- Sustituto: core + 3 fachadas. Dependencias: R7.9; R7.3 (`empresas` ownership, el rebuild la escribe); R7.6 (jobs estables); IPC mensual operativo. Impacto C7/EJECUCIÓN. Riesgo R2. Rollback R1 (fachadas intactas = fallback inmediato). Verificación: matriz modos × (subset/full/s9/CNV/EDGAR) con outputs comparados. C10: suite por modo. C11: n/a (el camino no la tiene; ver D9). C12: vía s5/sync existentes.
- Estado: **MERGE_CONDITIONAL** (condición: matriz de modos verde + R7.3/R7.6 estables).

## M4 — Publication: MERGE DE IMPLEMENTACIÓN en publisher (+ legacy a 08) → MERGE_CONDITIONAL

- Identificación: M4 · migrate + sync + publicar_v2 + s5 + publisher futuro + api · C12 · DATOS+EJECUCIÓN+CONTROL.
- Problema: 3 publicadores solapados + 1 sin lector (05 G5/G17, 04 §8, 06 §21).
- Tipo: IMPLEMENTACIÓN — convergen en el publisher canónico (D8): migrate→REPLACE por publisher (vía 08, nunca inverso); sync-PLAN como transporte tras gate (se conserva el mecanismo); publicar_v2→DEPRECATE (o staging si R7.1 lo justifica con criterios A7); s5 conserva export + gate (§20 del 07). Distinguir de ELIMINACIÓN de legacy (vive en 08, con su secuencia).
- Un solo gate: C10 PASS + C11 CERTIFIED (D9/A2), aplicado en swap PG y export CSV con mismos insumos; D8=mecanismo, D9=regla.
- Evidencia: destinos/mecanismos `[CÓDIGO]` (sync PLAN, migrate TRUNCATE+swap, DESTINO screener_v2, s5 OUT); solape 7 tablas `[CÓDIGO]`; lectores `[CÓDIGO]`+gaps (screener_hist ND).
- Sustituto: publisher + gate + api (con hist resuelto). Dependencias: R7.1 (diseño+staging), R7.10 (gate), gap hist (07 §10). Riesgo R3 (toca C12; mitigado por staging+swap+snapshot). Rollback R2 (publisher anterior + snapshot pre-swap). Verificación: tabla-nunca-vacía + suite publicación + bloqueo-sin-certificado. C10: suite staging. C11: exigida por el gate. C12: el propio objeto.
- Estado: **MERGE_CONDITIONAL** (condición: publisher R7.1 + gate R7.10 + hist resuelto).

## M5 — Motores de ratios: NO MERGE (diseño de equivalencia) → MERGE_PENDING_EVIDENCE

- Identificación: M5 · calcular_ratios_base + ratio_engine + f4_ratios + s2_ratios_cnv · C8 · DATOS.
- Problema: 4 motores, equivalencia no probada (05 §23, D7 CONDICIONAL).
- Lo que produce/consume/define cada uno: 06 RATIOS + 05 §8 (fuentes facts/derived+market/fact_financials/cnv_norm; salidas ratios/derived.ratio/fact_ratios/ratios_cnv; claves cik-PK-fila vs ratio_key vs cuit; redondeo motor-PG `round(...,6)` verificado, resto `[NO DETERMINABLE]`).
- Diseño de prueba (§12 del encargo): por CIK + período + ratio + unidad + moneda; join por claves canónicas (cik↔cuit vía mapa_entidades/identity); tolerancias: **sin justificación en evidencia** → por defecto igualdad exacta sobre valores canonizados; tolerancia solo si R7.2 la fundamenta (queda TBD, no inventada).
- Evidencia: estructural `[CÓDIGO]`; numérica `[NO DETERMINABLE]` → ningún merge proponible.
- Dependencias: R7.8; facts estables (D2/R7.5); IPC fijado (A10). Riesgo: n/a (sin cambio). Rollback: n/a.
- Estado: **MERGE_PENDING_EVIDENCE** (la prueba primero; el merge, si algo, después y fuera de este plan).

## M6 — precios market/producto: NO_MERGE

- Identificación: M6 · market_price_daily + precios (+precios_diarios) · C6/C8 · DATOS.
- Por qué no se fusionan (D6, 05 G8/§13): distinto instrumento-modelo (PG con instruments/mappings vs SQLite directa), distinta fuente-cadena (market_* vía m2 vs yfinance directo), distintos consumidores (ratio motor vs s4-producto), distinta granularidad temporal (serie canónica vs foto + diario aparte). Fusionar por "contienen precios" violaría la regla §7 (criterios 2–7).
- Evidencia: `[CÓDIGO]` (cadenas y consumidores disjuntos). Estado: **NO_MERGE** (permanecen separados; puente lector ya existe vía ratio_engine).

## M7 — StageReport vs dict s04: MERGE DE IMPLEMENTACIÓN menor → MERGE_CONDITIONAL

- Identificación: M7 · engine.report + dict legacy s04 · C9 · CONTROL.
- Tipo: IMPLEMENTACIÓN (ADAPT s04 a StageReport; mismo contrato C10 ya cumplido). Evidencia `[CÓDIGO]` (05 G10, 07A). Sustituto: StageReport uniforme. Dependencias: ninguna (mecánica acotada). Riesgo R1. Rollback R1. Verificación: test de contrato C10 (extender test_c11_contract). C10: el propio contrato.
- Estado: **MERGE_CONDITIONAL** (condición: test verde; ejecutable en cualquier fase temprana).

## Matriz global (§15)

| ID | Componentes | Tipo | Capa | Planos | Evidencia | Equivalencia | Sustituto | Dependencias | Riesgo | Rollback | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | identity v0/v1 | SEMÁNTICO | C2 | DATOS | CÓDIGO | concepto sí; impl. no | capa resolución | R7.4, tests | R2 | R3 | MERGE_CONDITIONAL |
| M2 | facts/derived | SEMÁNTICO-puente (+NO datos) | C6 | DATOS | CÓDIGO+ND | concepto sí; contenido ND | ninguno (stores quedan) | R7.5, muestreo | R1 | R1 | CONDITIONAL / NO_MERGE-datos |
| M3 | update/all/screener | IMPLEMENTACIÓN | C7 | EJEC+CTRL | CÓDIGO+EJEC | nominal sí; funcional ND | core+fachadas | R7.9, R7.3, R7.6, IPC | R2 | R1 | MERGE_CONDITIONAL |
| M4 | publishers | IMPLEMENTACIÓN | C12 | D+E+C | CÓDIGO | destinos sí; mecanismo no | publisher+gate | R7.1, R7.10, hist | R3 | R2 | MERGE_CONDITIONAL |
| M5 | 4 motores | — (diseño prueba) | C8 | DATOS | ND numérica | ND | ninguno | R7.8, facts, IPC | — | — | MERGE_PENDING_EVIDENCE |
| M6 | precios | NO_MERGE | C6/C8 | DATOS | CÓDIGO | concepto; resto no | — | — | — | — | NO_MERGE |
| M7 | StageReport/dict | IMPLEMENTACIÓN | C9 | CONTROL | CÓDIGO | contrato sí | StageReport | test C10 | R1 | R1 | MERGE_CONDITIONAL |

## Matriz de equivalencia (§16)

| Merge | Semántica | Función | Datos | Numérica | Provenance | Consumidores | Resultado |
|---|---|---|---|---|---|---|---|
| M1 | PASS | ND (granularidad) | ND (stores) | n/a | PASS (assertions) | ND (migración) | CONDITIONAL |
| M2-puente | PASS | PASS (trazar) | ND | ND | PASS (muestreo) | PASS (sin cambio) | CONDITIONAL |
| M2-datos | PASS | FAIL (granularidad) | FAIL (stores) | ND | — | FAIL (disjuntos) | NO_MERGE |
| M3 | PASS | ND | PASS (mismo output nominal) | ND | ND | PASS (mismos) | CONDITIONAL |
| M4 | PASS | PASS | PASS (destinos) | n/a | PASS (boletín+logs) | PASS (api) | CONDITIONAL |
| M5 | PASS (concepto) | ND | ND | ND | ND | ND | PENDING_EVIDENCE |
| M6 | PASS (concepto) | FAIL | FAIL | ND | — | FAIL | NO_MERGE |
| M7 | PASS | PASS | PASS | n/a | PASS | PASS | CONDITIONAL |

(ND = NO DETERMINABLE; nunca convertido en PASS.)

## Matriz de gates (§17)

| Merge | Precondición | Test | Ejecución | C10 | C11 | C12 | Backup | Rollback | Gate |
|---|---|---|---|---|---|---|---|---|---|
| M1 | R7.4 + tests diseño | cruce CIK/CUIT + adversarial | staging | suite bridge | n/a | n/a | SHA | R3 probado | tests verdes + sistemas intactos |
| M2 | R7.5 + muestreo | muestreo documentado | lectura | n/a | n/a | n/a | n/a | R1 | muestreo + revisión |
| M3 | R7.3/R7.6 + IPC | matriz de modos | staging | suite/modo | n/a | vía s5/sync | SHA | R1 (fachadas) | modos verdes + fachadas |
| M4 | R7.1 + hist + R7.10 | suite publ. + bloqueo-sin-cert | staging | suite staging | exigida | el objeto | snapshot | R2 probado | tabla-no-vacía + bloqueo |
| M5 | R7.8 + diseño §M5 | prueba numérica | lectura | n/a | n/a | n/a | n/a | n/a | prueba (futura) |
| M7 | test C10 | contrato extendido | directo acotado | el contrato | n/a | n/a | SHA | R1 | test verde |

## Relación con 08 (§18)

Merge precede a delete, nunca al revés: M4-publisher es precondición para retirar migrate (08: el REPLACE de migrate vive aquí como convergencia; su retiro físico sigue la secuencia de 08); M3-core precede al archive f-series (08-E); M2-puente no habilita ningún delete (los stores quedan); M1 no habilita delete de ningún sistema (ambos quedan); M7 no habilita deletes. Orden: MERGE/MIGRATE→VERIFICAR→VENTANA→ARCHIVE→eventualmente DELETE.

## Relación con R7.1–R7.12 (§19)

M1→R7.4 · M2→R7.5 · M3→R7.9 (tras R7.3/R7.6) · M4→R7.1+R7.10 · M5→R7.8 (prueba) · M6→ninguna (no-merge) · M7→cualquier fase temprana. Sin conflictos de fase.

## FX (§20)

Ningún merge toca columnas de moneda ni contradice D10: los puentes preservan `moneda`/unidad de origen; el core conserva el manejo de moneda por modo; market/producto separados mantienen sus cadenas FX; el servicio FX (R7.11) consume C6 posterior. OFFICIAL/MEP/CCL + 8 columnas, intactos como objetivo.

## Golden cases (§21)

Merges genéricos por CIK/cuit/run/período; ningún diseño hardcodea YPF (bridge, core y publisher parametrizan emisor; las pruebas de equivalencia deberán correrse multi-emisor en R7.2/R7.8, con YPF como un caso entre otros, no como techo).

## Resultado final (§22)

- MERGE FUTURO APROBABLE: ninguno incondicional (todo merge exige su gate; el más cercano es M7 tras test).
- MERGE CONDICIONAL: M1, M2-puente, M3, M4, M7 (condiciones en §17).
- MERGE BLOQUEADO: ninguno como estado propio (los bloqueos de borrado viven en 08; aquí M5 espera evidencia y M6/M2-datos se rechazan).
- NO MERGE: M2-datos, M6 (permanecen separados por arquitectura).
- EVIDENCIA FALTANTE: equivalencia numérica ratios (diseño M5), equivalencia funcional M3 (matriz de modos), lectores huérfanos (vía 08/R7.2), serie IPC fijada (A10).

## Seguridad (§23)

Ningún merge ejecutado. "MERGE_CONDITIONAL" = arquitectura planificable, no ejecución. Merges de datos destructivos (ninguno propuesto; M2-datos explícitamente NO) quedarían condicionados a backup+equivalencia+validación+rollback. R4 prohibido sin evidencia excepcional + autorización posterior específica (no otorgada).

## Verificación final (§25)

- `09_MERGE_PLAN.md` existe; 07/07A/08 intactos; código/DB/migraciones/producción intactos; cero merges/deletes/archives/moves/renames/refactors ejecutados (solo lectura + este documento).

MERGE_PLAN_STATUS = READY_FOR_IMPLEMENTATION

(El plan es implementable exclusivamente vía sus gates: M1–M4/M7 condicionados, M5 en espera de evidencia, M6 y M2-datos rechazados. Ningún merge autorizado fuera de su gate.)