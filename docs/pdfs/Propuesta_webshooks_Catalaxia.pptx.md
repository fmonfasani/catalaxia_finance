webshooks.
Desarrollo de Software · LATAM
Propuesta
Comercial
Módulo de Análisis Financiero
CEDEARs — Backoffice Catalaxia
Cliente  Catalaxia S.A.
Fecha  Mayo 2026  ·  v1.0
Iniciá tu
transformación digital
con nosotros.
Propuesta de Solución :
Módulo de Análisis Financiero de CEDEARS 
Python
Next.js
PostgreSQL
FastAPI
SEC EDGAR


Resumen Ejecutivo
Desarrollo de un módulo completo de análisis financiero integrado en el backoffice existente de Catalaxia.
Monitoreo en tiempo real de ratios fundamentales de 100 CEDEARs con datos actualizados automáticamente.
100+
Tickers
monitoreados
10+
Ratios por
ticker
3
Jobs
automatizados
4
Semanas
de entrega
¿Qué incluye?
•
Screener con tabla de mas de 100 
tickers y 10 ratios
•
Filtros min/max, sorting y exportación 
CSV
•
Panel de procesos con log en tiempo 
real
•
3 jobs automatizados (precios, 
financials, cálculo)
•
Base de datos en 3 capas: raw + 
calculado + jobs
•
Detalle por ticker con gauge de PER y 
barra 52s
•
API REST con 7 endpoints 
documentados
•
Polling de jobs cada 3s con React 
Query
•
Badges de estado de actualización en 
topbar
webshooks.com
2


Alcance del Proyecto
Base de Datos & Jobs
•
Tabla cedears — maestro de tickers
•
Tabla precios_raw (Yahoo Finance)
•
Tabla financials_raw (SEC EDGAR XBRL)
•
Tabla ratios — calculados y listos
•
Tabla jobs + job_errores (auditoría)
•
Job 1A: descarga precios diario
•
Job 1B: descarga SEC EDGAR semanal
•
Job 2: cálculo TTM, CAGR y ratios
•
Retry automático + logging por ticker
API REST — FastAPI
•
GET /api/cedears/screener
•
GET /api/cedears/{ticker}/ratios
•
GET /api/cedears/{ticker}/precio
•
POST /api/jobs/ratios/precios
•
POST /api/jobs/ratios/financials
•
POST /api/jobs/ratios/calculo
•
GET /api/jobs/{id}/status
•
Documentación openapi.json
Frontend — Next.js
•
Sidebar + topbar con badges de estado
•
Screener: tabla 100 tickers, 16 columnas
•
Filtros min/max: PER, Deuda, Precio
•
Filtro Exchange (NASDAQ/NYSE/AMEX)
•
Sorting + paginación 25/50/100 filas
•
Exportar CSV con datos filtrados
•
Detalle por ticker con gauge y barra 52s
•
Panel de jobs con log en tiempo real
•
Modal de errores por ticker
webshooks.com
3


Stack Tecnológico
BACKEND
Lenguaje
Python 3.11+
API Framework
FastAPI + Uvicorn
Scraping precios
yfinance (Yahoo Finance)
Scraping ratios
Playwright (Investing.com)
Financials
SEC EDGAR XBRL — sin API key
Base de datos
PostgreSQL 16
ORM
SQLAlchemy 2.0 + asyncpg
Scheduler
APScheduler — cron jobs
Líneas aprox.
~1500/2500 líneas de código
FRONTEND
Framework
Next.js 14 (App Router)
Lenguaje
TypeScript 5
Estilos
Tailwind CSS 3
Componentes
shadcn/ui
Fetch / cache
SWR + React Query
Iconos
Tabler Icons
Tipografía
Calibri / Arial
Líneas aprox.
~1200 / 1500 líneas de código
Total del proyecto:  ~4.000 líneas de código  ·  5 tablas PostgreSQL  ·  7 endpoints  ·  16 componentes React
webshooks.com
4


Informe de Investigación
Pipeline de Datos
CEDEARs
De la API de BYMA al Excel de Seguimiento
Fase  
Investigación y desarrollo
Scripts ejecutados  
8 pasos (02 → 08)
Tickers procesados  
2.176 BYMA → 502 únicos
Empresas con datos  
415 con ratios calculados
Fecha  
Mayo 2026
2.176
Tickers raw BYMA
502
CEDEARs únicos
295
Empresas en SEC
415
Ratios calculados
webshooks.com  ·  Módulo Análisis Financiero CEDEARs  ·  Confidencial


Pipeline Completo — 8 Pasos de ETL
Cada script es un paso independiente con input y output definidos. Se pueden correr secuencialmente o de forma selectiva.
1
cedears_base_ars.json
Fuente
BYMA API
502 tickers
2
02_mapear_cedears_sec.py
BYMA ticker
→ CIK SEC
422 mapeados
3
03_descargar_financials_sec.py
SEC EDGAR
XBRL JSON
295 empresas
4
04_descargar_precios.py
Yahoo Finance
yfinance
295 precios
5
05_calcular_ratios.py
TTM, CAGR
16 ratios
415 filas
6
06_precios_historicos.py
OHLCV diario
5+ años
295 CSVs
7
07_byma_locales.py
Acciones ARG
yfinance .BA
79 locales
8
08_generar_dataset_etl.py
company_master
PostgreSQL ready
data_export/
↓
webshooks.com  ·  Informe de Investigación — Módulo CEDEARs
3


Equipo de Trabajo
V
Valentino 
Backend A Dev
Precios + PER + EPS + Crec. EPS
•
Job 1A: yfinance → precios_raw 
(cron diario)
•
Scraping PER y EPS desde 
Investing.com
•
Scraping Crecimiento EPS 5 años
•
Endpoints GET precio + POST jobs
•
APScheduler + retry ×3 por ticker
40 hs
M
Backend B Dev
Financials + Cálculo de Ratios
•
Job 1B: SEC EDGAR → 
financials_raw
•
Scraping Margen, ROE y Payout 
(Investing)
•
Job 2: cálculo TTM, CAGR, EBITDA
•
FCFonCE y Deuda/EBITDA desde 
XBRL
•
Endpoint GET screener completo
40 hs
J
Joaquin
Frontend A Dev
Screener — Tabla + Filtros
•
Tabla 100 tickers, 16 columnas 
ratios
•
Filtros min/max PER, D/EBITDA, 
Precio
•
Sorting + paginación 25/50/100 
filas
•
Color condicional + exportar CSV
•
SWR refresh 60s + skeleton loading
40 hs
A
Aldana
Frontend B Dev
Procesos + Detalle de Ticker
•
ProcessCard.tsx + polling jobs React 
Query
•
Trigger POST jobs + React Query 3s
•
Detalle ticker: gauge PER + barra 
52s
•
Modal de errores por ticker
•
Badges de estado en topbar
40 hs
F
Federico
Arquitecto  ·  Tech Lead
•
Diseño de arquitectura: 3 capas (raw + calculado + jobs), 5 tablas 
PostgreSQL
•
Schema de BD completo y contrato openapi.json acordado antes 
de arrancar
•
Decisiones técnicas: TTM, fallback XBRL, separación Job 1 / Job 2
•
Integración y puesta en productivo
•
Supervisión, code review y QA de los 4 
colaboradores
•
Integración final, deploy , soporte correctivo 
por 90 dias
40 hs
webshooks.com
Mateo


Cronograma — 4 Semanas
Backend A
Backend B
Frontend A
Frontend B
Semana 1
02–06 Jun
Fundamentos
Schema BD + endpoints precios
Cron APScheduler
Schema ratios + Playwright
Setup Investing.com
Next.js + sidebar + topbar
Tabla /analisis-financiero vacía
React Query + ProcessCard
Cards en /procesos
Semana 2
09–13 Jun
Scraping + UI base
Scraping PER y EPS
Endpoints GET precio
Scraping Margen y ROE
INSERT financials_raw
Tabla mockeada 10+ columnas
Color condicional celdas
Ruta /[ticker] + cards ratios
Barra 52 semanas
Semana 3
16–20 Jun
Lógica completa
Crec. EPS + job endpoints
Rate limiting y retry
FCFonCE + Payout + D/EBITDA
Job 2 cálculo TTM
Filtros min/max + sorting
Paginación + CSV
Trigger POST + polling
Estados del job visual
Semana 4
23–27 Jun
Integración + QA
Integración frontend
Tests + openapi.json
Screener completo
Manejo de errores
SWR real + skeleton
Badges de estado
Modal errores + gauges
QA y entrega final
webshooks.com
6


Procesos
Seccion A: Procesos - Jobs y Card Analisis Financiero
webshooks.com
N
https://maqueta-catalaxia.vercel.app/


Analisis Financiero
https://maqueta-catalaxia.vercel.app/
Sección B  —  Analisis financiero
•
webshooks.com
N


Integración Backend Frontend / Jobs DB 
Integracion Backend - DB Jobs 
INtegracion Frontend / APIs - Jobs
webshooks.com
N


Inversión y Financiación
Inversión Total
USD 1.200
Precio fijo por proyecto · Sin costos adicionales
Soporte correctivo opcional: de 3 a 12 meses x  USD 125 / mes
Soporte correctivo pago único por USD 800, con la entrega del proyecto
Opciones de pago
Contado
Pago único al firmar
USD 1.200
10 % de descuento aplicado si se contrata hoy 
mismo
Inicio inmediato
3 Cuotas
Sin interés
USD 400 × 3
Cuota 1: al firmar
Cuota 2:Entrega 
Cuota 3: mes a partir de la entrega  
6 Cuotas
Con ajuste
USD 250 × 6
Cuota 1: al firmar
Cuotas 2: Entrega 
Cuota3-6: mensual  
webshooks.com
7


¿Cómo arrancamos?
01
Aprobación
Confirmar la propuesta y definir el plan de pago.
02
Primer pago
50% al inicio o primera cuota según el plan elegido.
03
Kickoff
1 hora con el equipo: schema BD y contrato de API.
04
Entrega
4 semanas de desarrollo + reportes semanales.
Resumen
Empresa
webshooks
Proyecto
Módulo CEDEARs
Inversión
USD 1.200
Duración
4 semanas
Inicio
Inmediato
Garantía
30 días post-entrega
Esta propuesta tiene validez de 30 días.
webshooks.
