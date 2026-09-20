# PARTE II — PREPARACIÓN DEL ENTORNO

Doce pasos. Se ejecutan **en orden**. Si un paso no da el resultado esperado,
**no sigas**: el siguiente asume que el anterior salió bien.

Todos los comandos se ejecutan **desde la raíz del repositorio**.

Cada comando de este capítulo fue ejecutado y su salida verificada. Donde el
repositorio **no** permite reproducir un paso desde cero, dice
`BLOCKER — NO REPRODUCIBLE ACTUALMENTE` y explica exactamente qué falta. No hay
comandos inventados: si no está acá, no existe.

> **Lo que vas a encontrar antes de terminar.** Dos pasos —el 4 y el 5— están
> bloqueados. Se puede operar el sistema igual, porque el entorno ya está
> montado en esta máquina; lo que **no** se puede hoy es levantarlo de cero en
> una máquina limpia siguiendo sólo el repositorio. Está dicho en el lugar donde
> te lo vas a encontrar, no al final.

---

## Paso 1 — Requisitos

**OBJETIVO**
Saber qué tiene que estar instalado antes de tocar el repositorio.

**PREREQUISITOS**
Ninguno.

**COMANDO**
```bash
git --version
python --version
docker --version
docker compose version
```

**QUÉ HACE**
Comprueba que las cuatro herramientas existan y estén en el `PATH`.

**RESULTADO ESPERADO**
Las cuatro responden con una versión. Versiones verificadas en el entorno de
referencia:

| herramienta | mínimo | verificado |
|---|---|---|
| Git | cualquiera con `clone` | — |
| Python | **3.11** | 3.11.9 |
| Docker | con `docker exec` y `docker inspect` | 29.6.1 |
| Docker Compose | v2+ | v5.3.0 |

No hace falta cliente `psql` local: todo el acceso a PostgreSQL va por
`docker exec`.

**VERIFICACIÓN**
```bash
python -c "import sys; assert sys.version_info >= (3, 11), sys.version; print('python OK', sys.version.split()[0])"
```
Imprime `python OK 3.11.x` o superior.

**SI FALLA**
- `python: command not found` o versión < 3.11 → instalá Python 3.11+ y volvé a
  abrir la terminal. En Windows, verificá que el instalador haya marcado *Add
  Python to PATH*.
- `docker: command not found` → instalá Docker Desktop y arrancalo.
- `docker compose version` falla pero `docker-compose --version` funciona → tenés
  Compose v1. Los comandos de este manual usan la forma `docker compose`
  (con espacio).

---

## Paso 2 — Git: obtener el repositorio

**OBJETIVO**
Tener el código en la máquina.

**PREREQUISITOS**
Paso 1.

**COMANDO**
```bash
git clone https://github.com/fmonfasani/catalaxia_finance.git
cd catalaxia_finance
```

**QUÉ HACE**
Clona el repositorio y entra en él. Todos los comandos de este manual salen de
ese directorio.

**RESULTADO ESPERADO**
El directorio existe y contiene `engine/`, `scripts/`, `migrations/`, `docs/`.

**VERIFICACIÓN**
```bash
git remote -v
ls engine/config.py migrations/engine/ scripts/engine/s00_smoke.py
```
El remoto es `https://github.com/fmonfasani/catalaxia_finance.git` y los tres
paths existen.

**SI FALLA**
- `Permission denied` o pide credenciales → el repositorio es privado; pedí
  acceso o usá un token.
- `fatal: destination path already exists` → ya lo tenés clonado; entrá y hacé
  `git pull`.

> **`DECISION_REQUIRED`** — hay una segunda rama que este manual **no** cubre en
> esta parte. El adaptador canónico de CNV, `econ_key`, `measurement_date`, el
> Financial Model y la homologación TIKR viven en un *worktree* aparte
> (`catalaxia-cnvmig`, rama `feat/cnv-canonical`) que **no está mergeado**. Con
> el clone de este paso tenés el pipeline SEC completo y el CNV legacy; no tenés
> esos cinco. Ver `MANUAL_SCOPE.md` §0 y la decisión D-1.

---

## Paso 3 — Python: entorno virtual

**OBJETIVO**
Aislar las dependencias del proyecto de las del sistema.

**PREREQUISITOS**
Pasos 1 y 2.

**COMANDO**
```bash
python -m venv .venv
# Linux / macOS / Git Bash:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
```

**QUÉ HACE**
Crea un entorno virtual en `.venv/` y lo activa.

**RESULTADO ESPERADO**
El prompt muestra `(.venv)` y `python` apunta al intérprete del entorno.

**VERIFICACIÓN**
```bash
python -c "import sys; print(sys.prefix)"
```
La ruta termina en `.venv`.

**SI FALLA**
- En PowerShell, `Activate.ps1` bloqueado por política → ejecutá
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` en esa terminal.
- `No module named venv` → en Debian/Ubuntu instalá `python3-venv`.

**`KNOWN_LIMITATION`** — `.gitignore` ignora `.env` y `__pycache__/` pero **no
menciona `.venv/`** (verificado). Si creás el entorno virtual dentro del repo,
agregalo a `.gitignore` o quedará como archivos sin trackear. Tampoco hay
`Makefile` ni script que automatice este paso: es manual.

---

## Paso 4 — Dependencias

**OBJETIVO**
Instalar las librerías que el pipeline necesita para correr.

**PREREQUISITOS**
Paso 3, con el entorno activado.

**COMANDO**

### `BLOCKER — NO REPRODUCIBLE ACTUALMENTE`

**No hay un comando canónico, porque el repositorio no declara las dependencias
del engine.**

`requirements.txt` tiene exactamente tres líneas, y son del **servicio API**, no
del pipeline:

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
psycopg2-binary==2.9.9
```

El engine importa además siete paquetes que **no están declarados en ningún
archivo del repositorio**. Verificado en el entorno de referencia:

| paquete | para qué | versión verificada |
|---|---|---|
| `sqlalchemy` | toda la capa de base de datos | 2.0.48 |
| `psycopg2` | driver PostgreSQL (sí está, vía `psycopg2-binary`) | 2.9.11 |
| `lxml` | parser XBRL/HTML | 6.1.1 |
| `requests` | descargas SEC y CNV | 2.32.5 |
| `openpyxl` | lectura y escritura de `.xlsx` | 3.1.0 |
| `yfinance` | precios de mercado | 1.3.0 |
| `pytest` | la suite de tests | 9.1.0 |

**Qué falta para desbloquearlo:** un `requirements.txt` (o un
`pyproject.toml`) que declare las dependencias del engine con sus versiones.
Arreglarlo está fuera del alcance de este manual.

**Qué podés hacer mientras tanto**, sabiendo que esta lista sale de una
instalación observada y **no** de una declaración del repositorio:

```bash
pip install -r requirements.txt
pip install sqlalchemy lxml requests openpyxl yfinance pytest
```

**QUÉ HACE**
La primera línea instala las tres dependencias del servicio API que sí están
declaradas. La segunda agrega, sin fijar versión, los seis paquetes que el
engine importa y el repositorio no menciona.

**RESULTADO ESPERADO**
`pip` termina sin error y los siete paquetes quedan importables. **No hay
versiones garantizadas**: si mañana una de esas librerías rompe compatibilidad,
nada en el repositorio lo impide. Ése es el costo real del `BLOCKER`.

**VERIFICACIÓN**
```bash
python - <<'EOF'
import importlib.util
faltan = [m for m in ("sqlalchemy", "psycopg2", "lxml", "requests",
                      "openpyxl", "yfinance", "pytest")
          if not importlib.util.find_spec(m)]
print("FALTAN:", faltan) if faltan else print("dependencias OK")
EOF
```

Con todo instalado imprime `dependencias OK` (verificado).

**SI FALLA**
- Falta alguno → instalalo con `pip install <paquete>`.
- `psycopg2` falla al compilar → usá `psycopg2-binary`, que es lo que declara
  `requirements.txt`.

---

## Paso 5 — Docker: los contenedores

**OBJETIVO**
Tener las dos instancias de PostgreSQL corriendo.

**PREREQUISITOS**
Paso 1, con Docker arrancado.

**COMANDO**
```bash
docker ps --format "{{.Names}}\t{{.Ports}}"
```

**QUÉ HACE**
Lista los contenedores en ejecución con sus puertos publicados.

**RESULTADO ESPERADO**
Los dos, con estos mapeos exactos:

```
catalaxia-engine-dev    127.0.0.1:5433->5432/tcp
catalaxia-db            127.0.0.1:5432->5432/tcp
```

Los dos corren `postgres:16`.

**VERIFICACIÓN**
```bash
docker inspect catalaxia-engine-dev --format '{{.Config.Image}} {{json .HostConfig.PortBindings}}'
docker inspect catalaxia-db          --format '{{.Config.Image}} {{json .HostConfig.PortBindings}}'
```

**SI FALLA**

*Falta `catalaxia-db`:*
```bash
docker compose up -d db
```
`docker-compose.yml` **sí** declara ese contenedor.

*Falta `catalaxia-engine-dev`:*

### `BLOCKER — NO REPRODUCIBLE ACTUALMENTE`

**`docker-compose.yml` no declara `catalaxia-engine-dev`.** Declara cuatro
contenedores —`catalaxia-db`, `catalaxia-pipeline`, `catalaxia-api` y
`catalaxia-nginx`— y ninguno es la base de desarrollo del puerto 5433, que es
**contra la que corren todos los comandos de este manual**.

Lo que se sabe del contenedor que hoy está corriendo, obtenido con
`docker inspect`:

| propiedad | valor observado |
|---|---|
| imagen | `postgres:16` (server 16.14) |
| puerto | `127.0.0.1:5433` → `5432/tcp` |
| `POSTGRES_DB` | `catalaxia` |
| `POSTGRES_USER` | `catalaxia` |
| `POSTGRES_PASSWORD` | el mismo valor que `POSTGRES_PASSWORD` en `.env` |
| volumen | **anónimo** (identificador generado, sin nombre) |
| política de reinicio | `no` |

El volumen anónimo y la ausencia en el compose indican que se creó a mano con
`docker run`. **El comando exacto que se usó no está registrado en el
repositorio**, así que no lo transcribo: sería inventarlo.

**Qué falta para desbloquearlo:** agregar el servicio al `docker-compose.yml`,
con volumen nombrado. Fuera del alcance de este manual.

**Consecuencia si sos un operador nuevo:** podés operar sobre un entorno ya
montado, pero no podés crearlo desde cero siguiendo el repositorio.

---

## Paso 6 — PostgreSQL: usuarios y privilegios

**OBJETIVO**
Entender con qué identidad se conecta el pipeline y por qué no es superusuario.

**PREREQUISITOS**
Paso 5.

**COMANDO**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT rolname, rolsuper FROM pg_roles \
   WHERE rolname IN ('catalaxia','catalaxia_engine','catalaxia_market_ro') ORDER BY 1"
```

**QUÉ HACE**
Lista los tres roles del engine y si son superusuario.

**RESULTADO ESPERADO**
```
catalaxia|t
catalaxia_engine|f
catalaxia_market_ro|f
```

Los tres existen y **sólo `catalaxia` es superusuario**. La separación la crea
la migración `011_rol_engine_sin_superuser.sql` y no es cosmética:

| rol | quién lo usa | por qué |
|---|---|---|
| `catalaxia` | **sólo** migraciones y arnés de tests | necesita DDL |
| `catalaxia_engine` | **la aplicación** | `NOSUPERUSER`, sin `DELETE`, sin `TRUNCATE` |
| `catalaxia_market_ro` | lectura de `market_*` | sólo lectura |

El motivo, tal como lo declara la migración: las garantías de inmutabilidad y de
no-borrado son **triggers**, y un superusuario los desactiva con
`SET session_replication_role = replica`. Si el engine se conectara como
superusuario, todo lo certificado sería revocable por accidente.

**VERIFICACIÓN**
```bash
python -c "from engine.config import load_settings; print(load_settings().db_user)"
```
Imprime `catalaxia_engine`. Si imprime `catalaxia`, alguien puso
`ENGINE_DB_USER` y el pipeline está corriendo con privilegios que no le
corresponden.

**SI FALLA**

*El rol `catalaxia_engine` no existe:* aplicá las migraciones (Paso 12 lo cubre) — la 011 lo crea.

*`password authentication failed for user "catalaxia_engine"`:*

**`KNOWN_LIMITATION`** — la migración 011 crea el rol pero **no** le asigna
contraseña; lo dice explícitamente: *«la password se asigna aparte, fuera del
control de versiones»*. La convención implícita —no documentada en ningún
lado antes de este manual— es que sea **la misma que `POSTGRES_PASSWORD`**,
porque `engine/config.py` usa ese valor como default de
`ENGINE_DB_PASSWORD`. Para asignarla:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "ALTER ROLE catalaxia_engine WITH LOGIN PASSWORD '<la misma que POSTGRES_PASSWORD>'"
```

---

## Paso 7 — Bases disponibles

**OBJETIVO**
Saber qué bases hay en el puerto 5433 y cuál usar. **Elegir mal la base es el
error más caro de este manual**, porque los comandos no avisan.

**PREREQUISITOS**
Paso 5.

**COMANDO**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d postgres -tAc \
  "SELECT datname, pg_size_pretty(pg_database_size(datname)) \
     FROM pg_database WHERE datname NOT IN ('template0','template1','postgres') ORDER BY 1"
```

**QUÉ HACE**
Lista las bases del contenedor de desarrollo con su tamaño.

**RESULTADO ESPERADO**
En el entorno de referencia hay ocho. Contenido verificado contando
`derived.fact`:

| base | tamaño | `derived.fact` | qué es |
|---|---:|---:|---|
| **`catalaxia`** | 4.467 MB | 133.902 | **la base de trabajo del engine.** Es el default de `ENGINE_DB_NAME` |
| `cnvmig` | 4.623 MB | 136.777 | migración canónica de CNV (worktree) |
| `metrgolden` | 4.623 MB | 136.697 | fixture del Golden Run de METR |
| `metrsem` | 4.624 MB | 138.398 | fixture de semántica CNV |
| `dbgcopy` | 4.272 MB | 88.789 | copia de depuración |
| `e2e_final` | 281 MB | 47.930 | fixture E2E |
| `metr5y` | 17 MB | 4.648 | demo METR 5 ejercicios |
| `f051_check` | 10 MB | 0 | fixture de verificación puntual |

**VERIFICACIÓN**
Antes de cualquier comando, comprobá contra cuál vas a correr:
```bash
python -c "from engine.config import load_settings; print(load_settings().describe())"
```

**SI FALLA**
- La base que esperás no está → o el contenedor es otro, o hay que crearla:
  ```bash
  docker exec catalaxia-engine-dev psql -U catalaxia -d postgres -c \
    "CREATE DATABASE <nombre> OWNER catalaxia"
  ```
  Una base recién creada **no tiene esquema**: hay que aplicarle las migraciones
  (Paso 12).

**`KNOWN_LIMITATION`** — seis de las ocho bases son fixtures de sprints
anteriores y no están documentadas fuera de esta tabla. Un operador nuevo no
tiene forma de saber cuál está viva salvo preguntando. **Ante la duda, usá
`catalaxia`.**

---

## Paso 8 — Puertos

**OBJETIVO**
Fijar cuál es el puerto de trabajo y cuál el intocable.

**PREREQUISITOS**
Paso 5.

**COMANDO**
```bash
docker ps --filter "name=catalaxia" --format "{{.Names}}\t{{.Ports}}"
```

**QUÉ HACE**
Muestra el mapeo de puertos de los dos contenedores.

**RESULTADO ESPERADO**

| puerto | contenedor | qué es | se escribe |
|---|---|---|---|
| **5433** | `catalaxia-engine-dev` | desarrollo, fixtures, todo el trabajo | **sí** |
| **5432** | `catalaxia-db` | **PRODUCCIÓN** | **nunca** |

Los dos exponen `5432/tcp` **dentro** del contenedor; lo que cambia es el puerto
del host. Por eso `docker exec ... psql` no lleva `-p`: adentro siempre es 5432.
El puerto del host sólo importa cuando la conexión viene de Python.

**VERIFICACIÓN**
```bash
python -c "from engine.config import load_settings; s=load_settings(); print(s.db_port, 'prod' if s.is_prod else 'dev')"
```
Tiene que imprimir `5433 dev`.

**SI FALLA**
Si imprime `5432 prod`, no llegaste hasta acá: `load_settings()` levanta
`RuntimeError` antes (Paso 11).

---

## Paso 9 — Variables de entorno

**OBJETIVO**
Saber qué variables gobiernan el destino y de dónde salen.

**PREREQUISITOS**
Paso 2.

**COMANDO**
```bash
python -c "from engine.config import load_settings; print(load_settings().describe())"
```

**QUÉ HACE**
Resuelve la configuración y la imprime. Es la forma canónica de responder
*«¿contra qué estoy corriendo?»*.

**RESULTADO ESPERADO**
```
catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False
```

**De dónde salen los valores.** `engine/config.py` combina el archivo `.env` de
la raíz con el entorno del proceso, y **el entorno del proceso gana**. Las diez
variables, con sus defaults reales:

| variable | default | qué hace |
|---|---|---|
| `ENGINE_DB_HOST` | `127.0.0.1` | host |
| `ENGINE_DB_PORT` | `5433` | **`5432` dispara EXT-010** |
| `ENGINE_DB_NAME` | `catalaxia` | base |
| `ENGINE_DB_USER` | `catalaxia_engine` | usuario de aplicación, **no** superusuario |
| `ENGINE_DB_PASSWORD` | el valor de `POSTGRES_PASSWORD` | contraseña |
| `ENGINE_ADMIN_DB_USER` | `catalaxia` | usuario para DDL y migraciones |
| `ENGINE_ADMIN_DB_PASSWORD` | el valor de `POSTGRES_PASSWORD` | |
| `ENGINE_MODE` | `FAST` | sólo `FAST`, `FULL`, `AUDIT`; otro valor ⇒ `ValueError` |
| `ENGINE_ALLOW_PROD` | `0` | `1` desactiva el guard de producción. **No usar** |
| `ENGINE_STATEMENT_TIMEOUT_MS` | `120000` | timeout de sentencia |

**No hace falta exportar la contraseña.** Sale de `.env`. Ese archivo **no está
versionado** y en el entorno de referencia contiene dos claves:
`POSTGRES_PASSWORD` y `DOLARITO_AUTH_CLIENT` (esta última sólo para la serie
histórica de dólar; la CNV no requiere autenticación).

Si `.env` no existe —instalación nueva— crealo en la raíz con al menos:
```
POSTGRES_PASSWORD=<la contraseña del contenedor catalaxia-engine-dev>
```

**Costumbre recomendada:** poner el destino explícito en cada comando, aunque
coincida con el default.
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
```

**VERIFICACIÓN**
El comando de arriba imprime la línea esperada, sin excepción.

**SI FALLA**
- `password authentication failed` → falta `.env` o la contraseña no coincide
  con la del contenedor. **El mensaje no menciona el `.env`**: hay que saberlo.
- `ENGINE_MODE invalido: X` → los únicos valores son `FAST`, `FULL`, `AUDIT`.
- `RuntimeError: EXT-010` → apuntaste a producción. Paso 11.

---

## Paso 10 — La diferencia entre 5432 y 5433

**OBJETIVO**
Que quede claro por qué un número decide si el sistema es seguro o no.

**PREREQUISITOS**
Pasos 8 y 9.

**COMANDO**
```bash
docker exec catalaxia-db          psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',' ORDER BY nspname) FROM pg_namespace \
    WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"

docker exec catalaxia-engine-dev  psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',' ORDER BY nspname) FROM pg_namespace \
    WHERE nspname IN ('engine','identity_v1','identity','fetch_raw','parsed','derived')"
```

**QUÉ HACE**
Muestra los esquemas de las dos instancias, lado a lado.

**RESULTADO ESPERADO**

| | 5432 · `catalaxia-db` | 5433 · `catalaxia-engine-dev` |
|---|---|---|
| esquemas | **`public` y nada más** | `derived,engine,fetch_raw,identity,identity_v1,parsed` |
| rol | producción | desarrollo |
| lo escribe | el deploy | vos |

La diferencia operativa: **producción no tiene `parsed` ni `derived`**. Si algún
día los tuviera, algo escribió donde no debía, y eso es un incidente.

**VERIFICACIÓN**
La primera consulta devuelve exactamente `public`.

**SI FALLA**
Si producción devuelve algo más que `public`, **pará todo**. Es un incidente:
`docs/runbooks/appendices/RECOVERY_PROCEDURES.md`, caso 20.

---

## Paso 11 — Protección de producción

**OBJETIVO**
Comprobar que el guard existe y funciona, en vez de confiar en que sí.

**PREREQUISITOS**
Paso 9.

**COMANDO**
```bash
ENGINE_DB_PORT=5432 python -c "
from engine.config import load_settings
try:
    print('NO BLOQUEO:', load_settings().describe())
except RuntimeError as e:
    print('BLOQUEADO:', e)
"
```

**QUÉ HACE**
Fuerza a propósito el puerto de producción y comprueba que el sistema se niegue.
Es una prueba **segura**: no abre ninguna conexión — falla al construir la
configuración, antes de tocar la red.

**RESULTADO ESPERADO**
```
BLOQUEADO: EXT-010: el engine apunta al puerto de produccion (5432). Usar
ENGINE_DB_PORT=5433 (dev) o ENGINE_ALLOW_PROD=1 explicito para modo AUDIT.
```

Cómo funciona: `Settings.is_prod` es, literalmente,
`self.db_port == "5432"`. Si es verdadero y `ENGINE_ALLOW_PROD` no vale `1`,
`load_settings()` levanta `RuntimeError`. **Ningún script llega a conectarse.**

**VERIFICACIÓN**
Que el mensaje empiece con `BLOQUEADO: EXT-010`.

**SI FALLA**

*Imprime `NO BLOQUEO`:* alguien dejó `ENGINE_ALLOW_PROD=1` en el entorno o en `.env`. Quitala:
```bash
unset ENGINE_ALLOW_PROD
grep -n "ENGINE_ALLOW_PROD" .env
```
**No sigas hasta que el guard vuelva a bloquear.**

**`KNOWN_LIMITATION`** — el guard protege el **engine de Python**. No protege
`docker exec ... psql` contra `catalaxia-db`, que escribe en producción sin
preguntar nada. Contra eso no hay barrera técnica: sólo la regla de no hacerlo.

---

## Paso 12 — Comprobación final del entorno

**OBJETIVO**
Cerrar la Parte II con una verificación que se pueda repetir siempre.

**PREREQUISITOS**
Pasos 1 a 11.

**COMANDO** — los cinco, en orden:
```bash
# 12.1 · contenedores
docker ps --format "{{.Names}}\t{{.Ports}}"

# 12.2 · destino del engine
python -c "from engine.config import load_settings; print(load_settings().describe())"

# 12.3 · esquemas de la base de trabajo
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',' ORDER BY nspname) FROM pg_namespace \
   WHERE nspname IN ('engine','identity_v1','identity','fetch_raw','parsed','derived')"

# 12.4 · producción intacta
docker exec catalaxia-db psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',') FROM pg_namespace \
   WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"

# 12.5 · huella de screener.db
stat -c '%y %s' data/screener.db
```

**QUÉ HACE**
Comprueba, en este orden: que los contenedores estén; contra qué base vas a
correr; que esa base tenga esquema; que producción siga limpia; y deja anotada
la huella del SQLite legacy para poder comparar al final.

**RESULTADO ESPERADO**

| # | esperado |
|---|---|
| 12.1 | `catalaxia-engine-dev 127.0.0.1:5433->5432/tcp` y `catalaxia-db 127.0.0.1:5432->5432/tcp` |
| 12.2 | `catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False` |
| 12.3 | `derived,engine,fetch_raw,identity,identity_v1,parsed` |
| 12.4 | **`public`** y nada más |
| 12.5 | una fecha y un tamaño — **anotalos** |

**GATE**
`PASS` si los cinco dan lo esperado. Cualquier desvío ⇒ **no avances a la Parte
III**.

**VERIFICACIÓN**
Los cinco comandos son de sólo lectura y se pueden repetir cuantas veces quieras.

**SI FALLA**
| # | síntoma | qué hacer |
|---|---|---|
| 12.1 | falta `catalaxia-db` | `docker compose up -d db` |
| 12.1 | falta `catalaxia-engine-dev` | Paso 5, `BLOCKER` |
| 12.2 | `password authentication failed` | Paso 9: falta `.env` |
| 12.2 | `prod=True` | Paso 11: sacá `ENGINE_ALLOW_PROD` |
| 12.3 | faltan esquemas | la base no tiene migraciones; ver abajo |
| 12.4 | algo más que `public` | **incidente**, Paso 10 |
| 12.5 | el archivo no existe | no bloquea la Parte II; sí bloquea el pipeline CNV legacy |

### Si falta el esquema: aplicar migraciones

```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python -c "
from engine.config import load_settings
from engine.db import get_admin_engine, apply_migrations
s = load_settings(); print(s.describe())
print('aplicadas:', len(apply_migrations(get_admin_engine(s))))
"
```

Sobre una base recién creada aplica **32** migraciones (verificado). Sobre una
que ya las tiene, imprime `aplicadas: 0` — la operación es idempotente. Usa el
usuario administrador (`catalaxia`), no el de aplicación.

---

### Nota sobre `s00_smoke.py`

El manual de referencia trata `S00_bootstrap` como la primera etapa del pipeline
SEC, y esa es la Parte III. Conviene saber esto antes de llegar:

**`s00_smoke.py` no se puede volver a correr sobre la misma base.** El script
inserta en `engine.checkpoints` sin `ON CONFLICT`, y hay un índice único sobre
`(stage_id, input_hash, code_version, contract_version)` donde `input_hash` es
el SHA-256 de `settings.describe()`. Como esa cadena es constante para una misma
base y modo, la segunda corrida siempre choca.

Verificado sobre una base creada para la prueba:

- **primera corrida** — `gate = PASS`, `rows_expected = 2`, `rows_parsed = 2`,
  `rows_rejected = 0`, exit `0`;
- **segunda corrida** — `psycopg2.errors.UniqueViolation: duplicate key value
  violates unique constraint "ux_checkpoints_reuse"`, exit **`1`**.

`KNOWN_LIMITATION`. Por eso la comprobación de entorno de este capítulo usa los
cinco comandos de sólo lectura del Paso 12 y **no** `s00_smoke.py`: hacía falta
una verificación repetible.

---

## Resumen de la Parte II

| paso | estado |
|---|---|
| 1 · Requisitos | ✅ reproducible |
| 2 · Git | ✅ reproducible |
| 3 · Python | ✅ reproducible |
| 4 · Dependencias | 🔴 **`BLOCKER`** — el repositorio no las declara |
| 5 · Docker | 🔴 **`BLOCKER`** — el compose no declara `catalaxia-engine-dev` |
| 6 · PostgreSQL | ⚠️ reproducible, con `KNOWN_LIMITATION` en la contraseña del rol |
| 7 · Bases | ⚠️ reproducible, con `KNOWN_LIMITATION` en 6 de 8 bases |
| 8 · Puertos | ✅ reproducible |
| 9 · Variables | ✅ reproducible |
| 10 · 5432 vs 5433 | ✅ reproducible |
| 11 · Guard de producción | ✅ reproducible y **verificado disparando** |
| 12 · Comprobación final | ✅ reproducible y repetible |

**Diez de doce pasos son reproducibles hoy.** Los dos bloqueados son ambos de
creación del entorno, no de operación: sobre un entorno ya montado se puede
trabajar; sobre una máquina limpia, no todavía.

---

*Los comandos de este capítulo fueron ejecutados y sus salidas verificadas. Las
versiones de paquetes provienen de una instalación observada, no de una
declaración del repositorio — que es exactamente el `BLOCKER` del Paso 4.
Ninguna operación de este capítulo escribe en producción; la única que escribe
en algún lado es la aplicación de migraciones, y sólo sobre la base de
desarrollo que elijas.*
