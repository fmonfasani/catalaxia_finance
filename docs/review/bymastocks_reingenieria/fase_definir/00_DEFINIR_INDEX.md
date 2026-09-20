# 00 — FASE DEFINIR — ÍNDICE Y CONTRATOS R1–R4
Estado: **FASE DEFINIR — decisiones OWNER registradas 2026-09-06**. SIN ejecución de código.

## 1. Qué es esta fase

Los contratos R1–R4 especifican QUÉ cambiar, DÓNDE (evidencia con línea/archivo), QUÉ NO puede pasar (invariantes),
CÓMO verificarlo y QUÉ gates cierran el R. Las decisiones arquitectónicas del owner quedan registradas en cada contrato.

## 2. Template de contrato

```text
CONTRATO R#
- OBJETIVO
- INVARIANTES (lo que NO puede pasar)
- ALCANCE EXACTO (archivo:línea + tabla)
- DISEÑO (alternativas + pasos para la fase de ejecución)
- VERIFICACIÓN (comandos/asserts que prueban cumplimiento)
- GATES DE PASO (binarios)
- CHECKLIST 10 PASOS (regla de seguridad)
- RIESGOS Y LÍMITES
- DECISIÓN OWNER (estado: DEFINIENDO → APPROVED → IMPLEMENTAR → DONE)
```

## 3. Matriz de estado

| R | Contrato | Objetivo | Estado | Gate principal |
|---|---|---|---|---|
| R1 | 01_R1_GIT_BASELINE.md | Repo público con baseline limpio: código bajo git, basura ignorada | **DEFINIENDO (HOLD)** | Clasificación semántica de las 1001 entradas aprobada |
| R2 | 02_R2_SECRETOS.md | Cero credenciales/defaults sensibles en código versionado | **APPROVED → IMPLEMENTAR** | `git grep` de patrones = 0 en tracked |
| R3 | 03_R3_RAW_INMUTABLE.md | Ningún path bajo `data/raw/` se borra; re-descarga archivada y logueada | **APPROVED → IMPLEMENTAR** (alt A) | 0 `unlink`/`remove` sobre raw en todo `scripts/` |
| R4 | 04_R4_CAPA11.md | Capa 11 independiente que certifica corridas desde `stage_runs` | **APPROVED → IMPLEMENTAR** (informativa) | c11 emite veredicto determinista para run OK y run BLOCK |

## 4. Decisiones OWNER (2026-09-06)

1. **R1** — NO ejecutar baseline. Mantener R1 en DEFINIR hasta completar la clasificación semántica de las 1001 entradas.
   Prohibido sobre componentes: DELETE, MERGE, REPLACE, ARCHIVE.
2. **R2** — APROBADO. Quitar todo valor sensible (IP/host, usuario prod, credenciales, tokens, API keys, passwords,
   defaults sensibles en `os.environ.get`). Config vía variables de entorno. Prod: variable ausente → FAIL temprano.
   `deploy.py` debe quedar limpio antes de incorporarse; `sincronizar_a_produccion.py` debe limpiarse.
   La rotación de infraestructura/credenciales es acción operativa separada y NO bloquea R2.
3. **R3** — APROBADA alternativa A (ARCHIVAR, NO BORRAR). RAW INMUTABLE bajo `data/raw/`. Sin
   unlink/os.remove/Path.unlink/shutil.rmtree sobre RAW. `re_download_edgar` conserva y archiva el RAW previo con
   timestamp, razón, nombre original y SHA256 previo; registro con provenance/ingesta; si la re-descarga falla el RAW
   previo sigue disponible y recuperable. **NO** implementar políticas TTL que borren RAW; retención fuera de esta
   ejecución. Borrados de temporales/fixtures/arteactos NO-RAW no se tocan.
4. **R4** — APROBADO. Capa 11 independiente de VALIDACIÓN (Capa10) y previa a PUBLICACIÓN (Capa12). C11 lee
   `engine.runs`, `engine.stage_runs`, `engine.checkpoints`. NO calcula, NO modifica tablas de cálculo, NO reemplaza
   VALIDACIÓN. Crear `scripts/engine/c11_certificar.py` y
   `migrations/engine/034_c11_certifications.sql` (numeración corregida en
   ejecución: el contrato decía `002`, pero `002_s01_identity.sql` ya existe y
   F-049 impone respetar el orden por nombre y el historial).
   Salida primaria: tabla `engine.certifications`. JSON solo como artefacto de evidencia, no fuente primaria.
5. **R4 — 40_certificar**: NO migrar su criterio a C11. Mantener mundos separados: `40_certificar → certificacion_nueva
   → legado` y `C11 → engine.certifications → futuro gate R5`. `40_certificar.py` queda como referencia histórica/piloto,
   NO es autoridad de Capa 11, NO modificarlo. Migración posterior = decisión luego de verificar C11 y R5.
6. **R4 — Activación**: C11 inicialmente INFORMATIVA. NO bloquea API ni PUBLICACIÓN. Secuencia: C11 → certificación
   informativa → VERIFICAR → CERTIFICAR C11 → R5 → gate vinculante. R5 queda FUERA de esta ejecución.

## 5. Arquitectura obligatoria (a respetar por toda implementación)

**12 capas**: 1 FUENTES · 2 IDENTIDAD · 3 RAW · 4 PARSED · 5 NORMALIZED · 6 ECONOMIC FACTS · 7 FINANCIAL MODEL ·
8 RATIOS · 9 PROVENANCE · 10 VALIDACIÓN · 11 CERTIFICACIÓN · 12 PUBLICACIÓN

**4 planos**: 1 DATOS · 2 CONTROL · 3 EJECUCIÓN · 4 INFRAESTRUCTURA

**Ciclo**: DEFINIR → IMPLEMENTAR → VERIFICAR → CERTIFICAR

**Regla por script** (todo script reingenierizado): una capa primaria, responsabilidad explícita, inputs, outputs,
dependencias, consumidores, contrato, invariantes, provenance, determinismo donde corresponda, idempotencia donde
corresponda, evidencia verificable. Ningún script es conforme por su nombre o ubicación.

## 6. Regla de no-ejecución

En esta tarea solo se actualizó documentación de contratos. R1 permanece en DEFINIR. R2/R3/R4 están APPROVED y
pueden pasar a IMPLEMENTAR (fase posterior explícita). Sin DELETE/MERGE/REPLACE/ARCHIVE sobre componentes.