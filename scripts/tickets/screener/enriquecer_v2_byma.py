# -*- coding: utf-8 -*-
"""
ENRIQUECER screener_v2 -- BYMA en pesos Y en dolares, con periodo declarado
===========================================================================
Solo toca `screener_v2` (la tabla en paralelo). `screener`, que es la que sirve
la API, no se toca nunca.

TRES PROBLEMAS QUE ARREGLA, Y QUE RESULTARON SER EL MISMO NUDO

  1. LA ETIQUETA MIENTE
     `market_cap_usd` tiene PESOS en las 54 empresas argentinas. Se ve en la
     mediana por grupo: S&P 500 = 44 mil millones, ADR = 4 mil millones,
     BYMA = 322 mil millones. La empresa argentina mediana no vale siete veces
     lo que la del S&P 500: la columna esta en pesos.

  2. EL PERIODO NO ES UN AÑO
     37 de las 56 apoyan sus ratios en un periodo INTERMEDIO, no en un
     ejercicio: 15 acumulan solo 3 meses, 5 acumulan 6 y 17 acumulan 9. s2 elige
     "el period_end mas reciente" sin preguntar cuando cierra el ejercicio.

     Un cuarto de año publicado como si fuera un año: el PER sale unas cuatro
     veces mas alto de lo que corresponde, y el numero es plausible, asi que no
     se nota mirando.

     OJO CON `cnv_estados_norm.tipo`: NO sirve para esto, aunque lo parezca.
     job5 lo completa con una adivinanza --
         if rev > 100_000_000_000: return "A"
         if mes in (12, 5, 6):     return "A"
         return "P"
     "si factura mucho, es anual". Por eso Aluar tiene seis cierres marcados "A"
     separados TRES MESES entre si. Una medicion basada en ese campo daba 23 de
     56; con el calendario real son 37.

  3. LOS DOS SON EL MISMO NUDO
     Recalculando el PER-TTM con la capitalizacion correcta, AGRO pasa de 0,65
     a 21,8 y HAVA de 0,02 a 21,8. Estaban marcadas `per_fuera_rango` por la
     escala, no por el periodo.

QUE NO HAY QUE CONSTRUIR: YA ESTABA
  per_ttm y ratios_ttm (56 filas cada una, del 2026-07-13) ya calculan los doce
  meses con des-acumulacion (`IAMC_TTM_decum`) -- los parciales de la CNV son
  ACUMULADOS desde el inicio del ejercicio (verificado con SEMI: 15.194 ->
  30.971 -> 50.418 millones), asi que armar el año es restar, no sumar. Eso ya
  esta resuelto. Lo que faltaba era ENCHUFARLO: el screener nunca las leyo.

LAS DOS MONEDAS, NO UNA
  Cada cifra de plata se publica dos veces: `_ars` con el valor nativo y
  `_usd_calc_mep_dolarito` con la conversion. Ninguna reemplaza a la otra.
  Se sigue la convencion que ya usaba s9: <campo>_<moneda>_<como>_<fuente>.

CADA CIFRA CON EL DOLAR DE SU FECHA
  - Capitalizacion: sale del precio de HOY  -> MEP de hoy.
  - Balance:        es de SU cierre         -> MEP de ese cierre.
  Son fechas distintas y se publican por separado (mep_precio_* y mep_balance_*).
  Bajo NIC 29 / RT 6 los balances argentinos ya vienen reexpresados en pesos del
  dia del cierre, asi que el dolar del cierre es el que corresponde -- no un
  promedio del periodo, que es lo que se usaria en un pais sin hiperinflacion
  (NIC 21.42-43).

EL PER DE LAS QUE PIERDEN PLATA
  21 de las 56 tienen perdida real. Su PER queda VACIO, con el motivo en
  `per_ttm_estado`. Un PER negativo no significa nada y publicarlo invita a
  ordenar por esa columna y sacar conclusiones al reves.

USO
  python enriquecer_v2_byma.py --dry-run
  python enriquecer_v2_byma.py
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
from _mep import MEP  # noqa: E402

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2-binary no instalado. Correr: pip install psycopg2-binary")

TABLA = "screener_v2"

# (columna, tipo). Todas nuevas: no se pisa nada de lo que ya hay.
NUEVAS = [
    ("market_cap_ars",                    "double precision"),
    ("market_cap_usd_calc_mep_dolarito",  "double precision"),
    ("mep_precio_valor",                  "double precision"),
    ("mep_precio_fecha",                  "text"),
    ("eps_ttm_ars",                       "double precision"),
    ("eps_ttm_usd_calc_mep_dolarito",     "double precision"),
    ("netincome_ttm_ars",                 "double precision"),
    ("netincome_ttm_usd_calc_mep_dolarito", "double precision"),
    ("mep_balance_valor",                 "double precision"),
    ("mep_balance_fecha",                 "text"),
    ("per_ttm",                           "double precision"),
    ("per_ttm_estado",                    "text"),
    ("per_ttm_metodo",                    "text"),
    ("ttm_periodo_fin",                   "text"),
    ("periodo_tipo",                      "text"),
    ("periodo_meses",                     "integer"),
    ("fy_end_month",                      "integer"),
]

# Estados de per_ttm en los que el PER NO se publica, y por que.
SIN_PER = {
    "perdida_real":     "la empresa perdio plata: un PER negativo no significa nada",
    "gap_trimestres":   "faltan trimestres para armar los doce meses",
    "pocos_trimestres": "no hay suficientes presentaciones",
    "escala_corrupta":  "los valores del balance tienen un error de escala",
    "stale":            "el ultimo balance es demasiado viejo",
}


def conn_pg():
    def _env():
        f = ROOT / ".env"
        if f.exists():
            for l in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                for k in ("DB_PASSWORD=", "POSTGRES_PASSWORD="):
                    if l.strip().startswith(k):
                        return l.split("=", 1)[1].strip().strip('"').strip("'")
        return "catalaxia"
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "catalaxia"),
        user=os.environ.get("DB_USER", "catalaxia"),
        password=os.environ.get("DB_PASSWORD") or _env())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sl = sqlite3.connect(str(DB))
    mep = MEP(sl)
    ini, fin, n = mep.cobertura
    print("ENRIQUECER screener_v2 -- BYMA en pesos y en dolares")
    print("=" * 66)
    print(f"  serie MEP: {ini} -> {fin}  ({n} ruedas)")

    # --- QUE PERIODO ES, segun la CNV y no segun una adivinanza ---------------
    # NO se usa cnv_estados_norm.tipo. Ese campo lo pone job5 con esta regla:
    #     if rev > 100_000_000_000: return "A"
    #     if mes in (12, 5, 6):     return "A"
    #     return "P"
    # Es decir: "si factura mucho, es anual". Por eso Aluar tiene seis cierres
    # marcados "A" separados TRES MESES entre si.
    #
    # La fuente autoritativa es fiscal_calendar, construido leyendo las paginas
    # de la CNV, donde figura "PERIODICIDAD: 1" (anual) o "3" (trimestral) y la
    # fecha de cierre. Cubre las 56 BYMA. Es la misma fuente que usa
    # recompute_ttm para des-acumular, asi que ambos coinciden por construccion.
    fcal = {cu: (fy, inc) for cu, fy, inc in sl.execute(
        "SELECT cuit, fy_end_month, inconsistent FROM fiscal_calendar")}

    def periodo_de(cuit, pe):
        """(anual|intermedio|desconocido, meses_acumulados)."""
        if not pe or cuit not in fcal:
            return "desconocido", None
        fy = fcal[cuit][0]
        if fy is None:
            return "desconocido", None
        mes = int(pe[5:7])
        if mes == fy:
            return "anual", 12
        # los parciales de la CNV son ACUMULADOS desde el inicio del ejercicio,
        # asi que los meses transcurridos son la distancia al fin de ejercicio.
        return "intermedio", (mes - fy) % 12

    filas = sl.execute("""
        SELECT s.ticker, s.cuit, s.ultimo_periodo, s.MarketCapUSD,
               p.eps_ttm, p.ttm_netincome, p.per_ttm, p.estado, p.metodo
        FROM screener s LEFT JOIN per_ttm p ON p.ticker = s.ticker
        WHERE s.grupo='byma_only'
    """).fetchall()
    print(f"  empresas BYMA: {len(filas)}")

    mep_hoy, fecha_hoy, _ = mep.en(fin)
    print(f"  MEP para precios (hoy): {mep_hoy:,.2f} del {fecha_hoy}\n")

    datos, sin_mep_bal, con_per, sin_per = [], 0, 0, {}
    rep, meses = {}, {}
    for tk, cuit, pe, mcap_ars, eps, ni, per, estado, metodo in filas:
        # 1. capitalizacion: precio de hoy -> MEP de hoy
        mcap_usd, _, _ = mep.convertir(mcap_ars, fecha_hoy)
        # 2. balance: su cierre -> MEP de ese cierre
        mep_bal, fbal, motivo_bal = mep.en(pe) if pe else (None, None, "sin_periodo")
        if not mep_bal:
            sin_mep_bal += 1
        eps_usd = (eps / mep_bal) if (eps is not None and mep_bal) else None
        ni_usd = (ni / mep_bal) if (ni is not None and mep_bal) else None
        # 3. el PER solo si el estado lo permite
        if estado in SIN_PER or per is None:
            per_pub = None
            sin_per[estado or "sin_ttm"] = sin_per.get(estado or "sin_ttm", 0) + 1
        else:
            # con la capitalizacion CORRECTA, no la que traia ratios_ttm
            per_pub = (mcap_ars / ni) if (ni and ni > 0) else None
            if per_pub:
                con_per += 1
        ptipo, pmeses = periodo_de(cuit, pe)
        rep[ptipo] = rep.get(ptipo, 0) + 1
        if ptipo == "intermedio":
            meses[pmeses] = meses.get(pmeses, 0) + 1
        datos.append((mcap_ars, mcap_usd, mep_hoy, fecha_hoy,
                      eps, eps_usd, ni, ni_usd, mep_bal, fbal,
                      per_pub, estado, metodo, pe,
                      ptipo, pmeses, fcal.get(cuit, (None, None))[0], tk))

    print(f"  periodo de cada fila (segun fiscal_calendar, NO segun `tipo`):")
    for k, v in sorted(rep.items(), key=lambda x: -x[1]):
        print(f"     {k:<14} {v:>3}")
    for m, v in sorted(meses.items()):
        print(f"        de los intermedios, {m:>2} meses acumulados: {v}")
    print()
    print(f"  con PER publicable      : {con_per}")
    print(f"  sin PER, con motivo     : {sum(sin_per.values())}")
    for e, k in sorted(sin_per.items(), key=lambda x: -x[1]):
        print(f"     {e:<18} {k:>3}   {SIN_PER.get(e,'sin estado TTM')}")
    if sin_mep_bal:
        print(f"  sin MEP para su cierre  : {sin_mep_bal}  (quedan vacias, no se rellenan)")

    if a.dry_run:
        print("\n  (dry-run) no se escribio nada.")
        return

    pg = conn_pg(); cur = pg.cursor()
    cur.execute("""SELECT lower(column_name) FROM information_schema.columns
                   WHERE table_name=%s""", (TABLA,))
    hay = {r[0] for r in cur.fetchall()}
    if not hay:
        sys.exit(f"FATAL: {TABLA} no existe. Correr publicar_screener_v2.py primero.")
    for c, t in NUEVAS:
        if c not in hay:
            cur.execute(f'ALTER TABLE "{TABLA}" ADD COLUMN "{c}" {t}')
    pg.commit()

    sets = ", ".join(f'"{c}"=%s' for c, _ in NUEVAS)
    cur.executemany(f'UPDATE "{TABLA}" SET {sets} WHERE ticker=%s', datos)
    pg.commit()
    print(f"\n  {TABLA}: {cur.rowcount if cur.rowcount>0 else len(datos)} filas BYMA actualizadas")

    # --- control de cordura: la mediana tiene que bajar a un orden creible ---
    cur.execute(f'''SELECT round(percentile_cont(0.5) WITHIN GROUP
                    (ORDER BY market_cap_usd_calc_mep_dolarito)/1e6)
                    FROM "{TABLA}" WHERE grupo='byma_only'
                      AND market_cap_usd_calc_mep_dolarito IS NOT NULL''')
    med = cur.fetchone()[0]
    print(f"  capitalizacion mediana BYMA: {med:,.0f} millones de USD")
    print("     (antes figuraba en 322.000 millones, que era pesos con etiqueta de dolares)")
    cur.execute('SELECT count(*) FROM screener')
    print(f"  control: `screener` intacta con {cur.fetchone()[0]} filas")
    pg.close(); sl.close()
    print("\nOK -- la API no cambia hasta que alguien la apunte a screener_v2.")


if __name__ == "__main__":
    main()
