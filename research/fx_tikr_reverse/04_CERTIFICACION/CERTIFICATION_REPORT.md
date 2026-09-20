# CERTIFICATION_REPORT — AGENTE 04 (Independent Certifier)

Fecha de auditoría: 2026-09-15
Auditor: AGENTE 04, independiente de AGENTE 01/02/03
Alcance: `research/fx_tikr_reverse/` (sandbox, NO producción)
Método: lectura directa de artefactos + re-ejecución de la suite de tests +
inspección de RAW/PARSED sin recalcular estadísticas.

No se modificó RAW, PARSED, NORMALIZED, estadísticas ni acceptance criteria.
No se rehizo ningún cálculo con el fin de obtener otro resultado.

---

## 0. Nota preliminar sobre el propio proceso de auditoría

El primer barrido (agente exploratorio, alcance amplio del repo) reportó que
`01_raw/` estaba vacío y que no existían SOURCE_DOSSIER/SOURCE_MATRIX ni
ejecuciones reales — solo specs y stubs. Una segunda pasada de lectura directa
de archivos mostró que eso era **incorrecto por incompletitud de búsqueda**:
existe una carpeta paralela `raw/` (distinta de `01_raw/`, que sí está vacía)
con 154 archivos JSON de A3500 reales, un snapshot HTML de OFICIAL con 3952
filas parseadas, y una carpeta `Perplexity/` con `SOURCE_DOSSIER.docx`,
`SOURCE_MATRIX.csv`, `SOURCE_GAPS.docx`, `SOURCE_METHODS.docx`,
`SOURCE_TIMELINE.csv`.

Se registra esto como hallazgo de proceso, no de contenido: **la convivencia de
`01_raw/` (vacío, de la generación de scripts stub) y `raw/` (poblado, de la
generación `engine/`) es una fuente de falsos negativos para cualquier
auditor o script que solo mire la ruta documentada en `source_registry.yaml`
(`01_raw/bcra_*`).** Ver BLOCKERS.csv, B-01.

---

## 1. AUDIT 1 — SOURCE

| Fuente | ¿Existe? | ¿Primaria? | ¿Reproducible? | ¿Fecha? | ¿Hash? | ¿Provenance? | Clasificación |
|---|---|---|---|---|---|---|---|
| A3500 (BCRA API Cotizaciones) | SÍ — `raw/bcra/a3500/*.json` (154 archivos) | SÍ, API oficial BCRA sin auth | SÍ (endpoint + fecha + collector versionado) | SÍ (`source_date`, `retrieved_at`) | SÍ (`sha256` por archivo) | SÍ completa (`engine/bcra_a3500.py`) | VERIFICADO POR EJECUCIÓN |
| OFICIAL (BCRA cierre-de-cotizaciones) | SÍ — 1 snapshot HTML + `parsed/bcra_oficial.csv` (3952 filas) | SÍ, publicación oficial BCRA | SÍ (un solo POST trae la serie completa; documentado en el propio collector) | SÍ (`retrieved_at`, snapshot fechado) | SÍ (`sha256` del HTML) | SÍ (`provenance_id` por fila referencia el hash del snapshot) | VERIFICADO POR EJECUCIÓN |
| MEP directa (BYMA) | NO — `raw/byma/mep.status.json` = `AUTH_REQUIRED` | N/A (no descargada) | N/A | SÍ (fecha del intento) | NO (`sha256: null`) | Parcial (status documentado, sin datos) | NO DETERMINABLE |
| CCL directa (BYMA) | NO — mismo patrón `AUTH_REQUIRED` | N/A | N/A | SÍ (intento) | NO | Parcial | NO DETERMINABLE |
| MEP/CCL reconstruida (instrumentos AL30/GD30/GGAL/YPF/PAMP) | NO — `raw/instruments/` solo contiene `SOURCES.md` (investigación), cero archivos de precio | N/A | Código sí (`engine/reconstruct.py`, `instruments.py` son funciones puras auditables), datos no | N/A | N/A | Especificación completa, cero datos | NO DETERMINABLE |
| SOURCE_DOSSIER / SOURCE_MATRIX (Perplexity) | SÍ — `Perplexity/SOURCE_DOSSIER.docx`, `SOURCE_MATRIX.csv`, `SOURCE_GAPS.docx`, `SOURCE_METHODS.docx`, `SOURCE_TIMELINE.csv` | Documental (referencias a fuentes primarias BCRA/BYMA/CNV/SEC con URL, organización, fecha, nivel de autoridad) | Las URLs son verificables externamente; el contenido del research en sí no fue re-verificado dato-por-dato en esta auditoría | SÍ (`ACCESS_DATE` por fila) | NO aplica (es un dossier de referencias, no de datos) | Parcial — SOURCE_MATRIX.csv trae `SOURCE_ID, URL, ORGANIZATION, CLAIM, AUTHORITY_LEVEL` por fila, lo cual es trazabilidad de nivel documental | VERIFICADO POR FUENTE (nivel documental, no dato numérico) |
| TIKR benchmark (12 valores POC 2023Q3-2026Q2) | SÍ — `fixtures/tikr_fx_12.csv` | NO declarado como primario: `provenance = "encargo-AGENTE02-P8 (fixture externo, no medido aquí)"` | NO — no hay forma de re-derivar estos 12 números desde una fuente TIKR citable en este sandbox | SÍ (`target_date` por fila) | NO | Insuficiente — "encargo" no es una fuente, es una instrucción de tarea | NO DETERMINABLE |

**Hallazgo dominante de AUDIT 1**: el benchmark TIKR que debe ser el objeto de
estudio no tiene fuente primaria documentada dentro del sandbox auditado. Sin
poder verificar de dónde salieron esos 12 valores (¿exportación real de TIKR?
¿capturado por qué usuario, qué fecha, qué screenshot/CSV original?), ningún
resultado de comparación aguas abajo puede certificarse como VERIFICADO POR
FUENTE — a lo sumo VERIFICADO POR EJECUCIÓN del cálculo interno, no de que el
cálculo compare contra el TIKR real.

---

## 2. AUDIT 2 — DATA (RAW / PARSED / NORMALIZED)

- **RAW inmutable**: `engine/common.py` implementa `write_raw_noreplace`
  (verificado por lectura del código fuente en `bcra_a3500.py` y
  `bcra_oficial.py`, que lo invocan). Los 154 archivos de A3500 y el snapshot
  de OFICIAL tienen sha256 propio. Clasificación: **VERIFICADO POR CÓDIGO**.
  No se intentó sobrescribir ningún archivo para confirmar el guard en runtime
  (hubiera sido modificar RAW, fuera de mandato).
- **PARSED reproducible**: `bcra_oficial.csv` es reproducible desde el
  snapshot HTML citado (mismo sha256 referenciado en cada `provenance_id`).
  **VERIFICADO POR CÓDIGO** (lectura de `parse_snapshot()` en
  `engine/bcra_oficial.py`); no se re-ejecutó el parser sobre el HTML crudo
  para confirmar bit-a-bit por no duplicar red/estado sin necesidad — el
  código es determinista y no tiene rutas de aleatoriedad.
- **NORMALIZED**: `engine/normalize.py` existe pero no se encontró ningún
  artefacto de salida normalizado (ninguna tabla única fecha×tipo_fx×escala
  con las 4 series juntas). Clasificación: **NO DETERMINABLE** — la capa 5
  (NORMALIZED) del contrato de 12 capas no tiene output verificable, solo
  código.

---

## 3. AUDIT 3 — STATISTICS

`scripts/stats.py` (clase A, sin red) implementa mean/median/mode/trimmed
mean/MAD/IQR/std/CV según `stats_spec.md`. Los 13 tests de
`tests/test_stats.py` pasan en re-ejecución independiente de esta auditoría
(`pytest research/fx_tikr_reverse/tests/ -q` → `13 passed`).

Sin embargo: **no existe ningún archivo de salida con estos estadísticos
calculados sobre series FX reales o sobre el FX implícito de TIKR.**
`stats.py` está probado en abstracto (inputs sintéticos de test), no ejecutado
sobre `fixtures/tikr_fx_12.csv` ni sobre A3500/OFICIAL parsed.

Clasificación: **VERIFICADO POR TEST** (la función es correcta) —
**NO DETERMINABLE** (no hay evidencia de que se haya aplicado al caso real).
No se recalculó nada por cuenta propia, conforme al mandato de no rehacer
estadísticas.

---

## 4. AUDIT 4 — TIKR vs candidatos

`scripts/tikr_fx_compare.py` es, verificado por lectura directa y confirmado
en esta auditoría, **un stub que aborta con `SystemExit` sin ejecutar ninguna
comparación**:

```
raise SystemExit(
    f"[{SCRIPT_VERSION}] NO IMPLEMENTADO (benchmark={a.benchmark!r} out={a.out!r}). "
    f"Sin benchmarks quarterly + 6 series FX con OBS-V1, el veredicto es UNKNOWN "
    f"por construcción. Clasificación: NO DETERMINABLE."
)
```

Este es el mismo estado que documenta el propio `outputs/CERTIFICATION.md`
interno (fechado 2026-09-15, git `f375090`), que ya declara:

```
TIKR_FX_METHOD = UNKNOWN
TIKR_FX_CONFIDENCE = 0.00
```

con razón explícita `D=0 < quorum 8`. Esta auditoría **confirma
independientemente** ese veredicto interno — no lo contradice ni lo mejora —
por la razón adicional de que ni siquiera el fixture TIKR tiene fuente
primaria (AUDIT 1) y las 4 series candidatas restantes (MEP/CCL directa y
reconstruida) no tienen un solo dato.

La única comparación empírica real que existe en el repo más amplio
(`data/TIKR_METR_HOMOLOGATION.md` §4) es:
- Anual, no quarterly.
- Una sola emisora (Metrogas).
- FX implícito ≈ mayorista (A3500) con desvío 0.0%-0.3% en 5 puntos FY2021-2025.
- El propio documento fuente señala anomalías internas del benchmark
  (EBITDA no reconcilia, acciones convertidas por FX, múltiplos no
  reconstruibles en 2024).

Este dato (**E1** en la taxonomía del `CERTIFICATION.md` interno) está
correctamente excluido del voto por `decision_criteria.md` §4 ("H1 anual NO
vota: es contexto, no evidencia quarterly"). Esta auditoría concuerda con esa
exclusión: 5 puntos anuales de una sola emisora no alcanzan para inferir
metodología trimestral, y las anomalías internas invalidan usar ese benchmark
como oráculo.

Clasificación de este audit: **NO DETERMINABLE** (no hay comparación
ejecutada; lo poco disponible es contextual y ya fue correctamente
descalificado por diseño propio del proyecto).

---

## 5. AUDIT 5 — ADVERSARIAL

| Riesgo | Hallazgo |
|---|---|
| Sesgo de selección | No aplica todavía — no hay selección de resultados porque no hay resultados. |
| Look-ahead bias | No aplica — sin comparación ejecutada. Riesgo latente: `decision_criteria.md` está fechado y congelado el mismo día (2026-09-15) que se generó el resto del sandbox; no hay commit git que demuestre que los criterios se fijaron *antes* de ver cualquier dato. Ver B-02. |
| Data snooping | Mismo riesgo latente que arriba: sin control de versiones (`research/` no trackeado en git), no hay forma de que un tercero verifique que `decision-v1.0.0` no fue ajustado después de una corrida exploratoria informal. |
| Survivor bias | No aplica al estado actual (sin universo de instrumentos con datos). |
| Instrumentos duplicados | No aplica — cero precios de instrumentos cargados. |
| Nominal mismatch | Controlado por diseño en `reconstruct.py` (`_check_pair` valida moneda de cada pata) — correcto pero no ejercitado con datos reales. |
| Settlement mismatch | Controlado por diseño (regla `UNDECLARED → NO_DECIDE`, nunca voto primario) — correcto, no ejercitado. |
| Stale prices | Controlado por diseño (`max_stale_days`) — no ejercitado. |
| Outliers | `decision_criteria.md` §4 fija de antemano "ningún umbral se mueve tras ver la tabla" — buen control anti-ajuste, pero aún no puesto a prueba porque no hay tabla que ver. |
| Conversiones espurias | No detectadas — no hay conversión ejecutada. |
| Circular reasoning | **Riesgo real detectado**: `source_registry.yaml` marca correctamente "TIKR: objeto de estudio, NUNCA fuente de FX" — buen diseño anti-circularidad. Sin embargo, el fixture TIKR (`fixtures/tikr_fx_12.csv`) proviene de un "encargo" sin fuente citable (AUDIT 1); si esos 12 valores fueran construidos por alguien con conocimiento previo de las series A3500/OFICIAL ya descargadas, existiría riesgo de circularidad no detectable desde este sandbox. No hay evidencia de que esto haya ocurrido, pero tampoco evidencia que lo descarte. Clasificación: **NO DETERMINABLE**, se marca como REQUIRED_FIX. |

**Conclusión de AUDIT 5**: los controles de diseño (anti-oracle, anti-ajuste,
fail-closed) están correctamente especificados y son, en general, más
rigurosos que el estado de datos que tienen detrás. El riesgo adversarial
predominante no es "resultado sesgado" (no hay resultado) sino "trazabilidad
insuficiente del propio proceso" por falta de versionado en git.

---

## 6. AUDIT 6 — ACCEPTANCE (REQ-FX-001..010)

Ver `ACCEPTANCE_MATRIX.csv` para la matriz completa. Resumen:

| REQ | Estado |
|---|---|
| REQ-FX-001 (matriz de fechas objetivo) | CUMPLE |
| REQ-FX-002 (A3500 fuente primaria) | CUMPLE PARCIAL — primaria sí, cobertura de los 12 POC no verificada punto a punto en esta auditoría |
| REQ-FX-003 (Oficial fuente primaria) | CUMPLE |
| REQ-FX-004 (MEP/CCL distinguen directa/reconstruida) | CUMPLE EN DISEÑO, NO EN DATOS — ninguna de las 4 columnas tiene una fila |
| REQ-FX-005 (FX instrumental reproducible desde instrumento+fecha+precios+settlement) | NO CUMPLE — cero precios de instrumentos |
| REQ-FX-006 (no imputar sin evidencia) | CUMPLE — verificado en cada script (fail-closed explícito) |
| REQ-FX-007 (8 estadísticos por período) | CUMPLE EN CÓDIGO, NO EJECUTADO sobre el caso real |
| REQ-FX-008 (comparar TIKR contra 6 series) | NO CUMPLE — script es stub |
| REQ-FX-009 (criterios definidos antes del análisis) | NO VERIFICABLE — sin git, no hay forma de probar el orden temporal |
| REQ-FX-010 (reproducible por auditor independiente) | CUMPLE PARCIAL — esta misma auditoría pudo re-ejecutar tests y leer provenance sin ayuda de los agentes previos, lo cual es evidencia a favor; pero el propio ejercicio reveló que `research/` no está en git, lo cual compromete la reproducibilidad a futuro si el directorio se pierde o se modifica sin registro |

---

## 7. Separación VERIFICADO / INFERIDO / NO DETERMINABLE

**VERIFICADO POR EJECUCIÓN**
- A3500 y OFICIAL tienen raw primario real con provenance completa.
- La suite de 13 tests pasa en re-ejecución independiente.
- `tikr_fx_compare.py` es, hoy, un stub fail-closed (confirmado leyendo el código y su comportamiento).

**INFERIDO**
- Que el diseño (fail-closed, anti-oracle, anti-ajuste) refleja intención honesta de los agentes previos — se infiere de la consistencia del código y la documentación, no de una declaración auditada de intenciones.
- Que H1 (evidencia anual METR≈mayorista) es indicativa pero no concluyente — inferencia razonable, no medición directa de este audit.

**NO DETERMINABLE**
- TIKR_FX_METHOD para el período quarterly 2023Q3-2026Q2 (POC).
- Procedencia real del fixture TIKR de 12 valores.
- Si `decision_criteria.md` fue congelado antes o después de cualquier exploración informal de datos (sin git, no verificable).
- Cobertura real de los 12 target dates POC en el A3500 raw existente (no se hizo el cruce fecha-a-fecha en esta auditoría porque hacerlo y publicarlo como "cobertura verificada" excede el mandato de un auditor que no debe generar nuevos cálculos sustantivos — esto queda para AGENTE 01/02/03, señalado como OPEN_FINDING).

---

## 8. Decisión de certificación

Aplicando la DECISION RULE del encargo (los 6 criterios deben cumplirse
todos):

1. Evidencia documental o empírica suficiente → **NO** (TIKR_BACKTEST no ejecutado, MEP/CCL sin datos).
2. Resultado reproducible → N/A (no hay resultado que reproducir).
3. Metodología supera criterios predefinidos → N/A.
4. Robustez ante outlier treatment → N/A.
5. No hay alternativa estadísticamente equivalente → N/A.
6. Evidencia no depende de ajuste post-hoc → parcialmente verificable (buen diseño anti-ajuste), pero no aplicable sin resultado.

**Ningún criterio puede evaluarse en positivo porque no existe el
insumo mínimo (TIKR_BACKTEST ejecutado + 3 de 4 series FX con datos).**

### VEREDICTO DE CERTIFICACIÓN

```
TIKR_FX_METHOD      = UNKNOWN
TIKR_FX_CONFIDENCE  = 0.00
TIKR_FX_EVIDENCE    = NO DETERMINABLE (insuficiente en origen; el propio
                       CERTIFICATION.md interno de AGENTE 03 ya lo declaraba
                       así; esta auditoría CONFIRMA independientemente ese
                       veredicto y no encuentra fundamento para mejorarlo NI
                       para objetarlo a la baja)
```

Esto **no es una corrección** al trabajo de AGENTE 01/02/03: es una
**confirmación independiente** de que su propio veredicto (UNKNOWN, D=0) es
correcto dado el estado real de los datos, incluyendo el material adicional
(`raw/`, `Perplexity/`) que no había sido citado explícitamente en el
`CERTIFICATION.md` interno pero que, al revisarlo, no cambia el resultado:
sigue faltando el TIKR_BACKTEST ejecutado y 3 de las 4 series MEP/CCL.

---

## 9. Camino a certificación (no ejecutado por este auditor — es prescriptivo, no un cálculo)

1. Poner `research/` bajo control de versiones para que REQ-FX-009 y
   REQ-FX-010 sean verificables a futuro (BLOCKER B-02).
2. Documentar la procedencia real del fixture TIKR de 12 valores o
   reemplazarlo por una exportación citable con fecha/usuario/hash
   (BLOCKER B-03).
3. Obtener credenciales BYMA o una fuente alternativa primaria/vendor
   declarada para MEP/CCL directa.
4. Cargar precios reales de AL30/GD30/GGAL/YPF/PAMP en `raw/instruments/`
   para habilitar `reconstruct.py` (que ya está listo y probado en su lógica
   pura).
5. Ejecutar `tikr_fx_compare.py` (reimplementado, no el stub) contra las 6
   series y el fixture TIKR con fuente corregida.
6. Volver a traer a AGENTE 04 para una segunda certificación — no
   autocertificar internamente.
