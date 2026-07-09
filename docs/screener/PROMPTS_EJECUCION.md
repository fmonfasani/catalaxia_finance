# Prompts de ejecución — Pipeline completo

> Prompts para que un agente ejecute el [PLAN_DETALLADO_EJECUCION.md](PLAN_DETALLADO_EJECUCION.md)
> fase por fase. Copiar/pegar. El plan es la fuente de verdad de las tareas; estos prompts
> orientan y ponen las reglas.

---

## PROMPT MAESTRO (pegar UNA vez, al arrancar)

```
Sos un agente de data engineering. Vas a ejecutar el pipeline completo del screener
(500 S&P + 16 ADR + 56 BYMA-only) siguiendo un plan ya escrito. Ejecutás FASE POR FASE, en
orden, parando en el "DoD" (definición de terminado) de cada fase para que el dueño confirme.

## Leé primero (tu spec)
- docs/screener/PLAN_DETALLADO_EJECUCION.md   ← EL PLAN: tareas por fase + DoD. Seguilo.
- docs/screener/PLAN_PIPELINE_COMPLETO.md     ← arquitectura E-T-L
- docs/screener/ESTADO_PIPELINE.md            ← estado actual (qué YA está hecho)
- docs/screener/RETOMAR_AQUI.md               ← contexto general del proyecto
- data/screener_export_README.md              ← el entregable y sus flags

## Precondición
data/screener.db (~754MB) DEBE estar presente (no está en git). Si no está, frená y pedila.
Instalá deps: pip install -r requirements.txt.

## Reglas duras
1. FASE POR FASE en orden (F1→F2→…). No saltees. Al terminar una fase, imprimí su DoD y PARÁ
   para confirmación del dueño antes de seguir.
2. Idempotente: cada stage reconstruye su salida (re-corrible sin duplicar). Provenance por
   dato (columna fuente_fund = edgar/cnv).
3. NO destruir data cruda: cnv_estados original queda; lo v2/norm va aparte.
4. Rate limits: SEC 10 req/s + header User-Agent; yfinance 429 → delays. UNA instancia a la vez.
5. NO git commit/push sin orden del dueño. Scratch (_*.py, temp_*, test_*) NO se commitea.
6. Reusá lo existente: calcular_ratios_base.py, precios_y_valuacion.py, el mapeo de
   usar_edgar_para_adr() en s6_ajustes.py. No reinventes.

## Decisión de diseño CLAVE (resolver en Fase 1)
Las S&P NO tienen CUIT; el screener hoy se keyea por cuit. Definí una CLAVE UNIFICADA:
`cik` para US/ADR, `cuit` para AR (o una columna `id` genérica). Es lo primero de la Fase 1.

## Empezá
Ejecutá la FASE 1. Cuando el dueño confirme el DoD, seguís con la Fase 2, y así.
```

---

## FASE 1 — Unificar (72 → 572)
```
Ejecutá la FASE 1 del plan (PLAN_DETALLADO_EJECUCION.md, tareas 1.1-1.7).
Objetivo: pasar de 72 a 572 empresas en la tabla `screener`.
1. Resolvé primero la CLAVE UNIFICADA (1.4): cik para US/ADR, cuit para AR.
2. Construí s7_unificar.py: inserta las 499 S&P + 16 ADR desde la tabla `ratios` (EDGAR) al
   screener, reusando el mapeo de columnas de usar_edgar_para_adr() en s6. Poné fuente_fund,
   grupo y sector (de empresas.sector_gics). Traé precio/52w de `precios` (join por cik).
   Idempotente (INSERT OR REPLACE). NO toques las 72 AR de CNV.
3. Wire s7 en run_screener.py (orden: s0→s2→s3→s4→s6→s7→s5). Re-corré s7→s5.
DoD: 572 filas en screener; cobertura por ratio y por universo (S&P/ADR/BYMA) impresa; cada
fila con fuente_fund + sector. PARÁ y mostrá el DoD.
```

## FASE 2 — Ratios de calidad (payout_status + EV/EBITDA)
```
Ejecutá la FASE 2 (tareas 2.1-2.5).
- payout_status: calculado / no_paga (sin form 339 en AR o sin .dividends en yf) / falta_dato.
- Re-parseá los ~12 AR "falta_dato" del HTML del form 339 (ya guardado).
- EV/EBITDA (EV = market_cap + deuda neta) y margen_operativo, para las 572.
DoD: payout con 3 estados (≥80% con respuesta); EV/EBITDA cobertura >70%; documentado en el
README del CSV. PARÁ y mostrá el DoD.
```

## FASE 3 — Jobs de actualización
```
Ejecutá la FASE 3 (tareas 3.1-3.9).
Construí run_update.py con modos --daily (precios yf), --monthly (IPC INDEC), --quarterly
(EDGAR incremental por lastFiled + CNV job5_v2 nuevos GUIDs + recompute ratios + rebuild
screener), --annual (sec_adr_ratios). Logging por corrida. Idempotente e incremental.
DoD: cada modo corre con log; edgar/cnv incrementales; --daily <5 min. PARÁ y mostrá el DoD.
```

## FASE 4 — Reproducibilidad + scheduling
```
Ejecutá la FASE 4 (tareas 4.1-4.4).
run_all.py (extract→transform→assemble→export, end-to-end). Probalo. Configurá Task Scheduler
(Windows): diario (--daily) y trimestral (--quarterly). Escribí docs/screener/OPERACION.md.
DoD: run_all reconstruye la base; scheduler configurado; OPERACION.md listo. PARÁ y mostrá el DoD.
```

## FASE 5 — Validación + entrega
```
Ejecutá la FASE 5 (tareas 5.1-5.4).
Validación cruzada (doble-nelson) sobre las 572. Reporte de cobertura por ratio y universo.
Export final + actualizar screener_export_README.md. Con OK del dueño: git commit + push.
DoD: cobertura documentada; validación sin outliers absurdos; repo al día. PARÁ y mostrá el DoD.
```

## FASE 6 — Expansión (opcional, solo con luz verde)
```
Ejecutá la FASE 6 (tareas 6.1-6.3): sumar ADR-BR/LATAM (ya en `ratios`), ratios de bancos
(parser bank-aware), mina 556. NO arrancar sin confirmación del dueño.
```
