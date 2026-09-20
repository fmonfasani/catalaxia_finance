# F-049 — EL RUNNER DE MIGRACIONES NO PUEDE APLICAR LAS MIGRACIONES

**Detectado:** 2026-08-29, en la fase H (reproducibilidad) del ciclo de release
**Estado: REGISTRADO, NO CORREGIDO** — el encargo prohíbe parchear el release
**Severidad: BLOQUEANTE para la distribución.** No afecta el sistema homologado.

---

## 1. El defecto

Desde una base limpia, con el checkout del tag `v1.0.0`, su propio runner
(`engine.db.apply_migrations`) **no aplica ninguna migración**:

```
sqlalchemy.exc.IntegrityError: duplicate key value violates unique constraint
DETAIL:  Key (filename)=(008_identity_v1.sql) already exists.
[SQL: INSERT INTO engine.schema_migrations (filename) VALUES (%(f)s)]
```

## 2. La causa: el registro se hace dos veces

**16 de las 29 migraciones de engine se auto-registran** al final de su propio SQL:

```sql
INSERT INTO engine.schema_migrations (filename)
VALUES ('008_identity_v1.sql') ON CONFLICT DO NOTHING;
```

Las 16 usan `ON CONFLICT DO NOTHING`, así que esa inserción siempre tiene éxito.

Y el runner **vuelve a registrarla**, sin `ON CONFLICT` (`engine/db.py:93-96`):

```python
conn.execute(text(sql_file.read_text(encoding="utf-8")))
conn.execute(
    text("INSERT INTO engine.schema_migrations (filename) VALUES (:f)"),
    {"f": sql_file.name},
)
```

La migración ya insertó la fila; el runner choca contra su propia PK.

## 3. El efecto es total, no parcial

`_apply_migrations` corre dentro de **una sola transacción**. Al fallar en la
primera migración auto-registrada (`008`), revierte todo: la base descartable quedó
**sin `engine.schema_migrations` siquiera**.

Verificado: `relation "engine.schema_migrations" does not exist` después del intento.

Las 7 primeras (`001`–`007`) no se auto-registran y habrían pasado; el rollback las
descarta igual.

## 4. Por qué nunca se había visto

**Las 16 migraciones auto-registradas se aplicaron siempre a mano**, con
`docker exec psql -f`, durante todos los ciclos de desarrollo. El runner nunca las
procesó.

La base homologada tiene las 29 registradas y correctas — pero llegó ahí por el
camino manual, no por el automático. El camino automático nunca se ejercitó hasta
que la fase H lo obligó.

Es la misma clase de hallazgo que F-038 y F-040: **un mecanismo que existe, se
supone funcionando, y nadie había ejercitado**.

## 5. Lo que NO es

- **No afecta el sistema homologado.** La base tiene sus 29 migraciones aplicadas y
  registradas; los 8 controles de integridad siguen en cero; el baseline coincide.
- **No es corrupción, ni pérdida, ni bypass.**
- **No invalida la homologación.** Lo auditado sigue siendo válido sobre el estado
  que se auditó.
- **No es F-048.** F-048 era «el release no está en ningún commit» y quedó cerrado:
  el commit `25756e1a` y el tag `v1.0.0` contienen los 148 archivos de V1.

## 6. Lo que sí es

**El release no se puede desplegar desde cero.** Un tercero que haga
`git checkout v1.0.0` y siga el procedimiento normal no obtiene el schema de V1.

Eso es exactamente el criterio de `RELEASE_BLOCKED` que el encargo define:
*«Si falla … RELEASE_BLOCKED. No parchear silenciosamente el release.»*

## 7. Corrección propuesta (no aplicada)

Dos vías, cualquiera de las dos alcanza. **La decisión es de producto, no técnica**,
porque cambia dónde vive la responsabilidad del registro:

1. **El runner deja de asumir que la migración no se registró:** agregar
   `ON CONFLICT (filename) DO NOTHING` al `INSERT` de `engine/db.py:94`. Un cambio de
   una línea, sin tocar ninguna migración.
2. **Las migraciones dejan de auto-registrarse:** quitar el `INSERT` final de las 16.
   Deja el registro como responsabilidad única del runner, pero rompe la posibilidad
   de aplicarlas sueltas con `psql -f` — que es como se aplicaron todas hasta hoy.

La opción 1 es menos invasiva y preserva ambos caminos. La 2 es más limpia
conceptualmente y elimina la duplicación de responsabilidad.

**Requiere autorización explícita**, porque el encargo de este ciclo prohíbe
corregir findings y modificar funcionalidad.

## 8. Verificación de que la corrección funcionaría

No se aplicó ninguna, así que **no está verificada**. La reproducción del defecto sí
lo está: base limpia + runner del tag → `duplicate key` en `008`, rollback total.
