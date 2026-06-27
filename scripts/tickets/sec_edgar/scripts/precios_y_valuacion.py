# -*- coding: utf-8 -*-
"""
Capa de precios + valuacion (PER, P/B, P/S, EV/EBITDA, yields).

Estrategia robusta para que funcione igual en acciones US y en ADR extranjeros:
usa MARKET CAP (yfinance lo da SIEMPRE en USD, sea US o ADR) en vez de
precio x acciones. Asi se evita el problema del "ratio del ADR" + acciones.

  PER = MarketCap_USD / NetIncome_USD
  donde NetIncome_USD = NetIncome_local * fx_a_usd  (fx=1 si ya reporta en USD)

Para los IFRS en moneda local (BRL/ARS) trae el tipo de cambio de yfinance.
ARS se marca con flag 'fx_ars' porque con la inflacion el ratio es poco fiable.

Lee building blocks de la tabla `ratios` (en moneda local) + precios yfinance.
Escribe la tabla `precios` y agrega columnas de valuacion a `ratios`.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir())
DB = ROOT / "data" / "screener.db"

PRICE_COLS = ["precio","market_cap","fx_a_usd","per","p_book","p_sales","ev_ebitda",
              "earnings_yield","fcf_yield","div_yield","flag_valuacion"]


def yf_ticker(t):  # yfinance usa '-' donde SEC usa '.'
    return t.replace(".", "-")


def fast(ticker):
    try:
        fi = yf.Ticker(yf_ticker(ticker)).fast_info
        return dict(last=fi.last_price, mcap=fi.market_cap, yhigh=fi.year_high,
                    ylow=fi.year_low, cur=fi.currency)
    except Exception:
        return None


def fx_rate(moneda, cache):
    """fx_a_usd: cuantos USD vale 1 unidad de la moneda local. USD -> 1."""
    if not moneda or moneda == "USD": return 1.0
    if moneda in cache: return cache[moneda]
    val = None
    try:
        # "BRL=X" en yfinance = USDBRL (cuantos BRL por 1 USD) -> invertir
        r = yf.Ticker(f"{moneda}=X").fast_info.last_price
        if r: val = 1.0 / r
    except Exception:
        val = None
    cache[moneda] = val
    return val


def main():
    con = sqlite3.connect(DB, timeout=60); con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    # asegurar columnas de valuacion en `ratios`
    existentes = {r[1] for r in cur.execute("PRAGMA table_info(ratios)")}
    for c in PRICE_COLS:
        if c not in existentes:
            tipo = "TEXT" if c == "flag_valuacion" else "REAL"
            con.execute(f'ALTER TABLE ratios ADD COLUMN "{c}" {tipo}')
    con.execute("""CREATE TABLE IF NOT EXISTS precios (
        cik TEXT PRIMARY KEY, ticker TEXT, precio REAL, market_cap REAL,
        year_high REAL, year_low REAL, currency TEXT, fecha TEXT)""")
    con.commit()

    filas = cur.execute("""SELECT cik, ticker, moneda, _netincome_ttm, _revenue_ttm,
        _ebitda_ttm, _equity, _deuda, _fcf_ttm, payout FROM ratios WHERE ticker IS NOT NULL""").fetchall()
    print(f"Bajando precios (yfinance) para {len(filas)} empresas...")
    fxc, ok, sinprecio = {}, 0, 0
    fecha = datetime.now(timezone.utc).isoformat()
    for i, (cik, tk, moneda, ni, rev, ebitda, eq, debt, fcf, payout) in enumerate(filas, 1):
        d = fast(tk)
        if not d or not d.get("mcap"):
            sinprecio += 1
            if i % 50 == 0: con.commit()
            continue
        mcap = d["mcap"]; precio = d["last"]
        fx = fx_rate(moneda, fxc)
        flag = "fx_ars" if moneda == "ARS" else ("sin_fx" if fx is None else None)
        def usd(x): return (x * fx) if (x is not None and fx is not None) else None
        ni_u, rev_u, eb_u, eq_u, debt_u, fcf_u = map(usd, (ni, rev, ebitda, eq, debt, fcf))
        cash_u = None  # (deuda neta usa _deuda; cash ya neteado no esta aqui)
        per = (mcap / ni_u) if (ni_u and ni_u > 0) else None
        p_book = (mcap / eq_u) if (eq_u and eq_u > 0) else None
        p_sales = (mcap / rev_u) if (rev_u and rev_u > 0) else None
        ev = (mcap + debt_u) if (debt_u is not None) else mcap
        ev_ebitda = (ev / eb_u) if (eb_u and eb_u > 0) else None
        earnings_yield = (ni_u / mcap) if (ni_u is not None and mcap) else None
        fcf_yield = (fcf_u / mcap) if (fcf_u is not None and mcap) else None
        divs_u = (payout * ni_u) if (payout is not None and ni_u is not None) else None
        div_yield = (divs_u / mcap) if (divs_u is not None and mcap) else None

        con.execute("INSERT OR REPLACE INTO precios VALUES (?,?,?,?,?,?,?,?)",
                    (cik, tk, precio, mcap, d.get("yhigh"), d.get("ylow"), d.get("cur"), fecha))
        con.execute(f"""UPDATE ratios SET precio=?, market_cap=?, fx_a_usd=?, per=?, p_book=?, p_sales=?,
            ev_ebitda=?, earnings_yield=?, fcf_yield=?, div_yield=?, flag_valuacion=? WHERE cik=?""",
            (precio, mcap, fx, per, p_book, p_sales, ev_ebitda, earnings_yield, fcf_yield, div_yield, flag, cik))
        ok += 1
        if i % 50 == 0:
            con.commit(); print(f"  {i}/{len(filas)} (ok={ok}, sin_precio={sinprecio})")
    con.commit()
    print(f"\nOK: {ok} con valuacion, {sinprecio} sin precio en yfinance")
    print(f"FX usados: {{ {', '.join(f'{k}={v:.5f}' if v else f'{k}=?' for k,v in fxc.items())} }}")
    n_per = con.execute("SELECT COUNT(*) FROM ratios WHERE per IS NOT NULL").fetchone()[0]
    print(f"Empresas con PER: {n_per}")
    con.close()


if __name__ == "__main__":
    main()
