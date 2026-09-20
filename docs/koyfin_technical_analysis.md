# Koyfin — Análisis Técnico Profundo

**URL analizada:** https://app.koyfin.com  
**Fecha:** 2026-09-07  
**Método:** Inspección de bundles JS, scripts externos, interceptación de requests, análisis de fiber React

---

## 1. Bundler y build system

| Componente | Valor |
|-----------|-------|
| **Bundler** | **Rolldown** (Rust, del equipo de Vite — bleeding edge, apenas público) |
| Output format | ES Modules (modulepreload nativo) |
| Code splitting | Sí — chunks por ruta (`m.ch0`, `m.ch1`, `m.ch2`) |
| Hash en filenames | Sí (`bundle.main.CQghw4oO.js`) — cache busting por contenido |
| Polyfill | `bundle.modulepreload-polyfill` — soporte para browsers sin modulepreload |

Koyfin es uno de los primeros productos en producción usando **Rolldown**, el reemplazo de Rollup escrito en Rust. Esto indica un equipo frontend muy al día con el ecosistema.

---

## 2. Inventario completo de bundles y tamaños

| Bundle | Tamaño (sin comprimir) | Contenido probable |
|--------|----------------------|-------------------|
| `bundle.vendor.react.js` | **949 KB** | React + ReactDOM core |
| `bundle.vendor.co.js` | **3.590 KB** | Design system propio con atomic CSS-in-JS (prefijo `fx-*`) |
| `bundle.vendor~main.js` | **2.250 KB** | Dependencias de producción (axios, immer, socket.io, d3, moment, zod, yup, segment) |
| `bundle.vendor~main~oidcMicrosoftRedirect.js` | **8 KB** | Página de redirect OIDC para Microsoft SSO |
| `bundle.main.js` | **1.922 KB** | Lógica principal de la app |
| `bundle.m.ch0.js` | **2.856 KB** | Route chunk 0 — módulo más pesado (con virtualización de tablas) |
| `bundle.m.ch1.js` | ~estimado | Route chunk 1 |
| `bundle.m.ch2.js` | ~estimado | Route chunk 2 |
| `bundle.base.js` | ~pequeño | Configuración base / bootstrapping |
| `vendor-bootstrap.js` | **3 KB** | Bootstrap mínimo (legacy) |
| **TOTAL visible** | **~12+ MB sin comprimir** | Con brotli: ~3–4 MB |

**Observación crítica:** 12 MB de JS sin comprimir es un bundle muy pesado. El chunk `vendor.co` de 3.5 MB es el responsable principal — indica un design system interno masivo con CSS-in-JS de generación atómica. Para comparación, shadcn/ui + Tailwind (Catalaxia) no tiene este costo.

---

## 3. Stack tecnológico completo

### Frontend core
| Tecnología | Evidencia |
|-----------|----------|
| **React** | `bundle.vendor.react` (949KB), `__reactFiber` en DOM |
| **React Router** | `window.__reactRouterVersion` detectado |
| **Rolldown** | Naming de bundles: `bundle.rolldown-runtime` |

### Estado / data management
| Librería | Evidencia |
|---------|---------|
| **Immer** | Detectado en `vendor~main` — manejo inmutable de estado |
| **Axios** | Detectado en `vendor~main` — cliente HTTP REST |
| **Socket.io** | Detectado en `vendor~main` — datos en tiempo real (precios live) |
| **Zod** | Detectado — validación de schemas TypeScript-first |
| **Yup** | Detectado — validación de formularios (tiene ambos: Zod + Yup) |

### Visualización
| Librería | Evidencia |
|---------|---------|
| **D3** | Detectado en `vendor~main` — charts custom de bajo nivel |
| **Virtualización propia** | `chunk0` — tablas con miles de filas virtualizadas |
| Sin Highcharts | No detectado (TIKR usa Highcharts, Koyfin usa D3) |
| Sin Recharts | No detectado |

### Styling
| Patrón | Evidencia |
|-------|---------|
| **Atomic CSS-in-JS** | `vendor.co` genera clases con prefijo `fx-XXXXXXX` |
| **CSS Modules** | Clases hasheadas en HTML (`navi-panel-layout__naviPanelLayout`) |
| **LightningCSS** | Variables `--lightningcss-dark/light` en CSS |
| **Fuente** | `aktiv-grotesk` (licencia paga, Dalton Maag) + `inter` fallback |
| **Iconos** | Font Awesome 6 Pro (kit `966c91c769` — licencia paga) |

El `vendor.co` (3.5MB) es probablemente su **design system propietario** compilado — un componente library interno con atomic CSS-in-JS runtime similar a Fela o StyleX.

### Fechas y utilidades
| Librería | Evidencia |
|---------|---------|
| **Moment.js** | Detectado — legacy (400KB solo de Moment) |
| **Numeral/accounting** | Detectado — formateo de números financieros |
| **Segment** | Detectado — CDP (Customer Data Platform) |

### Autenticación
| Componente | Evidencia |
|-----------|---------|
| **Microsoft Azure AD / MSAL** | `bundle.vendor~main~oidcMicrosoftRedirect` + `msal` detectado |
| **OIDC** | Protocolo OAuth 2.0 / OIDC standard |
| **SSO Microsoft** | Flujo dedicado de redirect |

---

## 4. APIs y comunicación con backend

### Protocolo principal
```
REST API — confirmado por patrón /v1/, /v2/ en main bundle
No GraphQL — no se detectó __typename ni gql
No Firebase — no se detectó
No Supabase — no se detectó
```

### Dominios propios (subdomains)
```
app.koyfin.com          → Frontend SPA
assets.koyfin.com       → CDN estático (imágenes, favicons)
mix.koyfin.com          → Mixpanel self-hosted proxy (privacidad)
cioanalytics.koyfin.com → Customer.io analytics proxy (self-hosted)
```

La decisión de proxear Mixpanel y Customer.io a través de subdominios propios (`mix.koyfin.com`, `cioanalytics.koyfin.com`) es una práctica profesional: evita que ad-blockers bloqueen el tracking y mejora la privacidad de datos de usuarios.

### WebSocket / Real-time
```
Socket.io detectado en vendor~main
→ Precios en tiempo real sin polling HTTP
→ Animaciones de blink-up/blink-down en tablas (tokens CSS dedicados)
```

### Feature flags
```
Sistema propio (isFeatureEnabled / featureFlag detectado)
No usa LaunchDarkly, Statsig, ni Split.io
```

---

## 5. Infraestructura de analytics y tracking

| Servicio | Propósito | Evidencia |
|---------|---------|---------|
| **Mixpanel** (self-hosted en `mix.koyfin.com`) | Product analytics | `window.mixpanel` activo |
| **Customer.io** (self-hosted en `cioanalytics.koyfin.com`) | Email/lifecycle marketing | `window.cioanalytics` activo |
| **Google Analytics** | Web analytics | `ga` + GTM dataLayer |
| **Google Tag Manager** | Tag management | `dataLayer` con events |
| **Microsoft Clarity** | Heatmaps + session recording | `window.clarity`, POST a `s.clarity.ms` |
| **Segment** | CDP (Customer Data Platform) | Detectado en bundle |

**Stack de analytics muy completo** — 5 herramientas simultáneas. Indica un equipo de growth/data robusto.

### Stack de pagos y revenue
| Servicio | Propósito |
|---------|---------|
| **Stripe v3** | Pagos (subscripciones) |
| **ProfitWell** | Revenue analytics / churn analysis |

### Stack de marketing/ads
| Servicio | Evidencia |
|---------|---------|
| Twitter Pixel | `static.ads-twitter.com/uwt.js` + `platform.twitter.com/oct.js` |
| Bing Ads | `bat.bing.com/bat.js` |
| CookieYes | Cookie consent management |
| Wordfly | Email marketing redirects (`r.wdfl.co/rw.js`) |

---

## 6. Monitoreo y error tracking

| Herramienta | Evidencia |
|-----------|---------|
| **Sentry** | Detectado en main bundle |
| **Rollbar** | Detectado en main bundle — ¡tienen ambos! |

Tener Sentry Y Rollbar simultáneamente es redundante y costoso. Sugiere legacy (probablemente empezaron con uno y agregaron el otro, sin remover el primero).

---

## 7. Arquitectura de frontend

```
┌─────────────────────────────────────────────────┐
│  Browser (React SPA)                            │
│                                                 │
│  React + React Router                           │
│  ├── Lazy routes (3 chunks: ch0, ch1, ch2)     │
│  ├── Estado: Immer (inmutable)                  │
│  ├── HTTP: Axios → REST API                     │
│  ├── Real-time: Socket.io → WebSocket           │
│  └── CSS: Atomic CSS-in-JS (fx-*) + CSS Modules│
│                                                 │
│  CDN: assets.koyfin.com                        │
└──────────────────┬──────────────────────────────┘
                   │ REST + WebSocket
┌──────────────────▼──────────────────────────────┐
│  Backend (no observable desde frontend)         │
│  Probable: Node.js o Go API, PostgreSQL,        │
│  Redis (real-time pub/sub para Socket.io)       │
└─────────────────────────────────────────────────┘
```

---

## 8. Módulos/features inferidos de los route chunks

El code splitting en 3 chunks (`ch0`, `ch1`, `ch2`) + `main` sugiere agrupación por feature area:

| Chunk | Tamaño | Feature area probable |
|-------|--------|----------------------|
| `bundle.main` | 1.922 KB | Shell, navegación, auth, estado global |
| `bundle.m.ch0` | 2.856 KB | Módulo más pesado — Charts + Financial statements (virtualización) |
| `bundle.m.ch1` | ~estimado | Screener / Portfolio / Watchlist |
| `bundle.m.ch2` | ~estimado | Dashboard / News / Calendar |

---

## 9. Mobile

| Plataforma | Evidencia |
|-----------|---------|
| **iOS app** | App Store ID `1616697676` — meta tag `apple-itunes-app` |
| **Twitter handle** | `@KoyfinCharts` — meta tag |
| **PWA** | No detectado service worker |

---

## 10. Lo que Catalaxia NO debe copiar de Koyfin

| Problema de Koyfin | Por qué evitarlo |
|-------------------|-----------------|
| **12+ MB de JS** | Moment.js (legacy), vendor.co design system masivo — demasiado pesado |
| **Moment.js** | Deprecated. Usar `date-fns` o `dayjs` (Catalaxia ya tiene TypeScript strict) |
| **Sentry + Rollbar** | Redundante. Elegir uno (Sentry es el estándar) |
| **vendor.co 3.5MB** | Design system custom masivo. shadcn/ui + Tailwind logra lo mismo en <100KB |
| **Font paga (aktiv-grotesk)** | Inter libre funciona igual de bien |
| **FA6 Pro (pago)** | Lucide Icons cubre el 95% gratis |
| **Dark-only** | Alienar usuarios que prefieren light mode |
| **5 analytics simultáneos** | Overhead de red + privacidad. Para v1: solo Mixpanel o Posthog |

## 11. Lo que Catalaxia SÍ debe tomar de Koyfin

| Feature | Implementación sugerida |
|---------|------------------------|
| **Virtualización de tablas** | TanStack Virtual (React) para el screener con 100+ filas |
| **Socket.io para precios live** | Mismo stack para updates en tiempo real |
| **Self-hosted analytics proxy** | Proxear Mixpanel/Posthog desde un subdominio propio |
| **Code splitting por ruta** | Next.js ya lo hace automáticamente con `dynamic()` |
| **Tokens blink-up/blink-down** | CSS tokens para animación de precios que cambian |
| **Axios + interceptors** | Para manejo centralizado de auth headers y errores |
| **Zod** | Validación de respuestas API (Catalaxia ya tiene TypeScript strict) |
| **Microsoft SSO** | OIDC via NextAuth.js — fácil en Next.js 14 |
