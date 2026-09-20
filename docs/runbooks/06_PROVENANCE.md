# 06 · PROVENANCE

Cómo ir desde un número publicado hasta el documento original, sin preguntarle
a nadie.

```
RESULTADO → FÓRMULA → INSUMO → FACT → CONCEPTO → CONTEXTO → DOCUMENTO → RAW → SHA256
```

---

## 1 · La cadena, tabla por tabla

| eslabón | dónde vive | clave |
|---|---|---|
| **resultado** | `derived.ratio` | `ratio_key` |
| **fórmula** | `derived.ratio.formula`, `formula_version` | — |
| **insumos** | `derived.ratio.inputs` (JSONB) | referencias a hechos |
| **fact** | `derived.fact` | `fact_key` |
| **origen del fact** | `derived.fact.source_fact_ids` (array) | → `parsed.facts.fact_id` |
| **concepto** | `parsed.facts.qname` / `tag` | |
| **contexto** | `parsed.facts.context_id`, `parsed.contexts` | |
| **documento** | `parsed.facts.accession_number` | |
| **RAW** | `parsed.facts.source_path`, `source_file` | |
| **SHA256** | `parsed.facts.source_hash` | y `fetch_raw.download_log.sha256` |

## 2 · Recorrerla hacia atrás — SEC

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT r.canonical_id, r.value, r.formula, r.formula_version, r.status,
       jsonb_pretty(r.inputs) AS insumos
  FROM derived.ratio r
 WHERE r.ratio_key = '<RATIO_KEY>'"
```

Después, por cada `fact_key` que aparezca en `inputs`:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT d.qname, d.value_numeric, d.unit_measure, d.period_kind,
       d.start_date, d.end_date, d.instant_date, d.context_id,
       d.accession_number,
       p.source_hash, p.source_path, p.source_file
  FROM derived.fact d
  JOIN parsed.facts p ON p.fact_id = d.source_fact_ids[1]
 WHERE d.fact_key = '<FACT_KEY>'"
```

Y verificá el archivo:

```bash
sha256sum "<source_path>"     # debe coincidir con source_hash
```

## 3 · Recorrerla hacia atrás — CNV

Idéntica en el modelo canónico, con dos campos más que **no son opcionales**
en emisores argentinos:

| campo | por qué importa |
|---|---|
| `measurement_date` | bajo IAS 29 la cifra está expresada en el poder adquisitivo de ese cierre. Sin él, el número no está definido |
| perímetro | `CONSOLIDADO` o `INDIVIDUAL`, primer componente de `context_id` |

`context_id` de CNV tiene la forma:

```
PERIMETRO|KIND|inicio|fin|medición
CONSOLIDADO|DURATION|2024-01-01|2024-12-31|2024-12-31
```

Ejemplo real y completo, con SHA verificado, en
`outputs/docs/fase_cnv/METR_FY2024_PROVENANCE.csv` (una fila por
*(ratio, rol, fact)*, 70 ratios cubiertos).

## 4 · Las dos identidades — no confundirlas

| clave | fórmula | qué identifica |
|---|---|---|
| **`fact_key`** | `sha256(entity_key\|accession\|qname\|context_id\|unit_measure)` | **la ocurrencia**: este hecho, en este documento |
| **`econ_key`** | `sha256(entity_id\|qname\|perimetro\|period_kind\|start\|end\|unit_measure\|measurement_date)` | **el hecho económico**: qué se mide, sin el documento |

Serialización canónica de `econ_key` (normativa, en
`migrations/engine/036_economic_identity.sql`):

```
separador  '|' exactamente uno entre campos
NULL       cadena vacía; NUNCA 'NULL' ni 'None'
fechas     ISO-8601 'YYYY-MM-DD', sin hora ni zona
end_date   para INSTANT se usa la fecha del instante
start_date para INSTANT queda vacío
encoding   UTF-8
digest     sha256 hexadecimal minúscula
```

**Varias ocurrencias pueden compartir `econ_key`.** Que un hecho aparezca en
dos documentos no es un duplicado: es el mismo hecho declarado dos veces, y
las dos declaraciones se conservan. `econ_key` es NULL para los hechos de SEC
en el ciclo actual — no es una omisión, es el alcance.

## 5 · Verificarla a mano

Con `fact_key` alcanza para reconstruirla, porque sus cinco componentes están
en la fila:

```bash
python - <<'PY'
import hashlib
# valores tomados de la fila de derived.fact
entity_key, accn, qname, ctx, unit = "<ek>", "<accn>", "<qname>", "<ctx>", "<unit>"
print(hashlib.sha256("|".join((entity_key, accn, qname, ctx, unit or "")).encode()).hexdigest())
PY
```

Si no reproduce el `fact_key` almacenado, la fila fue alterada.

## 6 · Qué NO tiene provenance

| resultado | estado |
|---|---|
| Ratios de SEC en `derived.ratio` | **sí**: `inputs` JSONB + `source_fact_ids` |
| Ratios de CNV del snapshot FY2024 | **sí**: `METR_FY2024_PROVENANCE.csv` |
| Hechos de CNV en `screener.db` | **parcial**: hay `accn`, **no hay SHA256** (`SG-02`) |
| Precios de mercado | **parcial**: `market_fetch_log`, `market_raw_files`; el enlace a emisor no resuelve (`SG-10`) |
| Ratios que combinan mercado y contabilidad | **no reconstruibles hoy** por lo anterior |

## 7 · Regla de oro

**Un número sin provenance no se publica.** Si no podés recorrer la cadena
hasta un SHA256 verificable, el resultado va a `NOT_CALCULABLE` con su causa,
no a la salida con una nota al pie.
