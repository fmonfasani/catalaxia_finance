# -*- coding: utf-8 -*-
"""
PASO 2 — EXTRACCION. Lee el manifiesto del paso 1, abre cada PDF, detecta si es
TEXTO o IMAGEN (escaneado), aplica el filtro de tipo_pdf de la config, y extrae
los line items canonicos (texto directo o via OCR). Devuelve los registros.
"""
from __future__ import annotations
import json, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[3]
MANIFIESTO = ROOT / "data" / "raw" / "cnv_ir" / "_manifiesto.json"


def es_texto(path, minimo=3000):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        txt = " ".join((p.extract_text() or "") for p in pdf.pages[:25])
    return len(txt.strip()) >= minimo, txt


def extraer(cfg, manifiesto=None):
    from parser_eeff import parsear_texto, normalizar
    if manifiesto is None:
        manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    registros = []
    for item in manifiesto:
        path = item["path"]
        try:
            hay_texto, txt = es_texto(path)
        except Exception as e:
            print(f"  {item['ticker']:<7} error abriendo PDF: {str(e)[:30]}"); continue
        # clasificar metodo
        if hay_texto:
            metodo = "texto"
        else:
            metodo = "imagen"
        # filtro tipo_pdf
        if cfg.tipo_pdf == "texto" and metodo != "texto":
            print(f"  {item['ticker']:<7} [skip] es imagen, filtro=solo texto"); continue
        if cfg.tipo_pdf == "imagen" and metodo != "imagen":
            print(f"  {item['ticker']:<7} [skip] es texto, filtro=solo imagen"); continue
        # extraer
        if metodo == "imagen":
            from ocr import ocr_pdf, backend_disponible
            if not backend_disponible():
                print(f"  {item['ticker']:<7} [imagen] sin OCR instalado -> pendiente")
                registros.append({**item, "metodo": "imagen_sin_ocr", "datos": {}}); continue
            txt = ocr_pdf(path) or ""
            metodo = "ocr"
        datos = parsear_texto(normalizar(txt))
        registros.append({**item, "metodo": metodo, "datos": datos})
        print(f"  {item['ticker']:<7} {metodo:<6} items={len(datos)}")
    return registros


if __name__ == "__main__":
    from config import Config
    regs = extraer(Config(tipo_pdf="cualquiera"))
    print(f"\nExtraidos: {len(regs)} registros")
