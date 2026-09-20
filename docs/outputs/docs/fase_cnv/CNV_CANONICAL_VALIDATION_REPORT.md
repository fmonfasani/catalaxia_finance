# CNV CANONICAL — INFORME DE VALIDACIÓN

**Fecha:** 2026-09-02
**Alcance:** verificación independiente de la migración descrita en
`CNV_CANONICAL_MIGRATION_REPORT.md`
**Base:** `cnvmig` (fixture aislado) · la homologada `catalaxia` no se modificó

---

## 1 · Qué hace independiente a esta validación

`scripts/engine/c4_auditoria_cnv.py` **no importa** `c4_cnv_adapter`. No
reutiliza su `fact_key`, ni su mapa de escalas, ni su lectura del origen.
Vuelve al SQLite y a los HTML en disco, reconstruye por su cuenta lo que la
capa canónica debería contener, y compara. Un error compartido tendría que
haber sido escrito dos veces, por separado.

Solo lee: `SELECT` contra Postgres, `SELECT` contra SQLite, `sha256` de
archivos. Ninguna escritura, ninguna DDL.

---

## 2 · Resultado de la auditoría

**24 verificaciones · 0 fallas · 1 aviso.** Detalle completo en
`CNV_CANONICAL_MIGRATION_REPORT.md` §5.

Los tres números que más pesan:

| Verificación | Resultado |
|---|---|
| Biyección origen ↔ canónico | 2.697 claves, multiplicidad idéntica |
| `sha256` recomputado hoy vs. almacenado | 56 / 56 documentos |
| Violaciones de pertenencia (F-061) | 0 en CNV · 0 en SEC (133.902 hechos) |

**Aviso único:** 50 filas de un documento sin `tipo_balance` quedan fuera de la
capa canónica. Es una exclusión declarada, no una pérdida silenciosa: el censo
del adaptador la nombra y el auditor la vuelve a nombrar. No se les puede
asignar perímetro sin inventarlo.

---

## 3 · F-061 — la prueba que sostiene todo

### El agujero es real y está medido

| Guarda | ¿Bloquea a dos emisores sin CIK? |
|---|---|
| `p.cik <> d.cik` | **no** — `NULL <> NULL` = NULL |
| `p.cik IS DISTINCT FROM d.cik` | **no** — `NULL IS DISTINCT FROM NULL` = false |
| `p.entity_id IS DISTINCT FROM d.entity_id` | **sí** |

### Mutación

T5 quita la cláusula de `entity_id` y verifica que el hecho ajeno **vuelva a
pasar**. Si no volviera, la protección la estaría dando otra condición —el
`accession_number`, el `qname`— y T3 estaría probando otra cosa. Por eso el
escenario comparte `accession_number` y `qname` entre los cinco hechos: lo
único que puede bloquear es el emisor.

T5b documenta por qué el arreglo no era el operador. T7 verifica la contracara
de T6: que acotar el invariante SEC por `source_kind` no deje de mirar a los
hechos no-SEC (ninguno tiene `cik`, ninguno finge un `entity_id` `CIK:`,
ninguno está sin `entity_id`).

**14/14 tests de F-061 en verde** (8 en `test_f061_entity_ownership.py`,
6 en `test_f061_ownership.py`), partiendo de un rojo previo de 3.

---

## 4 · Regresión

### Suite completa

```
233 passed · 3 failed · 1 skipped
```

Las 3 fallas son `test_f038_traza_corrida.py`, **preexistentes** y registradas
como tales en `DAY3_IMPLEMENTATION_REPORT.md` (`291 passed, 3 failed (F-038)`).
No las toca esta migración.

### Motor de ratios — comparación contra la base homologada

Se corrió el motor sobre el fixture y se comparó ratio por ratio contra
`catalaxia`:

```
ratios comunes: 32
divergencias en status / valor / moneda / formula_version / ratio_key: 0
solo en catalaxia: ninguno
solo en cnvmig:    4  (CIK 0000021344 = Coca-Cola)
```

Los 32 ratios compartidos son **idénticos hasta el `ratio_key`** —el hash de
identidad del ratio—, no solo en el valor. Los 4 extra son de KO, cuyos hechos
están en el fixture y que nunca se calcularon en la homologada.

El motor además volvió a correr sobre el fixture ya poblado:
`SIN_CAMBIO 36` — idempotente.

### Idempotencia del adaptador

| Corrida | parsed | derived |
|---|---|---|
| 1ª | 2.697 insertados | 2.697 insertados |
| 2ª | 0 insertados · 2.697 reusados | 0 insertados · 2.697 sin cambio |
| 3ª, con un valor mutado a mano | 0 · 2.697 reusados | 0 insertados · 2.696 sin cambio · **1 CONFLICTO** |

El conflicto se reporta y **no se sobrescribe**.

### Sobre los 5 archivos de test que no corren aquí

`test_cnv_authority`, `test_f050_lifecycle_s00_s02`, `test_f051_market_installation`,
`test_f054_aislamiento_emisores` y `test_f055_equivalencia_contextos` están
**sin commitear** en el repo principal y ejercitan código igualmente sin
commitear. Se copiaron al worktree y se corrieron:

| Archivo | Resultado en el worktree | Causa |
|---|---|---|
| `test_f051_market_installation` | **11/11 verde** | — |
| `test_f054_aislamiento_emisores` | 12/14 | las 2 fallas son *asserts sobre el texto fuente* de `s03_parse_ypf.py`, que en el repo principal tiene 66 líneas sin commitear que el worktree no tiene |
| `test_f055_equivalencia_contextos` | no colecta | `s04_normalize.SQL_CTX_CANONICO` no existe en el commit base |
| `test_cnv_authority` | 1/11 | código CNV sin commitear |
| `test_f050_lifecycle_s00_s02` | 7/16 | ídem |

Ninguna falla es de comportamiento: son desfasajes de versión, verificados uno
por uno. Los archivos se retiraron del worktree para no contaminar la línea de
base. **Queda como advertencia W-4: hay que rebasar antes de integrar.**

---

## 5 · Aislamiento

```
                migraciones   034   entity_id   hechos CNV   cik nullable
  catalaxia          34         0        0            0           NO
  cnvmig             35         1        1        2,697          YES
```

Sobre `catalaxia` solo se ejecutaron `pg_dump` de lectura para completar el
fixture (`market_price_daily`, `parsed.units/contexts/concepts`, `fetch_raw.*`,
`identity.*`, `market_*`). Ninguna escritura.

---

## 6 · Lo que esta validación **no** prueba

Dicho explícitamente, porque el silencio en un informe de validación se lee
como cobertura:

- **Un solo emisor.** METR. Nada aquí prueba que los otros 55 `byma_only` se
  comporten igual. La cobertura CNV **no** se amplió, por restricción del ciclo.
- **Ningún ratio CNV.** El motor sigue acotado a SEC. No se calculó ni se
  homologó un solo ratio sobre datos CNV.
- **Ningún piloto negativo.** No se ejecutó, por restricción del ciclo.
- **Ninguna corrección de los 30 candidatos duplicados** ni de las assertions
  históricas. Intactos, por restricción del ciclo.
- **La re-expresión IAS 29 no está resuelta** (W-1). Hoy no hay colisión —0
  casos medidos— pero el diseño no la previene.
- **Los 14 conceptos `CNV_*`/`EPS_*` llevan una unidad incorrecta** (W-2): son
  ratios adimensionales marcados `iso4217:ARS`.
- **Esto corre sobre un fixture, no sobre producción.** La migración 034 no se
  aplicó a la base homologada.

---

## 7 · Dictamen

Lo que el ciclo pedía se cumplió y está verificado de forma independiente: la
guarda de F-061 quedó protegida por un test de mutación que pasa de rojo a
verde por la razón correcta; los 2.697 hechos CNV de Metrogas entraron a la
capa canónica sin pérdidas, sin duplicados, sin colisiones y sin inventar un
solo CIK; los 56 documentos tienen su `sha256` verificado contra el archivo
hoy; y los 32 ratios SEC comparables salieron idénticos hasta el hash de
identidad.

Las cuatro advertencias abiertas son reales pero ninguna invalida lo migrado:
W-1 y W-2 son deuda de diseño sobre datos que hoy no la exhiben, W-3 es la
diferencia entre migrar y actualizar, y W-4 es de integración.

```
CNV_CANONICAL_GATE = PASS_WITH_WARNINGS
```

**Advertencias:** W-1 (re-expresión IAS 29 sin desempate) · W-2 (unidad
incorrecta en 14 conceptos `CNV_*`/`EPS_*`) · W-3 (adaptador INSERT-only) ·
W-4 (worktree desfasado del árbol principal: rebasar antes de integrar).

No es PASS a secas porque W-1 y W-2 tocan la corrección del dato y deben
cerrarse antes de ampliar cobertura. No es BLOCKED porque ninguna afecta lo que
efectivamente se migró ni degrada ninguna garantía vigente.
