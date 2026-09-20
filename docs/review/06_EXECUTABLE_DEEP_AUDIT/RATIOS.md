# Ficha: RATIOS — 4 motores + materializadores

### MOTOR 1: calcular_ratios_base.py (SEC-SQLite, producto)
- Fuente: `facts` (WHERE cik=? AND concepto IS NOT NULL) + meta de `empresas` (ticker, esquema, moneda, sector). Loop por CIKs con fecha_facts.
- Output: `ratios` (DROP TABLE + CREATE con cik PK) — destructividad: reemplazo total (regenerable).
- Fórmulas: `calcular(cur, cik)` (rasgos por esquema contable; moneda de `empresas`). NIL/negativos: `[NO-DETERMINABLE]` sin lectura de cuerpo (comparación numérica no ejecutada — ver 05 §23).
- Consumidor: s4/s6..s9 (producto). Tests: ninguno directo → TEST NO EXISTE (cobertura vía e2e de rebuild, no unitaria).
- PRODUCTIVO CONFIRMADO (vía quarterly rebuild + artefactos). Riesgo R2 (DROP+recreate + columna `per` acoplada a precios_y_valuacion).

### MOTOR 2: ratio_engine.py + ratio_defs.py + ratio_inputs.py (SEC-PG, motor)
- Fuente: `derived.fact` (sql_insumos, joins source_fact_ids) + `market_price_daily` + `identity_v1` (entidad por CIK con assertion VERIFIED).
- Funciones: `calcular_ev_sales/eps/pb/pe` + `evidencia_de` (con cik, accession, parsed_*). Output: `derived.ratio` (solo `--persist`).
- NIL/negativos: tratamiento en funciones (cuerpo no auditado línea a línea; comparación numérica ND).
- Tests: test_ratio_engine_ev_sales (TEST EXISTE). Consumidor de `derived.ratio`: ND.
- PRODUCTIVO PROBABLE. Riesgo R2 (sin lector verificado; autoridad v1 exigida).

### MOTOR 3: f4_ratios.py (CNV-legacy)
- Fuente: `fact_financials`. Output: `fact_ratios` (DROP+CREATE). Sin caller productivo (solo run_pipeline legacy). LEGACY. Riesgo R1 (inactivo; tablas huérfanas con posible lector ND).

### MOTOR 4: s2_ratios_cnv.py (CNV-canónico, producto)
- Fuente: `cnv_estados_norm` + `mapa_entidades` + `fiscal_calendar`. `calcular_cagr(valores_hist, ipc, years=5)` (usa IPC INDEC). Output: `ratios_cnv` (DROP+CREATE).
- Consumidor: s4 (producto). PRODUCTIVO CONFIRMADO (vía rebuild). Riesgo R2 (DROP+recreate; dependencia IPC mensual).

### Materializadores/derivados
- sec_adr_ratios → `adr_ratios` (ratio oficial 20-F, fuente externa; annual). jpm_adr → `adr_dividendos` + UPDATE screener. cedear_ratios → `cedear_ratios` + UPDATE screener. flags_calidad → UPDATE `ratios`. load_screener_ratios → `screener_ratios(_hist)`. ratios_ttm/per_ttm (cnv/metadata, ventana TTM). s7b/s7c (eps_base_per, cagr → UPDATE screener).
- Todos C8 con fuente propia (D8 confirmado); ninguno recalcula lo mismo que otro con la misma fuente (veredicto §13: dos motores calculan el mismo ratio nominal —p.ej. per— sobre dominios distintos; equivalencia numérica `[NO-DETERMINABLE]`).

### Veredicto auditoría ratios (§13)
Fuente/fórmula/período/unidad/moneda/numerador/denominador/NIL/negativos/output/provenance/consumidor difieren por dominio (tabla §8 de 05). No se ejecutó comparación numérica → equivalencia real `[NO-DETERMINABLE]`; duplicación confirmada solo a nivel D2/parcial, no sustitución.
