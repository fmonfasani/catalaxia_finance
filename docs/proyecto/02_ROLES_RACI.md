# Roles y Responsabilidades (RACI)

> Quién hace qué. **R** = Responsable (ejecuta) · **A** = Aprobador (rinde cuentas, 1 solo) ·
> **C** = Consultado · **I** = Informado.

---

## 1. Roles en detalle

### Federico — Tech Lead · Backend 2 · DBA/Infra
El pegamento del proyecto. Además de arquitecto, mete mano en backend e infra.
- **Datos/BD:** diseña el esquema PostgreSQL (tablas `screener` + `instrumentos`), el ORM
  (SQLAlchemy) y la migración desde el SQLite validado.
- **Infra/VPS:** configura Postgres en la VPS existente, deploy del backend, dominio/HTTPS, CORS,
  backups, y el entorno de **staging** para que los front consuman la VPS.
- **Backend 2:** asiste a Mateo — arma el scaffold, define el contrato de API, hace de par en los
  endpoints difíciles, code review.
- **Habilitador del frontend:** entrega el **contrato de API + mocks** el día 1 y la **URL de la
  VPS** apenas está, para que Joaquín y Aldana no queden bloqueados.
- **QA e integración final** + soporte post-entrega.

### Mateo — Backend 1
Dueño de la API.
- Endpoints: `/empresas`, `/empresas/{id}`, `/instrumentos`, `/cobertura`, `/jobs`.
- Integración del pipeline de datos ya existente (leer de Postgres, servir).
- Jobs + scheduler (APScheduler). Tests backend + `openapi.json`.

### Joaquín — Frontend A (Screener)
- Tabla de 572 empresas, columnas de ratios, sorting, paginación.
- Filtros (rangos min/max) + filtro por flag de calidad.
- **Toggle ARS/USD**, export CSV, panel de jobs con estado en vivo.

### Aldana — Frontend B (Detalle + confianza)
- Detalle de empresa: header (precio dual), panel de fundamentales.
- **Panel de instrumentos** (ADR/CEDEAR/local con ISIN, moneda, precio, ratio).
- Dividendos del ADR + yield, **vista CEDEAR**, comparador (mismo universo).
- Chips de provenance por dato, estados vacíos/loading/error, responsive.

## 2. Matriz RACI

| Área / entregable | Federico | Mateo | Joaquín | Aldana |
|---|:--:|:--:|:--:|:--:|
| Esquema BD + ORM | **A/R** | C | I | I |
| Migración SQLite → PostgreSQL | **A/R** | C | – | – |
| Infra VPS (Postgres, deploy, dominio, CORS, backups) | **A/R** | I | I | I |
| Contrato de API + mocks | **A/R** | C | C | C |
| Endpoints REST (empresas/instrumentos/cobertura) | A | **R** | I | I |
| Jobs + scheduler | A | **R** | – | I |
| Screener (tabla, filtros, toggle, export) | C | I | **R** | C |
| Panel de jobs (frontend) | C | C | **R** | – |
| Detalle de empresa + panel instrumentos | C | I | C | **R** |
| Dividendos ADR · vista CEDEAR · comparador | C | I | – | **R** |
| Provenance / UX / estados / responsive | C | – | C | **R** |
| Tests + `openapi.json` | C | **R** | R | R |
| QA e integración final | **A/R** | R | R | R |
| Deploy a producción | **A/R** | C | I | I |
| Coordinación con el cliente (Marcelo) | **A/R** | I | I | I |
| Reporte de avance semanal | **A/R** | R | R | R |

## 3. Reglas de colaboración

- **Aprobador único (A):** en cada fila hay un solo A. Si hay duda de alcance/decisión técnica,
  decide Federico (Tech Lead).
- **Desbloqueo:** si alguien queda trabado > medio día, lo levanta en el canal del equipo, no espera
  al viernes.
- **Front nunca espera al back:** trabajan contra el **contrato de API** (`04`) con mocks hasta que
  la VPS esté lista (Federico avisa la URL).
- **Backend nunca rompe el contrato sin avisar:** cualquier cambio de shape se comunica y se
  versiona en `04`.
