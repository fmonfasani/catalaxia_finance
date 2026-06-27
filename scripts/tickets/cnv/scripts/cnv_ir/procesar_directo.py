# -*- coding: utf-8 -*-
"""
Procesa un EEFF desde su URL de PDF DIRECTA (cuando el IR carga por JavaScript y
el discovery no lo encuentra). Vos copiás la URL del PDF desde el navegador y este
script lo baja, extrae, valida por identidades y (opcional) carga a la base.

Como obtener la URL directa del PDF:
  1. Abri el sitio de IR de la empresa en el navegador.
  2. Entra a "Estados Contables" / "Informacion financiera".
  3. Clic derecho sobre el link del EEFF -> "Copiar direccion del enlace".

Uso:
  python procesar_directo.py LEDE "https://....../estado-contable.pdf"
  python procesar_directo.py LEDE "https://....pdf" --cargar
"""
from __future__ import annotations
import sys, re, requests, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'data').is_dir())
CACHE = ROOT / "data" / "raw" / "cnv_ir"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}


def bajar(url, ticker):
    CACHE.mkdir(parents=True, exist_ok=True)
    nombre = re.sub(r"[^\w.-]", "_", url.rsplit("/", 1)[-1].split("?")[0])[:60] or "eeff"
    dest = CACHE / f"{ticker}__directo__{nombre}"
    if dest.suffix.lower() != ".pdf":
        dest = dest.with_suffix(".pdf")
    print(f"Bajando {url[:70]}...")
    data = requests.get(url, headers=H, timeout=60, verify=False).content
    if len(data) < 5000:
        print(f"  PDF muy chico ({len(data)} bytes) -> revisa la URL"); return None
    dest.write_bytes(data)
    print(f"  guardado: {dest.name} ({len(data)//1024} KB)")
    return dest


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cargar = "--cargar" in sys.argv
    if len(args) < 2:
        print('uso: python procesar_directo.py TICKER "URL_DEL_PDF" [--cargar]'); return
    ticker, url = args[0].upper(), args[1]
    dest = bajar(url, ticker)
    if not dest:
        return
    from parser_eeff import procesar_pdf
    r = procesar_pdf(str(dest))
    print(f"\nMetodo: {r['metodo']} | items: {len(r['datos'])} | identidad OK: {r['ok']}")
    for k, v in r["datos"].items():
        print(f"  {k:<18} {v:>22,.0f}")
    for nombre, err in r["checks"].items():
        if err is not None:
            print(f"  [{nombre}] error {err:.2f}%  [{'OK' if err < 1 else 'REVISAR'}]")
    if r["datos"]:
        print("\nRatios:")
        for k, v in r["ratios"].items():
            if v is not None:
                es_pct = k.startswith("m") or k in ("roe", "roa")
                print(f"  {k:<16} {(f'{v*100:.1f}%' if es_pct else f'{v:.2f}x')}")
    if cargar and r["ok"]:
        from paso4_normalizacion import _period_end
        from paso5_publicacion import publicar
        # periodo desde el nombre
        m = re.search(r"20\d{2}", dest.name); año = int(m.group()) if m else None
        pe = _period_end(año, 12) if año else None
        publicar([{"ticker": ticker, "datos": r["datos"], "period_end": pe, "tipo": "Q",
                   "fecha_reexpresion": pe, "moneda": "ARS", "esquema": "nic29", "fuente": "cnv-ir"}])
    elif cargar:
        print("\n  NO cargado: la identidad no cierra (revisar etiquetas).")


if __name__ == "__main__":
    main()
