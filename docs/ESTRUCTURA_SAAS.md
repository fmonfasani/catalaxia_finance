# Estructura del Proyecto — Plataforma SaaS

**Repo:** `catalaxia-platform` (monorepo nuevo)  
**Herramienta:** Turborepo  
**Fecha:** Septiembre 2026

---

## Árbol de directorios completo

```
catalaxia-platform/
│
├── apps/
│   ├── api/                          ← FastAPI backend (migrado desde repo actual)
│   │   ├── app/
│   │   │   ├── main.py               ← Entry point, CORS, middleware
│   │   │   ├── config.py             ← Settings desde env vars
│   │   │   ├── database.py           ← SQLAlchemy engine + session
│   │   │   ├── dependencies.py       ← Auth, rate limiting, plan checks
│   │   │   │
│   │   │   ├── routers/
│   │   │   │   ├── public.py         ← GET /api/v1/public/* (SaaS, freemium)
│   │   │   │   ├── catalaxia.py      ← GET /api/v1/catalaxia/* (privado, API key)
│   │   │   │   ├── admin.py          ← POST /api/v1/admin/jobs/* (interno)
│   │   │   │   └── health.py         ← GET /health (monitoring)
│   │   │   │
│   │   │   ├── models/
│   │   │   │   ├── ticker.py
│   │   │   │   ├── ratio.py
│   │   │   │   ├── screener.py
│   │   │   │   ├── api_key.py        ← NUEVO: autenticación de clientes
│   │   │   │   └── plan.py           ← NUEVO: freemium / pro / team
│   │   │   │
│   │   │   ├── services/
│   │   │   │   ├── screener.py       ← lógica de filtros + paginación
│   │   │   │   ├── ratios.py         ← cálculo y lectura de ratios
│   │   │   │   ├── precios.py        ← precio actual + 52w
│   │   │   │   └── cnv.py            ← balances CNV (solo namespace catalaxia)
│   │   │   │
│   │   │   └── jobs/
│   │   │       ├── scheduler.py      ← APScheduler setup
│   │   │       ├── job_precios.py    ← Job 1A: yfinance → precios_raw
│   │   │       ├── job_financials.py ← Job 1B: SEC EDGAR → financials_raw
│   │   │       └── job_ratios.py     ← Job 2: recalcular ratios
│   │   │
│   │   ├── tests/
│   │   │   ├── test_routers/
│   │   │   ├── test_services/
│   │   │   └── conftest.py
│   │   │
│   │   ├── alembic/                  ← migraciones de BD
│   │   │   ├── versions/
│   │   │   └── env.py
│   │   │
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── pyproject.toml
│   │
│   ├── screener/                     ← SaaS público (NUEVO — Next.js 14)
│   │   ├── app/
│   │   │   ├── layout.tsx            ← Root layout (font, theme provider)
│   │   │   ├── page.tsx              ← Landing page
│   │   │   │
│   │   │   ├── (auth)/               ← Route group: sin navbar principal
│   │   │   │   ├── login/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── register/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── layout.tsx
│   │   │   │
│   │   │   ├── (public)/             ← Route group: acceso libre
│   │   │   │   ├── layout.tsx        ← Navbar + footer
│   │   │   │   ├── screener/
│   │   │   │   │   └── page.tsx      ← Tabla principal con filtros
│   │   │   │   ├── stocks/
│   │   │   │   │   └── [ticker]/
│   │   │   │   │       └── page.tsx  ← Detalle de empresa
│   │   │   │   └── cedears/
│   │   │   │       └── page.tsx      ← Vista CEDEARs (preview limitado)
│   │   │   │
│   │   │   └── (protected)/          ← Route group: requiere login
│   │   │       ├── layout.tsx        ← Navbar con plan badge
│   │   │       ├── dashboard/
│   │   │       │   └── page.tsx      ← Home del usuario logueado
│   │   │       ├── watchlist/
│   │   │       │   └── page.tsx
│   │   │       ├── settings/
│   │   │       │   └── page.tsx      ← Plan, billing, API key
│   │   │       └── catalaxia/        ← Sección exclusiva Catalaxia S.A.
│   │   │           ├── layout.tsx    ← Solo accesible con plan "catalaxia"
│   │   │           ├── page.tsx      ← Dashboard Catalaxia
│   │   │           ├── screener/
│   │   │           │   └── page.tsx  ← Screener CEDEARs con datos CNV
│   │   │           └── balances/
│   │   │               └── [cuit]/
│   │   │                   └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── screener/
│   │   │   │   ├── ScreenerTable.tsx
│   │   │   │   ├── ScreenerFilters.tsx
│   │   │   │   ├── ColumnPicker.tsx
│   │   │   │   └── ExportButton.tsx
│   │   │   ├── stock/
│   │   │   │   ├── RatioGauge.tsx
│   │   │   │   ├── PriceBar52w.tsx
│   │   │   │   ├── RatiosTable.tsx
│   │   │   │   └── StockHeader.tsx
│   │   │   ├── layout/
│   │   │   │   ├── Navbar.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Footer.tsx
│   │   │   └── shared/
│   │   │       ├── PlanBadge.tsx
│   │   │       ├── QualityFlag.tsx   ← muestra flags de calidad de datos
│   │   │       └── BlinkPrice.tsx    ← animación blink-up/blink-down
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts                ← fetch wrapper con auth headers
│   │   │   ├── auth.ts               ← NextAuth config
│   │   │   ├── stripe.ts             ← Stripe client
│   │   │   └── formatters.ts         ← números financieros, porcentajes
│   │   │
│   │   ├── hooks/
│   │   │   ├── useScreener.ts        ← SWR hook para screener
│   │   │   ├── useTicker.ts          ← SWR hook para detalle
│   │   │   └── usePlan.ts            ← hook para plan del usuario
│   │   │
│   │   ├── styles/
│   │   │   ├── globals.css           ← tokens CSS: blink-up, blink-down
│   │   │   └── tokens.css            ← design tokens (colores, tipografía)
│   │   │
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── catalaxia/                    ← Backoffice existente (ya construido)
│       └── ...                       ← migrar desde repo actual
│
├── packages/
│   ├── ui/                           ← Componentes shadcn/ui compartidos
│   │   ├── src/
│   │   │   ├── components/
│   │   │   │   ├── data-table/       ← Tabla con TanStack Table + Virtual
│   │   │   │   ├── ratio-gauge/      ← Gauge de PER/ROE reutilizable
│   │   │   │   ├── price-sparkline/  ← Mini chart 52 semanas
│   │   │   │   ├── quality-badge/    ← Badge de flag de calidad
│   │   │   │   └── index.ts
│   │   │   └── lib/
│   │   │       └── utils.ts          ← cn(), clsx helpers
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   ├── types/                        ← TypeScript interfaces compartidas
│   │   ├── src/
│   │   │   ├── ticker.ts             ← Ticker, Company, Sector
│   │   │   ├── ratio.ts              ← Ratio, RatioValue, QualityFlag
│   │   │   ├── screener.ts           ← ScreenerFilters, ScreenerRow, Plan
│   │   │   ├── api.ts                ← ApiResponse<T>, PaginatedResponse<T>
│   │   │   └── index.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── config/                       ← Configs compartidas
│       ├── eslint/
│       │   └── index.js
│       ├── tailwind/
│       │   └── base.ts               ← tokens base (colores, fonts)
│       └── typescript/
│           └── base.json
│
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml        ← Producción (usa imágenes de ghcr.io)
│   │   ├── docker-compose.dev.yml    ← Dev local (build desde source)
│   │   └── docker-compose.test.yml   ← CI (con DB efímera)
│   └── nginx/
│       ├── api.conf                  ← proxy → api:8100
│       ├── screener.conf             ← proxy → screener:3000
│       └── catalaxia.conf            ← proxy → catalaxia:3001
│
├── .github/
│   └── workflows/
│       ├── deploy.yml                ← Deploy a Hetzner (push a main)
│       ├── backend-ci.yml            ← pytest + coverage
│       └── frontend-ci.yml           ← lint + typecheck + build check
│
├── turbo.json                        ← Pipeline de Turborepo
├── package.json                      ← Root (workspaces)
├── pnpm-workspace.yaml
└── README.md
```

---

## Responsabilidades de cada capa

### `apps/api` — Backend único para todo

| Router | Quién lo usa | Auth |
|--------|-------------|------|
| `/api/v1/public/*` | SaaS screener | Rate limiting por IP + plan JWT |
| `/api/v1/catalaxia/*` | Catalaxia S.A. | API key en header |
| `/api/v1/admin/*` | Interno / jobs | Admin JWT |

El backend **no cambia** al agregar el SaaS — solo se agrega el router `public.py` con sus propios endpoints y rate limits.

### `apps/screener` — SaaS público

Tres route groups de Next.js:
- `(auth)` — login / register, sin navbar
- `(public)` — screener, detalle de ticker — accesible sin login (con límites freemium aplicados en la API)
- `(protected)` — dashboard, watchlist, settings, y la sección `/catalaxia` exclusiva

### `packages/ui` — Componentes compartidos

Los dos frontends (`screener` + `catalaxia`) importan desde `@catalaxia/ui`. Al mejorar un componente (ej: la tabla del screener), ambas apps se benefician.

### `packages/types` — Tipos compartidos

Un solo lugar donde vive `ScreenerRow`, `Ratio`, `QualityFlag`, etc. El backend Python tiene su equivalente en Pydantic; los tipos TypeScript se generan o sincronizan manualmente.

---

## Flujo de datos del SaaS

```
Usuario abre /screener
        │
        ▼
Next.js page.tsx
  → useScreener({ filters, page }) [SWR hook]
      │
      ▼
  GET /api/v1/public/screener?per_max=20&roe_min=0.15&page=1
      │
      ├── middleware: check JWT plan (free → limitar a 50 empresas)
      ├── middleware: rate limit (100 req/min por IP)
      │
      ▼
  FastAPI screener service
  → SELECT * FROM ratios WHERE ... ORDER BY per ASC LIMIT 50
      │
      ▼
  JSON: { rows: [...], total: 553, page: 1, plan: "free" }
      │
      ▼
  ScreenerTable (TanStack Table + TanStack Virtual)
  → 500+ filas virtualizadas, scroll suave
  → BlinkPrice: CSS transition en celdas de precio
  → QualityFlag: badge si el dato tiene flags
```

---

## Modelo de datos nuevo (adiciones al esquema actual)

```sql
-- Clientes con acceso a la API
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,                    -- "Catalaxia S.A."
    key_hash    TEXT NOT NULL UNIQUE,             -- bcrypt del API key
    plan        TEXT NOT NULL DEFAULT 'public',  -- public | catalaxia | admin
    active      BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Usuarios del SaaS público
CREATE TABLE saas_users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL UNIQUE,
    plan        TEXT NOT NULL DEFAULT 'free',    -- free | pro | team
    stripe_id   TEXT,                            -- Stripe customer ID
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlists
CREATE TABLE watchlist_items (
    user_id     UUID REFERENCES saas_users(id),
    ticker      TEXT NOT NULL,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, ticker)
);
```

Solo 3 tablas nuevas. El esquema de ratios, precios, CNV no se toca.

---

## Convenciones del monorepo

### Nombrado de paquetes
```
@catalaxia/ui       → packages/ui
@catalaxia/types    → packages/types
@catalaxia/config   → packages/config
```

### Scripts desde la raíz
```bash
pnpm dev                    # levanta todos los apps en paralelo
pnpm dev --filter screener  # solo el SaaS frontend
pnpm dev --filter api       # solo el backend (uvicorn)
pnpm build                  # build de todos los apps
pnpm test                   # tests de todos los apps
pnpm lint                   # lint de todos los packages
```

### Variables de entorno
```
apps/api/.env           ← DATABASE_URL, SECRET_KEY, etc.
apps/screener/.env.local ← NEXT_PUBLIC_API_URL, NEXTAUTH_SECRET, STRIPE_KEY
apps/catalaxia/.env.local ← idem
```
Las variables compartidas (ej: API URL) viven en cada app, no en la raíz — para poder deployar apps independientemente.

---

## Archivos de configuración (ver `/docs/scaffold/`)

Los archivos listos para copiar están en:
```
docs/scaffold/
├── turbo.json
├── package.json              ← root
├── pnpm-workspace.yaml
├── packages/
│   └── types/src/
│       ├── ticker.ts
│       ├── ratio.ts
│       ├── screener.ts
│       └── api.ts
├── apps/
│   └── screener/
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       └── styles/
│           ├── globals.css
│           └── tokens.css
└── infra/
    └── docker/
        ├── docker-compose.yml
        └── docker-compose.dev.yml
```
