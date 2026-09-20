# PROVENANCE — Market Data

Cadena completa por dato: `market_price_daily.source_run_id` → `market_raw_runs` → `market_raw_files` → archivo en disco (sha256 verificado ahora).

## 83 — YPFD.BA

### Corridas

| run_id | estado | fuente | version | fetched_at_utc | tz mercado | ruedas | min | max | sha256 RAW |
|---|---|---|---|---|---|---|---|---|---|
| golden-83-20260824T121230Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 12:12:30 | America/Argentina/Buenos_Aires | 6633 | 2000-01-03 | 2026-08-21 | 29fed2f584c9 |
| golden-retest-83-20260824T121325Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 12:13:25 | America/Argentina/Buenos_Aires | 6633 | 2000-01-03 | 2026-08-21 | b8bb254af498 |
| golden-v3-83-20260824T214105Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:41:05 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | 5f5e5100571d |
| golden-retest2-83-20260824T214132Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:41:32 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | c72cc8d7e704 |
| golden-retest3-83-20260824T214323Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:43:23 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | a5bfb48308d9 |
| golden-v4-83-20260824T214714Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:47:14 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | 0f8321d9148c |
| golden-retest4-83-20260824T214742Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:47:42 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | 8e5724c161be |
| golden-v5-83-20260824T222632563307Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 22:26:32 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | 968eebde9941 |
| golden-v5-retest-83-20260824T222714192051Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 22:27:14 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | 2d04fb44fe36 |
| golden-v5-retest5-83-20260825T042727797783Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-25 04:27:27 | America/Argentina/Buenos_Aires | 6634 | 2000-01-03 | 2026-08-24 | 7ea29b881f92 |

### Archivos RAW verificados

| run_id | tipo | ruta | bytes | sha256 | verificacion |
|---|---|---|---|---|---|
| golden-83-20260824T121230Z | HISTORY_CSV | data\raw\market\83\golden-83-20260824T121230Z\history.csv | 769612 | 29fed2f584c9 | OK |
| golden-retest-83-20260824T121325Z | HISTORY_CSV | data\raw\market\83\golden-retest-83-20260824T121325Z\history.csv | 769486 | b8bb254af498 | OK |
| golden-v3-83-20260824T214105Z | HISTORY_CSV | data\raw\market\83\golden-v3-83-20260824T214105Z\history.csv | 769472 | 5f5e5100571d | OK |
| golden-retest2-83-20260824T214132Z | HISTORY_CSV | data\raw\market\83\golden-retest2-83-20260824T214132Z\history.csv | 769743 | c72cc8d7e704 | OK |
| golden-retest3-83-20260824T214323Z | HISTORY_CSV | data\raw\market\83\golden-retest3-83-20260824T214323Z\history.csv | 769775 | a5bfb48308d9 | OK |
| golden-v4-83-20260824T214714Z | HISTORY_CSV | data\raw\market\83\golden-v4-83-20260824T214714Z\history.csv | 769696 | 0f8321d9148c | OK |
| golden-retest4-83-20260824T214742Z | HISTORY_CSV | data\raw\market\83\golden-retest4-83-20260824T214742Z\history.csv | 769638 | 8e5724c161be | OK |
| golden-v5-83-20260824T222632563307Z | HISTORY_CSV | data/raw/market/83/golden-v5-83-20260824T222632563307Z/history.csv | 769625 | 968eebde9941 | OK |
| golden-v5-83-20260824T222632563307Z | META_JSON | data/raw/market/83/golden-v5-83-20260824T222632563307Z/meta.json | 1316 | ca0ad18fedb4 | OK |
| golden-v5-retest-83-20260824T222714192051Z | HISTORY_CSV | data/raw/market/83/golden-v5-retest-83-20260824T222714192051Z/history.csv | 769597 | 2d04fb44fe36 | OK |
| golden-v5-retest-83-20260824T222714192051Z | META_JSON | data/raw/market/83/golden-v5-retest-83-20260824T222714192051Z/meta.json | 1323 | 4ef51794c67e | OK |
| golden-v5-retest5-83-20260825T042727797783Z | HISTORY_CSV | data/raw/market/83/golden-v5-retest5-83-20260825T042727797783Z/history.csv | 769664 | 7ea29b881f92 | OK |
| golden-v5-retest5-83-20260825T042727797783Z | META_JSON | data/raw/market/83/golden-v5-retest5-83-20260825T042727797783Z/meta.json | 1324 | 8da3fc3ef5d6 | OK |

**13/13 archivos RAW coinciden byte a byte con el sha256 registrado.**

## 84 — YPF

### Corridas

| run_id | estado | fuente | version | fetched_at_utc | tz mercado | ruedas | min | max | sha256 RAW |
|---|---|---|---|---|---|---|---|---|---|
| golden-84-20260824T121247Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 12:12:47 | America/New_York | 8344 | 1993-06-29 | 2026-08-21 | 326543e3ce8e |
| golden-retest-84-20260824T121335Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 12:13:35 | America/New_York | 8344 | 1993-06-29 | 2026-08-21 | 7d229dff9a04 |
| golden-v3-84-20260824T214115Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:41:15 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | b9672774f1eb |
| golden-retest2-84-20260824T214143Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:41:43 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | 07223539958d |
| golden-retest3-84-20260824T214335Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:43:35 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | ee1e705773a3 |
| golden-v4-84-20260824T214724Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:47:24 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | 4fc4b2506eb8 |
| golden-retest4-84-20260824T214752Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 21:47:52 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | d7b3e8f7290c |
| golden-v5-84-20260824T222644819597Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 22:26:44 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | 0c20878f9f08 |
| golden-v5-retest-84-20260824T222724322764Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-24 22:27:24 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | 1677993388ea |
| golden-v5-retest5-84-20260825T042739898974Z | SUCCESS | yahoo | yfinance@1.3.0 | 2026-08-25 04:27:39 | America/New_York | 8345 | 1993-06-29 | 2026-08-24 | 4a5045198441 |

### Archivos RAW verificados

| run_id | tipo | ruta | bytes | sha256 | verificacion |
|---|---|---|---|---|---|
| golden-84-20260824T121247Z | HISTORY_CSV | data\raw\market\84\golden-84-20260824T121247Z\history.csv | 979431 | 326543e3ce8e | OK |
| golden-retest-84-20260824T121335Z | HISTORY_CSV | data\raw\market\84\golden-retest-84-20260824T121335Z\history.csv | 979433 | 7d229dff9a04 | OK |
| golden-v3-84-20260824T214115Z | HISTORY_CSV | data\raw\market\84\golden-v3-84-20260824T214115Z\history.csv | 979654 | b9672774f1eb | OK |
| golden-retest2-84-20260824T214143Z | HISTORY_CSV | data\raw\market\84\golden-retest2-84-20260824T214143Z\history.csv | 979540 | 07223539958d | OK |
| golden-retest3-84-20260824T214335Z | HISTORY_CSV | data\raw\market\84\golden-retest3-84-20260824T214335Z\history.csv | 979646 | ee1e705773a3 | OK |
| golden-v4-84-20260824T214724Z | HISTORY_CSV | data\raw\market\84\golden-v4-84-20260824T214724Z\history.csv | 979639 | 4fc4b2506eb8 | OK |
| golden-retest4-84-20260824T214752Z | HISTORY_CSV | data\raw\market\84\golden-retest4-84-20260824T214752Z\history.csv | 979517 | d7b3e8f7290c | OK |
| golden-v5-84-20260824T222644819597Z | HISTORY_CSV | data/raw/market/84/golden-v5-84-20260824T222644819597Z/history.csv | 979513 | 0c20878f9f08 | OK |
| golden-v5-84-20260824T222644819597Z | META_JSON | data/raw/market/84/golden-v5-84-20260824T222644819597Z/meta.json | 1269 | 14a1c2f375a9 | OK |
| golden-v5-retest-84-20260824T222724322764Z | HISTORY_CSV | data/raw/market/84/golden-v5-retest-84-20260824T222724322764Z/history.csv | 979522 | 1677993388ea | OK |
| golden-v5-retest-84-20260824T222724322764Z | META_JSON | data/raw/market/84/golden-v5-retest-84-20260824T222724322764Z/meta.json | 1276 | 1d0041a55a1b | OK |
| golden-v5-retest5-84-20260825T042739898974Z | HISTORY_CSV | data/raw/market/84/golden-v5-retest5-84-20260825T042739898974Z/history.csv | 979562 | 4a5045198441 | OK |
| golden-v5-retest5-84-20260825T042739898974Z | META_JSON | data/raw/market/84/golden-v5-retest5-84-20260825T042739898974Z/meta.json | 1277 | 77fbfee64add | OK |

**13/13 archivos RAW coinciden byte a byte con el sha256 registrado.**
