# Plan v2 — Datos CNV confiables (re-extracción robusta)

> Objetivo: **datos CNV con máxima integridad y consistencia** para el screener,
> corrigiendo de raíz los 8 problemas que descubrimos en el v1. No es empezar de cero:
> se conserva el descubrimiento (jobs 1-4) y se re-hace **solo la extracción** de forma
> robusta. Ver el v1 en [PLAN_ETL_SCREENER_CNV.md](PLAN_ETL_SCREENER_CNV.md) y el estado
> general en [RETOMAR_AQUI.md](RETOMAR_AQUI.md).

---

## Qué aprendimos en el v1 (→ los principios del v2)

| # | Problema descubierto | Principio v2 |
|---|---|---|
| 1 | El parser saca escala rota en filings recientes (~2024+) → basura en el último período | **Arreglar el parser** para el template nuevo (y el viejo) |
| 2 | `job5` NO guardó el HTML crudo → cualquier fix obliga a re-bajar | **Guardar SIEMPRE el HTML crudo** → futuros fixes = re-parsear (segundos) |
| 3 | Claves cruzadas (`cik`=CUIT vs `BYMA-*`) → hubo que normalizar después | **Claves canónicas desde el origen** (cik + ticker + cuit en cada fila) |
| 4 | Mezcla de vintages NIC 29 → CAGR quedó `vintage_mixto` (aproximado) | **Capturar la fecha de reexpresión + la columna comparativa** → serie consistente |
| 5 | La identidad contable NO caza escalas rotas (si todo el período está mal, cierra igual) | **Validación cross-período** (comparar cada período contra la historia de la empresa) |
| 6 | Bancos usan plantilla financiera → no parsean con códigos estándar | **Detectar bancos y rutearlos** (CNV oficial / parser aparte) |
| 7 | Dividendos: HTML guardado pero sin parsear montos → payout casi vacío | **Parsear montos** del form 339 (sin re-bajar, el HTML ya está) |
| 8 | Todo mezclado sin provenance | **Provenance por dato** (fecha presentación, reexpresión, fuente, escala) |

---

## Qué se re-lanza y qué NO

| Etapa | Acción | Por qué |
|---|---|---|
| Jobs 1-4 (discovery) | **NO se toca** | Universo, company pages, whitelists ya cacheados |
| **job5 (EEFF)** | **RE-LANZAR v2** | Es el que tiene el parser roto + no guardó HTML |
| job6 (dividendos) | **RE-PARSEAR, sin re-bajar** | El HTML crudo ya está en `eeff/div_html/` |
| job7 (validación) | Re-correr + agregar cross-período | Cazar escalas rotas |
| s0-s5 (screener) | Re-correr al final | Sobre datos limpios |

**Costo:** aif2 es rápido (~0,3s/página). Re-bajar el subset (72 empresas, ~31k GUIDs)
son **~3 horas**. El full 556 escala igual (el pipeline ya lo soporta con `--rango`).

---

## Las fases

### FASE A — Diagnóstico del template roto (ANTES de re-extraer)
No tocar nada hasta entender qué cambió.
- Bajar 3-5 `publicview` **recientes** (2024+) de empresas afectadas (TXAR, METR) y **viejos**
  de las mismas empresas.
- Comparar el HTML: ¿qué cambió en el layout que hace que el regex agarre el número
  equivocado? (nueva columna, código movido, formato de número distinto, "en miles" vs
  "en unidades", etc.)
- **Salida:** el patrón del template nuevo + el fix concreto del parser. Sin esto, re-extraer
  es re-generar la misma basura.

### FASE B — Re-extracción robusta de EEFF (`job5_v2`)
Por cada GUID de `whitelist_eeff` (subset primero, luego full):
- Fetch `publicview` → **GUARDAR el HTML crudo** en `eeff/eeff_html/{guid}.html`.
- **Parser v2**: arreglado para template nuevo + viejo; extrae el valor del período **y la
  columna comparativa** (año anterior).
- Guardar por dato: **cik canónico + ticker + cuit**, concepto, period_end,
  **fecha_presentacion**, **fecha_reexpresion**, valor, valor_comparativo, escala, guid.
- **NO deduplicar a un valor arbitrario**: la PK incluye `fecha_reexpresion` → se conservan
  todas las vintages (después se elige la consistente).
- Resume-safe, `--rango`, `--max`. Idempotente.

### FASE C — Validación de integridad
1. **Identidad contable** por filing (job7): Activo = Pasivo + PN.
2. **Cross-período** (lo nuevo): por empresa, marcar períodos cuyo Assets/Equity esté fuera
   del orden de magnitud de la historia propia (escala rota). Marcar, no borrar.
3. **Selección de vintage**: por período, quedarse con el valor de la **reexpresión más
   reciente** → serie histórica consistente para el CAGR (sin `vintage_mixto`).

### FASE D — Dividendos (re-parsear, SIN re-bajar)
- El HTML del form 339 ya está guardado (job6). Parser de **montos** → `cnv_dividendos` con
  monto real → **payout desde CNV** (no depender de yfinance).

### FASE E — Re-correr el screener ETL (s0-s5)
- Con claves canónicas, s0 (normalización) se simplifica o desaparece.
- s2-s5 igual, pero ahora sobre datos limpios → **último período confiable (sin staleness),
  CAGR con vintage consistente, payout real.**

---

## Gate final (definición de "datos perfectos")
- **0 períodos con escala rota** en el último período de cada empresa.
- **Staleness → 0** (o solo empresas que genuinamente no presentaron estados recientes).
- **CAGR sin flag `vintage_mixto`** (vintage controlado).
- **Payout desde CNV** > 15/72.
- Identidad contable cierra en el subset (salvo bancos, ruteados).
- Cada fila con provenance completo (fecha presentación, reexpresión, fuente, escala).

## Escalar a las 556
Mismo pipeline. Solo cambia el input: `job5_v2` **sin `--cuits`** (todo el universo). Las
fases C-E no cambian.

## La lección estructural
**Desacoplar bajar de parsear.** Guardando el HTML crudo, cualquier mejora futura del parser
es re-parsear local (segundos), sin volver a tocar la CNV nunca más. Es como debió estar
desde el v1.
