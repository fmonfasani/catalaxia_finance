# Bull Market Brokers — Análisis Técnico Completo

**URL analizada:** https://inversiones.bullmarket.com.ar/Cotizaciones/merval  
**Fecha:** 2026-09-07  
**Nota:** La app requiere login. El análisis se realizó desde la página de autenticación + inspección directa de bundles y endpoints públicos.

---

## 1. Stack tecnológico — resumen ejecutivo

| Capa | Tecnología |
|------|-----------|
| **Backend** | ASP.NET MVC (C# / .NET) |
| **Patrón** | Server-side rendering tradicional (MVC con Razor views) |
| **Frontend** | jQuery + Bootstrap + Material Design Components (MDC Web) |
| **Real-time** | **ASP.NET Core SignalR** — WebSocket para precios en vivo |
| **Auth** | ASP.NET Identity + Device Fingerprinting propio |
| **CDN** | Cloudflare (WAF + analytics + assets estáticos) |
| **Bundler** | ASP.NET Bundler & Minifier — **no webpack, no Vite** |

Esta es la arquitectura más tradicional de los tres competidores analizados. Bull Market usa un stack .NET clásico con jQuery, típico de sistemas financieros argentinos construidos hace 8-12 años.

---

## 2. Bundle system

| Bundle | URL pattern | Tamaño |
|--------|------------|--------|
| jQuery principal | `/bundles/js/jquery.min.js?v=hash` | **374 KB** |
| Seguridad/Auth JS | `/bundles/js/security.min.js?v=hash` | **516 KB** |
| Estilos auth | `/bundles/css/security.min.css?v=hash` | **414 KB** |
| **Total login page** | | **~1.3 MB** |

**Sistema de bundling**: ASP.NET MVC Bundler (no Webpack/Vite/Rolldown). Los bundles se identifican por path `/bundles/` y versioning con hash en query string (`?v=`). Este es el sistema de Microsoft de hace más de 10 años.

---

## 3. Framework y librerías frontend

### Confirmados
| Librería | Versión | Evidencia |
|---------|---------|---------|
| **jQuery** | Incluido en jquery.min.js | `window.$` y `window.jQuery` activos |
| **Bootstrap** | Detectado en CSS | clases `.col-md-`, `.container`, `.btn-` |
| **Material Design Components (MDC Web)** | Google MDC | CSS vars `--mdc-typography-*`, `--mdc-filled-button-*` |
| **jQuery Validate** | Detectado | bundle security.min.js |
| **Font Awesome** | 6.2.1 | `cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.1` |
| **Material Icons** | Google | `fonts.googleapis.com/icon?family=Material+Icons` |

### Híbrido Bootstrap + MDC Web
Usan **ambos** Bootstrap y Material Design Components simultáneamente — combinación inusual que sugiere refactors parciales a lo largo del tiempo. El login page carga MDC Web (Google's official Material Design implementation) pero también tiene Bootstrap. Esto indica que migaron parte de la UI a MDC sin completar la transición.

---

## 4. Sistema de diseño (inferido del CSS)

### Tipografía
```
font-family: Roboto, sans-serif  ← Material Design estándar
```

### Paleta de colores

| Rol | Color | Origen |
|-----|-------|--------|
| Primary teal | `#018786` | MDC default (no customizado) |
| Primary purple | `#6200ee` | MDC default (no customizado) |
| Brand blue 1 | `#1E27F3` | Custom Bull Market |
| Brand blue 2 | `#00176D` | Custom Bull Market (navy) |
| Brand blue 3 | `#2048DD` | Custom Bull Market |
| Brand blue 4 | `#4267ED` | Custom Bull Market |
| Brand light blue | `#B8C5F4` | Custom Bull Market |
| Error | `#b00020` | MDC estándar |

**Identidad visual**: Azules (`#00176D` navy + `#1E27F3` eléctrico). El teal y purple son los colores default de MDC que **no fueron customizados** — deuda de diseño evidente.

---

## 5. Arquitectura de routes y endpoints

### Pattern ASP.NET MVC
```
/Security/SignIn         → Controller: Security, Action: SignIn
/Cotizaciones/merval     → Controller: Cotizaciones, Action: merval (o route param)
/Cotizaciones/GetData    → AJAX endpoint (POST)
/Cotizaciones/GetMervalData → AJAX endpoint (POST, 200 sin auth)
/Cotizaciones/GetCotizaciones → AJAX endpoint (POST, 200 sin auth)
```

### Endpoints descubiertos

| Endpoint | Método | Status | Acceso |
|---------|--------|--------|--------|
| `/api/prices` | GET | 200 | Público |
| `/Cotizaciones/GetCotizaciones` | POST | 200 | Auth requerida |
| `/Cotizaciones/GetMervalData` | POST | 200 | Auth requerida |
| `/Cotizaciones/GetData` | POST | 405 | Auth + parámetros |
| `/Cotizaciones/GetMerval` | POST | 405 | Auth + parámetros |
| `/cotizacionesHub` | GET/WS | **200** | **SignalR Hub** |

### 🔑 SignalR Hub confirmado
```
/cotizacionesHub  →  200 OK
```
Este es el **WebSocket hub de precios en tiempo real**. Cuando el usuario está logueado y ve cotizaciones, el browser conecta a este hub via WebSocket para recibir actualizaciones de precios sin polling.

---

## 6. Real-time: ASP.NET Core SignalR

El hub `/cotizacionesHub` es la pieza técnica más relevante de Bull Market para Catalaxia. SignalR en .NET:

```
Browser <──WebSocket──> /cotizacionesHub (ASP.NET Core)
                              │
                    SQL Server / Redis pub/sub
                              │
                    BYMA / mercados externos
```

- Negociación automática WebSocket → Server-Sent Events → Long Polling (fallback)
- Hub methods: probablemente `SubscribeMerval`, `SubscribeCedears`, etc.
- Updates pushed al cliente cuando cambia precio

---

## 7. Autenticación y seguridad

```
POST /Security/SignIn
  Body:
    FingerPrint: [device fingerprint generado por JS]
    Email: user@email.com
    Password: ****
    __RequestVerificationToken: [CSRF token ASP.NET]
```

**Mecanismos de seguridad:**
- `__RequestVerificationToken` — protección CSRF nativa de ASP.NET MVC
- `FingerPrint` — campo oculto con device fingerprint del browser (anti-bot / anti-fraude)
- Cloudflare WAF — en frente del server
- Sin reCAPTCHA visible en login (el fingerprint es el mecanismo anti-bot)

---

## 8. Analytics y tracking

| Herramienta | ID / Config | Propósito |
|------------|------------|---------|
| **Google Tag Manager** | `GTM-K7QDB2X` | Tag management |
| **Cloudflare Web Analytics** | `beacon.min.js` | Analytics de performance |

Stack de analytics minimalista comparado con Koyfin (5 herramientas). Solo GTM + Cloudflare Analytics.

---

## 9. Infraestructura

| Componente | Tecnología |
|-----------|-----------|
| CDN / WAF | **Cloudflare** |
| Assets estáticos | `cdnjs.cloudflare.com` (Font Awesome) |
| Fonts | `fonts.googleapis.com` (Material Icons, Roboto) |
| Hosting | Detrás de Cloudflare — servidor propio (probablemente IIS + Windows Server) |
| SSL | Cloudflare SSL |

---

## 10. Secciones del producto (inferidas de las rutas)

| Ruta | Sección |
|------|---------|
| `/Cotizaciones/merval` | Cotizaciones del Merval |
| `/Cotizaciones/cedears` | CEDEARs (probable) |
| `/Cotizaciones/bonos` | Bonos (probable) |
| `/Security/SignIn` | Login |
| `/Home/` | Dashboard principal |

El patrón MVC sugiere controllers adicionales probables: `Ordenes/`, `Portfolio/`, `Cuenta/`, `Transferencias/`.

---

## 11. Tabla comparativa: Bull Market vs TIKR vs Koyfin vs Catalaxia

| Dimensión | Bull Market | TIKR | Koyfin | Catalaxia |
|-----------|------------|------|--------|-----------|
| **Backend** | ASP.NET MVC (C#) | Node.js (inferido) | Node.js (inferido) | FastAPI (Python) |
| **Frontend** | jQuery + MVC Views | Vue.js 2 + Vuetify | React + CSS Modules | Next.js 14 + Tailwind |
| **Bundler** | ASP.NET Bundler | Nuxt/Webpack | **Rolldown** (Rust) | Next.js (Turbopack) |
| **Real-time** | **SignalR WebSocket** | No evidente | **Socket.io** | A implementar |
| **Design system** | Bootstrap + MDC (sin terminar) | Vuetify 2 (viejo) | Untitled UI dark | shadcn/ui + Tailwind |
| **Tipografía** | Roboto | Inter | aktiv-grotesk | Inter |
| **Colores** | Navy blues | Naranja #f90 | Azul #3789f2 | A definir |
| **Auth** | .NET Identity + Fingerprint | Firebase Auth | MSAL/Azure AD | NextAuth.js |
| **Bundle total** | ~1.3MB (login) | ~desconocido | **~12MB** | Mínimo (shadcn) |
| **Modernidad** | ⭐⭐ (legacy) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 12. Lo que Catalaxia puede tomar de Bull Market

| Feature | Implementación para Catalaxia |
|---------|------------------------------|
| **SignalR → precios live** | Equivalente: WebSocket desde FastAPI con `fastapi-websocket` o SSE. Para el screener, actualizar precios cada 15min via polling es suficiente para v1 |
| **Device Fingerprinting en auth** | Para v2: `fingerprintjs` open source |
| **Cloudflare** | Sí — fácil de agregar al deploy de Coolify. WAF + analytics gratis en plan free |
| **GTM mínimo** | Un solo GTM en lugar de 5 analytics como Koyfin |

## 13. Lo que Catalaxia NO debe replicar de Bull Market

| Problema | Por qué evitarlo |
|---------|-----------------|
| **jQuery en 2026** | Deuda técnica enorme. Next.js + React es el estándar |
| **Server-side rendering MVC clásico** | Sin SPA = UX más lenta y difícil de mantener |
| **Bootstrap + MDC sin terminar de migrar** | Inconsistencia visual. Catalaxia: shadcn/ui único |
| **Colores MDC sin customizar** | El teal #018786 y purple #6200ee son los defaults de Material — no comunica identidad propia |
| **Roboto como única fuente** | Genérico. Inter es igual de neutral pero más moderna |
| **ASP.NET Bundler** | Sin tree-shaking, sin code splitting — bundle de 890KB para una página de login |
