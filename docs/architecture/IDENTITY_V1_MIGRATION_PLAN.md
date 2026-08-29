# IDENTITY V1 — PLAN DE MIGRACIÓN

**Fecha:** 2026-08-25
**Estado actual:** Fase 0 y Fase 1 completadas. Fase 2 en adelante, NO ejecutadas.

---

## Dónde estamos

```
[✔] Fase 0 — Esquema, sin datos
[✔] Fase 1 — Piloto de 4 emisores con evidencia real
[ ] Fase 2 — Backfill del catálogo legacy         ← siguiente, requiere decisión
[ ] Fase 3 — Doble lectura y reconciliación
[ ] Fase 4 — Corte: identity_v1 pasa a ser la fuente
[ ] Fase 5 — Retiro del schema `identity` y de dim_entity
```

Cada fase es reversible por sí sola. Ninguna fase posterior arranca sin que la
anterior tenga su evidencia escrita.

---

## Fase 0 — Esquema, sin datos ✔

`migrations/engine/008_identity_v1.sql` aplicada en 5433. Schema `identity_v1`
coexistiendo con `identity`, que **no se modificó**. 8 tablas, 21 CHECK, 3
índices únicos parciales, 3 triggers, 1 vista, 8 fuentes catalogadas.

**Reversible:** `DROP SCHEMA identity_v1 CASCADE` + borrar la fila de
`engine.schema_migrations`. Se ejecutó una vez durante el desarrollo, para
re-aplicar con el trigger de inmutabilidad corregido.

---

## Fase 1 — Piloto de 4 emisores ✔

4 emisores sembrados con evidencia real de SEC, GLEIF, CNV y Market.

```
0 conflictos abiertos · 5 reviews abiertas · 0 identificadores inventados
```

**Reversible:** `identity_v1_pilot.py --reset`.

---

## Fase 2 — Backfill del catálogo legacy (NO ejecutada)

### Lo que hay que migrar

| Origen | Volumen | Estado |
|---|---|---|
| `identity.entities` (5433) | **7.998** entidades, **0 con CUIT** | por migrar |
| `identity.identifiers` | YF_SYMBOL 10.414 · TICKER/US 10.403 · CIK 7.998 · TICKER/BYMA 11 · **CUIT: 0** | por migrar |
| `dim_entity` (SQLite legacy) | 573 entidades: 74 con CUIT, 512 con CIK, **13 con ambos** (todas `grupo='adr'`) | por migrar |
| `market_instruments` (5432) | ~584 instrumentos | por vincular |

### Las tres reglas del backfill

**1. El legacy entra como `CORROBORATING`, nunca como `AUTHORITATIVE`.**
`LEGACY_DIM_ENTITY` está catalogada así en `identity_v1.source` y la capa de
dominio ya lo respeta: en el banco adversario, el legacy intentando completar el
CUIT de GGAL produjo `CANDIDATE` y el CUIT autoritativo quedó vacío. El legacy
ya falló antes — es la fuente del CIK mal atribuido de YPF — así que no vuelve
a entrar con autoridad.

**2. Los 74 CUIT del legacy no se migran como verdad.** Se migran como
`CANDIDATE` y se contrastan contra GLEIF. Cada uno cae en uno de tres cubos:

| Caso | Acción |
|---|---|
| GLEIF publica el mismo CUIT (`RA000009`/`RA000010`, checksum OK) | `VERIFIED` por GLEIF; el legacy queda corroborando |
| GLEIF no publica CUIT (como GGAL, `RA999999`) | `REVIEW_REQUIRED` con el candidato legacy adjunto |
| GLEIF publica **otro** CUIT | `conflict` + `REVIEW_REQUIRED`. **No gana ninguno automáticamente** |

**3. Nada se migra sin `entity_key` nuevo.** Los `entity_id` legacy tipo
`CIK:0000904851` entran como identificadores `LEGACY_ENTITY_ID` (nunca
autoritativos, por CHECK) para poder rastrear el origen, pero la clave primaria
es un ULID nuevo. Es el punto de todo el diseño: romper el acoplamiento
clave↔CIK.

### El bloqueante de la Fase 2

Los 7.998 emisores de `identity.entities` son mayoritariamente **US (SEC)**. Para
ellos:

- el CIK es directo y autoritativo (`SEC_REGISTRY`);
- el CUIT **no aplica** (no son argentinos);
- el LEI requiere el puente CIK↔LEI que **no tiene fuente primaria** (G5).

Con lo que hay hoy, el backfill produciría del orden de **8.000
`REVIEW_REQUIRED`** por el puente CIK↔LEI, que ninguna persona va a procesar.
Esto no es un defecto de Identity v1: es el costo real de la carencia que el
ciclo G5 documentó, hecho visible.

**Decisión pendiente (D-I-04), es de producto y no técnica:**

| Opción | Qué implica |
|---|---|
| **A** — El LEI es opcional | No se abre review si falta LEI. El LEI se resuelve solo para los ~56 emisores argentinos, donde habilita el CUIT vía GLEIF |
| **B** — Review masiva | 8.000 reviews abiertas. Honesto y también inútil |
| **C** — Regla derivada documentada | Aceptar coincidencia GLEIF por nombre+jurisdicción como `CANDIDATE` automático, con revisión solo de los ambiguos. Nunca `VERIFIED` |

**Recomendación: A para el universo US, C para los argentinos.** El LEI solo
tiene valor operativo en Catalaxia como puente hacia el CUIT, y el CUIT solo
aplica a emisores argentinos. Abrir 8.000 reviews por un identificador que no se
usa sería teatro de rigor.

Hasta que esta decisión esté cerrada, la Fase 2 **no arranca**.

---

## Fase 3 — Doble lectura y reconciliación (NO ejecutada)

Los consumidores (screener, dashboard, API) siguen leyendo `identity` y
`dim_entity`. En paralelo se corre un reconciliador que, para cada entidad,
compara la respuesta de las dos capas y registra las divergencias.

**Criterio de salida:** cero divergencias no explicadas durante N corridas
consecutivas. Una divergencia "explicada" es una donde Identity v1 dice
`REVIEW_REQUIRED` y el legacy afirma un valor sin evidencia — ahí Identity v1
tiene razón y el legacy es el que está mal.

**Reversible:** apagar el reconciliador. Ningún consumidor cambió.

---

## Fase 4 — Corte (NO ejecutada)

Los consumidores pasan a leer `identity_v1`. Requiere:

- Fase 3 con criterio de salida cumplido y documentado;
- una vista de compatibilidad que devuelva la forma que hoy esperan los
  consumidores, para que el corte sea un cambio de origen y no una reescritura;
- una política explícita para `REVIEW_REQUIRED`: **qué hace el screener con una
  empresa cuya identidad no está resuelta.** Hoy el legacy muestra un valor
  plausible. Identity v1 va a decir "no sé", y el producto tiene que saber qué
  hacer con eso.

**Reversible:** revertir el origen de lectura. Los datos legacy siguen intactos.

---

## Fase 5 — Retiro (NO ejecutada)

`DROP SCHEMA identity`, retiro de `dim_entity` como fuente de identidad.
**Irreversible.** No se ejecuta sin backup verificado y sin al menos un ciclo
completo de operación estable sobre la Fase 4.

---

## Lo que este plan NO incluye, por instrucción del ciclo 4

- Canonical Economic Facts
- Escalar Market a 584 instrumentos
- Ejecutar CNV en modo FINANCIERO/TODO
- Modificar el parser SEC, el fetcher de Market o el de CNV

Identity v1 se construyó como capa independiente, y así queda hasta que el
backfill esté decidido.
