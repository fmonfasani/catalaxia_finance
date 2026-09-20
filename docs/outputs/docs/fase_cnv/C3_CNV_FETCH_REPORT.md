# C3 — CNV FETCHER — REPORTE DE EJECUCIÓN — Golden Case CEPU

Generado: 2026-08-25 (sesión de ejecución, baseline `catalaxia-baseline-2026-08-25`,
commit `444ee1a`). Alcance: llevar C3 de "implementado, nunca ejecutado" a una
primera ejecución real y validada, sin maquillar el resultado.

> **ADDENDUM (misma sesión, segunda vuelta)**: los §4 y §6 de abajo describen
> el diagnóstico ORIGINAL (BLOCK por idempotencia, bug de columnas en
> C-C3-007). Ambos se corrigieron después, con la idempotencia resuelta por
> decisión explícita del usuario ("hash canónico acotado", de 4 opciones
> presentadas). Además se encontró y corrigió un TERCER bug al re-validar
> (crash de `ux_checkpoints_reuse` en el insert de checkpoint). Las 3
> correcciones están validadas con corridas reales adicionales (runs 4-6) y
> con 8 tests de humo nuevos. **El detalle completo y actualizado de los 3
> fixes está en `.claude/state/CNV_C3_STATE.md` — ese archivo es la fuente de
> verdad vigente; este reporte queda como bitácora del diagnóstico inicial.**

## 1. Veredicto (actualizado)

**PASS — CHECKPOINTED, con idempotencia real.** Los 3 problemas descritos en
este reporte (idempotencia rota, bug de columnas en C-C3-007, y uno
adicional encontrado después — crash de checkpoint-reuse) fueron corregidos
y re-validados con ejecuciones reales (runs 4, 5 y 6, ver `CNV_C3_STATE.md`).
El checkpoint `8db8692ebce9439c8be69cbaf5c82979` de la primera corrida se
mantuvo estable (reutilizado, no duplicado) a través de 3 corridas PASS
adicionales. Contenido original del diagnóstico, sin editar, a continuación:

C3 **no está CERTIFIED**. El primer PASS es real y queda checkpointed; lo que
falta es una decisión de diseño para que la idempotencia pueda volver a pasar
en una corrida futura.

## 2. Validación de C2 (condición de entrada a C3)

El veredicto de C2 (`C2_CNV_REVIEWS_RESOLUTION.md`) exige, textualmente, dos
condiciones antes de un "primer fetch masivo": (a) resolver R-001/R-002/R-005
vía fuente externa (AFIP), (b) regenerar el inventario separando
CONTROLADA/VINCULADA.

- **(a)** No se resolvió — sigue requiriendo AFIP. Confirmado que las 3
  reviews (`REVIEWS_NO_CERRABLES` en el código) permanecen `OPEN` en
  `C2_CNV_IDENTITY_REVIEWS_V2.csv` y que C3 las trata como no-cerrables sin
  bloquear, tal como está diseñado.
- **(b)** No se cumplió como artefacto: `C0_CNV_PRESENTATION_INVENTORY.csv`
  sigue sin regenerar (fechado 2026-08-23, anterior a C2). **Pero se demostró
  que esto no aplica a un run `--scope EEFF_PROPIO`**: C3 nunca lee ese CSV,
  hace discovery en vivo con el clasificador ya corregido de
  `engine/cnv/discovery.py`. La corrida real lo confirma empíricamente:
  51 CONTROLADA + 27 VINCULADA separadas correctamente (antes vivían
  mezcladas en un solo bucket `EEFF_CONTROLADA`).

**Conclusión**: C2 validado para `EEFF_PROPIO`. Sigue abierto para
`FINANCIERO`/`TODO`.

## 3. Primera corrida real

| Campo | Valor |
|---|---|
| Comando | `python scripts/engine/c3_cnv_fetch.py --cuit 33650305499 --scope EEFF_PROPIO` |
| run_id | `5460d7b5db794d88baef2e8966dd72be` |
| git_commit | `444ee1ad0e1b092c79ce055ded0b993fbc55822d` |
| CUIT / entidad | `33650305499` — CENTRAL PUERTO S.A. (`CIK:0001717161`, binding=`C1_SEED`) |
| Duración | ~2 min (04:27:08 → 04:29:00 UTC) |
| Empresa page | HTTP 200, 2.261.611 bytes, VALID |
| Discovery | 1927 filas con guid, 1861 únicos, 66 duplicados por sección |
| Plan (EEFF_PROPIO) | 74 visores |
| Fetch | 74/74 OK, 0 fallidos, 0 en revisión |
| RAW escrito | 76 archivos, 10.248.839 bytes nuevos, 0 sobreescrituras |
| Gate | **PASS 10/10** |
| Checkpoint | `8db8692ebce9439c8be69cbaf5c82979` |

Cobertura de las 74 presentaciones EEFF_PROPIO fetcheadas: 100% con
`fecha_cierre` (rango 2018-12-31 → 2026-06-30), 100% NIIF, tipo_balance
CONSOLIDADO=61/INDIVIDUAL=13, periodicidad TRIMESTRAL=53/ANUAL=19/SEMESTRAL=2.

Hallazgo registrado sin ocultar (no bloqueante): `identity.entities.cuit` es
NULL en Postgres para esta entidad — el seed C1 nunca se promovió a la tabla.
Pertenece a C1; C3 lo registra y no lo corrige.

## 4. Corrida de idempotencia (`--rerun`) — BLOCK con causa raíz

| Campo | Valor |
|---|---|
| Comando | mismo + `--rerun` |
| run_id | `ae678ef50a2f44f38f35123e5fe769b5` |
| Gate | **BLOCK** — falla `C-C3-006` (blocking) |
| Checkpoint | ninguno (correctamente, el gate bloqueado no genera checkpoint) |
| Detalle del check | "escrituras nuevas=75 (esperado 0), SIN_CAMBIOS=0/75" |

**Causa raíz** (confirmada con `diff` byte a byte, no supuesta): tanto
`EMPRESA_PAGE` como `VISOR` incluyen contenido aleatorio por request:

- `EMPRESA_PAGE`: query-strings de cache-busting (`?v=<guid-random>`) en los
  `<link>`/`<script>` de CSS/JS estáticos — el contenido sustantivo (guids de
  presentaciones, títulos, fechas) es idéntico.
- `VISOR`: un `RequestVerificationToken` (anti-forgery ASP.NET), aleatorio por
  diseño de seguridad del propio CNV.

`RawStore.store()` calcula idempotencia por sha256 del cuerpo completo de la
respuesta. Con contenido garantizado-distinto en cada request, **el hash
nunca puede coincidir entre dos fetches**, sin importar reintentos. Evidencia
independiente en DB: `fetch_raw.cnv_artifact` tiene 150 filas con **150
sha256 distintos** (75 de cada corrida, 0 coincidencias).

Esto no es corrupción de datos ni un bug transitorio: es un límite de diseño
del gate `C-C3-006` frente a una fuente que nunca repite bytes. Se documenta
como decisión pendiente (ver `.claude/state/CNV_C3_STATE.md`, sección
"DECISIÓN REQUERIDA") en vez de resolverse unilateralmente en esta sesión.

## 5. Corrida negativa — manejo de error

| Campo | Valor |
|---|---|
| Comando | `--cuit 99999999999 --scope EEFF_PROPIO` (CUIT inexistente) |
| run_id | `e97e95e2fd7941aebe6ce6b506793772` |
| Resultado | **BLOCK correcto e inmediato**, exit code 1 |

CNV respondió HTTP 200 (la trampa documentada desde C0) pero con la shell
genérica de 40.720 bytes exactos. Validación: 4 reglas HARD falladas
(V-MIN-SIZE, V-EXPECTED-ENTITY, V-HAS-PRESENTATIONS, V-GENERIC-PAGE). C3 no
inventó identidad (2 hallazgos registrados), no intentó discovery, y guardó
la shell bajo su propio namespace `CUIT99999999999/` sin cruzarse con los
datos de CEPU.

## 6. Regresión

**Cero tests automatizados** para `engine/cnv/*` o `c3_cnv_fetch.py`,
confirmado antes y después de esta sesión. La validación de esta sesión es
integración real contra CNV en vivo (3 corridas), no cobertura de regresión
reproducible sin red.

**Bug de código encontrado, no corregido** (fuera del mandato de esta
sesión): el check `C-C3-007` lee columnas `estado_c2`/`estado` de
`C2_CNV_IDENTITY_REVIEWS_V2.csv`, pero el CSV real usa `status_prev`/`status`.
El resultado es que la sub-verificación "ninguna review no-cerrable se cerró
indebidamente" siempre pasa vacuamente (comparación contra `None`). Hoy el
veredicto PASS es correcto — se confirmó manualmente que R-001/002/005 siguen
`OPEN` — pero el check no lo está probando por sí mismo.

## 7. Artefactos de esta corrida

- `outputs/docs/fase_cnv/C3_CNV_{INVENTORY,MANIFEST,PROVENANCE,REVIEW_QUEUE,VALIDATION}.*`
  — reflejan la corrida MÁS RECIENTE (run 2, BLOCK); se sobreescriben en cada
  invocación normal del script.
- `outputs/docs/fase_cnv/C3_CNV_STAGE_REPORT_run{1,2,3}_*.json` — un archivo
  por corrida, extraído de `engine.stage_runs.report` (DB), nunca
  sobreescrito. Aquí queda preservado el PASS del run 1.
- `scratchpad/c3_runs/run{1,2,3}_*.log` — stdout completo de cada corrida.
- `data/raw/engine/cnv/CUIT{33650305499,99999999999}/` — RAW real en disco
  (gitignored, ~10 MB).

## 8. Próximo paso exacto

1. Decisión de diseño sobre idempotencia de `EMPRESA_PAGE`/`VISOR` (3
   opciones sin evaluar, listadas en `CNV_C3_STATE.md`).
2. Fix acotado del bug de columnas en `C-C3-007`.
3. Recién después: evaluar `--scope FINANCIERO` (requiere resolver o aceptar
   explícitamente R-001/R-002/R-005).

Detalle completo, evidencia cruda y comandos de verificación:
`.claude/state/CNV_C3_STATE.md`.
