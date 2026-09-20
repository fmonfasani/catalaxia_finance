# 22 — F10 Security: Auditoría formal de endpoints TLS

Auditoría de los 52 sitios con `verify=False` (baseline de F0) + endpoints del motor, con
estado TLS comprobado en vivo (TLSv1.3, handshake con cadena de confianza pública).
Clasificación: **camino productivo** (se endurece) vs **exploratorio one-shot** (se documenta, no se toca).

## Endpoints del camino productivo — TLS verificado + endurecidos (fail-closed)

| # | Endpoint | Consumido por | TLS (vivo, 2026-09-08) | Acción |
|---|---|---|---|---|
| 1 | `aif2.cnv.gov.ar/presentations/publicview/{guid}` | job5_v2 `:264`, job5 `:135`, job6 `:95`, pipeline/fetch_dgce `:17` | OK · Sectigo · TLSv1.3 · vence 2027-04-09 | `verify=False` → `verify=VERIFY` |
| 2 | `dolarapi.com/v1/dolares` | dolares/_dolar `:29` | OK · Google Trust · TLSv1.3 · 2026-11-11 | ídem |
| 3 | `criptoya.com/api/dolar` | dolares/_dolar `:36` | OK · Google Trust · TLSv1.3 · 2026-12-05 | ídem |
| 4 | `api.dolarito.ar/api/frontend/history/series` | dolares/fetch_dolarito_historico `:102` | OK · Google Trust · TLSv1.3 · 2026-11-30 | ídem |
| 5 | `comafi.com.ar/custodiaglobal/json/apps/getproducts.aspx` | tickets/screener/cedear_ratios `:50` (vía run_update --rebuild/--quarterly) | OK · DigiCert · TLSv1.3 · 2027-01-06 | ídem |
| 6 | `api.markitdigital.com/jpmadr-public/v1/*` | tickets/screener/jpm_adr `:48` (ídem) | OK · DigiCert · TLSv1.3 · 2026-09-28 | ídem |

El motor (`engine/`) **no tenía** `verify=False` (evidencia F0): usa el default de `requests`
(verificación activa). Fuentes del motor verificadas: `query1.finance.yahoo.com` (DigiCert,
2026-10-07), `www.sec.gov` (DigiCert, 2026-12-11), `data.sec.gov` (DigiCert, 2027-03-01) — OK.
`download.sec.gov` no resuelve públicamente (DNS fail) pero no es usado por el motor.

`run_update.py` (cron daily/quarterly): sus llamadas propias (datos.gob.ar, data.sec.gov,
cnv.gov.ar) ya usaban verificación por defecto; solo sobraba `urllib3.disable_warnings()` en su
proceso → **eliminado** (los warnings de TLS deben ser visibles).

## Mecanismo aplicado (fail-closed con escape explícito)

En cada script productivo: `VERIFY = os.environ.get("REQUESTS_VERIFY", "1") != "0"`, usado en
lugar de `verify=False`. Default **verifica** (fail-closed): si un certificado de fuente se rompe,
el job falla en voz alta y es registrado por el propio mecanismo resume-safe del script. Solo un
`REQUESTS_VERIFY=0` explícito y documentado como transitorio (mitigación MITM / integridad de RAW
quedan anotadas) desactiva la verificación. `requests` emite `InsecureRequestWarning` en ese caso
(no se silencia más).

## Exploratorio one-shot — NO se toca, queda documentado

`scripts/tickets/cnv/scripts/*` (cnv_ir, explorar_*, extract_*, grim_pipeline, _tmp_*, check_*,
comparar_*, verificar_*, derivar_*, cruce_*), `scripts/tickets/screener/_download_diagnostico.py`:
herramientas de análisis único / tickets, fuera del pipeline recurrente. Endpoints usados son los
mismos aif2/CNV y SEC de la tabla anterior (TLS válido). NO se aplicó el fix para no alterar la
reproducibilidad de análisis pasados; si alguna se reutiliza, migrar al mismo `REQUESTS_VERIFY`.

## Verificación

- Compilación: 10 archivos modificados `py_compile` OK.
- Live read-only: `_dolar.dolarapi()` y `_dolar.criptoya()` con `VERIFY=True` (default) → 7 y 8
  casas OK contra dolarapi.com y criptoya.com.
- Handshake TLS de los 9 hosts productivos + motor: todos TLSv1.3, cadena pública válida.

Cierre: **gap 1 (TLS) del 21_F9_GAP_MATRIX → ADDRESSED**. Fuentes sin bypass en camino productivo;
motor ya no tenía; bypass residual solo en herramientas one-shot documentadas.