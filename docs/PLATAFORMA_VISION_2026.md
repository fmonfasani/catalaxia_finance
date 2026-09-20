# Visión de Plataforma 2026
## De backoffice Catalaxia → SaaS financiero LATAM

**Autor:** Federico Monfasani  
**Fecha:** Septiembre 2026  
**Status:** Planificación

---

## El punto de partida real

Antes de proyectar, hay que ser honesto sobre dónde estamos:

| Capa | Estado actual |
|------|--------------|
| Pipeline SEC EDGAR | ✅ Producción — 553 empresas, 10 bugs corregidos, validado |
| Pipeline CNV | ✅ Producción — migración 2026-08-22 aplicada, 10/11 endpoints en 200 |
| API FastAPI | ✅ Parcialmente live — algunos endpoints aún en 500 |
| Frontend screener | ✅ Construido (Sprint 1-5), pendiente QA final (Sprint 6) |
| Deploy Hetzner | ⚠️ Migración desde Coolify → Hetzner directo (ver DEPLOY_HETZNER.md) |
| Sprint 6 | 🔄 En progreso — QA, polish, deployment final |

**Resumen:** El proyecto Catalaxia está al 85-90%. Lo que queda es cerrar Sprint 6, estabilizar producción, y entregar.

---

## La visión nueva: dos productos, una infraestructura

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INFRAESTRUCTURA COMPARTIDA                        │
│                                                                      │
│   SEC EDGAR (GAAP+IFRS) ──► ratios_pipeline ──► PostgreSQL          │
│   CNV Argentina          ──► cnv_pipeline   ──►                     │
│   yfinance (precios)     ──► precios_jobs   ──►                     │
│   BYMA (precios ARG)     ──► byma_jobs      ──►                     │
│                                                                      │
│                         FastAPI (backend único)                      │
│                     /api/v1/  ──  /api/v2/                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │                            │
    ┌─────────▼─────────┐      ┌──────────▼──────────────┐
    │  PRODUCTO A        │      │  PRODUCTO B              │
    │  catalaxia.com     │      │  screener.webshooks.com  │
    │                    │      │  (o dominio propio)      │
    │  Backoffice privado│      │                          │
    │  para Catalaxia    │      │  SaaS público            │
    │  S.A.              │      │  al estilo TIKR          │
    │                    │      │  (pero mejor)            │
    │  API exclusiva:    │      │                          │
    │  /api/v1/cata/*    │      │  + sección CEDEARs        │
    │  (auth requerida)  │      │  powered by Catalaxia    │
    └────────────────────┘      └──────────────────────────┘
```

---

## Fase 1 — Cerrar Catalaxia (lo que falta)

**Objetivo:** Entregar Sprint 6 limpio. App estable en producción.

### Tareas pendientes críticas

**Estabilización de producción (post-migración 2026-08-22):**
- [ ] Identificar el endpoint que sigue en 500 (1 de 11)
- [ ] Verificar que los 3 jobs corren en schedule en prod
- [ ] Confirmar datos: screener muestra 100+ empresas con ratios correctos
- [ ] Logging centralizado: docker logs en Hetzner + UptimeRobot

**Sprint 6 QA (CATA-111 a CATA-115):**
- [ ] QA Screener — filtros, export CSV, performance < 2s
- [ ] QA Detalle — 10+ empresas, gráficos, tabla histórica
- [ ] QA Watchlist + Comparador
- [ ] QA Jobs + Admin panel (logs en tiempo real)
- [ ] Security baseline (rate limiting, SQL injection, XSS)

**Deployment final:**
- [ ] CATA-104/105: Provisionar Hetzner CX22 + deploy automático vía GitHub Actions (ver DEPLOY_HETZNER.md)
- [ ] CATA-106: Docs finales (README, runbooks, architecture decisions)

**Criterio de "Catalaxia resuelto":**  
App en `catalaxia.webshooks.com`, todos los jobs corriendo, screener con 100+ empresas, 0 endpoints en 500, docs completos.

**Estimación:** 1-2 semanas desde hoy.

---

## Fase 2 — Preparar la infraestructura compartida

**Objetivo:** Antes de construir el SaaS, separar la capa de datos del backoffice Catalaxia para que sea reutilizable.

### API: dos namespaces en el mismo FastAPI

```
/api/v1/catalaxia/     → endpoints privados (requieren API key de Catalaxia S.A.)
/api/v1/public/        → endpoints del SaaS público (con rate limiting + plans)
/api/v1/admin/         → jobs, monitoring (requiere admin auth)
```

**Qué va en cada namespace:**

| Endpoint | Namespace | Acceso |
|---------|-----------|--------|
| `GET /screener` (553 empresas) | `/public/` | SaaS (freemium) |
| `GET /cedears/screener` | `/catalaxia/` | Catalaxia S.A. exclusivo |
| `GET /cedears/{ticker}/ratios` | `/catalaxia/` + `/public/` | Ambos |
| `GET /cnv/estados/{cuit}` | `/catalaxia/` | Exclusivo Catalaxia |
| `GET /cnv/ratios` | `/catalaxia/` | Exclusivo Catalaxia |
| `GET /precios/{ticker}` | `/public/` | SaaS |
| `POST /jobs/*` | `/admin/` | Admin |

**El punto clave:** Los datos de CNV (balances argentinos, ratios locales) son el diferenciador exclusivo de Catalaxia S.A. No se exponen en el SaaS público. Solo el screener de US stocks + CEDEARs/ADRs va al SaaS.

### Base de datos: sin cambios de esquema

El esquema actual ya es multi-producto. Solo hay que:
- Agregar tabla `api_keys` (qué cliente tiene qué permisos)
- Agregar tabla `plans` (freemium / pro para el SaaS)
- Agregar columna `source` en logs de jobs para distinguir contextos

**Estimación:** 1 semana (post-entrega Sprint 6).

---

## Fase 3 — Construir el SaaS público (TIKR mejorado)

**Objetivo:** Screener financiero público, mejor que TIKR, con el diferenciador de datos argentinos.

### Por qué puede ganarle a TIKR

| Dimensión | TIKR | Este SaaS |
|-----------|------|-----------|
| Tech stack | Vue 2 + Vuetify (legacy) | Next.js 14 + shadcn/ui (moderno) |
| Fuente de datos | Scraping (frágil, caro) | SEC EDGAR oficial (gratis, legal) |
| IFRS (LatAm) | Parcial | ✅ GAAP + IFRS unificado (ya hecho) |
| CEDEARs Argentina | ❌ | ✅ Cobertura local exclusiva |
| Datos CNV | ❌ | ✅ Balances argentinos reales |
| Precio | Freemium con paywall agresivo | Freemium más generoso en v1 |
| Mobile | Malo | shadcn/ui responsive desde el día 1 |
| Bundle | ~desconocido | < 1MB (vs 12MB de Koyfin) |

### Features del SaaS v1

**Screener (US Stocks + ADRs LatAm):**
- 553 empresas con 35+ ratios (lo que ya existe)
- Filtros: PER, ROE, Margen Neto, Deuda/EBITDA, FCF
- Sort + paginación + export CSV
- Flags de calidad visibles (el cinturón de seguridad)
- Blink-up / blink-down en precios (token CSS, no JS pesado)

**Detalle por ticker:**
- Gauge PER vs histórico del sector
- Barra 52 semanas
- Ratios históricos (6 años de historia ya disponible)
- Link a filing original en SEC EDGAR

**Sección "CEDEARs Argentina" (powered by Catalaxia):**
- Tabla de CEDEARs con precio ARS + equivalente USD (MEP)
- Ratios en USD (SEC EDGAR) + precio en ARS (BYMA)
- Ratio de conversión automático
- Badge "Datos CNV disponibles" para empresas con balances argentinos

**Modelo freemium:**
- Free: screener con 20 ratios, 50 empresas por búsqueda, sin export
- Pro ($9/mes): todos los ratios, export CSV, historial completo, CEDEARs section
- Team ($29/mes): múltiples usuarios, API access, alertas

### Stack técnico del SaaS

```
Frontend:  Next.js 14 + TypeScript + Tailwind + shadcn/ui
           (mismo que Catalaxia — reusar componentes)

Backend:   FastAPI (mismo — nuevo namespace /public/)

Auth:      NextAuth.js — email magic link + Google OAuth
           (Catalaxia usa el mismo patrón, separar por JWT claims)

Pagos:     Stripe — subscription plans (free/pro/team)

Analytics: Posthog self-hosted (1 tool, no 5 como Koyfin)

Deploy:    Hetzner CX32 + GitHub Actions (mismo server)
           screener.{dominio}.com

DB:        PostgreSQL compartido (tabla api_keys + plans encima)
```

### Lo que NO hacer (lecciones de Koyfin + TIKR)

- ❌ Moment.js → usar `date-fns`
- ❌ Bundle > 3MB → shadcn/ui + tree shaking
- ❌ Dark-only → light mode desde el día 1 (Koyfin perdió usuarios)
- ❌ 5 analytics simultáneos → solo Posthog
- ❌ Font paga (aktiv-grotesk) → Inter libre
- ❌ FA Pro → Lucide Icons
- ❌ Sin virtualización → TanStack Virtual para screener 500+ filas

**Estimación:** 6-8 semanas de desarrollo activo.

---

## Fase 4 — Integración Catalaxia dentro del SaaS

**Objetivo:** El frontend del SaaS tiene una sección especial para Catalaxia S.A. con su branding y datos exclusivos.

### Arquitectura de la integración

```
SaaS público (screener.com)
├── /screener          → Todos los usuarios
├── /stocks/{ticker}   → Todos los usuarios
├── /cedears           → Free (datos básicos)
│   └── /cedears/pro   → Plan Pro (datos completos)
└── /catalaxia         → Solo usuarios con API key Catalaxia S.A.
    ├── Screener CEDEARs con datos CNV
    ├── Balances comparados (SEC vs CNV)
    └── Panel admin de jobs Catalaxia
```

**Dos opciones de deploy:**

**Opción A — Embedded (recomendada para v1):**  
El frontend del SaaS incluye la sección `/catalaxia` como rutas protegidas. Un usuario de Catalaxia S.A. se autentica y ve su sección privada dentro del mismo dominio del SaaS. Más simple operativamente.

**Opción B — White-label:**  
`catalaxia.{dominio}.com` es un subdominio del SaaS que solo sirve las rutas de Catalaxia. Permite branding separado pero más infraestructura.

**Recomendación:** Empezar con Opción A, migrar a B si Catalaxia S.A. lo pide explícitamente.

---

## Roadmap de alto nivel

```
Sep 2026    Oct 2026    Nov 2026    Dic 2026    Ene 2027
   │            │           │           │           │
   ├──[F1]──────┤           │           │           │
   │ Cerrar     │           │           │           │
   │ Catalaxia  │           │           │           │
   │            ├──[F2]──┤  │           │           │
   │            │ API     │  │           │           │
   │            │ shared  │  │           │           │
   │            │         ├──────[F3]───────────────┤
   │            │         │  SaaS público (v1)      │
   │            │         │                         │
   │            │         │           ├──[F4]───────┤
   │            │         │           │ Integración │
   │            │         │           │ Catalaxia   │
```

**Hitos:**
- **Sep 30**: Catalaxia entregado y estable en producción
- **Oct 15**: API refactorizada con dos namespaces
- **Dic 1**: SaaS v1 en beta (screener público funcional)
- **Ene 15**: CEDEARs section + integración Catalaxia S.A.

---

## Decisiones técnicas clave

### ¿Un repo o dos?

**Recomendación: monorepo con Turborepo**

```
catalaxia-platform/
├── apps/
│   ├── api/              → FastAPI (backend único)
│   ├── catalaxia/        → Frontend actual (Next.js)
│   └── screener/         → Nuevo SaaS frontend (Next.js)
├── packages/
│   ├── ui/               → shadcn/ui components compartidos
│   ├── types/            → TypeScript types compartidos
│   └── config/           → ESLint, Tailwind base config
└── infra/
    └── hetzner/          → docker-compose.yml, nginx.conf, GitHub Actions workflow
```

**Por qué monorepo:** Los dos frontends comparten el 60% de componentes (tablas, filtros, charts). Duplicar es deuda técnica innecesaria.

### ¿Real-time en el SaaS?

Para v1: **no**. Polling cada 30 segundos es suficiente para un screener. Los precios en tiempo real (Socket.io) se agregan en v2 si los usuarios lo piden. Evita la complejidad operativa de Redis pub/sub desde el día 1.

### ¿Autenticación?

- Catalaxia S.A. ya tiene auth en el backoffice (admin panel protegido)
- El SaaS necesita auth pública: **NextAuth.js** con Google OAuth + email magic link
- Un JWT con claim `{ plan: "free|pro|team", org: "catalaxia|public" }` diferencia contextos

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| yfinance rompe de nuevo (ya pasó) | Alta | Medio | Pin version + test automatizado de precios semanales |
| SEC EDGAR cambia la API | Baja | Alto | Cache local de raw JSONs (ya implementado) — recalcula sin tocar la red |
| Catalaxia S.A. no renueva el contrato | Media | Medio | El SaaS público no depende de ellos — son un cliente más |
| Competidores copies el diferenciador CNV | Baja | Alto | Mover rápido en v1; los datos CNV requieren meses de ingeniería para replicar |
| Bundle crece descontrolado | Media | Bajo | Bundle analyzer en CI desde el día 1; alerta si > 1MB |

---

## Próximos pasos concretos

**Esta semana:**
1. Completar QA Sprint 6 (CATA-111 a CATA-115)
2. Identificar y corregir el endpoint que sigue en 500
3. Confirmar jobs corriendo en producción

**Próxima semana:**
1. CATA-104 / CATA-105 deploy final
2. CATA-106 docs
3. Entregar Sprint 6 a Catalaxia S.A.

**Después de la entrega:**
1. Brainstorm del nombre y dominio del SaaS público
2. Diseño del modelo freemium (qué va en free vs. pro)
3. Refactor API para namespace `/public/`
4. Setup del monorepo con Turborepo
