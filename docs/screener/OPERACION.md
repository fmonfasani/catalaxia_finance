# Operación del screener — correr, actualizar, mantener

> Manual operativo del pipeline productivo (500 S&P + 16 ADR + 56 BYMA-only = 571 empresas).
> Cómo reconstruir desde cero, cómo actualizar, cómo están programados los jobs, qué hacer si
> algo falla, y cómo mover la base entre máquinas.
> Contexto y arquitectura: [PLAN_PIPELINE_COMPLETO.md](PLAN_PIPELINE_COMPLETO.md).

---

## 0. TL;DR

| Quiero… | Comando |
|---|---|
| Reconstruir todo desde cero | `python run_all.py` |
| Reensamblar desde cache (rápido, offline) | `python run_all.py --skip-extract --skip-transform` |
| Actualizar precios (diario) | `python run_update.py --daily` |
| Actualizar fundamentales (trimestral) | `python run_update.py --quarterly` |
| Actualizar IPC (mensual) | `python run_update.py --monthly` |
| Actualizar ratio ADR (anual) | `python run_update.py --annual` |

Todos los scripts viven en `scripts/tickets/screener/`. Se corren **desde esa carpeta**.
Cada corrida deja log en `data/logs/`.

---

## 1. Precondición

- **`data/screener.db`** (~750 MB) debe estar presente. **No está en git** (ver §6).
- Dependencias: `pip install -r requirements.txt` (yfinance, requests, pandas…).
- Una sola instancia a la vez (SQLite: escritura concurrente se bloquea). Los scripts abren
  con `PRAGMA journal_mode=WAL` y `busy_timeout=60000`, pero **no corras dos jobs en paralelo**.

---

## 2. Reconstrucción desde cero — `run_all.py`

Orquesta el pipeline canónico completo:

```
EXTRACT  →  TRANSFORM  →  ASSEMBLE  →  EXPORT
```

- **EXTRACT** (red, lento): EDGAR companyfacts (saltea CIK ya cacheados), CNV discovery
  (opcional, `--with-cnv-fresh`), ratio ADR del 20-F/F-6.
- **TRANSFORM**: `calcular_ratios_base` (ratios EDGAR desde `facts`) **+** `precios_y_valuacion`
  (precios yfinance + `per`/`p_book`/`p_sales`/`ev_ebitda`).
  ⚠️ **Van SIEMPRE juntos**: `calcular_ratios_base` **dropea y recrea** la tabla `ratios`
  *sin* la columna `per`; `precios_y_valuacion` la vuelve a crear. Correr el primero sin el
  segundo deja `ratios` sin `per` → el PER de las 499 S&P queda en NULL (falla silenciosa,
  el pipeline "corre OK" pero la cobertura de PER cae a 0%). `run_all.py` los corre apareados.
- **ASSEMBLE**: `s0 → s2 → s3 → s4 → s6 → s7 → s8`.
- **EXPORT**: `s5 → data/screener_export.csv`.

Flags:

| Flag | Efecto |
|---|---|
| *(sin flags)* | todo; el extract saltea lo cacheado |
| `--skip-extract` | reusa `facts`/`cnv_estados_v2` cacheados (no baja de EDGAR/CNV) |
| `--skip-transform` | **no** recalcula `ratios` (mantiene la tabla tal cual) |
| `--offline` | sin red (implica `--skip-extract`) |
| `--only extract\|transform\|assemble\|export` | corre un solo stage |
| `--with-cnv-fresh` | además corre discovery CNV completo (job1..job7), frágil/lento |

**Verificación automática al final**: imprime `screener: 571 filas` y avisa si no dan 571.

> Nota: una reconstrucción *verdaderamente* desde cero (máquina limpia, sin cache) baja
> todo EDGAR (~600 CIK) + CNV (frágil, con rate-limit) → **horas**. Con cache/incremental
> las corridas siguientes son de minutos.

---

## 3. Actualización periódica — `run_update.py`

| Modo | Frecuencia | Qué hace | Duración típica |
|---|---|---|---|
| `--daily` | diario | yfinance: precio, máx/mín 52s, market cap (571) | <1 min |
| `--monthly` | mensual | baja IPC INDEC (serie 145.3, variación activa) y reconstruye el índice | ~10 s |
| `--quarterly` | trimestral | EDGAR incremental (CIK con `lastFiled` nuevo en 10-K/10-Q/20-F) + CNV incremental (subset, resume-safe) + **rebuild** (s0→s8→s5) | ~200 s |
| `--annual` | anual | `sec_adr_ratios` contra el 20-F nuevo | ~35 s |
| `--rebuild` | manual | solo el rebuild (s0→s8→s5), sin bajar nada | ~120 s |

- **Incremental de EDGAR**: compara `lastFiled` de SEC contra `empresas.fecha_facts` **por CIK**,
  y **solo** dispara con forms fundamentales (`10-K/10-Q/20-F` y `/A`) — no con 8-K/Form 4.
- **Incremental de CNV**: acotado al subset de 72 CUITs. Chequea conectividad con
  **reintentos + backoff** (5/10/20s sobre 2 URLs); la extracción de nuevos códigos
  reintenta 1 vez. Si CNV sigue caído, **difiere** (no cuelga, no arrastra dato viejo en
  silencio) y escribe `data/logs/cnv_last_status.json` con `deferred`, `new_codigos`
  pendientes, `newest_period` y `stale_days`. En `--quarterly` el resumen loguea `[!] CNV
  DIFERIDO` para que se note. **Monitoreo**: chequear ese JSON tras cada run trimestral.
- Todo idempotente. Cada corrida deja `data/logs/upd_YYYYMMDD_HHMMSS.log`.

---

## 4. Programación (Windows Task Scheduler)

Los jobs corren donde está la DB (local/VM), **no** en GitHub Actions (la DB no va a git).

### 4.1 Alta rápida (PowerShell, como admin)

Usar el script `scripts/tickets/screener/setup_scheduler.ps1` (crea las 4 tareas), **o**
a mano con `schtasks`:

```powershell
$py  = (Get-Command python).Source
$dir = "D:\Software Development\Porfolio\catalaxia-cedears-prod\scripts\tickets\screener"

# Diario 18:30 — precios
schtasks /Create /TN "Screener\Daily-Precios" /SC DAILY /ST 18:30 `
  /TR "cmd /c cd /d `"$dir`" && `"$py`" run_update.py --daily --quiet" /F

# Trimestral (día 1 de ene/abr/jul/oct) 03:00 — fundamentales + rebuild
schtasks /Create /TN "Screener\Quarterly-Fundamentales" /SC MONTHLY /MO 3 /D 1 /ST 03:00 `
  /TR "cmd /c cd /d `"$dir`" && `"$py`" run_update.py --quarterly --quiet" /F

# Mensual (día 5) 04:00 — IPC
schtasks /Create /TN "Screener\Monthly-IPC" /SC MONTHLY /D 5 /ST 04:00 `
  /TR "cmd /c cd /d `"$dir`" && `"$py`" run_update.py --monthly --quiet" /F

# Anual (2 de abril) 05:00 — ratio ADR
schtasks /Create /TN "Screener\Annual-ADR" /SC YEARLY /D 2 /M APR /ST 05:00 `
  /TR "cmd /c cd /d `"$dir`" && `"$py`" run_update.py --annual --quiet" /F
```

### 4.2 Verificar / correr / borrar

```powershell
schtasks /Query  /TN "Screener\Daily-Precios" /V /FO LIST   # estado + último resultado
schtasks /Run    /TN "Screener\Daily-Precios"               # disparar ahora (probar)
schtasks /Delete /TN "Screener\Daily-Precios" /F            # borrar
```

Un `Last Result` de `0x0` = OK. Distinto de 0 → revisar el log de esa corrida en `data/logs/`.

---

## 5. Si algo falla — diagnóstico

Primero: mirar el último log en `data/logs/` (los jobs escriben ahí siempre, aun en `--quiet`).

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `no such column: per` en s6/s7 | `ratios` quedó sin `per` (corrió `calcular_ratios_base` sin `precios_y_valuacion`) | `python run_all.py --only transform` (los corre apareados y restaura `per`), después `--rebuild` |
| PER de S&P en 0% pero "corre OK" | mismo caso anterior (falla silenciosa) | idem arriba; **verificar cobertura**, no solo el conteo de filas |
| `database is locked` | dos procesos tocando la DB, o una fase no cerró conexión | correr **una sola** instancia; el rebuild ya intercala `sleep` entre fases |
| `--daily` con muchos `[ERR] … no_data` | yfinance rate-limit (429) o ticker deslistado | reintentar más tarde; es tolerante (sigue con el resto) |
| EDGAR 403 | falta header User-Agent | ya seteado en los scripts; si persiste, SEC te bloqueó — esperar |
| CNV cuelga / timeout | CNV caído o rate-limit | `--quarterly` reintenta con backoff (5/10/20s); si sigue caído **difiere** y lo deja registrado (no arrastra dato viejo en silencio). Ver `data/logs/cnv_last_status.json` |
| BYMA con dato viejo | CNV estuvo caído varios runs | revisar `cnv_last_status.json`: `deferred:true` + `stale_days`. Si `stale_days > 180` con códigos nuevos pendientes → correr `--quarterly` cuando CNV vuelva |
| export con < 571 filas | alguna fase de assemble falló | ver qué fase dio `FAILED` en el log y correr `run_all.py --only assemble` |

**Regla de oro**: *"corre sin error" ≠ "actualizó bien"*. Después de un `--quarterly` o `run_all`,
verificar **cobertura por universo** (§ siguiente), no solo que dio 571 filas.

Chequeo rápido de salud:
```bash
python -c "import sqlite3;c=sqlite3.connect('data/screener.db').cursor();\
print('filas',c.execute('SELECT COUNT(*) FROM screener').fetchone()[0]);\
print('PER sp500',c.execute(\"SELECT COUNT(*) FROM screener WHERE grupo='sp500' AND PER IS NOT NULL\").fetchone()[0],'/499')"
```

---

## 6. Mover la base entre máquinas

- **`data/screener.db`** (~750 MB) **no va a git** (está en `.gitignore`). Se mueve aparte:
  copia directa (USB/red), o comprimida (`screener.db` → `.zip`, baja bastante).
- Lo que **sí** está versionado: todo el código (`scripts/`), los docs, los CSV chicos
  (`adr_ratios.csv`, `adr_tickers.csv`, `ipc_nacional.csv`, `screener_export.csv`) y las
  listas de universo. Con eso + la DB, cualquier máquina reconstruye/actualiza.
- En una máquina **sin** DB: hace falta el raw cache (`data/raw/`) para saltear la descarga,
  o correr `run_all.py` completo (baja todo de EDGAR/CNV — horas).
- Tras copiar la DB: `python run_all.py --skip-extract --skip-transform` para confirmar que
  ensambla y exporta 571 filas en la máquina nueva.

---

## 7. Mapa de archivos

```
scripts/tickets/screener/
  run_all.py        ← reconstrucción end-to-end (this doc §2)
  run_update.py     ← jobs periódicos (this doc §3)
  run_screener.py   ← solo assemble (s0→s8→s5), sin bajar nada
  s0..s8            ← stages de assemble
scripts/tickets/sec_edgar/scripts/
  construir_base.py         ← EXTRACT EDGAR (companyfacts)
  calcular_ratios_base.py   ← TRANSFORM (ratios desde facts) — dropea `ratios`
  precios_y_valuacion.py    ← TRANSFORM (precios + per/valuación) — restaura `per`
  sec_adr_ratios.py         ← ratio ADR oficial (20-F/F-6)
scripts/tickets/cnv/jobs/
  job1..job7                ← discovery + extract CNV (BYMA-only)
data/
  screener.db               ← base (no en git)
  screener_export.csv       ← entregable (versionado)
  ipc_nacional.csv          ← IPC INDEC (deflactor CAGR)
  logs/                     ← un log por corrida
```
