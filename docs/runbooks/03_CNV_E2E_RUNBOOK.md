# 03 · CNV — E2E PASO A PASO

**Advertencia que va primero porque cambia lo que podés hacer:**

> **No existe hoy un E2E de CNV ejecutable de punta a punta desde el repo
> principal.** El camino instrumentado (`c3_cnv_fetch.py`) no descarga estados
> financieros; el camino que produjo todos los datos CNV actuales es legacy y
> no tiene registro por documento; y el que los lleva al modelo canónico vive
> en un worktree sin mergear. Detalle y evidencia en
> `RUNBOOK_READINESS_REPORT.md` §4 (`SOFTWARE GAP SG-01`).

Este manual documenta **los tres tramos que sí existen**, con sus límites
reales, para que puedas operar lo que hay y saber exactamente qué falta.

**Caso de referencia: Metrogas S.A., CUIT `30657863676`, ticker METR.**

---

## Mapa de los tres tramos

```
TRAMO A · engine        c3_cnv_fetch.py     descarga VISOR y EMPRESA_PAGE
   (instrumentado)                          NO descarga los EEFF
                                            ledger: fetch_raw.cnv_download_log

TRAMO B · legacy        job5_v2_extract_    descarga y extrae los EEFF
   (produjo los datos)  eeff.py             destino: data/screener.db
                                            sin ledger, sin SHA almacenado
                        s0_normalizar_cnv.py  normaliza a cnv_estados_norm

TRAMO C · canónico      c4_cnv_adapter.py   lleva B al modelo PostgreSQL
   (worktree)                               NO está en el repo principal
```

---

## TRAMO A · C3_CNV_fetch

**1. Objetivo.** Descargar artefactos públicos de la CNV para un emisor,
dejando registro por artefacto.

**2. Precondiciones.** Entorno verificado (`01_COMMON_OPERATIONS.md` §1). La
identidad del emisor debe existir en `identity_v1`: la etapa la valida **antes**
de abrir corrida y corta con `SystemExit` si no cierra.

**3. Comando exacto.**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 \
  python scripts/engine/c3_cnv_fetch.py --cuit 30657863676
```

| argumento | default | qué hace |
|---|---|---|
| `--cuit` | — | CUIT sin guiones; se valida contra `identity_v1` |
| `--cik` | — | alternativa: resuelve el CUIT desde `identity_v1` |
| `--scope` | `FINANCIERO` | acota qué se descarga |
| `--desde-anio` | — | filtra por año de cierre ≥ N |
| `--max-visores` | — | tope de visores |
| `--adjuntos-presentaciones` | `0` | cuántos adjuntos bajar |
| `--adjunto-max-mb` | `30.0` | tope por adjunto |
| `--rerun` | off | **pasada de verificación de idempotencia** |
| `--delay-visor` | `DEFAULT_DELAYS['aif2.cnv.gov.ar']` | cortesía por host |

**Indicá exactamente uno de `--cuit` o `--cik`.** Los dos juntos, o ninguno,
producen `SystemExit("indicar exactamente uno: --cuit o --cik")`.

**5. Output esperado.** Termina con:
```
gate                    = PASS  checkpoint=<id>
```

**7. Validaciones.**

| check | bloqueante | qué verifica |
|---|---|---|
| `C-C3-001` | sí | conciliación plan→manifiesto, sin críticas fallidas |
| `C-C3-002` | sí | integridad del RAW **re-leyendo el disco** |
| `C-C3-003` | sí | provenance completa entidad→cuit→url |
| `C-C3-004` | sí | 0 artefactos aceptados que no validen contenido |
| `C-C3-005` | sí | rate limiting por host respetado |
| `C-C3-006` | sí | **idempotencia** (es la que evalúa `--rerun`) |
| `C-C3-007` | sí | identidad no inventada: reviews no cerrables intactas |
| `C-C3-008` | **no** | **doble hash**: compara el hash que declara la CNV contra el calculado |
| `C-C3-009` | sí | duplicados: 0 filas `(kind, key, sha)` repetidas |
| `C-C3-010` | sí | scope: 100 % de las descargas pertenecen al emisor pedido |

**Sobre `C-C3-008` — leelo antes de confiar en él.** Es el mecanismo de
detección de SHA mismatch. Está implementado y **no es bloqueante**. Pero en la
base actual, de **4.005 filas** de `fetch_raw.cnv_download_log`, `hash_cnv` es
**NULL en las 4.005**. Con `con_hash` vacío el check devuelve `PASS` sin
comparar nada. **El mecanismo existe y nunca se ejercita.**
`SOFTWARE GAP SG-02`.

Verificalo vos:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT count(*) filas, count(hash_cnv) con_hash, \
          count(*) FILTER (WHERE hash_cnv_match IS FALSE) mismatches \
     FROM fetch_raw.cnv_download_log"
```

**8. Logs.** `fetch_raw.cnv_download_log`, una fila por artefacto:
`artifact_kind`, `artifact_key`, `endpoint`, `http_status`, `bytes`,
`hash_cnv`, `hash_cnv_match`, `raw_path`, `duplicate_of`, `attempts`,
`elapsed_ms`, `downloaded_at`.

**9. Fallback automático.** `RateLimiter` con `DEFAULT_DELAYS` por host
(`engine/cnv/client.py`). La columna `attempts` existe; en los datos actuales
su máximo es **1**, es decir no hay evidencia de que algún reintento se haya
ejercitado.

**10. Fallback manual.** Volver a correr con `--rerun`.

**14. PASS** ⇒ exit `0`. El script devuelve `0` también con `WARNING`
(`return 0 if gate is not GateStatus.BLOCK else 1`). **16. BLOCK** ⇒ exit `1`.

**Límite del tramo A.** `artifact_kind` en el ledger toma sólo dos valores:
`VISOR` (3.936 filas) y `EMPRESA_PAGE` (69). **No hay ningún artefacto de
estados financieros.** Este tramo no alimenta la extracción.

---

## TRAMO B · Extracción legacy (la que produjo los datos)

> Este tramo **escribe en `data/screener.db`**. Es la única parte de estos
> manuales que modifica ese archivo. Anotá su huella antes y después.

### B.1 · Extracción

**3. Comando exacto.**
```bash
python scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py
```

**4. Input.** La lista de GUIDs de presentaciones y los HTML en
`scripts/tickets/cnv/eeff/eeff_html/`.

**5. Output esperado.**
```
JOB5 V2 · E-EEFF — Extraer [r0:r1] = <n> GUIDs (sleep <s>s, max <m>)
  Listo: ok=<n> skip=<n> cache=<n> err=<n> | dp=<n> | fetch=<n>/<n>
```

**6. Cómo interpretarlo — importante.** `err` es un **contador agregado**. No
dice qué documento falló ni por qué. Se imprime y se pierde.

**7. Validaciones.** Ninguna estructurada. No hay checks, ni gate, ni reporte,
ni `run_id`. Esta etapa no participa de `engine.runs`.

**8. Logs.** Sólo stdout. **No escribe en ninguna tabla de log.**
`SOFTWARE GAP SG-04`.

**11-13. Errores — el comportamiento real, que hay que conocer.**

En `scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py`, dos caminos descartan un
documento **en silencio y de forma permanente**:

```python
pe = period_end(html)
if not pe:
    err += 1
    _mark_done(guid)      # ← queda marcado como procesado
    continue
...
if len(datos) < 5:
    err += 1
    _mark_done(guid)      # ← idem
    continue
```

`_mark_done(guid)` lo registra como hecho, así que **una re-ejecución no lo
reintenta**. No queda registro del motivo en ninguna parte. Códigos
`CNV-EX-001` y `CNV-EX-002` del `ERROR_CATALOG.md`.

**20. Reanudar.** El script es *resume-safe* por diseño: los GUID ya hechos se
saltan (`skip`), y `--max` corta la corrida para retomarla después. Pero
"reanudar" **no** reintenta los que fallaron: quedan marcados.

**21. Idempotencia.** Alta por construcción (salta lo hecho), pero **no
verificable con un digest**: no hay `hash_out`.

### B.2 · Normalización

```bash
python scripts/tickets/screener/s0_normalizar_cnv.py
```

Produce `cnv_estados_norm` a partir de `cnv_estados_v2`, aplicando escala y
metadata. Sin gate ni reporte.

---

## TRAMO C · Adaptador canónico (worktree)

**No está en este repo.** Vive en el worktree `catalaxia-cnvmig`, rama
`feat/cnv-canonical`, y lleva `cnv_estados_norm` al modelo canónico
(`parsed.facts` / `derived.fact`) con `entity_id`, `context_id`,
`measurement_date`, `fact_key` y `econ_key`.

Referencia de comando, **para cuando se integre**:
```bash
ENGINE_DB_NAME=cnvmig ENGINE_DB_PORT=5433 \
  python scripts/engine/c4_cnv_adapter.py --cuit 30657863676 --persist
```
Sin `--persist` no escribe. Tiene guard propio: se niega a correr si
`db_name == "catalaxia"`.

Hasta que se mergee, este tramo es un **`RUNBOOK GAP`**: no se puede documentar
como operable desde el repo principal.

---

## Diagnóstico documento por documento

Ésta es la parte que más se necesita en producción, y es donde el sistema
más flojea. Está desarrollada con un caso real y completo en
`appendices/GOLDEN_RUNS.md` §3 (METR 30/09/2024 CONSOLIDADO).

Las cinco situaciones son **distintas** y hay que poder separarlas:

| situación | cómo se comprueba hoy |
|---|---|
| **No publicado por CNV** | `cnv_filings` en `screener.db` no lo lista |
| **Publicado, no descubierto** | está en `cnv_filings` pero no en `cnv_documents` |
| **Descubierto, no seleccionado** | está en `cnv_documents` y no en `scripts/tickets/cnv/datos/whitelist_eeff.csv` |
| **Seleccionado, no descargado** | está en la whitelist y **no** hay archivo en `eeff_html/` |
| **Descargado, nunca procesado** | hay archivo, **0 filas**, y el GUID **no está** en `data/log_job5_v2_done.txt` |
| **Procesado, parser lo descartó** | hay archivo, 0 filas, y el GUID **sí está** en el archivo DONE |
| **Parseado, sin datos** | hay filas pero faltan conceptos |

**La quinta y la sexta se confunden fácil y no son lo mismo.** La diferencia
está sólo en `data/log_job5_v2_done.txt`, un archivo de texto plano con un GUID
por línea. Es el único rastro que distingue "no le tocó el turno" de "se
intentó y falló".

Consulta base (reemplazá `<GUID>`):

```bash
python - <<'PY'
import csv, sqlite3, hashlib
from pathlib import Path
GUID = "<GUID>"
c = sqlite3.connect("file:data/screener.db?mode=ro", uri=True)
print("descubierto :", c.execute(
    "SELECT count(*) FROM cnv_documents WHERE docid=?", (GUID,)).fetchone()[0])
wl = {r["guid"] for r in csv.DictReader(
      open("scripts/tickets/cnv/datos/whitelist_eeff.csv", encoding="utf-8-sig"))}
print("seleccionado:", GUID in wl)
p = Path("scripts/tickets/cnv/eeff/eeff_html")/f"{GUID}.html"
print("en RAW      :", p.exists(), p.stat().st_size if p.exists() else "-")
print("sha256      :", hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "-")
done = set(open("data/log_job5_v2_done.txt", encoding="utf-8").read().split())
print("procesado   :", GUID in done)
for t in ("cnv_estados","cnv_estados_v2","cnv_estados_norm"):
    print(f"{t:<12}:", c.execute(
        f"SELECT count(*) FROM {t} WHERE accn=?", (GUID,)).fetchone()[0])
c.close()
PY
```

### Reconciliación de cobertura — hacela siempre

El sistema **no la hace solo**, y es donde aparecen los problemas reales:

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

Para METR devuelve `whitelist=286 disco=286 DONE=56 con_filas=56`. Pero
**"en disco" no es lo mismo que "es un documento"**: 226 de esos archivos son la
página de espera del visor (0 códigos con valor). El desglose real es
`PROCESSED_OK 56 · PENDING 4 · FAILED 226`. Ver `appendices/GOLDEN_RUNS.md` §3 y
`outputs/docs/fase_cnv/METROGAS_GOLDEN_RUN_REPORT.md`.

**Lo que estas consultas NO pueden responder:**

- **¿El SHA es válido?** Se puede *calcular*, pero **no hay contra qué
  compararlo**: ninguna tabla de `screener.db` guarda el SHA256 de un documento
  CNV. `SOFTWARE GAP SG-02`.
- **¿Por qué un documento procesado no dejó filas?** El descarte sólo suma al
  contador `err` en pantalla. Hay que abrir el HTML y leer el extractor.
  `SOFTWARE GAP SG-04`.

---

## Cierre

Al terminar cualquier tramo, comprobá:

```bash
stat -c '%y %s' data/screener.db
docker exec catalaxia-db psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',') FROM pg_namespace \
    WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"
```

El tramo A no toca `screener.db`. El tramo B **sí**: su huella va a cambiar, y
eso es correcto. Producción debe seguir con `public` y nada más.
