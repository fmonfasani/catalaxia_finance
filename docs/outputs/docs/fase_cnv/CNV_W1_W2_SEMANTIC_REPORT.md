# CNV — CIERRE SEMÁNTICO W-1 / W-2

**Fecha:** 2026-09-02
**Alcance:** análisis y fixtures. **No se implementó nada.** El adaptador, el
esquema y los datos migrados quedaron como estaban.
**Base:** `cnvmig` (fixture aislado) · `catalaxia` no se tocó
**Fixtures:** `tests/test_w1_w2_semantica.py` — 11/11 en verde
**Suite completa:** 244 passed · 3 failed (F-038, preexistentes) · 1 skipped

---

# W-1 · IDENTIDAD DE UN HECHO ECONÓMICO

## 1.0 · Lo primero que hay que decir: la premisa de W-1 estaba mal planteada

W-1 se abrió como *"la re-expresión IAS 29 podría crear dos hechos vigentes"*.
Al medirlo, el riesgo resultó ser otro y estar en otro lado.

**No hay una sola colisión por re-expresión en todo el corpus CNV:**

| Medición | Resultado |
|---|---|
| CUITs · filas · documentos en `cnv_estados_norm` | 72 · 106.421 · 2.453 |
| `(cuit, concepto, period_end, perímetro)` en más de un documento | **0** |
| `valor_comparativo` poblado | **0 filas** |
| `fecha_reexpresion` distinta de `period_end` | **0 de 106.421** |
| Períodos distintos por documento | **1** en los 2.453 |

`fecha_reexpresion` **no marca una re-expresión**: es una copia literal de
`period_end`, en el 100% de las filas. No aporta información.

La razón de los ceros no es que la re-expresión no ocurra. Es que **el
comparativo nunca entra**: cada documento aporta un solo período, y la columna
que lo guardaría está vacía. El riesgo no se evita: no se ve.

## 1.1 · Y en SEC, el mismo hueco tiene otra forma

En SEC los comparativos **sí** se ingestan, y quedan estampados con el período
del filing:

| Medición sobre `derived.fact` SEC | Resultado |
|---|---|
| Hechos no dimensionales | 37.047 |
| Con `end_date`/`instant_date` **≠** `report_period` | **18.464 (49,8%)** |
| Desfase más frecuente | 365 días (7.239) · 730-731 días (6.750) |

Dentro de un solo filing de KO (FY2024, 2.548 hechos) `report_period` vale
`2024-12-31` para todos, mientras las fechas reales van de **2015-12-31 a
2025-02-18**.

**`report_period` es un sello del documento, no el período del hecho.**

### Lo que ya protege

`ratio_inputs.py:82-83` exige que la fecha real iguale al `report_period`:

```sql
AND COALESCE(alias.instant_date::text, alias.end_date::text)
    = alias.report_period::text
```

Filtra el 54,4% de los hechos SEC. **El motor nunca toma un comparativo.** Es
una protección real y ya existe.

### Cuántos duplicados hay hoy, y si alguno llega al motor

Quitando el `accession` de la clave:

| | hechos | claves sin accession | colisiones |
|---|---|---|---|
| CNV | 2.697 | 2.697 | **0** |
| SEC | 133.902 | 133.709 | **193** |

Los 193 son el caso real de W-1 vivo hoy. Su desenlace:

| Miembros del grupo que pasan la guarda de fecha | Grupos | de ellos con valor distinto |
|---|---|---|
| 0 | 64 | 2 |
| 1 | **129** | 2 |
| 2 o más | **0** | — |

**Ningún grupo deja dos candidatos al motor.** La selección es determinista
hoy. W-1 es un defecto de la capa de almacenamiento, no del producto.

## 1.2 · Las cuatro preguntas, respondidas

### (1) Qué constituye la identidad de un hecho económico

```
entity_id · concepto · perímetro · (clase de período, inicio, fin)
          · unidad · fecha de medición
```

Tres piezas que hoy **no** están en la clave:

- **El período completo, no el cierre.** `context_id` es `PERÍMETRO@cierre`.
  Un flujo de tres meses y uno de doce que terminan el mismo día son el mismo
  `context_id`.
- **La clase de período.** El adaptador escribe `period_kind='INSTANT'` para
  todo. Medido: **1.002 de 2.697 hechos CNV (37,2%)** son conceptos de flujo
  —`Revenue`, `NetIncome`, `CF_*`, `EBITDA`…— grabados como instantes sin
  `start_date`.
- **La fecha de medición.** Bajo IAS 29 toda cifra se expresa en el poder
  adquisitivo del cierre. El mismo hecho en moneda de dic-2023 y en moneda de
  dic-2025 son **dos mediciones**, no una corrección de la otra.

Que los flujos CNV son acumulados —no del trimestre— está medido en METR
CONSOLIDADO: `Revenue` 205.186 → 504.193 → 898.642 → **1.217.305** millones
para los cierres de marzo, junio, septiembre y diciembre de 2025. Es la serie
acumulada del ejercicio, guardada como cuatro instantes sin duración.

### (2) Qué constituye una ocurrencia de ese hecho en un documento

```
identidad económica · documento (accession) · momento de publicación
```

Es lo que hoy identifica `fact_key = sha256(entity_key|accn|qname|ctx|unit)`.
**Su forma es correcta: es una clave de ocurrencia.** Lo que falta no es
arreglarla, es que exista además la otra.

### (3) ¿El accession debe formar parte de `fact_key`?

**Sí.** Las dos alternativas fallan, y fallan de maneras opuestas:

| Clave | Falla |
|---|---|
| **sin** accession | dos ocurrencias legítimas colapsan; la segunda pisa a la primera en la PK. Pérdida silenciosa. |
| **solo** con accession (hoy) | dos ocurrencias del mismo hecho conviven igualmente vigentes, sin orden entre ellas. Ambigüedad silenciosa. |

No hay una clave única que resuelva las dos. **Hacen falta dos claves y una
relación de vigencia entre ellas.**

### (4) Cómo modelar original / re-expresión / supersesión

La distinción que el modelo debe hacer, y hoy no hace:

| Caso | Qué es | Cómo debe modelarse |
|---|---|---|
| **Original** | primera publicación | ocurrencia efectiva de su `econ_key` |
| **Re-expresión IAS 29** | el mismo hecho en **otra unidad** de poder adquisitivo | **NO supersede.** Distinta `fecha_medición` ⇒ distinta unidad ⇒ otro hecho, igualmente válido |
| **Supersesión / restatement** | corrección del mismo hecho, **misma unidad** | el documento posterior supersede al anterior |
| **Mismo hecho en otro documento** | comparativo | misma `econ_key`, misma unidad, misma medición: **una sola efectiva** |

Confundir los dos del medio es el error grave: tratar una re-expresión IAS 29
como corrección **borra la serie histórica en moneda de origen**; tratar un
restatement como re-expresión **deja dos verdades vigentes**.

## 1.3 · Contrato propuesto

```
fact_key      = sha256(entity_key | accession | qname | context_id | unit)
                identidad de la OCURRENCIA.        [ya existe, se conserva]

econ_key      = sha256(entity_id | qname | perimetro | period_kind |
                       start_date | end_date | unit_measure | measurement_date)
                identidad del HECHO ECONÓMICO.     [nuevo]

effective_from / effective_to      vigencia de la ocurrencia dentro de su econ_key
supersedes  -> fact_key            a qué ocurrencia reemplaza (NULL si es original)
```

Con dos columnas nuevas de período y unidad que hoy no se escriben:
`period_kind` real (`DURATION`/`INSTANT`), `start_date`, y `measurement_date`.

### El invariante que impide el modo de falla

```sql
-- A lo sumo UNA ocurrencia efectiva por hecho económico.
SELECT econ_key, count(*)
  FROM derived.fact
 WHERE effective_to IS NULL
 GROUP BY 1 HAVING count(*) > 1;     -- debe dar 0 filas
```

Es la condición que W-1 pedía: **impide que una re-expresión legítima se
convierta en silencio en dos hechos igualmente vigentes.** Y por construcción
no bloquea la re-expresión legítima, porque la `fecha_medición` entra en la
`econ_key`: las dos mediciones son dos hechos, cada uno con su única
ocurrencia efectiva.

## 1.4 · Fixtures

`tests/test_w1_w2_semantica.py`, 6 tests. Los dos que cargan el peso:

**A — el mismo hecho en dos documentos.** `Revenue` CONSOLIDADO 2023, publicado
en el balance 2023 (100.000, moneda dic-2023) y re-expresado en el balance 2025
(315.000, moneda dic-2025).

- `fact_key` da dos claves distintas → **ambas vigentes, ningún orden**
- `econ_key` con `measurement_date` → **dos hechos distintos**, correcto
- `econ_key` **sin** `measurement_date` → **la misma clave**: es lo que permite
  emparejarlos y ordenarlos

**B — dos hechos legítimamente distintos.** `Revenue` del trimestre
(oct–dic 2025, 318.663) y del ejercicio (ene–dic 2025, 1.217.305). Mismo
emisor, concepto, cierre, perímetro **y documento**.

- mismo `context_id` → **misma `fact_key`** → en `derived.fact` la PK haría que
  uno de los dos **se pierda**
- `econ_key` con `(kind, inicio, fin)` → dos hechos distintos

B no es ambigüedad: es pérdida. Y es el caso que aparece apenas se extraiga el
comparativo o se separe el trimestre del acumulado.

---

# W-2 · UNIDADES DE LOS 14 CONCEPTOS `CNV_*` / `EPS_*`

## 2.0 · La evidencia, sin usar el nombre

Tres fuentes independientes, ninguna es el nombre del concepto.

**(a) El contrato del parser.** `job5_v2_extract_eeff.py` ya los separa
estructuralmente:

```python
CODIGOS   = { ... }                       # 37 conceptos monetarios
RATIOS_CNV = {"8000006": "liquidez", ..., "8000029": "rotacion_activos"}  # 12
NO_FACTOR = {"8000000", "8000001"}        # EPS: no se multiplica por la escala
# "EPS_basico y EPS_diluido ya están en pesos por acción
#  (no siguen la escala del documento)"
```

**(b) El documento.** La CNV publica `<propiedad id="..." etiqueta="...">valor</propiedad>`,
donde el valor es un **código** y la etiqueta lleva el significado
(`<propiedad id="AMEMoneda" etiqueta="Dólar (E.U.A.)">36</propiedad>`). De ahí
viene el `'7'` de `extraer_moneda()`: es un código, nunca fue una moneda ISO.

**(c) Recálculo sobre 2.453 documentos.** Para cada ratio publicado se
recalculó la magnitud desde los montos del **mismo documento** y se comparó
contra la fracción y contra el porcentaje:

```
coincide con la FRACCIÓN: 15.843     con el PORCENTAJE: 183      →  87:1
en 8 de los 12 ratios el porcentaje NO coincide ni una sola vez
```

Y las medianas lo confirman sin ambigüedad: `roe` 0,060 · `roa` 0,030 ·
`margen_neto` 0,060. Si fueran porcentajes serían 6,0 / 3,0 / 6,0.

**Los 12 son fracciones. Ninguno es un porcentaje.** Cualquier ×100 pertenece a
la capa de presentación, nunca al hecho.

## 2.1 · Clasificación

| Concepto | Naturaleza económica | monetary | per-share | percentage | ratio | Unidad canónica | Provenance original |
|---|---|:--:|:--:|:--:|:--:|---|---|
| `CNV_liquidez` | AC / PC | no | no | no | **sí** | `xbrli:pure` | escala del doc (no aplicada) |
| `CNV_prueba_acida` | (AC − Inv) / PC | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_solvencia` | PN / Pasivo | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_endeudamiento` | Pasivo / PN | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_apalancamiento` | Activo / PN | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_rotacion_activos` | Ventas / Activo | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_cobertura_intereses` | EBIT / Intereses | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_deuda_fin_ebitda` | Deuda fin. / EBITDA | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_ebitda_costos_fin` | EBITDA / Costos fin. | no | no | no | **sí** | `xbrli:pure` | ídem |
| `CNV_roe` | Resultado / PN — **tasa** | no | no | no¹ | **sí** | `xbrli:pure` | ídem |
| `CNV_roa` | Resultado / Activo — **tasa** | no | no | no¹ | **sí** | `xbrli:pure` | ídem |
| `CNV_margen_neto` | Resultado / Ventas — **tasa** | no | no | no¹ | **sí** | `xbrli:pure` | ídem |
| `EPS_basico` | Resultado por acción | **sí** | **sí** | no | no | `iso4217:ARS/xbrli:shares` · `unit_kind=DIVIDED` | pesos por acción, **sin** escala (`NO_FACTOR`) |
| `EPS_diluido` | ídem, diluido | **sí** | **sí** | no | no | `iso4217:ARS/xbrli:shares` · `unit_kind=DIVIDED` | ídem |

¹ Son tasas que la convención muestra como %, pero **el dato publicado es la
fracción**. La unidad es adimensional; el ×100 es presentación.

## 2.2 · Cómo quedaron migrados — la medición

**662 de 2.697 hechos (24,5%)** llevan una unidad que no les corresponde:

| tag | n | `decimals` | `unit_measure` | `currency` | valor p50 |
|---|--:|---|---|---|--:|
| `CNV_liquidez` | 56 | −3, −6 | `iso4217:ARS` | ARS | 0,555 |
| `CNV_roe` | 56 | −3, −6 | `iso4217:ARS` | ARS | 0,070 |
| `EPS_basico` | 56 | −3, −6 | `iso4217:ARS` | ARS | 1,960 |
| *(y 11 conceptos más)* | | | | | |

Dos errores, no uno:

1. **`unit_measure` / `currency`.** Un número adimensional declarado como pesos.
2. **`decimals`.** El adaptador mapea la escala del documento a `decimals`. Pero
   `decimals` es una **aserción de precisión**, no un factor de escala. Un
   consumidor que la honre redondea `CNV_liquidez = 0,555` al millón más
   cercano: **0**. El fixture lo ejecuta y lo verifica.

El error de `decimals` es más grave que el de la moneda, porque destruye el
valor en vez de solo describirlo mal.

## 2.3 · El engine no los distingue — demostrado

`ratio_engine.py:225-231` tiene el único control de unidad que existe: exige
que todos los fundamentals compartan `currency`.

```python
monedas = {f["currency"] for c, (_t, f) in elegidos.items() ...}
if len(monedas) != 1:
    return no("los fundamentals mezclan monedas ...")
```

`unit_measure` se lee (línea 169) y **se guarda en provenance sin validarse
jamás**. Un ratio adimensional marcado `ARS` pasa ese control exactamente igual
que un monto en pesos. El fixture lo comprueba: las cuatro naturalezas
—monetaria, ratio, tasa, por-acción— colapsan en una sola clase.

## 2.4 · La buena noticia: el modelo ya lo soporta

No hace falta cambiar el esquema. Los hechos SEC ya usan el vocabulario
completo, en la misma tabla:

| `unit_kind` | hechos SEC |
|---|--:|
| `SIMPLE` | 122.517 |
| `DIVIDED` | **1.236** |
| (null) | 10.149 |

```
EarningsPerShareBasic   kind=DIVIDED  measure=iso4217:USD/xbrli:shares  cur=USD  dec=2
xbrli:pure                                                                    5.356 hechos
iso4217:USD/xbrli:shares                                                      1.382 hechos
```

**El adaptador simplemente no usó ese vocabulario. La corrección es un mapeo,
no una migración de esquema.**

## 2.5 · Fixtures

5 tests. Cuatro hechos —`Revenue` monetario, `CNV_liquidez` ratio,
`CNV_margen_neto` tasa, `EPS_basico` por acción— en las dos codificaciones:

| Test | Resultado |
|---|---|
| la codificación actual no distingue nada | las 4 naturalezas → `monetary` |
| el vocabulario canónico sí las distingue | `monetary` / `adimensional` / `adimensional` / `per_share` |
| la guarda de moneda acepta un adimensional | una sola moneda: las 4 pasan |
| `decimals` de escala destruye el ratio | `round(0,555, −6) = 0` |

---

# 3 · Lo que este informe NO cierra

- **La fórmula de `roe`, `roa`, `margen_neto` y `cobertura_intereses`.** El
  recálculo no reproduce el valor publicado en la mayoría de los documentos
  (`roe`: 420 de 2.306). Es la discrepancia ya conocida. **Es un problema de
  fórmula, no de unidad** —el porcentaje coincide todavía menos— y queda
  abierto.
- **`tipo` = 'A'/'P' no es confiable.** Los tres documentos trimestrales de
  METR de 2025 están marcados `'A'`. El propio parser advierte que la regla
  anterior adivinaba.
- **Nada se implementó.** Ni el contrato de W-1 ni el mapeo de W-2.

---

# 4 · Dictamen

**W-1.** Las cuatro preguntas quedaron respondidas con mediciones, no con
criterio: la identidad económica necesita período completo, clase de período y
fecha de medición; la ocurrencia necesita el documento; el `accession` debe
quedar en `fact_key` porque las dos alternativas fallan de maneras opuestas; y
la re-expresión IAS 29 **no** es una supersesión. Los fixtures A y B están
construidos y exhiben los dos modos de falla —ambigüedad y pérdida—. El
contrato propuesto trae el invariante que W-1 pedía.

```
W1 = PASS
```

**W-2.** Los 14 conceptos quedaron clasificados con tres fuentes de evidencia
independientes del nombre, incluido un recálculo sobre 2.453 documentos que
descarta el porcentaje 87 a 1. Los fixtures demuestran que la codificación
actual colapsa las cuatro naturalezas en una, que el único control existente no
lo ve, y que el vocabulario canónico —ya poblado por 1.236 hechos SEC
`DIVIDED` y 5.356 `xbrli:pure`— las separa.

```
W2 = PASS
```

**Ambos PASS significan que la pregunta semántica quedó cerrada. No que el dato
esté bien.** Lo que la medición dejó a la vista:

| | hechos afectados | de 2.697 |
|---|--:|--:|
| unidad incorrecta (`iso4217:ARS` sobre adimensionales) | 662 | 24,5% |
| `decimals` de escala monetaria sobre adimensionales | 662 | 24,5% |
| flujos grabados como `INSTANT` sin `start_date` | 1.002 | 37,2% |
| `fact_key` que no distingue trimestre de acumulado | todos | 100% |

Integrar hoy metería esos 662 hechos mal unificados y esos 1.002 flujos
aplanados en la capa canónica, con una clave que no puede separar un trimestre
de un ejercicio. Ninguno de los cuatro puede corregirse dentro de este ciclo,
que prohíbe implementar.

```
INTEGRATION_READY = NO
```

**Falta, en este orden:**

1. `period_kind` real, `start_date` y `measurement_date` en el adaptador — sin
   eso `econ_key` no se puede construir.
2. Mapeo de unidades: `xbrli:pure` para los 12 ratios,
   `iso4217:ARS/xbrli:shares` + `DIVIDED` para los dos EPS, y `decimals`
   desacoplado de la escala del documento.
3. `econ_key`, `effective_from/to`, `supersedes` y el invariante de unicidad.
4. Re-migrar los 2.697 hechos con la codificación corregida y volver a correr
   la auditoría independiente.

Ninguno de los cuatro es grande. Los tres primeros son el adaptador; el cuarto
es una corrida. Lo que los hacía invisibles era que nadie había mirado la
unidad ni la duración: eso ya está hecho.
