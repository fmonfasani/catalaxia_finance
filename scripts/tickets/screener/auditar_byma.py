# -*- coding: utf-8 -*-
"""
AUDITAR las 56 BYMA, papel por papel, buscando el patron
=========================================================
Antes de escribir excepciones por papel hay que saber si son excepciones o si
hay una regla que no se vio. Este script mira las mismas seis dimensiones en
las 56 empresas y las junta, para que el patron -- si existe -- salte solo.

QUE MIRA CADA DIMENSION

  1. CALENDARIO      fiscal_calendar dice un mes de cierre. Se contrasta contra
                     los meses en que la empresa presento balances marcados como
                     anuales en el propio documento (PeriodoBalance=1). Si no
                     coinciden, el calendario esta mal para ese papel.
  2. ESCALA          Los parciales de la CNV son ACUMULADOS: dentro de un
                     ejercicio, las ventas no pueden bajar. Si bajan, hay error
                     de escala o de extraccion.
  3. IDENTIDAD       Activo = Pasivo + Patrimonio. El desvio dice si el balance
                     cierra.
  4. FRESCURA        Meses desde el ultimo dato. En Argentina, un balance de mas
                     de 9 meses ya no describe a la empresa.
  5. CONTINUIDAD     Huecos en la serie trimestral. Un hueco impide armar los
                     doce meses.
  6. MAGNITUD        Orden de la capitalizacion en USD. Sirve para detectar los
                     que quedaron fuera de escala aunque todo lo demas cierre.

USO
  python auditar_byma.py              # tabla por papel + patrones
  python auditar_byma.py --detalle    # ademas, el detalle de cada problema
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mep import MEP  # noqa: E402

HOY = dt.date.today()


def rev_serie(cur, cuit):
    return cur.execute(
        """SELECT period_end, valor FROM cnv_estados_norm
           WHERE cuit=? AND concepto LIKE '%Revenue%' AND valor IS NOT NULL
           ORDER BY period_end""", (cuit,)).fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalle", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    mep = MEP(con)

    # el mes de cierre segun el propio documento: PeriodoBalance=1 -> anual.
    # cnv_estados_v2.tipo ya no se usa (job5 lo adivinaba); aqui se toma el mes
    # de los period_end que fiscal_calendar considera anuales y se contrasta.
    fcal = {cu: (fy, inc, ms) for cu, fy, inc, ms in cur.execute(
        "SELECT cuit, fy_end_month, inconsistent, months_seen FROM fiscal_calendar")}
    per_ttm = {tk: (est, per) for tk, est, per in cur.execute(
        "SELECT ticker, estado, per_ttm FROM per_ttm")}

    filas = cur.execute(
        """SELECT ticker, cuit, ultimo_periodo, MarketCapUSD, Precio
           FROM screener WHERE grupo='byma_only' ORDER BY ticker""").fetchall()

    mep_hoy, _, _ = mep.en(mep.cobertura[1])
    res = []
    for tk, cuit, up, mcap, precio in filas:
        d = {"tk": tk, "cuit": cuit, "up": up}
        fy, inc, ms = fcal.get(cuit, (None, None, ""))
        d["fy"] = fy
        d["cal_incons"] = bool(inc)
        d["meses_vistos"] = ms or ""

        # --- 2. escala: el acumulado no puede bajar dentro del ejercicio -----
        ser = rev_serie(cur, cuit)
        caidas = 0
        if fy:
            porej = collections.defaultdict(list)
            for pe, v in ser:
                y, m = int(pe[:4]), int(pe[5:7])
                porej[y if m <= fy else y + 1].append((pe, v))
            for ej, s in porej.items():
                s.sort()
                for i in range(1, len(s)):
                    if s[i][1] < s[i - 1][1] * 0.9:
                        caidas += 1
        d["caidas"] = caidas

        # --- 3. identidad contable ------------------------------------------
        r = cur.execute(
            """SELECT MAX(ABS(identidad_desvio_pct)) FROM cnv_estados_norm
               WHERE cuit=? AND identidad_desvio_pct IS NOT NULL""", (cuit,)).fetchone()
        d["ident"] = r[0] if r and r[0] is not None else None

        # --- 4. frescura -----------------------------------------------------
        d["meses"] = ((HOY.year - int(up[:4])) * 12 + HOY.month - int(up[5:7])) if up else None

        # --- 5. continuidad --------------------------------------------------
        pes = sorted({pe for pe, _ in ser})
        huecos = 0
        for i in range(1, len(pes)):
            mm = (int(pes[i][:4]) - int(pes[i - 1][:4])) * 12 + int(pes[i][5:7]) - int(pes[i - 1][5:7])
            if mm > 3:
                huecos += 1
        d["huecos"] = huecos
        d["n_per"] = len(pes)

        # --- 6. magnitud ------------------------------------------------------
        d["musd"] = (mcap / mep_hoy / 1e6) if (mcap and mep_hoy) else None
        d["estado"] = per_ttm.get(tk, ("sin_ttm", None))[0]
        res.append(d)

    # ---------------------------------------------------------------- salida
    print("AUDITORIA de las 56 BYMA")
    print("=" * 96)
    print(f"{'tk':<8}{'cierra':>7}{'cal':>5}{'caidas':>7}{'ident%':>8}"
          f"{'meses':>7}{'huecos':>7}{'per':>5}{'M USD':>10}  estado")
    print("-" * 96)
    for d in res:
        cal = "MAL" if d["cal_incons"] else "ok"
        ident = f"{d['ident']:.1f}" if d["ident"] is not None else "-"
        musd = f"{d['musd']:,.0f}" if d["musd"] else "-"
        print(f"{d['tk']:<8}{str(d['fy']):>7}{cal:>5}{d['caidas']:>7}{ident:>8}"
              f"{str(d['meses']):>7}{d['huecos']:>7}{d['n_per']:>5}{musd:>10}  {d['estado']}")

    # ---------------------------------------------------------------- patrones
    print("\n" + "=" * 96)
    print("PATRONES")
    print("=" * 96)
    n = len(res)

    def cuenta(cond, etiqueta):
        s = [d["tk"] for d in res if cond(d)]
        print(f"  {etiqueta:<52} {len(s):>3}/{n}   {' '.join(s[:12])}"
              + (" ..." if len(s) > 12 else ""))
        return s

    cuenta(lambda d: d["cal_incons"], "calendario fiscal marcado inconsistente")
    cuenta(lambda d: d["caidas"] > 0, "acumulado que BAJA (escala o extraccion)")
    cuenta(lambda d: d["ident"] is not None and d["ident"] >= 5, "identidad A=P+PN fuera del 5%")
    cuenta(lambda d: d["meses"] is not None and d["meses"] > 9, "ultimo dato de mas de 9 meses")
    cuenta(lambda d: d["huecos"] > 0, "huecos en la serie trimestral")
    cuenta(lambda d: d["estado"] != "ok", "sin PER-TTM publicable")

    # cruce: los problemas se acumulan en los mismos papeles?
    print()
    prob = {d["tk"]: sum([d["cal_incons"], d["caidas"] > 0,
                          (d["ident"] or 0) >= 5, (d["meses"] or 0) > 9,
                          d["huecos"] > 0]) for d in res}
    dist = collections.Counter(prob.values())
    print("  cuantos problemas acumula cada papel:")
    for k in sorted(dist):
        tks = [t for t, v in prob.items() if v == k]
        print(f"     {k} problema(s): {len(tks):>3} papeles   {' '.join(sorted(tks)[:10])}"
              + (" ..." if len(tks) > 10 else ""))
    limpios = [t for t, v in prob.items() if v == 0]
    print(f"\n  papeles SIN ningun problema: {len(limpios)}/{n}")
    con.close()


if __name__ == "__main__":
    main()
