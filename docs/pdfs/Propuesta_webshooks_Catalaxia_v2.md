Iniciá tu
transformación digital
con nosotros.
Propuesta de Solución (actualizada):
Módulo de Análisis Financiero con SEC EDGAR — validado sobre 553 empresas reales
Python
Next.js
PostgreSQL
FastAPI
SEC EDGAR (GAAP+IFRS)
webshooks.
Desarrollo de Software · LATAM
Propuesta
Comercial
Módulo de Análisis Financiero
CEDEARs + ADRs LatAm — Backoffice Catalaxia
Cliente  Catalaxia S.A.
Fecha  Junio 2026 · v2.0


Desarrollo de un módulo de análisis financiero integrado al backoffice de Catalaxia. A diferencia de la propuesta original, la fuente de datos ya está validada empíricamente: 553
empresas reales calculadas y comparadas contra Investing.com, no una arquitectura en papel.
553
Empresas con ratios
ya calculados y validados
35+
Ratios fundamentales
por empresa (GAAP+IFRS)
8.021
Universo total disponible
en SEC EDGAR
1,3%
Divergencia mediana de PER
vs. Investing.com
¿Qué incluye?
webshooks.
Resumen Ejecutivo
Screener con +500 empresas reales y 35 ratios (no una
maqueta)
•
Cobertura S&P 500 (100%) + ADRs Argentina/Brasil/LatAm
•
Fuente única: SEC EDGAR oficial — cero scraping frágil
•
GAAP + IFRS unificados: desbloquea ADRs locales (GGAL,
PAM, etc.)
•
Sistema de flags de calidad — nunca se estima, se marca
•
Base de datos en 5 capas: catálogo → facts → ratios →
valuación → flags
•
API REST + frontend Next.js (módulo de presentación, a
construir)
•
3 jobs automatizados (precios, financials, cálculo)
•
Camino de migración SQLite → PostgreSQL ya definido
•
webshooks.com
2


Diferencia clave vs. la propuesta de Mayo: ya no partimos de una arquitectura sin probar. Hicimos ingeniería inversa de cada divergencia >10% entre EDGAR e Investing.com, diagnosticamos 10 causas
raíz y las corregimos.
Ratio
Divergencia mediana vs. Investing
Veredicto
EPS (anual)
0,0%
✓ Exacto
Margen Neto
0,0%
✓ Exacto
Payout
0,0%
✓ Exacto
PER (TTM)
1,3%
✓ Confiable
ROE (TTM, equity promedio)
0,4%
✓ Confiable
Crecimiento EPS 5 años
—
⚠ Metodología distinta de Investing
Hallazgo central
El bug de mayor impacto: deduplicar por el campo fy de XBRL en
vez del período (end) — el fy es el año del filing, no del dato, y
colapsaba años distintos. Corregirlo bajó las divergencias >10% de
107 a 39 (-64%).
Por qué importa para Catalaxia
Eliminamos la dependencia de scraping a Investing.com (frágil,
bloqueable, contra sus TOS) sin perder precisión. Riesgo legal y
de negocio: cero. Fuente 100% oficial y gratuita.
Control de calidad
429 de 553 empresas (78%) quedan completamente limpias (sin
flags) para screening serio. Las 124 restantes no se descartan ni se
inventan: quedan marcadas (roe_ns, fx, ni_fy) para decisión
humana.
webshooks.
Validación y Confiabilidad — lo nuevo desde Mayo
webshooks.com
3


Base de Datos & Jobs
API REST — FastAPI
Frontend — Next.js
webshooks.
Alcance del Proyecto
Catálogo de 8.021 empresas (sector/país/tamaño)
•
Facts GAAP+IFRS unificados (companyfacts XBRL)
•
Tabla ratios — 35+ por empresa, lista para servir
•
Sistema de flags de calidad (nunca se estima)
•
Migración SQLite → PostgreSQL (esquema ya definido)
•
Job 1A precios diario · Job 1B financials semanal · Job 2
cálculo
•
GET /api/cedears/screener (553 empresas, filtros)
•
GET /api/cedears/{ticker}/ratios
•
GET /api/cedears/{ticker}/precio
•
POST /api/jobs/ratios/{precios,financials,calculo}
•
GET /api/jobs/{id}/status
•
Documentación openapi.json
•
Screener: tabla 500+ empresas, columnas configurables
•
Filtros min/max: PER, Deuda/EBITDA, ROE, Precio
•
Filtro por flag de calidad ("solo datos limpios")
•
Sorting + paginación + exportar CSV
•
Detalle por ticker: gauge PER + barra 52 semanas
•
Panel de jobs con log en tiempo real
•
webshooks.com
4


BACKEND
Lenguaje
Python 3.11+
API Framework
FastAPI + Uvicorn
Precios
yfinance (Yahoo Finance)
Financials
SEC EDGAR XBRL — fuente única
Scraping
Investing.com (Playwright) — ya no es necesario
Base de datos
PostgreSQL 16 (hoy: SQLite validado)
ORM
SQLAlchemy 2.0 + asyncpg
Scheduler
APScheduler — cron jobs
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
Cambio clave vs. propuesta original: se elimina la dependencia de scraping a Investing.com para los ratios — reduce riesgo, costo de mantenimiento y superficie legal, sin perder precisión (validado
al 1,3% de divergencia).
webshooks.
Stack Tecnológico
webshooks.com
5


De la base completa de SEC EDGAR al dataset listo para producción — sin scraping, 100% trazable a la fuente oficial.
8.021
Empresas con ticker
en SEC EDGAR
100%
Cobertura del S&P 500
(large caps, ~19 años de historia)
553
Empresas con ratios
calculados hoy
429
Limpias (sin flags)
listas para screening
Composición del dataset actual
Segmento
Taxonomía
Estado
S&P 500 (large caps USA)
us-gaap
100% cubierto
ADRs Argentina (GGAL, PAM, BMA, CRESY, YPF...)
ifrs-full + us-gaap mixto
Desbloqueado (fix IFRS)
ADRs Brasil (VALE, ABEV, ITUB, GGB...)
ifrs-full
Desbloqueado (fix IFRS)
ADRs LatAm resto (UGP, NU, LOMA...)
ifrs-full
Desbloqueado (fix IFRS)
Cola larga USA (~7.458 restantes)
us-gaap
Pendiente (vía companyfacts.zip masivo)
webshooks.
Cobertura del Universo EDGAR
webshooks.com
6


Cada bloque tiene input/output definido y se puede re-ejecutar de forma independiente. El raw cache de SEC se descarga una sola vez (lo caro es el rate limit, no el cómputo).
1 · Catálogo
construir_catalogo.py
2 · Facts GAAP+IFRS
construir_base.py
3 · Ratios
calcular_ratios_base.py
4 · Valuación
precios_y_valuacion.py
5 · Flags de calidad
flags_calidad.py
Principio de diseño (heredado y reforzado): el raw cache (data/raw/*.json) es la fuente de verdad — se baja una vez de SEC EDGAR y la base se reconstruye sin volver a tocar la red. Si cambia una fórmula,
se recalcula en segundos, no en horas.
webshooks.
Arquitectura del Pipeline — 5 Bloques
8.021 empresas: ticker, CIK, sector,
país, tamaño
•
Todos los tags XBRL por empresa,
series temporales, ambas taxonomías
unificadas
•
~28 ratios fundamentales: márgenes,
ROE, deuda, FCF, CAGR 5y
•
PER, P/Book, EV/EBITDA con market
cap (USD) + FX para IFRS
•
ni_fy, roe_ns, fx, mktcap_rev — el
cinturón de seguridad
•
webshooks.com
7


Valentino — Backend A
Precios + integración de mercado
Mateo — Backend B
Financials + cálculo de ratios (ya validado)
Joaquín — Frontend A
Screener — tabla + filtros
Aldana — Frontend B
Procesos + detalle de ticker
Federico — Arquitecto · Tech Lead
webshooks.
Equipo de Trabajo
Job 1A: yfinance → precios_raw (cron diario)
•
Endpoints GET precio + POST jobs
•
APScheduler + retry ×3 por ticker
•
Pipeline EDGAR GAAP+IFRS, 35+ ratios, flags de calidad
•
Validación contra Investing (10 fixes, ver slide 3)
•
Tabla 500+ empresas, columnas de ratios
•
Filtros min/max + filtro por flag de calidad
•
Sorting + paginación + exportar CSV
•
Panel de jobs con polling en tiempo real
•
Detalle de ticker: gauge PER + barra 52s
•
Diseño de arquitectura de 5 bloques + esquema de BD
•
Metodología de validación EDGAR vs. Investing
•
Decisiones técnicas: TTM rodante, fallback GAAP/IFRS, flags
•
Integración, code review y QA del equipo
•
Deploy y soporte correctivo post-entrega
•
webshooks.com
8


Fase 0 — Validación de datos: COMPLETADA antes de empezar a cobrar. 553 empresas, 10 bugs corregidos, validado contra Investing.com. El riesgo técnico más grande del proyecto ya está resuelto.
Semana 1
Fundamentos
Semana 2
Integración de datos
Semana 3
Funcionalidad completa
Semana 4
Integración + QA
webshooks.
Cronograma — 4 Semanas de Implementación
Migración esquema BD a PostgreSQL
•
Endpoints base + cron jobs
•
Next.js + sidebar/topbar
•
Servir las 553 empresas vía API
•
Tabla screener con filtros reales
•
Ruta de detalle por ticker
•
Filtros min/max + flags de calidad
•
Jobs de actualización automática
•
Panel de procesos visual
•
Tests + manejo de errores
•
openapi.json documentado
•
QA y entrega final
•
webshooks.com
9


Inversión Total
USD 1.200
Precio fijo por proyecto · Sin costos adicionales
Incluye la validación de datos ya realizada (553 empresas) sin cargo extra
Soporte correctivo opcional: 3-12 meses x USD 125/mes, o único pago USD 800
Opciones de pago
Contado
Pago único al firmar
USD 1.200
10% de descuento si se contrata hoy mismo
Inicio inmediato
3 Cuotas
Sin interés
USD 400 × 3
Cuota 1: al firmar
Cuota 2: a la entrega
Cuota 3: mes posterior
6 Cuotas
Con ajuste
USD 250 × 6
Cuota 1: al firmar
Cuota 2: a la entrega
Cuotas 3-6: mensuales
webshooks.
Inversión y Financiación
webshooks.com
10


01
Aprobación
Confirmar la propuesta y definir el plan de pago.
02
Primer pago
50% al inicio o primera cuota según el plan
elegido.
03
Kickoff
1 hora con el equipo: revisión de las 553
empresas ya validadas + contrato de API.
04
Entrega
4 semanas de desarrollo + reportes semanales.
Empresa
webshooks
Inversión
USD 1.200
Proyecto
Módulo CEDEARs + ADRs LatAm (datos ya validados)
Duración
4 semanas
Inicio
Inmediato
Garantía
30 días post-entrega
Esta propuesta tiene validez de 30 días.
webshooks.
¿Cómo arrancamos?
webshooks.com
11
