# -*- coding: utf-8 -*-
"""
Bloque 0+1 del plan: CATALOGO + METADATA de todo el universo de tickers de SEC.

Bloque 0 (catalogo, rapido): company_tickers + _exchange + lista S&P500 ->
  arma la tabla `empresas` con las 8.021 empresas, su(s) ticker(s), exchange,
  flag es_sp500, sector GICS y grupo (sp500/adr_arg/adr_bra/otro).

Bloque 1 (metadata, largo, resume-safe): submissions/CIK.json por empresa ->
  completa SIC/industria, pais, tamaño de filer, cierre fiscal. Cachea el raw
  en data/raw/submissions/. Re-correr saltea lo ya hecho.

Uso:
  python construir_catalogo.py catalogo   -> solo Bloque 0 (rapido)
  python construir_catalogo.py meta        -> solo Bloque 1 (largo, background)
  python construir_catalogo.py             -> los dos
"""
from __future__ import annotations
import io, json, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

H = {"User-Agent": "Federico Monfasani fmonfasani@gmail.com", "Accept-Encoding": "gzip, deflate"}
H_WEB = {"User-Agent": "Mozilla/5.0 (research; fmonfasani@gmail.com)"}
DELAY = 0.12

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir())
DATA = ROOT / "data"
DB = DATA / "screener.db"
CAT = DATA / "catalogo"
RAW_SUBS = DATA / "raw" / "submissions"

ADR_ARG = {"YPF","GGAL","BMA","BBAR","SUPV","PAM","TEO","CRESY","TGS","CEPU","EDN","LOMA","IRS","BIOX","MELI","GLOB"}
ADR_BRA = {"PBR","VALE","ITUB","BBD","ABEV","GGB","SID","CIG","BSBR","SBS","VIV","UGP","XP","NU","STNE","PAGS","VTEX","INTR"}
# paises LatAm (para reclasificar 'otro' -> 'latam' tras submissions)
LATAM = {"Argentina","Brazil","Mexico","Chile","Colombia","Peru","Uruguay","Panama",
         "Bolivia","Paraguay","Ecuador","Venezuela","Costa Rica","Dominican Republic"}


def schema(con):
    # Migracion: si existe una `empresas` vieja (de construir_base) sin la
    # columna `grupo`, se reemplaza por el esquema-catalogo. La tabla `facts`
    # (la data pesada) NO se toca; el resumen de facts se re-llena en Bloque 2.
    cols = [r[1] for r in con.execute("PRAGMA table_info(empresas)")]
    if cols and "grupo" not in cols:
        con.execute("DROP TABLE empresas")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS empresas (
        cik TEXT PRIMARY KEY, nombre TEXT, ticker_ppal TEXT, exchange_ppal TEXT,
        es_sp500 INTEGER DEFAULT 0, grupo TEXT, sector_gics TEXT,
        sic TEXT, sic_desc TEXT, sector_sic TEXT, pais TEXT,
        category TEXT, fiscal_year_end TEXT,
        esquema TEXT, moneda TEXT, n_tags INTEGER, n_datapoints INTEGER,
        fecha_meta TEXT, fecha_facts TEXT
    );
    CREATE TABLE IF NOT EXISTS tickers (cik TEXT, ticker TEXT, exchange TEXT);
    CREATE TABLE IF NOT EXISTS descargas_log (cik TEXT, capa TEXT, estado TEXT, error TEXT, ts TEXT);
    CREATE INDEX IF NOT EXISTS ix_emp_grupo ON empresas(grupo);
    CREATE INDEX IF NOT EXISTS ix_emp_sp500 ON empresas(es_sp500);
    """)
    con.commit()


def sic_sector(sic):
    try: d = int(str(sic)[:2])
    except: return None
    if 1 <= d <= 9: return "Agro/Minería primaria"
    if 10 <= d <= 14: return "Minería/Energía extractiva"
    if 15 <= d <= 17: return "Construcción"
    if 20 <= d <= 39: return "Manufactura/Industria"
    if 40 <= d <= 49: return "Transporte/Utilities/Telecom"
    if 50 <= d <= 51: return "Comercio mayorista"
    if 52 <= d <= 59: return "Comercio minorista"
    if 60 <= d <= 67: return "Finanzas/Seguros/Inmobiliario"
    if 70 <= d <= 89: return "Servicios"
    return "Otro"


def bloque0(con):
    print("== BLOQUE 0: catalogo ==")
    ct = json.load(open(CAT / "company_tickers.json", encoding="utf-8"))
    # exchange map: cik -> lista (ticker, exchange)
    print("  bajando company_tickers_exchange.json ...")
    ex = requests.get("https://www.sec.gov/files/company_tickers_exchange.json", headers=H, timeout=30).json()
    fi = ex["fields"]; iticker=fi.index("ticker"); iex=fi.index("exchange"); icik=fi.index("cik")
    exch_por_cik = {}
    for row in ex["data"]:
        cik = str(row[icik]).zfill(10)
        exch_por_cik.setdefault(cik, []).append((str(row[iticker]).upper(), row[iex]))
    # S&P 500 (Wikipedia: Symbol, GICS Sector, CIK)
    print("  bajando lista S&P 500 ...")
    sp_sector = {}
    try:
        import pandas as pd
        html = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=H_WEB, timeout=30).text
        df = pd.read_html(io.StringIO(html))[0]
        for _, r in df.iterrows():
            if pd.notna(r.get("CIK")):
                sp_sector[str(int(r["CIK"])).zfill(10)] = r["GICS Sector"]
    except Exception as e:
        print(f"  (no se pudo bajar S&P500: {e})")
    print(f"  S&P500: {len(sp_sector)} empresas")

    # nombre + tickers por cik
    info = {}
    for e in ct.values():
        cik = str(e["cik_str"]).zfill(10)
        info.setdefault(cik, {"nombre": e.get("title",""), "tickers": []})
        t = (e.get("ticker") or "").upper()
        if t: info[cik]["tickers"].append(t)

    emp_rows, tick_rows = [], []
    for cik, d in info.items():
        exchs = exch_por_cik.get(cik, [])
        for tk, exo in exchs:
            tick_rows.append((cik, tk, exo))
        ticker_ppal = (exchs[0][0] if exchs else (d["tickers"][0] if d["tickers"] else None))
        exch_ppal = exchs[0][1] if exchs else None
        es_sp = 1 if cik in sp_sector else 0
        tks = set(d["tickers"])
        if es_sp: grupo = "sp500"
        elif tks & ADR_ARG: grupo = "adr_arg"
        elif tks & ADR_BRA: grupo = "adr_bra"
        else: grupo = "otro"
        emp_rows.append((cik, d["nombre"], ticker_ppal, exch_ppal, es_sp, grupo, sp_sector.get(cik)))

    con.execute("DELETE FROM tickers")
    con.executemany("INSERT INTO tickers VALUES (?,?,?)", tick_rows)
    # upsert empresas (preserva columnas de facts si ya existen)
    for row in emp_rows:
        con.execute("""INSERT INTO empresas (cik,nombre,ticker_ppal,exchange_ppal,es_sp500,grupo,sector_gics)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(cik) DO UPDATE SET nombre=excluded.nombre, ticker_ppal=excluded.ticker_ppal,
              exchange_ppal=excluded.exchange_ppal, es_sp500=excluded.es_sp500,
              grupo=COALESCE(excluded.grupo,empresas.grupo), sector_gics=excluded.sector_gics""", row)
    con.commit()
    print(f"  empresas en catalogo: {len(emp_rows)}  | tickers: {len(tick_rows)}")
    from collections import Counter
    c = Counter(r[5] for r in emp_rows)
    print(f"  por grupo: {dict(c)}")


def get_json_cache(url, cache_path):
    if cache_path.exists():
        try: return json.loads(cache_path.read_text(encoding="utf-8")), True
        except Exception: pass
    try:
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code != 200: return None, False
        data = r.json(); cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data), encoding="utf-8"); return data, False
    except Exception:
        return None, False


def bloque1(con):
    print("== BLOQUE 1: metadata (submissions), resume-safe ==")
    orden = "CASE grupo WHEN 'sp500' THEN 0 WHEN 'adr_arg' THEN 1 WHEN 'adr_bra' THEN 2 ELSE 3 END"
    ciks = [r[0] for r in con.execute(f"SELECT cik FROM empresas WHERE fecha_meta IS NULL ORDER BY {orden}, cik")]
    total = len(ciks)
    print(f"  pendientes: {total}")
    hechos = 0
    for cik in ciks:
        sub, era = get_json_cache(f"https://data.sec.gov/submissions/CIK{cik}.json", RAW_SUBS / f"CIK{cik}.json")
        if not era: time.sleep(DELAY)
        if not sub:
            con.execute("INSERT INTO descargas_log VALUES (?,?,?,?,?)", (cik,"submissions","error","sin_data",datetime.now(timezone.utc).isoformat()))
            con.execute("UPDATE empresas SET fecha_meta=? WHERE cik=?", ("ERROR", cik))
        else:
            sic = sub.get("sic"); pais = sub.get("stateOfIncorporationDescription") or (sub.get("addresses",{}).get("business",{}) or {}).get("stateOrCountry")
            grupo_act = con.execute("SELECT grupo FROM empresas WHERE cik=?", (cik,)).fetchone()[0]
            nuevo_grupo = grupo_act
            if grupo_act == "otro":
                nuevo_grupo = "latam" if (pais in LATAM) else ("us_other")
            con.execute("""UPDATE empresas SET sic=?, sic_desc=?, sector_sic=?, pais=?, category=?,
                fiscal_year_end=?, grupo=?, fecha_meta=? WHERE cik=?""",
                (str(sic) if sic else None, sub.get("sicDescription"), sic_sector(sic), pais,
                 sub.get("category"), sub.get("fiscalYearEnd"), nuevo_grupo,
                 datetime.now(timezone.utc).isoformat(), cik))
        hechos += 1
        if hechos % 100 == 0:
            con.commit(); print(f"  {hechos}/{total} ...")
    con.commit()
    print(f"  metadata completada: {hechos} empresas")


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    fase = sys.argv[1] if len(sys.argv) > 1 else "todo"
    con = sqlite3.connect(DB)
    schema(con)
    if fase in ("catalogo","todo"):
        bloque0(con)
    if fase in ("meta","todo"):
        bloque1(con)
    con.close()
    print("OK")


if __name__ == "__main__":
    main()
