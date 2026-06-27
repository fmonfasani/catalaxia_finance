# -*- coding: utf-8 -*-
"""
PASO 5 — PUBLICACION. Carga los registros normalizados (validados) a la tabla
`cnv_estados` de data/screener.db. Idempotente (INSERT OR REPLACE por PK).
Cada dato queda con su fecha de re-expresion, fuente y metodo.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "data" / "screener.db"


def crear_tabla(con):
    con.execute("""CREATE TABLE IF NOT EXISTS cnv_estados (
        ticker TEXT, cik TEXT, concepto TEXT, period_end TEXT, tipo TEXT,
        valor REAL, valor_comparativo REAL, fecha_reexpresion TEXT,
        form TEXT, escala INTEGER, accn TEXT, fuente TEXT DEFAULT 'cnv-6k',
        PRIMARY KEY (cik, concepto, period_end, fecha_reexpresion))""")
    con.commit()


def publicar(normalizados, db=DB):
    con = sqlite3.connect(db)
    crear_tabla(con)
    n = 0
    for r in normalizados:
        tk = r["ticker"]
        cik = (con.execute("SELECT cik FROM empresas WHERE ticker_ppal=?", (tk,)).fetchone() or [f"BYMA-{tk}"])[0]
        for concepto, valor in r["datos"].items():
            con.execute("""INSERT OR REPLACE INTO cnv_estados
                (ticker,cik,concepto,period_end,tipo,valor,valor_comparativo,fecha_reexpresion,form,escala,accn,fuente)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tk, str(cik), concepto, r["period_end"], r["tipo"], valor, None,
                 r["fecha_reexpresion"], "EEFF-IR", 1, None, r["fuente"]))
            n += 1
    con.commit()
    emp = con.execute("SELECT COUNT(DISTINCT ticker) FROM cnv_estados WHERE fuente='cnv-ir'").fetchone()[0]
    con.close()
    print(f"  publicados {n} datapoints | empresas cnv-ir en BD: {emp}")
    return n


if __name__ == "__main__":
    from config import Config
    from paso2_extraccion import extraer
    from paso3_validacion import validar
    from paso4_normalizacion import normalizar
    publicar(normalizar(validar(extraer(Config()))))
