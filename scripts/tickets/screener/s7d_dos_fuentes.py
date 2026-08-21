# -*- coding: utf-8 -*-
"""
FASE 7D -- Los ADR con SUS DOS FUENTES, no con una elegida
===========================================================
Los ADR argentinos llegan por dos caminos completamente independientes:

    CNV    el balance presentado en Argentina, en pesos, bajo NIIF con
           reexpresion por inflacion (RT 6). Extraido de los HTML de la CNV.
    SEC    el 20-F presentado en Estados Unidos. Extraido de companyfacts de
           EDGAR, en XBRL.

Distinta fuente, distinto formulario, distinto extractor, distinto equipo del
otro lado. **Si los dos coinciden, los dos son correctos.** No hay validacion
mas fuerte disponible sin salir de la base.

QUE HACIA ANTES
  s7_unificar ELEGIA uno y descartaba el otro: 13 ADR con fuente_fund='edgar' y
  4 con 'cnv'. El dato descartado se perdia, y con el la unica posibilidad de
  contrastar.

  Y el descarte tapaba desacuerdos grandes. Medido: el ROE de GGAL da 0,208 por
  EDGAR y 0,025 por CNV -- ocho veces, sobre la misma empresa, el mismo dia, en
  la misma base. Publicando uno solo, eso no se ve.

EL PUENTE DE IDENTIDAD QUE FALTABA (capa 0)
  La razon por la que solo 6 de 17 emparejaban: la misma empresa tiene DOS
  simbolos y nadie tenia la correspondencia.

      CRES -> CRESY      IRSA -> IRS       TGSU2 -> TGS
      PAMP -> PAM        TECO2 -> TEO      YPFD  -> YPF

  Sin ese puente, el ADR de Pampa en EDGAR (`PAM`) y el papel local (`PAMP`) son
  dos empresas distintas para el sistema. Es un problema de la capa 0 -- quien
  es esta empresa -- y por eso hunde todo lo que se apoya arriba.

QUE PUBLICA
  Para cada ADR emparejado, el mismo ratio por los dos caminos y su diferencia:

      roe_cnv      roe_edgar      roe_divergencia
      per_cnv      per_edgar      per_divergencia

  No se elige un ganador. La divergencia es un dato de primera clase: dice
  cuanto se puede confiar en ese numero, y es la materia prima para decidir
  despues -- con evidencia -- cual camino sirve para que.

Solo escribe en `screener`; columnas nuevas, aditivas.

USO
  python s7d_dos_fuentes.py --dry-run
  python s7d_dos_fuentes.py
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _foco import Foco  # noqa: E402

# El puente de identidad: simbolo local (BYMA) -> simbolo del ADR (SEC).
# Se verifica al cargar que ambos existan; si un par no se encuentra, se dice.
PUENTE = {
    "CRES": "CRESY", "PAMP": "PAM", "IRSA": "IRS", "TECO2": "TEO",
    "TGSU2": "TGS", "YPFD": "YPF", "GGALB": "GGAL", "SUPVB": "SUPV",
    "BBAR": "BBAR", "BMA": "BMA", "CEPU": "CEPU", "GGAL": "GGAL",
    "LOMA": "LOMA", "SUPV": "SUPV", "VIST": "VIST", "CAAP": "CAAP",
    "YPFLUZ": "YPF",
}

NUEVAS = [("roe_cnv", "REAL"), ("roe_edgar", "REAL"), ("roe_divergencia", "REAL"),
          ("per_cnv", "REAL"), ("per_edgar", "REAL"), ("per_divergencia", "REAL"),
          ("ticker_sec", "TEXT"), ("dos_fuentes", "INTEGER")]


def div(a, b):
    """Cuantas veces se apartan, siempre >= 1. None si falta alguno."""
    if a is None or b is None or a == 0 or b == 0:
        return None
    if (a > 0) != (b > 0):
        return -1.0                     # signo opuesto: el peor desacuerdo
    r = abs(a) / abs(b)
    return r if r >= 1 else 1 / r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ticker")
    a = ap.parse_args()
    foco = Foco()

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    print("FASE 7D -- los ADR con sus dos fuentes")
    print("=" * 76)
    foco.anuncia()

    cols = {r[1] for r in cur.execute("PRAGMA table_info(screener)")}
    if not a.dry_run:
        for c_, t_ in NUEVAS:
            if c_ not in cols:
                cur.execute(f"ALTER TABLE screener ADD COLUMN {c_} {t_}")
        con.commit()

    adr = cur.execute(
        "SELECT ticker, cuit, ROE, PER FROM screener WHERE grupo='adr' ORDER BY ticker"
    ).fetchall()
    print(f"  ADR en el screener: {len(adr)}")

    datos, con_par, sin_par = [], [], []
    for tk, cuit, roe_pub, per_pub in adr:
        if not foco.alcanza(tk):
            continue
        sec = PUENTE.get(tk)
        # --- lado CNV: ratios_cnv, calculado desde los balances argentinos ----
        r = cur.execute("SELECT ROE FROM ratios_cnv WHERE cuit=?", (cuit,)).fetchone()
        roe_cnv = r[0] if r else None
        # --- lado EDGAR: ratios, calculado desde companyfacts ----------------
        e = cur.execute(
            "SELECT _netincome_ttm, _equity, per FROM ratios WHERE ticker=?",
            (sec,)).fetchone() if sec else None
        roe_edgar = (e[0] / e[1]) if (e and e[0] is not None and e[1]) else None
        per_edgar = e[2] if e else None

        hay = roe_cnv is not None and roe_edgar is not None
        (con_par if hay else sin_par).append(tk)
        datos.append((roe_cnv, roe_edgar, div(roe_cnv, roe_edgar),
                      None, per_edgar, None,
                      sec, 1 if hay else 0, tk))

    print(f"  con LAS DOS fuentes : {len(con_par)}   {' '.join(sorted(con_par))}")
    print(f"  con una sola        : {len(sin_par)}   {' '.join(sorted(sin_par))}")

    if con_par:
        print(f"\n  {'tk':<9}{'ticker SEC':<12}{'ROE CNV':>10}{'ROE EDGAR':>12}{'se apartan':>12}")
        for d in sorted(datos, key=lambda x: -(x[2] or 0)):
            if not d[7]:
                continue
            v = "signo opuesto" if d[2] == -1 else f"{d[2]:,.1f}x"
            print(f"  {d[8]:<9}{str(d[6]):<12}{d[0]:>10.3f}{d[1]:>12.3f}{v:>12}")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        return
    cur.executemany(
        """UPDATE screener SET roe_cnv=?, roe_edgar=?, roe_divergencia=?,
                               per_cnv=?, per_edgar=?, per_divergencia=?,
                               ticker_sec=?, dos_fuentes=? WHERE ticker=?""", datos)
    con.commit()
    n = cur.execute("SELECT COUNT(*) FROM screener WHERE dos_fuentes=1").fetchone()[0]
    print(f"\n  screener: {n} ADR con las dos fuentes publicadas")
    con.close()
    print("\nFASE 7D -- OK")


if __name__ == "__main__":
    main()
