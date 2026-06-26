# Sprint 1 Entregables
**Período:** 20 de junio - 28 de junio de 2026 (1 semana)

---

## 📋 Resumen Ejecutivo

Sprint 1 se enfoca en **establecer la base infraestructural y arquitectónica** del proyecto. Las prioridades son:
1. Configurar base de datos y schema PostgreSQL
2. Estructura del backend (carpetas, dependencias)
3. Setup inicial del frontend
4. GitHub + Jira + CI/CD básico

**Status:** 18 tasks | **Asignación:** Federico (10), Joaquin (3), Aldana (2), Mateo (3)

---

## 🏗️ ARQUITECTURA & BASE DE DATOS

**Propietario:** Federico Monfa (@fmonfasani)

### 1. **CATA-1: Epic - Arquitectura y Base de Datos**
- [ ] Definir estructura de carpetas completa
- [ ] Documentar decisiones arquitectónicas
- [ ] Crear diagrama de componentes

**Entregables:**
- Carpeta `/docs/01-arquitectura.md` actualizado
- Estructura de `/backend` y `/frontend` definida
- README con instrucciones de setup local

---

### 2. **CATA-104: Define estructura de carpetas**
- [ ] Backend: `/fetchers`, `/calculators`, `/models`, `/routers`
- [ ] Frontend: `/app`, `/components`, `/hooks`, `/lib`
- [ ] Crear `.gitkeep` en carpetas clave

**Criterios de aceptación:**
- [ ] Estructura visible en repo
- [ ] Todos pueden clonar y tener la misma estructura
- [ ] Documentación de qué va en cada carpeta

---

### 3. **CATA-105: Diseño de endpoints API**
- [ ] Listar todos los endpoints (GET /precios, POST /ratios, etc.)
- [ ] Especificar request/response JSON
- [ ] Documentar autenticación (si aplica)

**Entregables:**
- `/docs/04-contrato-api.md` con OpenAPI spec draft

---

### 4. **CATA-106: Logging y monitoring strategy**
- [ ] Definir qué eventos loguear
- [ ] Estructura de logs (JSON, stdout, archivos)
- [ ] Integración con observabilidad (si aplica)

**Entregables:**
- Documento de estrategia de logging
- Configuración en `backend/logger.py` (skeleton)

---

## 🗄️ BASE DE DATOS

### 5. **CATA-7: Definir schema PostgreSQL**
- [ ] 5 tablas: `cedears`, `precios_raw`, `financials_raw`, `ratios`, `jobs`
- [ ] Especificar columnas, tipos, constraints
- [ ] Índices y claves foráneas

**Entregables:**
- `/docs/03-base-de-datos.md` (final)
- `/migrations/001_initial_schema.sql` (listo para ejecutar)

---

### 6. **CATA-8: Migración SQL ejecutable**
- [ ] `001_initial_schema.sql` debe poder ejecutarse sin errores
- [ ] Crear `001_seed_cedears.sql` con tickers base
- [ ] Documentar cómo aplicar migraciones

**Criterios de aceptación:**
- [ ] `psql -U postgres -d cedears_prod < migrations/001_initial_schema.sql` funciona
- [ ] Todas las tablas se crean sin errores
- [ ] Índices se crean automáticamente

---

## 🔌 BACKEND A: PRECIOS

**Propietario:** Federico Monfa (@fmonfasani)

### 7. **CATA-2: Epic - Backend A - Precios**
- [ ] Completar desarrollo de descarga de precios
- [ ] Tests pasando
- [ ] Documentación de endpoint

---

### 8. **CATA-65: Implementar endpoint GET /precios**
- [ ] Estructura básica en `backend/fetchers/precios.py`
- [ ] Endpoint HTTP que retorna lista de precios
- [ ] Request/response según spec en CATA-105

**Entregables:**
```python
# backend/app/routers/precios.py
@router.get("/precios")
async def get_precios(ticker: str = None) -> List[PrecioSchema]:
    # Retorna precios desde la DB
```

---

### 9. **CATA-66: Tests para normalización de tickers**
- [ ] Tests unitarios para `normalizar_ticker_yf()`
- [ ] Coverage > 80%
- [ ] Casos edge: "BRK.B" → "BRK-B", "GOOG" → "GOOG"

**Entregables:**
- `/backend/tests/test_fetchers_precios.py` con 10+ casos

---

### 10. **CATA-67: Documentación endpoint precios**
- [ ] Descripción en `/docs/SCRIPT_04_PRECIOS.md`
- [ ] Ejemplos de uso: cURL, Python
- [ ] Campos de entrada/salida documentados

---

## 💰 BACKEND B: FINANCIALS

**Propietario:** Mateo Llorente (@mateollorente)

### 11. **CATA-3: Epic - Backend B - Financials y Ratios**
- [ ] Estructura lista
- [ ] Documentación de fórmulas
- [ ] Setup de SEC EDGAR integration

---

### 12. **CATA-68: Estructura backend/calculators**
- [ ] Carpeta `/backend/calculators/` creada
- [ ] `ratios.py`, `ttm.py`, `cagr.py` como stubs
- [ ] Imports funcionales (sin NotImplementedError)

**Entregables:**
```python
# backend/calculators/ttm.py
def calcular_ttm_flujo(financials: List[Dict]) -> float:
    """Calcula TTM usando estrategia A, B o C."""
    pass
```

---

### 13. **CATA-69: Tests de estructura y imports**
- [ ] Todos los módulos importan sin errores
- [ ] Coverage mínimo: todos los archivos creados
- [ ] No hay circular imports

---

### 14. **CATA-70: Documento FORMULAS_RATIOS.md**
- [ ] Copiar desde `/research/docs/FORMULAS_RATIOS.md`
- [ ] Adaptar paths al nuevo repo
- [ ] Verificar referencias a columnas

---

## 🎨 FRONTEND A: SCREENER

**Propietario:** Joaquin Levis (@joaquinlevis)

### 15. **CATA-4: Epic - Frontend A - Screener**
- [ ] Setup Next.js completado
- [ ] Tailwind funcionando
- [ ] Componentes base creados

---

### 16. **CATA-72: Setup Next.js + Tailwind**
- [ ] `next.config.js` configurado
- [ ] `tailwind.config.js` con tema base
- [ ] `globals.css` con reset de Tailwind

**Criterios de aceptación:**
- [ ] `npm run dev` inicia sin errores
- [ ] Estilos Tailwind se aplican correctamente
- [ ] Página por defecto muestra algo

---

### 17. **CATA-73: Tabla de screener (skeleton)**
- [ ] Componente `<ScreenerTable />` creado
- [ ] Renderiza datos de muestra (mock)
- [ ] Columnas: ticker, precio, PER, EPS, CAGR

**Entregables:**
```tsx
// frontend/components/screener/ScreenerTable.tsx
export function ScreenerTable({ data }: Props) {
  return (
    <table>
      {/* Columnas de screener */}
    </table>
  );
}
```

---

## 📋 FRONTEND B: PROCESOS

**Propietario:** Aldana Oviedo (@OviedoAldana)

### 18. **CATA-5: Epic - Frontend B - Procesos y Detalle**
- [ ] Setup inicial completado
- [ ] Navegación base funcional

---

### 19. **CATA-78: Setup inicial frontend (procesos)**
- [ ] Layout base: header, sidebar, main
- [ ] Navegación entre secciones
- [ ] Estilos Tailwind aplicados

---

### 20. **CATA-79: Página /procesos con 6 cards**
- [ ] Renderiza 6 tarjetas de procesos
- [ ] Cada card tiene título, descripción, ícono
- [ ] Links funcionales (sin destino aún)

**Entregables:**
```tsx
// frontend/app/procesos/page.tsx
export default function ProcesosPage() {
  return (
    <div className="grid grid-cols-3 gap-4">
      {/* 6 cards */}
    </div>
  );
}
```

---

## 🚀 CI/CD & INFRAESTRUCTURA

**Propietario:** Federico Monfa (@fmonfasani)

### 21. **CATA-6: Epic - CI/CD e Infraestructura**
- [ ] GitHub workflows configurados
- [ ] Jira integraciones básicas
- [ ] Deploy documentation (sin activar)

---

### 22. **CATA-86: GitHub CODEOWNERS**
- [x] ✅ COMPLETADO - CODEOWNERS configurado
- [x] ✅ Rutas de protección por owner definidas

---

### 23. **CATA-87: Branch protection en main**
- [x] ✅ COMPLETADO - 1 approval requerido
- [x] ✅ Status checks habilitados

---

### 24. **CATA-88: GitHub PR template**
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` creado
- [ ] Incluye secciones: Cambios, Testing, Checklist
- [ ] Enlaza a CODEOWNERS para reviewers

---

### 25. **CATA-89: GitHub Issue templates**
- [ ] `ISSUE_TEMPLATE/bug_report.md`
- [ ] `ISSUE_TEMPLATE/feature_request.md`
- [ ] `ISSUE_TEMPLATE/tarea_sprint.md`

---

### 26. **CATA-90: Workflow backend-ci.yml**
- [ ] Lint con `ruff`
- [ ] Type check con `mypy`
- [ ] Tests con `pytest`
- [ ] Trigger: push a main + PR

---

### 27. **CATA-91: Workflow sql-lint.yml**
- [ ] Lint SQL con `sqlfluff`
- [ ] Trigger en cambios a `/migrations/`

---

### 28. **CATA-93: Configurar webhooks Jira**
- [ ] GitHub → Jira: actualizar status en PR/merge
- [ ] Jira → GitHub: crear issues desde Jira

---

### 29. **CATA-94: Jira dashboard inicial**
- [ ] Sprint board visible
- [ ] Backlog ordenado por prioridad
- [ ] Filtros funcionales (por epic, asignado, estado)

---

### 30. **CATA-11: Code review continuo**
- [ ] Revisar PRs del sprint
- [ ] Dar feedback
- [ ] Mantener código limpio y consistente

---

## 📊 Criterios de Aceptación - Sprint 1 COMPLETO

- [ ] Base de datos aplicada (schema visible en prod)
- [ ] Repos synced (git branches limpias)
- [ ] Workflows verdes (CI pasa)
- [ ] Documentación mínima para cada área
- [ ] Asignaciones actualizadas en Jira
- [ ] Sin bloqueadores técnicos para Sprint 2

---

## 🔄 Dependencias para Sprint 2

- **CATA-1 → CATA-20**: Arquitectura define paths para Sprint 2
- **CATA-7 → CATA-65**: Schema listo antes de escribir datos
- **CATA-72 → CATA-73**: Setup Next.js termina antes de componentes

---

## 📝 Notas

- Cada task tiene una persona asignada — no empezar sin confirmación
- Cualquier bloqueador → Slack a Federico inmediatamente
- Sprint review el **28 jun a las 18:00 UTC** (30 min)
- Sprint retro el **28 jun a las 18:30 UTC** (20 min)
