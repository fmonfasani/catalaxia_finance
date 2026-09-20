# Plan de QA y Riesgos

> Cómo probamos que funciona, y qué puede salir mal (con su plan B). Dueño: Federico.

---

## 1. Checklist de QA (Semana 4 — antes de entregar)

**API**
- [ ] Cada endpoint responde el shape de `04_CONTRATO_API.md` (happy-path).
- [ ] Cada endpoint maneja error (404 empresa inexistente) y vacío (filtro sin resultados).
- [ ] `/cobertura` devuelve 572 / 733 / 144 CEDEARs.
- [ ] Paginación y filtros dan resultados coherentes.
- [ ] `openapi.json` completo y navegable en `/docs`.

**Frontend**
- [ ] Screener: 572 empresas, sorting, paginación, toggle ARS/USD, export CSV.
- [ ] Filtros (rangos + flag de calidad) filtran de verdad.
- [ ] Detalle: fundamentales + panel de instrumentos (ISIN/precio/ratio) + dividendos ADR + vista CEDEAR.
- [ ] Estados vacío / loading / error en todas las vistas.
- [ ] Responsive (desktop + mobile), sin scroll horizontal.
- [ ] Chips de provenance visibles; disclaimers por universo (no comparar BYMA vs S&P 1:1).

**Datos (spot-check)**
- [ ] AAPL PER ≈ 37.9 · JPM ≈ 15.3 · GGAL ratio ADR 10 · AAPL CEDEAR 20:1.
- [ ] CCL coherente (~1.578) en los ADRs.
- [ ] Ninguna empresa "no significativa" aparece limpia en rankings.

**Infra**
- [ ] API en HTTPS, `Restart=always`, sobrevive reinicio.
- [ ] Backup diario de Postgres verificado (restaurar uno de prueba).
- [ ] Jobs registran en la tabla `jobs`.

## 2. Cómo se prueba cada entregable semanal
- Se prueba **de punta a punta** (front → API → Postgres en la VPS), no solo unit.
- El viernes, la demo **es** la prueba de aceptación del entregable (`07`).

## 3. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación | Dueño |
|---|---|---|---|
| **Backend atrasa y bloquea al front** | alto | Contrato de API + mocks el día 1; front nunca espera | Federico |
| **VPS/dominio demora del lado del cliente** | medio | Usar VPS propia + dominio provisorio; Marcelo no es bloqueante (`09`) | Federico |
| **Cambio de shape rompe al front** | medio | El contrato se versiona y se avisa antes de mergear (`08 §4`) | Mateo/Federico |
| **Alcance se estira (pedidos nuevos)** | alto | OUT explícito en `01`; entra por change request | Federico |
| **Data con error → parece bug nuestro** | medio | Provenance (source_url) prueba que el error es de la fuente, no del cálculo | Federico |
| **Un colega se traba callado** | medio | Regla: bloqueos se avisan el mismo día (`08 §7`); rúbrica de autonomía (`07`) | todos |
| **Postgres/infra se cae** | medio | `Restart=always` + backups diarios + monitoreo básico | Federico |
| **Comparar BYMA vs S&P engaña al usuario** | medio (reputacional) | UI fuerza separación por universo + disclaimers | Aldana |

## 4. Criterio de "listo para entregar"
Todo el checklist de §1 en verde **y** los criterios de aceptación de las 4 semanas (`07`) cumplidos.
Si algo queda amarillo, se documenta como limitación conocida (no se oculta).
