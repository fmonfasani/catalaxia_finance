# 99 — CIERRE FASE DEFINIR — ACTA DE DECISIONES (2026-09-06)
Estado: decisiones OWNER registradas en 00_INDEX y contratos 01–04. Sin código modificado. Sin DELETE/MERGE/REPLACE/ARCHIVE.

## Informe final (formato obligatorio)

### R1 — GIT BASELINE
```
CAPA → 2 CONTROL (gobierno de repo) · 4 INFRAESTRUCTURA (tracking)
PLANOS → CONTROL
CICLO → DEFINIR ✓ (parcial) · IMPLEMENTAR: BLOQUEADO
HOY → 1001 entradas git (954 untracked + 47 modified); ~41 % del código fuera de git;
       .gitignore cubre .env, data/raw, DBs, _tmp/_diag; faltan outputs/, scratchpad/, *.rar, ~$*
OBJETIVO → baseline limpio con fuente de verdad bajo git y basura ignorada, sin fugas a repo público
DECISIÓN → NO ejecutar baseline; mantener R1 en DEFINIR hasta completar clasificación semántica de las 1001 entradas
EVIDENCIA → git status --porcelain = 1001; tabla de clasificación en 01_R1 (sección 3); .gitignore actual
```

### R2 — SECRETOS
```
CAPA → 4 INFRAESTRUCTURA (config) · 2 CONTROL (política pública)
PLANOS → INFRAESTRUCTURA
CICLO → DEFINIR ✓ → IMPLEMENTAR (aprobado, pendiente exec)
HOY → deploy.py:26-29 host/user/url hardcodeados (untracked); sincronizar_a_produccion.py:63-67 IP+root
       defaults (TRACKEADO, público)
OBJETIVO → cero credenciales/literales IP/user/pass en código; env vars; prod ausente → FAIL temprano
DECISIÓN → APROBADO. Limpiar ambos scripts + barrido deploy.sh/otros. Rotación = operativo separado, NO bloquea R2
EVIDENCIA → deploy.py:26-29 · scripts/deploy/sincronizar_a_produccion.py:63-67 (verificado)
```

### R3 — RAW INMUTABLE
```
CAPA → 3 RAW · 9 PROVENANCE
PLANOS → DATOS
CICLO → DEFINIR ✓ → IMPLEMENTAR (aprobado, pendiente exec)
HOY → run_update.py:293-300 re_download_edgar hace f.unlink() sobre data/raw/companyfacts|submissions/CIK*.json
OBJETIVO → RAW inmutable: archivar (ts+razón+nombre+SHA256 previo), registrar ingesta/provenance,
           fallo de re-descarga → RAW previo disponible/recuperable
DECISIÓN → APROBADA alternativa A (archivar, no borrar). Sin TTL. Temporales/fixtures/arteactos NO-RAW intactos
EVIDENCIA → run_update.py:297-300 (única violación en producción); barrido de 20 unlink en scripts/ (19 no-RAW)
```

### R4 — CAPA 11 CERTIFICACIÓN
```
CAPA → 11 CERTIFICACIÓN (independiente de 10 VALIDACIÓN y 12 PUBLICACIÓN)
PLANOS → CONTROL (new acta) · lee DATOS (solo stage_runs/runs/checkpoints)
CICLO → DEFINIR ✓ → IMPLEMENTAR (aprobado, pendiente exec)
HOY → No existe capa 11 real: validar_suite/f6_sec autocertifican; 40_certificar.py es piloto TXAR (SQLite);
       API /v2/screener sin gate; schema engine.runs/stage_runs/checkpoints YA migrado
OBJETIVO → c11_certificar.py lee runs+stage_runs+checkpoints, emite acta en engine.certifications (PostgreSQL);
           determinista, idempotente, sin tocar tablas de cálculo
DECISIÓN → APROBADO. JSON solo evidencia. Mundos separados con 40_certificar (sin migrar su criterio).
           Activación INFORMATIVA; R5 (gate vinculante) FUERA
EVIDENCIA → migrations/engine/001_s00_bootstrap.sql (schema); api/main.py:377 (/v1/certificacion lee certificacion_nueva);
            40_certificar.py:27 (ticker='TXAR' hardcodeado)
```

## 1–7. Estado, dependencias, bloqueos y desbloqueados

1. **Estado R1** → DEFINIENDO (HOLD). Clasificación semántica de las 1001 entradas pendiente. Sin DELETE/MERGE/REPLACE/ARCHIVE.
2. **Estado R2** → APPROVED → IMPLEMENTAR (pendiente de fase exec).
3. **Estado R3** → APPROVED → IMPLEMENTAR (alternativa A: archivar, no borrar).
4. **Estado R4** → APPROVED → IMPLEMENTAR (activación informativa).

5. **Dependencias entre R1–R4**:
   - **R1 ↔ R2**: R2 limpieza previa a que el baseline incorpore `deploy.py` (INV2 de R1). R2 no espera al baseline.
   - **R1 ↔ R3/R4**: los archivos nuevos/alterados (run_update, c11, migración 034) se incorporarán a git en el baseline (cuando R1 se desbloquee). No bloquean.
   - **R2 ↔ R3 ↔ R4**: archivos disjuntos (`scripts/deploy/*` vs `run_update.py` vs `engine/`+`migrations/`) → **paralelizables**.
   - **R4 ← R5**: R4 produce el acta que R5 gateará. R5 fuera de esta ejecución.
   - **R4 ⊥ 40_certificar**: mundos separados; migración de criterio post-R5.

6. **Qué queda bloqueado**:
   - R1 (baseline/giit) — espera clasificación semántica.
   - DELETE / MERGE / REPLACE / ARCHIVE de componentes (todos).
   - Rotación de credenciales/infraestructura (acción operativa separada).
   - R5 (gate vinculante de PUBLICACIÓN) y cualquier bloqueo a la API.
   - Migración de la lógica de `40_certificar` a C11 (post-R5).
   - Cualquier política TTL / retención que borre RAW (fuera de R3).

7. **Qué puede pasar a IMPLEMENTAR** (con las reglas por-script y arquitectura de 00_INDEX secc. 5):
   - **R2** (independiente, riesgo bajo) → deploy.py limpio + sincronizar_a_produccion.py env-based + barrido.
   - **R3** (toca pipeline actualizador) → archive en re_download_edgar + ingesta/provenance + test.
   - **R4** (valor arquitectónico) → migración 034 + c11_certificar.py + test_c11_contract.py + manifest.

Orden sugerido de IMPLEMENTAR: **R2 → R3 → R4** (de menor a mayor superficie), cada uno con test y staging antes de prod.