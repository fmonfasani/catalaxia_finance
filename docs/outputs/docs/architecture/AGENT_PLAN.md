# AGENT_PLAN.md — Catalaxia Financial Data Engine

PHASE 0 deliverable · 2026-08-23 · Status: PROPOSED

## 1. Modelo de agentes

Orquestador único (sesión principal) + subagentes especializados invocados por tarea. Cada agente declara al nacer: alcance, docs normativos que debe leer, clase reproducibilidad de su output, y gate del que es responsable.

| Agente | Responsabilidad | Etapas | Docs obligatorios |
|---|---|---|---|
| architecture-agent (este, PHASE 0) | plan, ADRs, stage/dependency graphs, riesgos | S00 | todos los normativos |
| doc-keeper-agent | PIPELINE_VALIDATION_SPECIFICATION.md + documentación por fase; marca SUPERSEDED | transversal | KB §22/§25 |
| edgar-source-agent | fetch RAW + download_log + manifest | S02 | SPEC §4/§11–§13 |
| xbrl-parser-agent | PARSED con dimensiones; fixtures por layout | S03 | PROV §1–§2, piloto YPF |
| normalizer-agent | unidades/perímetro/moneda/calendario → NORMALIZED | S04 | SPEC §6–§10 |
| facts-agent | series FY/TTM, tres planos temporales | S05 | SPEC §9, EXT-NEW-003 |
| statements-agent | IS/BS/CF estructurados | S06 | DATA_CONTRACT §2 |
| market-agent | precios/FX/mcap + guards | S07 | s9 guards, EXT-NEW-011 |
| metrics-agent | fórmulas versionadas + lineage L0-L5 | S08–S09 | DATA_CONTRACT §3, FORMULAS_RATIOS |
| quality-auditor-agent | checks matriciales + certificación b7-style | S10–S11 | SPEC §14–§15/§22 |
| publish-agent | publicación solo certificado + provenance | S12 | SPEC §20 |
| benchmark-agent | contraste externo (drops manuales validados) | PHASE 11 | estándar admisión §2.2 |

## 2. Reglas de orquestación

0. Política de entregables: documentación → `outputs/docs/<area>/`; reportes con datos → `outputs/<tema>/`; código en `engine/` + `scripts/engine/` (ubicaciones funcionales). Ver PROGRAM_LOG.md.

1. Una etapa a la vez; ninguna etapa empieza sin: input checkpoint CERTIFIED + entrada DECISION_QUEUE vacía + docs de su fila leídos.
2. Escalado a humano SOLO por: decisión arquitectónica nueva, ambigüedad financiera material (definiciones de ratios), pérdida potencial de información, cambio irreversible, conflicto entre normas.
3. Toda implementación sigue el ciclo `PLAN→…→NEXT STAGE` y entrega el reporte estándar de STAGE_GRAPH §3.
4. Clasificación obligatoria de cada pieza: UNIVERSAL / SOURCE-SPECIFIC / TAXONOMY-SPECIFIC / INDUSTRY-SPECIFIC / ENTITY-SPECIFIC. Cualquier `if entity == "YPF"` en código = alerta de arquitectura inmediata.
5. Prohibido: inventar datos, correcciones silenciosas, segundo entry point de descarga, REPLACE con ventana.

## 3. Registros operativos

| Registro | Contenido | Ubicación propuesta |
|---|---|---|
| JOB_REGISTRY | cada corrida: run_id, stage, mode, gates, hashes | state.db (`runs`) |
| SCRIPT_REGISTRY | módulos del engine + versión + clase A/B/C/D | engine/manifest.yaml |
| STAGE_STATE | máquina de estados por etapa | state.db (`stages`) |
| CORRECTION_LOG | correcciones declarativas versionadas | state.db / parquet |

## 4. Golden test YPF

Regla de aceptación del programa: el engine v1 está DONE cuando para YPF reproduce y explica:
1. 100% de los facts XBRL del piloto (46.111 obs) en PARSED sin pérdida ni duplicación.
2. Serie Revenue FY2017–FY2025 con moneda correcta por vintage (ARS antes, USD después) y provenance completa hasta sha256.
3. Las 13 métricas del screener calculadas con formula_version, flags y null_reason donde corresponda.
4. Certificación b7-style por métrica con motivos citando checks.
5. Snapshot reproducible: recompute_command regenera métricas idénticas desde checkpoints.
