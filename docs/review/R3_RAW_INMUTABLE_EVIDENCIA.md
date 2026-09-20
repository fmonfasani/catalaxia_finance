# EVIDENCIA R3 — RAW INMUTABLE

| Campo | Valor |
|---|---|
| Fecha de emision | 2026-09-06 |
| Contrato | `docs/review/bymastocks_reingenieria/fase_definir/03_R3_RAW_INMUTABLE.md` (APPROVED → IMPLEMENTAR, alt. A) |
| Decisión owner | **ARCHIVAR, NO BORRAR. RAW ES INMUTABLE. Regla absoluta sobre `data/raw/`.** |
| Documento de test | `tests/test_r3_raw_inmutable.py` |
| Estado | **VERIFICADO — PENDIENTE CERTIFICACIÓN** (la certificación es etapa separada) |

---

## DEFINIR — qué significa RAW inmutable en este repositorio

**RAW** es `data/raw/` (fuente de verdad, filosofía P0-R3 principio 2). En esta
ejecución los crudos auditados son los que gestiona el camino EDGAR del screener:

- `data/raw/companyfacts/CIK*.json` — empresafacts de SEC (hechos XBRL).
- `data/raw/submissions/CIK*.json` — índice de presentaciones de SEC.

**Operaciones PROHIBIDAS** sobre `data/raw/` (regla absoluta):
`unlink` / `os.remove` / `os.unlink` / `Path.unlink` / `shutil.rmtree` /
`truncate` / equivalente, y cualquier política TTL destructiva.

**Operaciones PERMITIDAS**:
1. Crear/escribir una versión nueva en el path principal (nueva captura).
2. **ARCHIVAR** el crudo previo antes de reemplazarlo:
   moverlo a `data/raw/_stale/<ts>/<razon>/<tipo>/<nombre>` con provenance.
3. **RESTAURAR** el crudo previo desde el archive si la nueva captura falla.

**Contrato de archive** (mínimo, sin sistema grande):

| Aspecto | Definición |
|---|---|
| Destino | `data/raw/_stale/<ts>/<razon>/<tipo>/<nombre>` |
| `<ts>` | `datetime.now(utc).isoformat(timespec="seconds")` con `:`→`-` (válido en Windows) |
| `<razon>` | motivo: `re_download_edgar` |
| `<tipo>` | capa de origen: `companyfacts` / `submissions` (evita colisión de nombres entre capas) |
| Origen preservado | `origen_rel` (`companyfacts/CIK..json`) + `origen_abs` |
| SHA256 previo | sí, en provenance + `ingesta_log.hash` |
| Sidecar | `<nombre>.meta.json` junto al archivo archivado (nombre, origen, sha, bytes, ts, razón) |
| Registro | `ingesta_log` (fuente `sec_edgar`), `motivo = R3:archivado:<razon>` / `R3:restaurado:<razon>` |
| Colisión | nunca sobrescribe: sufijo `-1`, `-2`, ... |
| Idempotencia | `archivar()` es no-op si el archivo no existe; `restaurar()` no-op si el destino ya existe |
| Recuperación | `restaurar()` copia de vuelta desde el archive (la copia archivada se conserva) |
| Retención | **sin TTL; `_stale/` no se limpia en esta ejecución** (decisión posterior, INV5) |

**Relación versión previa ↔ nueva**: la fila `R3:archivado` (hash=sha previo)
seguida de la fila de descarga de `get_json_cache` (hash=sha nuevo, motivo
`forzado`/`nuevo`) comparten `entidad=cik` y `recurso=tipo`.

**Componente**: `scripts/tickets/screener/_raw_inmutable.py` — el ÚNICO que sabe
archivar/restaurar/registrar un crudo. `run_update.py` detecta y orquesta.

---

## IMPLEMENTAR

**Hallazgo (la única violación productiva de R3):** `run_update.py:300`
(`f.unlink()`) borraba `data/raw/companyfacts|submissions/CIK*.json` para forzar
la re-descarga EDGAR stale. Se reemplazó por **archive**:

- `scripts/tickets/screener/_raw_inmutable.py` (nuevo): `archivar()`,
  `restaurar()`, `registrar()` + `_ts()`, `sha256()`. Mueve el crudo a
  `_stale/`, escribe `*.meta.json`, registra en `ingesta_log`. Sin TTL.
- `scripts/tickets/screener/run_update.py`:
  - imports: `from _raw_inmutable import archivar as archivar_raw, ...`.
  - `re_download_edgar` (L299-335): ya no hay `f.unlink()`. Archiva ambos
    crudos (companyfacts + submissions), registra provenance, ejecuta
    `descargar_empresa`, y si la re-descarga no deja archivo nuevo en el path
    principal restaura el previo desde el archive y registra `R3:restaurado`.

Sin cambios de lógica económica, sin tocar PARSED/NORMALIZED, sin touch de
temporales (`TMP_PATH.unlink`, `tmp_new.unlink`) ni fixtures (`conftest
RAW_TEST_BASE`): INV6.

---

## VERIFICAR — tests ejecutados

```
python -m pytest tests/test_r3_raw_inmutable.py -v
=> 10 passed
```

Cobertura vs. los 10 puntos pedidos:

| # | Requisito | Test |
|---|---|---|
| 1 | RAW existente no desaparece tras nueva ingesta | `test_raw_no_desaparece_tras_nueva_ingesta` |
| 2 | Nueva versión no sobrescribe destructivamente la previa | ídem + `test_colision_nombre_no_destruye_datos` |
| 3 | SHA256 de la versión previa verificable | `test_sha256_version_anterior_verificable` |
| 4 | Archive conserva provenance | `test_archive_conserva_provenance` |
| 5 | Colisión de nombre no destruye datos | `test_colision_nombre_no_destruye_datos` |
| 6 | Reejecución segura/idempotente | `test_reejecucion_idempotente` |
| 7 | No DELETE sobre RAW en camino productivo | `test_no_delete_sobre_raw_camino_productivo` + `test_run_update_no_unlinka_raw` |
| 8 | Temporales/test no se confunden con RAW productivo | `test_tmp_y_test_no_tocan_raw_productivo` (+ snapshot de `data/raw` real) |
| 9 | Consumidores posteriores siguen funcionando | `test_consumidores_y_cadena_raw_parsed` (`get_json_cache` real) |
| 10 | No se rompe la cadena RAW → PARSED | ídem (path principal parseable) |
| + | INV4 fallo de re-descarga → previo disponible/restringido | `test_falla_red_restaura_previo` |

Regresión (sin tocar R2): `tests/test_r2_secretos.py` + `tests/test_runbook_operability.py`
`=> 518 passed`.

---

## GATES ejecutados

| Gate | Comando | Resultado |
|---|---|---|
| 0 borrados de RAW en código | `git grep -nE "unlink\|os.remove\|os.unlink\|Path.unlink\|shutil.rmtree\|.truncate" -- *.py *.sh` | Sólo tmp (`tmp_new`, `TMP_PATH`, `PIPE`), test fixture (`conftest RAW_TEST_BASE`) y sqlite de sync (R2). **0 sobre RAW.** |
| Sin operación destructiva referenciando `data/raw`/`raw_dir` | `git grep -nE "data/raw|raw_dir" -- *.py` filtrado por delete | **0 coincidencias** |
| `re_download_edgar` archive + log + fallback | suite R3 | PASS (10/10) |
| Provenance/ingesta con razón y fingerprint | `ingesta_log`: fila `R3:archivado` con `hash`=sha previo; `*.meta.json` | PASS |
| Sin TTL; `_stale/` no se limpia | revisión de `_raw_inmutable.py` y `run_update.py` | PASS |
| Sin regresiones | R2 + runbook | 518 passed |

Clasificación del barrido completo (92 hits de borrado en `scripts/`): todas son
`DROP TABLE`/`DELETE` sobre tablas derivadas, temporales, artefactos de mutación
adversarial, o fixtures de test. **RAW PRODUCTIVO: 1 hit (corregido).**

---

## NO CONFORMIDADES / LÍMITES

- No hay no conformidad R3 abierta (violación única corregida y verificada).
- Límite: `_stale/` crece sin retención definida — por diseño (INV5), la
  retención queda como decisión futura, nunca TTL por script.
- Límite: `market/tests/conftest.py` `rmtree RAW_TEST_BASE` es fixture de tests
  (INV6, no RAW productivo) y no se modificó.
- Límite: `sincronizar_a_produccion.py:117 local.unlink` es copia SQLite de sync
  (capa R2), no se toca.

---

## ESTADO

**VERIFICADO — PENDIENTE CERTIFICACIÓN.**

Evidencia reproducible, invariantes R3 cumplidas (INV1–INV7), sin violaciones RAW
productivas abiertas, provenance preservada, sin regresiones. La certificación se
emite en etapa separada del mismo modo que R2.

Referencias:
- Contrato: `docs/review/bymastocks_reingenieria/fase_definir/03_R3_RAW_INMUTABLE.md`
- Implementación: `scripts/tickets/screener/_raw_inmutable.py`, `scripts/tickets/screener/run_update.py`
- Tests: `tests/test_r3_raw_inmutable.py`