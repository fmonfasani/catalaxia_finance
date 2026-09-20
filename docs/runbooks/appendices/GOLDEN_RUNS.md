# GOLDEN RUNS

> **CORRECCIÓN (GATE 2).** Este informe caracterizó los 226 documentos no
> extraíbles como *"la página de espera del visor de la CNV"*, es decir como
> descargas que no capturaron nada. **Es incorrecto: ninguno está vacío y
> ninguno falló.** Se parten en dos poblaciones con causa distinta:
>
> | | n | qué son |
> |---|---:|---|
> | `ATTACHMENT_ONLY` | **197** | presentaciones de **2000–2018** cuyo estado contable es un **PDF adjunto**. La página trae la metadata del archivo (`TipoDeDocumento` = "Balance Consolidado" 142 / "Balance Subsidiaria" 55, `NombreDocumento`, `FechaAlta`) y nada más |
> | `OTHER_FORM` | **29** | el **formulario de participaciones en sociedades**, con datos reales: `MetroEnergía S.A.`, 95 % del capital y de los votos |
>
> La transición no es casual: la CNV pasó del PDF adjunto al formulario
> estructurado **en 2018-2019**. Antes de 2019 el 100 % son adjuntos; desde
> 2019, el 100 % son estructurados. Por eso los 60 documentos con datos
> empiezan justo ahí.
>
> **Consecuencia:** el techo de 60 documentos no es un defecto del downloader,
> es la frontera del formato. Existe recuperación (`c3_cnv_fetch.py
> --adjuntos-presentaciones`) pero devuelve PDF, que el pipeline no parsea.
> Evidencia en `CNV_INGESTION_CENSUS.csv`.

Casos de referencia para verificar una instalación. Si estos no dan lo
esperado, no sigas con datos reales.

---

## 1 · SEC — YPF S.A., CIK `0000904851`

**Por qué éste.** Está fijado en el código como `GOLDEN_CIK`
(`scripts/engine/s02_fetch_ypf.py:29`) y es el default de `--cik` en S02 y S03.
Además `C-S01-004` verifica explícitamente que la entidad exista.

### Entorno

```bash
ENGINE_DB_HOST=127.0.0.1
ENGINE_DB_PORT=5433          # NUNCA 5432
ENGINE_DB_NAME=catalaxia
ENGINE_MODE=FAST
```

### Comandos, en orden

```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s00_smoke.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s01_identity.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s02_fetch_ypf.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851
```

### Resultado esperado

| etapa | gate | exit | señal en consola |
|---|---|---|---|
| S00 | `PASS` | `0` | `rows_expected = 2`, `rows_rejected = 0` |
| S01 | `PASS` | `0` | `checks_expected = 4`, `checks_pass = 4` |
| S02 | `PASS` | `0` | `rows_failed = 0` |
| S03 | `PASS` | `0` | `[hash_out] hashout-v2 = <64 hex>`, `filings_rejected = 0` |
| S04 dry | `PASS` | `0` | `C-S04-005..009` en `SKIP` |
| S04 | `PASS` | `0` | `hash_in` / `hash_out` impresos |
| ratios | — | `0` | una línea por `canonical_id` |

### Verificación de la instalación

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT (SELECT count(*) FROM engine.schema_migrations)                       AS migraciones,
       (SELECT count(*) FROM fetch_raw.download_log WHERE cik='0000904851')  AS descargas,
       (SELECT count(*) FROM parsed.facts WHERE cik='0000904851')            AS facts,
       (SELECT count(*) FROM derived.fact
         WHERE cik='0000904851' AND valid_to IS NULL)                        AS derivados,
       (SELECT count(*) FROM engine.checkpoints WHERE stage_id='S03_parse')  AS checkpoints"
```

> **`RUNBOOK GAP RG-01`.** No hay valores esperados canónicos publicados para
> estos conteos: dependen de cuántos filings tenga YPF en EDGAR al momento de
> correr, y ese número crece. **Lo que sí es determinístico y hay que exigir**
> es: los 6 gates en `PASS`, `rows_failed = 0`, `filings_rejected = 0`, y —la
> propiedad fuerte— que **una segunda corrida de S03 dé checkpoint hit y el
> mismo `hash_out`**.

### Verificación de idempotencia (la prueba que sí es determinística)

```bash
# 1. anotá el hash_out de S03
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT report->'integrity'->>'hash_out' FROM engine.stage_runs \
    WHERE stage_id='S03_parse' AND report IS NOT NULL ORDER BY started_at DESC LIMIT 1"

# 2. re-corré S03
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py

# 3. el hash_out debe ser IDÉNTICO, y debe haber reutilizado el checkpoint
```

---

## 2 · CNV — Metrogas S.A., CUIT `30657863676`

**Estado: parcial.** Ver `03_CNV_E2E_RUNBOOK.md`. El tramo A corre; el tramo B
es legacy sin gate; el tramo C está en un worktree.

### Tramo A

```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 \
  python scripts/engine/c3_cnv_fetch.py --cuit 30657863676
```

Esperado: `gate = PASS  checkpoint=<id>`, exit `0`.

Verificación:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT artifact_kind, count(*), count(hash_cnv) AS con_hash \
     FROM fetch_raw.cnv_download_log WHERE cuit='30657863676' GROUP BY 1"
```

Esperado hoy: sólo `VISOR` y `EMPRESA_PAGE`, y **`con_hash = 0`**. Que
`con_hash` sea 0 **no es una falla de tu instalación**: es `SG-02`.

### Snapshot certificado disponible

El ejercicio **FY2024 de METR** tiene una certificación E2E completa —
7 documentos, 203 hechos, 70 ratios, auditoría independiente con 0 fallas — en
`outputs/docs/fase_cnv/METR_FY2024_E2E_REPORT.md`, con digests reproducibles en
`METR_FY2024_SNAPSHOT.json`:

```
documentos  27a779def75d99c0…
fact_key    2324f732c8dcd39f…
econ_key    ecd38d81a23c2953…
valores     ff30bc8c1b2b4377…
```

Sirve como referencia de valores esperados, **pero se produjo con el adaptador
del worktree**, no con el repo principal.

---

## 3 · Caso de diagnóstico obligatorio — METR 30/09/2024 CONSOLIDADO

Documento CNV **#3277363**, GUID `e04ceaf3-154a-4a37-96be-40496f91e2db`.

Existe porque **el CONSOLIDADO de ese trimestre falta** en los datos mientras el
INDIVIDUAL está. Sirve para medir hasta dónde llega el diagnóstico del sistema.

### Comando

```bash
python - <<'PY'
import csv, sqlite3, hashlib, sys
from pathlib import Path
sys.path.insert(0, "scripts/tickets/cnv/jobs")
import job5_v2_extract_eeff as j5

GUID = "e04ceaf3-154a-4a37-96be-40496f91e2db"
CUIT = "30657863676"
c = sqlite3.connect("file:data/screener.db?mode=ro", uri=True)

print("1. publicado por CNV :", c.execute(
    "SELECT count(*) FROM cnv_filings WHERE cuit=? AND fecha_cierre='2024-09-30'"
    "  AND tipo_balance='CONSOLIDADO'", (CUIT,)).fetchone()[0], "filas en cnv_filings")
print("2. descubierto       :", c.execute(
    "SELECT count(*) FROM cnv_documents WHERE docid=?", (GUID,)).fetchone()[0])

wl = [r for r in csv.DictReader(
        open("scripts/tickets/cnv/datos/whitelist_eeff.csv", encoding="utf-8-sig"))
      if r.get("cuit","").strip() == CUIT]
print("3. seleccionado      :", GUID in {r["guid"] for r in wl},
      f"(whitelist tiene {len(wl)} EEFF de este emisor)")

p = Path("scripts/tickets/cnv/eeff/eeff_html")/f"{GUID}.html"
print("4. descargado        :", p.exists(), f"{p.stat().st_size:,} bytes" if p.exists() else "")
print("5. sha256 calculado  :", hashlib.sha256(p.read_bytes()).hexdigest())
print("6. en RAW            :", p.exists())

h = p.read_text(encoding="utf-8", errors="replace")
pares = j5.parse(h)
datos = {j5.CODIGOS[k]: v for k, v in pares.items() if k in j5.CODIGOS}
print("7. parsea            :", len(pares), "codigos;",
      len(datos), "conceptos mapeados (el guard descarta si < 5)")
print("   period_end()      :", j5.period_end(h))
print("   tipo_balance()    :", j5.tipo_balance(h))
print("   factor_unidad()   :", j5.factor_unidad(h))

for t in ("cnv_estados_v2", "cnv_estados_norm"):
    print(f"8. filas en {t:<17}:", c.execute(
        f"SELECT count(*) FROM {t} WHERE accn=?", (GUID,)).fetchone()[0])

done = set(open("data/log_job5_v2_done.txt", encoding="utf-8").read().split())
print("9. procesado por job5:", GUID in done, f"(DONE tiene {len(done)} GUIDs)")
c.close()
PY
```

### Salida real (verificada)

```
1. publicado por CNV : 3 filas en cnv_filings
2. descubierto       : 1
3. seleccionado      : True (whitelist tiene 286 EEFF de este emisor)
4. descargado        : True 152,335 bytes
5. sha256 calculado  : 66292afffe7677c78b020bf3b9b7dc2a7864cb3bdee54d890ae19bd83764f811
6. en RAW            : True
7. parsea            : 69 codigos; 38 conceptos mapeados (el guard descarta si < 5)
   period_end()      : 2024-09-30
   tipo_balance()    : CONSOLIDADO
   factor_unidad()   : 1000000
8. filas en cnv_estados_v2   : 0
8. filas en cnv_estados_norm : 0
9. procesado por job5: False (DONE tiene 2457 GUIDs)
```

### Las 10 preguntas, respondidas

| # | pregunta | respuesta | cómo se sabe |
|---|---|---|---|
| 1 | ¿CNV publicó el documento? | **SÍ** | `cnv_filings` tiene CONSOLIDADO/T/2024-09-30 |
| 2 | ¿Discovery lo encontró? | **SÍ** | `cnv_documents` tiene el `docid` y su URL |
| 3 | ¿Fue seleccionado? | **SÍ** | está en `whitelist_eeff.csv`, clase `eeff` |
| 4 | ¿Fue descargado? | **SÍ** | 152.335 bytes en disco |
| 5 | ¿SHA válido? | **no determinable** | se calcula, pero **ninguna tabla guarda el SHA de un documento CNV** contra el cual compararlo. `SG-02` |
| 6 | ¿Está en RAW? | **SÍ** | |
| 7 | ¿Parsea? | **SÍ, perfectamente** | 38 conceptos, período, perímetro y escala correctos. Ninguno de los dos guards de descarte se activaría |
| 8 | ¿Tiene facts? | **NO** | 0 filas |
| 9 | ¿Fue excluido? | **NO — nunca fue procesado** | no está en `data/log_job5_v2_done.txt` |
| 10 | ¿Por qué? | **la corrida de extracción nunca llegó a él** | `job5` procesa un rango `filas[r0:r1]` acotado por `--max`; no hay reconciliación entre lo descargado y lo procesado |

### La brecha de cobertura, cuantificada

El caso no es una anomalía. Para METR:

```
  PROCESSED_OK    56    documentos extraidos
  PENDING          4    EEFF genuinos nunca intentados
  FAILED         226    descargas que capturaron la pagina de espera del visor
  REJECTED         0
  ------------------
  TOTAL          286
```

**De 286 seleccionados, 56 tienen datos.** Y las dos causas son distintas: 226
descargas **no trajeron el documento** (~77 KB de UI del visor, cero códigos con
valor) y 4 EEFF genuinos **nunca se intentaron**. El sistema no tiene ningún
control que compare esas columnas, así que ninguno de los dos casos aparece en
un reporte, contador o gate.

> Una medición anterior reportó "230 nunca procesados". Es la suma de los dos
> grupos, y confunde una descarga vacía con un documento pendiente. El desglose
> de arriba es el correcto.

Reproducilo:

```bash
python - <<'PY'
import csv, sqlite3
from pathlib import Path
CUIT = "30657863676"
H = Path("scripts/tickets/cnv/eeff/eeff_html")
done = set(open("data/log_job5_v2_done.txt", encoding="utf-8").read().split())
c = sqlite3.connect("file:data/screener.db?mode=ro", uri=True)
con_filas = {r[0] for r in c.execute(
    "SELECT DISTINCT accn FROM cnv_estados_v2 WHERE cuit=?", (CUIT,))}
g = [r["guid"] for r in csv.DictReader(
        open("scripts/tickets/cnv/datos/whitelist_eeff.csv", encoding="utf-8-sig"))
     if r.get("cuit","").strip() == CUIT]
print(f"whitelist={len(g)}  disco={sum((H/f'{x}.html').exists() for x in g)}  "
      f"DONE={sum(x in done for x in g)}  con_filas={sum(x in con_filas for x in g)}")
print("descargados y nunca procesados:",
      sum((H/f'{x}.html').exists() and x not in done for x in g))
c.close()
PY
```

**Conclusión operativa.** El sistema responde **nueve** de las diez preguntas
—y la novena sólo porque `data/log_job5_v2_done.txt` existe como archivo de
texto plano—. La que no puede responder es la validez del SHA (`SG-02`).

Pero el hallazgo importante no es esa pregunta: es que **la causa real de la
ausencia no es un error, sino una corrida incompleta que nadie detecta**. No
hay reconciliación `descargado → procesado → con datos`, ni gate que la exija,
ni contador que la exponga. `SOFTWARE GAP SG-04`.

Es la razón principal por la que el gate final de este sprint no es `PASS`.
