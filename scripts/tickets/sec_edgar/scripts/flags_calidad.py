# -*- coding: utf-8 -*-
"""
Capa de FLAGS de calidad sobre la tabla `ratios`. El cinturon de seguridad:
marca donde NO confiar ciegamente, sin borrar el dato.

Flags:
  ni_fy        : el "TTM" salio del ultimo anio fiscal (estrategia C), no un TTM
                 rodante -> PER/EPS/margen/ROE/payout pueden divergir por un item
                 no recurrente reciente.
  roe_ns       : equity < 5% de los activos (recompras) -> ROE no interpretable
                 (ej. GDDY ROE 398%).
  fx           : reporta en ARS (inflacion -> valuacion poco fiable) o sin FX.
  mktcap_rev   : el market cap de yfinance discrepa >50% del precio x acciones
                 reportadas (EDGAR) -> valuacion sospechosa (ej. ADBE). Solo se
                 aplica a empresas US (en ADRs las acciones son ordinarias, no
                 equivalentes al ADR, asi que no aplica).

Agrega columnas flag_* (0/1) y una columna `flags` (texto, los activos separados
por ';') a la tabla ratios.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir()) / "data" / "screener.db"
FLAG_COLS = ["flag_ni_fy","flag_roe_ns","flag_fx","flag_mktcap_rev"]


def main():
    con = sqlite3.connect(DB, timeout=60); con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    existentes = {r[1] for r in cur.execute("PRAGMA table_info(ratios)")}
    for c in FLAG_COLS:
        if c not in existentes:
            con.execute(f'ALTER TABLE ratios ADD COLUMN "{c}" INTEGER DEFAULT 0')
    if "flags" not in existentes:
        con.execute('ALTER TABLE ratios ADD COLUMN "flags" TEXT')
    con.commit()

    # shares outstanding mas reciente por empresa (para el chequeo de market cap)
    sh = {}
    for cik, val in cur.execute("""SELECT cik, val FROM facts WHERE concepto='SharesOutstanding'
            AND unit='shares' AND period_end=(SELECT MAX(period_end) FROM facts f2
            WHERE f2.cik=facts.cik AND f2.concepto='SharesOutstanding') GROUP BY cik"""):
        sh[cik] = val

    filas = cur.execute("""SELECT cik, ticker, grupo, moneda, ni_estrategia, _equity, _assets,
        per, precio, market_cap, flag_valuacion FROM ratios""").fetchall()
    n = 0
    cuenta = {c: 0 for c in FLAG_COLS}
    for (cik, tk, grupo, moneda, estr, eq, ass, per, precio, mcap, flag_val) in filas:
        f_ni = 1 if estr == "C" else 0
        f_roe = 1 if (eq is not None and ass and ass > 0 and eq < 0.05 * ass) else 0
        f_fx = 1 if (flag_val in ("fx_ars", "sin_fx")) else 0
        f_mc = 0
        if grupo in ("sp500", "us_other") and (moneda == "USD" or moneda is None) and precio and mcap and cik in sh and sh[cik]:
            implied = precio * sh[cik]
            if implied > 0 and abs(implied - mcap) / mcap > 0.5:
                f_mc = 1
        flags = ";".join([nm for nm, v in
                          [("ni_fy", f_ni), ("roe_ns", f_roe), ("fx", f_fx), ("mktcap_rev", f_mc)] if v])
        con.execute("""UPDATE ratios SET flag_ni_fy=?, flag_roe_ns=?, flag_fx=?, flag_mktcap_rev=?, flags=? WHERE cik=?""",
                    (f_ni, f_roe, f_fx, f_mc, flags or None, cik))
        for c, v in zip(FLAG_COLS, (f_ni, f_roe, f_fx, f_mc)):
            cuenta[c] += v
        n += 1
        if n % 200 == 0: con.commit()
    con.commit()
    print(f"Flags aplicados a {n} empresas.")
    for c in FLAG_COLS:
        print(f"  {c:<16} {cuenta[c]:>4}")
    limpias = con.execute("SELECT COUNT(*) FROM ratios WHERE flags IS NULL").fetchone()[0]
    print(f"  {'(sin flags)':<16} {limpias:>4}")
    con.close()


if __name__ == "__main__":
    main()
