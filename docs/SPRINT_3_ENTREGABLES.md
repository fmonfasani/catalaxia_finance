# Sprint 3 Entregables
**Período:** 6 de julio - 10 de julio de 2026 (1 semana)

---

## 📋 Resumen Ejecutivo

Sprint 3 se enfoca en **cálculos financieros core**. El objetivo es:
1. Implementar TTM, CAGR, ratios complejos
2. Conectar frontend con datos reales del backend
3. Filtrado y búsqueda en screener
4. Manejo de datos NULL y edge cases

**Status:** 16 tasks | **Asignación:** Mateo (8), Joaquin (4), Federico (2), Aldana (2)

---

## 💰 BACKEND B: FINANCIALS (CORE MATH)

**Propietario:** Mateo Llorente (@mateollorente)

### 1. **CATA-32: Implementar TTM (Trailing Twelve Months)**
- [ ] Estrategia A: 4 trimestres consecutivos (preferida)
- [ ] Estrategia B: Annual + YTD Actual - YTD Prior
- [ ] Estrategia C: Último annual solo
- [ ] Selecciona automáticamente basada en disponibilidad

**Entregables:**
```python
# backend/calculators/ttm.py
def calcular_ttm_flujo(
    financials: List[FinancialPeriod],
    metrica: str
) → Optional[float]:
    """
    Calcula TTM con fallback A → B → C
    Retorna None si hay gaps o datos inconsistentes
    """
```

**Criterios de aceptación:**
- [ ] Tests con 3 estrategias diferentes
- [ ] Verifica fechas (no gaps > 5 días entre trimestres)
- [ ] Handles casos donde no hay 4 trimestres

---

### 2. **CATA-33: Implementar CAGR (5-year)**
- [ ] Requiere mínimo 6 años de datos anuales (10-K)
- [ ] Fórmula: `(valor_final / valor_inicial)^(1/5) - 1`
- [ ] Retorna NULL si no hay suficientes datos

**Entregables:**
```python
def calcular_cagr(
    valores_anuales: Dict[int, float]  # {2021: 100, 2022: 120, ...}
) → Optional[float]:
    """CAGR de 5 años. Requiere 6+ data points."""
```

---

### 3. **CATA-34: Calcular ratios de valuación (PER, EPS)**
- [ ] PER = Precio / EPS_TTM
- [ ] EPS_TTM = NetIncome_TTM / Shares_Diluted
- [ ] PER = NULL si EPS ≤ 0

**Criterios de aceptación:**
- [ ] Tests con empresas reales
- [ ] PER nunca negativo
- [ ] EPS maneja divisiones por cero

---

### 4. **CATA-35: Calcular ratios de rentabilidad**
- [ ] Margen Neto = NetIncome_TTM / Revenue_TTM
- [ ] ROE_5Y = CAGR(NetIncome / Equity anual)
- [ ] Todas las métricas NULL si denominador ≤ 0

---

### 5. **CATA-36: Calcular ratios de flujo de caja**
- [ ] FCF_TTM = CFO_TTM - CapEx_TTM
- [ ] FCFonCE (dos variantes): FCF / (Equity + LT_Debt)
- [ ] FCFonCE Neto: FCF / (Equity + Deuda_Total - Cash)

---

### 6. **CATA-37: Calcular ratios de endeudamiento**
- [ ] Deuda/EBITDA (LP): LT_Debt / EBITDA_TTM
- [ ] Deuda/EBITDA (Total): (LT + ST Debt) / EBITDA_TTM
- [ ] Payout = Dividendos_TTM / NetIncome_TTM

---

### 7. **CATA-40: Job 2: Calcular ratios**
- [ ] Lee financials_raw + precios_raw
- [ ] Calcula todos los ratios para cada empresa
- [ ] UPSERT en tabla `ratios`
- [ ] Loguea en `jobs` / `job_errores`

**Entregables:**
```python
# backend/app/jobs/calculate_ratios.py
async def job_calculate_ratios():
    """Calcula ratios para todas las empresas"""
    # Lee precios_raw + financials_raw
    # Ejecuta CATA-32..37
    # Inserta en ratios
```

---

### 8. **CATA-41: Tests de ratios (coverage > 80%)**
- [ ] Tests para cada ratio con datos reales de empresas
- [ ] Edge cases: NULL inputs, negativos, división por cero
- [ ] Verifica consistencia entre variantes

---

## 🎨 FRONTEND A: SCREENER

**Propietario:** Joaquin Levis (@joaquinlevis)

### 9. **CATA-42: Conectar tabla screener con API real**
- [ ] Endpoint `GET /screener?limit=100` retorna lista de ratios
- [ ] Frontend fetch en `useEffect`
- [ ] Manejo de loading + error states

**Entregables:**
```tsx
// frontend/hooks/useScreener.ts
export function useScreener() {
  const [data, setData] = useState<Ratio[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetch('/api/screener')
      .then(r => r.json())
      .then(setData);
  }, []);
}
```

---

### 10. **CATA-43: Filtrado por rango (PER, CAGR, etc)**
- [ ] Sliders: Min/Max PER, Min/Max CAGR
- [ ] Filter activo actualiza tabla en tiempo real (debounced)
- [ ] Muestra "0 resultados" si no hay matches

**Criterios de aceptación:**
- [ ] Filtros son independientes (AND logic)
- [ ] Performance: filtrar 1000 rows < 100ms
- [ ] Mobile: sliders funcionales en pantalla chica

---

### 11. **CATA-44: Búsqueda por ticker/nombre**
- [ ] Input de búsqueda filtra por ticker o nombre empresa
- [ ] Case insensitive, búsqueda parcial ("AAP" matches "AAPPL")
- [ ] Debounce 300ms para no rerender excesivo

---

### 12. **CATA-45: Exportar tabla a CSV**
- [ ] Button "Descargar CSV"
- [ ] Descarga datos actuales de tabla (con filtros aplicados)
- [ ] Nombre: `screener_YYYY-MM-DD.csv`

---

## 📋 FRONTEND B: PROCESOS

**Propietario:** Aldana Oviedo (@OviedoAldana)

### 13. **CATA-46: Página /procesos/descarga-precios**
- [ ] Describe qué hace Job 1A
- [ ] Última ejecución, próxima ejecución
- [ ] Link a logs si hay errores

---

### 14. **CATA-47: Página /procesos/calculo-ratios**
- [ ] Describe qué hace Job 2
- [ ] Muestra últimas 5 ejecuciones (fecha, duración, status)
- [ ] Opción manual "Ejecutar ahora" (admin only)

---

## 🚀 CI/CD & INFRAESTRUCTURA

**Propietario:** Federico Monfa (@fmonfasani)

### 15. **CATA-72: Documentar nuevas migraciones**
- [ ] Guía de cómo crear nuevas migraciones
- [ ] Naming: `00X_descripcion.sql`
- [ ] Rollback strategy

---

### 16. **CATA-73: Monitoreo de jobs básico**
- [ ] Endpoint `GET /jobs/status` retorna últimas ejecuciones
- [ ] Log en DB cuándo inicio/fin cada job
- [ ] Alertas si job tarda > 5 min o falla

---

## 📊 Criterios de Aceptación - Sprint 3 COMPLETO

- [ ] Todos los ratios calculándose correctamente
- [ ] Screener muestra datos reales + filtrado funciona
- [ ] CSV export genera archivos válidos
- [ ] Jobs 1A, 1B, 2 corriendo en schedule
- [ ] Coverage tests > 75% en calculators
- [ ] Sin bloqueadores para Sprint 4

---

## 🔄 Dependencias para Sprint 4

- **CATA-32..37 → CATA-50+**: Ratios calculados
- **CATA-42..45 → CATA-52+**: Screener funcional es baseline

---

## ⚠️ Puntos Críticos

- **CATA-32 (TTM)**: Es la parte más compleja. Mateo: start ASAP
- **CATA-42**: Sin este, Joaquin queda bloqueado en Sprint 4
- **Fallbacks**: CATA-33..37 deben retornar NULL, no estimar valores

---

## 📝 Notas

- Mateo: Revisar `/research/docs/FORMULAS_RATIOS.md` para detalles exactos
- Joaquin: Diseño de filtros debe ser mobile-responsive
- Aldana: Páginas de procesos son "info only" por ahora
- Federico: Monitoreo de jobs es importante para producción
