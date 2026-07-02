import argparse
import csv
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / 'debug'
DATOS = ROOT / 'datos'
AUTOCOMPLETE = DEBUG / 'autocomplete.json'
OUTPUT_DIR = DATOS / 'html_descargados'
MANIFEST = OUTPUT_DIR / 'manifest.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0'
}


def slugify(text: str, maxlen: int = 80) -> str:
    if not text:
        return 'empresa'
    text = re.sub(r'[\s]+', '_', text.strip())
    text = re.sub(r'[^A-Za-z0-9_\-]', '', text)
    text = re.sub(r'_+', '_', text)
    return text[:maxlen].strip('_-') or 'empresa'


def matches_only_filter(item, only_value: str) -> bool:
    if not only_value:
        return True
    descripcion = str(item.get('descripcion', '')).lower()
    cuit = str(item.get('cuit', '')).lower()
    only_value = only_value.lower()
    return only_value in descripcion or only_value in cuit


def load_autocomplete():
    if not AUTOCOMPLETE.exists():
        raise FileNotFoundError(
            f'No se encontró {AUTOCOMPLETE}. Primero ejecute 01_auditoria_autocomplete.py'
        )

    with AUTOCOMPLETE.open('r', encoding='utf8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError('autocomplete.json debe contener una lista de objetos JSON')

    return data


def descargar_empresa(item, output_dir: Path):
    cuit = str(item.get('cuit', '')).strip()
    descripcion = str(item.get('descripcion', ''))
    if not cuit:
        raise ValueError('Empresa sin CUIT en autocomplete.json')

    safe_name = slugify(descripcion)
    filename = output_dir / f'{cuit}_{safe_name}.html'
    url = f'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}'

    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()

    filename.write_text(r.text, encoding='utf8')

    return {
        'cuit': cuit,
        'descripcion': descripcion,
        'url_empresa': url,
        'filename': filename.name,
        'bytes': len(r.text),
        'status': 'ok',
    }


def guardar_manifest(resultados, manifest_path: Path):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'cuit',
                'descripcion',
                'url_empresa',
                'filename',
                'bytes',
                'status',
            ],
        )
        writer.writeheader()
        writer.writerows(resultados)


def load_manifest_rows(manifest_path: Path):
    if not manifest_path.exists():
        return {}, set()
    with manifest_path.open('r', encoding='utf8', newline='') as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]
        rows_by_cuit = {row['cuit']: row for row in rows}
        ok_cuits = {row['cuit'] for row in rows if row.get('status') == 'ok'}
        return rows_by_cuit, ok_cuits


def main():
    parser = argparse.ArgumentParser(
        description='Descarga las páginas de empresa CNV para todas las entradas de autocomplete.json'
    )
    parser.add_argument(
        '--max',
        type=int,
        default=0,
        help='Cantidad máxima de empresas a descargar. 0 = todas',
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Segundos de espera entre requests',
    )
    parser.add_argument(
        '--only',
        type=str,
        default='',
        help='Filtra por nombre o CUIT de la empresa',
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Reanuda descargas usando el manifest existente',
    )
    args = parser.parse_args()

    empresas = load_autocomplete()
    if args.only:
        empresas = [e for e in empresas if matches_only_filter(e, args.only)]

    resultados = []
    resultados_by_cuit = {}
    resume_ok_cuits = set()
    if args.resume:
        prev_rows_by_cuit, resume_ok_cuits = load_manifest_rows(MANIFEST)
        resultados_by_cuit.update(prev_rows_by_cuit)
        print(f'Resumir descargas: saltando {len(resume_ok_cuits)} empresas ya descargadas')

    empresas = [e for e in empresas if str(e.get('cuit', '')) not in resume_ok_cuits]

    if args.max > 0:
        empresas = empresas[: args.max]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(empresas)
    nuevos_resultados = []

    print(f'Descargando {total} empresas desde {AUTOCOMPLETE}')
    for i, item in enumerate(empresas, start=1):
        descripcion = item.get('descripcion', '')
        cuit = item.get('cuit', '')
        print(f'[{i}/{total}] {cuit} - {descripcion}')
        try:
            resultado = descargar_empresa(item, OUTPUT_DIR)
            nuevos_resultados.append(resultado)
            resultados_by_cuit[cuit] = resultado
            print(f'    OK -> {resultado["filename"]} ({resultado["bytes"]} bytes)')
        except Exception as exc:
            print(f'    ERROR -> {exc}')
            error_row = {
                'cuit': cuit,
                'descripcion': descripcion,
                'url_empresa': f'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{cuit}',
                'filename': '',
                'bytes': 0,
                'status': f'error: {exc}',
            }
            nuevos_resultados.append(error_row)
            resultados_by_cuit[cuit] = error_row
        time.sleep(args.delay)

    resultados = list(resultados_by_cuit.values())
    guardar_manifest(resultados, MANIFEST)
    new_ok = sum(1 for r in nuevos_resultados if r['status'] == 'ok')
    print(f'\nDescarga completada: {new_ok}/{total} archivos descargados en esta ejecución')
    print(f'Manifest guardado en: {MANIFEST}')
    print(f'HTML guardados en: {OUTPUT_DIR}')


if __name__ == '__main__':
    main()
