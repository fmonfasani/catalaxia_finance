# -*- coding: utf-8 -*-
"""
FASE 5 - VALIDACION CRUZADA + REPORTE DE COBERTURA (no destructivo)
==================================================================
Corre chequeos de sanidad sobre las 571 empresas del screener y emite:
  1. Cobertura por ratio  x  universo (S&P / ADR / BYMA)
  2. Identidades contables donde son computables (PER ~= Precio/EPS, ROA vs ROE-E/A)
  3. Gate de rangos / outliers absurdos
  4. Spot-checks de valores conocidos (AAPL, MSFT, JPM...)
  5. Provenance (fuente_fund) por universo

Solo LEE la DB. Uso:  python validar_final.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"

RATIOS = ["ROE", "ROA", "MargenNeto", "margen_operativo", "DeudaEBITDA", "EPS",
          "FCF_CE", "Payout", "CAGR_EPS_5y", "PER", "PriceBook", "PriceSales",
          "ev_ebitda", "Precio"]
UNIVERSOS = [("sp500", "S&P 500"), ("adr", "ADR"), ("byma_only", "BYMA-only")]


def pct(n, d):
    return f"{100*n/d:.0f}%" if d else "-"


def cobertura(cur):
    print("\n" + "=" * 74)
    print("  1. COBERTURA POR RATIO  x  UNIVERSO")
    print("=" * 74)
    tots = {g: cur.execute("SELECT COUNT(*) FROM screener WHERE grupo=?", (g,)).fetchone()[0]
            for g, _ in UNIVERSOS}
    header = f"  {'ratio':<17s}" + "".join(f"{lbl:>16s}" for _, lbl in UNIVERSOS)
    print(header); print("  " + "-" * 70)
    for r in RATIOS:
        line = f"  {r:<17s}"
        for g, _ in UNIVERSOS:
            n = cur.execute(f'SELECT COUNT(*) FROM screener WHERE grupo=? AND "{r}" IS NOT NULL', (g,)).fetchone()[0]
            line += f"{f'{n}/{tots[g]} ({pct(n,tots[g])})':>16s}"
        print(line)
    print("  " + "-" * 70)
    print(f"  {'TOTAL empresas':<17s}" + "".join(f"{tots[g]:>16d}" for g, _ in UNIVERSOS))


def identidades(cur):
    print("\n" + "=" * 74)
    print("  2. IDENTIDADES CONTABLES (tolerancia relativa)")
    print("=" * 74)

    # PER ~= Precio / EPS  (donde ambos existen y EPS>0). ADR se saltea (ratio ADR escala precio).
    rows = cur.execute("""SELECT ticker, PER, Precio, EPS FROM screener
        WHERE grupo='sp500' AND PER IS NOT NULL AND EPS IS NOT NULL AND EPS>0 AND Precio IS NOT NULL""").fetchall()
    ok = bad = 0; ejemplos = []
    for tk, per, precio, eps in rows:
        implied = precio / eps
        if implied <= 0:
            continue
        rel = abs(per - implied) / implied
        if rel <= 0.12:
            ok += 1
        else:
            bad += 1
            if len(ejemplos) < 6:
                ejemplos.append(f"{tk}: PER={per:.1f} vs Precio/EPS={implied:.1f} (d{rel*100:.0f}%)")
    print(f"  PER ~= Precio/EPS (S&P):  {ok} coinciden (+/-12%), {bad} divergen de {ok+bad}")
    for e in ejemplos:
        print(f"     - {e}")
    print("     (divergencias esperables: EPS es fiscal-year, PER usa NI TTM + shares actuales)")

    # ROA debe ser <= ROE en magnitud cuando hay apalancamiento (assets>=equity>0)
    rows = cur.execute("""SELECT ticker, ROE, ROA FROM screener
        WHERE ROE IS NOT NULL AND ROA IS NOT NULL AND ROE>0 AND ROA>0""").fetchall()
    viol = [tk for tk, roe, roa in rows if roa > roe + 1e-6]
    print(f"\n  ROA <= ROE (apalancamiento, {len(rows)} con ambos>0):  "
          f"{len(rows)-len(viol)} OK, {len(viol)} violan" + (f" -> {viol[:8]}" if viol else ""))


def rangos(cur):
    print("\n" + "=" * 74)
    print("  3. GATE DE RANGOS / OUTLIERS")
    print("=" * 74)
    gates = [("ROE", -5, 5), ("ROA", -1, 1), ("MargenNeto", -10, 10),
             ("DeudaEBITDA", -5, 50), ("PER", 0, 500), ("PriceBook", -50, 50),
             ("PriceSales", 0, 50), ("ev_ebitda", -50, 200), ("CAGR_EPS_5y", -5, 5)]
    total_out = 0
    for campo, lo, hi in gates:
        outs = cur.execute(
            f'SELECT ticker, "{campo}" FROM screener WHERE "{campo}" IS NOT NULL AND ("{campo}"<? OR "{campo}">?) ORDER BY ABS("{campo}") DESC',
            (lo, hi)).fetchall()
        if outs:
            total_out += len(outs)
            muestra = ", ".join(f"{t}={v:.1f}" for t, v in outs[:4])
            print(f"  [{campo}] fuera de [{lo},{hi}]: {len(outs)} -> {muestra}")
    if total_out == 0:
        print("  Sin outliers fuera de rango razonable.")
    else:
        print(f"  Total fuera de rango: {total_out} (revisar; muchos van con flag_no_significativo)")


def spot_checks(cur):
    print("\n" + "=" * 74)
    print("  4. SPOT-CHECKS (valores conocidos)")
    print("=" * 74)
    for tk in ["AAPL", "MSFT", "JPM", "KO", "XOM"]:
        r = cur.execute('SELECT ticker, PER, PriceBook, ROE, MargenNeto FROM screener WHERE ticker=? AND grupo="sp500"', (tk,)).fetchone()
        if r:
            print(f"  {r[0]:<6s} PER={r[1]}  P/B={r[2]}  ROE={r[3]}  MargenNeto={r[4]}")
    print("  --- ADR (desde EDGAR 20-F oficial) ---")
    for tk in ["YPF", "PAM", "GGAL", "LOMA"]:
        r = cur.execute('SELECT ticker, PER, ROE, adr_ratio FROM screener WHERE ticker=? AND grupo="adr"', (tk,)).fetchone()
        if r:
            print(f"  {r[0]:<6s} PER={r[1]}  ROE={r[2]}  adr_ratio={r[3]}")


def provenance(cur):
    print("\n" + "=" * 74)
    print("  5. PROVENANCE (fuente_fund) POR UNIVERSO")
    print("=" * 74)
    for g, lbl in UNIVERSOS:
        rows = cur.execute("SELECT fuente_fund, COUNT(*) FROM screener WHERE grupo=? GROUP BY fuente_fund", (g,)).fetchall()
        print(f"  {lbl:<12s} " + ", ".join(f"{f or 'NULL'}={c}" for f, c in rows))


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    n = cur.execute("SELECT COUNT(*) FROM screener").fetchone()[0]
    print("=" * 74)
    print(f"  VALIDACION FINAL - screener con {n} empresas")
    print("=" * 74)
    cobertura(cur)
    identidades(cur)
    rangos(cur)
    spot_checks(cur)
    provenance(cur)
    con.close()
    print("\n" + "=" * 74)
    print("  VALIDACION COMPLETA")
    print("=" * 74)


if __name__ == "__main__":
    main()
