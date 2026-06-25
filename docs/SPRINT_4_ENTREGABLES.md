# Sprint 4 Entregables
**Período:** 13 de julio - 17 de julio de 2026 (1 semana)

---

## 📋 Resumen Ejecutivo

Sprint 4 se enfoca en **refinamiento y detalle**. El objetivo es:
1. Página de detalle de empresa (ticker individual)
2. Gráficos y visualización de datos históricos
3. Perfeccionar filtros y UX
4. Preparar para producción (logging, errores)

**Status:** 15 tasks | **Asignación:** Joaquin (5), Aldana (4), Federico (4), Mateo (2)

---

## 🎨 FRONTEND A: SCREENER + DETALLE

**Propietario:** Joaquin Levis (@joaquinlevis)

### 1. **CATA-50: Página /cedears/[ticker]**
- [ ] Renderiza detalle de una empresa
- [ ] Path dinámico: `/cedears/AAPL`
- [ ] Obtiene datos de `GET /api/cedears/:ticker`

**Entregables:**
```tsx
// frontend/app/cedears/[ticker]/page.tsx
export default function TickerPage({ params }: Props) {
  const ticker = params.ticker;
  // Fetch y renderiza detalle
}
```

---

### 2. **CATA-51: Card de información general**
- [ ] Nombre empresa, logo (si aplica), sector
- [ ] Datos: Precio, PER, EPS, Market Cap
- [ ] Cambio % del día (+ color rojo/verde)

---

### 3. **CATA-52: Gráfico de precio histórico (52w)**
- [ ] Usa `recharts` o `chart.js`
- [ ] Eje X: fechas (cada 2 semanas), Eje Y: precio USD
- [ ] Línea roja: high 52w, línea azul: low 52w, línea gris: actual

**Criterios de aceptación:**
- [ ] Responsive (mobile-friendly)
- [ ] Tooltip con fecha + precio al hover
- [ ] Legend visible

---

### 4. **CATA-53: Tabla de ratios históricos (5 años)**
- [ ] Columnas: Año, EPS, CAGR_EPS, Margen Neto, ROE, FCFonCE
- [ ] Ordenable por columna
- [ ] Highlight celdas con valores negativos (rojo)

---

### 5. **CATA-54: Link de screener → detalle**
- [ ] Clicking en row de tabla screener abre `/cedears/TICKER`
- [ ] Mantiene filtros en URL (ej: `?per_max=20&cagr_min=10`)
- [ ] Botón "Volver" regresa con filtros intactos

---

## 📋 FRONTEND B: PROCESOS

**Propietario:** Aldana Oviedo (@OviedoAldana)

### 6. **CATA-55: Página /procesos/descargas**
- [ ] Timeline de descargas (Job 1A)
- [ ] Tabla: Fecha, Tickers descargados, Duración, Status
- [ ] Mostrar errores si los hubo

---

### 7. **CATA-56: Página /procesos/calculos**
- [ ] Timeline de cálculos (Job 2)
- [ ] Tabla: Fecha, Empresas procesadas, Duración, Ratios calculados, Status
- [ ] Opción manual para ejecutar (admin only, está deshabilitada)

---

### 8. **CATA-74: Panel admin básico**
- [ ] URL: `/admin` (requiere autenticación)
- [ ] Botón: "Ejecutar Job 1A" (descargar precios ahora)
- [ ] Botón: "Ejecutar Job 2" (calcular ratios ahora)
- [ ] Ver logs en tiempo real (tail -f style)

**Criterios de aceptación:**
- [ ] Solo Federico y admins pueden acceder
- [ ] Confirmación "¿Ejecutar ahora?" antes de correr

---

### 9. **CATA-75: Cards de procesos mejorado**
- [ ] Muestra estado actual de cada job (Green/Yellow/Red)
- [ ] Last run time + next scheduled run
- [ ] Click para ver detalles completos

---

## 🔌 BACKEND A: PRECIOS

**Propietario:** Federico Monfa (@fmonfasani)

### 10. **CATA-76: Endpoint GET /cedears/:ticker**
- [ ] Retorna detalle de empresa + últimos 52w de precios
- [ ] Response incluye: nombre, logo_url, sector, precios históricos

**Entregables:**
```json
{
  "ticker": "AAPL",
  "nombre": "Apple Inc",
  "sector": "Technology",
  "precios_52w": [
    {"fecha": "2025-07-01", "precio": 150.23, "high_52w": 199, "low_52w": 120}
  ]
}
```

---

### 11. **CATA-77: Caché de datos históricos**
- [ ] Redis (o en-memory): cache de precios 52w
- [ ] TTL: 1 hora (refresh automático)
- [ ] Fallback: query DB si cache falla

---

## 💰 BACKEND B: FINANCIALS

**Propietario:** Mateo Llorente (@mateollorente)

### 12. **CATA-50: Endpoint GET /cedears/:ticker/ratios**
- [ ] Retorna ratios históricos (últimos 5 años)
- [ ] Response: lista de años con todos los ratios

---

### 13. **CATA-51: Endpoint GET /api/screener/csv**
- [ ] Genera CSV con datos actuales filtrados
- [ ] Headers: Ticker, Nombre, Precio, PER, EPS, CAGR, ...
- [ ] UTF-8 encoding

---

## 🚀 CI/CD & INFRAESTRUCTURA

**Propietario:** Federico Monfa (@fmonfasani)

### 14. **CATA-78: Logging avanzado (production-ready)**
- [ ] Todos los jobs loguean en formato JSON
- [ ] Campos: timestamp, job_id, status, duration_ms, error (si aplica)
- [ ] Logs en `backend/logs/` (rotación diaria)

**Entregables:**
```python
# backend/logger.py
def log_job_execution(job_name: str, status: str, duration: float):
    logger.info({
        "job": job_name,
        "status": status,
        "duration_ms": duration,
        "timestamp": datetime.utcnow().isoformat()
    })
```

---

### 15. **CATA-79: Error handling y retry logic**
- [ ] Jobs fallan gracefully (no crash total)
- [ ] Reintento automático si fallan (exponential backoff)
- [ ] Alertas a Slack si 3+ intentos fallan consecutivos
- [ ] Tabla `job_errores` con stack trace completo

---

## 📊 Criterios de Aceptación - Sprint 4 COMPLETO

- [ ] Página de detalle completamente funcional
- [ ] Gráficos renderizando datos reales
- [ ] Panel admin funcionando (solo Federico)
- [ ] Logging de jobs en producción
- [ ] Performance: detalle page carga < 2s
- [ ] Sin bloqueadores para Sprint 5

---

## 🔄 Dependencias para Sprint 5

- **CATA-50..54 → CATA-60+**: Detalle page necesario antes de QA
- **CATA-76..77 → CATA-50**: Endpoint requerido

---

## ⚠️ Puntos Críticos

- **CATA-52**: Gráfico es visual-critical. Joaquin: asegura performance con 100+ puntos
- **CATA-74**: Panel admin debe estar protegido (NO exponer endpoints sin auth)
- **CATA-78**: Logging debe estar desde Day 1 en prod para debugging

---

## 📝 Notas

- Joaquin: Las transiciones entre screener y detalle deben ser smooth
- Aldana: Admin panel puede ser simple pero debe ser útil
- Federico: Logging y retry logic previenen nightmares en producción
- Mateo: Caché de ratios es importante para performance con muchas empresas
