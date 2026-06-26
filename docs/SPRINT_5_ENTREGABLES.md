# Sprint 5 Entregables
**Período:** 20 de julio - 24 de julio de 2026 (1 semana)

---

## 📋 Resumen Ejecutivo

Sprint 5 se enfoca en **features avanzadas y optimización**. El objetivo es:
1. Watchlist personal (favoritos)
2. Alertas de precios
3. Exportación de datos (CSV, Excel)
4. Performance optimization + caching

**Status:** 16 tasks | **Asignación:** Joaquin (5), Aldana (4), Mateo (4), Federico (3)

---

## 🎨 FRONTEND A: SCREENER + WATCHLIST

**Propietario:** Joaquin Levis (@joaquinlevis)

### 1. **CATA-68: Botón "Agregar a watchlist"**
- [ ] Star icon en cada fila de tabla screener
- [ ] Click togglea: filled star (agregado) / outline (no agregado)
- [ ] Persiste en localStorage (cliente)
- [ ] Sincroniza con backend si hay autenticación

**Entregables:**
```tsx
// frontend/components/screener/WatchlistButton.tsx
export function WatchlistButton({ ticker }: Props) {
  const [isWatched, setIsWatched] = useState(false);
  
  return (
    <button onClick={() => setIsWatched(!isWatched)}>
      {isWatched ? '★' : '☆'} {ticker}
    </button>
  );
}
```

---

### 2. **CATA-69: Página /watchlist**
- [ ] Muestra solo empresas en watchlist
- [ ] Mismos filtros que screener principal
- [ ] Eliminar de watchlist: click derecho o botón trash
- [ ] Vacío: muestra "Agrega empresas para monitorear"

---

### 3. **CATA-70: Comparador de empresas**
- [ ] Seleccionar 2-4 empresas de watchlist
- [ ] Botón "Comparar"
- [ ] Tabla lado a lado: métricas de cada una
- [ ] Gráficos superpuestos (precio, CAGR, ROE)

**Criterios de aceptación:**
- [ ] Máximo 4 empresas simultáneamente
- [ ] Colores distintos para cada empresa
- [ ] Mobile: scroll horizontal si es necesario

---

### 4. **CATA-71: Exportar watchlist a CSV**
- [ ] Botón "Descargar watchlist"
- [ ] CSV con empresas del watchlist actual
- [ ] Incluye últimos ratios conocidos

---

### 5. **CATA-99: Alertas de precio**
- [ ] Interfaz: "Notificar si AAPL sube sobre $170"
- [ ] Almacena en localStorage (por ahora, sin backend)
- [ ] Muestra badge con # de alertas activas
- [ ] Click en badge muestra/edita alertas

---

## 📋 FRONTEND B: PROCESOS + DASHBOARD

**Propietario:** Aldana Oviedo (@OviedoAldana)

### 6. **CATA-100: Dashboard principal**
- [ ] Resumen: # empresas, cambio % del mercado, última actualización
- [ ] 4 cards: Descarga precios, Cálculo ratios, Watchlist, Comparador
- [ ] Quick links a paginas principales

---

### 7. **CATA-101: Estadísticas generales**
- [ ] Distribución PER (histograma)
- [ ] Distribución CAGR (histograma)
- [ ] Top 10 por PER, Top 10 por CAGR
- [ ] Última actualización de cada métrica

---

### 8. **CATA-102: Responsiveness + mobile UI**
- [ ] Todas las páginas en viewport < 600px
- [ ] Stack vertical en mobile
- [ ] Menú hamburguesa en lugar de sidebar
- [ ] Botones al menos 44x44px para touch

---

### 9. **CATA-103: Theming (light/dark mode)**
- [ ] Toggle en navbar
- [ ] Colores: light (#fff, #000) y dark (#1a1a1a, #f0f0f0)
- [ ] Persiste en localStorage
- [ ] Sistema de CSS variables para fácil cambio

---

## 💰 BACKEND B: OPTIMIZACIÓN

**Propietario:** Mateo Llorente (@mateollorente)

### 10. **CATA-107: Índices de DB para performance**
- [ ] `CREATE INDEX` en columnas frecuentes:
  - `precios_raw (ticker_sec, fecha_descarga DESC)`
  - `financials_raw (cik, periodo DESC)`
  - `ratios (per_ttm, cagr_5y)` para filtrados rápidos
- [ ] Analiza query plans con `EXPLAIN`

---

### 11. **CATA-108: Agregados pre-calculados**
- [ ] Vista materializada `ratios_latest` con últimos valores
- [ ] Refresh automático después de Job 2
- [ ] Queries al screener usan vista en lugar de tabla raw

---

### 12. **CATA-109: Endpoint /stats (estadísticas)**
- [ ] Retorna histogramas de PER, CAGR, etc.
- [ ] Query a vista materializada (< 100ms)
- [ ] Response cacheado por 1 hora

---

### 13. **CATA-110: Validación de datos rigurosa**
- [ ] Todos los inputs validados con Pydantic
- [ ] Rechazar valores fuera de rango (ej: PER > 1000, CAGR > 500%)
- [ ] Logging de rechazos para debugging

---

## 🔌 BACKEND A: WATCHLIST + ALERTAS

**Propietario:** Federico Monfa (@fmonfasani)

### 14. **CATA-99: Endpoint watchlist (future)**
- [ ] Placeholder para `GET/POST /user/watchlist` (autenticación pendiente)
- [ ] Por ahora: localStorage en frontend (implementado en CATA-68)
- [ ] Documentación para Sprint 6 cuando se agregue auth

---

### 15. **CATA-100: Health check endpoint**
- [ ] `GET /health` retorna status JSON
- [ ] Check: DB conectada, Jobs running, Cache healthy
- [ ] Response: `{"status": "ok", "timestamp": "2026-07-20T..."}` o error

---

### 16. **CATA-101: Documentación API final**
- [ ] OpenAPI/Swagger spec completo
- [ ] Actualizar `/docs/04-contrato-api.md`
- [ ] Ejemplos de todas las endpoints principales

---

## 📊 Criterios de Aceptación - Sprint 5 COMPLETO

- [ ] Watchlist completamente funcional (localStorage)
- [ ] Comparador de empresas funciona con 2-4 selecciones
- [ ] Dashboard muestra estadísticas en tiempo real
- [ ] Mobile UI responsive en todos los breakpoints
- [ ] Índices de DB mejoran query time > 50%
- [ ] Alertas guardadas en localStorage (backend preparado)
- [ ] Sin bloqueadores para Sprint 6

---

## 🔄 Dependencias para Sprint 6

- **CATA-68..71 → CATA-115**: Watchlist es feature estable
- **CATA-107..110 → CATA-114**: Performance listo para producción

---

## ⚠️ Puntos Críticos

- **CATA-70 (Comparador)**: UI compleja, start early
- **CATA-107 (Índices)**: Performance crítica si hay muchas empresas
- **CATA-102 (Mobile)**: No dejar para el final, probar constantemente

---

## 📝 Notas

- Joaquin: Watchlist es core feature, invierte tiempo en UX
- Aldana: Dashboard es "landing page" — prioridad visual
- Mateo: Índices de DB pueden no parecer "importantes" pero ahorran $ en servidor
- Federico: Health check es standard en producción, agregalo simple

---

## 🎯 Fin de Funcionalidad "Base"

Al final de Sprint 5, la aplicación tiene:
✅ Screener completo con filtros
✅ Detalle de empresas con gráficos
✅ Watchlist y comparador
✅ Admin panel con controles de jobs
✅ Dashboard y estadísticas
✅ Performance optimizada

Sprint 6 es **polish, testing, y deployment** único.
