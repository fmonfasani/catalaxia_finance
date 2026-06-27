# -*- coding: utf-8 -*-
"""
Constructor de base de datos del screener.

Descarga companyfacts de SEC EDGAR y guarda TODOS los tags (us-gaap E ifrs-full)
en SQLite, normalizando los conceptos core a un nombre canonico unico para que
una empresa us-gaap (NetIncomeLoss) y una IFRS (ProfitLoss) queden comparables.

Resuelve el "fix IFRS": el mapeo CANONICO de abajo tiene, por cada concepto,
los nombres de tag en las dos taxonomias (los ifrs-full fueron descubiertos
empiricamente sobre ADR reales: GGAL, ABEV, VIV, PAM, UGP, NU, GGB, LOMA).

Uso:
  python construir_base.py            -> ADR argentinos + brasileros (default)
  python construir_base.py SP500      -> (placeholder, se agrega despues)

Resume-safe: si la empresa ya esta en la base, la saltea.
"""
from __future__ import annotations
import json, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# Fase 1: solo ultimos N anios (base chica y rapida; alcanza para ratios + CAGR
# 5 anios). Fase 2 mas adelante: subir a 30 y re-parsear el raw cacheado.
ANIOS_HISTORIA = 6
CUTOFF = (datetime.now(timezone.utc) - timedelta(days=365 * ANIOS_HISTORIA)).date().isoformat()

H = {"User-Agent": "Federico Monfasani fmonfasani@gmail.com", "Accept-Encoding": "gzip, deflate"}
DELAY = 0.12
FORMS_OK = {"10-K","10-K/A","10-Q","10-Q/A","20-F","20-F/A","40-F","40-F/A","6-K","6-K/A"}

# Datos fuera del codigo: cache crudo (raw, fuente de verdad) + base derivada.
# Ver docs/screener/ y .gitignore (data/ no se versiona).
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir())
DATA = ROOT / "data"
DB = DATA / "screener.db"
CT = DATA / "catalogo" / "company_tickers.json"
RAW_FACTS = DATA / "raw" / "companyfacts"
RAW_SUBS = DATA / "raw" / "submissions"

# ── Mapeo canonico: concepto -> tags por taxonomia (el "fix IFRS") ──
CANONICO = {
 "Revenue":            {"us-gaap":["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet"], "ifrs-full":["Revenue","RevenueFromSaleOfGoods"]},
 "GrossProfit":        {"us-gaap":["GrossProfit"], "ifrs-full":["GrossProfit"]},
 "OperatingIncome":    {"us-gaap":["OperatingIncomeLoss"], "ifrs-full":["ProfitLossFromOperatingActivities"]},
 "PretaxIncome":       {"us-gaap":["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"], "ifrs-full":["ProfitLossBeforeTax"]},
 "NetIncome":          {"us-gaap":["NetIncomeLoss","ProfitLoss"], "ifrs-full":["ProfitLossAttributableToOwnersOfParent","ProfitLoss"]},
 "EPS_basic":          {"us-gaap":["EarningsPerShareBasic"], "ifrs-full":["BasicEarningsLossPerShare"]},
 "EPS_diluted":        {"us-gaap":["EarningsPerShareDiluted"], "ifrs-full":["DilutedEarningsLossPerShare"]},
 "Shares_diluted":     {"us-gaap":["WeightedAverageNumberOfDilutedSharesOutstanding"], "ifrs-full":["AdjustedWeightedAverageShares","WeightedAverageShares"]},
 "Shares_basic":       {"us-gaap":["WeightedAverageNumberOfSharesOutstandingBasic"], "ifrs-full":["WeightedAverageShares"]},
 "DA":                 {"us-gaap":["DepreciationDepletionAndAmortization","DepreciationAndAmortization","Depreciation"], "ifrs-full":["DepreciationAndAmortisationExpense","AdjustmentsForDepreciationAndAmortisationExpense"]},
 "Assets":             {"us-gaap":["Assets"], "ifrs-full":["Assets"]},
 "AssetsCurrent":      {"us-gaap":["AssetsCurrent"], "ifrs-full":["CurrentAssets"]},
 "Cash":               {"us-gaap":["CashAndCashEquivalentsAtCarryingValue"], "ifrs-full":["CashAndCashEquivalents"]},
 "Inventory":          {"us-gaap":["InventoryNet"], "ifrs-full":["Inventories"]},
 "Receivables":        {"us-gaap":["AccountsReceivableNetCurrent"], "ifrs-full":["TradeAndOtherCurrentReceivables","CurrentTradeReceivables"]},
 "Liabilities":        {"us-gaap":["Liabilities"], "ifrs-full":["Liabilities"]},
 "LiabilitiesCurrent": {"us-gaap":["LiabilitiesCurrent"], "ifrs-full":["CurrentLiabilities"]},
 "Debt":               {"us-gaap":["LongTermDebt","LongTermDebtNoncurrent"], "ifrs-full":["Borrowings","LongtermBorrowings"]},
 "Equity":             {"us-gaap":["StockholdersEquity"], "ifrs-full":["EquityAttributableToOwnersOfParent","Equity"]},
 "CFO":                {"us-gaap":["NetCashProvidedByUsedInOperatingActivities"], "ifrs-full":["CashFlowsFromUsedInOperatingActivities"]},
 "CapEx":              {"us-gaap":["PaymentsToAcquirePropertyPlantAndEquipment","PaymentsToAcquireProductiveAssets"], "ifrs-full":["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"]},
 "Dividends":          {"us-gaap":["PaymentsOfDividendsCommonStock","PaymentsOfDividends"], "ifrs-full":["DividendsPaidClassifiedAsFinancingActivities","DividendsPaid"]},
 "SharesOutstanding":  {"us-gaap":["CommonStockSharesOutstanding","EntityCommonStockSharesOutstanding"], "ifrs-full":["NumberOfSharesOutstanding"]},
}
# reverse: (taxonomia, tag) -> concepto canonico
TAG2CONCEPTO = {}
for concepto, taxs in CANONICO.items():
    for tax, tags in taxs.items():
        for tag in tags:
            TAG2CONCEPTO[(tax, tag)] = concepto

ADR_ARG = ["YPF","GGAL","BMA","BBAR","SUPV","PAM","TEO","CRESY","TGS","CEPU","EDN","LOMA","IRS","BIOX","MELI","GLOB"]
ADR_BRA = ["PBR","VALE","ITUB","BBD","ABEV","GGB","SID","CIG","BSBR","SBS","VIV","UGP","XP","NU","STNE","PAGS","VTEX","INTR"]


def crear_schema(con):
    # empresas: mismo esquema-catalogo que construir_catalogo.py (este script
    # solo COMPLETA las columnas de facts, no pisa el catalogo).
    con.executescript("""
    CREATE TABLE IF NOT EXISTS empresas (
        cik TEXT PRIMARY KEY, nombre TEXT, ticker_ppal TEXT, exchange_ppal TEXT,
        es_sp500 INTEGER DEFAULT 0, grupo TEXT, sector_gics TEXT,
        sic TEXT, sic_desc TEXT, sector_sic TEXT, pais TEXT,
        category TEXT, fiscal_year_end TEXT,
        esquema TEXT, moneda TEXT, n_tags INTEGER, n_datapoints INTEGER,
        fecha_meta TEXT, fecha_facts TEXT
    );
    CREATE TABLE IF NOT EXISTS facts (
        cik TEXT, taxonomia TEXT, tag TEXT, concepto TEXT, unit TEXT,
        period_start TEXT, period_end TEXT, val REAL,
        fy INTEGER, fp TEXT, form TEXT, filed TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_facts_cik ON facts(cik);
    CREATE INDEX IF NOT EXISTS ix_facts_concepto ON facts(concepto);
    """)
    con.commit()


def cargar_mapa_cik():
    ct = json.load(open(CT, encoding="utf-8"))
    m = {}
    for e in ct.values():
        t = (e.get("ticker") or "").upper()
        if t: m[t] = (str(e["cik_str"]).zfill(10), e.get("title",""))
    return m


def get_json_cache(url, cache_path):
    """Lee del cache crudo si existe; si no, descarga de SEC y lo guarda. El
    raw es la fuente de verdad: una vez bajado no se vuelve a pegar a SEC, asi
    la base se puede reconstruir (o cargar en Postgres) sin red. Devuelve
    (data, era_cache)."""
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8")), True
        except Exception:
            pass
    try:
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code != 200:
            return None, False
        data = r.json()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data), encoding="utf-8")
        return data, False
    except Exception:
        return None, False


def descargar_empresa(con, ticker, cik, nombre):
    # metadata (submissions) -- cacheada en data/raw/submissions/
    sub, era_cache = get_json_cache(f"https://data.sec.gov/submissions/CIK{cik}.json", RAW_SUBS / f"CIK{cik}.json")
    if not era_cache:
        time.sleep(DELAY)
    sub = sub or {}
    sic = sub.get("sic"); sic_desc = sub.get("sicDescription")
    pais = (sub.get("addresses",{}).get("business",{}) or {}).get("stateOrCountry") or sub.get("stateOfIncorporationDescription")
    fye = sub.get("fiscalYearEnd")

    facts, era_cache = get_json_cache(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", RAW_FACTS / f"CIK{cik}.json")
    if not era_cache:
        time.sleep(DELAY)
    if not facts:
        return None
    f = facts.get("facts", {})
    if not (f.get("us-gaap") or f.get("ifrs-full")):
        return ("sin-financials", 0, 0)

    filas = []
    tags_vistos = set()
    core_por_tax = {"us-gaap": set(), "ifrs-full": set()}
    for tax in ("us-gaap","ifrs-full"):
        for tag, body in f.get(tax, {}).items():
            concepto = TAG2CONCEPTO.get((tax, tag))
            for unit, datos in body.get("units", {}).items():
                for d in datos:
                    end = d.get("end")
                    if d.get("val") is None or d.get("form") not in FORMS_OK:
                        continue
                    if end and end < CUTOFF:   # fase 1: solo ultimos ANIOS_HISTORIA
                        continue
                    tags_vistos.add((tax, tag))
                    if concepto:
                        core_por_tax[tax].add(concepto)
                    filas.append((cik, tax, tag, concepto, unit,
                                  d.get("start"), d.get("end"), d.get("val"),
                                  d.get("fy"), d.get("fp"), d.get("form"), d.get("filed")))
    # esquema = la taxonomia que aporta MAS conceptos core (no "la que tenga
    # algun tag"): YPF tiene 1 tag us-gaap suelto pero su data real es IFRS.
    esquema = "ifrs-full" if len(core_por_tax["ifrs-full"]) > len(core_por_tax["us-gaap"]) else "us-gaap"
    # moneda = unidad dominante de los conceptos monetarios core (USD/BRL/ARS...)
    monedas = {}
    for r in filas:
        if r[3] and r[4] and r[4] not in ("shares","pure","USD/shares"):
            monedas[r[4]] = monedas.get(r[4], 0) + 1
    moneda = max(monedas, key=monedas.get) if monedas else None

    # idempotente: borra los facts viejos de este CIK antes de re-insertar
    con.execute("DELETE FROM facts WHERE cik=?", (cik,))
    con.executemany("INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", filas)
    # asegura la fila (por si se corre sin catalogo) y COMPLETA solo facts-cols
    con.execute("INSERT INTO empresas (cik, nombre) VALUES (?,?) ON CONFLICT(cik) DO NOTHING",
                (cik, nombre or facts.get("entityName")))
    con.execute("""UPDATE empresas SET esquema=?, moneda=?, n_tags=?, n_datapoints=?, fecha_facts=?,
                   sic=COALESCE(sic,?), sic_desc=COALESCE(sic_desc,?), pais=COALESCE(pais,?),
                   fiscal_year_end=COALESCE(fiscal_year_end,?) WHERE cik=?""",
                (esquema, moneda, len(tags_vistos), len(filas), datetime.now(timezone.utc).isoformat(),
                 str(sic) if sic else None, sic_desc, pais, fye, cik))
    con.commit()
    return (esquema, len(tags_vistos), len(filas))


def universo_objetivo(con, modo):
    """Devuelve lista de (ticker, cik, nombre) segun el bloque a bajar."""
    if modo == "sp500":
        return [(tk or cik, cik, nom) for cik, tk, nom in
                con.execute("SELECT cik, ticker_ppal, nombre FROM empresas WHERE es_sp500=1 ORDER BY ticker_ppal")]
    if modo == "latam":
        return [(tk or cik, cik, nom) for cik, tk, nom in
                con.execute("SELECT cik, ticker_ppal, nombre FROM empresas WHERE grupo IN ('adr_arg','adr_bra','latam') ORDER BY grupo, ticker_ppal")]
    # default: ADR ARG+BRA via company_tickers
    mapa = cargar_mapa_cik()
    out = []
    for tk in ADR_ARG + ADR_BRA:
        info = mapa.get(tk) or mapa.get(tk.replace(".","-")) or mapa.get(tk.split(".")[0])
        if info:
            out.append((tk, info[0], info[1]))
    return out


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "adr"
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=60)
    con.execute("PRAGMA busy_timeout=60000")   # concurrencia: espera si otro escribe
    try: con.execute("PRAGMA journal_mode=WAL")
    except Exception: pass
    crear_schema(con)
    universo = universo_objetivo(con, modo)
    print("="*64)
    print(f"  BLOQUE 2 (facts) -> {DB.name}  | modo={modo}  | historia={ANIOS_HISTORIA}a (desde {CUTOFF})")
    print(f"  Universo: {len(universo)} empresas")
    print("="*64)
    ya = {r[0] for r in con.execute("SELECT cik FROM empresas WHERE fecha_facts IS NOT NULL")}

    stats = {"us-gaap":0,"ifrs-full":0,"sin-financials":0,"sin-cik":0,"skip":0}
    n = len(universo)
    for i, (tk, cik, nombre) in enumerate(universo, 1):
        if cik in ya:
            stats["skip"]+=1; continue
        res = descargar_empresa(con, tk, cik, nombre)
        if res is None:
            print(f"  [{i:4}/{n}] {tk:<7} -> error/sin-facts"); stats["sin-financials"]+=1; continue
        esq, ntags, ndp = res
        stats[esq] = stats.get(esq,0)+1
        if i % 25 == 0 or i <= 5:
            print(f"  [{i:4}/{n}] {tk:<7} -> {esq:<10} {ntags:>3} tags, {ndp:>5} dp")

    # resumen
    print("\n" + "-"*64)
    tot_emp = con.execute("SELECT COUNT(*) FROM empresas").fetchone()[0]
    tot_dp = con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    tot_dp_core = con.execute("SELECT COUNT(*) FROM facts WHERE concepto IS NOT NULL").fetchone()[0]
    print(f"  Empresas en la base : {tot_emp}")
    print(f"  Datapoints totales  : {tot_dp:,}")
    print(f"  Datapoints 'core'   : {tot_dp_core:,} (conceptos canonicos)")
    print(f"  Por esquema         : {dict((k,v) for k,v in stats.items() if v)}")
    print(f"\n  OK {DB}")
    con.close()


if __name__ == "__main__":
    main()
