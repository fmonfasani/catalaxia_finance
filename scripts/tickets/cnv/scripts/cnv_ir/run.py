# -*- coding: utf-8 -*-
"""
ORQUESTADOR del pipeline CNV-IR. Corre el menu interactivo y ejecuta los 5 pasos:
  1. descarga   2. extraccion   3. validacion   4. normalizacion   5. publicacion

Uso:
  python run.py                 # menu interactivo (pregunta todo) + corre los pasos
  python run.py --rapido        # config por defecto (todas, ultimo, cualquier PDF)

Cada paso se puede correr suelto tambien (python paso1_descarga.py, etc.).
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import pedir_config, Config
from paso1_descarga import descargar
from paso2_extraccion import extraer
from paso3_validacion import validar
from paso4_normalizacion import normalizar
from paso5_publicacion import publicar


def correr(cfg):
    print("\n[1/5] DESCARGA DE PDFs"); print("-" * 40)
    manifiesto = descargar(cfg)
    if not manifiesto:
        print("\nNo se descargo ningun EEFF. (Desde Argentina deberian responder los IR.)")
        return
    print("\n[2/5] EXTRACCION DE DATOS"); print("-" * 40)
    registros = extraer(cfg, manifiesto)
    print("\n[3/5] VALIDACION (identidades contables)"); print("-" * 40)
    validados = validar(registros)
    print("\n[4/5] NORMALIZACION"); print("-" * 40)
    normalizados = normalizar(validados)
    if cfg.cargar_bd:
        print("\n[5/5] PUBLICACION A LA BASE"); print("-" * 40)
        publicar(normalizados)
    else:
        print("\n[5/5] (saltado: cargar_bd=False)")
    # resumen
    ok = sum(1 for v in validados if v["estado_val"] == "ok")
    esc = sum(1 for v in validados if v.get("metodo") == "imagen_sin_ocr")
    print("\n" + "=" * 48)
    print(f"  RESUMEN: {len(manifiesto)} PDFs | {ok} validados OK | {esc} escaneados sin OCR")
    print("=" * 48)


if __name__ == "__main__":
    if "--rapido" in sys.argv:
        from catalogo_ir import CATALOGO
        cfg = Config(empresas=list(CATALOGO))
        print("Modo rapido:", cfg.resumen())
    else:
        cfg = pedir_config()
    if cfg:
        correr(cfg)
