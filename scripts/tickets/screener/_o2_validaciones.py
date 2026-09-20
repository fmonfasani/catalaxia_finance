# -*- coding: utf-8 -*-
"""
O2 -- Validaciones pre-certificacion sobre DB canonica
=======================================================
Ports de los controles M2/M3 (scripts/materia_prima/30_validaciones.py,
gate_autoreporte, arbitro) generalizados al universo completo contra
data/screener.db. Ajustes de fidelidad al modelo de datos real:

  * cnv_reextract guarda cogs y da CON SIGNO (negativos, convencion EDGAR):
    la identidad de P&L es revenue + cogs = gross_profit.
  * cnv_reextract trae flujos trimestrales DES-ACUMULADOS (no YTD): la
    continuidad se evalua YoY (mismo trimestre, ano previo), no QoQ.
  * ebitda y ebit son lineas independientes en esta extraccion (no hay
    identidad derivable): C5 queda como flag informativo, no bloqueante.
  * La regla eps_diluido <= eps_basico aplica con ganancias; con perdidas
    el invariante se invierte (mas acciones -> perdida unitaria menor).

Controles:
  GATE-AR   autoreporte CNV vs ROE calculado      -> o2_gate_roe   [bloq]
  ARB-ROE   arbitro 3 vias calc/CNV/investing     -> o2_arbitro_roe[info]
  M3-C1     activos = pasivos + PN + minoria      -> o2_m3_checks  [bloq]
            (WARN si diff 1-5%, FALLA si > 5%)
  M3-C2     continuidad YoY: caida > 70% en el    -> o2_m3_checks  [bloq]
            mismo trimestre vs ano previo
  M3-C3     eps_diluted vs eps_basico segun       -> o2_m3_checks  [bloq]
            signo del periodo (holgura 1%)
  M3-C4     revenue + cogs = gross_profit         -> o2_m3_checks  [bloq]
            (tol 2% sobre |gross_profit|)
  M3-C5     ebitda ~ ebit - da                    -> o2_m3_checks  [info]
  M3-C6     cfo ~ net_income - da                 -> o2_m3_checks  [info]

Solo lectura de tablas certificadas; escribe unicamente tablas o2_*
(idempotente) y un JSON resumen en data/.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"

GATE_TOL = 0.20        # autoreporte vs calculado, diferencia absoluta
ARB_CNV_TOL = 0.20     # calculado vs self-report CNV, absoluto
ARB_INV_TOL = 0.25     # calculado vs investing.com, relativo
C1_WARN = 0.01         # C1 balance: umbral warn
C1_FALLA = 0.05        # C1 balance: umbral falla
PL_TOL = 0.02          # C4 P&L
EPS_TOL = 0.01         # C3 holgura redondeo
CONT_DROP = -0.70      # C2 caida YoY maxima tolerada
CFO_EBITDA_TOL = 0.40  # C5/C6 flag informativo


def pct(x):
    return None if x is None else round(100 * x, 2)


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    ts = datetime.now().isoformat(timespec="seconds")

    # Identidad: CUIT -> ticker canonico / grupo (dim_entity es el puente)
    canon, grupo = {}, {}
    for c, t, g in cur.execute(
        "SELECT cuit, ticker_canonico, grupo FROM dim_entity"
    ).fetchall():
        canon[str(c)] = t
        grupo[str(c)] = g or "sin_mapa"

    resumen = {"ts": ts, "db": str(DB)}

    # ------------------------------------------------------------------
    # GATE-AR: autoreporte CNV vs ROE calculado  [bloqueante]
    # ------------------------------------------------------------------
    cur.execute("DROP TABLE IF EXISTS o2_gate_roe")
    cur.execute("""
        CREATE TABLE o2_gate_roe (
            cuit TEXT, ticker TEXT, periodo TEXT,
            roe_calc REAL, roe_oficial REAL, diff_abs REAL,
            desvio INTEGER, ts TEXT
        )
    """)
    filas_gate = cur.execute(
        "SELECT cuit, ticker, ultimo_periodo, ROE, CNV_roe FROM ratios_cnv"
    ).fetchall()
    n_gate = n_gate_desvio = 0
    for cuit, tick, per, roe_c, roe_o in filas_gate:
        if roe_c is None or roe_o is None:
            continue
        diff = roe_c - roe_o
        desv = int(abs(diff) > GATE_TOL)
        cur.execute(
            "INSERT INTO o2_gate_roe VALUES (?,?,?,?,?,?,?,?)",
            (cuit, canon.get(str(cuit), tick), per, roe_c, roe_o,
             round(diff, 4), desv, ts),
        )
        n_gate += 1
        n_gate_desvio += desv
    resumen["gate_ar"] = {"comparados": n_gate, "desvios": n_gate_desvio}

    # ------------------------------------------------------------------
    # ARB-ROE: arbitro 3 vias (calculado / CNV / investing.com)  [info]
    # ------------------------------------------------------------------
    cur.execute("DROP TABLE IF EXISTS o2_arbitro_roe")
    cur.execute("""
        CREATE TABLE o2_arbitro_roe (
            cuit TEXT, ticker TEXT, grupo TEXT,
            roe_calc REAL, roe_cnv REAL, roe_investing REAL,
            disc_cnv INTEGER, desvio_inv INTEGER, veredicto TEXT, ts TEXT
        )
    """)
    ext_roe = {t: (r / 100.0 if r is not None else None)
               for t, r in cur.execute(
                   "SELECT ticker, roe FROM ratios_externos").fetchall()}
    n_arb = defaultdict(int)
    for cuit, tick, per, roe_c, roe_o in filas_gate:
        tk = canon.get(str(cuit), tick)
        rcnv, rinv = roe_o, ext_roe.get(tk)
        flags = []
        if rcnv is not None and roe_c is not None and abs(roe_c - rcnv) > ARB_CNV_TOL:
            flags.append("DISCREPANCIA_CNV")
        if rinv is not None and roe_c is not None:
            den = max(abs(roe_c), abs(rinv)) or 1e-9
            if abs(roe_c - rinv) / den > ARB_INV_TOL:
                flags.append("DESVIO_INVESTING")
        if not flags:
            flags = ["OK"] if (rcnv is not None or rinv is not None) else ["SIN_ARB"]
        verd = "+".join(flags)
        cur.execute(
            "INSERT INTO o2_arbitro_roe VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cuit, tk, grupo.get(str(cuit), "sin_mapa"), roe_c, rcnv, rinv,
             int("DISCREPANCIA_CNV" in verd), int("DESVIO_INVESTING" in verd),
             verd, ts),
        )
        n_arb[verd] += 1
    resumen["arbitro_roe"] = dict(n_arb)

    # ------------------------------------------------------------------
    # M3-C1..C6 sobre cnv_reextract (particionado por tipo_balance)
    # ------------------------------------------------------------------
    NEED = ("assets", "liabilities", "equity", "minority_interest",
            "revenue", "cogs", "gross_profit",
            "ebitda", "ebit", "da", "eps_basic", "eps_diluted",
            "net_income", "cfo")
    serie = defaultdict(dict)  # (cuit,tb) -> concepto -> {pe: valor}
    for cuit, conc, pe, val, tb in cur.execute(
        "SELECT cuit, concepto, period_end, valor, tipo_balance FROM cnv_reextract"
    ).fetchall():
        if conc in NEED and val is not None:
            serie[(cuit, tb)].setdefault(conc, {})[pe] = val

    cur.execute("DROP TABLE IF EXISTS o2_m3_checks")
    cur.execute("""
        CREATE TABLE o2_m3_checks (
            check_id TEXT, cuit TEXT, ticker TEXT, tipo_balance TEXT,
            periodo TEXT, valor_a REAL, valor_b REAL, diff_pct REAL,
            resultado TEXT, detalle TEXT, ts TEXT
        )
    """)

    stats = defaultdict(lambda: defaultdict(int))  # cid -> resultado -> n

    def registrar(cid, key, pe, va, vb, diff_rel, resultado, detalle):
        cuit, tb = key
        cur.execute(
            "INSERT INTO o2_m3_checks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (cid, cuit, canon.get(cuit), tb, pe, va, vb, pct(diff_rel),
             resultado, detalle, ts),
        )
        stats[cid][resultado] += 1

    for key, m in serie.items():
        peqs = set()
        for conc in m.values():
            peqs |= set(conc)

        # --- C1 identidad de balance [bloqueante, WARN 1-5%]
        for pe in sorted(peqs):
            a = m.get("assets", {}).get(pe)
            liab = m.get("liabilities", {}).get(pe)
            eq = m.get("equity", {}).get(pe)
            mi = m.get("minority_interest", {}).get(pe) or 0
            if a is None or (liab is None and eq is None) or not a:
                continue
            rhs = (liab or 0) + (eq or 0) + mi
            d = abs(a - rhs) / abs(a)
            res = "OK" if d <= C1_WARN else ("WARN" if d <= C1_FALLA else "FALLA")
            registrar("M3-C1_balance", key, pe, a, rhs, d, res,
                      "activos vs pasivos+PN+minoria")

        # --- C2 continuidad YoY mismo trimestre [bloqueante]
        rev = m.get("revenue", {})
        pes = sorted(rev)
        idx = {p: i for i, p in enumerate(pes)}
        for p2 in pes:
            d2 = date.fromisoformat(p2)
            p1 = f"{d2.year - 1}{p2[4:]}"  # mismo mes-dia, ano previo
            if p1 not in idx:
                continue
            gap = (d2 - date.fromisoformat(p1)).days
            v1, v2 = rev[p1], rev[p2]
            if not (330 <= gap <= 400) or not v1:
                continue
            g = (v2 - v1) / abs(v1)
            res = "OK" if g >= CONT_DROP else "FALLA"
            registrar("M3-C2_continuidad_yoy", key, f"{p1}->{p2}", v1, v2, g,
                      res, f"revenue YoY {round(100*g,1)}%")

        # --- C3 EPS diluido vs basico segun signo [bloqueante]
        eb, ed = m.get("eps_basic", {}), m.get("eps_diluted", {})
        for pe in sorted(set(eb) & set(ed)):
            b, dl = eb[pe], ed[pe]
            if b >= 0:
                ok = dl <= b * (1 + EPS_TOL)
                esperado = "dil<=bas"
            else:
                # perdida: mas acciones -> perdida unitaria menor o igual;
                # la holgura amplia hacia -infinito (mas negativo), no al revés
                ok = dl >= b * (1 + EPS_TOL)
                esperado = "dil>=bas (perdida)"
            registrar("M3-C3_eps_dil", key, pe, dl, b,
                      (dl - b) / abs(b) if b else None,
                      "OK" if ok else "FALLA", esperado)

        # --- C4 P&L con signo: revenue + cogs = gross_profit [bloqueante]
        # No aplica a intermediacion financiera (sin COGS semantico);
        # se marca N/A para no contaminar el gate.
        BANCOS = {"SUPV", "SUPVB", "BBAR", "BHIP", "GGAL", "GGALB",
                  "BPAT", "VALO", "BMA"}
        tk_ent = canon.get(key[0])
        rv, cg, gp = (m.get(k, {}) for k in ("revenue", "cogs", "gross_profit"))
        for pe in sorted(set(rv) & set(cg) & set(gp)):
            if tk_ent in BANCOS:
                registrar("M3-C4_pyl", key, pe, rv[pe] + cg[pe], gp[pe], None,
                          "N/A", "banco: identidad P&L no aplica")
                continue
            if not gp[pe]:
                continue
            d = abs(rv[pe] + cg[pe] - gp[pe]) / max(abs(gp[pe]), 1e-9)
            registrar("M3-C4_pyl", key, pe, rv[pe] + cg[pe], gp[pe], d,
                      "OK" if d <= PL_TOL else "FALLA",
                      "revenue+cogs vs gross_profit")

        # --- C5 ebitda ~ ebit - da  [informativo]
        eb_, ei, da = (m.get(k, {}) for k in ("ebitda", "ebit", "da"))
        for pe in sorted(set(eb_) & set(ei) & set(da)):
            den = max(abs(eb_[pe]), 1e-9)
            d = abs(eb_[pe] - (ei[pe] - da[pe])) / den
            registrar("M3-C5_ebitda_flag", key, pe, eb_[pe], ei[pe] - da[pe],
                      d, "INFO_OK" if d <= CFO_EBITDA_TOL else "INFO_DESVIA",
                      "lineas independientes en extraccion")

        # --- C6 cfo ~ net_income - da  [informativo]
        cf, ni, da6 = (m.get(k, {}) for k in ("cfo", "net_income", "da"))
        for pe in sorted(set(cf) & set(ni) & set(da6)):
            den = max(abs(ni[pe] - da6[pe]), 1e-9)
            d = abs(cf[pe] - (ni[pe] - da6[pe])) / den
            registrar("M3-C6_cfo_flag", key, pe, cf[pe], ni[pe] - da6[pe],
                      d, "INFO_OK" if d <= CFO_EBITDA_TOL else "INFO_DESVIA",
                      "requiere DeltaWC para cerrar")

    bloqueantes = ("M3-C1_balance", "M3-C2_continuidad_yoy",
                   "M3-C3_eps_dil", "M3-C4_pyl")
    resumen["m3_bloqueantes"] = {
        k: dict(stats[k]) for k in bloqueantes if k in stats}
    resumen["m3_informativos"] = {
        k: dict(stats[k]) for k in stats if k not in bloqueantes}

    con.commit()
    out_json = ROOT / "data" / "precert_o2_summary.json"
    out_json.write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    print(f"GATE-AR : {n_gate} comparados, {n_gate_desvio} desvios >{GATE_TOL:.0%}  [bloq]")
    print("ARB-ROE : " + ", ".join(f"{k}={v}" for k, v in sorted(n_arb.items())) + "  [info]")
    print("M3 bloqueantes:")
    for k in bloqueantes:
        s = stats.get(k)
        if not s:
            print(f"  {k:<22} (sin datos)")
            continue
        tot = sum(s.values())
        print(f"  {k:<22} " + ", ".join(f"{r}={s[r]}" for r in sorted(s)) +
              f"  ({round(100*s.get('FALLA',0)/tot,1)}% fallo)")
    print("M3 informativos:")
    for k in sorted(stats):
        if k in bloqueantes:
            continue
        s = stats[k]
        tot = sum(s.values())
        print(f"  {k:<22} " + ", ".join(f"{r}={s[r]}" for r in sorted(s)) +
              f"  ({round(100*s.get('INFO_DESVIA',0)/tot,1)}% desvio)")
    print(f"\nResumen -> {out_json}")
    con.close()


if __name__ == "__main__":
    main()
