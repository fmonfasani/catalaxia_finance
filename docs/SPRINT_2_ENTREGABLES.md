# Sprint 2 Entregables
**Período:** 29 de junio - 3 de julio de 2026 (1 semana)

---

## 📋 Resumen Ejecutivo

Sprint 2 se enfoca en **implementación core del backend**. El objetivo es tener:
1. Descarga de precios desde yfinance
2. Descarga de financials desde SEC EDGAR
3. Primeros tests de integración
4. Frontend: componentes reutilizables

**Status:** 15 tasks | **Asignación:** Federico (9), Mateo (3), Joaquin (2), Aldana (1)

---

## 🔌 BACKEND A: PRECIOS

**Propietario:** Federico Monfa (@fmonfasani)

### 1. **CATA-20: Descargar precios con yfinance**
- [ ] Función `descargar_precios_yfinance(tickers: List[str]) → Dict`
- [ ] Manejo de errores (ticker no válido, API down, timeout)
- [ ] Caching local en JSON temporal

**Entregables:**
```python
# backend/fetchers/precios.py
async def descargar_precios_yfinance(
    tickers: List[str], 
    cache_file: str = "precios.json"
) → Dict[str, PrecioData]:
    """Descarga precios actuales y 52-week high/low"""
```

**Criterios de aceptación:**
- [ ] Descarga exitosa de 10+ tickers
- [ ] Normaliza BRK.B → BRK-B automáticamente
- [ ] Captura: precio, currency, year_high, year_low
- [ ] Errores loguean pero no crashean proceso

---

### 2. **CATA-21: UPSERT precios en DB**
- [ ] Tabla `precios_raw` inserta/actualiza registros
- [ ] Evita duplicados (UNIQUE en ticker + fecha)
- [ ] Registra timestamp de inserción

**Entregables:**
```sql
-- migrations/002_insert_precios.sql
INSERT INTO precios_raw (byma_ticker, ticker_sec, last_price, ...)
ON CONFLICT (ticker_sec, fecha_descarga) 
DO UPDATE SET last_price = EXCLUDED.last_price;
```

---

### 3. **CATA-22: Job 1A: Refrescar precios (cron)**
- [ ] Cron job que descarga precios cada 15 minutos (market hours)
- [ ] Loguea cada ejecución en tabla `jobs`
- [ ] Reintenta en caso de error (max 3 intentos)

**Entregables:**
- `/backend/app/jobs/refresh_prices.py`
- Configuración en `docker-compose.yml` o Coolify

---

### 4. **CATA-23: Tests integración: yfinance → DB**
- [ ] Test descarga 5 tickers reales
- [ ] Verifica datos en DB después
- [ ] Rollback de cambios (transacción de test)

**Criterios de aceptación:**
- [ ] 5+ tests con coverage > 80%
- [ ] Usa fixture de DB limpia
- [ ] No depende de internet real (mock si aplica)

---

### 5. **CATA-24: Documentación SCRIPT_04_PRECIOS.md**
- [ ] Copiar desde `/research/docs/` y adaptar
- [ ] Especificar request/response del endpoint
- [ ] Ejemplos reales (cURL, Python)

---

## 💰 BACKEND B: FINANCIALS

**Propietario:** Mateo Llorente (@mateollorente)

### 6. **CATA-68: Implementar descarga SEC EDGAR**
- [ ] Función `descargar_financials_sec(cik_list: List[str]) → Dict`
- [ ] XBRL parsing para extraer métricas
- [ ] Captura Revenue, NetIncome, OperatingIncome, Deuda, Equity, Shares

**Entregables:**
```python
# backend/fetchers/sec_edgar.py
async def descargar_financials_sec(
    cik_list: List[str],
    years: int = 5
) → Dict[str, FinancialData]:
    """Descarga últimos 5 años de financials"""
```

---

### 7. **CATA-69: Crear tests SEC EDGAR y ratios**
- [ ] Test parsing XBRL de muestra real
- [ ] Verifica extracción de métricas
- [ ] Fallback logic funciona (Revenues → RevenueFromContract...)

**Criterios de aceptación:**
- [ ] 5+ tests con datos reales de SEC
- [ ] Coverage > 70%

---

### 8. **CATA-70: Implementar Job 1B: Refrescar financials**
- [ ] Cron que descarga financials 1x por semana (viernes)
- [ ] Deduplicación: INSERT ON CONFLICT DO NOTHING
- [ ] Loguea en tabla `jobs` / `job_errores`

**Entregables:**
- `/backend/app/jobs/refresh_financials.py`

---

## 🎨 FRONTEND A: SCREENER

**Propietario:** Joaquin Levis (@joaquinlevis)

### 9. **CATA-72: Componente ScreenerTable con sorting**
- [ ] Tabla renderiza datos reales de API mock
- [ ] Clicking en header para sort ascendente/descendente
- [ ] Indicador visual (↑↓) en columna active

**Entregables:**
```tsx
// frontend/components/screener/ScreenerTable.tsx
<th onClick={() => handleSort('per')}>
  PER {sortColumn === 'per' && (sortDir === 'asc' ? '↑' : '↓')}
</th>
```

---

### 10. **CATA-73: Tabla de ratios con columnas**
- [ ] Columnas: Ticker, Precio, PER, EPS, CAGR, Margen Neto
- [ ] Datos de muestra (mock JSON)
- [ ] Formato numérico: $ para precio, % para márgenes

---

## 📋 FRONTEND B: PROCESOS

**Propietario:** Aldana Oviedo (@OviedoAldana)

### 11. **CATA-78: Componente ProcessCard reutilizable**
- [ ] Props: titulo, descripcion, icono, onClick
- [ ] Estados: hover (darker bg), active (border highlight)
- [ ] Responsive: 3 cols en desktop, 1 en mobile

---

## 🚀 CI/CD & INFRAESTRUCTURA

**Propietario:** Federico Monfa (@fmonfasani)

### 12. **CATA-93: Configurar webhooks Jira-GitHub**
- [ ] GitHub → Jira: issue closes when PR merges
- [ ] Jira → GitHub: comment when task updated
- [ ] Test webhook con PR real

---

### 13. **CATA-94: Activar frontend-ci.yml**
- [ ] ESLint para `/frontend`
- [ ] TypeScript `--noEmit`
- [ ] `npm run build` sin errores

---

### 14. **CATA-95: Configurar Coolify project**
- [ ] Crear proyecto CATA en Coolify
- [ ] Configurar variables de entorno
- [ ] Webhook URL generado para deploy automático
- [ ] (NO ACTIVAR AÚN — solo preparar)

---

### 15. **CATA-96: README de setup local**
- [ ] Cómo clonar repo
- [ ] Cómo instalar dependencias (backend + frontend)
- [ ] Cómo correr `npm run dev` y tests
- [ ] Cómo aplicar migraciones DB

**Entregables:**
- `/README.md` completo con instrucciones step-by-step

---

## 📊 Criterios de Aceptación - Sprint 2 COMPLETO

- [ ] Precios descargándose correctamente (10+ tickers)
- [ ] Financials parseándose de SEC (5+ empresas)
- [ ] Jobs cron funcionando sin errores
- [ ] Tests CI verdes para backend + frontend
- [ ] Tabla screener renderiza datos mock
- [ ] Documentación actualizada
- [ ] Sin bloqueadores para Sprint 3

---

## 🔄 Dependencias para Sprint 3

- **CATA-20..24 → CATA-30+**: Endpoint precios listo
- **CATA-68..70 → CATA-40+**: Financials en DB
- **CATA-72..73 → CATA-43**: Tabla screener lista para datos reales

---

## 📝 Notas

- Mateo: Enfocarse en parsing XBRL — es la parte más compleja
- Federico: Precios es rápido; ayuda a otros si quedan bloqueados
- Joaquin: Diseño de tabla es critical-path para Sprint 3
- CI/CD debe pasar completamente antes de hacer merge a main
