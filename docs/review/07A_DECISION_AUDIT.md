# 07A — Auditoría de consistencia D1–D10 (pre-Paso 8)

Revisión estrictamente documental del Paso 7 contra 01–06. No se ejecuta ni modifica nada (código, DB, migraciones, producción intactos). Cada hallazgo: OK · AJUSTE DOCUMENTAL · PENDIENTE DE EVIDENCIA · CONTRADICCIÓN · DECISIÓN A REVISAR. Lo no demostrable queda NO DETERMINABLE.

## 1. Objetivo

Determinar si D1–D10 son internamente consistentes, precisas y seguras como base del Paso 8 (DELETE PLAN).

## 2. Base documental

01_EXECUTION_GRAPH · 02_DEPENDENCY_GRAPH · 03_DATA_OWNERSHIP · 04_PIPELINE_REAL · 05_DUPLICATION_MAP · 06_EXECUTABLE_DEEP_AUDIT(+INDEX) · 07_REENGINEERING_PLAN. Arquitectura obligatoria C1–C12 / 4 planos / ciclo DEFINIR→IMPLEMENTAR→VERIFICAR→CERTIFICAR, con IDENTIDAD≠CLASIFICACIÓN, PARSED≠NORMALIZED, VALIDACIÓN≠CERTIFICACIÓN, RAW inmutable, provenance en derivados, C12 exige C10+C11, una capa primaria por componente, sin capa 13.

## 3. Método

12 preguntas por decisión (§3 del encargo) + revisiones especiales (D8/D9, D2, estados, interdependencias) + regla de seguridad (ninguna recomendación = autorización de DELETE/MERGE/ARCHIVE; R4 nunca se aprueba por indicios nominales).

## 4. Matriz D1–D10

Preguntas: 1 formulación · 2 evidencia · 3 capa · 4 planos · 5 dependencias · 6 rollback · 7 verificación · 8 certificación · 9 contradicciones · 10 ambigüedad · 11 estado · 12 precondición.

| D | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | Veredicto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | OK | OK | OK | AJUSTE | OK | OK | OK | OK | OK | OK | OK | OK | AJUSTE (planos) |
| D2 | OK | OK | OK | OK | AJUSTE | OK | OK | OK | AJUSTE | AJUSTE | OK | OK | AJUSTES (término + f4) |
| D3 | OK | OK | OK | OK | AJUSTE | OK | OK | OK | OK | OK | OK | OK | AJUSTE (IPC) |
| D4 | OK | OK | OK | OK | AJUSTE | OK | OK | OK | OK | AJUSTE | OK | OK | AJUSTES (timing + docstring) |
| D5 | OK | OK | OK | OK | OK | OK | OK | OK | OK | AJUSTE | OK | OK | AJUSTE (criterio excepción) |
| D6 | OK | OK | AJUSTE | OK | OK | OK | OK | OK | OK | OK | OK | OK | AJUSTE (capa primaria) |
| D7 | OK | OK | OK | OK | OK | OK | OK | OK | AJUSTE | OK | OK | OK | AJUSTE (vía A4) |
| D8 | OK | OK | OK | OK | OK | OK | AJUSTE | OK | AJUSTE | AJUSTE | OK | OK | AJUSTES (gate único) |
| D9 | OK | OK | AJUSTE | OK | OK | AJUSTE | OK | OK | AJUSTE | AJUSTE | OK | OK | AJUSTES (gate + bypass) |
| D10 | OK | OK | OK | OK | AJUSTE | OK | OK | OK | OK | OK | OK | OK | AJUSTE (alcance FX publ.) |

Cero CONTRADICCIONES duras. Cero DECISIÓN A REVISAR (ninguna decisión debe revertirse). Cero PENDIENTE DE EVIDENCIA nuevo (los gaps ya viven en 07 §10/R7.2).

## 5. Hallazgos por decisión

- **D1**: planos "DATOS (+CONTROL por assertions)" impreciso — las assertions son datos; CONTROL solo aparece como consumidor (gate s04). → A-juste de redacción (A1-lista §7: planos DATOS+EJECUCIÓN).
- **D2**: (a) "canónico certificado" confunde C6 con C11 → reformular (§10). (b) `fact_financials` ARCHIVE CANDIDATE choca condicionalmente con D7-KEEP-f4 → precondición explícita (§7 A4).
- **D3**: falta dependencia del IPC mensual (s2 la exige) en dependencias y verificación → agregar (A10).
- **D4**: "DEPRECATE ya" contradice fase R7.6 → fijar timing (A5); `build_subset.py` cita v1 en docstring → actualizar al deprecar (A11).
- **D5**: "excepción documentada" para cargar_* sin criterios → definir criterio (defecto ADAPT; excepción solo con justificación + ventana) (A5b → ver §7 A6).
- **D6**: capas "C3/C6/C8" sin primaria explícita → primaria C3, afectadas C6/C8 (A8).
- **D7**: estado CONDICIONAL correcto; su verificación debe fijar serie IPC (vía A10).
- **D8**: VALIDATE/CERTIFY del flujo + gate D9 = un solo gate con dos insumos; la "mitigación transitoria" no debe leerse como autorización de tocar prod (A2).
- **D9**: bypass de emergencia sin condiciones → exigir doble control + registro + ventana, o eliminar mención (A3); regla "C10-12" → regla de control que abarca C10–C12 (A8).
- **D10**: alcance debe incluir `dolarito_cotizaciones` + FX publicado por sync (A12).

## 6. Contradicciones

Ninguna arquitectónica real. Tensiones condicionales (no contradicciones): D2-archive-fact_financials vs D7-keep-f4 (resuelta por A4: el archive exige decommission previo de f4); D8-mecanismo vs D9-regla (resuelta por A2: un solo gate). Ambas partes están condicionadas, por lo que no hay autorización implícita de nada.

## 7. Ajustes documentales propuestos (aplicar a 07, sin cambiar arquitectura)

- **A1**: D2 — sustituir "canónico certificado" por "canónico del dominio (provenance completa, validado por gates; certificable vía c11 por run)"; igual para `facts` (parcial). Distinguir siempre: canonicalidad de store / validación / certificación / publicación.
- **A2**: D8/D9 — fijar UN solo gate: una regla (C10 PASS + C11 CERTIFIED), aplicada en cada punto de promoción (swap PG, export CSV) con los mismos insumos. D8-VALIDATE produce evidencia C10; D8-CERTIFY ejecuta el gate según D9. Verificaciones cruzadas. La mitigación transitoria sobre migrate solo vía gates normales de cambio; no sustituye al reemplazo.
- **A3**: D9 — bypass solo con doble control + registro de incidente + ventana temporal; si no, eliminar la mención.
- **A4**: D2 — `fact_financials` archivable solo si f4 se decommissiona (decisión R7.8/R7.12); en caso contrario KEEP.
- **A5**: D4 — DEPRECATE se ejecuta en R7.6 (quitar "ya").
- **A6**: D5 — criterio de excepción para writers laterales (defecto ADAPT; excepción con justificación + ventana + revisión).
- **A7**: §6 del 07 — agregar definición: "DECIDIDO = decisión arquitectónica tomada; su ejecución queda condicionada a los gates y precondiciones de su fase" + precondiciones por decisión: D1 R7.4/tests verdes; D2 R7.5/muestreo; D3 R7.9/matriz de modos; D4 R7.6/ventana+SHA; D5 R7.3/snapshot+evidencia runtime; D6 R7.7/mapeo completo; D7 sin cambio (merges → equivalencia); D8 R7.1/staging+suite; D9 R7.10/block-test; D10 diseño R7.11.
- **A8**: D6 primaria C3 (afectadas C6/C8); D9 regla de plano CONTROL que abarca C10–C12 (sin reasignar capas).
- **A9**: interdependencias — eliminar D5→D4 (sin sustento: jobs v1 no depende de `empresas`); D1→D2 como secuenciación blanda, no dependencia dura.
- **A10**: D3/D7 — dependencia del IPC mensual (prerrequisito del rebuild) y fijación de serie para verificaciones.
- **A11**: D4 — actualizar referencia a v1 en `build_subset.py` (docstring) al deprecar.
- **A12**: D10 — incluir en el alcance `dolarito_cotizaciones` y el FX ya publicado por sync.

## 8. Evidencia faltante

Sin gaps nuevos: los 10 de 07 §10 cubren todo lo hallado (incl. TLS motor, reintentos, auth api, cron VPS, runtime legacy, bloqueo de suites). Todos calendarizados en R7.2 — no bloquean el Paso 8 (que debe respetarlos como precondiciones de candidatos, no resolverlos).

## 9. Revisión D8/D9

D8 define correctamente el MECANISMO (staging→swap, 07 §4) y D9 la REGLA de autorización (C10 PASS + C11) — con el ajuste A2 (un solo gate, dos puntos de aplicación con mismos insumos) quedan inequívocos: C10=validación (produce evidencia), C11=certificación (atestigua), C12=publicación (promueve), publisher=mecanismo C12, gate=condición de promoción. Flujo: BUILD→STAGING→C10 PASS→C11 CERTIFIED→ATOMIC SWAP→PUBLICADO. Sin dos gates independientes tras A2.

## 10. Revisión D2

"Canónico certificado" sí confunde C6 con C11 (c11 certifica corridas, no tablas per se). Aplicar A1: canonicalidad = propiedad del store+dominio; validación = gates; certificación = c11/40 por run/período; publicación = gateada. Arquitectura intacta.

## 11. Revisión de estados

DECIDIDO en 07 = decisión tomada con ejecución gateada (A7 lo explicita). D4/D5/D6/D8/D9 correctamente DECIDIDO-diseño; D7 correctamente CONDICIONAL. Candidatos DELETE/ARCHIVE/MERGE: todos NO-DECIDIDO o condicionales con precondición (07 §12–§14) — conformes a la regla de seguridad; ninguna etiqueta "legacy"/nominal autoriza nada por sí sola.

## 12. Revisión de dependencias

D1→D2 blanda (orden, no dependencia) · D2→D7 dura (facts estables antes de verificar ratios) · D5→D4 eliminada (A9) · D5→D3 dura (rebuild escribe `empresas`) · D6→archives dura (migración antes de archivar) · D7→merges por definición · D8→D9 co-diseño (gate dentro del publisher) · D9→C12 directa. Orden R7.1→R7.12 **coherente, sin cambios** (la depuración A9 no altera fases: R7.3 precede a R7.6 por riesgo de todos modos).

## 13. Impacto sobre R7.1–R7.12

Ninguno estructural: las fases se mantienen; A2/A3 endurecen R7.1/R7.10; A10 agrega prerrequisito IPC a R7.8/R7.9; A4 condiciona un archive de R7.12.

## 14. Decisión final sobre cada D

D1 CONFIRMADA (con A-planos) · D2 CONFIRMADA (con A1+A4) · D3 CONFIRMADA (con A10) · D4 CONFIRMADA (con A5+A11) · D5 CONFIRMADA (con A6) · D6 CONFIRMADA (con A8) · D7 CONFIRMADA como CONDICIONAL · D8 CONFIRMADA (con A2) · D9 CONFIRMADA (con A2+A3+A8) · D10 CONFIRMADA (con A12). Ninguna revertida; ninguna requiere evidencia nueva antes del Paso 8.

## 15. Gate de entrada al Paso 8

**READY_FOR_STEP_8** — con condiciones de entrada: (1) aplicar A1–A12 a 07 (documental, sin código); (2) respetar R4 y la regla de seguridad (§8 del encargo) para cada candidato; (3) tratar los 10 gaps como precondiciones de candidatos, no como bloqueos del plan. Sin contradicciones arquitectónicas. NO comenzar el Paso 8 en este acto (conforme a lo ordenado).
