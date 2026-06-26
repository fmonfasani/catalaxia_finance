# FUENTES DE DATOS: Acciones Argentinas en BYMA

**Objetivo**: Saber de dónde obtener datos financieros para cada acción argentina que cotiza en BYMA.

---

> ## ⚠️ CORRECCIÓN (jun 2026) — más ADRs argentinos están en EDGAR de lo que decía la tabla
>
> La tabla de abajo marcaba varias como "❌ NO cotiza en USA → scraping CNV". **Verificamos
> contra EDGAR y la mayoría SÍ filean con la SEC** (20-F en **IFRS**) y ya las descargamos:
>
> | Ticker | Estado real en EDGAR | Tags |
> |--------|----------------------|------|
> | **PAM** (Pampa) | ✅ IFRS | 289 |
> | **BBAR** (BBVA Arg) | ✅ IFRS | 227 |
> | **SUPV** (Supervielle) | ✅ IFRS | 239 |
> | **LOMA** (Loma Negra) | ✅ IFRS | 265 |
> | **EDN** (Edenor) | ✅ EDGAR | 196 |
> | **CEPU, TGS, BIOX, GLOB, GGAL, BMA, IRS, CRESY, TEO, YPF, MELI** | ✅ EDGAR | — |
>
> De **17 ADRs argentinos chequeados: ~16 están en EDGAR** (solo DESP faltaba), casi todos
> en **IFRS** — descargables con el **fix IFRS** (ver `ESPEC_TAGS_RATIOS.md` §7). Ya están
> en `data/screener.db` (grupo `adr_arg`). El scraping de CNV queda solo para las que **no**
> cotizan en USA (Molinos, Metrogas, Clarín, Ledesma, etc.).

## 📊 TABLA: Acciones Argentinas + Fuentes de Datos

| Ticker BYMA | Empresa | Cotiza en USA? | Ticker USA | Fuente de Datos | Automático? |
|-------------|---------|----------------|-----------|-----------------|------------|
| **YPFm** | YPF | ✅ SÍ (NYSE) | YPF | EDGAR | ✅ API SEC |
| **GGALm** | Grupo Financiero Galicia | ✅ SÍ (NASDAQ) | GGAL | EDGAR | ✅ API SEC |
| **BMAm** | Banco Macro | ✅ SÍ (NYSE) | BMA | EDGAR | ✅ API SEC |
| **TECO2m** | Telecom Argentina | ✅ SÍ (NASDAQ) | TARG | EDGAR | ✅ API SEC |
| **PAMPm** | Pampa Energía | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **EDNm** | Edenor | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **BBARm** | Banco BBVA Argentina | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **SUPVm** | Grupo Supervielle | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **CRESm** | Cresud | ✅ SÍ (NASDAQ) | CRESY | EDGAR | ✅ API SEC |
| **MOLAm** | Molinos Agro | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **METRm** | Metrogas | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **GCLAm** | Grupo Clarín | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **LEDEm** | Ledesma | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **IRSAm** | IRSA | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |
| **LOMAm** | Loma Negra | ❌ NO | - | CNV Argentina | ⚠️ Web scraping |

---

## 🟢 CATEGORIA 1: Cotizan en USA (EDGAR) - AUTOMÁTICO

### Acciones argentinas que cotizan en NYSE/NASDAQ

#### 1️⃣ **YPF (Yacimientos Petrolíferos Fiscales)**
```
Ticker BYMA:  YPFm
Ticker NYSE:  YPF
Sector:       Energy (Oil & Gas)

Data disponible en:
├─ EDGAR: ✅ SÍ (reporta a SEC)
├─ URL: data.sec.gov/api/xbrl/companyfacts/CIK0001104659
├─ Formato: JSON/XBRL (estructurado)
├─ Actualización: Cada trimestre (10-Q) y año (10-K)
└─ Método: API SEC EDGAR (automatizable)

Cómo obtener:
$ curl "https://data.sec.gov/api/xbrl/companyfacts/CIK0001104659/YPF-facts.json"
```

#### 2️⃣ **Grupo Financiero Galicia (GGAL)**
```
Ticker BYMA:  GGALm
Ticker NASDAQ: GGAL
Sector:       Financials (Banking)

Data disponible en:
├─ EDGAR: ✅ SÍ (reporta a SEC)
├─ CIK: 1069595
├─ Formato: JSON/XBRL
├─ Actualización: Trimestral
└─ Método: API SEC EDGAR (automatizable)
```

#### 3️⃣ **Banco Macro (BMA)**
```
Ticker BYMA:  BMAm
Ticker NYSE:  BMA
Sector:       Financials (Banking)

Data disponible en:
├─ EDGAR: ✅ SÍ (reporta a SEC)
├─ CIK: 1113245
├─ Formato: JSON/XBRL
├─ Actualización: Trimestral
└─ Método: API SEC EDGAR (automatizable)
```

#### 4️⃣ **Telecom Argentina (TARG)**
```
Ticker BYMA:  TECO2m
Ticker NASDAQ: TARG
Sector:       Technology (Telecom)

Data disponible en:
├─ EDGAR: ✅ SÍ (reporta a SEC)
├─ CIK: 1112872
├─ Formato: JSON/XBRL
├─ Actualización: Trimestral
└─ Método: API SEC EDGAR (automatizable)
```

#### 5️⃣ **Cresud (CRESY)**
```
Ticker BYMA:  CRESm
Ticker NASDAQ: CRESY
Sector:       Consumer Non-Cyclicals (Food & Agriculture)

Data disponible en:
├─ EDGAR: ✅ SÍ (reporta a SEC)
├─ CIK: 1082722
├─ Formato: JSON/XBRL
├─ Actualización: Trimestral
└─ Método: API SEC EDGAR (automatizable)
```

---

## 🔴 CATEGORIA 2: NO cotizan en USA - MANUAL

### Acciones argentinas SOLO en BYMA (sin cotización USA)

#### Ejemplos: PAMPA, Edenor, BBVA Argentina, Supervielle, Molinos, Metrogas, Clarín, Ledesma, IRSA, Loma Negra, etc.

```
Ticker BYMA:  PAMPm (Pampa Energía)
Sector:       Utilities (Electrical)

Data disponible en:
├─ EDGAR: ❌ NO (no cotiza en USA)
├─ CNV Argentina: ✅ SÍ (reporta a regulador local)
├─ BYVA: ✅ Bolsa de Valores de Buenos Aires
├─ Formato: PDF (no estructurado, difícil de automatizar)
├─ Actualización: Trimestral (con retraso)
└─ Método: Web scraping o descarga manual

Dónde obtener:
1. Sitio de BYVA: www.byma.com.ar → Búsqueda de empresa
2. Sitio investor relations de la empresa (si existe)
3. CNV Argentina: www.cnv.gov.ar → Búsqueda de emisores
4. Web scraping (frágil, puede cambiar formato)
```

---

## 🎯 RECOMENDACIÓN: Estrategia por Categoría

### OPCIÓN A: Solo acciones con EDGAR (5 empresas)
```
Empresas:  YPF, Galicia, Banco Macro, Telecom Argentina, Cresud
├─ Ventaja: Automático via API SEC
├─ Desventaja: Solo 5 empresas (cobertura limitada)
└─ Tiempo: 2 semanas de implementación

Implementación:
1. Usar mismo código que para CEDEARs USA
2. Agregar CIKs argentinos a la descarga
3. Calcular ratios con metodología uniforme
4. Comparar: CEDEARs USA + Acciones Argentinas USA

Resultado: ✅ Screener mixto (USA + Argentina) pero con data consistente
```

### OPCIÓN B: Solo acciones SOLO en BYMA (web scraping)
```
Empresas: PAMPA, Edenor, BBVA Arg, Supervielle, Molinos, etc. (~100+)
├─ Ventaja: Cobertura completa de BYMA local
├─ Desventaja: Frágil (web scraping), difícil mantener
└─ Tiempo: 4-6 semanas (por cada empresa, web scraping inestable)

Implementación:
1. Web scraping de BYVA/CNV
2. Parsear PDFs de estados financieros
3. Extraer datos manualmente por empresa
4. Actualizar manualmente cada trimestre

Resultado: ❌ Difícil de automatizar, requiere mantenimiento constante
```

### OPCIÓN C: MIXTA (RECOMENDADA) ⭐
```
Empresas: 
├─ Tier 1 (Automático via EDGAR): YPF, Galicia, BMA, Telecom, Cresud
└─ Tier 2 (Manual/Scraping): Top 10 BYMA más importantes (PAMPA, Edenor, etc.)

Implementación:
1. Fase 1: Implementar las 5 con EDGAR (2 semanas)
2. Fase 2: Agregar 5-10 importantes de BYMA con web scraping (3-4 semanas)
3. Resultado: ~15 empresas comparables

Ventaja: ✅ Balance entre cobertura y automatización
```

---

## 📋 CÓDIGO: Cómo obtener datos

### Para empresas con EDGAR (Automático)

```python
# Mismo código que para CEDEARs USA, solo agregar CIKs argentinos

import requests

# CIKs de empresas argentinas que cotizan en USA
argentina_ciks = {
    'YPF': '0001104659',
    'GGAL': '0001069595',
    'BMA': '0001113245',
    'TARG': '0001112872',
    'CRESY': '0001082722',
}

for ticker, cik in argentina_ciks.items():
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}/facts.json"
    response = requests.get(url)
    data = response.json()
    
    # Extraer datos (igual que para AAPL, MSFT, etc.)
    revenue = data['facts']['us-gaap']['Revenues']
    net_income = data['facts']['us-gaap']['NetIncomeLoss']
    # ... etc
```

### Para empresas SOLO en BYMA (Manual)

```python
# Web scraping (FRÁGIL - requiere mantenimiento)

from selenium import webdriver
from bs4 import BeautifulSoup

# Buscar empresa en BYVA
url = "https://www.byma.com.ar/es/acciones/PAMPm"

driver = webdriver.Chrome()
driver.get(url)
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Extraer datos (problemático: formato puede cambiar)
revenue = soup.find('div', class_='revenue').text
net_income = soup.find('div', class_='net_income').text

# ⚠️ PROBLEMA: Si BYVA cambia HTML, esto se rompe
```

---

## 🎯 PROPUESTA FINAL

### Fase 1: CEDEARs USA (AAPL, MSFT, NVDA, TSLA, AMZN)
- Fuente: EDGAR
- Tiempo: 2-3 semanas
- Automático: ✅ SÍ

### Fase 2: Acciones Argentinas con EDGAR (YPF, GGAL, BMA, TARG, CRESY)
- Fuente: EDGAR
- Tiempo: 1-2 semanas (reutilizar código Fase 1)
- Automático: ✅ SÍ

**Total Fase 1+2: 10 empresas, data automática, 3-5 semanas**

### Fase 3 (Opcional): Acciones SOLO BYMA (PAMPA, Edenor, etc.)
- Fuente: Web scraping CNV/BYVA
- Tiempo: 3-4 semanas
- Automático: ⚠️ Frágil

---

## 📊 RESUMEN: Dónde sacar datos

| Tipo | Empresas | Fuente | Automático | Esfuerzo |
|------|----------|--------|-----------|----------|
| **CEDEARs USA** | AAPL, MSFT, NVDA, TSLA, AMZN | EDGAR | ✅ | Bajo |
| **Arg en USA** | YPF, GGAL, BMA, TARG, CRESY | EDGAR | ✅ | Bajo |
| **SOLO BYMA** | PAMPA, Edenor, BBVA, etc. | CNV/BYVA | ⚠️ | Alto |

**Recomendación**: Empezar con Fases 1+2 (10 empresas automáticas), luego agregar Fase 3 si necesitas más cobertura.

¿Cuál es el plan?

