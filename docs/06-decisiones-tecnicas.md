# 06 — Decisiones técnicas clave

> Fuente: `Backend — Estrategia y decisiones técnicas.docx`. Cada decisión
> acá tuvo una alternativa descartada explícitamente — se documenta el por qué.

## SEC EDGAR vs TIKR — la decisión más importante del proyecto

**Decisión: SEC EDGAR como fuente principal. TIKR queda descartado.**

| | TIKR | SEC EDGAR XBRL |
|---|---|---|
| Datos | Ya procesados y formateados | Crudos, hay que calcular TTM/EBITDA manualmente |
| Costo | — | Gratis, sin auth |
| Legalidad | **Prohíbe explícitamente el scraping** en sus TOS, cierra cuentas | Uso programático explícitamente permitido |
| Riesgo | De negocio — perder la cuenta afecta también el uso manual | Ninguno |
| Estabilidad | El DOM puede cambiar y romper el scraper sin aviso | API estable, formato documentado |

TIKR de hecho toma sus datos de la misma SEC. Ir directo a la fuente elimina
un intermediario frágil y de alto riesgo. **TIKR no se usa en ningún punto
del pipeline de producción.**

Caso límite: empresas extranjeras que no reportan a la SEC en XBRL (algunos
ADRs indios, brasileños, europeos). Para esos casos, fallback a Investing.com
vía Playwright — no a TIKR.

## Modo headed vs headless para Playwright (Investing.com)

**Decisión: modo headed, o headless con stealth, según el entorno de deploy.**

Investing.com detecta bots por: propiedades de JS distintas en headless
(`navigator`, dimensiones de pantalla en cero), ausencia de cookies/historial,
y comportamiento "demasiado perfecto" (sin variación de timing).

| Opción | Cuándo usarla |
|---|---|
| Headed + `Xvfb` (pantalla virtual) | Servidor sin GUI, máxima confiabilidad |
| Headless + `playwright-stealth` | Más fácil de deployar, no 100% confiable |
| Perfil de usuario real (cookies/sesión) | Más robusto — el sitio ve el mismo browser que el humano |

Regla dura: **nunca correr más de un browser en paralelo contra Investing.com**
— aumenta la probabilidad de detección y de ban temporal de IP.

## TTM — por qué no se puede sumar los últimos 4 trimestres a lo bruto

Las empresas USA reportan en `10-Q` valores **YTD acumulados** desde el inicio
del año fiscal. El dato de Q3 de Income Statement ya incluye Q1+Q2+Q3 — no es
"el trimestre 3 solo".

Sumar ingenuamente los últimos 4 registros `form=10-Q` triplica Q1 y duplica
Q2. La solución es detectar la duración del período (`periodo_end -
periodo_start`) y aplicar la fórmula correcta según si es standalone o YTD.
Detalle completo en [`02-jobs.md`](02-jobs.md#lógica-de-ttm-el-cálculo-más-importante).

## EBITDA no existe en XBRL — ni en GAAP ni en NIIF

Es una métrica no-GAAP. Se construye sumando:

```
EBITDA = NetIncomeLoss + D&A + InterestExpense + IncomeTaxExpense
```

Los cuatro componentes sí existen en SEC EDGAR por separado. Si alguno falta,
el ratio que depende de EBITDA queda en `NULL` — **nunca se aproxima ni se
estima**, porque un valor estimado sin marcar como tal es peor que no
tener el dato.

## Una sola sesión de browser compartida entre Backend A y B (Investing.com)

Margen Neto y ROE (Backend B) y PER/EPS/Crec.EPS (Backend A) están en la
misma sección de Investing.com por ticker. Decisión: **una sola visita por
ticker extrae los 5 valores**, no visitas separadas por colaborador.

Trade-off aceptado: requiere coordinación entre Valentino y Mateo sobre quién
corre el scraper de Investing — pero reduce el tiempo total de scraping y el
riesgo de detección de bot a la mitad.

## UPSERT vs INSERT — depende de si la fuente es mutable

| Tabla | Estrategia | Por qué |
|---|---|---|
| `precios_raw` | UPSERT | El precio de ayer no importa, solo el último |
| `financials_raw` | INSERT con `ON CONFLICT DO NOTHING` | Los datos de SEC son inmutables; un duplicado exacto se ignora, una enmienda se inserta |
| `ratios` | UPSERT | Solo importa el último cálculo |

## Endpoint JSON interno de Investing.com — la pregunta abierta más importante

Antes de implementar Playwright contra Investing.com, **investigar si el
sitio tiene un endpoint JSON interno** que el browser consume al cargar la
página (común en sitios con frontend dinámico). Si existe, reduce el scraping
de minutos a segundos por ticker y elimina la dependencia del DOM —
cambiaría la arquitectura completa de Backend A y B.

> **Acción pendiente para Valentino y Mateo antes de escribir el scraper de
> Investing.com**: inspeccionar el Network tab del browser al cargar una
> página de ticker y buscar requests JSON/XHR antes de asumir que hace falta
> Playwright completo.

## El contrato a acordar antes de escribir código

1. Schema de BD completo, con tipos, nullables y constraints (ver `migrations/001_initial_schema.sql`).
2. Formato de `GET /api/jobs/{job_id}/status` — `processed`/`total` como números, no porcentaje (ver `docs/04-contrato-api.md`).
3. Comportamiento ante fallo parcial de un job: **no se reinicia desde cero**, los tickers ya procesados quedan, solo se reintentan los fallidos en `job_errores`.
