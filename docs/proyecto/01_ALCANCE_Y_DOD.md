# Alcance y Definition of Done

> Qué entra, qué NO entra, y qué significa "terminado". Si no está acá, no está en el alcance de
> las 4 semanas.

---

## 1. Objetivo

Convertir la base de datos ya construida (572 empresas · 733 instrumentos · doble precio ARS/USD ·
ratios oficiales) en un **producto consumible**: PostgreSQL en la VPS + API REST + frontend
(screener + detalle), con jobs de actualización.

## 2. Dentro del alcance (IN)

**Datos / Infra**
- Migración de la base (SQLite validado) a **PostgreSQL** en la VPS existente.
- Carga de las 572 empresas + 733 instrumentos + ratios/ precios ya calculados.
- Jobs de actualización (precios diario · fundamentales trimestral) corriendo en la VPS.
- Deploy del backend, dominio/HTTPS, CORS, backups automáticos.

**Backend (API REST · FastAPI)**
- `GET /empresas` (screener con filtros/orden/paginación).
- `GET /empresas/{id}` (fundamentales + instrumentos anidados).
- `GET /instrumentos` (por tipo/mercado).
- `GET /cobertura` (salud del dataset).
- `POST /jobs/{tipo}` + `GET /jobs/{id}/status`.
- `openapi.json` documentado.

**Frontend (Next.js)**
- Screener: tabla de 572 empresas, columnas de ratios, **toggle ARS/USD**, sorting, paginación,
  export CSV, filtros (rangos de ratios + flag de calidad), panel de jobs.
- Detalle de empresa: fundamentales + **panel de instrumentos** (ADR/CEDEAR/local con ISIN),
  dividendos del ADR + yield, **vista CEDEAR**, comparador (mismo universo), chips de provenance.
- Estados vacíos / loading / error · responsive.

## 3. Fuera del alcance (OUT) — para no discutir después

- Autenticación / usuarios / watchlists (se puede cotizar aparte).
- App móvil nativa / bot de Telegram/WhatsApp.
- Precio CEDEAR **real** de IAMC (queda el teórico usd × CCL; mejora futura).
- Completar ISIN faltantes vía OpenFIGI (mejora futura).
- Expansión del universo CNV completo (556) y parser bank-aware.
- Pagos / facturación dentro del producto.
- Rediseño del pipeline de datos (ya está hecho y validado; no se toca su lógica).

> Cualquier pedido nuevo del cliente entra por **change request** (se cotiza y se agenda aparte).

## 4. Definition of Ready (DoR) — una tarea puede empezar si…

- Tiene criterio de aceptación claro.
- Su dependencia (ej. contrato de API, endpoint, dato) está disponible o mockeada.
- Está estimada y asignada en Jira.

## 5. Definition of Done (DoD) — global

Una tarea/historia está **terminada** cuando:
1. Cumple su criterio de aceptación.
2. Corre en el entorno correspondiente (local + desplegada en staging de la VPS cuando aplica).
3. Tiene PR mergeado a `main` con **review de al menos 1 par** (ver `08`).
4. No rompe lo anterior (smoke test manual + tests donde correspondan).
5. Sin `console.log`/prints de debug ni credenciales hardcodeadas.

### DoD por tipo
- **Endpoint (backend):** responde con el shape del contrato (`04`), maneja error y vacío,
  aparece en `openapi.json`, probado con datos reales de la VPS.
- **Vista (frontend):** consume la API real (no mock), maneja loading/empty/error, responsive,
  respeta el diseño acordado.
- **Infra:** reproducible (documentado en `06`), con rollback o backup, sin pasos manuales secretos.

## 6. Criterios de aceptación por entregable semanal

| Semana | El entregable se acepta si… |
|---|---|
| **S1** | La API devuelve `/empresas` con **datos reales desde Postgres en la VPS**, y el front muestra la tabla consumiendo el **contrato** (mock ok). |
| **S2** | El front consume la **VPS real**: screener + detalle muestran las 572 empresas y sus instrumentos. |
| **S3** | Filtros (rangos + flag), export CSV, jobs (disparar + status) y vistas CEDEAR/dividendos funcionan de punta a punta. |
| **S4** | Tests + manejo de errores + responsive + `openapi.json`; producto integrado y desplegado; checklist de QA (`10`) en verde. |

## 7. Entregable final

Producto desplegado en la VPS (API + frontend), documentado (`openapi.json` + READMEs),
con jobs corriendo y backups activos. **Garantía: 30 días** de soporte correctivo post-entrega.
