# Ficha: IDENTITY — engine/identity.py, engine/identity_v1.py, backfills, bridges

### COMPONENTE: engine/identity.py (v0)

#### Identificación
- Path: `engine/identity.py` · Librería (no ejecutable directo) · Capa C2 · Plano DATOS
- Tablas: `identity.entities`, `identity.identifiers` (tickers solo aquí), `identifier_reviews`, `classifications` (DDL `002`)
- Funciones: `resolve_golden_ypf`, `resolve_por_cik`, hashing, catálogo SEC (`SEC_CATALOG_DIR`, `REPO_ROOT`)
- Writers: s01 (vía este módulo). Readers: s03, tests.
- Provenance PARCIAL (sin assertions). Idempotencia: resolución determinista.
- Destructividad: ninguna (no borra; disputas solo se cuentan).
- Tests: f035_entidad_muerta, f041_reafirmacion (parcial) — TEST EXISTE.
- Producción: vía s01 → PRODUCTIVO PROBABLE. Riesgo R2 (autoridad v0 YPF-izada).

### COMPONENTE: engine/identity_v1.py (v1)

#### Identificación
- Path: `engine/identity_v1.py` · Librería · Capa C2 · Plano DATOS
- Tablas: `source`, `entity` (entity_key opaco), `identifier`, `instrument`, `instrument_symbol`, `assertion`, `review`, `conflict`, vista `v_entity_resolution` (DDL `008/009/010/030/031`)
- Clases/funciones: `Evidence`, `bridge_verificado(left_ref, right_ref)`, resolución con assertion VERIFIED exigida.
- Writers: c3_identity_link, backfills (`backfill_cik`, `identity_v1_backfill_*`), pilots, f024. Readers: c3_validation, s04 (exige resolución autoritativa: gate C-S04-004), ratio_engine (resolver_entidad), benches.
- Semántica append-only: corregir = assertion nueva; conflictos → decisiones (`BRIDGE_RATIFICADO`); `UPDATE ... SET status='RESOLVED'` solo sobre reviews (:866-876).
- Separación: IDENTIDAD (entity/identifier) · INSTRUMENTO (instrument) · SÍMBOLO (instrument_symbol) · BRIDGE (assertions CIK↔LEI, **sin tabla `bridges`**) · REVIEW/CONFLICT.
- Tests: test_identity_v1, test_backfill_cik_adversarial, test_cnv_authority, test_cnv_identity_link, f061_ownership — cobertura adversarial real. TEST PASA (suites 01–05).
- Producción: PRODUCTIVO PROBABLE. Riesgo R2 (autoridad dividida con v0; veredicto abajo).

### ANEXO: backfills / pilots / ratificación
- `backfill_cik.py`, `identity_v1_backfill_dev/piloto/ratificar/adversario`, `identity_v1_pilot`, `f024_bma`, `cnv_validation_adversario/auditor`: escritores/lectores acotados de v1, con tests adversariales. PILOTO/TEST según caso; ninguno toca v0. Riesgo R1–R2.

### Veredicto auditoría identity especial (§10 del encargo)
- Duplicación G1: **real y confirmada** (mismo concepto, distinta granularidad/autoridad/consumidores, sin bridge v0↔v1).
- Coexistencia necesaria hoy: v0 alimenta s03-motor-SEC; v1 alimenta s04/ratio/c3 (s04 EXIGE v1). Ningún consumidor cruza → coexistencia operativa, no redundancia accidental.
- Bridge que falta: v0↔v1 (ningún componente lo implementa); intra-v1 existe (`bridge_verificado` CIK↔LEI).
- Migración: NO DECIDIDA (Paso 7).

### Contrato / Seguridad / Ocultas
- Contratos v0: PARCIAL (sin assertions). v1: IMPLEMENTADO (Evidence, authority_level, authoritative_for).
- Seguridad: sin secretos; `.env` solo para DB. R0.
- Ocultas: catálogo SEC en filesystem (v0); `authority_level`/`authoritative_for` como configuración de confianza (v1, DDL 031).
