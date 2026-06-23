# 03 - Documentación y Guías

Referencias y documentación técnica del proyecto screener financiero.

## Documentos Principales

### Plan y Arquitectura
- **PLAN_SCREENER_218_ACCIONES.md** ⭐
  - Plan formal completo con 4 fases de implementación
  - Timeline, deliverables, arquitectura de carpetas
  - Requisitos técnicos y criterios de éxito
  - **LEER PRIMERO** si recién empieza

### Guías Técnicas
- **GUIA_RATIOS_EDGAR_vs_INVESTING.md**
  - Cuáles ratios tomar directo de EDGAR vs cuáles calcular
  - Metodología uniforme para 13 ratios
  - Diferencias entre GAAP y non-GAAP

- **FUENTES_DATOS_ACCIONES_ARGENTINA_BYMA.md**
  - Mapping completo de dónde obtener cada tipo de dato
  - CEDEARs (200+), ADRs (18), Panel Líder BYMA
  - yfinance vs SEC EDGAR vs BYMADATA

### Investigación Técnica
- **EJEMPLO_CALCULO_LOCAL.md**
  - Opción A vs Opción B de metodologías de cálculo
  - Impacto en resultados finales

- **INSTRUCCIONES_DESCARGA_MANUAL.md**
  - Pasos manuales para descargar datos de BYMADATA
  - Alternativa si se necesita datos locales

- **RESUMEN_FINAL_HALLAZGOS.md**
  - Conclusiones de investigación: usar GAAP EDGAR
  - Validaciones realizadas
  - Por qué se descartó Investing.com

## Información por Métrica

Cada métrica está explicada en los documentos técnicos con:
- Fórmula exacta
- Fuente de datos recomendada
- Tratamiento de casos especiales (deuda negativa, no EBITDA, etc.)
- Comparabilidad entre CEDEARs y ADRs

## Validación de Datos

Se realizaron pruebas de convergencia:
- **Revenue**: ~99% similitud EDGAR vs Investing.com
- **Deuda/Equity**: ~99% similitud
- **Ratios derivados**: Validación manual en 7 empresas piloto

## Para Nuevas Acciones

Si quieres agregar más acciones (más allá de 200 CEDEARs + 18 ADRs):
1. Agregar ticker a CSV en 02_EXTRACCION_EDGAR/datos/
2. Ejecutar script correspondiente
3. La arquitectura es escalable — sin cambios de código

---
**Ubicación actual:** demo_catalaxia/03_DOCUMENTACION/
**Datos relacionados:** ../02_EXTRACCION_EDGAR/datos/
**Reportes finales:** ../04_REPORTES/
