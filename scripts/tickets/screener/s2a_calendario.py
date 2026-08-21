# -*- coding: utf-8 -*-
"""
CAPA 2 -- El cierre de ejercicio, dicho por el documento
=========================================================
Corrige fiscal_calendar leyendo `PeriodoBalance` de los estados contables, que
es donde la CNV declara la periodicidad: 1 = anual, 2 = semestral, 3 = trimestral.
El mes de cierre de los documentos ANUALES es el fin de ejercicio.

POR QUE HACE FALTA
  fiscal_calendar se construye desde las paginas de entidad y marca 12 de las 56
  BYMA como `inconsistent`, sin decidir. Esa duda envenena todo lo de arriba: las
  reglas de unidad comparan periodos entre si, la coherencia agrupa por
  ejercicio, y el CAGR necesita saber cuales son los cierres anuales. Con el
  calendario mal, las tres miden cosas distintas.

  Sintoma que lo destapo: al calcular el CAGR de Aluar daba 100% ANUAL de
  crecimiento en dolares, porque comparaba trimestres sueltos como si fueran
  ejercicios.

RESULTADO SOBRE LAS 12 EN DUDA
  8 coinciden con lo que ya decia el calendario -- la marca `inconsistent` era
  ruido de la adivinanza vieja de job5, no un problema real.
  4 cambian:
      A3     12 -> 6    34 documentos anuales, TODOS con cierre en junio
      TGNO4   3 -> 12    8 anuales, sin competencia
      EDSH    1 -> 12    6 contra 1
      MORI   12 -> 5     3 contra 2   <- evidencia floja, se aplica marcado

  A3 CONFIRMA fix_manual.py, que habia llegado a junio por otro camino (mirando
  FechaInicio=1-jul en los anuales). Dos fuentes independientes de acuerdo: es
  la mejor validacion que hubo del metodo.

CADA CAMBIO QUEDA CON SU EVIDENCIA
  fy_end_origen  'documento' | 'paginas_cnv'
  fy_end_votos   cuantos documentos anuales lo respaldan, y contra cuantos
  Un cierre deducido nunca se confunde con uno leido, y el que tenga evidencia
  floja se puede filtrar.

USO
  python s2a_calendario.py --dry-run
  python s2a_calendario.py
  python s2a_calendario.py --ticker A3
"""
from __future__ import annotations
import argparse
import collections
import csv
import glob
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _foco import Foco  # noqa: E402

WL = ROOT / "scripts" / "tickets" / "cnv" / "datos" / "whitelist_eeff_codigos.csv"
EEFF = ROOT / "scripts" / "tickets" / "cnv" / "eeff"
RX_PER = re.compile(r'claveinformativa="PeriodoBalance"[^>]*>\s*([0-9]{1,2})', re.I)
RX_CIE = re.compile(r'claveinformativa="FechaCierre"[^>]*>[^<]*?(\d{4}-\d{2}-\d{2})', re.I)

# Con menos votos que esto, el cierre se aplica pero se marca como flojo: la
# evidencia no alcanza para descartar la alternativa.
VOTOS_FIRMES = 4


def docs_por_cuit():
    idx = {os.path.splitext(os.path.basename(p))[0].lower(): p
           for p in glob.glob(str(EEFF / "*" / "*.html"))}
    por = collections.defaultdict(list)
    with open(WL, encoding="utf-8-sig", errors="ignore") as f:
        for r in csv.DictReader(f):
            g = (r.get("guid") or "").lower()
            if g in idx:
                por[(r.get("cuit") or "").strip()].append(idx[g])
    return por


def cierre_declarado(rutas):
    """Counter{mes: votos} de los documentos que se declaran ANUALES."""
    meses = collections.Counter()
    for p in rutas:
        try:
            h = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        mp, mc = RX_PER.search(h), RX_CIE.search(h)
        if mp and mc and mp.group(1).strip() == "1":
            meses[int(mc.group(1)[5:7])] += 1
    return meses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ticker")
    a = ap.parse_args()

    foco = Foco()
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    print("CAPA 2 -- cierre de ejercicio segun el documento")
    print("=" * 74)
    foco.anuncia()

    if not WL.exists():
        sys.exit(f"FATAL: falta {WL}")
    por = docs_por_cuit()
    print(f"  documentos localizados: {sum(len(v) for v in por.values())}")

    cols = {r[1] for r in cur.execute("PRAGMA table_info(fiscal_calendar)")}
    if not a.dry_run:
        for c_, t_ in (("fy_end_origen", "TEXT"), ("fy_end_votos", "TEXT")):
            if c_ not in cols:
                cur.execute(f"ALTER TABLE fiscal_calendar ADD COLUMN {c_} {t_}")
        con.commit()

    filas = cur.execute(
        """SELECT s.ticker, s.cuit, f.fy_end_month, f.inconsistent
           FROM screener s JOIN fiscal_calendar f ON f.cuit = s.cuit
           WHERE s.grupo='byma_only' ORDER BY s.ticker""").fetchall()

    cambios, iguales, sin_ev, flojos = [], 0, [], []
    for tk, cuit, fy, inc in filas:
        if not foco.alcanza(tk):
            continue
        meses = cierre_declarado(por.get(cuit, []))
        if not meses:
            sin_ev.append(tk)
            continue
        top = meses.most_common()
        real, votos = top[0]
        contra = top[1][1] if len(top) > 1 else 0
        firme = votos >= VOTOS_FIRMES and votos > contra * 2
        if real == fy:
            iguales += 1
            continue
        cambios.append((tk, cuit, fy, real, votos, contra, firme))
        if not firme:
            flojos.append(tk)

    print(f"\n  coinciden con el calendario : {iguales}")
    print(f"  CAMBIAN                     : {len(cambios)}")
    print(f"  sin documentos anuales      : {len(sin_ev)}"
          + (f"  ({', '.join(sin_ev[:8])})" if sin_ev else ""))
    if cambios:
        print(f"\n     {'tk':<9}{'antes':>6}{'ahora':>7}{'votos':>7}{'contra':>8}  evidencia")
        for tk, cu, fy, real, v, cn, firme in cambios:
            print(f"     {tk:<9}{fy:>6}{real:>7}{v:>7}{cn:>8}  "
                  + ("firme" if firme else "FLOJA: se aplica marcado"))

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        return

    for tk, cuit, fy, real, v, cn, firme in cambios:
        cur.execute("""UPDATE fiscal_calendar
                       SET fy_end_month=?, inconsistent=?, fy_end_origen='documento',
                           fy_end_votos=?
                       WHERE cuit=?""",
                    (real, 0 if firme else 1, f"{v} contra {cn}", cuit))
    # las que coinciden tambien quedan certificadas: la duda estaba de mas
    cur.execute("""UPDATE fiscal_calendar SET fy_end_origen='documento', inconsistent=0
                   WHERE cuit IN (SELECT cuit FROM screener WHERE grupo='byma_only')
                     AND fy_end_origen IS NULL""")
    con.commit()

    n = cur.execute("""SELECT COUNT(*) FROM fiscal_calendar f
                       JOIN screener s ON s.cuit=f.cuit
                       WHERE s.grupo='byma_only' AND f.inconsistent=1""").fetchone()[0]
    print(f"\n  fiscal_calendar actualizado. Quedan {n} en duda"
          + (f": {', '.join(flojos)}" if flojos else ""))
    con.close()
    print("\n  Ojo: los ratios ya calculados NO se rehacen solos.")
    print("  Hay que volver a correr s1, s2 y recompute_ttm.")


if __name__ == "__main__":
    main()
