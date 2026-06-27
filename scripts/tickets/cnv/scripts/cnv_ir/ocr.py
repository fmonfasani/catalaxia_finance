# -*- coding: utf-8 -*-
"""
OCR para EEFF escaneados (imagen). Rasteriza con PyMuPDF (fitz) y OCR-ea con el
primer backend disponible: pytesseract (necesita binario tesseract) o easyocr.

Degradacion elegante: si no hay backend, devuelve None (el caller marca el PDF
como 'escaneado, requiere OCR'). En una maquina con tesseract instalado:
  pip install pytesseract        +  instalar Tesseract-OCR (con idioma 'spa')
o:
  pip install easyocr
"""
from __future__ import annotations
import warnings
warnings.filterwarnings("ignore")

_BACKEND = None


def backend_disponible():
    """Devuelve 'pytesseract' | 'easyocr' | None (cacheado)."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND or None
    import shutil
    try:
        import pytesseract  # noqa
        if shutil.which("tesseract"):
            _BACKEND = "pytesseract"; return _BACKEND
    except ImportError:
        pass
    try:
        import easyocr  # noqa
        _BACKEND = "easyocr"; return _BACKEND
    except ImportError:
        pass
    _BACKEND = ""
    return None


def _paginas_a_imagenes(path, dpi=200, max_paginas=40):
    """PDF -> lista de imagenes PIL (via fitz). Solo paginas con poco texto
    (las de estados suelen ser tablas escaneadas)."""
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    imgs = []
    doc = fitz.open(path)
    for i, page in enumerate(doc):
        if i >= max_paginas:
            break
        pix = page.get_pixmap(dpi=dpi)
        imgs.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    doc.close()
    return imgs


def ocr_pdf(path, idioma="spa"):
    """Devuelve el texto OCR del PDF, o None si no hay backend."""
    bk = backend_disponible()
    if not bk:
        return None
    imgs = _paginas_a_imagenes(path)
    textos = []
    if bk == "pytesseract":
        import pytesseract
        for im in imgs:
            textos.append(pytesseract.image_to_string(im, lang=idioma))
    elif bk == "easyocr":
        import easyocr
        reader = easyocr.Reader(["es"], gpu=False)
        import numpy as np
        for im in imgs:
            res = reader.readtext(np.array(im), detail=0, paragraph=True)
            textos.append(" ".join(res))
    return " ".join(textos)


if __name__ == "__main__":
    import sys
    bk = backend_disponible()
    print(f"Backend OCR: {bk or 'NINGUNO (instalar pytesseract+tesseract o easyocr)'}")
    if bk and len(sys.argv) > 1:
        t = ocr_pdf(sys.argv[1])
        print(f"Texto OCR extraido: {len(t) if t else 0} chars")
