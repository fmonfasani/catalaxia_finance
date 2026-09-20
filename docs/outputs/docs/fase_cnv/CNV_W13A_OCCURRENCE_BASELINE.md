# CNV W-1.3A — BASELINE DE OCURRENCIAS

**Fecha:** 2026-09-02 · medición previa a cualquier cambio de código.
**Origen:** `data/screener.db` del repo principal, abierto **en modo solo lectura**.
**Fixture:** `catalaxia-cnvmig/data/w13a_fixture.db` (124 MB, 6 tablas CNV).

---

## 1 · Dónde ocurre la pérdida, exactamente

La cadena tiene **dos** puntos de pérdida, no uno:

| paso | script | cláusula | PK | qué hace |
|---|---|---|---|---|
| RAW → `cnv_estados_v2` | `job5_v2_extract_eeff.py` | `INSERT OR IGNORE` | `(cuit, concepto, period_end, fecha_reexpresion, tipo_balance)` | **descarta** el segundo documento |
| `v2` → `cnv_estados_norm` | `s0_normalizar_cnv.py` | `INSERT OR REPLACE` | **la misma** | **sobrescribe** con el último |

Es la misma clave en los dos, con comportamientos silenciosos opuestos: `v2`
conserva el primero, `norm` conservaría el último. **Arreglar solo `job5` no
alcanza**: `s0` volvería a colapsar las ocurrencias recién preservadas.

### La clave es económica, no documental

```
PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion, tipo_balance)
```

Identifica **lo que se mide**, no **quién lo declara**. Y `fecha_reexpresion` no
aporta nada:

```
filas 102.323 · PK completa 102.323 claves · PK sin fecha_reexpresion 102.323
-> fecha_reexpresion agrega 0 claves
```

`job5` la inserta como cadena vacía. La clave efectiva es
`(cuit, concepto, period_end, tipo_balance)`.

---

## 2 · Cardinalidades de partida

| | filas | documentos | CUITs |
|---|--:|--:|--:|
| `cnv_estados_v2` | 102.323 | 2.350 | 71 |
| `cnv_estados_norm` | 106.421 | 2.453 | 72 |
| documentos RAW en disco | — | 2.364 | — |

`norm` tiene 103 documentos que `v2` no tiene: llegan por otra vía de ingesta.

---

## 3 · Los documentos que producen colisión

Siete tripletas `(cuit, período, perímetro)` con dos documentos. Para cada una,
lo que el RAW contiene frente a lo que la tabla conservó:

| CUIT | período | perímetro | documento | conceptos en RAW | filas en `v2` | **descartadas** |
|---|---|---|---|--:|--:|--:|
| 30500833781 (LONG) | 2018-12-31 | INDIVIDUAL | `5ec882c1` | 36 | 36 | 0 |
| | | | `6e42e64b` | 42 | 6 | **36** |
| 30500833781 | 2019-03-31 | INDIVIDUAL | `ae6025b3` | 36 | 36 | 0 |
| | | | `e0caf38b` | 41 | 6 | **35** |
| 30500833781 | 2020-12-31 | INDIVIDUAL | `a7b4cf63` | 42 | 42 | 0 |
| | | | `cc9f66fc` | 38 | 2 | **36** |
| 30501290323 (INTR) | 2021-12-31 | CONSOLIDADO | `d22a6454` | 46 | 46 | 0 |
| | | | `8e2551d5` | 47 | 1 | **46** |
| 30502112259 (FIPL) | 2025-06-30 | CONSOLIDADO | `3af9154f` | 48 | 48 | 0 |
| | | | `d776e1b2` | 51 | 3 | **48** |
| 30696170580 (_ADR_0580) | 2019-12-31 | CONSOLIDADO | `02a03799` | 46 | 46 | 0 |
| | | | `73288a26` | 48 | 2 | **46** |
| 30715471953 (BYMA) | 2021-12-31 | CONSOLIDADO | `863efe00` | 45 | 45 | 0 |
| | | | `ee3e755d` | 46 | 1 | **45** |
| | | | | | **total** | **292** |

Todos los documentos declaran, cada uno una sola vez, la **misma**
`FechaCierre`, la **misma** `UnidadMedida`, el **mismo** `PeriodoBalance` y el
**mismo** `TipoBalance` que su pareja. No hay ningún campo del documento que
permita decir que uno es "el bueno".

### Números de presentación

Las parejas se presentan con pocos minutos de diferencia:

| par | presentación A | presentación B | distancia |
|---|--:|--:|--:|
| BYMA 2021-12-31 | #2864462 | #2864443 | 19 |
| LONG 2020-12-31 | #2728138 | #2728103 | 35 |
| FIPL 2025-06-30 | #3425196 | — | — |

---

## 4 · El caso BYMA, que prueba que el conservado puede ser el incorrecto

Serie de `PPE` CONSOLIDADO del emisor, tal como está hoy en la tabla:

```
2021-06-30   1.363.538.003
2021-09-30   1.481.185.590
2021-12-31      11.060.815    <- el documento que SÍ entró
2022-03-31   1.835.280.221
2022-06-30   2.137.175.733
```

Y la serie INDIVIDUAL del mismo emisor se mueve en 11–12 millones.

El documento descartado (`ee3e755d`) trae **1.593.406.319** — el valor que la
serie consolidada exige, entre 1.481 M y 1.835 M.

El texto se parsea limpio en los dos:

```
863efe00:  1110100 PROPIEDADES PLANTAS Y EQUIPOS    11060815.00
ee3e755d:  1110100 PROPIEDADES PLANTAS Y EQUIPOS  1593406319.00
```

`INSERT OR IGNORE` conserva **el que llega primero**, no el correcto. Acá
conservó el que la serie desmiente.

> Este caso queda como fixture de regresión. **No se codifica ninguna excepción
> para BYMA**: la corrección es estructural y el test solo exige que las dos
> ocurrencias estén.

---

## 5 · Reproducción del defecto antes de tocar nada

`tests/test_w13a_occurrence_preservation.py`, escrito contra el esquema real
extraído del job (`SCHEMA_V2`, `SQL_INSERT`), sin cambiar un solo umbral:

```
5 failed, 5 passed
```

| test | falla porque |
|---|---|
| I1 | dos documentos, misma identidad → sobrevive 1 de 2 |
| I3 | tres documentos → 1 ocurrencia |
| I5 | valores distintos → se pierde uno |
| I6 | BYMA → se conserva solo `863efe00`, el que la serie desmiente |
| I8 | reingerir los 7 casos: **866 filas insertadas, 468 sobreviven → 398 perdidas** |

Los 5 que pasaban lo hacían por razones triviales: I2 (idempotencia) se cumple
*porque* la clave colapsa, que es justamente el defecto.

---

## 6 · Qué habilita este baseline

La pérdida está localizada, medida y acotada:

- **292 ocurrencias** de 7 documentos, recuperables desde el RAW en disco;
- **dos** puntos de la cadena a corregir, no uno;
- un identificador documental **ya existente** —`accn`, el GUID del archivo—
  que no hay que inventar;
- un ordinal de publicación en el 100 % de los documentos, para poder ordenar
  las ocurrencias después.
