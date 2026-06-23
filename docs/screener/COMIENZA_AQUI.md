# 🚀 COMIENZA AQUI

Estructura completamente reorganizada. Acá está la guía rápida.

## 📖 Paso 1: Lee la Documentación (5-10 min)

```
demo_catalaxia/
├─ README_PRINCIPAL.md          ← Lee esto primero (visión general)
└─ 03_DOCUMENTACION/PLAN_SCREENER_218_ACCIONES.md  ← Luego esto (plan detallado)
```

**¿Qué aprenderás?**
- Qué son CEDEARs y ADRs
- Los 13 ratios que calcularemos
- Las 5 fases de implementación
- Fuentes de datos (EDGAR + yfinance)

---

## 📊 Paso 2: Entiende la Estructura

```
demo_catalaxia/
│
├─ 01_INVESTIGACION_INVESTING/     ⚠️ NO USAR (scraping fallido de Investing)
│  └─ Ver README.md para entender por qué se descartó
│
├─ 02_EXTRACCION_EDGAR/            ✅ NÚCLEO (esto es lo que funciona)
│  ├─ scripts/                     (5 scripts de descarga + cálculos)
│  └─ datos/                       (entrada: listas | salida: CSVs)
│
├─ 03_DOCUMENTACION/               📚 (planes y guías técnicas)
│  └─ 7 documentos de referencia
│
├─ 04_REPORTES/                    📈 (salida final: Excel + HTML)
│
└─ logs/                           📝 (logs de ejecución)
```

---

## 🏃 Paso 3: Ejecuta los Scripts (si quieres probar)

**Requisitos:**
```bash
pip install yfinance pandas numpy sec-edgar-downloader openpyxl requests
```

**Ejecución:**
```bash
cd demo_catalaxia/02_EXTRACCION_EDGAR/scripts

# Fase 1: Generar listas de CEDEARs y ADRs
python 01_descargar_cedears_adrs.py
→ Output: ../datos/cedears_200_procesados.csv, adrs_18_argentinos.csv

# Fase 2: Descargar precios actuales desde yfinance
python 02_descargar_precios_yfinance.py
→ Output: ../datos/precios_completos.csv

# Fase 3-5: Pendientes de implementación
# python 03_descargar_datos_edgar.py
# python 04_calcular_ratios.py
# python 05_generar_screener.py
```

**Tiempo:** ~15-20 minutos para scripts 01-02

---

## 📋 Paso 4: Revisa los Datos

Los datos se generan aquí:
```
demo_catalaxia/02_EXTRACCION_EDGAR/datos/

cedears_200_procesados.csv   ← 127 CEDEARs (AAPL, MSFT, TSLA, etc.)
adrs_18_argentinos.csv       ← 18 ADRs (BBAR, BMA, GGAL, MELI, etc.)
precios_completos.csv        ← Precios actuales + 52w high/low + vol
[próximos]
financieros_edgar.csv        ← Datos de balance sheet e income
ratios.csv                   ← 13 ratios calculados
```

---

## 🎯 Paso 5 (Futuro): Genera el Plan/Informe

Con la estructura clara, puedes:
1. **Armar un informe ejecutivo** sobre el proyecto
2. **Presentar a stakeholders** con:
   - Qué acciones incluye (218+)
   - Qué ratios calcula (13)
   - Timeline de ejecución (4 fases)
   - Fuentes de datos validadas (EDGAR ~99% confiable)

---

## ⚡ Decisiones Técnicas Clave

| Pregunta | Respuesta | Por Qué |
|----------|-----------|--------|
| ¿Investing.com? | ❌ NO | Protecciones anti-scraping + cambios de estructura |
| ¿SEC EDGAR? | ✅ SÍ | API oficial + gratuita + ~99% fiable |
| ¿CEDEARs + ADRs? | ✅ SÍ | Comparabilidad total con metodología uniforme |
| ¿yfinance? | ✅ SÍ | Precios actuales diarios + 52 semanas |
| ¿Escalable? | ✅ SÍ | Estructura lista para 300+ acciones sin cambios |

---

## 📚 Documentos de Referencia

### Entendimiento General
- `README_PRINCIPAL.md` - Índice y visión general
- `01_INVESTIGACION_INVESTING/README.md` - Por qué falló Investing

### Implementación
- `03_DOCUMENTACION/PLAN_SCREENER_218_ACCIONES.md` - Plan formal
- `02_EXTRACCION_EDGAR/README.md` - Detalles técnicos

### Metodología
- `03_DOCUMENTACION/GUIA_RATIOS_EDGAR_vs_INVESTING.md` - 13 ratios
- `03_DOCUMENTACION/FUENTES_DATOS_ACCIONES_ARGENTINA_BYMA.md` - Mapping

---

## ❓ FAQ Rápido

**P: ¿Por dónde empiezo?**  
R: Lee `README_PRINCIPAL.md` (5 min), luego `PLAN_SCREENER_218_ACCIONES.md` (10 min).

**P: ¿Cuánto tarda ejecutar todo?**  
R: Scripts 01-02: ~20 min. Scripts 03-05: ~2-3 horas (cuando estén implementados).

**P: ¿Necesito descargar Investing?**  
R: NO. Todo viene de SEC EDGAR (oficial) + yfinance (precios).

**P: ¿Qué pasa con la carpeta 01_INVESTIGACION_INVESTING/?**  
R: Referencia histórica. Muestra qué se intentó y por qué no funcionó.

**P: ¿Puedo agregar más acciones?**  
R: SÍ. Agrega ticker a `02_EXTRACCION_EDGAR/datos/*.csv` y ejecuta scripts.

---

## 🎯 Resumen de Cambios

### Antes (Caos)
```
demo_catalaxia/
├─ 50+ archivos sueltos
├─ Scripts de scraping fallidos
├─ 20+ documentos sin organizar
├─ Datos duplicados en varias carpetas
└─ Imposible entender qué sirve
```

### Ahora (Claridad)
```
demo_catalaxia/
├─ 01_INVESTIGACION_INVESTING/  [NO USAR - referencia]
├─ 02_EXTRACCION_EDGAR/         [USAR - funciona]
├─ 03_DOCUMENTACION/            [LEER - guías]
├─ 04_REPORTES/                 [OUTPUT - resultados]
├─ logs/                        [TÉCNICO - logs]
├─ README_PRINCIPAL.md          [INICIO]
└─ COMIENZA_AQUI.md             [ESTE ARCHIVO]
```

---

**Status:** ✅ REORGANIZACIÓN COMPLETADA  
**Próximo:** Leer documentación y ejecutar scripts  
**Fecha:** 2026-06-23
