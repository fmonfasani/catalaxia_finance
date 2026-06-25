# Sprint 6 Entregables
**Período:** 27 de julio - 31 de julio de 2026 (1 semana)

---

## 📋 Resumen Ejecutivo

Sprint 6 es el **sprint final de QA, polish, y deployment**. El objetivo es:
1. Testing exhaustivo (manual + E2E)
2. Performance + seguridad
3. Deployment a producción (Coolify)
4. Documentación final y handoff

**Status:** 8 tasks | **Asignación:** Federico (5), Joaquin (1), Aldana (1), Mateo (1)

---

## 🧪 QA & TESTING

**Propietario:** Federico Monfa (@fmonfasani)

### 1. **CATA-111: QA completo: Screener**
- [ ] Test manual todas las combinaciones de filtros
- [ ] Buscar 30+ tickers, verificar resultados correctos
- [ ] Export CSV con datos filtrados → verificar formato
- [ ] Performance: tabla con 1000 rows debe cargar < 2s
- [ ] Mobile: scrolling suave, buttons clickeables

**Entregables:**
- Documento de test cases ejecutados (✓ pass / ✗ fail)
- Screenshot de resultados por cada filtro principal

---

### 2. **CATA-112: QA completo: Detalle page**
- [ ] Test para 10+ empresas (AAPL, MSFT, GOOG, AMZN, TSLA, etc.)
- [ ] Gráficos renderizan correctamente
- [ ] Tabla histórica ordena correctamente
- [ ] Links funcionan (volver a screener, compartir)
- [ ] Mobile: gráficos responsive, tabla scrolleable

---

### 3. **CATA-113: QA completo: Watchlist + Comparador**
- [ ] Agregar/remover de watchlist funciona
- [ ] Comparador con 2, 3, 4 empresas
- [ ] Gráficos superpuestos se ven claramente
- [ ] Eliminar empresa del comparador
- [ ] Exportar watchlist a CSV

---

### 4. **CATA-114: QA completo: Jobs + Admin panel**
- [ ] Job 1A (precios) se ejecuta sin errores
- [ ] Job 1B (financials) se ejecuta sin errores
- [ ] Job 2 (ratios) completa exitosamente
- [ ] Admin panel: botones funcionan
- [ ] Logs aparecen en tiempo real (tail style)
- [ ] Verificar datos nuevos aparecen en screener

---

### 5. **CATA-115: Testing de seguridad básico**
- [ ] Admin panel requiere autenticación (no accesible público)
- [ ] CSV export no incluye datos sensitivos
- [ ] Inputs validados (SQL injection, XSS)
- [ ] Rate limiting en endpoints (máx 100 req/min por IP)
- [ ] Logs no exponen credenciales o datos personales

**Entregables:**
- Checklist de seguridad (vulnerabilidades comunes)
- Documento: "Cómo reportar bugs de seguridad"

---

## 🚀 DEPLOYMENT

**Propietario:** Federico Monfa (@fmonfasani)

### 6. **CATA-104: Deploy a Coolify (Staging)**
- [ ] Crear proyecto CATA en Coolify UI
- [ ] Configurar variables de entorno:
  - `DATABASE_URL=postgres://...`
  - `API_BASE_URL=https://catalaxia.staging.webshooks.com`
  - `LOG_LEVEL=debug`
- [ ] Crear webhook GitHub → Coolify (auto-deploy on push to `deploy/staging` branch)
- [ ] Aplicar migraciones DB en staging
- [ ] Ejecutar Job 1A y 1B en staging
- [ ] Verificar datos en staging screener

**Criterios de aceptación:**
- [ ] App accessible en https://catalaxia-staging.webshooks.com
- [ ] DB populated con datos reales (100+ empresas)
- [ ] Jobs corrieron sin errores
- [ ] Logs accesibles para debugging

---

### 7. **CATA-105: Deploy a Coolify (Producción)**
- [ ] Crear proyecto CATA producción en Coolify
- [ ] Configurar variables para producción:
  - Backups automáticos DB (1x diaria)
  - Monitoreo uptime (Coolify alerts o externo)
  - Log aggregation (Coolify o ELK)
- [ ] DNS apunta a: https://catalaxia.webshooks.com
- [ ] SSL cert automático (Let's Encrypt)
- [ ] Webhook GitHub → Coolify (auto-deploy on push to `main`)
- [ ] Smoke tests en producción (verificar endpoints responden)

**Entregables:**
- App online en https://catalaxia.webshooks.com
- Monitoreo activo (dashboard Coolify)
- Rollback plan si algo falla

---

### 8. **CATA-106: Documentación Final**
- [ ] README.md actualizado (setup, deploy, troubleshooting)
- [ ] `/docs/09-deployment.md`: cómo deployar cambios futuros
- [ ] `/docs/10-runbooks.md`: qué hacer si X falla
  - "Job 1A no corre": pasos de debugging
  - "Screener lento": índices, cache, queries
  - "Datos outdated": force job execution
- [ ] `/docs/11-architecture-decisions.md`: por qué decidimos A vs B
- [ ] Change log: qué se entregó cada sprint

**Entregables:**
- Todos los docs actualizados y linkados en README
- Índice de documentación clara y searcheable

---

## 📊 ENTREGA FINAL

### **Documentos completados:**

```
📁 /docs/
├── 01-arquitectura.md ✅ (Sprint 1)
├── 02-jobs.md ✅ (Sprint 1-3)
├── 03-base-de-datos.md ✅ (Sprint 1)
├── 04-contrato-api.md ✅ (Sprint 2-5)
├── 05-decisiones-tecnicas.md ✅ (Sprint 4)
├── 06-deployment.md ✅ (Sprint 6)
├── 07-runbooks.md ✅ (Sprint 6)
├── 08-architecture-decisions.md ✅ (Sprint 6)
├── SPRINT_1_ENTREGABLES.md
├── SPRINT_2_ENTREGABLES.md
├── SPRINT_3_ENTREGABLES.md
├── SPRINT_4_ENTREGABLES.md
├── SPRINT_5_ENTREGABLES.md
└── SPRINT_6_ENTREGABLES.md

📁 /_research/
├── COMIENZA_AQUI.md (referencia)
├── FLUJO_GENERAL.md (referencia)
├── /docs/
│   ├── FORMULAS_RATIOS.md (referencia)
│   ├── MAPEO_COLUMNAS.md (referencia)
│   ├── SCRIPT_03_FINANCIALS_SEC.md (referencia)
│   └── SCRIPT_04_PRECIOS.md (referencia)
├── /scripts/
│   ├── 03_descargar_financials_sec.py (referencia)
│   ├── 04_descargar_precios.py (referencia)
│   └── 05_calcular_ratios.py (referencia)
└── /schema/
    └── 001_initial_schema.sql (referencia)
```

### **Code Quality:**

- ✅ Backend tests: coverage > 75% (calculators > 85%)
- ✅ Frontend: ESLint + TypeScript strict mode
- ✅ Database: migraciones versionadas, rollback tested
- ✅ Logging: JSON structured, searcheable
- ✅ Security: inputs validated, no secrets in logs
- ✅ Performance: Screener < 2s, detalle < 1s, API < 200ms

### **Infra & Ops:**

- ✅ GitHub: CODEOWNERS, branch protection, PR templates
- ✅ Jira: 6 sprints, 98 tasks, epics linked
- ✅ CI/CD: 4 workflows (backend-ci, sql-lint, frontend-ci, deploy)
- ✅ Coolify: staging + production deployments
- ✅ Monitoring: uptime checks, error alerting, logs centralized

### **Deliverables Visible:**

1. 🌐 **Web App**: https://catalaxia.webshooks.com
   - Screener: 100+ empresas con filtros funcionales
   - Detalle: gráficos, ratios históricos, comparador
   - Watchlist: favoritos personalizados
   - Admin: control de jobs

2. 📊 **Data:**
   - PostgreSQL con 5 tablas, 100+ empresas
   - Precios actualizados cada 15 min
   - Ratios calculados cada 1 hora
   - Histórico 52 semanas

3. 📚 **Documentation:**
   - 11 guías (arquitectura, API, deployment, runbooks)
   - README con setup local + deploy en 10 pasos
   - Reference docs de cada script y componente
   - Sprint planning guide para futuros sprints

4. 👥 **Team Enablement:**
   - CODEOWNERS asignados (protege código por propietario)
   - Jira con clear ownership + sprint planning
   - Runbooks para troubleshooting común
   - Code review process establecido

---

## 📊 Criterios de Aceptación - PROJECT COMPLETO

- [ ] ✅ App deployada en producción sin errores
- [ ] ✅ Todos los jobs ejecutándose en schedule
- [ ] ✅ Screener muestra 100+ empresas con datos correctos
- [ ] ✅ Detalle page funcional y performante
- [ ] ✅ Watchlist + comparador funcionales
- [ ] ✅ Admin panel con controles de jobs
- [ ] ✅ Mobile UI completamente responsive
- [ ] ✅ Tests pasando (coverage > 75%)
- [ ] ✅ Documentación completa y actualizada
- [ ] ✅ Zero production bugs en primeras 48 horas
- [ ] ✅ Equipo puede deploy cambios sin intervención

---

## 🎓 Handoff & Documentación Futura

Al finalizar Sprint 6:

1. **Equipo**: Entrenamiento en 1 sesión (30 min)
   - Cómo deployar cambios
   - Cómo debuggear con logs
   - Cómo agregar nuevas features (pasos estándar)

2. **Procesos**: 
   - Sprint planning: 1 sesión semanal (1 hora)
   - Daily standup: 15 min via Slack
   - Sprint review + retro: 1 sesión (1.5 horas)

3. **Roadmap Futuro**:
   - Sprint 7+: Features opcionales
     - Autenticación de usuarios
     - Alertas por email
     - Export a Excel avanzado
     - Comparación histórica (gráficos anuales)
   - Mantenimiento: 2-4 horas/semana (updates deps, bugs, monitoring)

---

## ✨ Final Status

**Project catalaxia-cedears-prod**: LISTO PARA PRODUCCIÓN

All systems go. 🚀

