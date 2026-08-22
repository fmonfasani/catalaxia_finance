# -*- coding: utf-8 -*-
"""
E1 -- Extraccion de XBRL desde el EXPEDIENTE de EDGAR (pipeline paralelo de ADR)
================================================================================
Pipeline paralelo al de construir_base.py. Mismo esquema de salida, misma tabla
de conceptos canonicos, y una tabla propia para no tocar `facts` hasta que los
datos esten certificados.

POR QUE HACE FALTA UN CAMINO APARTE
  construir_base.py lee UNA sola fuente: la API data.sec.gov/api/xbrl/
  companyfacts. Es un resumen que la SEC arma juntando los hechos de todos los
  expedientes, y para varios emisores extranjeros ese resumen no ingirio las
  presentaciones nuevas.

  Medido el 2026-08-21, mirando el ultimo dato CONTABLE (excluyendo los
  metadatos `dei`, que son de caratula y no son balance):

      S&P 500   80 de 80 al dia          (muestra aleatoria, semilla 7)
      ADR        6 de 14 al dia, 8 NO

      atrasados en 2024:  BBAR BMA CEPU LOMA PAMP SUPV TGS
      atrasado en 2025-03: GGAL

  Que CAAP, TECO2, VIST e YPF SI esten al dia descarta que sea una limitacion
  de la SEC con extranjeros o con el formulario 20-F: es una diferencia entre
  emisores, segun como arman su XBRL.

  Por mas veces que se corra el pipeline actual, esos ocho no van a avanzar: se
  le esta preguntando a un resumen que no los tiene.

EL DATO SI ESTA, EN EL EXPEDIENTE
  El 20-F de BBAR del ejercicio 2025 (0001628280-26-024441) trae su XBRL
  completo entre sus 238 archivos. Verificado bajandolo:

      bbar-20251231_htm.xml    9,8 MB    bajado en 14,3 s
      parseo                             0,2 s con la libreria estandar
      resultado                          4.762 hechos, 824 conceptos

      ProfitLoss     332.572.682.000   2025-01-01 .. 2025-12-31
      Assets      25.408.391.308.000   al 2025-12-31

  Ocho empresas por ~10 MB son unos dos minutos, una vez al año -- presentan el
  20-F en abril. No hay dependencias nuevas.

QUE NO HAY QUE PARSEAR
  Las cuatro linkbases (_cal, _def, _lab, _pre, ~4,5 MB) son de presentacion y
  calculo: como se agrupan los rubros en el informe impreso. No hacen falta,
  porque el mapeo tag -> concepto canonico ya existe en CANONICO y los tags
  salen de la misma taxonomia IFRS que usa companyfacts. Se reusa lo que ya
  funciona; lo unico nuevo es de donde salen los hechos.

LA DIMENSION ES LO QUE HAY QUE MIRAR CON CUIDADO
  De los 4.762 hechos, muchos estan desagregados por segmento, por moneda o por
  clase de instrumento. La cifra consolidada es la que NO tiene dimensiones.
  Tomar una con dimensiones da un numero real que responde a otra pregunta --
  el mismo problema del perimetro individual/consolidado que ya conocemos.

  Se guarda `n_dimensiones` en cada hecho para que la eleccion sea explicita y
  auditable, en vez de quedar escondida en un filtro.

ATERRIZA EN UNA TABLA PROPIA
  `facts_xbrl`, con el MISMO esquema de `facts` mas la huella que le falta:
  accession, decimales y n_dimensiones. No se toca `facts` hasta certificar
  contra companyfacts en las empresas donde ambas fuentes tienen el mismo
  periodo -- es el mismo criterio que se uso con screener_v2.

USO
  python e1_adr_xbrl.py --dry-run          # que bajaria y por que
  python e1_adr_xbrl.py                    # los ADR atrasados
  python e1_adr_xbrl.py --ticker BBAR
  python e1_adr_xbrl.py --certificar       # contrasta contra companyfacts
"""
from __future__ import annotations
import argparse
import collections
import gzip
import json
import os
import sqlite3
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
RAW = ROOT / "data" / "raw" / "xbrl_expedientes"
sys.path.insert(0, str(ROOT / "scripts" / "tickets" / "screener"))

UA = {"User-Agent": os.environ.get(
    "SEC_USER_AGENT", "catalaxia-research fmonfasani@gmail.com")}
PAUSA = 0.35              # la SEC limita ~10 pedidos/segundo; esto queda holgado
TABLA = "facts_xbrl"

# Formularios cuyo XBRL trae estados contables completos.
FORMS = ("20-F", "20-F/A", "40-F", "10-K", "10-K/A")

# QUE FECHA CUENTA COMO CIERRE
#   Un balance no solo informa su periodo: tambien declara HECHOS POSTERIORES,
#   con la fecha real en que ocurrieron. Dos ejemplos medidos en este mismo
#   lote, ambos dentro del ejercicio 2025:
#
#       YPF   BorrowingsInterestRate  al 2026-02-19
#       LOMA  Borrowings              al 2026-01-23   (concepto canonico Debt)
#
#   Tomar el MAX(period_end) hace creer que la serie llega a 2026. Filtrar por
#   `dei` no alcanza -- son hechos contables de verdad. Filtrar por concepto
#   canonico TAMPOCO: `Borrowings` es canonico y aun asi aparece suelto.
#
#   Lo unico que separa un cierre de un hecho posterior es la fecha: un cierre
#   cae a fin de mes de un mes de trimestre. Se usa el mismo criterio para las
#   dos tablas, porque comparar frescura con dos varas distintas es como se
#   producen los "ya esta al dia" falsos.
SQL_CIERRE = ("substr(period_end,6,2) IN ('03','06','09','12') "
              "AND substr(period_end,9,2) IN ('28','29','30','31')")

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLA} (
    cik           TEXT,
    taxonomia     TEXT,
    tag           TEXT,
    concepto      TEXT,
    -- NOT NULL en TODA columna de la clave, y cadena vacia en vez de NULL.
    --
    -- SQLite no aplica unicidad cuando una columna de la clave es NULL: acepta
    -- infinitas filas iguales sin protestar. Los hechos de balance (Assets,
    -- Equity) son de fecha puntual y no tienen period_start, asi que iban NULL
    -- y la clave no existia para ellos. Medido: la tabla paso de 36.241 a
    -- 54.795 filas al correr el proceso dos veces, y `Assets` de BBAR quedo
    -- cuatro veces. Los hechos de periodo (Revenue) nunca se duplicaron,
    -- porque esos si traen fecha de inicio.
    --
    -- El NOT NULL es lo que hace que esto falle fuerte si alguien lo revierte,
    -- en vez de volver a crecer en silencio.
    unit          TEXT NOT NULL DEFAULT '',
    period_start  TEXT NOT NULL DEFAULT '',
    period_end    TEXT NOT NULL DEFAULT '',
    val           REAL,
    fy            INTEGER,
    fp            TEXT,
    form          TEXT,
    filed         TEXT,
    -- la huella que `facts` no tiene y aca entra desde el primer dia
    accession     TEXT,
    decimales     TEXT,
    n_dimensiones INTEGER,
    -- la firma `Eje=Miembro;...` ordenada. Va en la clave porque el CONTEO de
    -- dimensiones no distingue un segmento de otro (ver `parsear`).
    dimensiones   TEXT NOT NULL DEFAULT '',
    -- `unit` va en la clave porque varios emisores publican la MISMA cifra en
    -- pesos y en dolares dentro del mismo balance (CAAP, VIST, TGS). Sin esto
    -- una moneda pisa a la otra. Y es justo el dato doble que buscabamos para
    -- BYMA, con la ventaja de que la conversion la hizo la propia empresa.
    PRIMARY KEY (cik, tag, period_start, period_end, dimensiones, unit, accession)
);
CREATE INDEX IF NOT EXISTS ix_fx_cik ON {TABLA}(cik, concepto, period_end);
"""


def canonico():
    """Reusa la tabla CANONICO de construir_base sin importarlo entero."""
    import re
    s = (Path(__file__).parent / "construir_base.py").read_text(
        encoding="utf-8", errors="ignore")
    m = re.search(r"CANONICO\s*=\s*(\{.*?\n\})", s, re.S)
    if not m:
        return {}
    tabla = eval(m.group(1))            # literal del propio repo, no entrada externa
    inv = {}
    for concepto, porTax in tabla.items():
        for tax, tags in porTax.items():
            for t in tags:
                inv[(tax, t)] = concepto
    return inv


def pedir(url, timeout=120):
    t0 = time.time()
    r = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return f.read(), f.getcode(), int((time.time() - t0) * 1000)


def ultima_presentacion(cik):
    """(accession, form, filed, reportDate) del ultimo formulario con estados."""
    raw, _, _ = pedir(f"https://data.sec.gov/submissions/CIK{cik}.json", 60)
    d = json.loads(raw)
    r = d["filings"]["recent"]
    for form, fd, rd, acc, xb in zip(
            r["form"], r["filingDate"], r["reportDate"], r["accessionNumber"],
            r.get("isXBRL", [0] * len(r["form"]))):
        if form in FORMS and xb:
            return acc, form, fd, rd
    return None, None, None, None


def instancia(cik, accession):
    """URL del XBRL de la presentacion. None si no lo encuentra."""
    n = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{n}"
    raw, _, _ = pedir(f"{base}/index.json", 60)
    for it in json.loads(raw)["directory"]["item"]:
        if it["name"].endswith("_htm.xml"):
            return f"{base}/{it['name']}", it["name"]
    return None, None


def parsear(raw, inv):
    """[(tag, taxonomia, concepto, unit, ini, fin, val, dec, ndim, dims)]

    CONTAR LAS DIMENSIONES NO ALCANZA PARA IDENTIFICAR EL HECHO
      La primera version guardaba solo `n_dimensiones`, y la clave primaria la
      usaba para distinguir filas. Eso pierde datos: la venta de cemento y la de
      hormigon tienen las DOS una dimension, asi que colisionan y la segunda
      pisa a la primera. Medido en la primera corrida: 1.448 hechos de 6.229
      (23%) desaparecian sin que nada fallara -- el modo de error que ya nos
      mordio tres veces en este proyecto.

      Por eso se guarda la firma completa `Eje=Miembro;Eje=Miembro` ordenada, y
      es ESA la que entra en la clave. `n_dimensiones` se conserva porque el
      filtro habitual (`= 0` para la cifra consolidada) es mas legible asi.
    """
    root = ET.fromstring(raw)
    ctx = {}
    for c in root.iter():
        if not c.tag.endswith("}context"):
            continue
        ini = fin = None
        miembros = []
        for e in c.iter():
            t = e.tag.split("}")[-1]
            if t == "startDate":
                ini = e.text
            elif t == "endDate":
                fin = e.text
            elif t == "instant":
                fin = e.text
            elif t == "explicitMember":
                eje = (e.get("dimension") or "?").split(":")[-1]
                mie = (e.text or "?").strip().split(":")[-1]
                miembros.append(f"{eje}={mie}")
        ctx[c.get("id")] = (ini, fin, len(miembros), ";".join(sorted(miembros)))
    unidades = {}
    for u in root.iter():
        if not u.tag.endswith("}unit"):
            continue
        m = [e.text.split(":")[-1] for e in u.iter()
             if e.tag.endswith("}measure") and e.text]
        unidades[u.get("id")] = "/".join(m) if m else None

    out = []
    for e in root.iter():
        ci = e.get("contextRef")
        if not ci or ci not in ctx or e.text is None:
            continue
        txt = e.text.strip().replace(",", "")
        if not txt or not txt.lstrip("-").replace(".", "").isdigit():
            continue          # texto libre: no es un hecho numerico
        tag_full = e.tag
        tax = ("ifrs-full" if "ifrs" in tag_full else
               "us-gaap" if "us-gaap" in tag_full else
               "dei" if "/dei/" in tag_full else "otro")
        tag = tag_full.split("}")[-1]
        ini, fin, ndim, firma = ctx[ci]
        # el signo lo maneja XBRL con `sign`; se respeta
        val = float(txt) * (-1 if (e.get("sign") == "-") else 1)
        out.append((tag, tax, inv.get((tax, tag)), unidades.get(e.get("unitRef")),
                    ini, fin, val, e.get("decimals"), ndim, firma))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ticker")
    ap.add_argument("--certificar", action="store_true")
    ap.add_argument("--todos", action="store_true",
                    help="no solo los atrasados: todos los ADR")
    a = ap.parse_args()

    con = sqlite3.connect(str(DB))
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()
    con.executescript(DDL)
    RAW.mkdir(parents=True, exist_ok=True)

    try:
        from _ingesta_log import crear as crear_log, registrar
        crear_log(con)
    except ImportError:
        registrar = None

    from _identidad_adr import PUENTE, SIN_REGISTRO_SEC

    print("E1 -- XBRL desde el expediente (pipeline paralelo de ADR)")
    print("=" * 74)
    inv = canonico()
    print(f"  mapeo de conceptos reusado de construir_base: {len(inv)} tags")

    # --------------------------------------------------- 1. A QUIEN LE TOCA
    universo, vistos = [], set()
    for tk in sorted(PUENTE):
        if tk in SIN_REGISTRO_SEC:
            continue
        if a.ticker and tk.upper() not in {x.strip().upper()
                                           for x in a.ticker.split(",")}:
            continue
        sec, cik = PUENTE[tk]
        if not cik:
            r = cur.execute("SELECT cik FROM ratios WHERE ticker=? AND "
                            "grupo NOT LIKE 'byma_yf'", (sec,)).fetchone()
            cik = r[0] if r else None
        if not cik or cik in vistos:
            continue
        vistos.add(cik)
        # El ultimo CIERRE que ya tenemos por la via de companyfacts (ver
        # SQL_CIERRE: sin ese filtro un hecho posterior pasa por cierre).
        ult = cur.execute(
            f"SELECT MAX(period_end) FROM facts WHERE cik=? "
            f"AND taxonomia<>'dei' AND concepto IS NOT NULL AND {SQL_CIERRE}",
            (cik,)).fetchone()[0]
        universo.append((tk, sec, cik, ult))

    print(f"  emisores a evaluar: {len(universo)}")

    # -------------------------------------------------------- 2. QUE BAJAR
    plan = []
    for tk, sec, cik, ult in universo:
        try:
            acc, form, filed, rd = ultima_presentacion(cik)
            time.sleep(PAUSA)
        except Exception as e:
            print(f"   {tk:<8} no se pudo consultar el indice: {str(e)[:40]}")
            continue
        if not acc:
            print(f"   {tk:<8} sin presentacion con XBRL")
            continue
        atrasado = (not ult) or (rd and rd > ult)
        if atrasado or a.todos:
            plan.append((tk, sec, cik, acc, form, filed, rd, ult))
        motivo = (f"{form} del {filed} cubre hasta {rd}; tenemos hasta {ult}"
                  if atrasado else f"al dia hasta {ult}")
        print(f"   {tk:<8}{'BAJAR ' if (atrasado or a.todos) else 'saltea'}  {motivo}")

    print(f"\n  a bajar: {len(plan)}")
    if a.dry_run:
        print("\n  (dry-run) no se bajo nada.")
        return

    # ------------------------------------------------------- 3. BAJAR Y CARGAR
    total = 0
    for tk, sec, cik, acc, form, filed, rd, ult in plan:
        try:
            url, nombre = instancia(cik, acc)
            time.sleep(PAUSA)
            if not url:
                print(f"   {tk:<8} el expediente no trae _htm.xml")
                continue
            destino = RAW / f"{cik}_{acc.replace('-','')}.xml.gz"
            if destino.exists():
                raw = gzip.decompress(destino.read_bytes())
                cod, ms = 200, 0
                print(f"   {tk:<8} desde el crudo guardado ({len(raw)/1e6:.1f} MB)")
            else:
                raw, cod, ms = pedir(url)
                # EL CRUDO SE GUARDA SIEMPRE. Reprocesar sin red es lo que
                # permite mejorar el parser sin volver a molestar a la SEC.
                destino.write_bytes(gzip.compress(raw))
                print(f"   {tk:<8} bajado {len(raw)/1e6:.1f} MB en {ms/1000:.1f}s")
                time.sleep(PAUSA)

            hechos = parsear(raw, inv)
            # `or ''`: ninguna columna de la clave puede ir NULL (ver DDL).
            filas = [(cik, tax, tag, cpt, unit or '', ini or '', fin, val,
                      int(fin[:4]) if fin else None, None, form, filed,
                      acc, dec, ndim, firma)
                     for tag, tax, cpt, unit, ini, fin, val, dec, ndim, firma
                     in hechos if fin]
            cur.executemany(
                f"INSERT OR REPLACE INTO {TABLA} VALUES "
                f"({','.join('?' * 16)})", filas)   # 16 columnas contadas del DDL
            # el INSERT OR REPLACE colapsa filas en silencio si la clave no
            # identifica el hecho; se compara y se avisa en vez de confiar.
            antes = cur.execute(
                f"SELECT count(*) FROM {TABLA} WHERE accession=?", (acc,)).fetchone()[0]
            con.commit()
            total += antes
            nuevos = sum(1 for f in filas if ult is None or (f[6] or "") > ult)
            print(f"            {antes:>6} hechos  ({nuevos} posteriores a lo que teniamos)")
            # Un colapso NO es de por si un problema: en XBRL inline la misma
            # cifra aparece varias veces (en el estado y otra vez en la nota).
            # Solo es perdida cuando dos filas con la misma clave traen valores
            # DISTINTOS. Avisar de las dos cosas por igual entrena a ignorar el
            # aviso, que es como se nos escaparon los errores anteriores.
            if antes < len(filas):
                vistos, choques = {}, 0
                for f in filas:
                    k = (f[2], f[4], f[5], f[6], f[15])
                    if k in vistos and vistos[k] != f[7]:
                        choques += 1
                    vistos[k] = f[7]
                rep = len(filas) - antes - choques
                if choques:
                    print(f"            AVISO: {choques} hechos con la misma clave y "
                          f"VALOR DISTINTO -- se perdio uno de cada par")
                if rep:
                    print(f"            ({rep} repeticiones del mismo valor: sin perdida)")
            if registrar:
                registrar(con, "sec_edgar_xbrl", cik, recurso="instancia",
                          url=url, respuesta=cod, contenido=raw,
                          duracion_ms=ms, filas_nuevas=len(filas),
                          motivo=f"{form} {acc}")
        except Exception as e:
            print(f"   {tk:<8} ERROR: {str(e)[:60]}")
            if registrar:
                registrar(con, "sec_edgar_xbrl", cik, recurso="instancia",
                          respuesta=0, motivo=str(e)[:120])

    print(f"\n  {TABLA}: {total} hechos cargados")
    n = cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT cik) FROM {TABLA}").fetchone()
    print(f"  acumulado: {n[0]} hechos de {n[1]} emisores")

    # IDEMPOTENCIA, COMPROBADA -- NO SUPUESTA
    #   Correr esto dos veces tiene que dejar la tabla igual. La primera version
    #   no lo cumplia (36.241 -> 54.795) y nada fallaba: SQLite acepta claves
    #   duplicadas cuando una columna va NULL. Es el mismo modo de error que ya
    #   nos costo tres bugs en este proyecto: codigo que no falla y devuelve mal.
    #
    #   Por eso se mide aca, en cada corrida, en vez de confiar en el DDL.
    dup = cur.execute(
        f"SELECT COUNT(*) FROM (SELECT 1 FROM {TABLA} "
        f"GROUP BY cik, tag, period_start, period_end, dimensiones, unit, "
        f"accession HAVING COUNT(*) > 1)").fetchone()[0]
    if dup:
        print(f"\n  NO IDEMPOTENTE: {dup} claves repetidas. La tabla crece en cada")
        print(f"  corrida y cualquier suma sobre ella cuenta de mas. NO usar.")
    else:
        print(f"  idempotencia: 0 claves repetidas (correr de nuevo no cambia nada)")

    print("\n  `facts` NO se toco. Correr --certificar antes de unir.")
    con.close()


if __name__ == "__main__":
    main()
