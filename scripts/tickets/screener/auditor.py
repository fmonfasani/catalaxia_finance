# -*- coding: utf-8 -*-
"""
AUDITOR GENERAL -- el estado completo de los datos, y la deriva contra el mes anterior
=======================================================================================
Se corre UNA VEZ AL MES. No busca huecos: mide todo, guarda el resultado y lo
compara contra la corrida anterior.

POR QUE MENSUAL Y NO UNA FOTO
  Una foto dice "hay 111 huecos". No dice si el mes pasado habia 90 o 140, que
  es lo unico que responde la pregunta que importa: **mejoro o empeoro?**

  Ese fue el problema de fondo durante dos meses: se arreglaba sin saber si se
  avanzaba, y cada hallazgo nuevo parecia un retroceso aunque fuera lo
  contrario. Sin deriva, el trabajo no tiene final visible.

NO BAJA NADA. TERMINA PREGUNTANDO.
  El auditor mide y clasifica; la descarga es una decision. Un diagnostico que
  ademas actua obliga a elegir entre no mirar o dejar que actue solo.

  Y la clasificacion es lo que convierte "faltan datos" en trabajo con costo
  conocido: de los 11 huecos de cobertura que habia, 10 eran de identidad --
  cinco minutos -- y solo 1 era descarga real.

LAS SEIS DIMENSIONES
  1 COBERTURA     cada empresa tiene las fuentes que le CORRESPONDEN
                  (_expectativa). Sin esa referencia el auditor reporta 500
                  falsos huecos: las del S&P 500 no presentan en la CNV.
  2 COMPLETITUD   los periodos esperados segun su calendario fiscal
                  (_completitud), separando huecos interiores de atrasos.
  3 FRESCURA      distribucion de antiguedad, no un promedio. El promedio
                  esconde justamente lo que hay que ver.
  4 CONSISTENCIA  las nueve capas de tablero.py.
  5 TRAZABILIDAD  que hechos no declaran su procedencia.
  6 DERIVA        que cambio desde la auditoria anterior.

USO
  python auditor.py                 # audita y guarda
  python auditor.py --sin-guardar   # solo mira
  python auditor.py --historia      # las corridas anteriores
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
DB = ROOT / "data" / os.environ.get("SCREENER_DB", "screener.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _expectativa import diagnostico as diag_cobertura       # noqa: E402
from _completitud import diagnostico as diag_completitud     # noqa: E402

DDL = """
CREATE TABLE IF NOT EXISTS auditoria (
    corrida_at TEXT NOT NULL,
    dimension  TEXT NOT NULL,
    metrica    TEXT NOT NULL,
    valor      REAL,
    detalle    TEXT,
    PRIMARY KEY (corrida_at, dimension, metrica)
);
"""


def flecha(hoy, antes):
    """Como se lee la deriva. Sin corrida previa, no se inventa una."""
    if antes is None:
        return "  (primera corrida)"
    d = hoy - antes
    if abs(d) < 0.5:
        return "  = igual"
    return f"  {'+' if d > 0 else ''}{d:,.0f} vs la anterior"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-guardar", action="store_true")
    ap.add_argument("--historia", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    con.executescript(DDL)

    if a.historia:
        print("CORRIDAS ANTERIORES")
        print("=" * 70)
        for c_, n in cur.execute(
                "SELECT corrida_at, COUNT(*) FROM auditoria GROUP BY 1 ORDER BY 1 DESC"):
            print(f"   {c_}   {n} metricas")
        return

    ahora = dt.datetime.now().isoformat(timespec="seconds")
    prev = cur.execute(
        "SELECT MAX(corrida_at) FROM auditoria").fetchone()[0]
    antes = {}
    if prev:
        antes = {(d, m): v for d, m, v in cur.execute(
            "SELECT dimension, metrica, valor FROM auditoria WHERE corrida_at=?",
            (prev,))}

    print("AUDITOR GENERAL")
    print("=" * 78)
    print(f"  base: {DB.name}")
    print(f"  corrida anterior: {prev or 'ninguna'}")
    m = []                                   # (dimension, metrica, valor, detalle)

    # ------------------------------------------------------- 1 COBERTURA
    print("\n1 COBERTURA -- cada empresa tiene las fuentes que le corresponden")
    por = collections.defaultdict(lambda: [0, 0])
    faltan = []
    for tk, cu, g in cur.execute("SELECT ticker, cuit, grupo FROM screener").fetchall():
        falt, hay, _ = diag_cobertura(con, cu, tk, g)
        d = por[g]
        d[0] += 1
        if falt:
            d[1] += 1
            faltan.append((tk, g, sorted(falt)))
    for g, (n, mal) in sorted(por.items()):
        print(f"   {g:<12}{n - mal:>5} de {n:<5} completas")
        m.append(("cobertura", f"completas:{g}", n - mal, f"de {n}"))
    m.append(("cobertura", "incompletas", len(faltan),
              "; ".join(f"{t}:{','.join(f_)}" for t, _, f_ in faltan[:10])))
    print(f"   incompletas: {len(faltan)}{flecha(len(faltan), antes.get(('cobertura','incompletas')))}")
    for tk, g, f in faltan[:8]:
        print(f"      {tk:<9}{g:<12}falta {', '.join(f)}")

    # ----------------------------------------------------- 2 COMPLETITUD
    print("\n2 COMPLETITUD -- los periodos que deberia tener cada serie")
    fcal = {cu: fy for cu, fy in cur.execute(
        "SELECT cuit, fy_end_month FROM fiscal_calendar")}
    cl = collections.Counter()
    esp_t = ten_t = 0
    peor = []
    for tk, cu in cur.execute(
            "SELECT ticker, cuit FROM screener WHERE grupo='byma_only'").fetchall():
        ten, esp, falt = diag_completitud(con, cu, fcal.get(cu))
        if not esp:
            cl["sin_calendario"] += 1
            continue
        esp_t += len(esp)
        ten_t += len([x for x in ten if x in esp])
        for _, k in falt:
            cl[k] += 1
        i = sum(1 for _, k in falt if k == "interior")
        if i:
            peor.append((tk, i))
    pct = ten_t * 100.0 / esp_t if esp_t else 0
    print(f"   periodos esperados {esp_t}, tenemos {ten_t}  ({pct:.0f}%)"
          + flecha(pct, antes.get(("completitud", "pct"))))
    for k in ("interior", "punta", "cola_vieja"):
        print(f"      {k:<14}{cl[k]:>5}"
              + flecha(cl[k], antes.get(("completitud", k))))
        m.append(("completitud", k, cl[k], None))
    m.append(("completitud", "pct", round(pct, 1), f"{ten_t}/{esp_t}"))
    if peor:
        print("   peores (huecos INTERIORES, los que rompen la serie):")
        for tk, i in sorted(peor, key=lambda x: -x[1])[:6]:
            print(f"      {tk:<9}{i:>3}")

    # -------------------------------------------------------- 3 FRESCURA
    print("\n3 FRESCURA -- antiguedad del dato mas nuevo (distribucion, no promedio)")
    hoy = dt.date.today()
    fr = collections.Counter()
    # OJO: no reutilizar `cur` dentro de un bucle que itera sobre `cur` -- la
    # segunda consulta consume el cursor y el bucle exterior termina en la
    # primera vuelta. Daba 1 empresa donde hay 72. Se materializa la lista y se
    # usa un cursor aparte para las consultas de adentro.
    cur2 = con.cursor()
    for tk, cu, g in cur.execute("SELECT ticker, cuit, grupo FROM screener").fetchall():
        r = cur2.execute(
            "SELECT MAX(period_end) FROM cnv_estados_norm WHERE cuit=?", (cu,)).fetchone()[0]
        if not r:
            continue
        d = (hoy - dt.date.fromisoformat(r)).days // 30
        k = ("<=4 meses" if d <= 4 else "5-9" if d <= 9 else "10-18" if d <= 18
             else ">18 meses")
        fr[k] += 1
    for k in ("<=4 meses", "5-9", "10-18", ">18 meses"):
        if fr[k]:
            print(f"      {k:<12}{fr[k]:>5}" + flecha(fr[k], antes.get(("frescura", k))))
            m.append(("frescura", k, fr[k], None))

    # ----------------------------------------------------- 4 CONSISTENCIA
    print("\n4 CONSISTENCIA -- las capas del pipeline")
    def q1(sql, *p):
        try:
            r = cur.execute(sql, p).fetchone()
            return r[0] if r else 0
        except sqlite3.Error:
            return None
    capas = [
        ("unidad_en_duda", "SELECT COUNT(*) FROM cnv_estados_norm "
                           "WHERE usd_clase IN ('unidad','no_unidad') "
                           "AND valor_corregido IS NULL"),
        ("docs_incoherentes", "SELECT COUNT(DISTINCT cuit||period_end) FROM "
                              "cnv_estados_norm WHERE coherencia_falla IS NOT NULL"),
        ("sin_perimetro", "SELECT COUNT(*) FROM cnv_estados_norm "
                          "WHERE tipo_balance IS NULL OR tipo_balance=''"),
        ("calendario_en_duda", "SELECT COUNT(*) FROM fiscal_calendar f "
                               "JOIN screener s ON s.cuit=f.cuit "
                               "WHERE s.grupo='byma_only' AND f.inconsistent=1"),
    ]
    for nombre, sql in capas:
        v = q1(sql)
        if v is None:
            print(f"      {nombre:<22} no evaluable")
            continue
        print(f"      {nombre:<22}{v:>7}" + flecha(v, antes.get(("consistencia", nombre))))
        m.append(("consistencia", nombre, v, None))

    # ---------------------------------------------------- 5 TRAZABILIDAD
    print("\n5 TRAZABILIDAD -- hechos que no declaran de donde salen")
    tot = q1("SELECT COUNT(*) FROM cnv_estados_norm WHERE valor IS NOT NULL") or 0
    sin_mep = q1("SELECT COUNT(*) FROM cnv_estados_norm WHERE valor_usd IS NULL "
                 "AND valor IS NOT NULL AND SUBSTR(concepto,1,4) NOT IN ('CNV_','EPS_')") or 0
    print(f"      sin conversion a USD  {sin_mep:>7} de {tot}"
          + flecha(sin_mep, antes.get(("trazabilidad", "sin_usd"))))
    m.append(("trazabilidad", "sin_usd", sin_mep, f"de {tot}"))
    try:
        ing = q1("SELECT COUNT(*) FROM ingesta_log") or 0
        print(f"      descargas registradas {ing:>7}")
        m.append(("trazabilidad", "ingesta_log", ing, None))
    except sqlite3.Error:
        print("      ingesta_log: no existe todavia")

    # --------------------------------------------------------- 6 DERIVA
    print("\n6 DERIVA")
    if not prev:
        print("   primera corrida: no hay con que comparar.")
        print("   La proxima ya va a poder decir si mejoro o empeoro.")
    else:
        cambios = [(d, k, v, antes[(d, k)]) for d, k, v, _ in m
                   if (d, k) in antes and antes[(d, k)] is not None
                   and abs(v - antes[(d, k)]) >= 1]
        if not cambios:
            print("   nada cambio desde la corrida anterior.")
        for d, k, v, ant in sorted(cambios, key=lambda x: -abs(x[2] - x[3]))[:12]:
            print(f"   {d:<14}{k:<24}{ant:>8,.0f} -> {v:>8,.0f}")

    if not a.sin_guardar:
        cur.executemany(
            "INSERT OR REPLACE INTO auditoria VALUES (?,?,?,?,?)",
            [(ahora, d, k, v, det) for d, k, v, det in m])
        con.commit()
        print(f"\n  guardado: {len(m)} metricas en `auditoria` ({ahora})")

    # ------------------------------------------------------ LA PREGUNTA
    print("\n" + "=" * 78)
    print("  QUE HACER -- el auditor no baja nada; esto es una propuesta")
    if faltan:
        print(f"   {len(faltan)} empresa(s) sin una fuente que les corresponde.")
    if cl["interior"]:
        print(f"   {cl['interior']} huecos INTERIORES: la empresa presento antes y")
        print(f"      despues, asi que el dato del medio deberia existir.")
    if cl["punta"]:
        print(f"   {cl['punta']} de punta: atraso de actualizacion, lo resuelve el")
        print(f"      pipeline diario.")
    print("\n   Para saber si un hueco es 404 (no existe), 429 (nos limitaron) o")
    print("   un parser que fallo, hace falta ingesta_log poblado.")
    con.close()


if __name__ == "__main__":
    main()
