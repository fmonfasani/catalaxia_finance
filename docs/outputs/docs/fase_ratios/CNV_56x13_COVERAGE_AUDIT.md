# CNV 56 × 13 — AUDITORÍA DE COBERTURA COMERCIAL

**2026-09-01** · auditoría independiente · **solo lectura** · sin commits
Ninguna base modificada. Reproducible con los comandos del anexo.

Matrices: [`CNV_56x13_COVERAGE_MATRIX.csv`](CNV_56x13_COVERAGE_MATRIX.csv) ·
[`CNV_56x13_QUALITY_MATRIX.csv`](CNV_56x13_QUALITY_MATRIX.csv) ·
evidencia cruda: `CNV_56x13_EVIDENCE.json`

---

# CNV_56x13_COVERAGE_GATE = **FAIL**

```
CANONICAL_COMMERCIAL_COVERAGE  =     0 / 728   (0,0 %)
CANONICAL_PROVENANCE_COVERAGE  =     0 / 728   (0,0 %)
HOMOLOGATED_COVERAGE           =     0 / 728   (0,0 %)
LEGACY_ONLY_COVERAGE           =   486 / 728   (66,8 %)
```

**El `FAIL` no es de la auditoría —que se ejecutó entera— sino de la cobertura
auditada.** Ninguna de las 728 celdas puede mostrarse hoy como dato canónico de
Catalaxia. Y no es por un defecto: es el sistema negándose a mostrar lo que no
puede respaldar.

---

## 0. Dos discrepancias de premisa, antes de la matriz

El encargo pide detenerse y reportar antes de fabricar. Hay dos cosas que no
son como el enunciado supone.

### 0.1 · «los 13 ratios del contrato vigente» — el contrato vigente no tiene 13

`RATIO_CONTRACT.md` v1.0 (el vigente) declara **17 ratios prioritarios + 3
componentes = 20 `canonical_id`**. No 13.

Existen **tres** listas de 13 distintas en el proyecto:

| origen | los 13 |
|---|---|
| **`RATIO_CONTRACT_v0_13ratios.md`** | Current, Quick, Gross Margin, Operating Margin, Net Margin, ROE, ROA, D/E, EPS, P/E, P/B, P/S, EV/EBITDA |
| `s4_ensamblar.py` (screener CNV legacy) | ROE, ROA, MargenNeto, DeudaEBITDA, EPS, FCF/CE, Payout, CAGR EPS 5y, PER, PriceBook, PriceSales, Max52w, Min52w |
| `b5_metricas.py` (pipeline BYMA) | precio_usd, per, max_52w, dif_max_52w, min_52w, dif_min_52w, deuda_ebitda, eps_anual, crecimiento_eps_5y, margen_neto, roe_5y, fcf_market_cap, payout |

**Decisión de la auditoría:** se usan los 13 de **`RATIO_CONTRACT_v0_13ratios.md`**,
porque es el único **documento de contrato** del proyecto con exactamente 13, y
porque **12 de sus 13 tienen `canonical_id` en el contrato vigente**. El
decimotercero —`quick_ratio`— no figura en la lista prioritaria vigente pero
está implementado en `ratio_defs.RATIOS`, así que tampoco es un ratio inventado.

Se documenta por celda en la columna `en_contrato_vigente`. **No se inventó
ningún ratio.**

### 0.2 · «56 empresas CNV» — son 56, pero no son lo que el nombre sugiere

El universo existe y es consistente: **56 filas, 56 CUIT distintos**, coincidente
en seis tablas legacy (`screener`, `screener_gold`, `entity_validacion`,
`per_ttm`, `ratios_ttm`, `gate_roe`) y en `mercado_byma`.

Pero su semántica es la que su nombre dice: **`grupo = 'byma_only'` son las
empresas que cotizan SÓLO en BYMA — las que NO tienen ADR.** Y de ahí se sigue
todo lo demás:

```
sin ADR  →  sin presentación ante la SEC  →  sin CIK  →  sin fundamentals canónicos
```

Los tres CUIT autoritativos del sistema (YPF, TGS, CEPU) **no pertenecen a este
universo**: están en `grupo = 'adr'` (17 empresas). El universo de 56 y la
superficie canónica son, por construcción, disjuntos.

---

## 1. Universo — los 56, medidos contra la identidad canónica

```
CUIT del universo legacy ........................ 56
presentes en identity_v1 ........................  0
con CUIT autoritativo ...........................  0
con entidad y CIK ...............................  0
con artefactos CNV en fetch_raw .................  0
con instrumento ligado a entidad ................  0
```

**Cero. No «pocos»: cero.** Ni uno de los 56 CUIT existe en `identity_v1`.

### Y sin embargo, el precio sí está

```
tickers byma_only .................................. 56
con instrumento en market_instruments .............. 54
con precios en market_price_daily .................. 53
con enlace instrumento → entidad ...................  0
```

**53 de 56 tienen precio en la superficie canónica de Market.** Lo que falta no
es el dato de mercado: es la prueba de a qué entidad pertenece esa especie
cotizante.

Ése es exactamente el join por ticker que el sistema se niega a hacer —el mismo
que en una etapa anterior del proyecto hizo aparecer precios de Coursera como
argentinos. El precio existe y no se usa, a propósito.

### Estado de identidad, por columna

| dimensión | valor | consecuencia |
|---|---|---|
| `entity_key` | **ninguno** | no hay a quién atribuir un ratio |
| CUIT en `identity_v1` | 0/56 | el CUIT legacy no fue promovido al modelo canónico |
| CIK | 0/56 | esperado: sin ADR no hay filing SEC |
| LEI | 0/56 | — |
| instrumento (Market) | 54/56 existen, **0 ligados** | el enlace es el eslabón faltante |
| elegibilidad CNV | 0/56 | ningún CUIT autoritativo ⇒ el fetcher los bloquea |

---

## 2. La matriz 56 × 13 = 728 celdas

| estado | celdas | % |
|---|---:|---:|
| **CALCULADO** | **0** | **0,0 %** |
| `LEGACY_ONLY` | 486 | 66,8 % |
| `IDENTITY_BLOCKED` | 242 | 33,2 % |
| `NOT_CALCULABLE` | 0 | — |
| `NO_DATA` | 0 | — |
| `NO_MARKET_DATA` | 0 | — |
| `AMBIGUO` | 0 | — |
| `NOT_TESTED` | 0 | — |

Los estados no usados están en cero porque **el bloqueo de identidad es
anterior a todos ellos**. No se puede decir «falta la deuda financiera» de una
entidad que no existe en el modelo canónico: la pregunta no llega a plantearse.

### Regla de clasificación aplicada

```
S1 tiene valor                     → CALCULADO          (0 celdas)
S1 no · legacy sí tiene valor      → LEGACY_ONLY        (486)
S1 no · legacy tampoco             → IDENTITY_BLOCKED   (242)
```

En las 728 el motivo canónico es el mismo, y está escrito en cada fila:

> *el CUIT no existe en identity_v1: el universo byma_only son emisores SIN ADR,
> por lo tanto sin CIK y sin filings SEC* — más el bloqueo específico del ratio.

---

## 3. Por qué ninguna celda es `CALCULADO`

La definición del §5 del encargo exige nueve condiciones. **Fallan las nueve, y
por dos causas independientes que se acumulan.**

### Causa A · la entidad no existe en el modelo canónico (afecta 728/728)

Sin `entity_key` no hay a quién atribuir el ratio, no hay `derived.fact` que
consultar y no hay provenance posible.

### Causa B · el ratio no está implementado (afecta 10 de los 13)

Aun si los 56 estuvieran en identity con fundamentals, **el motor canónico
calcula cuatro ratios**, y de los 13 auditados sólo tres tienen implementación:

| ratio | ¿implementado en S1? | bloqueo adicional |
|---|---|---|
| `eps` | **sí** (`eps_v1`) | — |
| `pe` | **sí** (`pe_v1`, `FY`) | — |
| `pb` | **sí** (`pb_v1`) | — |
| `current_ratio` | no | — |
| `quick_ratio` | no | además no figura en el contrato vigente |
| `gross_margin` | no | — |
| `operating_margin` | no | — |
| `net_margin` | no | — |
| `roa` | no | — |
| `ps` | no | — |
| `roe` | no | **decisión D4 abierta** — 4 variantes conviviendo |
| `debt_to_equity` | no | **decisión D5 abierta** — 3 numeradores distintos |
| `ev_ebitda` | no | **decisión D3 abierta** — 12 candidatos de D&A |

`ev_sales`, el cuarto ratio implementado, **no está entre los 13 auditados.**

Consecuencia: aun resolviendo la identidad de las 56, el techo inmediato sería
**3 de 13 ratios = 168 celdas**, no 728.

---

## 4. `LEGACY_ONLY` — qué existe fuera de la superficie canónica

486 celdas tienen valor en legacy. **No se copian, no se recomiendan y no se
convierten en canónicas.**

| ratio | legacy | tabla · columna | superficie |
|---|---:|---|---|
| `roa` | **56/56** | `screener_gold.roa` | S3 |
| `net_margin` | 55/56 | `screener_gold.margen_neto` | S3 |
| `roe` | 52/56 | `screener_gold.roe` | S3 |
| `ps` | 52/56 | `screener_gold.p_sales` | S3 |
| `eps` | 50/56 | `screener.EPS` | S4 |
| `gross_margin` | 49/56 | `screener_gold.margen_bruto` | S3 |
| `operating_margin` | 49/56 | `screener_gold.margen_operativo` | S3 |
| `pb` | 49/56 | `screener_gold.p_book` | S3 |
| `ev_ebitda` | 40/56 | `screener_gold.ev_ebitda` | S3 |
| `pe` | 34/56 | `screener_gold.per` | S3 |
| `current_ratio` | **0/56** | — | — |
| `quick_ratio` | **0/56** | — | — |
| `debt_to_equity` | **0/56** | — | — |

Tres de los 13 no existen **en ninguna** superficie para este universo: ni
canónica ni legacy.

### Qué respaldo tienen esos 486 valores

| | |
|---|---|
| provenance hasta el documento | **ninguna.** `screener_gold` y `screener` no tienen columna de puntero a hecho de origen, ni hash, ni accession |
| certificación legacy | 54/56 `CERTIFICADO`, 2 `interno-ok` — es el sello **del pipeline legacy**, con su propia suite de identidades contables |
| fiabilidad de la capitalización | **16/56 con `mcap_confiable = 0`** — y de ella dependen P/E, P/B, P/S y EV/EBITDA |
| datos CNV crudos disponibles | 85.922 filas normalizadas, 79.133 documentos, 6.000 presentaciones, 191 dividendos — **todo en SQLite**, nada en `fetch_raw` canónico |

El sello `CERTIFICADO` del legacy **no es homologación**. Certifica que pasó
las identidades contables del pipeline antiguo; no que el número se pueda seguir
hasta un documento.

---

## 5. Provenance

```
COMPLETE     0 / 728
INCOMPLETE   0 / 728
NONE       728 / 728
```

No se infirió provenance de la existencia de un valor: las 486 celdas
`LEGACY_ONLY` **tienen valor y no tienen cadena**, que es precisamente la
distinción que esta auditoría existe para hacer.

---

## 6. Validación

| clasificación | celdas | % |
|---|---:|---:|
| `HOMOLOGATED` | **0** | 0,0 % |
| `TESTED` | 0 | 0,0 % |
| `LEGACY_ONLY` | 486 | 66,8 % |
| `CONTRACT_ONLY` | 186 | 25,5 % |
| `NOT_VALIDATED` | 56 | 7,7 % |

`CONTRACT_ONLY` = el ratio está definido en el contrato vigente pero no hay
valor ni canónico ni legacy para esa empresa. `NOT_VALIDATED` = las 56 celdas de
`quick_ratio`, que ni siquiera figura en el contrato vigente.

**La homologación del vertical slice —25/25 con desvío 1,59e-7— no se
extrapola.** Cubre 8 emisores que **no pertenecen a este universo**. Aplicarla
acá sería exactamente el error que el encargo prohíbe.

---

## 7. Discrepancias

```
celdas con valor en S1 y en legacy simultáneamente:  0
discrepancias:                                        0
```

No hay ninguna que comparar: los conjuntos son disjuntos. Cero discrepancias
**no significa acuerdo** — significa que no hay solapamiento donde pueda haber
desacuerdo. Distinción que importa para no leer este cero como una validación.

---

## 8. Casos especiales

| caso | qué se encontró |
|---|---|
| **Bancos** | El universo `byma_only` incluye bancos regionales sin ADR. Su cobertura legacy es la peor en los ratios que dependen de `Revenue` — el mismo límite del modelo contable que ya se midió en Galicia y Macro |
| **ADR** | **Ninguno.** `byma_only` los excluye por definición. Los 17 con ADR —incluidos los 3 CUIT autoritativos— están en otro grupo |
| **Sin instrument linkage** | **56/56.** 54 tienen instrumento en Market y **ninguno** ligado a una entidad. El eslabón faltante más concreto de todo el universo |
| **Múltiples CUIT / AMBIGUO** | 0 casos: los 56 CUIT son distintos entre sí. Los 4 CUIT ambiguos conocidos (Galicia, AA2000, YPF Energía Eléctrica, Supervielle) están en el grupo ADR, no acá |
| **EPS ≤ 0** | No evaluable canónicamente. En legacy, 6 de 56 no tienen EPS |
| **Dependientes de EBITDA** | `ev_ebitda` — bloqueado por D3 aun con identidad resuelta. 40/56 en legacy |
| **Dependientes de TTM** | 10 de los 13 son de flujo. El motor canónico no tiene TTM: aun implementados, saldrían `FY` |
| **Sólo legacy** | 486 celdas. Ver §4 |

---

## 9. Las dos cifras comerciales, separadas

### A · `CANONICAL_COMMERCIAL_COVERAGE = 0 / 728`

Celdas que Catalaxia puede mostrar **hoy, desde S1, con provenance suficiente**.

Cero. Sin matices.

### B · `DISCLOSED_COVERAGE = 486 / 728` (66,8 %)

Celdas que **podrían** mostrarse si se etiquetan explícitamente como
legacy/referencia, sin provenance verificable y con la advertencia de que
provienen de un pipeline distinto del que respalda el producto.

**No deben mezclarse.** Una pantalla que mostrara 486 celdas legacy junto a las
canónicas del vertical slice, sin distinción visible, destruiría la única
propuesta de valor que Catalaxia tiene: que cada número se puede auditar.

Y la asimetría es cruel de mirar pero hay que mirarla: **el legacy cubre el
66,8 % de esta matriz y el canónico el 0 %.** Lo que el producto sabe respaldar
no se solapa con lo que el producto ya muestra.

---

## 10. Blockers, en orden

| # | blocker | alcance | qué desbloquea |
|---|---|---|---|
| **B1** | **Los 56 CUIT no están en `identity_v1`** | 728/728 | todo. Es condición previa a cualquier otra cosa |
| **B2** | **0/54 instrumentos ligados a entidad** | los 4 ratios de mercado | P/E, P/B, P/S, EV/EBITDA — el precio ya existe |
| **B3** | **Sin fundamentals canónicos** — no hay filings SEC porque no hay ADR; la vía es CNV, y `fetch_raw` tiene 3 CUIT de 56 | 728/728 | los 9 ratios contables |
| **B4** | **10 de los 13 ratios no implementados en S1** | 560/728 | aun con B1–B3 resueltos, el techo sería 168 celdas |
| **B5** | **D3, D4, D5 abiertas** | `ev_ebitda`, `roe`, `debt_to_equity` | 168 celdas más |
| **B6** | **Sin TTM** | 10 de 13 son de flujo | comparabilidad |

**B1 y B3 son el mismo problema visto por dos lados**: este universo no tiene
fuente SEC, así que su camino canónico es CNV — y el piloto CNV midió que sólo
3 de 17 CUIT conocidos son elegibles, ninguno de ellos de estos 56.

---

## 11. Dictamen

# CNV_56x13_COVERAGE_GATE = **FAIL**

**La auditoría se ejecutó completa y es reproducible.** El `FAIL` califica la
cobertura, no el trabajo: a la pregunta *«¿qué cobertura comercialmente
defendible existe sobre el universo CNV?»*, la respuesta medida es **ninguna**.

### Por qué FAIL y no PASS_WITH_WARNINGS

Convertir 0/728 en «PASS con advertencias» sería la misma operación que el
encargo prohíbe tres veces: `NULL → 0`, `NOT_CALCULABLE → 0`,
`LEGACY_ONLY → CANONICAL`. Cero no es un warning.

### Lo que el FAIL no significa

**No es un defecto del sistema.** Las 728 celdas están correctamente bloqueadas:
el motor se niega a atribuir un ratio a una entidad que no puede identificar, y
se niega a usar un precio que no puede probar que le pertenece —aunque lo tenga
delante, en 53 de 56 casos.

Un sistema que hubiera unido por ticker mostraría hoy 486 celdas con aspecto
canónico. Éste muestra cero y explica por qué. **Ésa es la diferencia que el
producto vende.**

### Qué habilitaría la cobertura, en orden

1. **Promover los 56 CUIT a `identity_v1`** con evidencia — desbloquea todo lo demás
2. **Ligar los 54 instrumentos a sus entidades** — habilita los 4 ratios de mercado sobre datos que ya existen
3. **Ingesta CNV canónica** para los fundamentals — es la única vía: no hay SEC
4. **Implementar los 10 ratios faltantes** y resolver D3/D4/D5
5. **TTM**

Los pasos 1 y 2 son de identidad y enlace, no de ingesta pesada: son el mejor
retorno por esfuerzo de toda la lista.

### Para el discurso comercial

- **No mostrar este universo como cobertura de Catalaxia.** Hoy no lo es.
- La demo y el piloto siguen siendo los 8 emisores del vertical slice, que sí
  tienen respaldo.
- Si un prospecto pregunta por las 56 empresas argentinas: existen en una capa
  anterior, con 486 valores y **sin procedencia verificable**, y decirlo así.

---

### Anexo · reproducción

```bash
# universo legacy
sqlite3 data/screener.db "SELECT count(*), count(DISTINCT cuit)
                            FROM screener WHERE grupo='byma_only'"      # 56 | 56

# interseccion con la identidad canonica (0 en las cinco lineas)
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
  WITH u(cuit) AS (VALUES ('30500006613'), ...)
  SELECT count(*) FROM u WHERE EXISTS (SELECT 1 FROM identity_v1.identifier i
    WHERE i.id_type='CUIT' AND i.id_value=u.cuit AND i.valid_to IS NULL)"

# market: el precio esta, el enlace no
#   con instrumento 54/56 · con precios 53/56 · ligados a entidad 0/56

# la matriz completa
python scratchpad/cnv_56x13_audit.py
   -> 728 celdas · LEGACY_ONLY 486 · IDENTITY_BLOCKED 242 · CALCULADO 0
```

Ninguna base fue modificada: la auditoría sólo ejecuta `SELECT`.
