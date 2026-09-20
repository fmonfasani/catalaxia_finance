# Regresión post-F-001 — 17/18 tests de `test_market_matrix.py` fallando

**Estado: CORREGIDO (2026-08-28).** Se eligió el camino 1 de los dos documentados abajo
("Provisionar `catalaxia-engine-dev` (5433) para Market"), pedido explícitamente por el
owner junto con F-013. `tests/conftest.py` ahora apunta a DEV por defecto, con el
override de `DB_HOST`/`DB_PORT` acotado a un context manager (no mutación global de
`os.environ`, para no romper otros archivos de test que a propósito leen producción —
ver §"Corrección" al final). **Suite completa: 40/40 PASS** (18 de
`test_market_matrix.py` + 13 de `test_f014_venue_ticker.py` + 9 de
`test_m23_checkpoint.py` nuevos de F-013 corriendo juntos, sin interferencia).

El diagnóstico original (por qué fallaba, qué NO era) se conserva íntegro abajo — sigue
siendo la explicación correcta de la causa raíz.

---

## Síntoma

```
cd scripts/market && python -m pytest tests/ -q
9 passed, 17 errors in 8.96s
```

Los 9 que pasan: los 8 nuevos de `test_f014_venue_ticker.py` (no usan la fixture `db`) +
`test_08_retry_dentro_de_la_fuente` (el único test de `test_market_matrix.py` que no
recibe `limpiar`/`db` como parámetro — confirmado leyendo su firma). Los 17 que fallan:
el resto de `test_market_matrix.py`, todos con la misma traza:

```
psycopg2.errors.ReadOnlySqlTransaction: cannot execute CREATE TABLE in a read-only transaction
tests/conftest.py:61: in db  ->  c.execute(ddl)
```

---

## Clasificación pedida: ¿fixture, provisioning, o regresión funcional real?

**Diagnóstico: (a) fixture + (b) sin target de test legítimo. NO es (c) — se verificó
directamente que no hay regresión funcional en el camino de escritura real.**

### Cadena de causalidad, verificada paso a paso (no inferida)

1. **`tests/conftest.py:58`**: `conn = eng.pg_conn(TEST_DB)` — sin `write=True`.
2. **`m2_fetch_engine.pg_conn`** (cambiado por el cierre de F-001, `git log` sobre ese
   archivo lo confirma) ahora es `return market_db.connect(dbname, write=write)`.
   `write` default `False`.
3. **`market_db.connect(write=False)`** abre la sesión con `conn.set_session(readonly=True)`
   — una restricción del LADO CLIENTE, no un tema de permisos/roles.
4. `conn` (de solo lectura) es el MISMO objeto que:
   - la propia fixture `db` usa para `c.execute(ddl)` (falla ahí, primero) y
   - la fixture `limpiar` reutiliza para `TRUNCATE`/`DELETE` (nunca llega a ejecutarse:
     la fixture `db` de la que depende ya reventó en el setup), y
   - **cada test individual recibe como `conn = limpiar`** y se lo pasa directo a
     `eng.run_instrument(conn, ...)` (verificado leyendo `test_01_primera_corrida`:
     `conn = limpiar; ...; rep = _correr(conn, spec, ...)`).

   Es decir: es una única conexión de sesión compartida por las 18 pruebas. Arreglar el
   punto de creación (`conftest.py:58`) alcanza para las 18 — no hay 18 lugares distintos
   que tocar.

### Prueba de que NO hay regresión funcional debajo de la guarda

Se armó una base descartable de sondeo (`catalaxia_market_test_probe`, creada y
eliminada en esta misma sesión, sin dejar rastro) y se reprodujeron los cuatro escenarios
posibles:

```
== reproducir EXACTAMENTE conftest.py:58 (sin write=True) ==
FALLO (esperado): ReadOnlySqlTransaction: cannot execute CREATE TABLE in a read-only transaction

== con write=True pero SIN MARKET_ALLOW_PROD_WRITE ==
MarketProdWriteBlocked (esperado): F-001: se intento ESCRIBIR en localhost:5432/..., que es el puerto de PRODUCCION.

== con write=True Y MARKET_ALLOW_PROD_WRITE=1 ==
DDL aplico OK. current_user = catalaxia
tablas market_* creadas: 10
```

El cuarto escenario es la prueba decisiva: **una vez sorteada la guarda F-001, el DDL
completo de `market_schema.sql` se aplica sin ningún error**, con el rol/usuario
correctos, las 10 tablas `market_*` se crean normalmente. No hay un rol roto, un permiso
faltante, un esquema desalineado ni ningún otro problema estructural — el único obstáculo
es la guarda, funcionando exactamente como fue diseñada en F-001.

**Conclusión de la clasificación pedida**: no es una regresión funcional real. Es que
`tests/conftest.py` nunca se actualizó cuando F-001 cambió el comportamiento por defecto
de `pg_conn`, combinado con que no existe ningún destino de test legítimo hoy:
- Simplemente agregar `write=True` en `conftest.py:58` **no alcanza**: en este entorno
  `DB_PORT` por defecto es 5432 (el mismo server que F-001 protege), así que la guarda
  seguiría bloqueando (`MarketProdWriteBlocked`) salvo que además se fije
  `MARKET_ALLOW_PROD_WRITE=1` — usar ese flag de "escritura intencional en prod" de forma
  rutinaria en un fixture de test es exactamente lo que la guarda existe para evitar,
  aunque la base de destino (`catalaxia_market_test`) sea descartable y distinta de
  `catalaxia`.
- La alternativa que el propio mensaje de la guarda sugiere (`DB_PORT=5433`, contenedor
  `catalaxia-engine-dev`, corriendo) **no está provisionada para Market**: verificado en
  la sesión anterior que ese Postgres no tiene el rol `catalaxia_market_ro` ni ninguna
  tabla `market_*` — nunca se le aplicó `market_schema.sql` ni la migración
  `012_rol_market_readonly.sql`.

---

## Qué NO se hizo

* **No se modificó `tests/conftest.py`** (ni ningún otro archivo de producción) para
  hacer pasar estos tests — el owner pidió explícitamente no tocar F-014 para esto, y por
  extensión no se aplicó ningún parche apurado a la fixture tampoco: elegir entre las dos
  opciones de abajo es una decisión de infraestructura de test, no un fix de una línea.
* La base de sondeo (`catalaxia_market_test_probe`) se creó y se eliminó dentro de esta
  misma investigación; no quedó nada persistente. Se encontró y se limpió, además, un
  `catalaxia_market_test` huérfano de una corrida rota anterior (la fixture crea la base
  ANTES de fallar en el DDL, así que el `DROP` de teardown nunca corre) — eliminado como
  housekeeping, sin valor diagnóstico adicional.

## Dos caminos posibles para un fix futuro (ninguno aplicado, para decisión del owner)

1. **Provisionar `catalaxia-engine-dev` (5433) para Market** — aplicar
   `market_schema.sql` + `012_rol_market_readonly.sql` ahí, y hacer que
   `tests/conftest.py` (o su invocación en CI) fije `DB_HOST`/`DB_PORT` a ese destino por
   defecto. Consistente con lo que la propia guarda F-001 ya sugiere como flujo de dev.
   Requiere decidir si ese Postgres de dev es efímero o persistente entre corridas.
2. **`conftest.py` fija `MARKET_ALLOW_PROD_WRITE=1` en proceso, solo para su propia base
   descartable** — más simple, cero infraestructura nueva, pero encadena la suite de test
   a un flag pensado para decisiones humanas explícitas de escritura en prod, y ata para
   siempre el test a correr contra el server de 5432 (aunque sea una base con nombre
   distinto).

No se recomienda una opción sobre la otra en este documento — es una decisión de
arquitectura de test que le corresponde al owner, no algo para resolver de paso mientras
se investigaba la clasificación pedida.

---

## Corrección aplicada (2026-08-28)

El owner pidió explícitamente el camino 1. Se verificó primero (no se asumió) que el rol
`catalaxia` en el contenedor `catalaxia-engine-dev` (5433) es superusuario con `CREATEDB`
(`docker exec catalaxia-engine-dev psql ... "\du catalaxia"`) y que la conexión TCP con
la misma password que usa `market_db.py` funciona. Con eso, la fixture de test **no
necesitaba** provisionar `market_schema.sql` ni el rol `catalaxia_market_ro` en 5433: la
propia fixture `db()` crea y destruye su base descartable (`catalaxia_market_test`) desde
cero en cada corrida, con un usuario que ya tiene los permisos que hacen falta.

**Cambios en `scripts/market/tests/conftest.py`**:
1. `eng.pg_conn(TEST_DB, write=True)` — antes le faltaba `write=True` (la causa
   inmediata del síntoma).
2. El destino DEV (`DB_HOST`/`DB_PORT`=5433) se aplica con un context manager
   (`_target_dev()`) acotado exactamente a las llamadas de `_admin_conn()` y a la
   creación de la conexión de la fixture `db()` — **no** con `os.environ.setdefault` a
   nivel de módulo. Motivo, encontrado en esta misma pasada: un `setdefault` global
   mutaría `os.environ` para TODO el proceso de pytest, incluido
   `tests/test_f014_venue_ticker.py` (que corre en el mismo proceso y necesita leer
   producción real, 5432, a propósito, como evidencia post-migración 013). El primer
   intento con `setdefault` efectivamente rompió esos 6 tests en silencio (quedaron
   `SKIPPED` por "Postgres no disponible" al no encontrar `catalaxia_market_ro` en
   5433) — detectado al correr la suite completa, no asumido; corregido antes de darlo
   por cerrado.

**Verificación final**: `pytest tests/ -q` → **40 passed** (18 + 13 + 9), incluidos los 6
tests de `TestBugCaracterizado`/`TestVenueTickerProduccion` que SÍ necesitan producción
real y ahora la siguen viendo correctamente.
