# -*- coding: utf-8 -*-
"""
FASE 1 -- Normalizacion y control de UNIDAD
===========================================
Va entre s0 (que une las fuentes) y s2 (que calcula ratios). El hueco de la
numeracion existia: s0, s2, s3... Este es su lugar natural -- despues de tener
todos los hechos juntos, antes de que alguien haga una cuenta con ellos.

POR QUE UNA CAPA PROPIA Y NO UN PARCHE MAS
  Un numero sin su unidad no es un dato. Todo lo que viene despues -- ratios,
  PER, capitalizacion, comparaciones contra otras fuentes -- da resultados
  plausibles y equivocados si la unidad esta mal, y no se nota mirando. Merece
  una etapa con nombre, que corra siempre y deje dicho que encontro.

EL PROBLEMA, MEDIDO
  El documento declara su unidad en el encabezado ('$', 'Miles de $',
  'Millones de $') y job5 la lee bien. El problema es que el documento SE
  CONTRADICE: declara una unidad y adentro tiene numeros de otra.

  Prueba: GCDI declara 'Miles de $' en dos trimestres seguidos. Los numeros
  crudos son 53.886.256 en uno y 37,66 en el otro. Un millon de veces de
  diferencia con la misma declaracion. Lo mismo en HARG ('Millones de $':
  66.554.000.000 contra 238.930.000) y BPAT ('MILES DE $': 68.797.746.249.000
  contra 46.219.302.000).

  En general la declaracion SI sirve -- los crudos se ordenan como deben:
      $                mediana 3.039.196.638   (9-11 digitos)
      Miles de $       mediana   101.360.040   (8-9)
      MILES DE $       mediana    19.745.926   (7-8)
      Millones de $    mediana       338.986   (5-7)
      MILLONES DE $    mediana        60.754   (4-6)
  Los intrusos son pocos y se salen de rango: 'Millones de $' tiene 8 documentos
  con crudos de 12-13 digitos, y '$' tiene 26 con crudos de 1 a 5.

COMO SE DETECTA: EN DOLARES, NO EN PESOS
  Se probaron tres reglas y las dos primeras estaban contaminadas por inflacion:

  1. Contra la mediana historica de la empresa -> marcaba 29 casos repartidos
     parejo entre 2018 y 2026. Ese reparto uniforme es la firma de la inflacion,
     no de un error: con 100% anual, un valor de 2019 ES mil veces menor que uno
     de 2026.
  2. Banda absoluta en pesos -> mismo problema, 75 casos con sesgo temporal.
  3. Banda en DOLARES al MEP de cada fecha -> el dolar no se licua. Verificado:
     la mediana anual de la facturacion en USD queda plana ocho años seguidos
     (10^7,73 a 10^8,16 entre 2018 y 2025). La inflacion deja de interferir.

  Con la banda en dolares: 65 de 2.203 filas fuera (2,95%), en 20 papeles.

TRES SUBPROCESOS, Y LA SEPARACION IMPORTA
  detectar   Solo lee. Deja la tabla `unidad_sospechas` con cada caso, su
             desvio y el factor que lo explicaria. Corre SIEMPRE: es barato y
             es el registro de que el control se hizo.
  corregir   Escribe, y solo lo que pasa una verificacion independiente de como
             se dedujo el factor. Es una decision, no un automatismo.
  certificar Vuelve a medir despues de corregir y devuelve codigo != 0 si
             quedan casos sin explicar, para que un job encadenado se entere.

  Estan separados porque detectar es seguro y corregir no. Mezclarlos obliga a
  elegir entre no mirar o escribir a ciegas.

  LIMITE QUE HAY QUE SABER: la deteccion dice cual es el raro, NO cual esta
  bien. En GCDI la serie es 94.980 / 21.470 / 36.830 / 53.886.256.000 / 58.070;
  el grande parece el error, pero GCDI capitaliza 8 millones de dolares y una
  empresa asi no factura 95.000 pesos al año -- lo mas probable es que el raro
  sea el correcto y los otros cinco esten mal. Por eso `corregir` exige un ancla
  externa y, cuando no la tiene, marca en vez de escribir.

USO
  python s1_unidades.py                    # detectar (solo lee)
  python s1_unidades.py --corregir         # detectar + corregir lo verificable
  python s1_unidades.py --certificar       # detectar + salir != 0 si algo queda
  python s1_unidades.py --ticker GCLA      # un solo papel
"""
from __future__ import annotations
import argparse
import collections
import math
import os
import statistics
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mep import MEP    # noqa: E402
from _foco import Foco  # noqa: E402

TABLA = "unidad_sospechas"
# Conceptos de flujo que sirven para medir el tamaño de la empresa. Los ratios
# CNV_* y el EPS quedan fuera: no son importes y no llevan la escala.
CONCEPTO = "Revenue"
UMBRAL = 1.8        # ordenes de magnitud fuera de la banda p5..p95
MIN_MUESTRA = 200


def banda_usd(con, mep, foco):
    """(p5, p95, n) de la facturacion en USD. La banda sale de los datos."""
    filas, fuera_serie = [], 0
    q = f"""SELECT cuit, period_end, valor FROM cnv_estados_norm
            WHERE concepto LIKE '%{CONCEPTO}%' AND valor IS NOT NULL AND valor <> 0"""
    for cuit, pe, v in con.execute(q):
        m, _, _ = mep.en(pe)
        if not m:
            fuera_serie += 1
            continue
        usd = abs(v) / m
        if usd > 0:
            filas.append((math.log10(usd), cuit, pe, v, m))
    if len(filas) < MIN_MUESTRA:
        return None, None, filas, fuera_serie
    L = sorted(f[0] for f in filas)
    return L[int(len(L) * 0.05)], L[int(len(L) * 0.95)], filas, fuera_serie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corregir", action="store_true")
    ap.add_argument("--certificar", action="store_true")
    ap.add_argument("--ticker", help="uno o varios, separados por coma")
    a = ap.parse_args()

    foco = Foco()
    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    mep = MEP(con)

    print("FASE 1 -- Normalizacion y control de UNIDAD")
    print("=" * 66)
    foco.anuncia()
    ini, fin, nr = mep.cobertura
    print(f"  serie MEP: {ini} -> {fin} ({nr} ruedas)")

    # ---------------------------------------------------------- 1. DETECTAR
    p5, p95, filas, sin_mep = banda_usd(con, mep, foco)
    if p5 is None:
        sys.exit(f"  Muestra insuficiente ({len(filas)} filas). No se puede fijar la banda.")
    print(f"  filas de {CONCEPTO} evaluadas: {len(filas)}"
          + (f"   ({sin_mep} sin MEP para su fecha)" if sin_mep else ""))
    print(f"  banda de facturacion: {10**p5:,.0f} .. {10**p95:,.0f} USD")

    tick = {r[0]: r[1] for r in con.execute("SELECT cuit, ticker FROM screener")}
    sosp = []
    for lg, cuit, pe, v, m in filas:
        tk = tick.get(cuit, cuit)
        if not foco.alcanza(tk):
            continue
        d = (lg - p95) if lg > p95 else ((lg - p5) if lg < p5 else 0.0)
        if abs(d) <= UMBRAL:
            continue
        # el factor que lo devolveria a la banda, redondeado a potencia de 1000
        centro = (p5 + p95) / 2
        k = round((centro - lg) / 3)                 # 3 = log10(1000)
        # DOS FALLAS DISTINTAS, y conviene no mezclarlas:
        #   unidad     el desvio es una potencia limpia de 1.000 (3, 6, 9
        #              ordenes). Un factor mal aplicado. Se puede corregir.
        #   no_unidad  el desvio no encaja en ninguna potencia: valores de 3,
        #              12, 20 pesos de facturacion. Ningun factor lleva de 3 a
        #              cien millones. Ahi el extractor tomo el campo equivocado,
        #              no la unidad equivocada, y multiplicar solo lo disfraza.
        _k = abs(d) / 3.0
        clase = "unidad" if abs(_k - round(_k)) < 0.25 else "no_unidad"
        sosp.append((tk, cuit, pe, v, m, 10 ** lg, round(d, 2),
                     1000.0 ** k, clase))

    print(f"\n  fuera de banda (mas de {UMBRAL} ordenes): {len(sosp)}")
    por = collections.Counter(s[0] for s in sosp)
    print(f"  papeles afectados: {len(por)}")
    _cl = collections.Counter(s[8] for s in sosp)
    print(f"     de unidad (potencia limpia de 1.000) : {_cl.get('unidad', 0)}")
    print(f"     OTRA causa (campo equivocado)        : {_cl.get('no_unidad', 0)}")
    for tk, n in por.most_common(12):
        print(f"     {tk:<10} {n:>3}")

    cur.execute(f"""CREATE TABLE IF NOT EXISTS {TABLA} (
        ticker TEXT, cuit TEXT, period_end TEXT, concepto TEXT,
        valor REAL, mep REAL, usd REAL, desvio_ordenes REAL,
        factor_sugerido REAL, estado TEXT, detectado_at TEXT,
        PRIMARY KEY (cuit, period_end, concepto))""")
    import datetime as dt
    ahora = dt.datetime.now().isoformat(timespec="seconds")
    cur.executemany(
        f"""INSERT OR REPLACE INTO {TABLA}
            (ticker, cuit, period_end, concepto, valor, mep, usd,
             desvio_ordenes, factor_sugerido, estado, detectado_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [(tk, cu, pe, CONCEPTO, v, m, usd, d, f, cl, ahora)
         for tk, cu, pe, v, m, usd, d, f, cl in sosp])
    con.commit()
    print(f"  registradas en `{TABLA}`")

    if sosp:
        print(f"\n  los 10 mas extremos:")
        print(f"     {'tk':<9}{'periodo':<12}{'valor':>22}{'USD':>16}{'ordenes':>9}{'factor':>12}")
        for tk, cu, pe, v, m, usd, d, f, cl in sorted(sosp, key=lambda x: -abs(x[6]))[:10]:
            print(f"     {tk:<9}{pe:<12}{v:>22,.0f}{usd:>16,.0f}{d:>9.1f}{f:>12,.6g}  {cl}")

    # --------------------------------------------------------- 2. CORREGIR
    if a.corregir:
        print("\n  --corregir todavia no escribe: falta el ancla externa que decida")
        print("  QUE lado esta bien. La deteccion dice cual es el raro, no cual es")
        print("  el correcto -- en GCDI el valor extremo parece el unico sano.")
        print("  Los casos quedan en `unidad_sospechas` para resolverlos con")
        print("  datos/excepciones_papel.csv o con una fuente de contraste.")

    # ------------------------------------------------------- 3. CERTIFICAR
    if a.certificar:
        pend = cur.execute(
            f"SELECT COUNT(*) FROM {TABLA} WHERE estado IN ('unidad','no_unidad')").fetchone()[0]
        print(f"\n  CERTIFICACION: {pend} casos de unidad sin resolver")
        con.close()
        if pend:
            print("  -> se sale con codigo 1 para que un job encadenado se entere.")
            sys.exit(1)
        return
    con.close()
    print("\nFASE 1 -- OK")


if __name__ == "__main__":
    main()
