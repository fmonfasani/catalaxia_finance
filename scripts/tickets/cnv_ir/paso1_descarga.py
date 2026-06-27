# -*- coding: utf-8 -*-
"""
PASO 1 — DESCARGA. Para cada empresa: descubre los EEFF en su IR, los clasifica
(anual/trimestral + año) y descarga los que matchean la config (tipo de
presentacion + periodos). Cachea en data/raw/cnv_ir/. Devuelve un MANIFIESTO.

No extrae datos: solo baja PDFs y los rotula. El paso 2 los lee.
"""
from __future__ import annotations
import re, json, requests, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "raw" / "cnv_ir"
MANIFIESTO = CACHE / "_manifiesto.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}

MESES_ES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
            "noviembre": 11, "diciembre": 12}


def clasificar_eeff(nombre, cierre_mes=12):
    """Devuelve (año, mes, tipo). tipo: 'anual' | 'trimestral'.
    Usa el cierre fiscal: si el periodo coincide con el cierre -> anual."""
    n = nombre.lower()
    # año (el mas grande presente)
    años = [int(a) for a in re.findall(r"20\d{2}", n)]
    año = max(años) if años else None
    # mes del periodo (por fecha dd.mm o 'Nro T' o mes en texto)
    mes = None
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})", n)        # 31.03.2025
    if m:
        mes = int(m.group(2))
    if mes is None:
        for nombre_mes, num in MESES_ES.items():
            if nombre_mes in n:
                mes = num; break
    # trimestre explicito: "3_T", "3T", "3°T", "1Q", "1er trim", "T3", "Q1"
    mt = (re.search(r"([1-4])\s*[°ºo._\- ]{0,3}(?:t|q|trim)(?:imestre|estral)?(?:[._\b]|$)", n)
          or re.search(r"\b(?:t|q|trim)[._\- ]{0,2}([1-4])\b", n))
    trimestre = int(mt.group(1)) if mt else None
    if trimestre and mes is None:
        mes = (cierre_mes - 3 * (4 - trimestre) - 1) % 12 + 1   # aprox
    # tipo: anual si el mes coincide con el cierre, o si dice "anual"/"ejercicio" sin trimestre
    if mes == cierre_mes or "anual" in n or (trimestre == 4):
        tipo = "anual"
    elif trimestre or (mes and mes != cierre_mes):
        tipo = "trimestral"
    else:
        tipo = "anual"   # por defecto (ejercicio completo)
    return año, mes, tipo


def _pasa_filtro(año, tipo, cfg):
    if cfg.tipo_presentacion != "ambos" and tipo != cfg.tipo_presentacion:
        return False
    if not cfg.solo_ultimo and año is not None:
        if cfg.año_desde and año < cfg.año_desde:
            return False
        if cfg.año_hasta and año > cfg.año_hasta:
            return False
    return True


def _descargar(url, ticker):
    CACHE.mkdir(parents=True, exist_ok=True)
    nombre = re.sub(r"[^\w.-]", "_", url.rsplit("/", 1)[-1])[:70]
    dest = CACHE / f"{ticker}__{nombre}"
    if dest.suffix.lower() != ".pdf":
        dest = dest.with_suffix(".pdf")
    if dest.exists() and dest.stat().st_size > 10000:
        return dest
    try:
        data = requests.get(url, headers=UA, timeout=45, verify=False).content
        if len(data) < 10000:
            return None
        dest.write_bytes(data)
        return dest
    except Exception:
        return None


def descargar(cfg, catalogo=None):
    from discovery import descubrir_eeff
    if catalogo is None:
        from catalogo_ir import CATALOGO as catalogo
    manifiesto = []
    for tk in cfg.empresas:
        info = catalogo.get(tk)
        cierre = info[2] if info else 12
        pdfs = descubrir_eeff(tk, catalogo)
        if not pdfs:
            print(f"  {tk:<7} SIN EEFF (IR no responde / sin link)")
            continue
        # clasificar y filtrar
        clasificados = []
        for url in pdfs:
            año, mes, tipo = clasificar_eeff(url.rsplit("/", 1)[-1], cierre)
            if _pasa_filtro(año, tipo, cfg):
                clasificados.append((url, año, mes, tipo))
        if cfg.solo_ultimo:
            clasificados = clasificados[:1]      # discovery ya viene ordenado por recencia
        bajados = 0
        for url, año, mes, tipo in clasificados:
            dest = _descargar(url, tk)
            if dest:
                manifiesto.append({"ticker": tk, "url": url, "path": str(dest),
                                   "año": año, "mes": mes, "tipo": tipo})
                bajados += 1
        print(f"  {tk:<7} {len(pdfs)} EEFF en IR, {len(clasificados)} pasan filtro, {bajados} bajados")
    CACHE.mkdir(parents=True, exist_ok=True)
    MANIFIESTO.write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    print(f"\n  Manifiesto: {len(manifiesto)} PDFs -> {MANIFIESTO}")
    return manifiesto


if __name__ == "__main__":
    from config import pedir_config
    cfg = pedir_config()
    if cfg:
        descargar(cfg)
