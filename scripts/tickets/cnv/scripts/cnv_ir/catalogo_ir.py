# -*- coding: utf-8 -*-
"""
Catalogo CURADO de los 56 papeles BYMA-only -> nombre, SECTOR, cierre fiscal y
URLs de Relacion con Inversores (donde publican los EEFF).

Campos por ticker: (nombre, sector, cierre_mes, [urls_ir])
  sector: para filtrar (energia, gas, bancos, financiero, real_estate,
          materiales, industrial, agro, consumo, medios, salud, holding, infra)
  cierre_mes: mes de cierre de ejercicio (12=diciembre, 6=junio, etc.)
  urls_ir: [] si no se conoce -> el discovery intenta fallback (bolsar/buscador)

NOTA: las URLs con [] hay que completarlas (facil desde Argentina). El que tenga
la URL correcta, agregarla aca. La identidad contable valida si el EEFF es el bueno.
"""

CATALOGO = {
    # --- materiales / industria pesada ---
    "ALUA":  ("Aluar", "materiales", 6, ["https://www.aluar.com.ar/inversores"]),
    "TXAR":  ("Ternium Argentina", "materiales", 12, ["https://ar.ternium.com/es/inversores"]),
    "HARG":  ("Holcim Argentina", "materiales", 12, ["https://www.holcim.com.ar/inversionistas"]),
    "CELU":  ("Celulosa Argentina", "materiales", 5, ["https://www.celulosaargentina.com.ar/inversores"]),
    "CARC":  ("Carboclor", "materiales", 12, ["https://www.carboclor.com.ar/"]),
    "RIGO":  ("Rigolleau", "materiales", 12, ["https://www.rigolleau.com.ar/inversores"]),
    "FIPL":  ("Fiplasto", "materiales", 6, []),
    # --- industrial / bienes durables ---
    "MIRG":  ("Mirgor", "industrial", 12, ["https://www.mirgor.com.ar/inversores", "https://ri.mirgor.com.ar/"]),
    "FERR":  ("Ferrum", "industrial", 6, ["https://www.ferrum.com/inversores"]),
    "LONG":  ("Longvie", "industrial", 12, ["https://www.longvie.com/inversores"]),
    "DOME":  ("Domec", "industrial", 12, []),
    "AGRO":  ("Agrometal", "industrial", 12, ["https://www.agrometal.com.ar/inversores"]),
    "INTR":  ("Introductora de Bs As", "industrial", 12, []),
    "REGE":  ("Garcia Reguera", "industrial", 12, []),
    "POLL":  ("Polledo", "industrial", 12, []),
    # --- agro / alimentos ---
    "LEDE":  ("Ledesma", "agro", 5, ["https://www.ledesma.com.ar/inversores"]),
    "SAMI":  ("San Miguel", "agro", 12, ["https://www.sanmiguelglobal.com/inversores"]),
    "MOLA":  ("Molinos Agro", "agro", 6, ["https://www.molinosagro.com.ar/inversores"]),
    "INVJ":  ("Inversora Juramento", "agro", 6, ["https://www.juramento.com.ar/inversores"]),
    "SEMI":  ("Molinos Juan Semino", "agro", 9, []),
    # --- consumo / retail ---
    "MOLI":  ("Molinos Rio de la Plata", "consumo", 12, ["https://www.molinos.com.ar/inversores"]),
    "MORI":  ("Morixe", "consumo", 6, ["https://www.morixe.com.ar/inversores"]),
    "HAVA":  ("Havanna", "consumo", 12, ["https://www.havanna.com.ar/inversores"]),
    "GRIM":  ("Grimoldi", "consumo", 12, ["https://www.grimoldi.com/inversores"]),
    "PATA":  ("Imp y Exp de la Patagonia", "consumo", 6, ["https://www.laanonima.com.ar/inversores"]),
    # --- real estate ---
    "CTIO":  ("Consultatio", "real_estate", 12, ["https://www.consultatio.com.ar/inversores"]),
    "GCDI":  ("GCDI", "real_estate", 12, ["https://www.gcdi.com.ar/inversores"]),
    "RAGH":  ("RAGHSA", "real_estate", 6, ["https://www.raghsa.com.ar/"]),
    "CADO":  ("Carlos Casado", "real_estate", 9, ["https://www.carloscasado.com.ar/"]),
    "COUR":  ("Continental Urbana", "real_estate", 6, []),
    # --- energia (electricidad) ---
    "CECO2": ("Endesa Costanera", "energia", 12, ["https://www.centralcostanera.com/"]),
    "CAPX":  ("Capex", "energia", 4, ["https://www.capex.com.ar/inversores"]),
    "TRAN":  ("Transener", "energia", 12, ["https://www.transener.com.ar/inversores"]),
    "EDSH":  ("EDESA Holding", "energia", 12, ["https://www.edesa.com.ar/"]),
    # --- gas ---
    "TGNO4": ("Transportadora Gas del Norte", "gas", 12, ["https://www.tgn.com.ar/inversores"]),
    "METR":  ("Metrogas", "gas", 12, ["https://www.metrogas.com.ar/inversores"]),
    "GBAN":  ("Gas Natural Ban", "gas", 12, ["https://www.naturgy.com.ar/inversores"]),
    "CGPA2": ("Camuzzi Gas Pampeana", "gas", 12, ["https://www.camuzzigas.com.ar/"]),
    "ECOG":  ("Ecogas Inversiones", "gas", 12, ["https://www.ecogas.com.ar/inversores"]),
    "DGCU2": ("Distribuidora Gas Cuyana", "gas", 12, ["https://www.ecogas.com.ar/"]),
    "DGCE":  ("Distribuidora Gas del Centro", "gas", 12, ["https://www.ecogas.com.ar/"]),
    # --- infraestructura (concesiones viales) ---
    "AUSO":  ("Autopistas del Sol", "infra", 12, ["https://www.ausol.com.ar/inversores"]),
    "OEST":  ("Grupo Concesionario del Oeste", "infra", 12, ["https://www.aec.com.ar/inversores"]),
    # --- bancos / financiero ---
    "BHIP":  ("Banco Hipotecario", "bancos", 12, ["https://www.hipotecario.com.ar/inversores"]),
    "BPAT":  ("Banco Patagonia", "bancos", 12, ["https://www.bancopatagonia.com.ar/inversiones/"]),
    "VALO":  ("Banco de Valores", "bancos", 12, ["https://www.bancodevalores.com/inversores"]),
    "BYMA":  ("Bolsas y Mercados Argentinos", "financiero", 12, ["https://www.byma.com.ar/relacion-con-inversores/informacion-financiera/"]),
    "A3":    ("A3 Mercados", "financiero", 12, ["https://www.a3mercados.com.ar/"]),
    # --- medios / telecom ---
    "GCLA":  ("Grupo Clarin", "medios", 12, ["https://www.grupoclarin.com/inversores"]),
    "CVH":   ("Cablevision Holding", "medios", 12, ["https://www.cablevisionholding.com/inversores"]),
    # --- salud ---
    "RICH":  ("Laboratorios Richmond", "salud", 12, ["https://www.richmond.com.ar/inversores"]),
    "ROSE":  ("Instituto Rosenbusch", "salud", 12, []),
    # --- holding / otros ---
    "BOLT":  ("Boldt", "holding", 12, ["https://www.boldt.com.ar/inversores"]),
    "COME":  ("Sociedad Comercial del Plata", "holding", 12, ["https://www.comercialdelplata.com.ar/inversores"]),
    "GARO":  ("Garovaglio y Zorraquin", "holding", 9, []),
    "GAMI":  ("B-Gaming", "holding", 12, []),
}

SECTORES = sorted(set(v[1] for v in CATALOGO.values()))


def por_sector(sector):
    return [tk for tk, v in CATALOGO.items() if v[1] == sector]


def info(ticker):
    return CATALOGO.get(ticker)
