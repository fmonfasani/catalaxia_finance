# CNV multi-perímetro — diagnóstico de arquitectura y plan de cambios

**2026-09-02** · inspección previa a implementar · **sin modificar código todavía**

---

## Resumen en tres líneas

1. **El scope YA se extrae**, en las dos superficies, desde un **campo estructurado
   de CNV** — no por heurística. El requisito §3 ya está cumplido.
2. **Se pierde en un solo lugar**, y es deliberado: `_perimetro.py` elige UNO por
   `(cuit, period_end)`. Está documentado, con dos alternativas rechazadas.
3. **Hay una bifurcación que no puedo resolver solo**: las dos superficies CNV son
   distintas y **METR sólo existe en una de ellas**. Ver §6.

---

## 1. Inventario del pipeline CNV — hay dos, no uno

### A · Superficie canónica · PostgreSQL 5433

```
c3_cnv_fetch.py            fetcher, con gate de elegibilidad por CUIT autoritativo
  └─ engine/cnv/discovery.py   clasifica cada presentación
       └─ fetch_raw.cnv_presentation   82.493 filas · tipo_balance · norma_contable
       └─ fetch_raw.cnv_artifact        3.985 filas
       └─ fetch_raw.cnv_download_log
```

**Cobertura: 3 CUIT.** `30546689979` (YPF), `30657862068` (TGS), `33650305499`
(CEPU). Sin capa de normalización a conceptos ni cálculo de ratios: hoy llega
hasta el RAW y la presentación.

### B · Superficie legacy · SQLite `data/screener.db`

```
job5_v2_extract_eeff.py  →  cnv_estados_v2        102.323 filas · tipo_balance
job8_doc_meta.py         →  cnv_doc_meta          TipoBalance estructurado
s0_normalizar_cnv.py     →  cnv_estados_norm      106.421 filas · 72 CUIT
                                                   tipo_balance + perimetro_mixto
s2_ratios_cnv.py         →  ratios_cnv            72 filas   ← EL SCOPE MUERE ACÁ
s4_ensamblar.py          →  screener              572 filas  ← sin scope
s8_calidad.py            →  screener_gold         567 filas  ← sin scope
recompute_ttm.py         →  ratios_ttm
```

**Cobertura: 72 CUIT, 30 períodos de mediana. METR está acá.**

---

## 2. Dónde SÍ está el scope — y de dónde sale

**No hay que construirlo. Está, y su origen es estructural, no inferido.**

| capa | campo | origen |
|---|---|---|
| canónica | `fetch_raw.cnv_presentation.tipo_balance` | `discovery.py:211,214` — parsea `TIPO BAL.` / `TIPO BALANCE` del título de la presentación CNV |
| canónica | `.norma_contable` | ídem — NIIF / NCP / OTROS |
| legacy | `cnv_doc_meta.tipo_balance` | `job8_doc_meta.py` — campo `<propiedad claveinformativa="TipoBalance">`. **Cobertura verificada: 100 % de 2.145 documentos** |
| legacy | `cnv_estados_v2.tipo_balance` | `job5` lo extrae del documento; poblado al 100 % de 102.323 filas |
| legacy | `cnv_estados_norm.tipo_balance` | `s0_normalizar_cnv.py:158` — `COALESCE(m.tipo_balance, e.tipo_balance, '')` |
| legacy | `cnv_estados_norm.perimetro_mixto` | bandera de que el período tiene los dos |

Distribución medida en la superficie canónica:

```
CONSOLIDADO · NIIF   2.952      INDIVIDUAL · NCP     3.024
CONSOLIDADO · (s/n)  3.573      INDIVIDUAL · NIIF    2.331
CONSOLIDADO · NCP      486      INDIVIDUAL · OTROS     504
(null)              69.623   ← presentaciones que no son EEFF (hechos relevantes, etc.)
```

**Conclusión: el requisito §3 —clasificar por metadata del filing y no por los
números— ya está satisfecho.** El `unresolved` que pedís existe de facto como
`tipo_balance IS NULL` / `''`; falta darle nombre y hacerlo explícito.

---

## 3. Dónde se PIERDE — un solo punto, y a propósito

### `scripts/tickets/screener/_perimetro.py`

```python
def perimetro_preferido(cur, cuit, period_end):
    """Perímetro a usar para ese cuit+periodo."""
    # 1º el que tenga Revenue; a igualdad, el más completo
    filas = sorted(filas, key=lambda f: (f[1], f[2]), reverse=True)
    return filas[0][0]        # ← se elige UNO y se descartan los demás

def filtro_sql(cur, cuit, period_end):
    p = perimetro_preferido(cur, cuit, period_end)
    return (" AND tipo_balance=? ", [p]) if p else ("", [])
```

**Su docstring documenta la decisión y las alternativas rechazadas:**

> «Por cada (cuit, period_end) se elige UN perímetro y se usan SOLO sus
> conceptos. Se descartaron dos reglas antes de ésta: *"consolidado siempre"*
> destruye el 73 % de los conceptos en casos mixtos; *"el más completo"* en una
> holding elige el individual, que es justo el perímetro sin operaciones.»

Esto **no es un bug**. Es una decisión consciente, tomada para evitar el
problema opuesto —mezclar perímetros dentro de un ratio— y compartida por cuatro
consumidores para que no diverjan:

```
s2_ratios_cnv.py:37       from _perimetro import perimetro_preferido, filtro_sql
s4_ensamblar.py:30        from _perimetro import filtro_sql
s8_calidad.py
recompute_ttm.py:27       from _perimetro import filtro_sql
```

**Lo que hay que cambiar no es la regla de aislamiento —que es correcta— sino su
alcance: hoy aísla eligiendo uno; debe aislar enumerando todos.**

### Y tres razones estructurales por las que un segundo scope no sobreviviría

En `s2_ratios_cnv.py`:

```python
257:  cur.execute("DROP TABLE IF EXISTS ratios_cnv")
259:  CREATE TABLE ratios_cnv (cuit TEXT PRIMARY KEY, ...)   ← una fila por empresa
428:  INSERT OR REPLACE INTO ratios_cnv                       ← el segundo pisa al primero
```

`PRIMARY KEY (cuit)` es el bloqueo duro: **aunque `_perimetro` devolviera los
dos, la tabla sólo puede guardar uno.** Y `screener` / `screener_gold` no tienen
columna de scope en absoluto.

---

## 4. Diff lógico propuesto

```
ANTES
  cnv_estados_norm (con tipo_balance)
    → _perimetro.perimetro_preferido()  → elige UNO
      → s2 calcula ratios de ese uno
        → ratios_cnv  PK(cuit)          → 1 fila
          → screener / screener_gold    → sin scope

DESPUÉS
  cnv_estados_norm (con tipo_balance)
    → _perimetro.perimetros_disponibles() → [CONSOLIDADO, INDIVIDUAL, UNRESOLVED]
      → for scope in disponibles:
          s2 calcula ratios SÓLO con conceptos de ese scope
        → ratios_cnv  PK(cuit, period_end, statement_scope) → N filas
          → screener / screener_gold + columna statement_scope
            → vista legacy con default_scope = perimetro_preferido()
```

`perimetro_preferido()` **no se borra**: pasa a ser el `default_scope` que §19
pide para no romper consumidores.

---

## 5. Componentes a modificar

| # | archivo | cambio | riesgo |
|---|---|---|---|
| 1 | `_perimetro.py` | agregar `perimetros_disponibles()`; conservar `perimetro_preferido()` como default | **bajo** — es aditivo |
| 2 | `s2_ratios_cnv.py` | bucle por scope; PK `(cuit, period_end, statement_scope)` | **medio** — cambia el esquema de `ratios_cnv` |
| 3 | `s4_ensamblar.py` | propagar scope; decidir qué scope va a `screener` | **medio** — `screener` alimenta la API |
| 4 | `s8_calidad.py` | certificar por scope | bajo |
| 5 | `recompute_ttm.py` | TTM por scope | bajo |
| 6 | salidas CSV/MD | columna `statement_scope` + `METR_CNV_SCOPE_COMPARISON.md` | bajo |
| 7 | tests | 6 nuevos (§20) | — |

### Consumidores que asumen una fila por empresa

```
api/main.py            /v2/screener · /v2/screener/{ticker} · /v2/grupos · /v2/stats
docs/producto/screener.html                (screener_gold)
scripts/deploy/sincronizar_a_produccion.py (empuja screener a producción)
scripts/tickets/screener/load_screener_ratios.py
```

Todos leen `screener` / `screener_gold`. Si esas tablas ganan filas por scope,
**la API devuelve duplicados**. Por eso `default_scope` no es opcional: es la
condición para no romper producción.

---

## 6. LA BIFURCACIÓN — necesita tu decisión

**Las dos superficies CNV no cubren las mismas empresas, y METR sólo está en una.**

```
identity_v1 · CUIT de METR (30657863676) ....... 0 filas
fetch_raw.cnv_presentation · CUIT distintos .... 3   (YPF, TGS, CEPU)
cnv_estados_norm · METR ....................... 30 períodos, ambos perímetros
```

| | canónica (PostgreSQL) | legacy (SQLite) |
|---|---|---|
| ¿tiene scope al ingerir? | **sí** | **sí** |
| ¿tiene capa de conceptos? | **no** | sí (51 conceptos) |
| ¿tiene ratios? | no | sí |
| ¿está METR? | **NO** | **sí** |
| ¿se puede correr el caso de regresión §11? | **no** | **sí** |
| estatus en el contrato de producto | **CANÓNICA** | REFERENCE ONLY |

**El conflicto:** el caso de regresión obligatorio es METR FY2025, y METR **no
puede entrar a la superficie canónica** sin promover su CUIT a `identity_v1` —
que es modificar Identity, prohibido en los ciclos anteriores y fuera del
alcance de éste.

### Tres caminos

**A · Implementar sobre legacy.** Se puede probar con METR hoy mismo, cumple los
16 criterios de aceptación de §24 y arregla el punto donde el dato realmente se
pierde. Contra: se invierte trabajo en la superficie declarada REFERENCE ONLY.

**B · Implementar sobre canónica.** Arquitectónicamente correcto y alineado con
el contrato. Contra: **no se puede validar con METR** —habría que usar YPF, TGS o
CEPU— y además exige construir la capa de conceptos y de ratios CNV, que hoy no
existe. Es un proyecto, no un cambio.

**C · Las dos, en orden.** `_perimetro.py` + `s2/s4/s8` ahora (probado con METR),
y el modelo `statement_scope` queda especificado para cuando la canónica tenga
capa de conceptos. El diseño se valida con datos reales antes de migrarlo.

**Recomiendo C.** El cambio real es chico y está muy localizado —una función
nueva y una clave primaria—, METR lo valida de inmediato, y no se compromete la
arquitectura canónica con una implementación no probada.

---

## 7. Lo que NO hay que construir

Vale decirlo porque el encargo asume que sí:

- **El clasificador de scope.** Existe, y lee un campo estructurado de CNV.
- **La regla de no-mezcla.** Existe en `_perimetro.py` y ya la comparten cuatro
  consumidores. Hay que ampliarla, no crearla.
- **La captura de scope en el RAW.** Las dos superficies ya lo guardan.
- **Lógica específica de METR.** No existe hoy y no hay que agregarla: el
  `perimetro_mixto` ya es genérico y marca 72 empresas.

---

## 8. Riesgo principal

`ratios_cnv` se reconstruye con `DROP TABLE` en cada corrida, así que cambiar su
clave primaria no requiere migración. **Pero `screener` y `screener_gold` sí
alimentan producción**, y agregarles filas por scope rompería la API y la página
publicada. El cambio en `s4`/`s8` tiene que entrar con `default_scope` desde el
primer commit, no después.

---

## Estado

**Diagnóstico entregado. Sin código modificado.** Esperando tu decisión sobre
§6 (A, B o C) para implementar.
