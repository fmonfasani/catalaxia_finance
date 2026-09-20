# 10 — TARGET ARCHITECTURE (ESTADO FINAL) — BYMAStocks
Estado: FASE 1 (auditoría). Arquitectura objetivo docae para la fase DEFINIR. NO hay migración todavía.

## 1. Principios

1. **Una verdad por dominio de datos (no múltiples).**
2. **Separación VALIDACIÓN ⇔ CERTIFICACIÓN** (el cálculo nunca es el juez).
3. **Capa 11 independiente y gate obligatorio** en la publicación.
4. **RAW es inmutable: jamás se borra; se versiona.**
5. **Provenance completa por corrida** (quién escribió qué, desde qué fuentes, bajo qué contrato).
6. **Ownership declarado por tabla** en manifest.yaml.
7. **Cero secretos en código.**

## 2. Arquitectura objetivo por capa

| Capa | Fuente de verdad | Dueño (único) |
|---|---|---|
| 01 FUENTES | s02_fetch (EDGAR), s03 (YF), discovery (CNV) | engine |
| 02 IDENTIDAD | engine/identity_v1.* (entity, identifier, assertion, source) | engine (M1 absorbe f1, construir_*) |
| 03 RAW | data/raw (fingerprint) | engine (inmutable) |
| 04 PARSED | engine/xbrlparse, s03_parse | engine |
| 05 NORMALIZADO | engine/s04_normalize | engine |
| 06 EF | engine/ratio_inputs | engine |
| 07 MODELO | engine/ratio_defs | engine |
| 08 RATIOS | scripts/engine/ratio_engine | engine (M2 absorbe f4) |
| 09 PROVENANCE | engine.stage_runs + identity_v1.source + report | engine |
| 10 VALIDACIÓN | infra validación (asserts + tests) | quality/ops |
| 11 CERTIFICACIÓN | capa 11 NUEVA (independiente) | ops/gobernanza |
| 12 PUBLICACIÓN | api (gate con 11) + gen_screener_html | api |

## 3. Orquestación

- **Un solo orquestador** (`run_engine`) que ejecuta fases y escribe `stage_runs` (checkpoints). Nada más escribe `stage_runs`.
- `run_all` se retira (s0..s8 absorbidos por el engine) o se deja como alias de compatibilidad hasta R8.
- No hay carreras: un pipeline a la vez (lock en `stage_runs`).

## 4. Tablas canónicas resultantes

| Tabla | Rol | Escritores tras target |
|---|---|---|
| identity_v1.* | identidad autoritativa | 1 (engine) |
| engine.stage_runs | checkpoints | 1 (orquestador) |
| screener | salida pública | 1 (fase de build + capa 11 valida) |
| empresas | legado lectura | 0 escritores (solo lectura) |
| derived.fact | analítica adversaria | 1 (adversario sobre copia) |

## 5. API y publicación

- `api/main.py` pública `screener` **solo si** la certificación de la última corrida es satisfactoria (firma/hash en stage_runs).
- `api /v1` legacy se depreca con migración del cliente.

## 6. Seguridad

- Secretos: env vars / secret manager. `deploy.py`, `sincronizar` limpiados (I-005).
- `.env`, `data/`, documentos fuera de git salvo baseline acordado.

## 7. Qué NO se hace en fase 1

- No hay migración, ni DROP, ni DELETE, ni cambios de esquema.
- No se cambia el comportamiento actual de escrituras.
- No se toca la base de producción hasta la fase 8-9 con reglas de seguridad aplicadas.

## 8. Criterios de aceptación del target

- (a) cero secretos en código;
- (b) una sola fuente de identidad (identity_v1);
- (c) un solo cálculo de ratios;
- (d) un solo pipeline de datos;
- (e) capa 11 emite certificación y la API la respeta;
- (f) RAW nunca borrada;
- (g) ownership declarado por tabla con 1 escritor canónico.