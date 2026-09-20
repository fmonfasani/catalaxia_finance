# 07 — Reengineering Plan

**FASE 2 — REINGENIERÍA, PASO 7.** Plan verificable a partir de 01–06 (única base). Este paso DECIDE arquitectura; NO ejecuta DELETE/MERGE/REPLACE/ARCHIVE/MOVE/RENAME/REFACTOR/MIGRATION/SCHEMA/CODE/PROD. Cada decisión trae 14 campos (§REGLA). Sin evidencia no hay decisión (→ PENDIENTE DE EVIDENCIA).

- CAPA: 12 capas C1–C12 (sin capa 13). PLANOS: DATOS/CONTROL/EJECUCIÓN/INFRAESTRUCTURA.
- CICLO: relevamiento 01→06 completo, cruzado y con contradicciones registradas (04 §21).
- HOY: §HOY abajo (arquitectura real: cron screener productivo + motor SEC certificado sin llegada a usuario + 3 publicadores PG + dualidades identidad/hechos/precios).
- OBJETIVO: §OBJETIVO abajo (una cadena inequívoca FUENTE→...→C12 con gate de certificación, ownership único por objeto, dualidades con bridge o dominio separado).
- DECISIÓN: matrices §5–§6 (estados DECIDIDO/CONDICIONAL/PENDIENTE/RECHAZADO; acciones KEEP/ADAPT/MERGE/REPLACE/ARCHIVE/DELETE/DEPRECATE/REVIEW — todas a futuro).
- EVIDENCIA: citas 01–06 + §10 (gaps). Lo no demostrable queda PENDIENTE, nunca se infiere.

## 1. Resumen ejecutivo

1. Lo más riesgoso (R4) es la publicación: PG `screener` depende de `migrate_sqlite_to_pg` (TRUNCATE+swap) y `screener_hist` no tiene writer. Fase R7.1 lo reemplaza por publisher con staging+swap atómico y gate C10/C11.
2. Nada productivo se toca sin sustituto verificado: cada DELETE/MERGE candidato exige precondición de evidencia (§8) y rollback (§9).
3. Las dualidades identidad (v0/v1) y hechos (facts/derived.fact) se resuelven con bridge + dominio canónico, no con borrado: ambos lados tienen consumidores vigentes.
4. Los 3 pipelines screener convergen en un core con modos (sin sacrificar incremental/subset/s9/CNV/EDGAR).
5. La certificación (c11 + 40_certificar) se vuelve condición necesaria de publicación mediante gate en el publisher, sin mezclar C10 con C11.
6. FX/multimoneda y multiemisor quedan como arquitectura objetivo (D10 + Golden Cases), fuera de implementación.

## 2. Problemas prioritarios

| # | Problema | Severidad | Evidencia |
|---|---|---|---|
| P1 | migrate TRUNCATE único camino a PG `screener` | R4 | 06 §21 CRÍTICO |
| P2 | `screener_hist` servida sin writer | R4 (hueco) | 04 §13, 06 §21 |
| P3 | jobs CNV con `verify=False` en camino productivo | R3 | 06 §21 ALTO |
| P4 | sync reemplazo en PG prod sin dry-run + shell/SSH | R3 | 06 §21 ALTO |
| P5 | identidad dual sin bridge (v0/v1) | R2 estructural | 05 G1, 06 IDENTITY |
| P6 | hechos duales sin bridge (facts/derived.fact) | R2 estructural | 05 G2 |
| P7 | `empresas` 4 writers (uno con DROP) | R2+riesgo | 03 §16.4, 05 G11 |
| P8 | 3 generadores de `screener` con divergencia s9/subset | R2 operativo | 05 G3 |
| P9 | certificación no llega a publicación | R2 arquitectónico | 04 §17, 06 §15 |
| P10 | motores de ratios sin equivalencia numérica | R2 (bloquea merges) | 05 §23, 06 RATIOS |

## HOY

Arquitectura real (04 §19 + 03 + 05): `run_update` (cron) produce `screener.db` → s5 exporta CSV; sync (7 tablas) + migrate (full copy, único a `screener`) publican PG; api sirve 3 tablas (una sin writer). Motor SEC YPF-golden con provenance completa y c11, sin llegada a usuario. Market autónomo salvo `dim_instrument`. Dualidades v0/v1, facts/derived, precios×2+market, 4 motores ratios. Tres publicadores PG solapados. Validación por dominio sin C11 unificada en publicación.

## OBJETIVO

Una cadena por dominio (SEC-canónica, CNV-canónica, Market-canónica) con ownership único, provenance extremo a extremo, C10 por etapa, C11 como condición necesaria de C12 mediante gate en el publisher (staging→swap atómico). Dualidades: con bridge verificable o separadas por dominio con contrato. Un core de rebuild con modos. FX como servicio C7 con tipos OFFICIAL/MEP/CCL. YPF como Golden Case dentro de arquitectura genérica, no como techo.

## Principios (§2 del encargo, adoptados sin cambios)

RAW inmutable · PARSED≠NORMALIZED · IDENTIDAD≠CLASIFICACIÓN · derivados con provenance · VALIDACIÓN≠CERTIFICACIÓN · PUBLICACIÓN requiere VALIDACIÓN+CERTIFICACIÓN · una capa primaria por componente · sin capa 13 · C11≠C10 · C12 no publica no-certificado.

## 3. Decisiones arquitectónicas D1–D10

Formato por decisión: problema · evidencia · capa · planos · componentes · dependencias · impacto · riesgo · alternativa considerada · decisión+estado · orden · rollback · verificación · certificación requerida.

### D1 — Identity V0 vs V1 → **B+C (bridge + migración progresiva), DECIDIDO**
- Problema: dos autoridades sin bridge (05 G1, 06 IDENTITY). Evidencia: consumidores disjuntos (s01/s03↔v0; s04/ratio/c3↔v1). Capa C2; planos DATOS (+CONTROL por assertions). Componentes: s01, s03, s04, ratio_engine, c3_identity_link, backfills. Dependencias: s04 EXIGE v1 (gate C-S04-004); s03 exige v0.
- Impacto: lectura cruzada sin reescritura. Riesgo: R2 (doble autoridad temporal). Alternativas: A (mantener) insuficiente — deja el conflicto; D (reemplazar V0) imposible — s01/s03 la exigen; E innecesaria.
- Decisión: construir bridge de resolución v0↔v1 (solo lectura, assertions de equivalencia) y migrar consumidores por etapas (primero lectores nuevos al bridge). Reversible por etapas (eliminar assertions revierte). Orden: fase R7.4 (tras ownership). Rollback: R3 (dual-write/bridge: desactivar bridge, ambos sistemas intactos). Verificación: tests de resolución cruzada por CIK/CUIT + adversarial (extender test_cnv_identity_link). Certificación: no requiere C11 (es C2), pero el bridge se versiona.

### D2 — facts vs derived.fact (+fact_financials) → **canónicos por dominio + bridge de provenance, DECIDIDO**
- Problema: mismo hecho SEC en dos stores (05 G2). Evidencia: fuentes idénticas (EDGAR), granularidad/consumidores distintos (06 RATIOS). Capa C6; plano DATOS. Componentes: construir_base, s04, ratio_engine, calcular_ratios_base. Dependencias: producto lee facts; motor lee derived.
- Impacto: ningún consumidor cambia de store (cada dominio conserva el suyo). Riesgo R2. Alternativa: fusión en un store — RECHAZADA (distinta granularidad/provenance/consumidores; equivalencia numérica no probada).
- Decisión: `facts` (SQLite) canónico del producto-SQLite; `derived.fact` (PG) canónico certificado; bridge = mapear `source_fact_ids`↔filas facts para trazabilidad cruzada (solo lectura). `fact_financials` (CNV-legacy): ARCHIVE CANDIDATE tras decommission f4 (§12). Orden R7.5. Rollback R1 (bridge de lectura). Verificación: muestreo cruzado CIK/período documentado. Certificación: n/a (C6).

### D3 — UPDATE/ALL/SCREENER → **core común con modos, DECIDIDO**
- Problema: 3 generadores con divergencia s9/subset (05 G3). Evidencia: mismo output nominal, distinto alcance/mecanismo (05 §10). Capa C7; planos EJECUCIÓN+CONTROL. Componentes: run_update, run_all, run_screener, s0..s9, jobs. Dependencias: cron (quarterly), flags manuales.
- Impacto: un rebuild core parametrizable (modo=incremental-subset | full-universe | phases-import; s9 opcional; CNV=subprocess|pre-extraído; EDGAR=incremental|full). Riesgo R2 (no sacrificar capacidades: checklist §verificación).
- Alternativas: un único pipeline — RECHAZADA si pierde modos; varios especializados — aceptable como estado intermedio, no objetivo.
- Decisión: core + modos; los 3 entry points se conservan como fachadas hasta verificación. Orden R7.9 (tras ratios/CNV). Rollback R1 (fachadas intactas). Verificación: matriz de modos × (subset/full/s9/CNV/EDGAR) con outputs comparados. Certificación: C10 por modo.

### D4 — CNV v1/v2 → **v2 vigente, v1 DEPRECATE→ARCHIVE, DECIDIDO**
- Problema: v1 paralela sin caller (05 G6). Evidencia: run_all/run_update invocan v2; v1 solo docstrings. Capa C3/C4; plano EJECUCIÓN. Componentes: job5/6 v1/v2, jobs 1–4,7,8, c3, build_subset.
- Impacto: ninguno productivo (v1 sin caller). Riesgo R1. Decisión: DEPRECATE v1 ya (marcar, sin borrar); ARCHIVE tras ventana + SHA + verificación de no-uso (fase R7.12). c3, jobs 1–4,7,8: KEEP. Orden R7.6. Rollback R1 (restore desde archive con SHA). Verificación: grep de callers + ventana sin ejecución + backup con hash.
- No eliminar v1 todavía (restricción del encargo).

### D5 — `empresas` → **ownership único construir_base, DECIDIDO**
- Problema: 4 writers, uno con DROP (03 §16.4, 05 G11). Evidencia: base (productivo), catalogo (DROP legacy), cargar_* (UPDATEs laterales). Capa C2; plano DATOS. Dependencias: f1, s-series leen.
- Impacto: writers laterales pasan a declarar excepción o migrar a base. Riesgo R2 (ventana de escritura concurrente). Decisión: owner = construir_base; catalogo → ARCHIVE CANDIDATE (previa evidencia de no-runtime, §10); cargar_argentina_cnv/cargar_byma_yfinance → ADAPT (vía base) o excepción documentada. Orden R7.3 (temprano, riesgo de pisada). Rollback R2 (snapshot previo de `empresas`). Verificación: auditoría de writers + test de no-DROP. Certificación: n/a.

### D6 — Market → **canónicos sin fusión de precios, DECIDIDO**
- Problema: instrumentos/símbolos/precios en dos cadenas (05 G8/§13). Evidencia: m1 puentea dim_instrument→market_instruments; producto usa yfinance no market_*. Capa C3/C6/C8; plano DATOS. Componentes: m1/m2/m4/m5, f014, market_db, dim_instrument, precios.
- Decisión: `market_instruments` canónico PG (owner m1); `dim_instrument` = fuente de migración, luego ARCHIVE-legacy (tras migrar m1 a fuente propia o contrato); `market_symbol_mappings` canónico de mapeo; `precios` (SQLite) precio-producto + `market_price_daily` precio-motor: **no fusionar** (cadenas/consumidores distintos). FX fuera del core market (servicio C7, D10). Orden R7.7. Rollback R1/R2. Verificación: mapeo dim→market completo antes de archivar.

### D7 — Ratios → **KEEP 4 motores; merges PENDIENTES DE VERIFICACIÓN, CONDICIONAL**
- Problema: 4 motores, equivalencia numérica no probada (05 §23). Evidencia: dominios disjuntos (06 RATIOS). Capa C8; plano DATOS.
- Decisión: conservar los 4; separar contractualmente CÁLCULO/MATERIALIZACIÓN/PUBLICACIÓN por motor; `fact_ratios` → ARCHIVE CANDIDATE (legacy sin lector). Ningún merge sin equivalencia numérica demostrada → estado CONDICIONAL/PENDIENTE. Orden R7.8. Rollback n/a (sin cambio). Verificación requerida: comparación numérica por CIK/período (§10).

### D8 — Publication → **publisher canónico staging+swap+gate, DECIDIDO (prioritario)**
- Problema: R4 migrate + hist sin writer + 3 publicadores solapados (06 §21). Evidencia: 04 §8, 03 §11. Capa C12; planos DATOS+EJECUCIÓN+CONTROL.
- Decisión: publisher canónico nuevo con flujo BUILD STAGING→CHECK SCHEMA→LOAD→VALIDATE→CERTIFY→ATOMIC SWAP (detalle §4); migrate → DEPRECATE inmediato (aviso) y REPLACE al activar el publisher; sync PLAN se conserva como transporte de sus 7 tablas **detrás del gate** (no publica sin C10 PASS + C11); publicar_v2 → DEPRECATE (sin lector) o reutilizar como staging; `screener_hist`: resolver writer (§10) o retirar lectura de api; s5 se conserva + gate de certificación (§20). Orden R7.1 (primero). Rollback R2 (snapshot pre-swap + publisher anterior disponible). Verificación: tabla nunca vacía (check post-swap) + suite de publicación. Certificación: C11 requerida por el gate.
- Alternativa (parchear migrate con pre-checks): RECHAZADA como estado final (TRUNCATE directo incompatible con safety); aceptable solo como mitigación transitoria.

### D9 — C10/C11/C12 → **gate en el publisher, DECIDIDO**
- Problema: C11 no alimenta publicación (04 §17). Evidencia: api no lee certifications; s5/sync sin gate. Capas C10/C11/C12; plano CONTROL.
- Decisión: C12 NO PUBLICA si C10≠PASS o C11≠CERTIFIED; el gate vive en el publisher canónico (staging no promueve sin certificados); 40_certificar se referencia con c11 (mapeo período↔run) sin fusionarlos. Orden R7.10 (tras publisher). Rollback R1 (gate con bypass auditado solo en emergencia — registrado, no recomendado). Verificación: publicación bloqueada con certificado ausente (test). Certificación: el propio gate es C11-consumidor.

### D10 — FX/multimoneda → **arquitectura objetivo C7, DECIDIDO (diseño, sin implementar)**
- Problema: conversión dispersa sin motor (05 §14). Evidencia: b4/_mep/s3_precios + tablas crudo/curada. Capa C7 (primaria objetivo); plano DATOS.
- Decisión: servicio/tabla FX con fx_type {OFFICIAL,MEP,CCL}, columnas value_original/currency_original/value_converted/currency_converted/fx_rate/fx_date/fx_source/fx_method; ARS/USD; consume C6 + provenance, alimenta C8. Sin capa 13. Orden R7.11. Rollback n/a (nuevo). Verificación futura: cobertura de tipos por fecha.

## 4. Publication safety first (R7.1)

Flujo objetivo del publisher canónico: BUILD STAGING (copia a `_stage`) → CHECK SCHEMA (columnas/tipos vs destino; aborta sin tocar prod) → LOAD (COPY) → VALIDATE (C10 suite sobre staging: conteos, PKs, rangos) → CERTIFY (exige C11 vigente del run origen) → ATOMIC SWAP (promoción; verificación post-swap: tabla no vacía + conteo esperado) → rollback R2 (snapshot pre-swap conservado por ventana). Mitigación transitoria opcional (no sustituye): pre-checks en migrate. Sin implementación en este paso.

## 5. Decision matrix

| ID | Problema | Evidencia | Decisión | Capa | Planos | Componentes | Riesgo | Dependencias | Rollback | Verificación | Certificación |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | identidad dual | 05 G1 | bridge+progresiva | C2 | DATOS | s01/s03/s04/ratio/c3_link | R2 | s04 exige v1 | R3 | tests cruce | n/a |
| D2 | hechos duales | 05 G2 | canónicos+bridge | C6 | DATOS | base/s04/ratio/calc | R2 | consumidores fijos | R1 | muestreo cruzado | n/a |
| D3 | 3 rebuilds | 05 G3 | core+modos | C7 | EJEC+CTRL | update/all/screener,s0..s9 | R2 | cron,flags | R1 | matriz modos | C10/modo |
| D4 | jobs v1 | 05 G6 | DEPRECATE→ARCHIVE | C3/C4 | EJEC | job5/6 v1 | R1 | ninguna prod. | R1 | no-uso+SHA | n/a |
| D5 | empresas 4W | 03§16/05 G11 | owner=base | C2 | DATOS | base/catalogo/cargar_* | R2 | f1,s-series | R2 | audit writers | n/a |
| D6 | market dual | 05 G8/§13 | canónicos, no fusión | C3/C6/C8 | DATOS | m1/m2,dim,precios | R2 | m1←f1 | R1/R2 | mapeo completo | n/a |
| D7 | 4 motores | 05§23 | KEEP; merge PENDIENTE | C8 | DATOS | calc/ratio/f4/s2 | R2 | s4,domain | n/a | equivalencia num. | n/a |
| D8 | publicación R4 | 06§21 | publisher+gate | C12 | D+E+C | s5/sync/migrate/pub/api | R4→R1 | PG,api | R2 | tabla-no-vacía | C11 |
| D9 | C11 no llega | 04§17 | gate en publisher | C10-12 | CONTROL | c11/40/pub | R2 | publisher | R1 | bloqueo sin cert | C11 |
| D10 | FX disperso | 05§14 | servicio C7 | C7 | DATOS | dolares/b4/_mep | R1 | C6/C8 | n/a | cobertura tipos | n/a |

Estados: D1,D2,D3,D4,D5,D6,D8,D9,D10 DECIDIDO (plan); D7 CONDICIONAL (merges PENDIENTES DE EVIDENCIA). Rechazadas: fusión facts/derived (D2-alt), pipeline único sin modos (D3-alt), parche migrate como final (D8-alt).

## 6. Component decision matrix (extracto relevante)

| Componente | HOY | OBJETIVO | Acción futura | Justificación | Evidencia | Dependencias | Estado |
|---|---|---|---|---|---|---|---|
| run_update | cron productivo | fachada del core (modo incremental-subset) | ADAPT | conservar schedule+capacidades | 04 P-SCR-UPDATE | cron, jobs | DECIDIDO |
| run_all/run_screener | alternativos manuales | fachadas (full-universe / phases-import) | ADAPT | no sacrificar modos | 05 G3 | s0..s9 | DECIDIDO |
| migrate_sqlite_to_pg | único a PG screener (TRUNCATE) | DEPRECATE→REPLACE por publisher | REPLACE | R4 | 06 §21 | api, PG | DECIDIDO |
| sincronizar_a_produccion | transporte 7 tablas | transporte tras gate | ADAPT | conserva mecanismo, agrega condición | 03 §11 | PG | DECIDIDO |
| publicar_screener_v2 | publica sin lector | DEPRECATE o staging del publisher | DEPRECATE | sin consumidor | 04 §8 | PG | DECIDIDO |
| engine/s03.py | sin consumidor | ARCHIVE | ARCHIVE | D0, sin uso | 05 §4.4 | ninguna | DECIDIDO |
| job5/6 v1 | paralelos sin caller | ARCHIVE (tras ventana) | DEPRECATE→ARCHIVE | D7 | 05 G6 | ninguna prod. | DECIDIDO |
| construir_catalogo | writer con DROP | ARCHIVE (previa no-runtime) | ARCHIVE | riesgo pisada | 05 G11 | empresas | CONDICIONAL |
| f-series/fact_ratios/screener_gold | legacy sin lector | ARCHIVE (tras migrar dim_instrument) | ARCHIVE | 04 §7 | m1←dim | CONDICIONAL |
| s04 dict reporte | D2 mecánica | ADAPT a StageReport | ADAPT | uniformidad C10 | 05 G10 | c10 | DECIDIDO |
| c11 / 40_certificar | certificadores por dominio | KEEP + referencia cruzada | KEEP | ambos con rol | 06 C11 | publisher (gate) | DECIDIDO |
| motores ratios (4) | vigentes por dominio | KEEP | KEEP | sin equivalencia | 05 §23 | sus dominios | DECIDIDO |
| s01/s02/s03 | golden YPF | KEEP (golden) + genérico aparte a futuro | KEEP | YPF es Golden Case | 04 §3 | e2e | DECIDIDO |
| api/main.py | sirve 3 tablas | KEEP + resolver hist | ADAPT | producto | 04 §18 | PG | DECIDIDO |

## 7. Orden de implementación (por dependencias reales)

- **R7.1 Safety publication** (D8; sin dependencias; riesgo mayor primero).
- **R7.2 Brechas de evidencia** (§10 en paralelo; desbloquean merges y archives).
- **R7.3 Ownership `empresas`** (D5; riesgo de pisada activo; previa a CNV).
- **R7.4 Identity bridge** (D1; tras ownership; base de s04/ratio).
- **R7.5 Facts bridge** (D2; tras identity; base de ratios).
- **R7.6 CNV v1 deprecate** (D4; independiente, temprana).
- **R7.7 Market canónico** (D6; requiere dim_instrument migrado).
- **R7.8 Ratios verificación** (D7; requiere facts estables).
- **R7.9 Pipeline core+modos** (D3; requiere CNV/ratios estables).
- **R7.10 Gate C10/C11/C12** (D9; requiere publisher R7.1).
- **R7.11 FX objetivo** (D10; requiere C7 estable).
- **R7.12 Cleanup/archive** (D4/D5/D6/D7-archives; al final, con ventanas cumplidas).

## 8. Dependency gates (patrón por cambio futuro)

PRECONDITION (evidencia §10 + backup/SHA) → CHANGE (acotado, una fase) → TEST (suite existente + nueva específica) → EXECUTION (staging/entorno no-prod) → VALIDATION (C10 del dominio) → CERTIFICATION (C11 donde aplique) → NEXT CHANGE (solo si el gate anterior está en PASS/CERTIFIED). Ningún cambio depende de decisión no verificada (D7-merges esperan a §10).

## 9. Rollback

R0 reversible (fachadas, flags) · R1 restore simple (bridge off, DEPRECATE revertido, archive con SHA) · R2 snapshot (tablas PG/SQLite pre-cambio, publisher anterior disponible) · R3 dual-write/bridge (identidad, facts) · R4 irreversible: **prohibido** sin demostrar innecesariedad + backup + ventana (aplica a futuros DELETE; ninguno en este plan).

## 10. Evidencia faltante

| Gap | Impacto | Cómo demostrarlo | Paso |
|---|---|---|---|
| equivalencia numérica ratios | bloquea merges D7 | comparación por CIK/período motor-vs-motor | R7.2/R7.8 |
| writer de screener_hist | bloquea C12 completa | trazabilidad PG (logs/contribuciones) o retirar lectura api | R7.2/R7.1 |
| lectores derived.ratio/fact_ratios/screener_gold/screener_v2/boletín/CSV | bloquea archives | grep+runtime audit + ventana | R7.2/R7.12 |
| reintentos HTTP s02/c3 | robustez | lectura engine.fetch/client + test de fallo | R7.2 |
| TLS motor | seguridad | verificar client/fetch (jobs ya hallados sin verify) | R7.2 |
| auth API | seguridad | auditoría api/main auth | R7.2 |
| cron VPS activo | alcance productivo | verificación en VPS (fuera de este entorno) | R7.2 |
| runtime legacy (catalogo/pipeline) | archives seguros | logs/ventana de no-uso | R7.2/R7.12 |
| bloqueo real de suites | gate efectivo | matriz suite→bloqueo | R7.2/R7.10 |
| CCL/oficial por fila | FX completo | productor por tipo | R7.11 |

## 11. Ratios (remisión)

Ver decisión D7 (§3) + matriz (§5) + orden R7.8 (§7) + gap de equivalencia numérica (§10). Sin contenido adicional: 4 motores KEEP, merges pendientes de verificación.

## 12. Candidatos de eliminación futura (ninguno se ejecuta)

| Candidato | Evidencia | Consumidores | Sustituto | Migración | Rollback | Condición previa |
|---|---|---|---|---|---|---|
| engine/s03.py | sin import (05 §4.4) | ninguno | n/a (librería muerta) | ninguna | R1 (restore) | ventana + SHA |
| job5/6 v1 | sin caller productivo (05 G6) | ninguno verificado | v2 (vigente) | ninguna | R1 | ventana + §10 |
| construir_catalogo | legacy con DROP (05 G11) | ninguno productivo verificado | construir_base | ninguna | R1 | probar no-runtime |
| screener_gold/fact_ratios | sin lector (04/05) | ND (gap) | screener/ratios | ninguna | R2 (snapshot) | cerrar gap lectores |
| f-series restantes | legacy (04 §7) | m1←dim_instrument | core CNV (D3) | migrar dim | R2 | R7.7+R7.9 |

Si no se demuestra seguridad: NO ELIMINABLE TODAVÍA (estado actual de todos menos s03.py/jobs-v1, que esperan ventana).

## 13. Candidatos de merge (semántico vs implementación vs datos)

- Identity v0/v1: MERGE SEMÁNTICO vía bridge (no de implementación ni de datos en esta fase).
- UPDATE/ALL/SCREENER: MERGE DE IMPLEMENTACIÓN en core (no semántico: modos conservados).
- Publication: MERGE DE IMPLEMENTACIÓN en publisher (transportes conservados tras gate).
- Motores ratios: NINGÚN merge (ni semántico: dominios distintos) hasta equivalencia numérica.
- Precios market/producto: NINGÚN merge (cadenas distintas).

## 14. Candidatos de archive (legacy, con condición)

engine/s03.py, jobs v1, construir_catalogo, f-series (tras R7.7/R7.9), fact_ratios/screener_gold (tras gaps). Cada archive: evidencia de sustitución + ventana de coexistencia + restore con SHA + provenance del archive + condición (§12). RAW nunca se archiva destructivamente (principio).

## 15. Target architecture

```
FUENTES (EDGAR/CNV/Yahoo/INDEC/20-F/demo)
  ↓
IDENTIDAD C2 (v0+v1 con bridge; empresas owner=base)
  ↓
RAW C3 (inmutable: SEC fs, CNV RawStore, market_raw_*, ingesta_log) [auditan _raw_inmutable/manifests]
  ↓
PARSED C4 (parsed.*, cnv_estados*, market canonical)
  ↓
NORMALIZED C5 (derived.fact-cols-norm, cnv_estados_norm, silver_norm)
  ↓
ECONOMIC FACTS C6 (derived.fact ⟷ facts con bridge; fact_financials archivado)
  ↓
FINANCIAL MODEL C7 (s4/screener, FX-service OFFICIAL/MEP/CCL, core rebuild con modos)
  ↓
RATIOS C8 (4 motores por dominio + materializadores; equivalencia pendiente)
  ↓
PROVENANCE C9 — transversal (run_id/checkpoints/hashes/manifests/ingesta/source_fact_ids)
  ↓
VALIDACIÓN C10 (gates, suites, job7, m4, 30_validaciones) ─┐
  ↓                                                          │ controles del pipeline
CERTIFICACIÓN C11 (c11, 40_certificar) ────────────────────┤ (C10≠C11, sin mezcla)
  ↓                                                          │
PUBLICACIÓN C12 (s5, publisher staging+swap con GATE, api) ◄┘ (C12 exige C10 PASS + C11)
```

Dominios: SEC-canónica (motor PG + golden YPF), CNV-canónica (jobs v2 + assemble), Market-canónica (m1/m2/m4 + guarda F-001), FX (servicio C7). PROVENANCE transversal; C10/C11/C12 como controles, no etapas de datos.

## 16. Target data ownership (objeto: OWNER/WRITERS/READERS/CONTRACT/PROVENANCE)

- identity: owner dual→bridge (D1); writers s01+v1-convención; readers s03/s04/ratio/c3; contrato assertions+authority; provenance assertions.
- RAW: owner por fuente (s02/c3/m2); writers únicos; readers parse; contrato inmutabilidad+hash; provenance manifests/logs.
- parsed/normalized: owner s03/s04/s0/materia_prima según tabla; writers únicos; contrato DDL migraciones; provenance completa (motor) / parcial (sqlite).
- facts: owner por dominio (base/derived); bridge de trazabilidad; contrato granularidad declarada.
- ratios: owner por motor; contrato fuente+ventana+moneda; provenance parcial→completa donde aplique.
- market/FX: owner m1/m2/FX-service; contrato F-001 + fx-evidencia.
- screener: owner core-rebuild; writer único por modo; readers s5/sync; contrato columnas ASSEMBLE; provenance orden+logs.
- certifications: owner c11/40; contrato INV1/INV5 y período; provenance completa.
- publication: owner publisher canónico; contrato staging+swap+gate; provenance boletín.

## 17. Target pipelines

- SEC-canónica: e2e (golden YPF) + stages genéricos (s04/ratio/c11) reutilizables por CIK; Golden Cases separados de la arquitectura (YPF permanece como caso, no como techo).
- CNV-canónica: c3 (RAW) + jobs v2 + assemble vía core (D3); v1 archivada.
- Market-canónica: m1→m2→m4 (+m5 auditoría) con `dim_instrument` migrado.
- Financial model: core rebuild con modos (incremental-subset/full/s9/CNV/EDGAR).
- Ratios: 4 motores con contratos; merges solo con equivalencia.
- Publication: publisher + gate (D8/D9); s5 con gate; api con hist resuelto.

## 18. Golden cases (rol, no lista definitiva)

Dimensiones: industria, jurisdicción, estándar contable, moneda, instrumento, tipo de filing, estructura financiera, FX. YPF permanece (SEC 20-F, ADR+Byma, ARS/USD). Los casos fijan contratos (gates de volumen/forma) sin hardcodear la arquitectura.

## 19. Multimoneda (objetivo)

C6 → C7 → FX → C8 con ARS/USD, OFFICIAL/MEP/CCL, fecha, fuente, método, provenance (D10). Sin implementación en este plan.

## 20. Certification gate (objetivo)

C12 NO PUBLICA si C10≠PASS o C11 ausente. Vive en el publisher (staging no promueve). Bypass solo de emergencia, auditado. Sin implementar en este plan.

## 21. Rollback (remisión)

Ver §9 (clases R0–R4 y regla R4). Sin contenido adicional.

## 22. Evidence gaps (remisión)

Ver §10 (tabla de 10 gaps con impacto, demostración y paso). Sin contenido adicional.

## 23. Criterios de éxito (verificación del plan, §22.24)

Qué queda/qué cambia/qué se fusiona/qué se reemplaza/qué se archiva/qué podría eliminarse: §6 + §12–§14. En qué orden: §7 (dependencias). Por qué: §3 (14 campos). Con qué evidencia: citas 01–06 + §10. Con qué rollback: §9 (R0–R4). Qué falta: §10 (10 gaps). El plan es ejecutable por fases con gates (§8) sin ambigüedad de alcance.

## 24. Resumen final (formato §22)

1. Resumen ejecutivo: §1. 2. Problemas: §2 (P1–P10). 3. Decisiones: §3 (D1–D10). 4. Matriz: §5. 5. Componentes: §6. 6. Publication safety: §4. 7. Identity: D1. 8. Facts: D2. 9. CNV: D4. 10. Market: D6. 11. Ratios: D7. 12. FX: D10/§19. 13. C10/C11/C12: D9/§20. 14. Pipelines: §17. 15. Ownership: §16. 16. Delete: §12. 17. Merge: §13. 18. Archive: §14. 19. Dependencias: D-matrices + §8. 20. Orden: §7. 21. Rollback: §9. 22. Gaps: §10. 23. Target: §15. 24. Éxito: §23.