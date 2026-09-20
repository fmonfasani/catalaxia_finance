# PARTE X — PROVENANCE

Este capítulo responde la pregunta fundamental del proyecto: **¿de dónde
salió este número?** Y obliga, no sugiere: *"un número sin provenance no se
publica"* (`06_PROVENANCE.md` §7).

La cadena que todo número publicado debe poder recorrer:

```
RESULTADO → FÓRMULA → INSUMO → FACT → CONCEPTO → CONTEXTO → DOCUMENTO → RAW → SHA256
```

Cada eslabón vive en una tabla con su clave exacta:

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

**El material de este capítulo está verificado en vivo (2026-09-04), no
escrito de memoria.** Fuente primaria: `docs/manual/ANNEX_YPF.md` §11 y
`docs/runbooks/06_PROVENANCE.md`.

---

## Paso 1 — Recorrido SEC desde un hecho publicado (verificado completo)

**OBJETIVO**
Partir de un número publicado en `derived.fact`, bajar hasta el archivo RAW y
cerrar con un SHA256 verificado contra disco — sin preguntarle a nadie.

**PREREQUISITOS**
Parte V (los hechos existen) y Partes III-IV (el RAW y el parseo existen).

**El hecho elegido:** `Assets` (activo total), YPF, 2025-12-31,
USD 29.439.000.000.

**1 · De `derived.fact` al `parsed.facts` de origen:**
```sql
SELECT fact_key, tag, value_numeric, currency, report_period,
       accession_number, source_fact_ids[1]
  FROM derived.fact
 WHERE cik='0000904851' AND valid_to IS NULL AND tag='Assets'
   AND NOT is_dimensional
   AND COALESCE(instant_date::text,end_date::text)=report_period::text
 ORDER BY report_period DESC LIMIT 1;
```
```
fact_key = 7365a6c2b4d55fa9c48f88e8bf8485440a7e6bf6e66e9035a867e67e7b7f43a7
tag      = Assets
valor    = 29439000000 USD
período  = 2025-12-31
accession= 0001193125-26-126363
source_fact_ids[1] = 165389
```

**2 · Del `parsed.facts` al RAW y su hash:**
```sql
SELECT fact_id, cik, accession_number, qname, context_id,
       source_file, source_path, source_hash
  FROM parsed.facts WHERE fact_id=165389;
```
```
fact_id       = 165389
qname         = https://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full#Assets
context_id    = PAsOn12_31_2025
source_file   = d95578d20f.htm
source_path   = CIK0000904851/filings/000119312526126363/
                0001193125-26-126363-xbrl.zip!d95578d20f.htm
source_hash   = 960c7a2e28de2028a26ca1ff73525b3b03ec333ebe2365ea261a07302f68d823
```

**`KNOWN_LIMITATION`** — nótese que el componente IFRS del `qname` es
`https://xbrl.ifrs.org/taxonomy/2025-03-27/ifrs-full#Assets`. Con este caso
no se manifestaría, pero es el mismo punto de la Parte IV Paso 3
(`is_custom`): la taxonomía vive en el penúltimo segmento, no en el último.

**3 · La verificación final — SHA256 del archivo real dentro del ZIP:**
```python
import zipfile, hashlib
with zipfile.ZipFile("data/raw/engine/CIK0000904851/filings/"
                      "000119312526126363/0001193125-26-126363-xbrl.zip") as zf:
    data = zf.read("d95578d20f.htm")
hashlib.sha256(data).hexdigest()
```
```
960c7a2e28de2028a26ca1ff73525b3b03ec333ebe2365ea261a07302f68d823
```

**Coincide, dígito por dígito, con `source_hash`.** La cadena
`derived.fact → parsed.facts → RAW → SHA256` cierra para este hecho.

**RESULTADO ESPERADO / VERIFICACIÓN**
El hash recalculado sobre el archivo en disco reproduce el `source_hash`
almacenado. Verificado. Cualquier desvío → **la fila fue alterada**: tratála
como incidente (regla de oro, al final).

---

## Paso 2 — Recorrido SEC desde un *ratio* publicado

**OBJETIVO**
Bajar desde `derived.ratio` hasta la misma cadena, por la entrada que va de
un resultado a sus insumos.

**Procedimiento** (`06_PROVENANCE.md` §2):

**1 · El ratio y sus insumos:**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT r.canonical_id, r.value, r.formula, r.formula_version, r.status,
       jsonb_pretty(r.inputs) AS insumos
  FROM derived.ratio r
 WHERE r.ratio_key = '<RATIO_KEY>'"
```

**2 · Por cada `fact_key` de `inputs`, el hecho y su origen:**
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

**3 · Verificá el archivo** (el `source_path` apunta al archivo — dentro del
ZIP cuando corresponde):
```bash
sha256sum "<source_path>"
```
debe coincidir con `source_hash`.

**Qué garantiza el motor a nivel de ratio** (Parte VII, R10): cada fila de
`derived.ratio.inputs` guarda, por insumo, el tag elegido, la cadena
evaluada, el `fact_key`, los `source_fact_ids` y el hash del archivo fuente.
La guarda F-061 exige que esa provenance pertenezca al **mismo** emisor,
filing y concepto.

---

## Paso 3 · La diferencia CNV — dos campos que no son opcionales

**OBJETIVO**
Saber qué exige la cadena cuando la fuente es CNV, antes de asumir que el
procedimiento SEC generaliza tal cual.

En emisores argentinos la cadena es idéntica en el modelo canónico, con dos
campos **obligatorios**:

| campo | por qué importa |
|---|---|
| `measurement_date` | bajo **IAS 29** la cifra está expresada en el poder adquisitivo de ese cierre. Sin él, el número no está definido |
| perímetro | `CONSOLIDADO` o `INDIVIDUAL`, primer componente de `context_id` |

`context_id` de CNV tiene la forma
`PERIMETRO|KIND|inicio|fin|medición`, por ejemplo:
```
CONSOLIDADO|DURATION|2024-01-01|2024-12-31|2024-12-31
```

Ejemplo real y completo con SHA verificado:
`outputs/docs/fase_cnv/METR_FY2024_PROVENANCE.csv` — una fila por
*(ratio, rol, fact)*, **70 ratios cubiertos** (pilar METR, Parte IX).

---

## Paso 4 · Las dos identidades — no confundirlas

**OBJETIVO**
Que un operador nunca mezcle *"este hecho, en este documento"* con *"qué se
está midiendo"*.

| clave | fórmula | qué identifica |
|---|---|---|
| **`fact_key`** | `sha256(entity_key\|accession\|qname\|context_id\|unit_measure)` | **la ocurrencia**: este hecho, en este documento |
| **`econ_key`** | `sha256(entity_id\|qname\|perimetro\|period_kind\|start\|end\|unit_measure\|measurement_date)` | **el hecho económico**: qué se mide, sin el documento |

Serialización canónica de `econ_key` (normativa, en
`migrations/engine/036_economic_identity.sql`): separador `|` exactamente
uno entre campos; NULL como cadena **vacía** (nunca `'NULL'`/`'None'`);
fechas ISO-8601 sin hora ni zona; para INSTANT el `end_date` es la fecha del
instante y el `start_date` queda vacío; UTF-8; digest sha256 hexadecimal
minúscula.

**Consecuencia práctica:** varias ocurrencias pueden compartir `econ_key`
sin ser un duplicado — es el mismo hecho declarado dos veces, y las dos
declaraciones se conservan. En el ciclo actual `econ_key` es **NULL para los
hechos de SEC**: es el alcance (ver Parte IX), no una omisión.

**Verificarla a mano** — con `fact_key` alcanza, porque sus cinco
componentes están en la fila:
```bash
python - <<'PY'
import hashlib
entity_key, accn, qname, ctx, unit = "<ek>", "<accn>", "<qname>", "<ctx>", "<unit>"
print(hashlib.sha256("|".join((entity_key, accn, qname, ctx, unit or "")).encode()).hexdigest())
PY
```
Si no reproduce el `fact_key` almacenado, la fila fue alterada.

---

## Paso 5 · Qué NO tiene provenance — el mapa honesto

**OBJETIVO**
Saber dónde deja de cerrarse la cadena, antes de publicar un número que no se
sostiene.

| resultado | estado |
|---|---|
| Ratios SEC en `derived.ratio` | **sí**: `inputs` JSONB + `source_fact_ids` |
| Ratios CNV del snapshot FY2024 | **sí**: `METR_FY2024_PROVENANCE.csv` |
| Hechos CNV en `screener.db` | **parcial**: hay `accn`, **no hay SHA256** |
| Precios de mercado | **parcial**: `market_fetch_log`, `market_raw_files`; el enlace a emisor no resuelve (`SG-10` / **L-5**) |
| Ratios que combinan mercado y contabilidad | **no reconstruibles hoy** por el punto anterior |

**`KNOWN_LIMITATION`** — es la causa estructural de que la valuación
generalizada esté bloqueada (Parte IX/XI del plan de mercado): el enlace
`market_instruments.entity_id` es un entero legacy, no el `entity_id`
namespaced del engine, y no hay tabla puente. **Documentada, no arreglada**
en este manual.

---

## Regla de oro

> **Un número sin provenance no se publica.** Si no podés recorrer la cadena
> hasta un SHA256 verificable, el resultado va a `NOT_CALCULABLE` con su
> causa — no a la salida con una nota al pie.

**GATE de la Parte X:** un procedimiento de provenance está verificado si y
sólo si **reproduce** el `source_hash` almacenado calculando el SHA256 del
archivo en disco (Paso 1, completado para `Assets` YPF 2025-12-31). La
cadena de ratios queda verificable método por método (Paso 2); el resto del
mapa (Paso 5) está dicho sin suavizar.

---

*Los comandos de este capítulo fueron ejecutados y sus salidas verificadas en
vivo (2026-09-04), incluida la verificación de SHA256 contra el archivo físico
dentro del ZIP. Ninguna operación escribe en producción (5432).*