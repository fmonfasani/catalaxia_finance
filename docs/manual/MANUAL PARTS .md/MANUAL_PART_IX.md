# PARTE IX — CNV

**Advertencia que va primero, porque cambia lo que se puede hacer:** **no
existe hoy un E2E de CNV ejecutable de punta a punta desde el repo
principal.** El camino instrumentado (`c3_cnv_fetch.py`) no descarga estados
financieros; el camino que produjo todos los datos CNV actuales es legacy y no
tiene registro por documento; y el que los lleva al modelo canónico vive en un
worktree sin mergear (`RUNBOOK_READINESS_REPORT.md` §4, `SG-01`).

**Estado:** `PARCIAL` — tramos A y B ejecutables; tramo C `DECISION_REQUIRED`
(D-1).

**Material de base:** `docs/runbooks/03_CNV_E2E_RUNBOOK.md` completo (315
líneas); `docs/runbooks/appendices/GOLDEN_RUNS.md` §2-§3;
`outputs/docs/fase_cnv/METROGAS_GOLDEN_RUN_REPORT.md`; `MANUAL_SCOPE.md`
`L-6`, `L-7`, `L-9`, `L-10`.

**Caso de referencia:** Metrogas S.A., CUIT `30657863676`, ticker **METR**.

---

## Paso 1 · El mapa de los tres tramos

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

**La identidad primero.** La identidad del emisor debe existir en
`identity_v1` con CUIT; la etapa la valida **antes** de abrir corrida y corta
con `SystemExit` si no cierra. No se inventa un CIK: METR es
`CUIT:30657863676`, y BMA (que figura como `CIK:0001347426` autoritativo SEC)
tiene 0 filas como CUIT (F-024). El CUIT **es** la clave de identidad CNV.

---

## Paso 2 · Tramo A — `c3_cnv_fetch` (instrumentado, con gate)

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
| `--rerun` | off | pasada de verificación de idempotencia |
| `--delay-visor` | `DEFAULT_DELAYS` | cortesía por host |

**Se indica exactamente uno de `--cuit` o `--cik`.** Los dos, o ninguno,
producen `SystemExit("indicar exactamente uno: --cuit o --cik")`.

Output esperado: `gate = PASS  checkpoint=<id>`, exit `0`.

**Validaciones (`C-C3-001..010`)** — todas bloqueantes salvo `C-C3-008`:
reconciliación plan→manifiesto, integridad del RAW releyendo disco, provenance
completa, 0 artefactos aceptados que no validen contenido, rate limiting por
host, idempotencia (`--rerun`), identidad no inventada, **doble hash
(`C-C3-008`, no bloqueante)**, duplicados `(kind, key, sha)`, scope 100 %.

**`C-C3-008` — leelo antes de confiar en él.** Es el mecanismo de SHA mismatch
y **nunca se ejercita**: en la base actual, de **4.005 filas** de
`fetch_raw.cnv_download_log`, `hash_cnv` es **NULL en las 4.005**. Con
`con_hash` vacío el check devuelve `PASS` sin comparar nada (`SG-02`).
Verificalo, no lo creas:

```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT count(*) filas, count(hash_cnv) con_hash, \
          count(*) FILTER (WHERE hash_cnv_match IS FALSE) mismatches \
     FROM fetch_raw.cnv_download_log"
```

**Límite del tramo A (L-7):** `artifact_kind` toma solo dos valores — `VISOR`
(3.936) y `EMPRESA_PAGE` (69). **No hay ningún artefacto de estados
financieros.** Este tramo **no alimenta la extracción**.

---

## Paso 3 · Tramo B — extracción legacy (la que produjo los datos)

> **Este tramo escribe en `data/screener.db`.** Es la única parte de estos
> manuales que modifica ese archivo. Anotá su huella antes y después.

```bash
python scripts/tickets/cnv/jobs/job5_v2_extract_eeff.py
python scripts/tickets/screener/s0_normalizar_cnv.py
```

Output esperado de job5:

```
JOB5 V2 · E-EEFF — Extraer [r0:r1] = <n> GUIDs (sleep <s>s, max <m>)
  Listo: ok=<n> skip=<n> cache=<n> err=<n> | dp=<n> | fetch=<n>/<n>
```

**Cómo interpretarlo:** `err` es un **contador agregado**. No dice qué
documento falló ni por qué. Se imprime y se pierde. No hay checks, ni gate, ni
reporte, ni `run_id`. **No escribe en ninguna tabla de log** (`SG-04`).

**Los dos caminos de descarte silencioso y permanente** (códigos
`CNV-EX-001`/`CNV-EX-002` del `ERROR_CATALOG`): cuando `period_end` falla o hay
menos de 5 conceptos, `_mark_done(guid)` queda registrado como hecho, así que
**una re-ejecución no lo reintenta** y no queda registro del motivo
(`KNOWN_LIMITATION L-6`).

Reanudar: es *resume-safe* por diseño (los hechos se saltan, `--max` corta la
corrida), pero **no** reintenta fallidos. Idempotencia alta por construcción,
pero **no verificable con un digest**: no hay `hash_out`.

---

## Paso 4 · Tramo C — adaptador canónico (worktree, no ejecutable hoy)

```bash
ENGINE_DB_NAME=cnvmig ENGINE_DB_PORT=5433 \
  python scripts/engine/c4_cnv_adapter.py --cuit 30657863676 --persist
```

Sin `--persist` no escribe. Tiene guard propio: se niega a correr si
`db_name == "catalaxia"`. Hasta que se mergee, es un `RUNBOOK GAP`: **no hay
manera de documentarlo como operable desde el repo principal**.

---

## Paso 5 · Diagnóstico documento por documento

Las situaciones son **distintas** y hay que poder separarlas. La quinta y la
sexta se confunden fácil y **no son lo mismo**:

| situación | cómo se comprueba hoy |
|---|---|
| **No publicado por CNV** | `cnv_filings` en `screener.db` no lo lista |
| **Publicado, no descubierto** | está en `cnv_filings` pero no en `cnv_documents` |
| **Descubierto, no seleccionado** | está en `cnv_documents` y no en `scripts/tickets/cnv/datos/whitelist_eeff.csv` |
| **Seleccionado, no descargado** | está en la whitelist y **no** hay archivo en `eeff_html/` |
| **Descargado, nunca procesado** | hay archivo, **0 filas**, y el GUID **no** está en `data/log_job5_v2_done.txt` |
| **Procesado, parser lo descartó** | hay archivo, 0 filas, y el GUID **sí** está en el archivo DONE |
| **Parseado, sin datos** | hay filas pero faltan conceptos |

La única diferencia entre las dos del medio es `data/log_job5_v2_done.txt`,
un archivo de texto plano con un GUID por línea. **Es el único rastro que
distingue "no le tocó el turno" de "se intentó y falló".**

**Reconciliación de cobertura — hacela siempre** (el sistema no la hace solo):

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
**"en disco" no es lo mismo que "es un documento"**: de esos 286, 226 archivos
son la página de espera del visor (0 códigos con valor) y 4 EEFF genuinos se
descargaron y nunca se procesaron. El desglose real, del golden run:

```
  PROCESSED_OK    58    documentos extraídos (56 en el sprintf del sprint de runbooks)
  REJECTED         2    presentaciones alternativas, colisión de PK económica
  FAILED_FINAL   226    cáscaras del visor — no son documentos
  PENDING          0
  ------------------
  TOTAL          286
```

**El techo de 60 documentos no es un defecto del downloader, es la frontera
del formato:** la CNV pasó del PDF adjunto al formulario estructurado en
2018-2019; antes de 2019 el 100 % son adjuntos (`ATTACHMENT_ONLY` 197, cubren
2000-2018) y desde 2019 el 100 % son estructurados (`OTHER_FORM` 29 es el
formulario de participaciones, con datos reales de MetroEnergía). Existe lo que
los parsea hoy: nada.

**Lo que estas consultas NO pueden responder:**
- **¿El SHA es válido?** Se puede *calcular*, pero no hay contra qué
  compararlo: ninguna tabla de `screener.db` guarda el SHA256 de un documento
  CNV (`SG-02`).
- **¿Por qué un documento procesado no dejó filas?** El descarte solo suma al
  contador `err`. Hay que abrir el HTML y leer el extractor (`SG-04`).

---

## Paso 6 · Unidades y perímetros — los invariantes del dato CNV

Verificado sobre los 2.795 hechos canónicos del golden run (FASE 4-5):

| `unit_ref` | n | familia |
|---|---:|---|
| `ars@1e6` | 1.120 | monetarios, escala 10⁶ |
| `ars@1e3` | 915 | monetarios, escala 10³ |
| `pure` | 576 | ratios que publica la propia CNV (`CNV_*`, son dato, no cálculo) |
| `ars-por-accion` | 111 | EPS básico/diluido |
| `ars@1e0` | 73 | monetarios, escala 10⁰ |

- `currency = ARS` en 2.219; NULL en los 576 adimensionales, que es lo
  correcto. **La unidad nunca se pierde**; `decimals` es NULL por decisión
  certificada (la escala vive en `unit_ref`).
- Flujos vs saldos: **ningún flujo quedó tratado como INSTANT** (1.070
  INSTANT, 1.038 DURATION, 111 EPS DURATION). Todo `DURATION` arranca el
  1 de enero: la CNV acumula YTD.
- **NIL = "‑" no es 0.** El `"–"` del documento es ausencia, no valor.

---

## GATE de la Parte IX

| tema | estado |
|---|---|
| Tramo A | ejecutable, con gate; **sin EEFF** (`L-7`) |
| Tramo B | ejecutable, **sin gate ni ledger** (`L-6`); modifica `screener.db` |
| Tramo C | **`DECISION_REQUIRED` (D-1)** — no se ejecuta desde el repo principal |
| Diagnóstico | 7 situaciones distinguibles; **queda una pregunta sin respuesta** (validez del SHA, `SG-02`) |
| Cobertura | reconciliación manual; **no hay gate que la exija** (`SG-04`) |

Al terminar cualquier tramo, comprobá la huella:

```bash
stat -c '%y %s' data/screener.db
docker exec catalaxia-db psql -U catalaxia -d catalaxia -tAc \
  "SELECT string_agg(nspname,',') FROM pg_namespace \
    WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"
```

El tramo A no toca `screener.db`. El tramo B **sí** — y eso es correcto.
Producción debe seguir con `public` y nada más.

---

*Caso completo de diagnóstico y cifras de cobertura en
`GOLDEN_RUNS.md` §3 y `METROGAS_GOLDEN_RUN_REPORT.md`. Este capítulo no agrega
ningún comando que no esté en esas fuentes.*