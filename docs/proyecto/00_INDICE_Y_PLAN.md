# Proyecto Catalaxia Screener — Plan e índice maestro

> Documento raíz. Todo lo que el equipo necesita para arrancar sin dudas.
> Proyecto: **webshooks → Catalaxia** · Módulo Screener Financiero AR + US.
> Duración: **4 semanas** (Mié **15/07** → Vie **14/08/2026**) · Equipo: 4 · **Stack dockerizado en VPS Hetzner**.

---

## 1. Qué estamos construyendo

La **data ya está hecha y validada** (572 empresas, 3 mercados, doble precio ARS/USD, ratios
CEDEAR/ADR oficiales, modelo de 2 niveles, provenance por dato). Lo que falta es **productizarla**:
migrarla a PostgreSQL en la VPS, exponerla por una **API REST**, y construir un **frontend**
(screener + detalle) que la consuma. En 4 semanas.

**El riesgo técnico más grande (la calidad de los datos) ya está resuelto.** Esto es un proyecto
de *ingeniería de producto*, no de investigación.

## 2. Equipo y roles (resumen — detalle en `02_ROLES_RACI.md`)

| Persona | Rol | Responsable de |
|---|---|---|
| **Federico** | Tech Lead · Backend 2 · DBA/Infra | BD + ORM, migración a PostgreSQL, VPS (Postgres/deploy/dominio/CORS/backups), asiste a Mateo en backend, habilita a los front a consumir la VPS |
| **Mateo** | Backend 1 | API REST (empresas, instrumentos, cobertura, jobs), integración del pipeline, scheduler |
| **Joaquín** | Frontend A | Screener: tabla, filtros, toggle ARS/USD, export, panel de jobs |
| **Aldana** | Frontend B | Detalle: panel de instrumentos, dividendos ADR, vista CEDEAR, comparador, UX/confianza |

## 3. Cronograma (detalle en `07_PLAN_ENTREGAS_SEMANAL.md`)

| Sprint | Fechas | Entregable interno (medida de avance) |
|---|---|---|
| **Fase 0** | ✅ hecho | 572 empresas, ratios oficiales, CCL validado |
| **Semana 1** | Mié 15 → Vie 24 Jul | Postgres + API **dockerizados** en la VPS + front con mocks |
| **Semana 2** | Lun 27 → Vie 31 Jul | Front consumiendo la VPS real: screener + detalle (572) |
| **Semana 3** | Lun 3 → Vie 7 Ago | Filtros + flags + jobs + vistas CEDEAR/dividendos |
| **Semana 4** | Lun 10 → Vie 14 Ago | Tests, errores, responsive, **entrega** |

> Los entregables semanales son **una herramienta interna** de avance y de evaluación del equipo.
> El cliente (Marcelo) **no aprueba** entregables; se coordina por separado (ver `09`).

## 4. Índice de documentos

**🔒 Internos (para el equipo)**
| Doc | Para qué | Quién lo usa |
|---|---|---|
| `00_INDICE_Y_PLAN.md` | este mapa | todos |
| `01_ALCANCE_Y_DOD.md` | qué entra / qué no + Definition of Done | todos |
| `02_ROLES_RACI.md` | quién hace qué (RACI) | todos |
| `03_ARQUITECTURA_Y_BD.md` | arquitectura + esquema de PostgreSQL | Federico, Mateo |
| `04_CONTRATO_API.md` | el pacto backend↔frontend (con mocks) | todos |
| `05_SETUP_DEV.md` | levantar el proyecto local | todos |
| `06_INFRA_DEPLOY_VPS.md` | **Docker/Hetzner**: Postgres + API en contenedores, proxy reverso, backups (+ plantillas en `infra/`) | Federico |
| `07_PLAN_ENTREGAS_SEMANAL.md` | entregables por persona, semana a semana | todos |
| `08_ESTANDARES_TRABAJO.md` | git, PR, testing, DoR/DoD | todos |
| `10_QA_Y_RIESGOS.md` | plan de QA + riesgos | Federico, QA |

**🌐 Externos / cliente**
| Doc | Para qué |
|---|---|
| `../pdfs/Propuesta_webshooks_Catalaxia_v4.pptx` | propuesta comercial |
| `09_COORDINACION_CLIENTE.md` | kickoff, qué confirmar con Marcelo, entrega |

**🗂️ Jira**
| Archivo | Para qué |
|---|---|
| `jira/jira_import.csv` | backlog importable (épicas/historias/sprints) |
| `jira/GUIA_JIRA.md` | crear el proyecto e importar el CSV |

## 5. Orden de lectura para el equipo (onboarding, 30 min)

1. Este documento (visión + roles + cronograma).
2. `01_ALCANCE_Y_DOD.md` — para saber qué es "terminado".
3. Su rol en `02_ROLES_RACI.md` y sus tareas en `07_PLAN_ENTREGAS_SEMANAL.md`.
4. `04_CONTRATO_API.md` (front y back) + `05_SETUP_DEV.md`.
5. `08_ESTANDARES_TRABAJO.md` antes del primer commit.

## 6. Reglas de oro del proyecto

- **El contrato de API se acuerda en el día 1.** Los frontends arrancan con **datos mock** basados
  en el contrato; no esperan al backend. (Ver `04`.)
- **La data es la fuente de verdad y ya existe.** No se inventan datos; si algo falta, se marca (flags).
- **Reporte cada viernes** (ver `07`): avance por persona + demo del entregable de la semana.
- **Nada a `main` sin PR + review** (ver `08`).
