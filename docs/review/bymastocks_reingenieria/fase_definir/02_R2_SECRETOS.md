# CONTRATO R2 — CEROS SECRETOS EN CÓDIGO
Estado: **APPROVED → IMPLEMENTAR** · Origen: ficha P0-R2 · Evidencia verificada 2026-09-06.
Decisión OWNER: APROBADO. Quitar todo valor sensible de infraestructura. Config via variables de entorno.
Prod: variable ausente → FAIL temprano, sin defaults silenciosos.

## 1. OBJETIVO

Eliminar credenciales y valores de infraestructura (host/IP/usuario/URI) hardcodeados en código versionado.
La política ya existe en `.gitignore`: *"este repositorio es PUBLICO. Ningun token, clave ni contrasena va
escrito en el codigo"*. R2 la hace cumplir sobre los archivos identificados + barrido de otros scripts de deploy.

## 2. INVARIANTES (lo que NO puede pasar)

- INV1 — Ningún valor sensible aparece como literal en código **versionado** (ni como default de `os.environ.get`):
  IP/host, usuario de producción, credenciales, tokens, API keys, passwords.
- INV2 — Configuración de infraestructura se lee de variables de entorno / `.env` (`.env` ya ignorado).
- INV3 — En producción, variable obligatoria ausente → FAIL temprano. Sin default silencioso para valores sensibles.
- INV4 — `deploy.py` (hoy untracked) debe quedar limpio ANTES de incorporarse al repositorio.
- INV5 — **NO** se toca la rotación de infraestructura/credenciales en R2: es acción operativa separada y no bloquea R2.

## 3. ALCANCE EXACTO (evidencia)

| Archivo | Trackeado? | Líneas | Hallazgo |
|---|---|---|---|
| `deploy.py` | NO (untracked) | 26–29 | `server_host`, `server_user`, `api_url` hardcodeados + otros valores del bloque `Deploy` |
| `scripts/deploy/sincronizar_a_produccion.py` | **SÍ** | 63–67 | `HOST` default = IP real, `USER` default `"root"`, `CONT`/`PGUSER`/`PGDB` defaults |
| `scripts/deploy/sincronizar_a_produccion.py` | SÍ | 100 | `local.unlink` (copia SQLite temporal — ver R3 NO aplica, no es raw) |
| `deploy.sh` | untracked | por revisar | script de deploy sin revisión de secretos |

Nota: `sincronizar_a_produccion.py` está versionado → IP + usuario quedaron en historial. La **rotación** es
acción operativa separada y NO bloquea R2 (decisión owner). `deploy.py` no está versionado, pero debe quedar
limpio antes de su incorporación.

## 4. DISEÑO (para fase EXEC)

1. `deploy.py`: reemplazar literales por `os.environ.get("CATALAXIA_HOST")` etc., sin default sensible;
   fallar explícito si falta la variable.
2. `sincronizar_a_produccion.py`: quitar defaults sensibles (`HOST`, `USER`) → exigir env; dejar defaults solo para
   valores NO sensibles de entorno dev (documentar).
3. Barrido de `deploy.sh` y cualquier `*deploy*`, `*sync*`, `*upload*` bajo `scripts/` para literales IP/user/pass.
4. (Acción operativa separada, NO parte de este contrato) Rotación de IP/usuario si quedaron expuestos.
5. `.env.example` con claves comentadas sin valores reales.
6. Código de deploy: variable requerida ausente → raise con mensaje claro (FAIL temprano).

## 5. VERIFICACIÓN

- `git grep -nE '(passwor|token|secret|api_?key|= "[^"]*(root|admin))'` por archivo tracked → 0.
- Barrido IP: `git grep -nE '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'` sobre `scripts/`+raíz → 0 (o falsos positivos documentados).
- Importar/`--help` de `sincronizar_a_produccion.py` SIN env → falla temprana con mensaje; no ejecuta con default.
- `deploy.py` sin literales sensibles (sigue untracked, pero listo para incorporación).

## 6. GATES DE PASO (binarios)

- [ ] `git grep` de patrones credenciales/IP en tracked = 0 (o falsos positivos documentados).
- [ ] Código de deploy falla temprano si falta env requerido.
- [ ] `deploy.py` limpio antes de cualquier incorporación a git.
- [ ] Sin cambio de comportamiento funcional del deploy cuando las env están presentes.

## 7. CHECKLIST 10 PASOS (regla de seguridad)

| Paso | Estado |
|---|---|
| 1 dependencias | `deploy.py` (deployers), `sincronizar_a_produccion.py` (deployers) |
| 2 ownership | scripts/deploy (owner) |
| 3 duplicación semántica | N/A |
| 4 comportamiento | Sin secrets: falla temprano; R2 no cambia cálculos ni datos |
| 5 consumidores | Operadores de deploy/despliegue |
| 6 impacto | Bajo con `.env` poblado; alto si se rompe deploy (mitigado: staging primero) |
| 7 alternativa | Secret manager externo (futuro); ahora env + `.env` |
| 8 plan migración | Sección 4 |
| 9 verificación | Sección 5 |
| 10 certificación | Owner + deploy exitoso en staging antes de prod |

## 8. RIESGOS Y LÍMITES

- Riesgo: romper deploy si una variable deja de tener default → mitigado con mensaje explícito + deploy en staging.
- Límite: la **rotación** de credenciales es accion operativa separada, NO bloqueo de R2.
- Límite: R2 no cubre `.claude/worktrees` (si pegan código, revisar igual); barrido futuro.

## 9. DECISIÓN OWNER

| Decisión | Resultado |
|---|---|
| R2 | **APROBADO** |
| Quitar IP/host, usuario prod, credenciales, tokens, API keys, passwords, defaults sensibles | SÍ |
| Config via variables de entorno; prod ausente → FAIL temprano | SÍ |
| `deploy.py` limpio antes de incorporarse | SÍ |
| `sincronizar_a_produccion.py` limpiado | SÍ |
| Rotación de infraestructura/credenciales | Acción operativa separada — NO bloquea R2 |
| Fase | **APPROVED → IMPLEMENTAR** |