# -*- coding: utf-8 -*-
"""
FASE 0 -- Normalizacion de clave cnv_estados
=============================================
Construye mapa_entidades + cnv_estados_norm con clave canonica por CUIT.

Insumos:
  - data/screener.db -> cnv_estados (crudo)
  - scripts/tickets/cnv/datos/empresas.csv  (56 BYMA, ticker<->cuit)
  - scripts/tickets/cnv/datos/empresas_subset.csv (72 subset, ticker<->cuit<->grupo)

Proceso:
  1. Lee mapping ticker<->cuit (empresas.csv + empresas_subset.csv)
  2. Construye tabla mapa_entidades (cuit, ticker, cik_byma, cik_cuit, nombre, grupo)
  3. Lee cnv_estados, separa BYMA-* (viejas) de CUIT (nuevas)
  4. Normaliza viejas: BYMA-{TICKER} -> buscar CUIT en mapping -> cik = CUIT
  5. UNION + dedup por (cuit, concepto, period_end, fecha_reexpresion)
  6. Escribe cnv_estados_norm
  7. Gate: huerfanas = 0, consistencia viejo-vs-nuevo

Idempotente: DROP/RECREATE sus tablas de salida.
"""
from __future__ import annotations
import csv, sqlite3, re
from pathlib import Path
from collections import defaultdict

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "data").is_dir())
import os as _os
# Permite apuntar a una copia de prueba sin tocar produccion:
#   set SCREENER_DB=screener.db.test   (o export en bash)
DB = ROOT / "data" / _os.environ.get("SCREENER_DB", "screener.db")
DATOSCNV = ROOT / "scripts" / "tickets" / "cnv" / "datos"
EMPRESAS56 = DATOSCNV / "empresas.csv"
SUBSET = DATOSCNV / "empresas_subset.csv"


def leer_mapping():
    """Retorna dict ticker->{cuit, empresa, grupo} + dict cuit->ticker.
    El subset es autoritativo: si un ticker ya esta en empresas.csv pero
    el subset trae otro CUIT, el del subset prevalece (casos BOLT, PATA).
    """
    by_ticker = {}
    by_cuit = {}
    _next_suffix = {}

    def add_entry(ticker, cuit, empresa, grupo):
        ticker = ticker.strip().upper()
        cuit = cuit.strip()
        if not ticker or not cuit:
            return
        # Caso A: CUIT ya registrado con OTRO ticker (ej. BOLT+GAMI mismo CUIT)
        if cuit in by_cuit and by_cuit[cuit] != ticker:
            # El ticker nuevo apunta al mismo CUIT
            if ticker not in by_ticker:
                by_ticker[ticker] = {"cuit": cuit, "empresa": empresa, "grupo": grupo}
            elif by_ticker[ticker]["cuit"] != cuit:
                # Conflicto: ticker ya existe con CUIT distinto -> sufijo
                _next_suffix[ticker] = _next_suffix.get(ticker, 1) + 1
                alt_ticker = f"{ticker}_{_next_suffix[ticker]}"
                by_ticker[alt_ticker] = {"cuit": cuit, "empresa": empresa, "grupo": grupo}
                by_cuit[cuit] = alt_ticker
            else:
                pass  # ticker ya apunta a este CUIT
            return
        by_cuit[cuit] = ticker
        if ticker in by_ticker:
            existing = by_ticker[ticker]
            if existing["cuit"] != cuit:
                # Mismo ticker, CUIT distinto (PATA caso)
                _next_suffix[ticker] = _next_suffix.get(ticker, 1) + 1
                alt_ticker = f"{ticker}_{_next_suffix[ticker]}"
                by_ticker[alt_ticker] = {"cuit": cuit, "empresa": empresa, "grupo": grupo}
                by_cuit[cuit] = alt_ticker
            else:
                if grupo:
                    existing["grupo"] = grupo
                if empresa:
                    existing["empresa"] = empresa
        else:
            by_ticker[ticker] = {"cuit": cuit, "empresa": empresa, "grupo": grupo}

    # 1) empresas.csv (56 BYMA) - primero, asi tickers reales tienen prioridad
    with open(EMPRESAS56, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ticker = r["ticker"].strip().upper()
            cuit = r["cuit"].strip()
            if ticker and cuit:
                add_entry(ticker, cuit, r.get("empresa", "").strip(), "byma_only")

    # 2) empresas_subset.csv - agrega ADR solo si CUIT no esta ya (BYMA tiene prioridad)
    with open(SUBSET, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ticker = r["ticker"].strip().upper()
            cuit = r["cuit"].strip()
            if not cuit:
                continue
            # Si CUIT ya mapeado por BYMA, preservar ticker real
            if cuit in by_cuit:
                continue
            if not ticker:
                ticker = "_ADR_" + cuit[-4:]
            add_entry(ticker, cuit, r.get("empresa", "").strip(), r.get("grupo", "").strip() or "adr")

    return by_ticker, by_cuit


def extraer_ticker_de_cik(cik):
    """De 'BYMA-ALUA' -> 'ALUA'. Si no tiene prefijo BYMA-, retorna None."""
    m = re.match(r"BYMA[-_](\w+)", cik)
    return m.group(1).upper() if m else None


def build():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    cur = con.cursor()

    print("FASE 0 -- Normalizacion de clave cnv_estados")
    print("=" * 60)

    # --- Leer mapping ---
    by_ticker, by_cuit = leer_mapping()
    print(f"\nMapping: {len(by_ticker)} tickers, {len(by_cuit)} CUITs")

    # --- Leer cnv_estados_v2 (fuente=cnv-aif2) ---
    # PARCHE 1: la v2 trae las unidades ya normalizadas (unidad_factor resuelve las
    # cinco variantes de texto: '$', 'Miles de $', 'MILES DE $', 'Millones de $',
    # 'MILLONES DE $') y `valor` queda expresado en pesos. Verificado: la serie de
    # TXAR/Assets es continua justo donde el factor salta de 1.000 a 1.000.000.
    # Ojo: el `ticker` de v2 es la razon social, no el simbolo -> se resuelve por CUIT.
    cur.execute("SELECT ticker, cuit, concepto, period_end, tipo, valor, valor_comparativo, fecha_reexpresion, form, unidad_factor, accn, fuente FROM cnv_estados_v2 WHERE fuente='cnv-aif2'")
    rows = cur.fetchall()
    print(f"Filas cnv_estados_v2 (fuente=cnv-aif2): {len(rows)}")

    # PARCHE 1b: las filas source_type='BYMA' de la normalizacion anterior aportan
    # la punta reciente de la serie. Verificado: en los 46 tickers presentes en ambas
    # vias, BYMA es mas nuevo en los 46 (BOLT adelanta 3 trimestres). No colisionan
    # con v2 en ninguna clave (cuit, concepto, period_end).
    try:
        cur.execute("""SELECT ticker, cuit, concepto, period_end, tipo, valor,
                              valor_comparativo, fecha_reexpresion, form, escala, accn, fuente
                       FROM cnv_estados_norm WHERE source_type='BYMA'""")
        rows_byma = cur.fetchall()
    except sqlite3.OperationalError:
        rows_byma = []          # primera corrida: aun no existe la tabla
    print(f"Filas BYMA (punta reciente): {len(rows_byma)}")

    old, new = 0, 0
    orphan_old = []
    orphan_new = []
    filas_norm = []

    # PARCHE 1c: se recorren las dos fuentes con su origen explicito. El dedup de
    # mas abajo ya prefiere CUIT (v2) sobre BYMA cuando hay conflicto, asi que la
    # precedencia queda garantizada sin tocar esa logica.
    for r, origen in ([(x, "CUIT") for x in rows] + [(x, "BYMA") for x in rows_byma]):
        ticker_orig, cik_orig, concepto, pe, tipo, valor, vc, frexp, form, escala, accn, fuente = r

        # v2 y las filas BYMA ya vienen con CUIT real en la 2a columna; la rama
        # historica 'BYMA-{TICKER}' solo aplicaba a la v1.
        ticker_from_cik = extraer_ticker_de_cik(cik_orig)

        if ticker_from_cik:
            # Fila vieja: BYMA-{TICKER}
            old += 1
            ticker = ticker_from_cik
            mapping = by_ticker.get(ticker)
            if not mapping:
                orphan_old.append((cik_orig, ticker))
                continue
            cuit = mapping["cuit"]
            ticker_canon = ticker
        else:
            # Fila nueva: cik = CUIT
            new += 1
            cuit = cik_orig
            mapping_ticker = by_cuit.get(cuit)
            if not mapping_ticker:
                orphan_new.append((cuit, ticker_orig))
                continue
            ticker_canon = mapping_ticker

        source_type = origen
        # PARCHE 2: vintage_reexpresion = period_end.
        # No se extrae del documento: es la regla NIC 29 / RT 6 -- cada cifra viene
        # expresada en moneda de poder adquisitivo de su propia fecha de cierre.
        # Verificado: cada documento de v2 aporta un unico period_end (2.145 docs).
        # Al poblarla se activa maquinaria que ya existe y estaba dormida:
        #   - la PK de cnv_estados_norm (que incluye fecha_reexpresion) deja de colapsar
        #   - el gate de consistencia de mas abajo empieza a discriminar de verdad
        #   - el `ORDER BY fecha_reexpresion DESC` de s4.get_valor pasa a ordenar algo
        frexp = pe if frexp in (None, "") else frexp
        filas_norm.append((cuit, ticker_canon, concepto, pe, tipo, valor,
                           vc if vc is not None else None,
                           frexp, form, escala, accn, fuente, source_type))

    print(f"\n  Viejas (BYMA-*): {old} -> {old - len(orphan_old)} mapeadas, {len(orphan_old)} huerfanas")
    print(f"  Nuevas (CUIT):   {new} -> {new - len(orphan_new)} mapeadas, {len(orphan_new)} huerfanas")
    print(f"  Total normalizadas: {len(filas_norm)}")

    if orphan_old:
        print(f"\n  ATENCION: BYMA huerfanas ({len(orphan_old)}):")
        for cik, ticker in orphan_old[:10]:
            print(f"     {cik} -> ticker={ticker} no esta en mapping")
    if orphan_new:
        print(f"\n  ATENCION: CUITs huerfanos ({len(orphan_new)}):")
        for cuit, nombre in orphan_new[:10]:
            print(f"     CUIT {cuit} (ticker_orig={nombre}) no esta en mapping")

    # --- Dedup ---
    grupos = defaultdict(list)
    for f in filas_norm:
        key = (f[0], f[2], f[3], f[7] or "")
        grupos[key].append(f)

    filas_dedup = []
    dup_check = 0
    divergencias = []
    div_por_entidad = defaultdict(int)
    div_byma_vs_cuit = 0

    for key, group in grupos.items():
        if len(group) == 1:
            filas_dedup.append(group[0])
        else:
            dup_check += 1
            valores = set(g[5] for g in group if g[5] is not None)
            tiene_byma = any(g[12] == "BYMA" for g in group)
            tiene_cuit = any(g[12] == "CUIT" for g in group)
            if len(valores) > 1:
                divergencias.append((key, valores, group))
                div_por_entidad[key[0]] += 1
                if tiene_byma and tiene_cuit:
                    div_byma_vs_cuit += 1
            # Preferir CUIT sobre BYMA cuando hay conflicto
            cuit_vals = [g for g in group if g[12] == "CUIT" and g[5] is not None]
            any_vals = [g for g in group if g[5] is not None]
            if cuit_vals:
                filas_dedup.append(cuit_vals[0])
            elif any_vals:
                filas_dedup.append(any_vals[0])
            else:
                filas_dedup.append(group[0])

    total_antes = len(rows) + len(rows_byma)   # PARCHE 1: ahora son dos fuentes
    total_despues = len(filas_dedup)
    pct_div = round(100 * len(divergencias) / max(dup_check, 1), 1)
    print(f"\n  Dedup: {total_antes} -> {total_despues} filas ({total_antes - total_despues} eliminadas, {dup_check} grupos con duplicados)")
    if divergencias:
        print(f"\n  ATENCION: {len(divergencias)} divergencias ({pct_div}% de {dup_check} grupos duplicados):")
        print(f"     BYMA-vs-CUIT: {div_byma_vs_cuit}, intra-CUIT: {len(divergencias) - div_byma_vs_cuit}")
        print(f"     Entidades afectadas: {len(div_por_entidad)}")
        for cuit, cnt in sorted(div_por_entidad.items(), key=lambda x: -x[1])[:5]:
            print(f"       CUIT {cuit}: {cnt} divergencias")
        print("     Top 5 ejemplos:")
        for key, vals, group in divergencias[:5]:
            fontes = set(g[12] for g in group)
            print(f"       cuit={key[0]} conc={key[1]} pe={key[2]} vals={vals} fuentes={fontes}")
        print("     (posible vintage de reexpresion distinto)")
    else:
        print("  OK: Gate consistencia: 0 divergencias en valores duplicados")

    # --- Escribir cnv_estados_norm ---
    cur.execute("DROP TABLE IF EXISTS cnv_estados_norm")
    cur.execute("""
        CREATE TABLE cnv_estados_norm (
            cuit TEXT,
            ticker TEXT,
            concepto TEXT,
            period_end TEXT,
            tipo TEXT,
            valor REAL,
            valor_comparativo REAL,
            fecha_reexpresion TEXT,
            form TEXT,
            escala INTEGER,
            accn TEXT,
            fuente TEXT DEFAULT 'cnv-aif2',
            source_type TEXT,
            PRIMARY KEY (cuit, concepto, period_end, fecha_reexpresion)
        )
    """)
    cur.executemany("INSERT OR REPLACE INTO cnv_estados_norm VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", filas_dedup)
    con.commit()
    n_filas = len(filas_dedup)
    print(f"\n  -> cnv_estados_norm: {n_filas} filas escritas")

    # --- Escribir mapa_entidades ---
    cur.execute("DROP TABLE IF EXISTS mapa_entidades")
    cur.execute("""
        CREATE TABLE mapa_entidades (
            cuit TEXT,
            ticker TEXT,
            nombre TEXT,
            grupo TEXT,
            cik_byma TEXT,
            es_primario INTEGER DEFAULT 1,
            PRIMARY KEY (cuit, ticker)
        )
    """)
    mapa_rows = []
    seen_cuit = set()
    # Primarios: iterar by_cuit (un ticker por CUIT)
    for cuit, ticker in list(by_cuit.items()):
        info = by_ticker.get(ticker, {})
        cur.execute("SELECT DISTINCT cik FROM cnv_estados WHERE fuente='cnv-aif2' AND cik=?",
                    (f"BYMA-{ticker}",))
        cik_byma = cur.fetchone()
        cik_byma_str = cik_byma[0] if cik_byma else None
        mapa_rows.append((cuit, ticker, info.get("empresa", ""), info.get("grupo", ""), cik_byma_str, 1))
        seen_cuit.add(cuit)
    # Alternativos: tickers en by_ticker que apuntan a CUITs ya vistos
    for ticker, info in sorted(by_ticker.items()):
        cuit = info["cuit"]
        if cuit in seen_cuit and ticker != by_cuit.get(cuit):
            cur.execute("SELECT DISTINCT cik FROM cnv_estados WHERE fuente='cnv-aif2' AND cik=?",
                        (f"BYMA-{ticker}",))
            cik_byma = cur.fetchone()
            cik_byma_str = cik_byma[0] if cik_byma else None
            mapa_rows.append((cuit, ticker, info.get("empresa", ""), info.get("grupo", ""), cik_byma_str, 0))

    cur.executemany("INSERT OR REPLACE INTO mapa_entidades VALUES (?,?,?,?,?,?)", mapa_rows)
    con.commit()
    n_map = len(set(r[0] for r in mapa_rows))
    n_rows = len(mapa_rows)
    print(f"  -> mapa_entidades: {n_map} CUITs distintos, {n_rows} filas")

    # --- Gate: huerfanas ---
    if orphan_old or orphan_new:
        print(f"\n  FAIL: GATE FALLADO: {len(orphan_old)} BYMA + {len(orphan_new)} CUIT huerfanos")
        print("     Revisar mapping antes de avanzar a FASE 2.")
    else:
        print(f"\n  PASS: GATE PASADO: 0 huerfanas, {n_map} entidades mapeadas, {n_filas} filas normalizadas")

    # --- Reporte de entidades ---
    cur.execute("SELECT cuit, ticker, grupo, cik_byma FROM mapa_entidades ORDER BY ticker")
    entities = cur.fetchall()
    print(f"\n  Entidades en mapa_entidades ({len(entities)}):")
    by_group = defaultdict(int)
    for e in entities:
        by_group[e[2] or "sin_grupo"] += 1
    for g, cnt in sorted(by_group.items()):
        print(f"    {g:<15} {cnt}")

    con.close()
    print("\nFASE 0 -- OK")


if __name__ == "__main__":
    build()
