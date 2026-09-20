*# F-051 — LAS MIGRACIONES DE MARKET NO TIENEN MECANISMO DE APLICACIÓN

**Detectado:** 2026-08-31, E2E de v1.0.1 (Fase 4)
**Estado: REGISTRADO, NO CORREGIDO** — el ciclo E2E prohíbe corregir findings
**Severidad: media.** Una instalación limpia de Market queda sin una garantía homologada.

---

## 1. El hallazgo

`migrations/market/` contiene 3 archivos:

```
012_rol_market_readonly.sql
013_venue_ticker.sql
025_f038_invariantes_corrida.sql
```

**Ningún script del release los aplica.** El runner oficial
(`engine.db.apply_migrations`) apunta a `MIGRATIONS_DIR = REPO_ROOT/migrations/engine`
y no conoce `migrations/market`. La única referencia a esa carpeta en todo el código
es `release_baseline.py`, que la lista para el manifiesto — no la ejecuta.

Market instala su schema con `scripts/market/m19_apply_schema.py`, que aplica
`scripts/market/market_schema.sql`. Ese archivo **no es un runner de migraciones**:
es un schema consolidado, sin registro ni control de versiones aplicadas.

## 2. Qué queda cubierto y qué no

Verificado sobre la instalación limpia `e2e_v101` tras aplicar el mecanismo oficial
de Market:

| | en `market_schema.sql` | en la base limpia |
|---|---|---|
| 10 tablas `market_*` | sí | **sí** |
| `venue_ticker` (F-014) | sí, 8 ocurrencias | **sí** |
| `ck_estado_coherente_con_artefacto` (F-038) | **no** | **NO** |

`venue_ticker` sobrevivió porque alguien lo consolidó en el schema. El CHECK de F-038
no, y por eso **no existe en una instalación limpia**.

## 3. Evidencia causal

El mismo `INSERT` de un `SUCCESS` sin `sha256` —lo que F-038 debe impedir— en ambas
bases:

```
catalaxia (homologada):  ERROR ... violates check constraint "ck_estado_coherente_con_artefacto"
e2e_v101  (limpia)    :  ERROR ... violates foreign key constraint "market_raw_runs_instrument_id_fkey"
```

En la limpia lo detiene **otra barrera** (una FK accidental del fixture), no la
garantía. Con un `instrument_id` válido, la fila entraría.

**La garantía de F-038 no está instalada.**

## 4. Por qué la homologación no lo vio

La homologación verificó `ck_estado_coherente_con_artefacto` **sobre la base
homologada**, donde yo mismo lo había aplicado a mano con `psql -f` en el ciclo de
F-038. Nunca se ejercitó una instalación limpia de Market.

Es el mismo patrón que F-049 —donde el runner de engine nunca se había ejercitado— y
que F-050. **Tres veces el mismo tipo de defecto: un mecanismo que se supone
funcionando y que nadie había corrido desde cero.**

## 5. Lo que NO es

- **No afecta la base homologada**, que tiene el CHECK aplicado y validado.
- **No es pérdida ni corrupción** de datos existentes.
- **No invalida F-014**: `venue_ticker` sí se instala.

## 6. Corrección propuesta (no aplicada)

Tres vías; la elección es de arquitectura, no técnica:

1. **Extender el runner** para que aplique también `migrations/market/`, con su propia
   tabla de registro o compartiendo `engine.schema_migrations`. Unifica el mecanismo.
2. **Consolidar** el CHECK de F-038 en `market_schema.sql`, como ya está `venue_ticker`.
   Mínimo, pero perpetúa que Market no tenga versionado de migraciones.
3. **Dar a Market su propio runner**, simétrico al de engine.

La 1 es la que elimina la asimetría. La 2 es la que cierra el hueco concreto con menos
cambio.

**Requiere autorización**: el ciclo E2E prohíbe corregir findings.
