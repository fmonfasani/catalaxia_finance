# -*- coding: utf-8 -*-
"""
_caducidad -- que rebajar, segun lo que la empresa PRESENTO
============================================================
EL PROBLEMA QUE RESUELVE
  construir_base.py saltea toda empresa que ya tenga datos:

      ya = {r[0] for r in con.execute(
          "SELECT cik FROM empresas WHERE fecha_facts IS NOT NULL")}
      ...
      stats["skip"] += 1; continue

  El cache es POR EMPRESA, no por fecha: una vez bajada, nunca se rebaja. Todas
  se bajaron el 2026-06-26 y quedaron congeladas ahi.

  El daño depende del formulario. Un 10-Q trimestral deja un atraso maximo de
  tres meses; un 20-F ANUAL deja hasta DOCE. Verificado contra EDGAR el
  2026-08-21:

      BBAR  ultimo 20-F 2026-04-09    tenemos hasta 2024-12-31
      LOMA  ultimo 20-F 2026-04-28    tenemos hasta 2024-12-31
      SUPV  ultimo 20-F 2026-04-08    tenemos hasta 2024-12-31

  Los tres presentaron el ejercicio 2025 en abril de 2026. Bajamos en junio y
  aun asi tenemos 2024: el cache los salteo desde una descarga anterior.

LA PREGUNTA CORRECTA
  No es "ya la baje?" sino "la baje DESPUES de que presentara algo nuevo?".

  EDGAR publica el indice de presentaciones de cada emisor y ya lo tenemos
  bajado: 8.020 archivos en data/raw/submissions/, que cubren 552 de los 609
  CIK. La comprobacion sale gratis sobre lo que hay en disco.

QUE FORMULARIOS CUENTAN
  Solo los que traen estados contables. Un Form 4 -- compraventa de un
  directivo -- se presenta todas las semanas y no aporta un solo numero
  financiero: contarlo haria que TODA empresa figure siempre desactualizada, y
  el aviso dejaria de significar algo.

DOS NIVELES, Y CONVIENE USAR LOS DOS
  local   lee el indice cacheado. Instantaneo y sin red. Detecta a los que
          estaban atrasados ya en la ultima bajada del indice.
  remoto  vuelve a pedir el indice. Una consulta chica por empresa; detecta lo
          presentado desde entonces.

  El local se corre siempre; el remoto solo sobre los que el local no descarta,
  que es lo que lo hace barato.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

# Formularios que traen estados contables. El resto se ignora.
FORMS_CONTABLES = {
    "10-K", "10-Q", "10-K/A", "10-Q/A",          # emisores de EE.UU.
    "20-F", "20-F/A", "40-F",                     # emisores extranjeros, anual
    "6-K", "6-K/A",                               # extranjeros, intermedios
}

RAW_SUBS = "data/raw/submissions"


def es_cik_sec(cik):
    """True si es un CIK real de la SEC.

    `facts` guarda tambien filas con clave ficticia -- 'BYMA-A3' y similares --
    para papeles que solo cotizan en Buenos Aires. No son registrantes de la SEC
    y preguntar por su indice de presentaciones no tiene sentido.
    """
    return str(cik or "").strip().isdigit()


def _ruta(root, cik):
    if not es_cik_sec(cik):
        return None
    return Path(root) / RAW_SUBS / f"CIK{int(str(cik).lstrip('0') or 0):010d}.json"


def ultima_presentacion(root, cik, forms=None):
    """(fecha, form, accession, reportDate) de la ultima presentacion contable.

    Lee el indice CACHEADO. Devuelve (None,)*4 si no esta bajado.
    """
    forms = forms or FORMS_CONTABLES
    p = _ruta(root, cik)
    if p is None or not p.exists():
        return None, None, None, None
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return None, None, None, None
    r = d.get("filings", {}).get("recent", {})
    mejor = (None, None, None, None)
    for form, fd, acc, rd in zip(r.get("form", []), r.get("filingDate", []),
                                 r.get("accessionNumber", []),
                                 r.get("reportDate", [])):
        if form not in forms:
            continue
        if mejor[0] is None or fd > mejor[0]:
            mejor = (fd, form, acc, rd)
    return mejor


def edad_indice(root, cik):
    """Fecha de la presentacion mas nueva del indice, sea del tipo que sea.

    Sirve para saber cuan viejo es el propio indice: si su ultima entrada es de
    hace meses, el indice esta desactualizado y su respuesta no es concluyente.
    """
    p = _ruta(root, cik)
    if p is None or not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return None
    fd = d.get("filings", {}).get("recent", {}).get("filingDate", [])
    return max(fd) if fd else None


def hay_que_rebajar(root, cik, nuestro_ultimo_reporte):
    """(True|False|None, motivo).

    None cuando no se puede decidir -- indice ausente o sin presentaciones
    contables. No se asume "esta al dia": un dato ausente se declara, no se
    interpreta a favor.
    """
    if not es_cik_sec(cik):
        return False, "no es un registrante de la SEC"
    fd, form, acc, rd = ultima_presentacion(root, cik)
    if fd is None:
        return None, "sin indice de presentaciones"
    if not rd:
        return None, f"presentacion {form} sin reportDate"
    if not nuestro_ultimo_reporte:
        return True, f"no tenemos nada; hay {form} de {fd}"
    if rd > nuestro_ultimo_reporte:
        return True, (f"{form} del {fd} cubre hasta {rd}; "
                      f"tenemos hasta {nuestro_ultimo_reporte}")
    return False, f"al dia hasta {nuestro_ultimo_reporte}"
