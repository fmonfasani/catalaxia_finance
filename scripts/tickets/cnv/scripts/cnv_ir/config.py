# -*- coding: utf-8 -*-
"""
Configuracion del pipeline: menu INTERACTIVO que pregunta antes de descargar:
  1. Que empresas:   un papel / un sector / todas
  2. Tipo de presentacion:  anual / trimestral / ambos
  3. Periodos:  ultimo / desde año X hasta año Y
  4. Tipo de PDF:  solo texto / solo imagen (OCR) / cualquiera

Se puede usar interactivo (pedir_config) o por codigo (Config(...)).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from catalogo_ir import CATALOGO, SECTORES, por_sector


@dataclass
class Config:
    empresas: list = field(default_factory=list)     # tickers a procesar
    tipo_presentacion: str = "ambos"                  # anual | trimestral | ambos
    solo_ultimo: bool = True                          # solo la ultima presentacion
    año_desde: int | None = None
    año_hasta: int | None = None
    tipo_pdf: str = "cualquiera"                       # texto | imagen | cualquiera
    cargar_bd: bool = True

    def resumen(self):
        emp = ("TODAS (%d)" % len(self.empresas)) if len(self.empresas) > 5 else ", ".join(self.empresas)
        per = "ultimo" if self.solo_ultimo else f"{self.año_desde}-{self.año_hasta}"
        return (f"empresas={emp} | presentacion={self.tipo_presentacion} | "
                f"periodos={per} | pdf={self.tipo_pdf} | cargar_bd={self.cargar_bd}")


def _preguntar(prompt, opciones, default):
    print(prompt)
    for k, v in opciones.items():
        print(f"   {k}) {v}")
    r = input(f"   Opcion [{default}]: ").strip() or default
    return r


def pedir_config():
    print("\n" + "=" * 56)
    print("  CONFIGURACION DEL PIPELINE CNV-IR (EEFF argentinos)")
    print("=" * 56)

    # 1. empresas
    r = _preguntar("\n1) Que empresas procesar?",
                   {"1": "Todas las BYMA-only (56)", "2": "Un sector",
                    "3": "Un papel puntual"}, "1")
    if r == "2":
        print("   Sectores: " + ", ".join(SECTORES))
        sec = input("   Sector: ").strip().lower()
        empresas = por_sector(sec)
        if not empresas:
            print(f"   (sector '{sec}' sin empresas; uso todas)"); empresas = list(CATALOGO)
    elif r == "3":
        tk = input("   Ticker (ej. ALUA): ").strip().upper()
        empresas = [tk] if tk in CATALOGO else list(CATALOGO)
    else:
        empresas = list(CATALOGO)

    # 2. tipo de presentacion
    r = _preguntar("\n2) Tipo de presentacion?",
                   {"1": "Ambos", "2": "Solo anual", "3": "Solo trimestral"}, "1")
    tipo_pres = {"1": "ambos", "2": "anual", "3": "trimestral"}[r]

    # 3. periodos
    r = _preguntar("\n3) Que periodos?",
                   {"1": "Solo la ultima presentacion", "2": "Rango de años (desde-hasta)"}, "1")
    solo_ultimo, desde, hasta = True, None, None
    if r == "2":
        solo_ultimo = False
        try:
            desde = int(input("   Desde año (ej. 2022): ").strip())
            hasta = int(input("   Hasta año (ej. 2026): ").strip())
        except ValueError:
            print("   (años invalidos; uso ultimo)"); solo_ultimo = True

    # 4. tipo de PDF
    r = _preguntar("\n4) Que PDFs procesar?",
                   {"1": "Cualquiera (texto + imagen con OCR)",
                    "2": "Solo texto (rapido, sin OCR)",
                    "3": "Solo imagen (los escaneados, con OCR)"}, "1")
    tipo_pdf = {"1": "cualquiera", "2": "texto", "3": "imagen"}[r]

    # 5. cargar a BD
    r = _preguntar("\n5) Cargar a la base de datos?",
                   {"1": "Si (solo lo que valida)", "2": "No (solo reporte)"}, "1")
    cargar = (r == "1")

    cfg = Config(empresas=empresas, tipo_presentacion=tipo_pres, solo_ultimo=solo_ultimo,
                 año_desde=desde, año_hasta=hasta, tipo_pdf=tipo_pdf, cargar_bd=cargar)
    print("\n" + "-" * 56)
    print("  CONFIG:", cfg.resumen())
    print("-" * 56)
    if input("  Confirmar y arrancar? [s/N]: ").strip().lower() not in ("s", "si", "y"):
        print("  Cancelado."); return None
    return cfg


if __name__ == "__main__":
    cfg = pedir_config()
    print("\nConfig final:", cfg.resumen() if cfg else "cancelado")
