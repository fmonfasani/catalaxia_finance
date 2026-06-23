# ❌ Scripts Fallidos: Scraping de Investing.com

Este directorio contiene todos los intentos de scraping de Investing.com que **NO funcionaron**.

Se mantiene aquí como **referencia histórica** para que los colaboradores vean:
- Qué se intentó
- Por qué falló
- Qué lecciones se aprendieron

---

## ¿Por Qué Estos Scripts No Funcionan?

### 1. **Protecciones Anti-Scraping de Investing.com**
Investing.com implementa varias capas de protección:
- CloudFlare DDoS protection
- User-Agent validation
- JavaScript rendering (contenido dinámico)
- Rate limiting agresivo
- Session validation
- IP blocking

### 2. **Cambios Frecuentes de HTML**
- La estructura del HTML cambia regularmente
- Los selectores CSS/XPath se rompen constantemente
- Requeriría mantenimiento continuo

### 3. **Limitaciones Técnicas**
- Violación de Términos de Servicio
- Datos inconsistentes vs datos oficiales
- No es una fuente de verdad confiable

---

## Scripts Incluidos

| Script | Intención | Por Qué Falló |
|--------|-----------|--------------|
| `demo_api_direct.py` | API directa de Investing | API no es pública |
| `demo_inspect_investing.py` | Inspeccionar estructura | Datos dinámicos (JavaScript) |
| `demo_inspect_page.py` | Análisis de página | CloudFlare bloqueó |
| `demo_network_inspection.py` | Análisis de red | Sesiones invalidadas |
| `demo_scraping_interactive.py` | Selenium + interacción | Rate limiting agresivo |
| `demo_scraping_stealth.py` | Headers falsificados | IP bloqueado |
| `demo_scraping_working.py` | Último intento | Funcionó por ~5 minutos, luego bloqueado |
| `demo_session_persistence.py` | Mantener sesión | Cookies expiradas rápidamente |
| `demo_comparativa_*.py` | Comparar con SEC EDGAR | Investing bloqueó antes de terminar |

---

## ¿Cuál Era la Alternativa?

### ✅ SEC EDGAR (La solución real)

En lugar de scraping inestable:
```python
# Fácil, oficial, gratuito, confiable
import yfinance as yf
ticker = yf.Ticker("AAPL")
data = ticker.info  # Todos los datos necesarios
```

**Ventajas:**
- ✅ API oficial (SEC)
- ✅ Datos auditados
- ✅ Sin rate limiting razonable
- ✅ 99% similar a Investing.com
- ✅ Legal y ético

---

## Lecciones Aprendidas

1. **No hacer scraping si hay una API oficial** ← ⭐ Lección principal
2. **Las protecciones anti-scraping existen por razones legales**
3. **Investing.com es una agregadora, no la fuente original** (EDGAR lo es)
4. **Mantener scrapers es caro en tiempo y frágil**
5. **yfinance + SEC EDGAR = solución industrial**

---

## Para Colaboradores

Si alguna vez necesitan descargar datos financieros:

**❌ NO hacer:**
```bash
python demo_scraping_working.py  # Esto ya no funciona
```

**✅ HACER:**
```bash
python scripts/screener/02_descargar_precios_yfinance.py
python scripts/screener/06_descargar_datos_edgar.py
```

Ver [`../PLAN_SCREENER_218_ACCIONES.md`](../PLAN_SCREENER_218_ACCIONES.md) para el flujo completo.

---

**Conclusión:** Este directorio es un museo de intentos fallidos. La solución real está en la carpeta `../scripts/`.

No repitan estos scripts. Usen las fuentes oficiales.
