# PLAN: Screener Financiero 218+ Acciones (CEDEARs + ADRs)

**Fecha**: 2026-06-23  
**Objetivo**: Construir screener automático de 218+ acciones (200+ CEDEARs + 18 ADRs argentinos)  
**Fuentes de Datos**: SEC EDGAR + yfinance  
**Costo**: $0  
**Status**: Listo para comenzar

---

## 📊 ALCANCE

### Acciones Incluidas
```
200+ CEDEARs (Acciones USA que cotizan en BYMA)
  Ejemplos: AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, etc.
  Data: yfinance + EDGAR
  
18 ADRs (Empresas argentinas que cotizan en USA)
  BBAR, BMA, CAAP, CEPU, CRESY, EDN, GGAL, GLOB, 
  IRS, LOMA, MELI, PAM, SUPV, TEO, TGS, TS, TX, YPF
  Data: yfinance + EDGAR
  
70+ Acciones SOLO BYMA (Excluidas - requieren USD 40)
```

**Total Screener: 218+ acciones**

---

## 🎯 RATIOS A CALCULAR

Para cada acción, calcular 13 ratios:

```
VALUACIÓN:
├─ 1. P/E (Price/Earnings)
├─ 2. P/Book (Price/Book Value)
├─ 3. Deuda/Equity
└─ 4. Deuda/EBITDA

RENTABILIDAD:
├─ 5. Margen Neto (NI / Revenue)
├─ 6. ROE (Net Income / Equity)
├─ 7. Operating Margin
└─ 8. EBITDA Margin

LIQUIDEZ & FLUJO:
├─ 9. FCF (Free Cash Flow)
├─ 10. FCF Yield
├─ 11. Payout Ratio (Dividendos / NI)
└─ 12. Current Ratio

CRECIMIENTO:
└─ 13. EPS CAGR 5Y (si disponible)
```

---

## 📁 ARQUITECTURA

```
demo_catalaxia/
├─ PLAN_SCREENER_218_ACCIONES.md (este archivo)
│
├─ 04_descargar_cedears_adrs.py
│  ├─ Descargar lista de 200+ CEDEARs desde RAVA/BYMADATA
│  ├─ Descargar 18 ADRs argentinos
│  └─ Guardar tickers en CSV
│
├─ 05_descargar_precios_yfinance.py
│  ├─ Descargar precios actuales (yfinance)
│  ├─ Descargar datos históricos (52 semanas)
│  └─ Guardar en CSV/JSON
│
├─ 06_descargar_datos_edgar.py
│  ├─ Descargar financieros de SEC EDGAR para 18 ADRs
│  ├─ Extraer Revenue, Net Income, Assets, Liabilities, Cash Flow
│  └─ Guardar en CSV/JSON
│
├─ 07_calcular_ratios.py
│  ├─ Calcular 13 ratios para cada acción
│  ├─ Aplicar metodología uniforme
│  └─ Guardar tabla de ratios
│
├─ 08_generar_screener.py
│  ├─ Consolidar todos los datos
│  ├─ Crear tabla comparativa
│  ├─ Rankings por métrica
│  └─ Generar reporte HTML/Excel
│
├─ data/
│  ├─ cedears_200.csv (lista de 200+ CEDEARs)
│  ├─ adrs_18.csv (lista de 18 ADRs argentinos)
│  ├─ precios.csv (precios actuales de yfinance)
│  ├─ financieros_edgar.csv (datos financieros de EDGAR)
│  ├─ ratios.csv (13 ratios calculados)
│  └─ screener_final.xlsx (reporte final)
│
├─ output/
│  ├─ screener_ranking_pe.html
│  ├─ screener_ranking_roe.html
│  ├─ screener_ranking_margin.html
│  └─ screener_summary.txt
│
└─ logs/
   ├─ descargas.log
   ├─ errores.log
   └─ calculos.log
```

---

## 📅 FASES DE IMPLEMENTACIÓN

### FASE 1: Recopilación de Datos (Semana 1)

**Tarea 1.1: Obtener lista de CEDEARs**
```
Entrada: RAVA screener (200+ CEDEARs)
Método: Copiar lista manualmente o web scraping
Salida: cedears_200.csv con columnas [ticker, empresa, sector, precio]
Tiempo: 2 horas
```

**Tarea 1.2: Obtener lista de ADRs argentinos**
```
Entrada: Lista oficial de 18 ADRs (ya disponible)
Método: Crear CSV manualmente
Salida: adrs_18.csv con [ticker, empresa, bolsa, sector]
Tiempo: 30 minutos
Archivo: adrs_18.csv
```

**Tarea 1.3: Descargar precios actuales**
```
Entrada: cedears_200.csv + adrs_18.csv
Script: 05_descargar_precios_yfinance.py
Salida: precios.csv [ticker, precio, 52w_high, 52w_low, vol]
Tiempo: 1 hora
```

---

### FASE 2: Datos Financieros (Semana 2)

**Tarea 2.1: Descargar datos EDGAR para ADRs**
```
Entrada: adrs_18.csv (tickers: BMA, GGAL, CRESY, TEO, TGS, TS, TX, YPF, etc.)
Script: 06_descargar_datos_edgar.py
Extrae:
├─ Revenue (anual, TTM)
├─ Net Income (anual, TTM)
├─ Operating Income
├─ Total Assets
├─ Total Liabilities
├─ Stockholders' Equity
├─ Depreciation & Amortization
├─ Operating Cash Flow
├─ Capital Expenditures
├─ Diluted Shares Outstanding
└─ Dividends (si disponible)

Salida: financieros_edgar.csv
Tiempo: 2-3 horas
```

**Tarea 2.2: Obtener datos para CEDEARs**
```
Para CEDEARs (empresas USA puras), obtener datos de EDGAR:
Entrada: cedears_200.csv
Script: 06_descargar_datos_edgar.py (adaptar para USA ticker mapping)
Salida: financieros_cedears.csv
Tiempo: 4-5 horas (depende de cantidad de tickers)
```

---

### FASE 3: Cálculo de Ratios (Semana 2-3)

**Tarea 3.1: Calcular 13 ratios**
```
Script: 07_calcular_ratios.py

Entrada: 
  - precios.csv (yfinance)
  - financieros_edgar.csv (EDGAR)
  - financieros_cedears.csv (EDGAR)

Cálculos (metodología uniforme):
├─ P/E = Precio / EPS
├─ P/Book = Precio / (Equity / Shares)
├─ Deuda/Equity = Total Debt / Equity
├─ Deuda/EBITDA = Debt / (OpInc + D&A)
├─ Margen Neto = NI / Revenue
├─ ROE = NI / Equity
├─ Operating Margin = OpInc / Revenue
├─ EBITDA Margin = EBITDA / Revenue
├─ FCF = CFO - CapEx
├─ FCF Yield = FCF / Market Cap
├─ Payout Ratio = Dividends / NI
├─ Current Ratio = Current Assets / Current Liab
└─ EPS CAGR 5Y = (EPS_final / EPS_inicial)^(1/5) - 1

Salida: ratios.csv
Tiempo: 3-4 horas
```

---

### FASE 4: Screener Final (Semana 3)

**Tarea 4.1: Consolidar datos**
```
Script: 08_generar_screener.py

Entrada:
  - precios.csv
  - financieros_edgar.csv
  - financieros_cedears.csv
  - ratios.csv

Salida: screener_final.xlsx con tabs:
├─ Resumen General (218 acciones con 13 ratios)
├─ Ranking P/E (de menor a mayor)
├─ Ranking ROE (de mayor a menor)
├─ Ranking Margen Neto
├─ Ranking Deuda/Equity
├─ Ranking FCF Yield
└─ Por Sector (USA, Argentina, etc.)

Tiempo: 2 horas
```

**Tarea 4.2: Generar reportes**
```
Output:
├─ screener_summary.txt (resumen ejecutivo)
├─ screener_ranking_pe.html (tabla HTML sorteable)
├─ screener_ranking_roe.html
└─ screener_ranking_margin.html

Tiempo: 1 hora
```

---

## 💾 DATOS NECESARIOS

### Input

**De yfinance (Automático)**
```
Para 218 acciones:
- Precio actual
- 52-week high/low
- Volume
- Market Cap
- Dividends
```

**De SEC EDGAR (Automático para ADRs)**
```
Para 18 ADRs argentinos:
- Revenue (10-K)
- Net Income (10-K)
- Assets, Liabilities (Balance Sheet)
- Cash Flow (10-K)
- Depreciation & Amortization (10-K)
- Diluted Shares (10-K)
- Dividends (10-K/10-Q)
```

**De yfinance (Automático para CEDEARs)**
```
Para 200+ CEDEARs:
Extraer los mismos datos vía API de yfinance
(yfinance accede a EDGAR internamente)
```

### Output

```
screener_final.xlsx
├─ 218 filas (acciones)
├─ 20+ columnas (ticker, empresa, precio, 13 ratios, etc.)
├─ Filtrable por sector
├─ Sorteable por cualquier métrica
└─ Comparable entre CEDEARs y ADRs con métrica uniforme
```

---

## 🔧 REQUISITOS TÉCNICOS

**Python Libraries**
```
yfinance              # Descargar precios
sec-edgar-downloader  # Descargar financieros 10-K
pandas                # Manipular datos
numpy                 # Cálculos numéricos
requests              # HTTP requests
openpyxl              # Generar Excel
beautifulsoup4        # Web scraping (si necesario)
```

**Instalación**
```bash
pip install yfinance sec-edgar-downloader pandas numpy requests openpyxl
```

---

## 📈 TIMELINE

| Fase | Tarea | Tiempo | Responsable | Status |
|------|-------|--------|-------------|--------|
| 1 | Obtener CEDEARs | 2h | Automático | ⏳ |
| 1 | Obtener ADRs | 0.5h | Manual | ⏳ |
| 1 | Descargar precios | 1h | Automático | ⏳ |
| 2 | Descargar EDGAR ADRs | 3h | Automático | ⏳ |
| 2 | Descargar EDGAR CEDEARs | 5h | Automático | ⏳ |
| 3 | Calcular ratios | 4h | Automático | ⏳ |
| 4 | Consolidar & generar | 3h | Automático | ⏳ |
| **TOTAL** | | **18.5h** | | |

**Tiempo real (con optimizaciones)**: 1-2 semanas

---

## 📋 DELIVERABLES

### Archivos
```
✓ screener_final.xlsx (tabla de 218 acciones + 13 ratios)
✓ screener_summary.txt (resumen ejecutivo)
✓ screener_ranking_pe.html (ordenado por P/E)
✓ screener_ranking_roe.html (ordenado por ROE)
✓ screener_ranking_margin.html (ordenado por margen)
```

### Documentación
```
✓ PLAN_SCREENER_218_ACCIONES.md (este archivo)
✓ GUIA_RATIOS_METODOLOGIA.md (explicación de cada ratio)
✓ DATA_SOURCES.md (dónde vienen los datos)
✓ INSTRUCCIONES_USO.md (cómo usar el screener)
```

### Código
```
✓ 04_descargar_cedears_adrs.py
✓ 05_descargar_precios_yfinance.py
✓ 06_descargar_datos_edgar.py
✓ 07_calcular_ratios.py
✓ 08_generar_screener.py
```

---

## ⚠️ RIESGOS & MITIGACIONES

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|-----------|
| EDGAR API lento para 200+ requests | Media | Cachear datos, usar sesiones |
| Algunos ADRs sin datos en EDGAR | Baja | Usar último disponible |
| yfinance bloqueado/rate limited | Baja | Usar delays, proxies |
| Inconsistencias entre fuentes | Media | Validar datos vs manual checks |

---

## ✅ CRITERIOS DE ÉXITO

```
☑ Descargar precios para 218 acciones ✓
☑ Descargar financieros para 18 ADRs ✓
☑ Descargar financieros para 200+ CEDEARs ✓
☑ Calcular 13 ratios con metodología uniforme ✓
☑ Crear tabla final con 218 x 20 datos ✓
☑ Generar reportes HTML/Excel ✓
☑ Documentación completa ✓
☑ Código reproducible ✓
```

---

## 🚀 PRÓXIMOS PASOS

1. **Confirmar**: ¿Comenzamos con Fase 1?
2. **Crear lista de CEDEARs**: ¿Tienes acceso a descargarlos de RAVA?
3. **Configurar ambiente**: Instalar Python libraries
4. **Comenzar scripts**: Empezar con 04_descargar_cedears_adrs.py

---

**Última actualización**: 2026-06-23  
**Estado**: Listo para comenzar implementación
