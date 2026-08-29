# CONTRATO — MECANISMO DE MIGRACIONES

**Fecha:** 2026-08-29 · **Motivo:** F-049 · **Escrito antes de modificar código.**
**Alcance:** exclusivamente el mecanismo de aplicación y registro. No toca ninguna
migración funcional, ni datos, ni tablas de negocio.

---

## Fase A — Las tres preguntas, con evidencia

### 1. ¿El runner `engine/db.py` es el mecanismo oficial? **Sí.**

**Cinco etapas del pipeline lo invocan al arrancar**, antes de hacer nada:

```
scripts/engine/s00_smoke.py:28        applied = edb.apply_migrations(engine)
scripts/engine/s01_identity.py:115    applied = edb.apply_migrations(engine)
scripts/engine/s02_fetch_ypf.py:206   applied = edb.apply_migrations(engine)
scripts/engine/s03_parse_ypf.py:344   applied = edb.apply_migrations(engine, settings=settings)
scripts/engine/c3_cnv_fetch.py:295    applied = edb.apply_migrations(engine)
```

No hay ningún otro camino invocado por el sistema. `apply_migrations` abre además su
propia conexión administrativa (F-025/F-027), porque aplicar DDL es administrativo por
definición.

### 2. ¿`psql -f` está oficialmente soportado? **No. Y además no funciona solo.**

Es la herramienta con la que se aplicaron a mano las migraciones durante el
desarrollo. **No es autosuficiente**, y está demostrado:

```
$ psql -d <base limpia> -f migrations/engine/008_identity_v1.sql
ERROR:  relation "engine.schema_migrations" does not exist
```

`engine.schema_migrations` **la crea el runner** (`engine/db.py:80`), no una
migración. Una migración auto-registrada aplicada suelta sobre una base limpia falla
en su última línea — justamente la del auto-registro.

O sea: el auto-registro existía para soportar un mecanismo que **nunca funcionó de
forma autónoma**.

### 3. ¿Quién debe registrar en `engine.schema_migrations`? **El runner, y sólo él.**

Es quien crea la tabla, quien decide qué está pendiente (`done`) y quien controla la
transacción. Que la migración también se registre duplica la responsabilidad sin
agregar capacidad.

---

## El patrón histórico ya decía esto

| migraciones | ¿se auto-registran? | cuándo se escribieron |
|---|---|---|
| `001`–`007` | **no** | diseño original, para el runner |
| `008`–`024` (16) | **sí** | ciclos de Identity V1, aplicadas a mano |
| `026`–`031` | **no** | ciclos recientes, siguiendo el patrón original |

**El diseño original y el más reciente coinciden: el runner es el único responsable.**
Las 16 del medio rompieron ese contrato, y el defecto quedó latente porque en la base
homologada ya estaban registradas y el runner las saltaba.

---

## Fase B — Las dos soluciones

### A) `INSERT … ON CONFLICT DO NOTHING` en el runner

| criterio | resultado |
|---|---|
| atomicidad | igual: una transacción |
| idempotencia | sí |
| instalación desde cero | **sí, funcionaría** |
| ejecución parcial | igual |
| rollback | igual |
| ejecución repetida | sí |
| ejecución individual (`psql -f`) | **sigue sin funcionar** — la tabla no existe |
| trazabilidad | **peor**: dos escritores, imposible saber cuál registró |
| compatibilidad con el contrato | **rompe el principio de dueño único** |
| riesgo de migración parcialmente aplicada | **mayor**: si una migración se auto-registra y el runner falla después, la fila puede quedar sin su DDL |

**Cambio:** una línea. **Costo:** preserva un mecanismo que no funciona y consolida
dos dueños del registro.

### B) Eliminar el auto-registro de las 16

| criterio | resultado |
|---|---|
| atomicidad | DDL y registro en la misma transacción del runner |
| idempotencia | sí — `done` decide |
| instalación desde cero | **sí** |
| ejecución parcial | el runner revierte todo; no quedan filas huérfanas |
| rollback | correcto: sin registro sin DDL, ni DDL sin registro |
| ejecución repetida | sí |
| ejecución individual | **explícitamente no soportada**, y se documenta |
| trazabilidad | **un solo escritor** |
| compatibilidad con el contrato | **alinea las 29 con `001`–`007` y `026`–`031`** |
| riesgo de parcialidad | **menor** |

**Cambio:** quitar 2 líneas de 16 archivos. Ninguna es funcional.

---

## Decisión: **B**

No por estética. Por tres razones contractuales:

1. **A preserva un mecanismo roto.** El auto-registro existe para soportar `psql -f`,
   que no funciona sobre base limpia porque depende de una tabla que crea el runner.
   Mantenerlo es mantener una promesa que el sistema no cumple.
2. **Dueño único.** El principio que el propio encargo fija. A lo viola por diseño; B
   lo restaura.
3. **El patrón histórico ya eligió B.** 13 de las 29 migraciones —las primeras y las
   últimas— nunca se auto-registraron. Las 16 del medio son la excepción, no la regla.

### Qué se modifica

Sólo la sentencia de auto-registro en 16 archivos:

```sql
INSERT INTO engine.schema_migrations (filename)
VALUES ('<nombre>.sql') ON CONFLICT DO NOTHING;
```

**No se toca** ninguna sentencia funcional: ni tablas, ni triggers, ni CHECKs, ni
GRANTs, ni datos.

### Efecto sobre la base homologada: ninguno

Las 29 ya están registradas. `apply_migrations` las encuentra en `done` y las salta.
Quitar el auto-registro no cambia una sola fila.

### Consecuencia declarada

**Aplicar una migración con `psql -f` ya no la registra.** Es intencional: el registro
es responsabilidad del runner. Quien aplique una migración a mano queda fuera del
mecanismo oficial, y el runner la volverá a aplicar en el próximo arranque — por eso
toda migración debe ser idempotente (`IF NOT EXISTS`, `DROP … IF EXISTS`, `CREATE OR
REPLACE`), como ya lo son.
