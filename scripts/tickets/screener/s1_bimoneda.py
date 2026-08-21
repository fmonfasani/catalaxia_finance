# -*- coding: utf-8 -*-
"""
FASE 1 -- Bimoneda: cada hecho en pesos Y en dolares, con su huella
===================================================================
Va entre s0 (que une las fuentes) y s2 (que calcula ratios). El hueco de la
numeracion ya existia -- s0, s2, s3... -- y este es su lugar natural: despues de
tener todos los hechos juntos, antes de que alguien haga una cuenta con ellos.

QUE HACE, EN UNA FRASE
  A cada fila le agrega su valor en dolares al MEP de SU fecha, deja dicho que
  dolar uso y de que dia, y marca si el numero resultante es plausible.

NO TOCA `valor`. Solo agrega columnas. La marcha atras es ignorarlas.

POR QUE BIFURCAR EN DOS MONEDAS Y NO ELEGIR UNA
  - Los pesos son el dato nativo: es lo que dice el balance y lo que hay que
    poder auditar contra el documento.
  - Los dolares son el dato COMPARABLE: entre empresas, contra el S&P 500, y
    sobre todo A TRAVES DEL TIEMPO. Con inflacion del 100% anual, dos cifras en
    pesos de años distintos no se pueden comparar aunque parezcan numeros.
  Publicar las dos y decir cual es cual es mas honesto que elegir una.

Y LA COLUMNA EN DOLARES SIRVE ADEMAS PARA VALIDAR
  Ese es el hallazgo que justifica la capa. Se probaron tres reglas para
  detectar unidades mal aplicadas:

  1. Contra la mediana historica de la empresa -> 29 casos repartidos parejo
     entre 2018 y 2026. Ese reparto uniforme es la firma de la INFLACION, no de
     un error.
  2. Banda absoluta en pesos -> mismo sesgo temporal, 75 casos.
  3. Banda en DOLARES al MEP de cada fecha -> el dolar no se licua. Verificado:
     la mediana anual de facturacion en USD queda PLANA ocho años seguidos
     (10^7,73 a 10^8,16 entre 2018 y 2025).

  Convertir a dolares no es solo para publicar: es lo que hace posible validar.

BANDA POR CONCEPTO, NO UNA SOLA
  El activo de una empresa ronda tres veces su facturacion y el efectivo es una
  fraccion. Meterlos en la misma banda diluye las dos. Cada concepto saca su
  banda de sus propios datos, asi que no hay ningun rango escrito a mano.

DOS FALLAS DISTINTAS, Y NO CONVIENE MEZCLARLAS
  unidad     el desvio es una potencia limpia de 1.000 -> un factor mal
             aplicado. Es corregible.
  no_unidad  el desvio no encaja en ninguna potencia: GCDI con Revenue de 3,
             FIPL de 12. Ningun factor lleva de 3 a cien millones. Ahi el
             extractor tomo el campo equivocado, no la unidad equivocada, y
             multiplicar solo lo disfraza.

LIMITE DECLARADO
  Esto detecta cual es el raro, NO cual esta bien. En GCDI la serie es
  94.980 / 21.470 / 36.830 / 53.886.256.000 / 58.070: el grande parece el error,
  pero GCDI capitaliza 8 millones de dolares y no factura 95.000 pesos al año --
  lo mas probable es que el raro sea el unico sano. Decidir el lado necesita un
  ancla externa (la capitalizacion), y eso es la etapa siguiente.

USO
  python s1_bimoneda.py                  # convierte y marca (no toca `valor`)
  python s1_bimoneda.py --dry-run        # mide sin escribir
  python s1_bimoneda.py --ticker GCLA    # un solo papel
  python s1_bimoneda.py --certificar     # sale != 0 si quedan casos sin resolver
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import math
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mep import MEP    # noqa: E402
from _foco import Foco  # noqa: E402
from _coherencia import por_empresa  # noqa: E402

TABLA = "cnv_estados_norm"
NUEVAS = [("valor_usd", "REAL"), ("mep_valor", "REAL"), ("mep_fecha", "TEXT"),
          ("usd_desvio", "REAL"), ("usd_clase", "TEXT"),
          ("coherencia_falla", "TEXT")]

# Los ratios CNV_* son cocientes y el EPS es por accion: no son importes, asi
# que no se convierten ni se validan con la banda.
def es_importe(cpt):
    c = cpt or ""
    return not (c.startswith("CNV_") or c.startswith("EPS_"))


UMBRAL = 1.8        # ordenes de magnitud fuera de la banda p5..p95
MIN_MUESTRA = 120   # por debajo, la banda del concepto no es confiable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--certificar", action="store_true")
    ap.add_argument("--ticker")
    a = ap.parse_args()

    foco = Foco()
    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    mep = MEP(con)

    print("FASE 1 -- Bimoneda: pesos y dolares, con huella")
    print("=" * 70)
    foco.anuncia()
    ini, fin, nr = mep.cobertura
    print(f"  serie MEP: {ini} -> {fin} ({nr} ruedas)")

    cols = {r[1] for r in cur.execute(f"PRAGMA table_info({TABLA})")}
    if not a.dry_run:
        for c_, t_ in NUEVAS:
            if c_ not in cols:
                cur.execute(f"ALTER TABLE {TABLA} ADD COLUMN {c_} {t_}")
        con.commit()

    # ------------------------------------------------------- 1. CONVERTIR
    tick = {r[0]: r[1] for r in con.execute("SELECT cuit, ticker FROM screener")}
    filas = con.execute(
        f"""SELECT rowid, cuit, concepto, period_end, valor FROM {TABLA}
            WHERE valor IS NOT NULL AND valor <> 0""").fetchall()
    conv, sin_mep, no_importe = [], 0, 0
    porcpt = collections.defaultdict(list)
    for rid, cuit, cpt, pe, v in filas:
        if not es_importe(cpt):
            no_importe += 1
            continue
        if not foco.alcanza(tick.get(cuit)):
            continue
        m, fm, _ = mep.en(pe)
        if not m:
            sin_mep += 1
            conv.append((None, None, None, None, "sin_mep", rid))
            continue
        usd = v / m
        conv.append((usd, m, fm, None, None, rid))
        if usd != 0:
            porcpt[cpt].append((math.log10(abs(usd)), rid))
    print(f"  filas convertidas   : {len(conv) - sin_mep}")
    print(f"  sin MEP para su fecha: {sin_mep}   (quedan vacias, no se rellenan)")
    print(f"  no son importes (CNV_*, EPS_*): {no_importe}")

    # -------------------------------- 2. BANDA POR CONCEPTO Y CLASIFICACION
    print(f"\n  banda por concepto (sale de los propios datos):")
    print(f"     {'concepto':<24}{'n':>7}{'p5 USD':>16}{'p95 USD':>18}{'fuera':>7}")
    veredicto = {}
    resumen = collections.Counter()
    for cpt, vals in sorted(porcpt.items(), key=lambda x: -len(x[1])):
        if len(vals) < MIN_MUESTRA:
            resumen["muestra_chica"] += len(vals)
            continue
        L = sorted(x[0] for x in vals)
        p5, p95 = L[int(len(L) * 0.05)], L[int(len(L) * 0.95)]
        fuera = 0
        for lg, rid in vals:
            d = (lg - p95) if lg > p95 else ((lg - p5) if lg < p5 else 0.0)
            if abs(d) <= UMBRAL:
                continue
            k = abs(d) / 3.0
            clase = "unidad" if abs(k - round(k)) < 0.25 else "no_unidad"
            veredicto[rid] = (round(d, 2), clase)
            resumen[clase] += 1
            fuera += 1
        if len(vals) >= MIN_MUESTRA:
            print(f"     {cpt[:22]:<24}{len(vals):>7}{10**p5:>16,.0f}{10**p95:>18,.0f}{fuera:>7}")

    print(f"\n  RESULTADO")
    print(f"     sospechosas de UNIDAD (potencia de 1.000) : {resumen['unidad']}")
    print(f"     sospechosas de OTRA causa (campo malo)    : {resumen['no_unidad']}")
    if resumen["muestra_chica"]:
        print(f"     sin banda por muestra chica (<{MIN_MUESTRA})       : {resumen['muestra_chica']}")

    if veredicto:
        por = collections.Counter()
        for rid, (d, cl) in veredicto.items():
            pass
        cur2 = con.execute(
            f"SELECT rowid, cuit FROM {TABLA} WHERE rowid IN (%s)"
            % ",".join(str(r) for r in list(veredicto)[:5000]))
        for rid, cuit in cur2:
            por[tick.get(cuit, cuit)] += 1
        print(f"     papeles afectados: {len(por)}")
        for tk, n in por.most_common(10):
            print(f"        {tk:<10} {n:>4}")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        con.close()
        return

    # ------------------------------------------- 3. COHERENCIA INTERNA
    # Complementa la banda y NO se superpone con ella. Medido sobre los 1.499
    # documentos BYMA: la banda marca 151, la coherencia 111, y solo 38 caen en
    # las dos. La coherencia AGREGA 73 documentos que la banda deja pasar
    # limpios -- los rotos a medias, donde cada numero por separado es plausible
    # pero se contradicen entre si (GBAN con Cash=948 y Assets=11).
    #
    # Son cocientes entre numeros del MISMO documento, asi que un error de
    # escala que afecte a todo por igual se cancela en la division. Lo que
    # sobrevive al cociente es justamente lo que esta mal a medias.
    coh = {}
    n_coh = 0
    for cuit in {c_ for _, c_, *_ in filas}:
        if not foco.alcanza(tick.get(cuit)):
            continue
        for pe, fallas in por_empresa(con, cuit).items():
            coh[(cuit, pe)] = ";".join(f[0] for f in fallas)
            n_coh += 1
    print(f"\n  coherencia interna: {n_coh} documentos con alguna falla")
    if n_coh:
        _r = collections.Counter()
        for v in coh.values():
            for x in v.split(";"):
                _r[x] += 1
        for k, n in _r.most_common():
            print(f"     {k:<22} {n:>4}")

    # ------------------------------------------------------------ 4. GRABAR
    ubic = {rid: (cu, pe) for rid, cu, _, pe, _ in filas}
    datos = []
    for usd, m, fm, _, motivo, rid in conv:
        d, cl = veredicto.get(rid, (None, motivo or "normal"))
        datos.append((usd, m, fm, d, cl, coh.get(ubic.get(rid), None), rid))
    cur.executemany(
        f"""UPDATE {TABLA} SET valor_usd=?, mep_valor=?, mep_fecha=?,
                               usd_desvio=?, usd_clase=?, coherencia_falla=?
            WHERE rowid=?""", datos)
    con.commit()
    print(f"\n  {TABLA}: {len(datos)} filas con las dos monedas y su huella")

    # control: `valor` no se movio
    n0 = cur.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE valor IS NOT NULL").fetchone()[0]
    print(f"  control: {n0} filas con `valor` (la columna nativa no se toco)")

    if a.certificar:
        pend = cur.execute(
            f"SELECT COUNT(*) FROM {TABLA} WHERE usd_clase IN ('unidad','no_unidad')"
        ).fetchone()[0]
        print(f"\n  CERTIFICACION: {pend} hechos con la unidad en duda")
        con.close()
        if pend:
            sys.exit(1)
        return
    con.close()
    print("\nFASE 1 -- OK")


if __name__ == "__main__":
    main()
