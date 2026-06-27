# -*- coding: utf-8 -*-
"""
Catalogo CURADO de los ~55 papeles BYMA-only -> sus sitios de Relacion con
Inversores (donde publican los EEFF). NO se adivinan URLs: son las conocidas.
Los que no tienen IR confirmado quedan con [] y el discovery los busca por
bolsar / buscador como fallback.

tipo: orienta la libreria de etiquetas (banco usa "Ingresos por intereses",
industrial "Ventas netas", utility/gas "Ingresos por servicios", etc.).
"""

# ticker -> (nombre, [urls IR/inversores candidatas], tipo)
CATALOGO = {
    "ALUA":  ("Aluar", ["https://www.aluar.com.ar/inversores"], "industrial"),
    "MIRG":  ("Mirgor", ["https://www.mirgor.com.ar/inversores", "https://ri.mirgor.com.ar/"], "industrial"),
    "LEDE":  ("Ledesma", ["https://www.ledesma.com.ar/inversores"], "agro"),
    "SAMI":  ("San Miguel", ["https://www.sanmiguelglobal.com/inversores"], "agro"),
    "HARG":  ("Holcim Argentina", ["https://www.holcim.com.ar/inversionistas", "https://www.holcim.com.ar/"], "industrial"),
    "CELU":  ("Celulosa Argentina", ["https://www.celulosaargentina.com.ar/inversores"], "industrial"),
    "MOLA":  ("Molinos Agro", ["https://www.molinosagro.com.ar/inversores"], "agro"),
    "MOLI":  ("Molinos Rio de la Plata", ["https://www.molinos.com.ar/inversores"], "industrial"),
    "GRIM":  ("Grimoldi", ["https://www.grimoldi.com/inversores"], "industrial"),
    "FERR":  ("Ferrum", ["https://www.ferrum.com/inversores"], "industrial"),
    "RIGO":  ("Rigolleau", ["https://www.rigolleau.com.ar/inversores"], "industrial"),
    "LONG":  ("Longvie", ["https://www.longvie.com/inversores"], "industrial"),
    "MORI":  ("Morixe", ["https://www.morixe.com.ar/inversores"], "agro"),
    "HAVA":  ("Havanna", ["https://www.havanna.com.ar/inversores"], "industrial"),
    "CARC":  ("Carboclor", ["https://www.carboclor.com.ar/"], "industrial"),
    "AGRO":  ("Agrometal", ["https://www.agrometal.com.ar/inversores"], "industrial"),
    "INVJ":  ("Inversora Juramento", ["https://www.juramento.com.ar/inversores"], "agro"),
    "RICH":  ("Laboratorios Richmond", ["https://www.richmond.com.ar/inversores"], "industrial"),
    "BOLT":  ("Boldt", ["https://www.boldt.com.ar/inversores"], "holding"),
    "CADO":  ("Carlos Casado", ["https://www.carloscasado.com.ar/"], "real_estate"),
    "RAGH":  ("RAGHSA", ["https://www.raghsa.com.ar/"], "real_estate"),
    "CTIO":  ("Consultatio", ["https://www.consultatio.com.ar/inversores"], "real_estate"),
    "GCDI":  ("GCDI", ["https://www.gcdi.com.ar/inversores"], "real_estate"),
    "IRSA":  ("IRSA", ["https://www.irsa.com.ar/inversores"], "real_estate"),
    # utilities / energia / gas
    "CECO2": ("Endesa Costanera", ["https://www.centralcostanera.com/", "https://www.centralcostanera.com/inversores"], "utility"),
    "CAPX":  ("Capex", ["https://www.capex.com.ar/inversores"], "utility"),
    "TRAN":  ("Transener", ["https://www.transener.com.ar/inversores"], "utility"),
    "TGNO4": ("Transportadora Gas del Norte", ["https://www.tgn.com.ar/inversores"], "gas"),
    "METR":  ("Metrogas", ["https://www.metrogas.com.ar/inversores"], "gas"),
    "GBAN":  ("Gas Natural Ban", ["https://www.naturgy.com.ar/inversores"], "gas"),
    "CGPA2": ("Camuzzi Gas Pampeana", ["https://www.camuzzigas.com.ar/"], "gas"),
    "ECOG":  ("Ecogas Inversiones", ["https://www.ecogas.com.ar/inversores"], "gas"),
    "DGCU2": ("Distribuidora Gas Cuyana", ["https://www.ecogas.com.ar/"], "gas"),
    "DGCE":  ("Distribuidora Gas del Centro", ["https://www.ecogas.com.ar/"], "gas"),
    "AUSO":  ("Autopistas del Sol", ["https://www.ausol.com.ar/inversores"], "utility"),
    "OEST":  ("Grupo Concesionario del Oeste", ["https://www.aec.com.ar/inversores"], "utility"),
    "EDSH":  ("EDESA Holding", ["https://www.edesa.com.ar/"], "utility"),
    # bancos / financieras
    "BHIP":  ("Banco Hipotecario", ["https://www.hipotecario.com.ar/inversores"], "banco"),
    "BPAT":  ("Banco Patagonia", ["https://www.bancopatagonia.com.ar/inversiones/"], "banco"),
    "VALO":  ("Banco de Valores", ["https://www.bancodevalores.com/inversores"], "banco"),
    "BYMA":  ("Bolsas y Mercados Argentinos", ["https://www.byma.com.ar/relacion-con-inversores/informacion-financiera/"], "holding"),
    "A3":    ("A3 Mercados", ["https://www.a3mercados.com.ar/"], "holding"),
    # holdings / medios / otros
    "GCLA":  ("Grupo Clarin", ["https://www.grupoclarin.com/inversores"], "holding"),
    "CVH":   ("Cablevision Holding", ["https://www.cablevisionholding.com/inversores"], "holding"),
    "COME":  ("Sociedad Comercial del Plata", ["https://www.comercialdelplata.com.ar/inversores"], "holding"),
    "GAMI":  ("B-Gaming", ["https://www.boldt.com.ar/"], "industrial"),
    "PATA":  ("Imp y Exp de la Patagonia", ["https://www.laanonima.com.ar/inversores"], "industrial"),
    "DOME":  ("Domec", [], "industrial"),
    "GARO":  ("Garovaglio y Zorraquin", [], "holding"),
    "FIPL":  ("Fiplasto", [], "industrial"),
    "INTR":  ("Introductora de Bs As", [], "industrial"),
    "SEMI":  ("Molinos Juan Semino", [], "agro"),
    "POLL":  ("Polledo", [], "industrial"),
    "COUR":  ("Continental Urbana", [], "real_estate"),
    "REGE":  ("Garcia Reguera", [], "industrial"),
    "TXAR":  ("Ternium Argentina", ["https://ar.ternium.com/es/inversores"], "industrial"),
}
