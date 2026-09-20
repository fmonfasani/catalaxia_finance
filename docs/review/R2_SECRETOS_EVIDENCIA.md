# R2 — Evidencia de Verificacion: CERO SECRETOS EN CODIGO

**Fecha de ejecucion:** 2026-09-06
**Ambiente:** Windows 11 / Python 3.11.9 / pytest 9.1.0 / PowerShell 5.1
**Nota:** el `git grep` de la compuerta corre sobre el arbol versionado (`git grep` solo ve archivos tracked).
**Alcance:** contrato R2 "CERO SECRETOS EN CODIGO" (deploy/sync/api/engine).

---

## 1. Que se implemento (resumen de cambios)

| Archivo | Cambio |
|---|---|
| `scripts/deploy/sincronizar_a_produccion.py` | IP `89.167.96.239` y usuario `root` hardcodeados reemplazados por `CATALAXIA_HOST` / `CATALAXIA_SSH_USER` obligatorias (`_requerida()` -> exit 2 sin default). |
| `deploy.py` | idem + URLs dinamicas via `CATALAXIA_API_URL` / `CATALAXIA_DASHBOARD_URL`. |
| `deploy_production.sh` | `CATALAXIA_SSH_TARGET` / `CATALAXIA_API_URL` / `CATALAXIA_DASHBOARD_URL` via `:?` (FAIL temprano). |
| `api/main.py` | `DB_PASSWORD` sin default silencioso (`"catalaxia"` -> `""`). |
| `.env.example` | variables nuevas documentadas (obligatorias + opcionales no sensibles). |
| `DEPLOY.md`, `EXTRACTION_KNOWLEDGE_BASE.md` | IP de produccion fuera de docs tracked. |

Tests nuevos:
- `tests/test_r2_secretos.py` (15 tests: estaticos + comportamiento por subprocess)
- `tests/test_runbook_operability.py` (22 tests de operabilidad de runbooks)

---

## 2. Resultado de la suite de tests

### 2.1 `tests/test_r2_secretos.py` — 15 pasados

Comando:
```
python -m pytest tests/test_r2_secretos.py -v
```

Resultado (salida real):

```
tests/test_r2_secretos.py::test_deploy_sin_ip_literal[path0] PASSED
tests/test_r2_secretos.py::test_deploy_sin_ip_literal[path1] PASSED
tests/test_r2_secretos.py::test_deploy_sin_ip_literal[path2] PASSED
tests/test_r2_secretos.py::test_deploy_sin_ip_literal[path3] PASSED
tests/test_r2_secretos.py::test_deploy_sin_user_at_ip[path0] PASSED
tests/test_r2_secretos.py::test_deploy_sin_user_at_ip[path1] PASSED
tests/test_r2_secretos.py::test_deploy_sin_user_at_ip[path2] PASSED
tests/test_r2_secretos.py::test_deploy_sin_user_at_ip[path3] PASSED
tests/test_r2_secretos.py::test_sin_default_silencioso_en_variables_sensibles[path0] PASSED
tests/test_r2_secretos.py::test_sin_default_silencioso_en_variables_sensibles[path1] PASSED
tests/test_r2_secretos.py::test_api_sin_password_default_silencioso PASSED
tests/test_r2_secretos.py::test_sincronizar_sin_env_falla_temprano PASSED
tests/test_r2_secretos.py::test_sincronizar_con_env_mantiene_flujo PASSED
tests/test_r2_secretos.py::test_deploy_py_sin_env_falla_temprano PASSED
tests/test_r2_secretos.py::test_deploy_py_instancia_lee_env PASSED

15 passed in 1.43s
```

### 2.2 `tests/test_runbook_operability.py` — 22 pasados

```
python -m pytest tests/test_runbook_operability.py -q
22 passed in 1.15s
```

Total verificado en esta pasada: **37 PASSED** (15 + 22).

---

## 3. Sintaxis (py_compile)

```
python -m py_compile deploy.py scripts/deploy/sincronizar_a_produccion.py api/main.py tests/test_r2_secretos.py
```
Resultado: `PY-COMPILE OK`.

---

## 4. Compuerta R2 (barrido `git grep` sobre tracked)

### Gate 1 — Sin IP de infraestructura en codigo de deploy
Comando:
```
git grep -n -E "([0-9]{1,3}\.){3}[0-9]{1,3}" -- api/ engine/ scripts/deploy/ deploy.py deploy.sh deploy_production.sh
```
Resultado: solo loopback `127.0.0.1` (defaults dev documentados y permitidos). **OK.**

### Gate 2 — IP de produccion fuera de tracked
```
git grep -n "89.167.96.239"
```
Resultado: **0 coincidencias**. **OK.**

### Gate 3 — Sin secretos/tokens en zonas del contrato
```
git grep -n -i -E 'DOLARITO_AUTH_CLIENT|secret|bearer|token|password\s?=' -- api/ scripts/deploy/ deploy.py deploy_production.sh deploy.sh docker-compose.yml engine/config.py
```
Resultado: solo falsos positivos benignos, ninguno es un secreto real:
- `api/main.py:13` — `DB_PASSWORD=***` (placeholder enmascarado en docstring)
- `api/main.py:96` — `os.environ.get("DB_PASSWORD", "")` (el fix R2: default vacio)
- `deploy.sh:13` — `POSTGRES_PASSWORD=tu_password_aqui` (placeholder instructivo)
- `engine/config.py:72,76` — defaults vacios que leen del entorno (fail-safe)
**OK.**

---

## 5. Como reproducir

Desde la raiz del repo:
```
python -m pytest tests/test_r2_secretos.py tests/test_runbook_operability.py -v
# y los 3 gates de git grep de la seccion 4
```

---

## 6. Lectura

- La implementacion declara **IMPLEMENTAR + VERIFICAR** R2.
- Este documento es la **evidencia de verificacion** (tests + gates), no una acta de certificacion firmada.
- Para declarar R2 **CERTIFICADO** hace falta: decision formal del owner + documento de cierre designado (acta), usando esta evidencia como insumo.