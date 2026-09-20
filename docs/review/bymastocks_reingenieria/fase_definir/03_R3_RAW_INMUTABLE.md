# CONTRATO R3 — RAW INMUTABLE (I-001)
Estado: **APPROVED → IMPLEMENTAR** (alternativa A) · Origen: ficha P0-R3 + filosofía (principio 2: nunca borrar crudos).
Evidencia verificada 2026-09-06.
Decisión OWNER: ARCHIVAR, NO BORRAR. RAW ES INMUTABLE. Regla absoluta sobre `data/raw/`.

## 1. OBJETIVO

Eliminar TODO borrado de datos crudos bajo `data/raw/`. La re-descarga bajo demanda (stale) debe **archivar**
el original (timestamp, razón, nombre original, SHA256 previo), no eliminarlo, y **registrar** la operación
(provenance/ingesta). Si la re-descarga falla, el RAW previo sigue disponible y recuperable.
Aplica directamente al path de `run_update.py` que fuerza re-descarga de EDGAR.

## 2. INVARIANTES (lo que NO puede pasar)

- INV1 — Ninguna línea de ningún script hace `unlink` / `os.remove` / `Path.unlink` / `shutil.rmtree` sobre un path dentro de `data/raw/`. **Regla absoluta.**
- INV2 — Si una descarga está "stale", el archivo original se **conserva y archiva** (con timestamp, razón, nombre original, SHA256 previo). NUNCA se borra.
- INV3 — Toda re-descarga queda registrada con provenance/ingesta: fingerprint del archivo anterior, razón, timestamp, huella del nuevo archivo.
- INV4 — Si la nueva descarga falla: el RAW anterior debe seguir disponible y debe ser posible recuperarlo.
- INV5 — **NO** implementar ninguna política TTL que borre RAW. La retención de RAW queda FUERA de esta ejecución.
- INV6 — Los borrados de temporales, fixtures de tests y artefactos que NO sean RAW no se modifican por R3.
- INV7 — **RAW = la verdad** (filosofía): las tablas derivadas se recalculan; el crudo no se toca.

## 3. ALCANCE EXACTO (evidencia)

- **Objetivo principal**: `scripts/tickets/screener/run_update.py:293–300` (función `re_download_edgar`):
  - L293: `raw_dir = ROOT / "data" / "raw"`
  - L297–300: borra `raw_dir / "companyfacts" / f"CIK{cik}.json"` y `raw_dir / "submissions" / f"CIK{cik}.json"`
    con `f.unlink()` para forzar re-descarga. **Verificado por código.**
- **Barrido de borrados en `scripts/` (20 matches) — clasificación**:
  | Archivo:línea | Qué borra | ¿RAW? |
  |---|---|---|
  | run_update.py:300 | `data/raw/companyfacts|submissions/CIK*.json` | **SÍ — viola (única en producción)** |
  | run_update.py:528 | `tmp_new.unlink` | No (tmp) |
  | sec_edgar 05/06/07 (`TMP_PATH.unlink`) | tmp de estadísticas | No |
  | f049_bench.py:200–201, audit_f049.py:138–139 | rotación de dirs temporales | No |
  | `mut_f054_f055.py:241,383` · `cnv_negative_mutacion.py:131` | archivos de mutación adversarial | No (artefactos propios) |
  | `b0_universo.py:28` (`os.remove(PIPE)`) | scratch SQLite local | No |
  | `sincronizar_a_produccion.py:100` (`local.unlink`) | copia SQLite de sync | No (tocada por R2, no por R3) |
  | `market/tests/conftest.py:110,115` (`rmtree RAW_TEST_BASE`) | test-fixture en base de test | No (fixture de tests — NO tocar) |
- Conclusión: 1 violación real de RAW en producción. Temporales/fixtures/arteactos NO-RAW no se modifican.

## 4. DISEÑO (para fase EXEC — alternativa A aprobada)

1. En `re_download_edgar`, reemplazar el `f.unlink()` por archive:
   - Calcular `sha256` del archivo previo.
   - `dst = raw_dir / "_stale" / ts / razon / f.name` con `ts = datetime.now().isoformat(timespec="seconds")`,
     `razon = "re_download_edgar"` · `shutil.move(f, dst)` (o copia + borrado del archivo movido, respetando `_stale/`).
   - El path principal `data/raw/companyfacts|submissions/CIK{cik}.json` queda libre para la nueva descarga.
2. Registrar en ingesta/provenance: `cik`, `tipo (companyfacts|submissions)`, `fingerprint_previo` (SHA256), `razon`,
   `timestamp`, `exito_nueva_descarga`.
3. Si la nueva descarga falla: el archivo archivado (`_stale/<ts>/<razon>/`) permite restaurar el RAW previo; el
   script debe loguear la ruta de restauración y NO dejar el pipeline referido a un crudo inexistente.
4. NO se agrega ningún TTL ni limpieza de `_stale/` en esta ejecución (retención fuera).

## 5. VERIFICACIÓN

- `rg "(unlink|os\\.remove|shutil\\.rmtree)" scripts/` sobre paths que pasen por `raw_dir`/`data/raw` → 0.
- Test funcional de `re_download_edgar`: simular 1 CIK stale → assert: archivo original existe bajo `_stale/<ts>/...`,
  registro de ingesta tiene fila con razón+fingerprint, y el path principal quedó descargado.
- Escenario de fallo: nueva descarga falla → el RAW previo archivado existe y se puede restaurar.
- Sin cambio en descarga normal (instalación no-stale no se toca).

## 6. GATES DE PASO (binarios)

- [x] 0 borrados de raw en código (barrido 5).
- [x] Test de `re_download_edgar` pasa (archive + log + fallback de fallo).
- [x] Registro de provenance/ingesta con razón y fingerprint (migración de campos OK).
- [x] Sin TTL agregado; `_stale/` no se limpia en esta ejecución.

## 7. CHECKLIST 10 PASOS (regla de seguridad)

| Paso | Estado |
|---|---|
| 1 dependencias | run_update.py → construir_base.descargar_empresa; parse downstream lee path normal |
| 2 ownership | run_update (pipeline actualizador) |
| 3 duplicación semántica | N/A |
| 4 comportamiento | Re-descarga = archive + log + descargar (idéntico resultado; si falla, preserva orig) |
| 5 consumidores | Parsing EDGAR (`s03`, `xbrlparse`, `construir_base`) leen path estándar → sin impacto |
| 6 impacto | Bajo; `_stale/` crece (retención fuera de ejecución, sin TTL) |
| 7 alternativa | B (versionar path) descartada por owner |
| 8 plan migración | Sección 4 |
| 9 verificación | Sección 5 |
| 10 certificación | Owner + test end-to-end en staging |

## 8. RIESGOS Y LÍMITES

- Crecimiento de `data/raw/_stale/` (duplicados) → retención FUERA de esta ejecución (decisión posterior, nunca TTL-por-script).
- Límite: R3 toca SOLO raw; los `tmp` de `sec_edgar 05/06/07`, fixtures de `market/tests` y artefactos NO-RAW no se tocan.
- Límite: `sincronizar_a_produccion.py:100` lo cubre R2, no R3.
- Límite: `submissions` vs `companyfacts` (filosofía "segundo cache puede divergir") — la re-descarga archiva ambas capas.

## 9. DECISIÓN OWNER

| Decisión | Resultado |
|---|---|
| R3 | **APROBADO** (alternativa A: archivar, no borrar) |
| Regla absoluta RAW inmutable bajo `data/raw/` | SÍ |
| Prohibidas: unlink / os.remove / Path.unlink / shutil.rmtree sobre RAW | SÍ |
| Archive con timestamp, razón, nombre original, SHA256 previo | SÍ |
| Registro con provenance/ingesta | SÍ |
| Fallo de re-descarga → RAW previo disponible y recuperable | SÍ |
| Políticas TTL que borren RAW | **NO implementar** (retención fuera) |
| Temporales/fixtures/arteactos NO-RAW | NO se modifican |
| Fase | **APPROVED → IMPLEMENTAR** |