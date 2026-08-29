# -*- coding: utf-8 -*-
"""
M1 -- Symbol mapping: Identity canonica -> Yahoo
=================================================
Lee identidad desde data/screener.db (dim_entity + dim_instrument) y
puebla market_instruments + market_symbol_mappings en PostgreSQL.

Reglas:
  * tipo='adr'      -> instrument_type=ADR,   ticker_yahoo = ticker tal cual
  * tipo ordinario  -> instrument_type=LOCAL, ticker_yahoo = ticker + '.BA'
  * CERO mappings inventados: si no se puede derivar -> UNMAPPED
  * ticker_yahoo repetido entre instrumentos distintos -> CONFLICT/AMBIGUOUS

F-014: ademas de ticker_canonico (clave del EMISOR, sin cambios de significado),
puebla venue_ticker (simbolo de ESTA fila en su exchange) via
`f014_venue_ticker.derivar_venue_ticker()`, exclusivamente desde
`dim_instrument.ticker` -- nunca desde `dim_entity.ticker_canonico`. Ver
outputs/docs/fase_market/F014_VENUE_TICKER_CONTRACT.md.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
SQLITE = ROOT / "data" / "screener.db"

BYMA_MERCADOS = {"BYMA", "BYMA/BOLSAS", "PANEL GENERAL"}


import market_db
import f014_venue_ticker as venue


def pg_conn(*, write: bool = False):
    """Conexion a PostgreSQL a traves de la guarda F-001 (market_db).

    SOLO LECTURA por defecto. Escribir exige `write=True` en el call site y, si
    el destino es el puerto 5432, ademas `MARKET_ALLOW_PROD_WRITE=1`.
    """
    return market_db.connect(None, write=write)


def derivar(ticker: str, mercado: str, tipo: str):
    """Devuelve (instrument_type, ticker_yahoo|None, nota)."""
    t = (ticker or "").strip()
    merc = (mercado or "").upper()
    tip = (tipo or "").lower()
    if not t or t.startswith("_ADR_"):
        return None, None, f"ticker invalido/sintetico: {t!r}"
    if tip == "adr" or ("NYSE" in merc or "NASDAQ" in merc):
        if "." in t:
            return None, None, f"ADR con punto sospechoso: {t}"
        return "ADR", t, None
    if merc in BYMA_MERCADOS or merc.startswith("BYMA"):
        return "LOCAL", f"{t}.BA", None
    if merc == "US" and "." not in t:
        # subyacente norteamericano del universo CEDEAR:
        # el ticker canonico YA es simbolo Yahoo
        return "US", t, None
    return None, None, f"mercado/tipo no reconocido: {merc}/{tip}"


def main():
    lite = sqlite3.connect(SQLITE)
    filas = lite.execute("""
        SELECT di.instrument_id, di.entity_id, de.ticker_canonico,
               de.cuit, de.grupo, di.ticker, di.mercado, di.tipo, di.moneda, di.ratio
        FROM dim_instrument di
        LEFT JOIN dim_entity de ON de.entity_id = di.entity_id
        ORDER BY di.instrument_id
    """).fetchall()
    lite.close()

    # primer paso: construir registros derivados
    regs, por_yahoo = [], {}
    for iid, eid, canon, cuit, grupo, tick, merc, tipo, moneda, ratio in filas:
        itype, tyahoo, nota = derivar(tick, merc, tipo)
        status = "MAPPED" if tyahoo else "UNMAPPED"
        exchange = ("NYSE" if itype == "ADR" else "BUE" if itype == "LOCAL" else None) if itype else None
        vr = venue.derivar_venue_ticker(canon, tick, exchange)
        regs.append(dict(
            instrument_id=str(iid), entity_id=str(eid),
            ticker_canonico=(canon or tick or "").strip(),
            instrument_type=itype, exchange=exchange,
            country="AR", currency=(moneda or "").strip().upper() or None,
            security_type=(tipo or "").strip() or None,
            ratio_adr=ratio, ticker_yahoo=tyahoo, status=status,
            conflict_detail=nota,
            venue_ticker=vr.venue_ticker, venue_ticker_source=vr.venue_ticker_source,
        ))
        if tyahoo:
            por_yahoo.setdefault(tyahoo, []).append(str(iid))

    # colisiones de simbolo yahoo
    for ty, iids in por_yahoo.items():
        if len(iids) > 1:
            for r in regs:
                if r["ticker_yahoo"] == ty:
                    r["status"] = "CONFLICT"
                    r["conflict_detail"] = f"simbolo compartido con {','.join(i for i in iids if i != r['instrument_id'])}"

    now = datetime.now(timezone.utc)
    conn = pg_conn(write=True)          # escribe market_symbol_mappings
    cur = conn.cursor()
    psycopg2.extras.execute_values(cur, """
        INSERT INTO market_instruments
            (instrument_id, entity_id, ticker_canonico, instrument_type, exchange,
             country, currency, security_type, ratio_adr, source, active,
             venue_ticker, venue_ticker_source)
        VALUES %s
        ON CONFLICT (instrument_id) DO UPDATE SET
            entity_id=EXCLUDED.entity_id, ticker_canonico=EXCLUDED.ticker_canonico,
            instrument_type=EXCLUDED.instrument_type, exchange=EXCLUDED.exchange,
            currency=EXCLUDED.currency, security_type=EXCLUDED.security_type,
            ratio_adr=EXCLUDED.ratio_adr, updated_at=now(),
            venue_ticker=EXCLUDED.venue_ticker,
            venue_ticker_source=EXCLUDED.venue_ticker_source
    """, [(
        r["instrument_id"], r["entity_id"], r["ticker_canonico"],
        r["instrument_type"] or "OTHER", r["exchange"], r["country"],
        r["currency"], r["security_type"], r["ratio_adr"], "dim_instrument", True,
        r["venue_ticker"], r["venue_ticker_source"],
    ) for r in regs], page_size=500)

    psycopg2.extras.execute_values(cur, """
        INSERT INTO market_symbol_mappings
            (instrument_id, ticker_yahoo, exchange_expected, currency_expected,
             status, conflict_detail, source, resolved_at)
        VALUES %s
        ON CONFLICT (instrument_id) DO UPDATE SET
            ticker_yahoo=EXCLUDED.ticker_yahoo,
            exchange_expected=EXCLUDED.exchange_expected,
            currency_expected=EXCLUDED.currency_expected,
            status=EXCLUDED.status, conflict_detail=EXCLUDED.conflict_detail,
            resolved_at=EXCLUDED.resolved_at
    """, [(
        r["instrument_id"], r["ticker_yahoo"], r["exchange"], r["currency"],
        r["status"], r["conflict_detail"], "dim_instrument",
        now if r["status"] == "MAPPED" else None,
    ) for r in regs], page_size=500)
    conn.commit()

    # resumen
    from collections import Counter
    c_status = Counter(r["status"] for r in regs)
    c_tipo = Counter(r["instrument_type"] or "?" for r in regs)
    diverge = [r for r in regs if r["venue_ticker"] and r["venue_ticker"] != r["ticker_canonico"]]
    print(f"instrumentos procesados : {len(regs)}")
    print("por estado              :", dict(c_status))
    print("por tipo                :", dict(c_tipo))
    print(f"venue_ticker != ticker_canonico (F-014): {len(diverge)}")
    for r in sorted(diverge, key=lambda r: r["instrument_id"]):
        print(f"  {r['instrument_id']:>6} canonico={r['ticker_canonico']:<8} venue_ticker={r['venue_ticker']}")
    unmapped = [r for r in regs if r["status"] == "UNMAPPED"]
    conflicts = [r for r in regs if r["status"] == "CONFLICT"]
    if unmapped:
        print(f"\nUNMAPPED ({len(unmapped)}):")
        for r in unmapped[:12]:
            print(f"  {r['instrument_id']:>6} {r['ticker_canonico']:<10} {r['conflict_detail']}")
        if len(unmapped) > 12:
            print(f"  ... y {len(unmapped)-12} mas")
    if conflicts:
        print(f"\nCONFLICT ({len(conflicts)}):")
        for r in conflicts[:10]:
            print(f"  {r['instrument_id']:>6} {r['ticker_canonico']:<10} {r['ticker_yahoo']:<10} {r['conflict_detail']}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
