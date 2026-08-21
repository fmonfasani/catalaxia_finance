# -*- coding: utf-8 -*-
"""
APLICAR a la base real la correccion de PK de cnv_estados_v2
=============================================================
QUE PASO
  El commit e044552 arreglo la causa raiz de una perdida silenciosa de datos:
  la PK de cnv_estados_v2 era (cuit, concepto, period_end, fecha_reexpresion),
  con fecha_reexpresion vacia en el 100% de las filas, y el INSERT era
  OR IGNORE. El segundo documento de cada periodo se descartaba sin avisar.

  La correccion (agregar tipo_balance a la PK) se valido sobre la copia de
  pruebas y NUNCA se aplico a la base real. Medido el 2026-08-21:

      data/screener.db        81.695 filas   PK vieja
      data/screener.db.test  102.323 filas   PK con tipo_balance
      diferencia              20.628         <- las filas recuperadas

  Todo lo que se construyo encima (screener_v2, per_ttm, los ratios) se apoya
  en una base a la que le falta el 25% de los datos.

LAS 35 FILAS QUE SOLO ESTAN EN LA REAL
  Se revisaron una por una antes de escribir esto. Son todas de BOLT, periodo
  2018-10-31, un unico documento con la escala rota: Assets=3,17 cuando los
  otros periodos de la misma empresa dan ~98.000.000.000. Son coherentes entre
  si (1,63 + 1,53 = 3,17), o sea: bien entre ellas, mal de escala. El factor de
  unidad no se aplico al extraer ese documento. La re-extraccion las descarto,
  que es lo correcto. No hay nada que conservar.

COMO SE HACE
  Swap por renombrado, no DELETE + INSERT: la tabla anterior queda intacta como
  cnv_estados_v2_pre_pk y volver atras es un renombrado. Si algo falla a mitad,
  la transaccion no se confirma y la tabla original no se toco.

QUE NO TOCA
  PostgreSQL, la API y screener_v2. Esos se regeneran despues, ya sobre la base
  completa.

USO
  python aplicar_pk_cnv_v2.py --dry-run
  python aplicar_pk_cnv_v2.py
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DESTINO = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
ORIGEN = ROOT / "data" / os.environ.get("SCREENER_DB_ORIGEN", "screener.db.test")
TABLA = "cnv_estados_v2"
BACKUP = f"{TABLA}_pre_pk"


def pk_de(con, tabla):
    import re
    r = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (tabla,)).fetchone()
    if not r:
        return None
    m = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", r[0], re.I)
    return [x.strip() for x in m.group(1).split(",")] if m else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    for p in (DESTINO, ORIGEN):
        if not p.exists():
            sys.exit(f"FATAL: no existe {p}")

    dst = sqlite3.connect(str(DESTINO))
    dst.execute("PRAGMA busy_timeout=60000")
    src = sqlite3.connect(str(ORIGEN))

    n_dst = dst.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0]
    n_src = src.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0]
    pk_dst, pk_src = pk_de(dst, TABLA), pk_de(src, TABLA)

    print("APLICAR correccion de PK a cnv_estados_v2")
    print("=" * 62)
    print(f"  destino {DESTINO.name:<20} {n_dst:>7} filas  PK: {', '.join(pk_dst)}")
    print(f"  origen  {ORIGEN.name:<20} {n_src:>7} filas  PK: {', '.join(pk_src)}")

    # --- PRECONDICIONES: no escribir si algo no cierra ----------------------
    if "tipo_balance" not in pk_src:
        sys.exit("ABORTA: el origen no tiene tipo_balance en la PK. No es la version corregida.")
    if "tipo_balance" in pk_dst:
        print("\n  El destino YA tiene la PK corregida. Nada que hacer.")
        return
    if n_src < n_dst:
        sys.exit(f"ABORTA: el origen tiene MENOS filas ({n_src}) que el destino ({n_dst}).")

    K = "cuit, concepto, period_end, fecha_reexpresion"
    ka = {r for r in dst.execute(f"SELECT {K} FROM {TABLA}")}
    kb = {r for r in src.execute(f"SELECT {K} FROM {TABLA}")}
    solo_dst, solo_src = ka - kb, kb - ka
    print(f"\n  claves solo en el destino (se pierden) : {len(solo_dst)}")
    print(f"  claves solo en el origen  (se ganan)   : {len(solo_src)}")

    # Las 35 conocidas son de BOLT/2018-10-31 con la escala rota. Si aparecen
    # otras distintas, algo cambio desde que se reviso y hay que mirarlo.
    if solo_dst:
        emp = {r[0] for r in solo_dst}
        per = {r[2] for r in solo_dst}
        print(f"     son de {len(emp)} cuit(s) y {len(per)} periodo(s): "
              f"{sorted(per)[:3]}")
        if len(solo_dst) > 50:
            sys.exit(f"ABORTA: se perderian {len(solo_dst)} filas, mas de las 35 revisadas. "
                     f"Revisar antes de continuar.")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        return

    # --- el swap, en una transaccion ----------------------------------------
    ddl = src.execute("SELECT sql FROM sqlite_master WHERE name=?", (TABLA,)).fetchone()[0]
    cols = [c[1] for c in src.execute(f"PRAGMA table_info({TABLA})")]
    filas = src.execute(f"SELECT * FROM {TABLA}").fetchall()

    try:
        dst.execute("BEGIN")
        dst.execute(f"DROP TABLE IF EXISTS {TABLA}__new")
        dst.execute(ddl.replace(TABLA, f"{TABLA}__new", 1))
        dst.executemany(
            f"INSERT INTO {TABLA}__new ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})", filas)
        n_new = dst.execute(f"SELECT COUNT(*) FROM {TABLA}__new").fetchone()[0]
        if n_new != n_src:
            raise RuntimeError(f"entraron {n_new} filas y se esperaban {n_src}")
        dst.execute(f"DROP TABLE IF EXISTS {BACKUP}")
        dst.execute(f"ALTER TABLE {TABLA} RENAME TO {BACKUP}")
        dst.execute(f"ALTER TABLE {TABLA}__new RENAME TO {TABLA}")
        dst.commit()
    except Exception as e:
        dst.rollback()
        sys.exit(f"ERROR: {e}\n  La tabla original NO se toco.")

    # --- verificacion --------------------------------------------------------
    n_fin = dst.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0]
    n_bak = dst.execute(f"SELECT COUNT(*) FROM {BACKUP}").fetchone()[0]
    print(f"\n  {TABLA}: {n_fin} filas   (antes {n_bak}, guardadas en {BACKUP})")
    print(f"  PK ahora: {', '.join(pk_de(dst, TABLA))}")

    # Las filas ganadas tienen que traer valores creibles, no ceros.
    nul = dst.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE valor IS NULL").fetchone()[0]
    cero = dst.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE valor = 0").fetchone()[0]
    print(f"  control: {nul} filas con valor nulo, {cero} en cero "
          f"({(nul+cero)*100.0/n_fin:.1f}% del total)")
    docs = dst.execute(
        f"SELECT COUNT(DISTINCT cuit || period_end) FROM {TABLA}").fetchone()[0]
    print(f"  documentos distintos (cuit+periodo): {docs}")
    print("\n  Para volver atras:")
    print(f"     ALTER TABLE {TABLA} RENAME TO x; "
          f"ALTER TABLE {BACKUP} RENAME TO {TABLA};")
    dst.close(); src.close()
    print("\nOK -- falta regenerar lo que depende: s0, s2, per_ttm y screener_v2.")


if __name__ == "__main__":
    main()
