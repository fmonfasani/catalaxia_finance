# 21 — F9: Matriz de gaps post-F8

Severidad por separado de bloqueo de producción (un gap HIGH puede no bloquear STAGING pero sí producción). Evidencia `[CÓDIGO]`/`[EJECUCIÓN]`/`[TEST]`/`[NO DETERMINABLE]`.

## Gaps

| # | GAP | CAPA / PLANO | DEPENDENCIA | SEVERIDAD | BLOQUEA PROD | EVIDENCIA EXISTENTE | EVIDENCIA FALTANTE |
|---|---|---|---|---|---|---|---|
| 1 | TLS `verify=False` en fetch | EXTRACCIÓN / seguridad | ninguno | BLOCKER | SÍ (integridad/trazabilidad de fuentes) | código | auditoría formal de endpoints |
| 2 | auth/CORS API | API / exposición | ninguno | BLOCKER | SÍ (datos expuestos sin control) | código | test de autorización sobre API desplegada |
| 3 | cron-VPS no automatizado | EJECUCIÓN / deploy | 1, 4 | BLOCKER | SÍ (producción depende de disparo manual) | DEPLOY.md, setup_vps | runbook verificado en servidor |
| 4 | runtime legacy (python/venv/entorno VPS) | EJECUCIÓN / deploy | ninguno | HIGH | condiciona 3 | setup_vps.sh | health-check en prod |
| 5 | S03 replace-all / NO_DANGLING | EJECUCIÓN-PARSER / provenance | 4 | BLOCKER condicional | SÍ cuando se manifiesta (gate C10) | `NO_DANGLING` gate + 2 mediciones (90.398, curado) | auto-mitigación |
| 6 | CNV E2E en PG | CNV / integración | 3, 4 | HIGH | condiciona alcance CNV (hoy WARN) | CNV_SCOPE WARN | cadena completa en PG |
| 7 | M5 (schedule) | MARKET / control | 3 | HIGH | condiciona mercado | gap conocido | plan |
| 8 | hist-writer | MARKET | 3 | HIGH | condiciona históricos | gap conocido | plan |
| 9 | ratios equivalence | DERIVED / producto | 6, 7, 8 | HIGH | no bloquea confianza SEC | contratos ratios | matriz de equivalencia completa |
| 10 | market quality | MARKET / producto | 6–9 | MEDIUM | no | reportes parciales | auditoría de calidad |
| 11 | estado terminal de etapa ausente (abort transversal) | CONTROL / state machine | ninguno | HIGH | no (no contamina datos) | S3 reconciliación F9; 16 residuos | diseño de etapa ABORTED |
| 12 | 16 residuos stage-RUNNING (test-f040/f050) | CONTROL / higiene | 11 | NO-BLOCK | no | F9 S2 | sweeper post-mecanismo |
| 13 | tests CNV/f038 stale (9 fallos preexistentes) | CNV-IDENTITY / tests | 6 | MEDIUM | no | 9 FAIL en regresión F9 | actualización de fixtures |

## Matriz de prioridad y orden de ejecución

Orden por **dependencia arquitectónica y riesgo**, no por facilidad:

1. **TLS (1)** y **auth/CORS (2)** — seguridad base de cualquier despliegue.
2. **runtime legacy (4)** — prerequisito de entorno para ejecutar en VPS.
3. **cron-VPS (3)** — automatización de la ejecución productiva; depende de 1–2 y 4.
4. **S03 replace/dangling (5)** — integridad de provenance; desbloquea confianza E2E; puede ejecutarse en paralelo con 1–3.
5. **CNV E2E (6)** — cierra el WARN de alcance; depende de 3–4.
6. **M5 (7)** y **hist-writer (8)** — mercado; dependen de 3; parcialmente de 6.
7. **ratios equivalence (9)** — producto; depende de 6–8.
8. **market quality (10)** — producto; depende de 7–9.
9. **estado terminal de etapa (11)** — fase de control dedicada (requiere cambio de enum + `run_scope` + tests); transversal, sin urgencia de datos.
10. **residuos 16 (12)** y **tests stale (13)** — manteni-miento; dependen de 11 y 6 respectivamente.

## Cierre de la matriz

- BLOCKER: 1, 2, 3, 5. HIGH: 4, 6, 7, 8, 9, 11. MEDIUM: 10, 13. NO-BLOCK: 12.
- Ninguno de los gaps de control (11, 12) pone en riesgo datos, provenance o publicación; todos los quirúrgicos de datos están en EXTRACCIÓN/EJECUCIÓN/MARKET y ya tienen debates previos (S03 con gate).

> Ninguna tarea de esta matriz se implementa en F9 (regla: auditoría). Las propuestas mínimas se documentan en el resultado; F10 define cuál(es) ejecutar.