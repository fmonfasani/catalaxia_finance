# -*- coding: utf-8 -*-
"""
CORREGIR la escala de las filas BYMA en cnv_estados_norm
=========================================================
cnv_estados_norm tiene dos fuentes. La extraccion de la CNV ('CUIT') lee del
documento si los numeros van en unidades, miles o millones. La fuente BYMA
asume SIEMPRE escala 1, asi que las empresas que presentan en miles quedan
divididas por mil y las que presentan en millones, por un millon.

Y son siempre los periodos MAS RECIENTES: la fuente BYMA es la que trae lo
ultimo. El dato mas nuevo de cada empresa -- el que usa el screener para los
ratios -- es el que mas riesgo tiene.

EL FACTOR SE DEDUCE POR VECINO TEMPORAL, NO POR MODA
  Se toma el documento de la MISMA empresa mas proximo en fecha que declare
  factor. Usar "el factor mas frecuente de la empresa" fue el primer intento y
  estaba mal: las empresas CAMBIAN de unidad con la inflacion (CECO2 uso 1 hasta
  2024-03 y 1.000 desde 2024-06), asi que la moda habria multiplicado por mil
  periodos viejos que estaban bien.

Y SE VERIFICA CON DOS REGLAS INDEPENDIENTES DE LA DEDUCCION
  1. El acumulado no puede bajar. Los parciales de la CNV son ACUMULADOS desde
     el inicio del ejercicio, asi que dentro de un ejercicio las ventas no
     pueden decrecer.
  2. El mismo periodo del año anterior. El valor corregido tiene que caer en el
     mismo orden de magnitud; el sin corregir, no.

  Solo se escribe lo que pasa la verificacion. Medido sobre 88 documentos BYMA:
      43  ya correctos (factor 1)
      26  deducidos y CONFIRMADOS      <- se corrigen
       6  no confirmados               <- se marcan, no se tocan
      13  sin vecino del que deducir   <- se marcan
       1  ambiguo (CVH 2025-06-30 declarado con factor 1 y con 1.000.000)

QUE NO SE ESCALA
  - Los ratios `CNV_*` (apalancamiento, roe, liquidez...): son cocientes, con
    valores entre 0 y ~300. Multiplicarlos por un millon los destruye.
  - EPS_basico y EPS_diluido: son por accion, no llevan la escala del
    documento. Verificado en la fuente CUIT, que si escala: las medianas por
    factor son 2,91 / 9,81 / 44,25 -- suben 3x y 4x, no 1000x, o sea que la
    diferencia es el tamaño de la empresa y no la escala.

TRAZABILIDAD
  Cada fila corregida queda con `escala_origen='vecino_temporal'` y el factor en
  `escala`. Un factor deducido nunca se confunde con uno leido del documento.

USO
  python corregir_escala_byma.py --dry-run
  python corregir_escala_byma.py
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
from _escala_byma import factores_declarados, vecino, serie_acumulada, crece  # noqa: E402

TABLA = "cnv_estados_norm"
BACKUP = f"{TABLA}_pre_escala"

# No son importes: no se escalan.
def es_importe(concepto):
    c = (concepto or "")
    if c.startswith("CNV_"):
        return False              # ratios
    if c.startswith("EPS_"):
        return False              # por accion
    return True


def rev(con, cuit, pe):
    r = con.execute(
        """SELECT valor FROM cnv_estados_norm WHERE cuit=? AND period_end=?
           AND concepto LIKE '%Revenue%' AND valor IS NOT NULL
           ORDER BY ABS(valor) DESC LIMIT 1""", (cuit, pe)).fetchone()
    return r[0] if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    print("CORREGIR escala de las filas BYMA")
    print("=" * 62)
    decl, amb = factores_declarados(con)
    fy = {cu: m for cu, m in con.execute(
        "SELECT cuit, fy_end_month FROM fiscal_calendar")}
    tick = {r[0]: r[1] for r in con.execute("SELECT cuit, ticker FROM screener")}

    docs = con.execute(
        f"SELECT DISTINCT cuit, period_end FROM {TABLA} WHERE source_type='BYMA'"
    ).fetchall()
    print(f"  documentos BYMA: {len(docs)}   cierres con factor declarado: {len(decl)}")

    corregir, marcar = [], []
    for cu, pe in docs:
        if (cu, pe) in amb:
            marcar.append((cu, pe, "ambiguo")); continue
        f, pv, dist = vecino(decl, cu, pe)
        if not f:
            marcar.append((cu, pe, "sin_vecino")); continue
        if f == 1:
            continue                              # ya esta bien
        # --- verificacion 1: el acumulado del ejercicio -------------------
        m = fy.get(cu)
        v1 = crece(serie_acumulada(con, cu, pe, m)) if m else None
        # --- verificacion 2: el mismo periodo del año anterior ------------
        v = rev(con, cu, pe)
        va = rev(con, cu, f"{int(pe[:4]) - 1}{pe[4:]}")
        v2 = None
        if v and va:
            r_sin, r_con = v / va, (v * f) / va
            v2 = (0.2 < r_con < 5) and not (0.2 < r_sin < 5)
        if v2 is True or (v2 is None and v1 is False):
            corregir.append((cu, pe, f, pv, dist))
        else:
            marcar.append((cu, pe, "no_confirmado"))

    print(f"\n  ya correctos (factor 1)        : {len(docs) - len(corregir) - len(marcar)}")
    print(f"  a CORREGIR (verificados)       : {len(corregir)}")
    from collections import Counter
    for k, n in Counter(m[2] for m in marcar).most_common():
        print(f"  se marcan, no se tocan [{k:<14}]: {n}")

    if corregir:
        print("\n  documentos a corregir:")
        for cu, pe, f, pv, d in sorted(corregir, key=lambda x: str(tick.get(x[0])))[:30]:
            print(f"     {str(tick.get(cu, cu))[:8]:<9}{pe}   x{f:<10,} (vecino {pv}, {d}d)")

    if a.dry_run:
        n = sum(con.execute(
            f"SELECT COUNT(*) FROM {TABLA} WHERE cuit=? AND period_end=? "
            f"AND source_type='BYMA'", (cu, pe)).fetchone()[0]
            for cu, pe, *_ in corregir)
        print(f"\n  (dry-run) se habrian tocado {n} filas. No se escribio nada.")
        return

    # --- copia de seguridad y columnas de trazabilidad ----------------------
    cols = {r[1] for r in cur.execute(f"PRAGMA table_info({TABLA})")}
    if BACKUP not in {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}:
        cur.execute(f"CREATE TABLE {BACKUP} AS SELECT * FROM {TABLA}")
        con.commit()
        print(f"\n  copia de seguridad: {BACKUP} "
              f"({cur.execute(f'SELECT COUNT(*) FROM {BACKUP}').fetchone()[0]} filas)")
    for c, t in (("escala_origen", "TEXT"), ("escala_revisar", "TEXT")):
        if c not in cols:
            cur.execute(f"ALTER TABLE {TABLA} ADD COLUMN {c} {t}")
    con.commit()

    tocadas = 0
    try:
        cur.execute("BEGIN")
        for cu, pe, f, pv, d in corregir:
            cur.execute(f"""UPDATE {TABLA}
                            SET valor = valor * ?, escala = ?,
                                escala_origen = 'vecino_temporal'
                            WHERE cuit=? AND period_end=? AND source_type='BYMA'
                              AND valor IS NOT NULL
                              AND concepto NOT LIKE 'CNV\\_%' ESCAPE '\\'
                              AND concepto NOT LIKE 'EPS\\_%' ESCAPE '\\'""",
                        (f, f, cu, pe))
            tocadas += cur.rowcount
        for cu, pe, motivo in marcar:
            cur.execute(f"""UPDATE {TABLA} SET escala_revisar=?
                            WHERE cuit=? AND period_end=? AND source_type='BYMA'""",
                        (motivo, cu, pe))
        con.commit()
    except Exception as e:
        con.rollback()
        sys.exit(f"ERROR: {e}\n  Nada se escribio. La copia esta en {BACKUP}.")

    print(f"\n  filas corregidas : {tocadas}")
    print(f"  filas marcadas   : {sum(1 for _ in marcar)} documentos")

    # --- control: los ratios y el EPS NO se movieron ------------------------
    for cpt in ("CNV_roe", "EPS_basico"):
        r = cur.execute(f"""SELECT MAX(ABS(n.valor)) FROM {TABLA} n
                            WHERE n.concepto=? AND n.source_type='BYMA'""", (cpt,)).fetchone()
        print(f"  control {cpt:<12}: maximo {r[0]:,.2f}" if r[0] else f"  control {cpt}: sin datos")
    con.close()
    print("\nOK -- falta regenerar: s2, recompute_ttm y screener_v2.")


if __name__ == "__main__":
    main()
