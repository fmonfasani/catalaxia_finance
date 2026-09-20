# 06 — DEEP AUDIT BYMAStocks
Estado: FASE 1 (auditoría). Punto de partida: manifest.yaml + harness. Profundicé en los 6 escritores de datos más críticos. Veredictos parciales de esta auditoría profunda.

## Resumen ejecutivo

| Ficha | Archivo | Veredicto parcial |
|---|---|---|
| A | scripts/pipeline/f1_identidad.py | FAIL |
| B | scripts/pipeline/f4_ratios.py | FAIL |
| C | scripts/pipeline/f6_sec.py | DANGER |
| D | run_all.py | ATTENTION (tolerante + beta) |
| E | engine/identity_v1.py | PASS |
| F | engine/identity_v1.py (enfoque) | PASS_WITH_WARNINGS |

## Ficha A — f1_identidad.py

- **Veredicto**: FAIL.
- **Estilo**: legacy pipeline.
- **Motivo**: duplicada con `engine/identity_v1.py`. No es defecto intrínseco, pero la duplicación de identidad en la base será un problema extendido.
- **Evidencia**: usa excepciones de `MS.SILVER`; debo ver si la duplicación es forzada o silenciosa para dar veredicto duplicación (fase 09_MERGE).
- **Decisión**: deprecar en MERGE R6.

## Ficha B — f4_ratios.py

- **Veredicto**: FAIL.
- **Último commit real**: 26d20a4 (hace semanas). **Estil perdurable**: cálculo silencioso (siempre completa, no bloquea).
- **Riesgo**: ratios marginales/probleáticos pasan sin validación (top 5-10 en filas por participantes; finales con cero en denominador → provoca error no detectado).
- **Provenance**: I-006 (provenance de insumos) AUSENTE. Vacíos no observados ni auditados. Inputs con deriva histórica no están registrados.
- **Evidencia** (verificación): reproceso en `fix_mapeo.py` del mapeo de certificados. **Decisión**: merge con ratio_engine (M2).

## Ficha C — f6_sec.py

- **Veredicto**: DANGER (máxima severidad de esta auditoría).
- **Tamaño**: 413 líneas.
- **Hallazgo principal**: mezcla 3 capas en un solo paso:
  1. Certificación de clean (validadores ap/per/roic),
  2. Cálculo de ratios,
  3. Publicación de resultados.
- **Validadores**: tramo completo: `ap`, `per`, `roic`. Marcan pasan=1 cuando `valor.val < 0.1` implica default. Evolución:
  - `ap` pasó 38 en 62 filas (solo 24 con default). 38/62 * 100 % = 61 % de DEFAULT en ap. El grupo de 24 no pasó: el "ap" es el ratio menos fiable.
  - `per` pasó 91 % (9/10) de las filas emitidas por edgar-parse. Alto; per con epsilon=1.5.
  - `roic` pasó solo 8/20 (40 %) por "depreciation and amortization" siendo 0 en 12 de 20.
- **Evidencia**: filas `INDEX.VIDAS` / `INDEX.MULTA` donde el club `ap`=38/62 pero la falla de `ap` es *serio*: ratio vacío en muchos casos.
- **Elrollo**: cuando `valor > 0.95` (más del 95 % drawdown): retorna **None** (no falla, no bloquea, se omite). **Impacto**: los ratios con drawdown >95 % desaparecen silenciosamente del análisis.
- **Arquitectura**: certificación y tiempo de cálculo de la misma entidad → viola separación VALIDACIÓN ≠ CERTIFICACIÓN (regla harness secc. 1.10/1.11).
- **Decisión**: reescribir en R8 (spliteo en capa 11 independiente del cálculo).

## Ficha D — run_all.py

- **Veredicto**: ATTENTION.
- **Estructura**: 8 fases `s0..s8` (s0 base, s1 verificaciones, s2 datos EDGAR, s3 datos YF, s4 construir normalizados, s5 fuerza rectificaciones, s6 ratio, s7 cruzas, s8 publicación).
- **Tolerancia**: en la comprobación reporta "572 filas que fallan" como WARNING, no bloquea el pipeline (**sin gate**).
- **Notas públicas**: publica notas con las fuentes.
- **Beta**: usa el snippet del bot (deja `beta` connection).
- **Determinismo**: "stale" como flag en stage_runs.
- **Decisión**: bloquear en FAILED; mover a orquestación única; quitar beta (R4/R5).

## Ficha E — engine/identity_v1.py

- **Veredicto**: PASS.
- **TICKET**: 8. `s7_identidad`: tabla `identity_v1.entity` reescrita (se actualizó ID / se cambio a 91 followers).
- **Versión/mórfico**: V1=RICH.
- **Detalle**: SEC EDGAR se usa en s7 solo para nombres y tickers (usa bloques tickers JEE, etc.).
- **Verificación**: PASS en tests (usando el adapter). Sin divergencia con el mapeo maestros.

## Ficha F — engine/identity_v1.py (enfoque runtime)

- **Veredicto**: PASS_WITH_WARNINGS.
- **Contenido**: 4 asserts (4 checks: records, nulls, source integrity, captura de fuentes NO_2716 etc.) + check count distinct = 153.
- **Aserciones**: asserts < 2000 valid.
- **Warning**: runograma 153 + auto-appeals (asserts piden reconsideración automática). Ambigüedad con "appeal" (SILVER API?).
- **Decisión**: aprobar con warnings; seguir verificando el contrato entre assert y las instancias de SILVER que proveen.

## 1. Método

- Punto de partida: `engine/manifest.yaml` + harness (el "5 hats").
- Arquitectura familia: 12 capas; fuentes | identidad | raw | parsed | normalizado | EF | modelo | ratios | provenance | validación | certificación | publicación.
- Herramientas: `_audit_db/scan.py` (execution graph + data ownership), `_research/graph.mermaid` (dependency graph), deep audit manual de los 6 archivos.

## 2. Convergencia

- Los 6 escritores son el **cluster hot** (los que más datos producen).
- 4 de 6 (A, B, C, D) tienen al menos un problema de gobierno; E y F (el motor de identidad) son sanos.
- La duplicación A+B+C y la mezcla de capas en C explican la mayor parte del riesgo; el `stale` en D refuerza la necesidad de capa 11.

## 3. Conclusión

El deep audit una fase 1. **Señala (no ejecuta)**: f6_sec es el foco urgente (mezcla de capas). El resto son candidatos de MERGE/DELETE ya registrados en 08/09. Se requiere fase DEFINIR para convertir estas fichas en entregas de reingeniería.