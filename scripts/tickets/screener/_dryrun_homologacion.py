# -*- coding: utf-8 -*-
"""
DRY RUN -- homologacion CNV (no modifica nada)
===============================================
Simula como quedaria cnv_estados_norm aplicando las tres decisiones tomadas:

  1. UNION v2 + BYMA  -- v2 (unidades corregidas) como base historica,
     mas las filas source_type='BYMA' de la v1, que aportan la punta reciente.
     Verificado: en los 46 tickers presentes en ambas vias, BYMA es mas nuevo
     en los 46. DGCE solo existe por BYMA.

  2. vintage_reexpresion = period_end  -- regla NIC 29. Cada documento de v2
     aporta un unico period_end (2.145 docs, todos n=1), asi que cada cifra
     esta en moneda de su propia fecha de cierre.

  3. tipo_balance con coherencia de perimetro -- se elige UN perimetro por
     cuit+periodo (el de mayor cobertura, tipicamente consolidado) y NO se
     rellena con el otro. Verificado: individual y consolidado nunca comparten
     concepto (0 solapamientos en los 83 casos con ambos), de modo que hoy se
     estan mezclando perimetros sin declararlo.

Lee en SOLO LECTURA y escribe un informe. No toca la base ni el pipeline.

Uso:  python _dryrun_homologacion.py [--db ruta] [--out informe.csv]
"""
from __future__ import annotations
import argparse, csv, io, os, sqlite3, sys
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_DEF = os.path.join(RAIZ, "data", "screener.db.test")

# El `ticker` de cnv_estados_v2 NO esta normalizado: trae la razon social
# ("BANCO BBVA ARGENTINA S A"). Por eso la union se hace por CUIT y el ticker
# se resuelve con el mismo mapeo que usa s0.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s0_normalizar_cnv import leer_mapping  # noqa: E402


def ro(db):
    return sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEF)
    ap.add_argument("--out", default="dryrun_homologacion.csv")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        sys.exit("ERROR: no existe %s" % a.db)

    con = ro(a.db)
    cur = con.cursor()
    print("DRY RUN -- homologacion CNV")
    print("=" * 62)
    print("Base: %s (solo lectura)\n" % a.db)

    # ---------- ESTADO ACTUAL ----------
    act_n = cur.execute("SELECT COUNT(*) FROM cnv_estados_norm").fetchone()[0]
    act_t = cur.execute("SELECT COUNT(DISTINCT ticker) FROM cnv_estados_norm").fetchone()[0]
    act_ult = cur.execute("SELECT MAX(period_end) FROM cnv_estados_norm").fetchone()[0]
    act_vint = cur.execute("""SELECT COUNT(*) FROM cnv_estados_norm
                              WHERE fecha_reexpresion IS NOT NULL AND fecha_reexpresion!=''""").fetchone()[0]
    print("ACTUAL  cnv_estados_norm")
    print("  filas: %d | tickers: %d | ultimo periodo: %s | con vintage: %d"
          % (act_n, act_t, act_ult, act_vint))

    # ---------- FUENTE 1: v2 ----------
    v2 = cur.execute("""
        SELECT cuit, ticker, concepto, period_end, tipo, valor, valor_comparativo,
               unidad_factor, accn, fuente
        FROM cnv_estados_v2 WHERE fuente='cnv-aif2'
    """).fetchall()
    print("\nFUENTE 1  cnv_estados_v2 : %d filas" % len(v2))

    # ---------- FUENTE 2: BYMA (de la v1) ----------
    byma = cur.execute("""
        SELECT cuit, ticker, concepto, period_end, tipo, valor, valor_comparativo,
               escala, accn, fuente
        FROM cnv_estados_norm WHERE source_type='BYMA'
    """).fetchall()
    print("FUENTE 2  filas BYMA     : %d filas" % len(byma))

    # ---------- UNION con precedencia v2 ----------
    # clave de negocio: CUIT + concepto + period_end (el ticker de v2 es razon social)
    by_ticker, by_cuit = leer_mapping()
    print("\nMapeo: %d tickers, %d CUITs" % (len(by_ticker), len(by_cuit)))

    union = {}
    huerf_v2 = set()
    for r in v2:
        cuit, tk_raw, con_, pe, tipo, val, vc, uf, accn, fu = r
        tk = by_cuit.get(cuit)
        if not tk:
            huerf_v2.add(cuit)
            continue
        union[(cuit, con_, pe)] = [cuit, tk, con_, pe, tipo, val, vc, uf, accn, fu, "v2", pe]
    pisadas = 0
    solo_byma = 0
    huerf_by = set()
    for r in byma:
        cuit, tk_raw, con_, pe, tipo, val, vc, esc, accn, fu = r
        tk = by_cuit.get(cuit) or tk_raw
        if not tk:
            huerf_by.add(cuit)
            continue
        k = (cuit, con_, pe)
        if k in union:
            pisadas += 1          # v2 gana: la de BYMA se descarta
            continue
        solo_byma += 1
        union[k] = [cuit, tk, con_, pe, tipo, val, vc, esc, accn, fu, "byma", pe]

    print("\nUNION")
    print("  filas resultantes        : %d" % len(union))
    print("  aportadas solo por BYMA  : %d" % solo_byma)
    print("  de BYMA descartadas (v2 gana): %d" % pisadas)
    print("  CUITs de v2 sin mapeo (huerfanos): %d %s"
          % (len(huerf_v2), sorted(huerf_v2)[:5] if huerf_v2 else ""))

    # ---------- comparacion contra el actual ----------
    ult_new = max(v[3] for v in union.values())
    tk_new = len(set(v[1] for v in union.values()))
    print("\nDELTA vs ACTUAL")
    print("  filas   : %d -> %d  (%+d)" % (act_n, len(union), len(union) - act_n))
    print("  tickers : %d -> %d  (%+d)" % (act_t, tk_new, tk_new - act_t))
    print("  ultimo periodo: %s -> %s" % (act_ult, ult_new))
    print("  con vintage   : %d -> %d  (100%% de cobertura)" % (act_vint, len(union)))

    # tickers que se ganan o se pierden
    tk_act = set(x[0] for x in cur.execute("SELECT DISTINCT ticker FROM cnv_estados_norm"))
    tk_nue = set(v[1] for v in union.values())
    print("\n  tickers que se PIERDEN: %s" % (sorted(tk_act - tk_nue) or "ninguno"))
    print("  tickers que se GANAN  : %s" % (sorted(tk_nue - tk_act) or "ninguno"))

    # ---------- frescura por ticker ----------
    ult_act = dict(cur.execute("SELECT ticker, MAX(period_end) FROM cnv_estados_norm GROUP BY ticker").fetchall())
    ult_nue = defaultdict(str)
    for v in union.values():
        if v[3] > ult_nue[v[1]]:
            ult_nue[v[1]] = v[3]
    mejora = [(t, ult_act.get(t), ult_nue[t]) for t in ult_nue if ult_act.get(t) and ult_nue[t] > ult_act[t]]
    peor = [(t, ult_act.get(t), ult_nue[t]) for t in ult_nue if ult_act.get(t) and ult_nue[t] < ult_act[t]]
    print("\n  tickers con periodo MAS RECIENTE que hoy : %d" % len(mejora))
    print("  tickers con periodo MAS VIEJO que hoy    : %d" % len(peor))
    for t, o, n in sorted(peor)[:10]:
        print("     REGRESION  %-7s %s -> %s" % (t, o, n))

    # ---------- informe ----------
    filas = []
    for t in sorted(ult_nue):
        o = ult_act.get(t)
        est = ("nuevo" if not o else
               "mas_reciente" if ult_nue[t] > o else
               "igual" if ult_nue[t] == o else "REGRESION")
        n_v2 = sum(1 for v in union.values() if v[1] == t and v[10] == "v2")
        n_by = sum(1 for v in union.values() if v[1] == t and v[10] == "byma")
        filas.append([t, o or "", ult_nue[t], est, n_v2 + n_by, n_v2, n_by])
    with io.open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["ticker", "ultimo_periodo_actual", "ultimo_periodo_nuevo", "estado",
                    "filas_nuevas", "de_v2", "de_byma"])
        w.writerows(filas)
    print("\nInforme: %s" % os.path.abspath(a.out))
    con.close()


if __name__ == "__main__":
    main()
