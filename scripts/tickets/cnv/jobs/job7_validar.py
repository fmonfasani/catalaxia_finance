# -*- coding: utf-8 -*-
"""
JOB 7 · VALIDACION / LIMPIEZA (offline, 0 requests)
===================================================
Recorre lo cargado en cnv_estados y recalcula la identidad contable por filing
(cik + period_end): Activo == Pasivo + PN. Los filings que la violan por encima de
la tolerancia son mal-parseados (plantilla vieja/no estandar, ej. Boldt 2018 con
Assets=3) -> se listan en la tabla cnv_estados_suspect para que el screener los
excluya. Con --purge, ademas los BORRA de cnv_estados.

Por defecto SOLO REPORTA (no borra nada). El --purge es SELECTIVO: elimina unicamente
el grupo "parseo roto" (|Assets| < umbral, ej. Boldt-2018 con Assets=3), que es basura
sin valor. Los suspect con valores reales (bancos, filings viejos) NO se borran: quedan
marcados en cnv_estados_suspect para que el screener los excluya via join, preservando
el crudo por si un parser bank-aware los rescata despues.

Uso:
    python job7_validar.py                       # reporta + escribe cnv_estados_suspect (no borra)
    python job7_validar.py --tol 5               # tolerancia identidad en % (default 5)
    python job7_validar.py --purge               # ELIMINA solo el grupo "parseo roto" (|Assets| < umbral)
    python job7_validar.py --purge --umbral-roto 150   # define el corte de "roto" (default 150)
    python job7_validar.py --purge-todo          # ELIMINA los 21 suspect (agresivo; incluye bancos/viejos)
"""
from __future__ import annotations
import sys, sqlite3
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / "screener.db"


def main():
    args = sys.argv[1:]
    tol = float(args[args.index("--tol") + 1]) if "--tol" in args else 5.0
    umbral = float(args[args.index("--umbral-roto") + 1]) if "--umbral-roto" in args else 150.0
    purge = "--purge" in args
    purge_todo = "--purge-todo" in args

    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""SELECT cik, period_end, concepto, valor FROM cnv_estados
                   WHERE fuente='cnv-aif2' AND concepto IN ('Assets','Liabilities','Equity')""")
    filings = {}
    for cik, pe, concepto, valor in cur.fetchall():
        filings.setdefault((cik, pe), {})[concepto] = valor

    suspect = []
    for (cik, pe), d in filings.items():
        if all(k in d for k in ("Assets", "Liabilities", "Equity")) and d["Assets"]:
            err = abs((d["Liabilities"] + d["Equity"]) - d["Assets"]) / abs(d["Assets"]) * 100
            if err >= tol:
                suspect.append((cik, pe, round(err, 2), d["Assets"], d["Liabilities"] + d["Equity"]))

    rotos = [s for s in suspect if abs(s[3]) < umbral]   # s[3] = Assets -> basura de parseo
    reales = [s for s in suspect if abs(s[3]) >= umbral]  # valores reales, identidad no cierra (bancos/viejos)

    print(f"JOB7 · Validacion identidad contable (tol {tol}%, umbral roto |Assets|<{umbral:.0f})")
    print(f"  filings con Activo/Pasivo/PN: {len(filings)}")
    print(f"  suspect (identidad > {tol}%): {len(suspect)}  =  {len(rotos)} rotos + {len(reales)} reales-desbalanceados")
    print("  -- ROTOS (candidatos a --purge) --")
    for cik, pe, err, a, le in sorted(rotos, key=lambda x: -x[2])[:20]:
        print(f"    cik={cik:<12} {pe}  err={err:>10.2f}%  Assets={a:.0f}  P+PN={le:.0f}")
    print("  -- REALES-DESBALANCEADOS (se marcan, NO se borran) --")
    for cik, pe, err, a, le in sorted(reales, key=lambda x: -x[2])[:20]:
        print(f"    cik={cik:<12} {pe}  err={err:>10.2f}%  Assets={a:.0f}  P+PN={le:.0f}")

    cur.execute("""CREATE TABLE IF NOT EXISTS cnv_estados_suspect
                   (cik TEXT, period_end TEXT, error_pct REAL, assets REAL, pasivo_pn REAL,
                    grupo TEXT, PRIMARY KEY (cik, period_end))""")
    cur.execute("DELETE FROM cnv_estados_suspect")
    cur.executemany("INSERT OR REPLACE INTO cnv_estados_suspect VALUES (?,?,?,?,?,?)",
                    [(*s, "roto" if abs(s[3]) < umbral else "real_desbalanceado") for s in suspect])
    con.commit()
    print(f"  -> tabla cnv_estados_suspect: {len(suspect)} filings marcados (col grupo)")

    a_borrar = suspect if purge_todo else (rotos if purge else [])
    if a_borrar:
        n = 0
        for cik, pe, *_ in a_borrar:
            cur.execute("DELETE FROM cnv_estados WHERE cik=? AND period_end=? AND fuente='cnv-aif2'", (cik, pe))
            n += cur.rowcount
        con.commit()
        etiqueta = "TODO (incluye bancos/viejos)" if purge_todo else "solo rotos"
        print(f"  --purge {etiqueta}: {n} filas eliminadas de cnv_estados ({len(a_borrar)} filings)")
    elif suspect:
        print("  (solo reporte; --purge borra los rotos, --purge-todo borra los 21)")
    con.close()


if __name__ == "__main__":
    main()
