# F-061 — ANÁLISIS DE CAUSA RAÍZ

**Severidad: HIGH** · **Estado: ABIERTO, NO CORREGIDO** · **Fecha: 2026-09-01**
Test de aceptación: [`tests/test_f061_ownership.py`](../../../tests/test_f061_ownership.py) — **hoy 4 verdes, 2 rojos a propósito**

---

## 1. El caso, reproducido

El ataque A7 del banco adversario clonó `AssetsCurrent` y `LiabilitiesCurrent`
de **AAPL** (`us-gaap`, USD) bajo el CIK de **GGAL**, re-etiquetados a
`CurrentAssets` y `CurrentLiabilities` (`ifrs-full`, coherentes con la taxonomía
que GGAL declara) y en ARS.

GGAL, banco, no tenía ninguno de los dos tags: `current_ratio` daba
`NO_CALCULABLE`. Después del ataque:

```
current_ratio(GGAL) = 0.893293
current_ratio(AAPL) = 0.8933
```

**El mismo número, dígito por dígito.** Nada en la salida lo delataba: es un
valor plausible para un `current_ratio`, dentro de rango, sin marca.

El ataque corrió sobre una **copia descartable** de la base (`recrear()` +
control `Z` que compara la huella de la base homologada antes y después). Este
audit lo reprodujo en un **schema temporal** con emisores sintéticos `CIK-A` y
`CIK-B` — ningún nombre real interviene, porque la regla que falta no es de
nombres.

---

## 2. Dónde entra el dato

```
SEC EDGAR (RAW)
      │  S02 fetch · sha256 por archivo
      ▼
parsed.facts        fact_id · cik · accession_number · qname · value_numeric
      │             (135.077 filas, 8 CIK)
      │  S04 normalize · agrupa por (cik, accession, qname, context_id, unit_ref)
      ▼
derived.fact        fact_key · entity_key · cik · accession_number · qname
                    · source_fact_ids bigint[]  ◄── el puntero a la evidencia
      │             (88.789 vigentes)
      │
      │  ══════ AQUÍ SE PIERDE LA IDENTIDAD ══════
      ▼
capa de ratios      SELECT ... FROM derived.fact
                     WHERE valid_to IS NULL AND cik = :c
```

El dato entra por `parsed.facts`, que lleva `cik` y `accession_number` reales
del documento. `derived.fact` conserva ambos **y además** `entity_key` **y
además** `source_fact_ids`, el puntero a las filas de `parsed.facts` que lo
originaron.

Toda la información necesaria para detectar el fraude **ya está en la fila**.

---

## 3. Dónde se pierde la identidad

Tres pasos, y el fallo está entre el primero y el segundo.

### Paso 1 — la entidad se resuelve con rigor

`screener_demo.py:287-322` resuelve la entidad por el camino fuerte
(`identity_v1.instrument` → `entity_key`) y, si no hay enlace, exige que el CIK
declarado resuelva a **exactamente una** entidad con assertion `VERIFIED`. Si no,
devuelve `REVIEW_REQUIRED`. Esto está bien hecho.

Resultado: `ent = {"entity_key": ..., "cik": ...}`.

### Paso 2 — la identidad degrada a una igualdad de texto

```python
# screener_demo.py:95 · matriz_producto.py:72 · e2e_producto.py:106 · ratios_inventario.py:66
WHERE valid_to IS NULL AND cik = :c AND is_numeric AND NOT is_dimensional
```

**El `entity_key` se descarta.** Lo que llegó como clave opaca respaldada por una
assertion se convierte en una igualdad de texto sobre una columna que cualquier
escritura puede fijar.

`derived.fact.entity_key` existe, está indexado (`ix_dfact_entidad`), y **la capa
de ratios no lo usa nunca**.

### Paso 3 — la provenance se lee, pero sólo para imprimir

`screener_demo.evidencia_de()` sí sigue `source_fact_ids` hasta `parsed.facts`.
Pero mírese qué selecciona:

```python
SELECT fact_id, taxonomy, namespace, qname, context_id, unit_ref, measure,
       decimals, source_kind, source_file, source_path, source_hash
  FROM parsed.facts WHERE fact_id = ANY(:ids)
```

**No selecciona `cik`.** Ni `accession_number`. La función que existe justamente
para exhibir el origen del dato no trae el campo que dice de quién es. Y su
resultado se adjunta a la salida como decoración: nunca condiciona el cálculo.

> La cadena de provenance está construida, se recorre entera, y no se usa para
> decidir nada. Es un testigo al que nadie le pregunta.

---

## 4. Qué clave relaciona entity / CIK / fact

| nivel | clave | ¿la usa la capa de ratios? |
|---|---|---|
| entidad | `identity_v1.entity.entity_key` (ULID opaco) | para resolver; **no para filtrar** |
| identificador | `identity_v1.identifier` (CIK, con assertion) | sí, para validar el CIK |
| hecho derivado | `derived.fact.entity_key` | **NUNCA** |
| hecho derivado | `derived.fact.cik` | **sí — es el único filtro** |
| evidencia | `derived.fact.source_fact_ids` → `parsed.facts.fact_id` | sólo para mostrar |
| documento | `parsed.facts.cik` + `accession_number` + `source_hash` | **NUNCA leído para validar** |

La relación existe y es completa. El defecto es que el eslabón que se usa para
filtrar (`cik`, texto libre) es el más débil de la cadena, y el más fuerte
(`source_fact_ids` → documento con hash) no se consulta.

---

## 5. La validación que falta

**Regla de pertenencia.** Todo `fact_id` de `derived.fact.source_fact_ids` debe
resolver a una fila de `parsed.facts` del **mismo emisor**, del **mismo filing**
y del **mismo concepto**.

```sql
-- INVARIANTE_PERTENENCIA (declarado en tests/test_f061_ownership.py)
SELECT count(*)
  FROM derived.fact d
  CROSS JOIN LATERAL unnest(d.source_fact_ids) AS s(fid)
  LEFT JOIN parsed.facts p ON p.fact_id = s.fid
 WHERE d.valid_to IS NULL
   AND (p.fact_id IS NULL                          -- puntero huérfano
     OR p.cik              <> d.cik                -- hecho de OTRO emisor
     OR p.accession_number <> d.accession_number   -- hecho de OTRO filing
     OR p.qname            <> d.qname)             -- hecho de OTRO concepto
```

No menciona ninguna empresa, ningún ticker, ningún nombre. Es una regla de
**ownership vía provenance**: exactamente lo que el encargo pide.

### La fila fabricada la viola dos veces, de forma independiente

| campo de la fila fabricada | valor | contra `parsed.facts` |
|---|---|---|
| `cik` | GGAL | los punteros resuelven a filas de **AAPL** → **violación** |
| `entity_key` | el de GGAL (copiado) | no se compara — no hace falta |
| `qname` | `ifrs-full:CurrentAssets` | los punteros llevan `us-gaap:AssetsCurrent` → **violación** |
| `source_fact_ids` | **los de AAPL** | ← la huella del fraude |

Dos detectores distintos la ven. El ataque tendría que haber falsificado también
las filas de `parsed.facts` **y** el `source_hash` del archivo descargado de la
SEC para pasar inadvertido.

### El invariante se cumple hoy — adoptarlo no exige backfill

```
filas derived vigentes .............. 88.789
punteros source_fact_ids ........... 135.077
violación cik(derived) ≠ cik(parsed) ....... 0
violación accession ≠ accession ............ 0
violación qname ≠ qname .................... 0
violación puntero huérfano ................. 0
```

**0 violaciones sobre 135.077 punteros.** La regla se puede activar mañana sin
migrar un solo dato. Verificado por
`test_la_base_de_trabajo_cumple_hoy_el_invariante`.

---

## 6. Por qué el engine acepta insumos de otra entidad

No por un descuido puntual, sino por una **asimetría de diseño**: la capa de
identidad se construyó para ser rigurosa, y la capa de ratios se construyó
asumiendo que los datos que llegan ya son correctos.

Tres razones concretas, en orden de peso:

1. **El filtro es `cik`, no `entity_key`.** Una columna de texto en vez de la
   clave opaca respaldada por assertion.
2. **La provenance no gatea.** `evidencia_de()` la recorre para mostrarla; nada
   la compara.
3. **Los gates existentes están acotados a la corrida.** `C-S04-005` compara
   `derived.fact WHERE run_id = <actual>` contra `parsed.facts WHERE run_id =
   <actual>`. Dentro de una corrida todo cierra. La contaminación —como ya
   demostró **F-054**— aparece en la **siguiente**.

Es el mismo patrón que F-054, un nivel más arriba: allí los `source_fact_ids`
quedaban apuntando a filas de otro emisor por reutilización de ids; acá se
demuestra que **aunque apunten mal, nadie mira**. F-054 cerró la puerta de
entrada; F-061 es que no hay control en la salida.

---

## 7. Qué otros ratios sufren lo mismo

**Los 17 del engine.** Todos toman sus insumos del mismo diccionario
`disp`, producido por una sola función:

```
facts_ultimo_ejercicio(conn, cik)   ──►  disp[tag]  ──►  los 14 fundamentales
                                                    └──►  pe, market_cap, price_to_book
```

Y los cuatro módulos de la capa repiten la misma selección:

```
scripts/engine/screener_demo.py:95
scripts/engine/matriz_producto.py:72
scripts/engine/e2e_producto.py:106
scripts/engine/ratios_inventario.py:66
```

`test_f061_rojo_los_modulos_de_ratios_filtran_por_pertenencia` los enumera y
falla nombrando los cuatro. El fix tiene que llegar a los cuatro, o a un punto
común del que los cuatro dependan — que es lo que el contrato propone
(`ratio_inputs`, §RATIO_CONTRACT.md).

### Y las tres superficies legacy no son auditables en absoluto

```
fact_financials  punteros de provenance: NINGUNO
facts            punteros de provenance: NINGUNO
ratios           punteros de provenance: NINGUNO
screener_gold    punteros de provenance: NINGUNO
```

En S2, S3 y S4 el invariante **no se puede ni siquiera evaluar**: no existe el
puntero al hecho de origen. No es que fallen el control; es que no hay control
posible. Ése es el argumento decisivo para que la superficie canónica sea S1.

---

## 8. El test de aceptación

`tests/test_f061_ownership.py` — **6 tests, 4 verdes y 2 rojos a propósito.**

| test | hoy | qué demuestra |
|---|---|---|
| `test_el_detector_encuentra_los_hechos_ajenos` | **verde** | el invariante marca los 2 punteros ajenos |
| `test_control_positivo_los_hechos_legitimos_no_se_marcan` | **verde** | y no marca los 3 legítimos — sin esto podría pasar marcándolo todo |
| `test_la_correccion_propuesta_excluye_los_hechos_ajenos` | **verde** | con la guarda puesta, B se queda sólo con su hecho propio |
| `test_la_base_de_trabajo_cumple_hoy_el_invariante` | **verde** | 0 de 135.077 → adoptable sin backfill |
| `test_f061_rojo_la_seleccion_actual_rechaza_hechos_ajenos` | **ROJO** | **criterio de aceptación** |
| `test_f061_rojo_los_modulos_de_ratios_filtran_por_pertenencia` | **ROJO** | **criterio de aceptación** — alcance: los 4 módulos |

Salida real del test rojo:

```
AssertionError: la seleccion adopto hechos del emisor A bajo el cik de B:
{'CurrentLiabilities', 'CurrentAssets'}.
Falta la guarda de pertenencia sobre source_fact_ids (ver GUARDA_PERTENENCIA).
```

### La unión causal

El test **no copia** la consulta: la **extrae del código vivo** con
`inspect.getsource(screener_demo.facts_ultimo_ejercicio)` y le sustituye los
nombres de tabla por los del schema temporal. Si alguien cambia la consulta, el
test cambia de resultado. Ésa es la relación causal entre el test y la garantía
— la misma técnica que se usó en T3/T4/T5 del ciclo CNV.

Y `test_la_correccion_propuesta_excluye_los_hechos_ajenos` corre **esa misma
consulta extraída** con la guarda añadida, y pasa. Es decir: **el fix ya está
demostrado antes de escribirse.**

### El fix, literal

```sql
   AND NOT EXISTS (
         SELECT 1 FROM unnest(d.source_fact_ids) AS s(fid)
          LEFT JOIN parsed.facts p ON p.fact_id = s.fid
          WHERE p.fact_id IS NULL
             OR p.cik              <> d.cik
             OR p.accession_number <> d.accession_number
             OR p.qname            <> d.qname)
```

Declarado como `GUARDA_PERTENENCIA` en el test para que la implementación lo
reutilice literalmente y no lo reinterprete.

---

## 9. Lo que este análisis NO cierra

**F-061 queda ABIERTO.** El encargo prohíbe implementar, y cerrarlo exige que
los dos tests rojos pasen. Hoy fallan, que es lo correcto.

Tres cosas que la guarda **no** resuelve y que conviene no confundir:

| ataque | ¿lo detiene la guarda? | quién debería |
|---|---|---|
| A7 · hecho de otra empresa | **sí** | la guarda |
| A2a · signo de `Equity` invertido | **no** | la identidad `Activo = Pasivo + PN` (A2b sí lo vio) |
| A8 · falta el tag preferido, cae al fallback con otro valor | **no** | es comportamiento declarado, no un defecto |

La guarda protege contra hechos **ajenos**, no contra hechos **propios y
equivocados**. Para eso el contrato exige, por separado, los controles de
identidad contable (§Test Contract, T3).

---

## 10. Correr los tests

```bash
# los seis
python -m pytest tests/test_f061_ownership.py -v
   -> 4 passed, 2 failed   (correcto mientras F-061 esté abierto)

# la suite sin los rojos, mientras dure
python -m pytest tests/ -k "not f061_rojo"

# criterio de cierre de F-061
python -m pytest tests/test_f061_ownership.py
   -> 6 passed
```

Ningún test escribe en datos persistidos: el schema temporal se crea y se
destruye en el fixture. Verificado tras la corrida —
`information_schema.schemata` sin `f061_tmp`, `derived.fact` en 88.789 y
`parsed.facts` en 135.077, sin cambios.
