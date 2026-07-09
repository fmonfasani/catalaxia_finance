# Plan detallado de ejecución — Pipeline completo (572 empresas)

> Plan operativo con **fases, tareas y entregables** para llevar el screener a producción:
> 500 S&P + 16 ADR + 56 BYMA-only, todos los ratios, replicable y actualizable con jobs.
> Contexto y arquitectura: [PLAN_PIPELINE_COMPLETO.md](PLAN_PIPELINE_COMPLETO.md).

Convenciones: `[ ]` pendiente · `[x]` hecho · **DoD** = definición de "terminado".
Los ratios de las 572 YA existen (tabla `ratios` EDGAR + screener CNV) → el grueso es
unificar + automatizar.

---

## FASE 1 — Unificar los 3 universos en el screener  ⏱ bajo · SIN dependencias
**Objetivo:** pasar de 72 a 572 empresas en la tabla `screener`, con provenance.

Tareas:
- [ ] 1.1 Auditar la tabla `ratios` (EDGAR): cobertura por grupo (sp500/adr_arg) de
      roe/per/p_book/eps/margen/cagr/payout. (Ya medido: ~500 S&P con ratios.)
- [ ] 1.2 Fijar el mapeo `ratios`→`screener` (reusar el del cableo ADR de s6:
      roe→ROE, per→PER, p_book→PriceBook, eps_anual→EPS, margen_neto→MargenNeto,
      deuda_ebitda→DeudaEBITDA, p_sales→PriceSales, payout→Payout, cagr_eps_5y→CAGR_EPS_5y).
- [ ] 1.3 Construir **`s7_unificar.py`**: inserta en `screener` las filas sp500 + adr desde
      `ratios`, con `fuente_fund='edgar'`, `grupo`, `sector` (de `empresas.sector_gics`),
      `Currency`. Idempotente (INSERT OR REPLACE por cik/cuit). NO toca las 72 AR de CNV.
- [ ] 1.4 Resolver la CLAVE del screener (hoy `cuit`): las S&P no tienen cuit → usar `cik`
      como clave unificada, o una columna `id` (cik para US, cuit para AR).
- [ ] 1.5 Traer precios/52w de `precios` para las S&P (join por cik).
- [ ] 1.6 Wire `s7` en `run_screener.py` (orden: s0→s2→s3→s4→s6→**s7**→s5).
- [ ] 1.7 Re-correr s7→s5 → `screener_export.csv` con 572.

**Entregables:** `s7_unificar.py` · `screener` con 572 filas · export CSV · s7 en el orquestador.
**DoD:** 572 filas; cobertura por ratio y por universo medida e impresa; cada fila con
`fuente_fund` (edgar/cnv) y `sector`; re-run idempotente (mismo resultado).

---

## FASE 2 — Completar ratios de calidad  ⏱ medio · depende de F1
**Objetivo:** cerrar payout con certeza y agregar el mejor termómetro de valuación.

Tareas:
- [ ] 2.1 **`payout_status`** (columna): clasificar cada empresa en `calculado` /
      `no_paga` (sin filing 339 en AR, o sin `.dividends` en yf) / `falta_dato`. Lógica en s6/s7.
- [ ] 2.2 Re-parsear los ~12 AR "falta_dato" desde el HTML del form 339 (job6 ya lo guardó)
      → recuperar el monto → payout real.
- [ ] 2.3 **EV/EBITDA** (columna): EV = market_cap + deuda neta; EBITDA ya está en facts/ratios.
      Calcular para las 572 (agregar al motor `calcular_ratios_base` + `ratios_cnv`).
- [ ] 2.4 **Margen operativo** (columna): OperatingIncome/Revenue — refleja el negocio real
      (sin ruido FX/RECPAM en AR).
- [ ] 2.5 Re-correr + medir cobertura de payout_status, EV/EBITDA, margen operativo.

**Entregables:** columnas `payout_status`, `ev_ebitda`, `margen_operativo` en el screener.
**DoD:** payout con 3 estados (≥80% con respuesta); EV/EBITDA con cobertura >70%; documentado
en el README del CSV.

---

## FASE 3 — Jobs de actualización periódica  ⏱ medio · depende de F1
**Objetivo:** `run_update.py` que refresca la base sin re-hacer todo.

Tareas:
- [ ] 3.1 **`run_update.py`** con modos `--daily` `--monthly` `--quarterly` `--annual`.
- [ ] 3.2 `upd_precios` (diario): yfinance precio/máx-mín 52s/market_cap para las 572. Idempotente.
- [ ] 3.3 `upd_ipc` (mensual): bajar el IPC nuevo de datos.gob.ar y hacer append a `ipc_nacional.csv`.
- [ ] 3.4 `upd_edgar` (trimestral): via API SEC, detectar CIKs con `lastFiled` nuevo → re-bajar
      SOLO esos companyfacts (incremental).
- [ ] 3.5 `upd_cnv` (trimestral): correr `job5_v2` sobre GUIDs nuevos (resume-safe con done log).
- [ ] 3.6 `upd_ratios`: recalcular ratios (base + cnv + IPC) tras edgar/cnv.
- [ ] 3.7 `upd_adr_ratios` (anual): `sec_adr_ratios` contra el 20-F nuevo.
- [ ] 3.8 `rebuild_screener`: s0→s2→s3→s4→s6→s7→s5.
- [ ] 3.9 Logging por corrida (`data/logs/upd_YYYYMMDD.log`) + manejo de errores (que un
      papel que falla no tumbe el job).

**Entregables:** `run_update.py` con los 4 modos + jobs individuales.
**DoD:** cada modo corre idempotente y con log; edgar/cnv incrementales (no re-bajan todo);
una corrida `--daily` actualiza precios en <5 min.

---

## FASE 4 — Reproducibilidad + scheduling  ⏱ bajo · depende de F1-F3
**Objetivo:** reconstrucción desde cero + automatización.

Tareas:
- [ ] 4.1 **`run_all.py`**: extract (edgar+cnv+yf+ipc+adr_ratios) → transform (ratios) →
      assemble (s0..s7) → export. End-to-end, idempotente.
- [ ] 4.2 Probar `run_all.py` (sobre la DB actual, con cache) → confirma que reconstruye.
- [ ] 4.3 Configurar **Task Scheduler** (Windows): tarea diaria (`run_update.py --daily`) y
      trimestral (`run_update.py --quarterly`).
- [ ] 4.4 `docs/screener/OPERACION.md`: cómo correr manual, cómo están programados los jobs,
      qué hacer si falla, cómo mover la DB entre máquinas.

**Entregables:** `run_all.py` · tareas programadas · `OPERACION.md`.
**DoD:** `run_all.py` reconstruye la base; scheduler configurado y probado; doc de operación.

---

## FASE 5 — Validación + entrega  ⏱ bajo · depende de F1-F4
**Objetivo:** confiabilidad + publicación.

Tareas:
- [ ] 5.1 Validación cruzada (doble-nelson) sobre las 572: identidades, DuPont, rangos.
- [ ] 5.2 Reporte de cobertura final por ratio y por universo (S&P / ADR / BYMA).
- [ ] 5.3 Export final + actualizar `screener_export_README.md` (fuentes, flags, limitaciones).
- [ ] 5.4 `git commit + push` (código, docs, CSV; DB aparte). Actualizar `PROBLEMAS_ACTUALES`.

**Entregables:** screener productivo validado + en GitHub.
**DoD:** cobertura documentada; validación sin outliers absurdos; repo al día; DB versionada aparte.

---

## FASE 6 — Expansión (opcional, después)
- [ ] 6.1 Sumar ADR-BR/LATAM (38 más, ya en `ratios`) → ~610 empresas.
- [ ] 6.2 Ratios propios de bancos (parser bank-aware de la plantilla financiera CNV).
- [ ] 6.3 Mina 556 (CNV completo).

---

## Cronograma sugerido (dependencias)
```
F1 (unificar) ──► F2 (ratios calidad) ──► F5 (validar/entregar)
      └──────────► F3 (jobs update) ──► F4 (run_all + scheduling) ──► F5
```
Empezar por **F1** (rinde muchísimo: 572 en el screener de una). F2 y F3 pueden ir en paralelo
después. F4 y F5 cierran. F6 es futuro.

## Riesgos / notas
- **Clave unificada**: las S&P no tienen cuit → definir bien la clave (cik para US, cuit para AR).
  Es la decisión de diseño más importante de F1.
- **Rate limits**: SEC (10 req/s, User-Agent) y yfinance (429) → respetar delays en los jobs.
- **La DB (754MB) no va a git** → los jobs corren donde está la DB (local/VM), no en GitHub Actions.
