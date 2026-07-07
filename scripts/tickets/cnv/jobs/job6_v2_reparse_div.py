#!/usr/bin/env python3
from __future__ import annotations
import re, csv, sqlite3, html as html_mod
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir())
DB = ROOT / 'data' / 'screener.db'
WHITELIST = BASE / 'datos' / 'whitelist_div.csv'
SUBSET = BASE / 'datos' / 'empresas_subset.csv'
HTML_DIR = BASE / 'eeff' / 'div_html'

RX_PRESENTATION = re.compile(r"var presentation\s*=\s*'(.*?)';", re.DOTALL)
RX_FILA = re.compile(r'<fila[^>]*>(.*?)</fila>', re.DOTALL)


def extract_prop(xml_section: str, prop_id: str) -> str:
    m = re.search(
        r'<propiedad\s+id="' + re.escape(prop_id) + r'"[^>]*>([^<]*)</propiedad>',
        xml_section,
    )
    return m.group(1) if m else ''


def extract_prop_label(xml_section: str, prop_id: str) -> tuple[str, str]:
    m = re.search(
        r'<propiedad\s+id="' + re.escape(prop_id) + r'"([^>]*)>(?:([^<]*)</propiedad>)?',
        xml_section,
    )
    if m:
        attrs = m.group(1)
        val = m.group(2) or ''
        lb = re.search(r'etiqueta="([^"]*)"', attrs)
        return val, lb.group(1) if lb else ''
    return '', ''


def parse_iso_date(s: str) -> str:
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    return m.group(1) if m else s


def parse_one_html(path: Path) -> list[dict] | None:
    try:
        raw = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None
    m = RX_PRESENTATION.search(raw)
    if not m:
        return None
    xml = html_mod.unescape(m.group(1))

    fecha_resolucion = ''
    dg = re.search(
        r'<entidad[^>]*clave="DatosGenerales"[^>]*>(.*?)</entidad>', xml, re.DOTALL
    )
    if dg:
        fecha_resolucion = parse_iso_date(extract_prop(dg.group(1), 'FechaDeResolucion'))

    de = re.search(
        r'<entidad[^>]*clave="Dividendos"[^>]*>(.*?)</entidad>', xml, re.DOTALL
    )
    if not de:
        return []
    filas = RX_FILA.findall(de.group(1))
    if not filas:
        return []

    results = []
    for fx in filas:
        monto = extract_prop(fx, 'MontoDelDividendo')
        if not monto:
            continue
        fecha_pago = parse_iso_date(extract_prop(fx, 'FechaEnQueSePoneADisposicion'))
        _, moneda_lb = extract_prop_label(fx, 'MonedaDelDividendo')
        _, tipo_lb = extract_prop_label(fx, 'TipoDeDividendo')
        results.append(
            dict(
                monto=monto,
                fecha=fecha_pago or fecha_resolucion,
                moneda=moneda_lb,
                tipo=tipo_lb,
            )
        )
    return results


def main():
    subset_cuits = set()
    with open(SUBSET, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            c = r.get('cuit', '').strip()
            if c:
                subset_cuits.add(c)
    print(f'CUITs in subset: {len(subset_cuits)}')

    rows = []
    with open(WHITELIST, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            cuit = r.get('cuit', '').strip()
            clase = r.get('clase', '').strip()
            guid = r.get('guid', '').strip()
            if (
                cuit in subset_cuits
                and clase == 'dividendo'
                and (HTML_DIR / f'{guid}.html').is_file()
            ):
                rows.append(r)
    total = len(rows)
    print(f'Total dividend filings in subset: {total}')

    parsed_rows = []
    fail = 0
    no_monto = 0
    for r in rows:
        guid = r['guid'].strip()
        divs = parse_one_html(HTML_DIR / f'{guid}.html')
        if divs is None:
            fail += 1
            continue
        if not divs:
            no_monto += 1
            continue
        monto_total = 0.0
        fecha = ''
        for d in divs:
            try:
                monto_total += float(d['monto'])
            except ValueError:
                pass
            if not fecha and d['fecha']:
                fecha = d['fecha']
        parsed_rows.append(
            dict(
                cuit=r['cuit'].strip(),
                empresa=r.get('empresa', '').strip(),
                guid=guid,
                clase='dividendo',
                formulario='Pago de Dividendos',
                fecha_candidata=fecha,
                monto_candidato=str(monto_total) if monto_total else '',
                por_accion='',
                snippet='',
                fuente='cnv-aif2-v2',
            )
        )

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS cnv_dividendos;
        CREATE TABLE cnv_dividendos (
            cuit TEXT,
            empresa TEXT,
            guid TEXT PRIMARY KEY,
            clase TEXT,
            formulario TEXT,
            fecha_candidata TEXT,
            monto_candidato TEXT,
            por_accion TEXT,
            snippet TEXT,
            fuente TEXT DEFAULT 'cnv-aif2'
        );
    """
    )
    inserted = 0
    for d in parsed_rows:
        try:
            cur.execute(
                """INSERT OR REPLACE INTO cnv_dividendos
                   (cuit, empresa, guid, clase, formulario,
                    fecha_candidata, monto_candidato, por_accion,
                    snippet, fuente)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    d['cuit'],
                    d['empresa'],
                    d['guid'],
                    d['clase'],
                    d['formulario'],
                    d['fecha_candidata'],
                    d['monto_candidato'],
                    d['por_accion'],
                    d['snippet'],
                    d['fuente'],
                ),
            )
            inserted += 1
        except Exception as e:
            print(f'  ! DB error {d["guid"]}: {e}')
    con.commit()
    con.close()

    montos = []
    for d in parsed_rows:
        if d['monto_candidato']:
            try:
                montos.append(float(d['monto_candidato']))
            except ValueError:
                pass
    entities = set(d['cuit'] for d in parsed_rows)

    print(f'Successfully parsed:  {len(parsed_rows)}')
    print(f'Failed to parse:      {fail}')
    print(f'No monto found:       {no_monto}')
    if montos:
        print(f'Total amount range:   {min(montos):,.2f}  –  {max(montos):,.2f}')
        print(f'Sum of all dividends: {sum(montos):,.2f}')
    print(f'Unique entities:      {len(entities)}')
    print(f'Rows inserted:        {inserted}')
    print('Done.')


if __name__ == '__main__':
    main()
