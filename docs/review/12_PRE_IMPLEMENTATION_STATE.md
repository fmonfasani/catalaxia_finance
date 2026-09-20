# 12 — Estado pre-implementación (evidencia de punto de partida)

Registro previo a cualquier modificación F1. Solo lectura + este documento.

- Rama: `fix/ttm-ratios-cnv`. HEAD: `2993918 fix(F-050): cerrar corridas con run_scope en S00/S01/S02`.
- Working tree SUCIO con cambios preexistentes ajenos a este paso (~90 archivos M: engine/db.py, engine/identity.py, s00–s04, c3, run_update, market_db, setup_vps.sh, pipeline/*, api/main.py, docs; ~30 D docs/logs; ~200 ?? incl. `tests/test_c11_contract.py` y los documentos 01–11). `[EJECUCIÓN: git status]`.
- `scripts/engine/s04_normalize.py`: MODIFICADO preexistente vs HEAD (E2E-checkpoint F-031, canonización F-055, fix `parser_version` de sesión anterior). Baseline F1 = working tree actual, no HEAD. Report legacy dict en s04:640-666, sin import de `engine.report`. `[CÓDIGO]`.
- `tests/test_c11_contract.py`: existe en disco, pasa (26 con e2e), pero UNTRACKED en git (sin historial). Extenderlo lo mantiene untracked. `[EJECUCIÓN]`.
- DB: PG dev/test alcanzable (suites previas PASS en este entorno); producción: sin acceso desde aquí y sin tocar (registro: intacta por abstención). SQLite locales presentes (`screener.db` 70 tablas, etc.). Migraciones: 032/033/034 untracked + `engine/manifest.yaml` modificado — NO tocar. `[EJECUCIÓN]`.
- Archivos autorizados F1 (únicos): `scripts/engine/s04_normalize.py` (solo bloque de reporte) + `tests/test_c11_contract.py` (solo extensión).
- Precondiciones §3: 11 = READY_FOR_IMPLEMENTATION ✓ · F0/F1 = READY ✓ · modificaciones concurrentes extensas pero en regiones distintas (se verificará en el diff: solo bloque reporte + test) · producción intacta ✓. Veredicto: PROCEED con alcance vigilado.
