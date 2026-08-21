# -*- coding: utf-8 -*-
"""
CAPA 6 -- Contraste contra una fuente externa
==============================================
Compara nuestros hechos contra `eerr_externos` (investing.com, cargado por
scripts/carga_externos/). Es la unica capa que puede decidir CUAL LADO ESTA
BIEN: todas las anteriores detectan que algo no cierra, pero ninguna sabe si el
raro es el error o el unico sano.

POR QUE VA DESPUES DE LA CAPA 2 Y NO ANTES
  Nuestros parciales son ACUMULADOS desde el inicio del ejercicio; los de
  investing son TRIMESTRES SUELTOS. Comparar sin alinear da desvios de 2x, 3x o
  4x que parecen errores y no lo son -- son la diferencia entre nueve meses y
  tres.

  Se vio en GCLA: el Q1 (donde acumulado y suelto son lo mismo) coincidia al
  0,75x, y los demas daban 3x. Sin la capa 2 -- el calendario fiscal, que dice
  cual es el Q1 -- esa distincion no se puede hacer, y la conclusion habria sido
  que esta todo mal.

  Por eso el contraste externo pertenece aca y no antes. Es el ejemplo mas claro
  de que la SECUENCIA de las validaciones importa tanto como las validaciones.

QUE ANCLA SE PROBO Y NO SIRVIO
  La capitalizacion. La idea era acotar la facturacion como proporcion del valor
  de la empresa. Medido sobre las 53 sanas: el ratio va de 0,00x a 4,3x. Una
  holding y una operativa no se parecen en nada, asi que no acota nada. GCLA
  daba "plausible" con 0,0079 teniendo problemas reales.

COBERTURA
  29 de las 56 BYMA tienen contraste. Las otras 27 quedan sin ancla externa y se
  informan como tales -- no se dan por buenas por falta de contradiccion.

USO
  python s6_contraste.py
  python s6_contraste.py --ticker GCLA
"""
from __future__ import annotations
import argparse
import collections
import math
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _foco import Foco  # noqa: E402

# eerr_externos guarda MILLONES de la moneda nativa (ver carga_externos/loader.py)
ESCALA_EXTERNA = 1e6
TOL = 0.25          # +/- 25%: por debajo de eso, coincide


def meses(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def desacumular(serie, fy_end_month):
    """[(period_end, acumulado)] -> [(period_end, trimestre suelto)].

    Los parciales de la CNV son acumulados desde el inicio del ejercicio: el Q1
    ya es el trimestre suelto, y cada uno de los siguientes es la diferencia con
    el anterior. Solo se resta cuando los periodos son consecutivos (3 meses);
    si hay un hueco, el trimestre suelto no se puede reconstruir y queda None.
    """
    out, prev = [], None
    for pe, cum in serie:
        m = int(pe[5:7])
        q = 4 - ((fy_end_month - m) % 12) // 3
        if q == 1:
            suelto = cum
        elif prev and meses(prev[0], pe) == 3:
            suelto = cum - prev[1]
        else:
            suelto = None
        out.append((pe, suelto))
        prev = (pe, cum)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker")
    a = ap.parse_args()
    foco = Foco()

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    print("CAPA 6 -- contraste contra fuente externa")
    print("=" * 76)
    foco.anuncia()

    fcal = {cu: fy for cu, fy in cur.execute(
        "SELECT cuit, fy_end_month FROM fiscal_calendar")}
    ext_tk = {r[0] for r in cur.execute("SELECT DISTINCT ticker FROM eerr_externos")}
    byma = cur.execute(
        "SELECT ticker, cuit FROM screener WHERE grupo='byma_only' ORDER BY ticker"
    ).fetchall()
    sin_ancla = [t for t, _ in byma if t not in ext_tk]
    print(f"  BYMA con contraste externo: {len(byma) - len(sin_ancla)}/{len(byma)}")
    print(f"  sin ancla externa         : {len(sin_ancla)}"
          f"   (no se dan por buenas por falta de contradiccion)")

    resumen = collections.Counter()
    detalle = []
    for tk, cuit in byma:
        if tk not in ext_tk or not foco.alcanza(tk):
            continue
        fy = fcal.get(cuit)
        if not fy:
            resumen["sin_calendario"] += 1
            continue
        for cpt in ("Revenue", "NetIncome", "GrossProfit"):
            # PERIMETRO: investing publica CONSOLIDADO. Contrastar contra
            # nuestro individual metia un sesgo sistematico -- en el 72% de los
            # casos que no cuadraban, lo nuestro era MAS CHICO, que es
            # exactamente lo que pasa cuando el individual de una holding no
            # incluye la facturacion de sus controladas.
            #
            # Medido, sobre las mismas comparaciones:
            #     INDIVIDUAL    mediana 0,704   dentro de +/-25%: 42%
            #     CONSOLIDADO   mediana 0,862   dentro de +/-25%: 67%
            #
            # Queda un 14% de residuo, asi que el perimetro explica el grueso
            # pero no todo. Lo que reste no se atribuye a esto.
            nuestro = cur.execute(
                """SELECT period_end, COALESCE(valor_corregido, valor)
                   FROM cnv_estados_norm
                   WHERE cuit=? AND concepto LIKE ? AND valor IS NOT NULL
                     AND (tipo_balance='CONSOLIDADO' OR NOT EXISTS (
                          SELECT 1 FROM cnv_estados_norm x
                          WHERE x.cuit=cnv_estados_norm.cuit
                            AND x.period_end=cnv_estados_norm.period_end
                            AND x.tipo_balance='CONSOLIDADO'))
                   ORDER BY period_end""", (cuit, f"%{cpt}%")).fetchall()
            if len(nuestro) < 2:
                continue
            sueltos = dict(desacumular(nuestro, fy))
            for pe, ve in cur.execute(
                    """SELECT period_end, valor FROM eerr_externos
                       WHERE ticker=? AND concepto=?""", (tk, cpt)):
                mio = sueltos.get(pe)
                if mio is None or not ve:
                    continue
                suyo = ve * ESCALA_EXTERNA
                if suyo == 0:
                    continue
                r = mio / suyo
                if abs(r - 1) <= TOL:
                    resumen["coincide"] += 1
                elif r > 0 and abs(math.log10(abs(r))) >= 2.2:
                    resumen["escala"] += 1
                    detalle.append((tk, pe, cpt, mio, suyo, r, "ESCALA"))
                else:
                    resumen["difiere"] += 1
                    detalle.append((tk, pe, cpt, mio, suyo, r, "difiere"))

    tot = sum(resumen[k] for k in ("coincide", "difiere", "escala"))
    print(f"\n  comparaciones hechas: {tot}")
    if tot:
        print(f"     COINCIDEN (dentro de +/-{TOL:.0%}) : {resumen['coincide']:>5}"
              f"  ({resumen['coincide']*100.0/tot:.1f}%)")
        print(f"     difieren                       : {resumen['difiere']:>5}")
        print(f"     ESCALA (mas de 2 ordenes)      : {resumen['escala']:>5}"
              f"   <- aqui la fuente externa decide")
    if detalle:
        print(f"\n  los desvios de ESCALA, donde el externo resuelve el lado:")
        print(f"     {'tk':<8}{'periodo':<12}{'concepto':<14}{'nuestro':>18}{'externo':>18}{'ratio':>10}")
        for tk, pe, cpt, mio, suyo, r, cl in [d for d in detalle if d[6] == "ESCALA"][:12]:
            print(f"     {tk:<8}{pe:<12}{cpt:<14}{mio:>18,.0f}{suyo:>18,.0f}{r:>10,.4g}")
    con.close()
    print("\nCAPA 6 -- OK")


if __name__ == "__main__":
    main()
