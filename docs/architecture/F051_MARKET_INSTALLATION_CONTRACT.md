# CONTRATO — F-051 · INSTALACIÓN DE MARKET

**Fecha:** 2026-08-31 · **Escrito antes de modificar código.**
**Alcance:** exclusivamente el mecanismo de instalación. No toca datos, ni
`ticker_canonico`, ni el comportamiento funcional de Market.

---

## 0. El defecto, reproducido

`m19_apply_schema.py` aplica `scripts/market/market_schema.sql` — un schema
consolidado, **sin registro de versiones**. Las tres migraciones de
`migrations/market/` **no las aplica nadie**: el runner oficial
(`engine.db.apply_migrations`) apunta a `migrations/engine` y no las conoce.

Verificado sobre instalación limpia tras aplicar el mecanismo oficial de Market:

| | en `market_schema.sql` | en la base limpia |
|---|---|---|
| 10 tablas `market_*` | sí | **sí** |
| `venue_ticker` (F-014) | sí | **sí** |
| `ck_estado_coherente_con_artefacto` (F-038) | **no** | **NO** |

Prueba causal — el mismo `INSERT` de un `SUCCESS` sin `sha256`:

```
catalaxia (homologada):  violates check constraint "ck_estado_coherente_con_artefacto"
e2e_v101  (limpia)    :  violates foreign key constraint "market_raw_runs_instrument_id_fkey"
```

En la limpia lo detiene **otra barrera**. La garantía de F-038 no está instalada.

## 1. Inventario de las migraciones de Market

| archivo | qué hace | ¿cubierto por `market_schema.sql`? |
|---|---|---|
| `012_rol_market_readonly.sql` | crea el rol `catalaxia_market_ro` y sus GRANTs | **no** |
| `013_venue_ticker.sql` | agrega `venue_ticker` y lo puebla | **sí**, consolidado |
| `025_f038_invariantes_corrida.sql` | `ck_estado_coherente_con_artefacto` | **NO** |

Dos de las tres quedan fuera de cualquier mecanismo automático.

## 2. Cuál es el mecanismo oficial

**El runner de `engine/db.py`.** Es el único con registro (`engine.schema_migrations`),
orden determinista, transacción única y control de idempotencia — todo lo que F-049
dejó demostrado y probado con 14 escenarios.

`m19_apply_schema.py` **no es un runner**: es un aplicador de un schema consolidado,
idempotente pero sin versionado. Seguirá existiendo para crear las tablas base; lo que
no puede seguir haciendo es ser el *único* camino, porque no aplica migraciones.

## 3. La decisión: extender el runner, no duplicarlo

El encargo lo dice explícitamente: *«NO copiar simplemente el CHECK dentro de
market_schema.sql si eso evita solucionar el problema de que las migraciones de Market
no se ejecutan»*.

**Se extiende el runner existente para que aplique también `migrations/market/`.**

### Por qué así y no de las otras dos formas

| opción | por qué no |
|---|---|
| copiar el CHECK a `market_schema.sql` | cierra el síntoma y perpetúa que Market no tenga versionado. La 012 seguiría sin aplicarse |
| darle a Market su propio runner | **crea un segundo mecanismo paralelo**, que es exactamente lo que el encargo prohíbe y lo que causó F-049 |

### Cómo

`apply_migrations` pasa a recorrer **una lista ordenada de directorios**:
`migrations/engine` y luego `migrations/market`. Un solo registro
(`engine.schema_migrations`), una sola transacción, un solo dueño.

**Orden determinista:** dentro de cada directorio, por nombre; entre directorios,
engine antes que market. Market depende de las tablas que crea `market_schema.sql`,
no de las de engine, así que el orden entre ambos es indistinto — pero se fija para
que sea reproducible.

### El registro no puede colisionar

Los nombres se registran **prefijados por su directorio** (`engine/008_….sql`,
`market/013_….sql`). Sin eso, `012_rol_market_readonly.sql` y un futuro
`012_*.sql` de engine competirían por la misma PK.

**Consecuencia sobre bases existentes:** la base homologada tiene 29 filas con el
nombre desnudo. Cambiar el formato haría que el runner las creyera pendientes y las
re-aplicara. Las migraciones son idempotentes (`IF NOT EXISTS`, `DROP … IF EXISTS`,
`CREATE OR REPLACE`), así que re-aplicarlas es seguro — pero **re-ejecutar 29
migraciones en cada arranque no es aceptable**.

Por eso el runner reconoce **ambos formatos** al decidir qué está pendiente: una
migración registrada con nombre desnudo se considera aplicada. Escribe siempre el
formato nuevo.

## 4. Dependencia de orden con `market_schema.sql`

`013` y `025` hacen `ALTER TABLE market_instruments` / `market_raw_runs`: **exigen que
las tablas existan**. Si el runner corre antes que `m19_apply_schema.py`, fallan.

**Contrato:** las migraciones de Market se aplican **sólo si sus tablas existen**. Si
no existen, se saltean con aviso — Market todavía no está instalado en esa base, y el
runner de engine no debe fallar por eso.

Esto es una condición real del sistema, no una excusa: `engine` y `market` son dos
schemas con ciclos de vida separados, y una base puede tener uno sin el otro (la base
de engine en dev no tenía Market hasta que se aplicó su schema).

## 5. Lo que NO se hace

- No se modifican datos ni `ticker_canonico`.
- No se toca `market_schema.sql` — `venue_ticker` sigue donde está.
- No se toca el comportamiento funcional de Market.
- No se crea un segundo runner.
- No se cierran ni falsifican corridas históricas.

## 6. Acceptance

Sobre base limpia, con `market_schema.sql` aplicado:

1. el runner aplica las 3 migraciones de Market;
2. `ck_estado_coherente_con_artefacto` **existe**;
3. `venue_ticker` **sigue existiendo**;
4. segunda ejecución: 0 re-aplicadas, 0 duplicados;
5. un fallo a mitad revierte todo;
6. la base sin tablas de Market no rompe el runner de engine;
7. la base homologada **no re-aplica** sus 29 migraciones.

Y la mutación: quitar `025` del directorio debe hacer que el CHECK desaparezca de una
instalación limpia — demostrando que es esa migración la que lo instala.
