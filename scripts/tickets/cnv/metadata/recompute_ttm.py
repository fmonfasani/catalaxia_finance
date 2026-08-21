# -*- coding: utf-8 -*-
"""Stage recompute_ttm: EPS/PER estilo IAMC para empresas CNV (only-BYMA).

Usa el fin de ejercicio AUTORITATIVO de fiscal_calendar (no lo adivina) para
des-acumular NetIncome (YTD->trimestre), suma TTM (ultimos 4 trimestres) y publica
PER_ttm SOLO si pasa los gates; si no, guion con motivo. Cero falsos positivos.

Escribe la tabla paralela `per_ttm` (no toca `screener`) con provenance + estado.

    python scripts/tickets/cnv/metadata/recompute_ttm.py         # corre + reporte
    python scripts/tickets/cnv/metadata/recompute_ttm.py --test  # tests golden

Metodo IAMC (fuente: PDF "Analisis de Acciones"): EPS = suma 4 trimestres netos;
si EPS<=0 -> guion. Ver memoria per-ttm-iamc-method.
"""
from __future__ import annotations
import os as _os
import argparse, os, sqlite3, sys, datetime as dt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DB = os.path.join(ROOT, "data", _os.environ.get("SCREENER_DB", "screener.db"))
FRESH_MONTHS = 15
REV_CANDS = ["Revenue", "Ventas", "IngresosOrdinarios"]


def mb(a, b):  # meses entre dos period_end 'YYYY-MM-DD'
    return (int(b[:4]) - int(a[:4])) * 12 + (int(b[5:7]) - int(a[5:7]))


def qnum(month, fy):        # 1..4, con fy=mes de cierre => Q4
    return 4 - ((fy - month) % 12) // 3


def series(cur, cuit, concepto):
    d = {}
    for pe, v in cur.execute(
        "select period_end,valor from cnv_estados_v2 where cuit=? and concepto=? "
        "and valor is not null order by period_end", (cuit, concepto)):
        d[pe] = v
    return sorted(d.items())


def decum(ser, fy):
    """YTD acumulado -> trimestre standalone, usando fin de ejercicio fy (autoritativo)."""
    out, prev = [], None
    for pe, cum in ser:
        q = qnum(int(pe[5:7]), fy)
        sa = cum if q == 1 else (cum - prev[1] if (prev and mb(prev[0], pe) == 3) else None)
        out.append((pe, sa)); prev = (pe, cum)
    return out


def ttm_last4(ser, fy):
    """Devuelve (ttm, window[4], motivo_o_None)."""
    sa = [(pe, v) for pe, v in decum(ser, fy) if v is not None]
    if len(sa) < 4:
        return None, None, "pocos_trimestres"
    w = sa[-4:]
    if any(mb(w[i][0], w[i + 1][0]) != 3 for i in range(3)):
        return None, None, "gap_trimestres"
    return sum(v for _, v in w), w, None


def rev_concept(cur):
    for k in REV_CANDS:
        if cur.execute("select 1 from cnv_estados_v2 where concepto=? limit 1", (k,)).fetchone():
            return k
    return None


def derive_shares(cur, cuit):
    """Acciones = mediana de NetIncome/EPS_basico entre periodos (robusto a outliers:
    Q1 con EPS chico infla shares; EPS corrupto lo hunde -> la mediana los descarta)."""
    ni = dict(series(cur, cuit, "NetIncome"))
    eb = dict(series(cur, cuit, "EPS_basico"))
    vals = []
    for pe, e in eb.items():
        n = ni.get(pe)
        if n is not None and e and abs(e) > 0.5:
            sh = n / e
            if sh > 0:
                vals.append(sh)
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def compute(cur, dbmax, revk):
    fcal = {cu: fy for cu, fy in cur.execute("select cuit,fy_end_month from fiscal_calendar")}
    # `precio_ars` desaparecio en la migracion IAMC -> MEP (commit e88b450): era la
    # columna de precio en pesos cuando el dolar de referencia salia de IAMC. Su
    # equivalente hoy es `Precio`, que para byma_only es el precio nativo en ARS
    # (Aluar 968,50; A3 3.425,00 -- los precios de pantalla en BYMA).
    # Sin este cambio el script muere con "no such column: precio_ars".
    uni = cur.execute("select cuit,ticker,ultimo_periodo,EPS,PER,Precio,MarketCapUSD from screener "
                      "where grupo='byma_only'").fetchall()
    rows = []
    for cuit, tk, up, eps, per, pxars, mcap in uni:
        fy = fcal.get(cuit)
        had_per = per is not None and str(per).strip() not in ("", "None")
        if fy is None:
            rows.append((cuit, tk, None, None, None, "sin_fiscal_calendar", had_per)); continue
        ser = series(cur, cuit, "NetIncome")
        ttm, w, motivo = ttm_last4(ser, fy)
        if motivo:
            rows.append((cuit, tk, None, None, None, motivo, had_per)); continue
        last = w[-1][0]
        if mb(last, dbmax) > FRESH_MONTHS:
            rows.append((cuit, tk, None, None, None, "stale", had_per)); continue
        # gate de escala vs Revenue TTM
        if revk:
            rttm, rw, rmot = ttm_last4(series(cur, cuit, revk), fy)
            if rttm and abs(rttm) > 0 and abs(ttm) > 2 * abs(rttm):
                rows.append((cuit, tk, None, None, None, "escala_corrupta", had_per)); continue
        # IAMC: EPS<=0 -> guion
        if ttm <= 0:
            rows.append((cuit, tk, ttm, None, None, "perdida_real", had_per)); continue
        # PER = MarketCap / NetIncome_TTM. La col MarketCapUSD guarda el market cap en
        # ARS (= shares * precio_ars); fallback a shares desde EPS_basico si falta.
        if mcap and mcap > 0:
            per_ttm = mcap / ttm
            eps_ttm = (pxars / per_ttm) if (pxars and per_ttm) else None
        else:
            shares = derive_shares(cur, cuit)
            eps_ttm = (ttm / shares) if shares else None
            per_ttm = (pxars / eps_ttm) if (eps_ttm and pxars) else None
        if per_ttm is None:
            estado = "sin_marketcap"
        elif not (1 <= per_ttm <= 100):      # cota de sanidad (IAMC: >100 -> guion; <1 implausible)
            estado = "per_fuera_rango"
        else:
            estado = "ok"
        rows.append((cuit, tk, ttm, eps_ttm, per_ttm, estado, had_per))
    return rows


def persist(cur, rows):
    cur.executescript("""
        DROP TABLE IF EXISTS per_ttm;
        CREATE TABLE per_ttm(
            cuit TEXT PRIMARY KEY, ticker TEXT, ttm_netincome REAL, eps_ttm REAL,
            per_ttm REAL, estado TEXT, tenia_per INTEGER, metodo TEXT, built_at TEXT);
    """)
    now = dt.datetime.now().isoformat(timespec="seconds")
    cur.executemany("INSERT INTO per_ttm VALUES(?,?,?,?,?,?,?,?,?)",
                    [(cu, tk, ttm, ept, prt, st, int(had), "IAMC_TTM_decum", now)
                     for cu, tk, ttm, ept, prt, st, had in rows])


def report(rows):
    import collections
    ok = [r for r in rows if r[5] == "ok"]
    recov = [r for r in ok if not r[6]]
    print(f"byma_only procesadas: {len(rows)}")
    print(f"PER_ttm valido (publicable): {len(ok)}")
    print(f"  de esos, recuperadas (no tenian PER): {len(recov)}")
    print(f"{'tk':>7} {'TTM_NI(Bn)':>11} {'PER_ttm':>8} {'tenia':>6}")
    for cu, tk, ttm, ept, prt, st, had in sorted(ok, key=lambda r: -(r[2] or 0)):
        flag = "" if had else "  <- RECUPERADA"
        print(f"{tk:>7} {ttm/1e9:>11.2f} {('%.1f'%prt) if prt else 'n/a':>8} {str(had):>6}{flag}")
    mot = collections.Counter(r[5] for r in rows if r[5] != "ok")
    print("\nguion (motivo):", dict(mot))


def run_tests(cur, dbmax, revk):
    """Tests golden contra verdad conocida."""
    fcal = {cu: fy for cu, fy in cur.execute("select cuit,fy_end_month from fiscal_calendar")}
    checks = []
    for tk, exp_sign in [("GRIM", +1)]:
        row = cur.execute("select cuit from mapa_entidades where ticker=?", (tk,)).fetchone()
        cu = row[0]; fy = fcal.get(cu)
        assert fy is not None, f"{tk} sin fiscal_calendar"
        ttm, w, motivo = ttm_last4(series(cur, cu, "NetIncome"), fy)
        assert motivo is None, f"{tk}: {motivo}"
        sign = 1 if ttm > 0 else -1
        ok = (sign == exp_sign)
        checks.append((tk, fy, round(ttm/1e9, 2), ok))
        print(f"  {tk}: FY={fy} TTM={ttm/1e9:+.2f}Bn -> {'PASS' if ok else 'FAIL'}")
    assert all(c[3] for c in checks), "tests golden fallaron"
    print("tests golden OK")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--test", action="store_true"); a = ap.parse_args()
    con = sqlite3.connect(DB); cur = con.cursor()
    if not cur.execute("select 1 from sqlite_master where name='fiscal_calendar'").fetchone():
        sys.exit("Falta fiscal_calendar. Corre build_fiscal_calendar.py primero.")
    dbmax = cur.execute("select max(period_end) from cnv_estados_v2 where concepto='NetIncome'").fetchone()[0]
    revk = rev_concept(cur)
    if a.test:
        run_tests(cur, dbmax, revk); return
    rows = compute(cur, dbmax, revk)
    persist(cur, rows); con.commit()
    report(rows)
    con.close()


if __name__ == "__main__":
    main()
