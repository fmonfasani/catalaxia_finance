# 22 — F10 Security (blockers): Implementation Result

Fase de seguridad sobre **solo DOS gaps BLOCKER de producción** de la matriz F9: TLS en fuentes
(1) y auth/CORS del API (2). El hallazgo transversal de F9 (11: estado terminal de etapa) ya fue
cerrado por la fase hermana `22_F10_STATE_MACHINE.md` (StageState.ABORTED + cierre de etapa en
`run_scope`) en este mismo árbol; aquí no se duplica.

## Cambios

### TLS en camino productivo (gap 1 → ADDRESSED)
10 archivos: `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py`, `job5_extract_eeff.py`,
`job6_extract_div.py`, `scripts/pipeline/fetch_dgce.py`, `scripts/dolares/_dolar.py`,
`scripts/dolares/fetch_dolarito_historico.py`, `scripts/tickets/screener/cedear_ratios.py`,
`scripts/tickets/screener/jpm_adr.py` (`verify=False` → `verify=VERIFY`, default fail-closed
`REQUESTS_VERIFY=1`; se eliminan `urllib3.disable_warnings()`), `run_update.py` (solo se quita el
silenciamiento global). `engine/` no tenía bypass (evidencia F0) → sin cambios.
Auditoría completa con handshake TLSv1.3 de los 10 endpoints en
`22_F10_SECURITY_TLS_ENDPOINT_AUDIT.md`: todos los certificados válidos (2026–2027), el fix no
rompe la operación. Exploratorios one-shot documentados, no tocados.

### Auth/CORS API (gap 2 → ADDRESSED)
`api/main.py`:
- **Autenticación obligatoria** en TODOS los endpoints vía dependency global `require_key`
  (header `X-API-Key`, comparación constante en tiempo). **Fail-closed**: sin `API_KEY`
  configurada → 503 `api_key_not_configured`; clave ausente/incorrecta → 401.
- **CORS con lista blanca** `API_CORS_ORIGINS` (coma separada; guardar `*`= cualquiera SIN
  credenciales; vacío = mismo-origen). Se elimina `allow_origins=["*"]+credentials` y el eco
  arbitrario del `Origin` en los handlers de error.
- **Sin leakage de detalles en 500**: la respuesta ya no incluye `tipo`/`detalle` de la excepción
  (se loguea completo server-side).
- Health reporta `auth: required|not_configured`.
- Despliegue documentado en `docs/DEPLOY.md` §6 y `.env.example` (`API_KEY`, `API_CORS_ORIGINS`).

## Tests

- `tests/test_api_security.py` (nuevo, 9/9 PASS): 503 sin API_KEY · 401 sin/incorrecta · 200 con
  clave (health + jobs) · POST escribe requiere clave · preflight CORS origen permitido/no
  permitido · 500 sin leak. Read-only.
- `tests/test_f9_state_reconciliation.py` (previo, 6/6 PASS): intacto.
- Live: fetch dolarapi/criptoya con TLS verificado OK (solo lectura).

## Regresión y perímetro

La suite completa del árbol WIP tiene fallos preexistentes/flaky AJENOS a F10 security:
- **Familia CNV/identidad** (f038, f040, f041, cnv_authority, cnv_identity_link): stale de
  fixtures tras autoridad identity (autodeclarado en F6).
- **Familia ratio-engine / r2-deploy / runbook/docgen**: dependen del estado de archivos del
  árbol WIP y de la DB DEV (documentado: con mis cambios cuentan 30 fallos en esos módulos; sin
  mis cambios, 37 — el árbol no tiene baseline limpio).
Ninguno de los 42 fallos de la corrida completa importa ni ejercita los 10 archivos tocados
(verificado por grep de imports). Ninguna escritura sobre DB productiva; DEV solo con `-q`.

## Estado

| Gap F9 | SEVERIDAD | ESTADO |
|---|---|---|
| 1 · TLS `verify=False` en fuentes productivas | BLOCKER | **ADDRESSED** (fail-closed) |
| 2 · auth/CORS API | BLOCKER | **ADDRESSED** (API_KEY + allowlist) |
| 11 · estado terminal de etapa | HIGH | ADDRESSED (fase hermana 22_F10_STATE_MACHINE) |
| 3 · cron-VPS · 4 · runtime legacy · 5 · S03 · 6–10 | — | pendientes (no son blockers de esta fase) |

Paso siguiente recomendado (según prioridad F9): cron-VPS + runtime (3 y 4), que habilita la
operación productiva; luego S03 (5). Falta en producción real: **setear `API_KEY`/`API_CORS_ORIGINS`
en el `.env` de la VPS** y rotarla periódicamente.

STEP_22 = SECURITY_BLOCKERS
NEXT = CRON_VPS_AND_RUNTIME