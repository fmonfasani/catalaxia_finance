# 22 — F10: Actualización de la matriz de gaps

Sólo actualiza la matriz que dejó `21_F9_GAP_MATRIX.md`. **Ningún gap de
producción se implementó en F10** (regla del sprint: sólo la máquina de
estados, y sólo si el resto era dependencia directa — no lo fue).

## Matriz actualizada

| # | GAP | CAPA / PLANO | SEVERIDAD | BLOQUEA PROD | DEPENDENCIA | EVIDENCIA | FASE PROPUESTA |
|---|---|---|---|---|---|---|---|
| 1 | TLS `verify=False` en fetch | EXTRACCIÓN / seguridad | BLOCKER | SÍ | ninguna | código | **F11** |
| 2 | auth/CORS API | API / exposición | BLOCKER | SÍ | ninguna | código | **F11** |
| 3 | cron-VPS no automatizado | EJECUCIÓN / deploy | BLOCKER | SÍ | 1, 2, 4 | `DEPLOY.md`, `setup_vps.sh` | F12 |
| 4 | runtime legacy (VPS) | EJECUCIÓN / deploy | HIGH | condiciona 3 | ninguna | `setup_vps.sh` | F12 |
| 5 | S03 replace-all / `NO_DANGLING` | PARSER / provenance | BLOCKER condicional | SÍ cuando se manifiesta | 4 | gate `NO_DANGLING` + 2 mediciones | F13 |
| 6 | CNV E2E en PG | CNV / integración | HIGH | condiciona alcance CNV | 3, 4 | `CNV_SCOPE=WARN` (C10) | F14 |
| 7 | M5 (schedule) | MARKET / control | HIGH | condiciona mercado | 3 | gap conocido | F14 |
| 8 | hist-writer | MARKET | HIGH | condiciona históricos | 3 | gap conocido | F14 |
| 9 | ratios equivalence | DERIVED / producto | HIGH | no bloquea confianza SEC | 6, 7, 8 | contratos de ratios | F15 |
| 10 | market quality | MARKET / producto | MEDIUM | no | 6–9 | reportes parciales | F15 |
| **11** | **estado terminal de etapa ausente** | **CONTROL / máquina de estados** | ~~HIGH~~ **CERRADO** | ~~no~~ **n/a** | ninguna | `22_F10_STATE_MACHINE.md`, `StageState.ABORTED`, `tests/test_f10_state_machine.py` (35/36) | ✅ **F10** |
| **12** | **16 residuos stage-RUNNING** | **CONTROL / higiene** | NO-BLOCK | no | 11 (cerrado) | `22_PRE_F10_STATE.md` §"los 16" — decisión (C) legacy/test residue, documentada, no tocados | **cerrado por decisión**, no requiere fase |
| 13 | tests CNV/f038 stale | CNV-IDENTITY / tests | MEDIUM | no | 6 | 9 FAIL preexistentes en regresión (F9), +3 reconfirmados en F10 (mismo origen: identidad CUIT no autoritativa en DEV) | F16 |

## Qué cambió respecto de F9

- **Gap #11 pasa de HIGH a CERRADO.** Implementado, probado (35/36 tests,
  1 skip intencional), y verificado con auditoría post-implementación en 8
  puntos (`22_IMPLEMENTATION_RESULT.md` §9), todos limpios.
- **Gap #12 se cierra por decisión, no por trabajo.** Los 16 residuos quedan
  como evidencia histórica del defecto ya corregido; no bloquean nada
  (verificado: C10/C11/C12 los tratan igual con `state='RUNNING'` que con
  `'ABORTED'`, porque deciden por `gate_status`, no por `state`). No generan
  una fase propia.
- **El resto de la matriz no se tocó.** Ningún gap de producción (1–10, 13)
  se implementó. El gap #13 creció en evidencia: los 3 fallos de identidad
  que aparecieron en la regresión de F10 (`CUIT_NO_AUTORITATIVO` en Central
  Puerto S.A.) son la misma familia que F9 ya había clasificado, no un gap
  nuevo.

## Orden propuesto (sin cambios respecto de F9 en la cabecera)

F10 no reordena la prioridad: los gaps #1/#2 (TLS, auth/CORS) ya eran la
prioridad más alta en `21_F9_GAP_MATRIX.md` — sin dependencias, seguridad base
de cualquier despliegue — y seguían sin resolverse antes de F10 igual que
después. El cierre de #11 no adelanta a ningún otro gap: era una rama
paralela (control/auditoría), no algo que bloqueara a #1–#10.

1. **F11 — TLS + auth/CORS** (gaps 1, 2). Sin dependencias, BLOCKER, base de
   cualquier despliegue.
2. **F12 — runtime + cron-VPS** (gaps 4, 3). Depende de F11.
3. **F13 — S03 replace/provenance** (gap 5). Puede correr en paralelo con
   F11/F12; depende sólo de 4.
4. **F14 — CNV E2E + Market (M5/hist-writer)** (gaps 6, 7, 8). Depende de
   F12.
5. **F15 — ratios equivalence + market quality** (gaps 9, 10). Depende de
   F14.
6. **F16 — tests stale** (gap 13). Depende de 6 (CNV E2E); mantenimiento, sin
   urgencia de datos.

## Recomendación de F11

**TLS `verify=False` (gap 1) + auth/CORS de la API (gap 2).** Los dos son
`BLOCKER`, los dos tienen dependencia `ninguna` (pueden empezar ya), y los
dos son la definición misma de "seguridad base" que el resto de la matriz da
por sentada. Ninguno tiene relación con la máquina de estados que cerró F10:
son puramente de la capa EXTRACCIÓN/API, sin overlap de archivos ni de
tablas.
