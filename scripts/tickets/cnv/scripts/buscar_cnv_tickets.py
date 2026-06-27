from googlesearch import search
import pandas as pd
import re
import time

empresas = {
    "LEDE":"Ledesma",
    "SAMI":"San Miguel",
    "MOLA":"Molinos Agro",
    "INVJ":"Inversora Juramento",
    "SEMI":"Molinos Juan Semino",

    "BHIP":"Banco Hipotecario",
    "BPAT":"Banco Patagonia",
    "VALO":"Banco de Valores",

    "GRIM":"Grimoldi",
    "HAVA":"Havanna",
    "MOLI":"Molinos Río de la Plata",
    "MORI":"Morixe",
    "PATA":"Patagonia",

    "CAPX":"Capex",
    "CECO2":"Central Costanera",
    "EDSH":"EDESA",
    "TRAN":"Transener",

    "A3":"A3",
    "BYMA":"BYMA",

    "CGPA2":"Camuzzi",
    "DGCE":"Distribuidora Gas del Centro",
    "DGCU2":"Distribuidora Gas Cuyana",
    "ECOG":"Ecogas",
    "GBAN":"Gas Natural BAN",
    "METR":"Metrogas",
    "TGNO4":"Transportadora de Gas del Norte",

    "BOLT":"Boldt",
    "COME":"Sociedad Comercial del Plata",
    "GAMI":"GAMI",
    "GARO":"Garovaglio y Zorraquín",

    "AGRO":"Agrometal",
    "DOME":"Domec",
    "FERR":"Ferrum",
    "INTR":"Introductora de Buenos Aires",
    "LONG":"Longvie",
    "MIRG":"Mirgor",
    "POLL":"Polledo",
    "REGE":"García Reguera",

    "AUSO":"Autopistas del Sol",
    "OEST":"Concesionaria del Oeste",

    "ALUA":"Aluar",
    "CARC":"Carboclor",
    "CELU":"Celulosa Argentina",
    "FIPL":"Fiplasto",
    "HARG":"Holcim Argentina",
    "RIGO":"Rigolleau",
    "TXAR":"Ternium Argentina",

    "CVH":"Cablevisión Holding",
    "GCLA":"Grupo Clarín",

    "CADO":"Carlos Casado",
    "COUR":"Continental Urbana",
    "CTIO":"Consultatio",
    "GCDI":"GCDI",
    "RAGH":"Raghsa",

    "RICH":"Laboratorios Richmond",
    "ROSE":"Instituto Rosenbusch"
}

resultado=[]

for ticker,nombre in empresas.items():

    consulta=f'site:cnv.gov.ar "{nombre}" Empresa'

    url="NO ENCONTRADA"

    try:
        for r in search(consulta,num_results=5):
            if "/SitioWeb/Empresas/Empresa/" in r:
                url=r
                break
    except Exception:
        pass

    print(ticker,url)

    resultado.append({
        "Ticker":ticker,
        "Empresa":nombre,
        "AIF":url
    })

    time.sleep(1)

df=pd.DataFrame(resultado)

df.to_excel("AIF_CNV.xlsx",index=False)
df.to_csv("AIF_CNV.csv",index=False,encoding="utf-8-sig")

print("Listo.")