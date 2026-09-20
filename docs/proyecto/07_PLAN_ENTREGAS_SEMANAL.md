# Plan de entregas semanal (avance + rendimiento)

> El corazón del seguimiento interno. Cada semana tiene **un entregable por persona** con criterio
> de aceptación, y una **rúbrica de rendimiento**. Los entregables son una herramienta interna:
> el cliente (Marcelo) **no aprueba**, pero se usan para medir avance y desempeño del equipo.
> Cadencia: **cierre y demo los viernes.** · **Arranque: miércoles 15/07/2026.**

## Calendario

| Sprint | Fechas | Cierre / demo |
|---|---|---|
| Sprint 1 · Fundamentos | **Mié 15 → Vie 24 Jul** | Vie 24 Jul |
| Sprint 2 · Integración | Lun 27 → Vie 31 Jul | Vie 31 Jul |
| Sprint 3 · Funcionalidad | Lun 3 → Vie 7 Ago | Vie 7 Ago |
| Sprint 4 · QA + entrega | Lun 10 → Vie 14 Ago | **Entrega Vie 14 Ago** |

> El Sprint 1 arranca a mitad de semana (Mié 15) y corre hasta el Vie 24 — esa semana larga es
> ideal para el setup de infra dockerizada (Postgres + API en la VPS). Kickoff con Marcelo: antes
> del miércoles 15 (ver `09`).

---

## Fase 0 — Data (ya completada ✅)
572 empresas · 3 mercados · doble precio ARS/USD · ratios CEDEAR/ADR oficiales · CCL validado
(1,3 %) · modelo 2 niveles · provenance. **El riesgo técnico grande ya está resuelto.**

---

## Semana 1 — Fundamentos · Mié 15 → Vie 24 Jul
**Meta:** Postgres + API **dockerizados** en la VPS Hetzner (`/opt/catalaxia`) con datos reales + front consumiendo el contrato (mock).

| Persona | Tareas | Entregable de la semana |
|---|---|---|
| **Federico** | Esquema PostgreSQL + migración (572/733) en la VPS · deploy API base + HTTPS + CORS · **entregar contrato de API (`04`) + mocks** el día 1 | Postgres cargado + `/cobertura` respondiendo por HTTPS + URL de staging avisada |
| **Mateo** | Scaffold FastAPI · conexión a Postgres (SQLAlchemy async) · `GET /empresas` + `GET /cobertura` · `/health` | `GET /empresas` devuelve datos reales desde Postgres |
| **Joaquín** | Scaffold Next.js (sidebar/topbar) · tabla screener contra **mocks** del contrato | Tabla de empresas navegable (con datos mock) |
| **Aldana** | Base compartida del front · ruta de detalle contra **mocks** · componentes base (cards, chips) | Página de detalle maquetada (con datos mock) |

**Aceptación S1:** la API sirve `/empresas` real desde la VPS **y** el front muestra la tabla desde
el contrato. (No hace falta que el front ya pegue a la VPS: eso es S2.)

---

## Semana 2 — Integración de datos · Lun 27 → Vie 31 Jul
**Meta:** el front deja los mocks y consume la **VPS real**; screener + detalle con 572 empresas.

| Persona | Tareas | Entregable |
|---|---|---|
| **Federico** | Cargar/verificar 733 instrumentos + dividendos ADR · endpoints `/instrumentos` y `/empresas/{id}` con Mateo · **asistir a los front** a apuntar a la VPS (CORS, staging) | Front consumiendo la VPS sin bloqueos |
| **Mateo** | `GET /empresas/{id}` (fundamentales + instrumentos anidados) · `GET /instrumentos` con filtros · paginación | Endpoints de detalle/instrumentos según contrato |
| **Joaquín** | Screener contra API real · toggle **ARS/USD** · sorting + paginación | Screener real con 572 empresas y toggle de moneda |
| **Aldana** | Detalle contra API real · panel de fundamentales + **panel de instrumentos** | Detalle real con panel de instrumentos (ISIN/precio/ratio) |

**Aceptación S2:** abrir el front en staging y ver las 572 empresas reales + un detalle con sus
instrumentos, todo desde la VPS.

---

## Semana 3 — Funcionalidad completa · Lun 3 → Vie 7 Ago
**Meta:** filtros, flags, jobs y las vistas de valor (CEDEAR, dividendos).

| Persona | Tareas | Entregable |
|---|---|---|
| **Federico** | Jobs + scheduler en la VPS · `POST /jobs` + `GET /jobs/{id}/status` · monitoreo básico | Jobs disparables desde la API, con estado |
| **Mateo** | Filtros compuestos en `/empresas` (per_lt, roe_gt, solo_limpias…) · endpoints de jobs · tests de endpoints | Filtros server-side + jobs andando |
| **Joaquín** | Filtros min/max + filtro por **flag de calidad** · **export CSV** · **panel de jobs** en vivo | Screener con filtros, export y panel de jobs |
| **Aldana** | **Dividendos ADR + yield** · **vista CEDEAR** (precio con ratio) · **comparador** · chips de provenance | Vistas CEDEAR/dividendos/comparador funcionando |

**Aceptación S3:** filtrar por PER/ROE + "solo limpias", exportar CSV, disparar un job y verlo en
el panel, y ver la vista CEDEAR y los dividendos de un ADR.

---

## Semana 4 — Integración + QA + entrega · Lun 10 → Vie 14 Ago
**Meta:** producto integrado, probado, desplegado. **Entrega: viernes 14/08.**

| Persona | Tareas | Entregable |
|---|---|---|
| **Federico** | Hardening infra · backups verificados · deploy prod · **QA de integración** (`10`) · code review final | Producto desplegado + checklist QA en verde |
| **Mateo** | Tests backend · manejo de errores · `openapi.json` documentado | API testeada y documentada |
| **Joaquín** | Estados vacíos/loading/error · responsive · pulido del screener | Screener pulido y robusto |
| **Aldana** | Estados/loading/error · responsive · disclaimers por universo · pulido del detalle | Detalle pulido + disclaimers de confianza |

**Aceptación S4 (entrega):** todo el checklist de `01_ALCANCE_Y_DOD.md §6` + `10_QA_Y_RIESGOS.md`
en verde, producto corriendo en la VPS.

---

## Rúbrica de rendimiento (uso interno, por persona y por semana)

Puntuar 1–5 cada viernes. Sirve para dar feedback concreto, no para castigar.

| Criterio | Qué mira | 1 | 3 | 5 |
|---|---|---|---|---|
| **Entrega** | ¿cumplió el entregable de la semana? | no llegó | parcial | completo y a tiempo |
| **Calidad** | ¿pasó review sin re-trabajo grande? | muchos fixes | algunos | limpio |
| **Autonomía** | ¿resolvió o pidió ayuda a tiempo? | se trabó callado | pidió tarde | destrabó solo/a tiempo |
| **Colaboración** | ¿ayudó, comunicó, respetó el contrato? | aislado | ok | sumó al equipo |

**Cómo se registra:** una fila por persona/semana en una planilla (o en Jira, campo custom). El
promedio da una señal de tendencia — lo importante es la **conversación de 5 min** que habilita.

## Reporte de los viernes (15 min, todo el equipo)
1. Cada uno muestra su entregable (demo, no slides).
2. Se marca cada entregable como ✅ / ⚠ / ❌ y se anota bloqueo si lo hubo.
3. Se completa la rúbrica.
4. Se confirman las tareas de la semana siguiente en Jira.
