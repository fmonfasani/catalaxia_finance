# RETOMAR ACÁ — punto de entrada para continuar el proyecto

> **Si sos un agente/dev retomando esto en otra máquina o IDE: leé este archivo primero.**
> Te pone al día con el estado, la decisión clave, el bloqueante y el próximo paso.
> El detalle está en los otros docs de esta carpeta (ver punteros al final).

Última actualización: 2026-07.

---

## 0. Cómo levantar el proyecto en otra compu

1. `git clone https://github.com/fmonfasani/catalaxia_finance.git`
2. La base **`data/screener.db` (728MB) NO está en git** (supera el límite de GitHub).
   Opciones: (a) copiarla aparte (USB/drive) y ponerla en `data/`, o (b) reconstruirla
   corriendo los pipelines (EDGAR → yfinance → jobs CNV, ver docs por etapa).
3. Leé, en este orden: este archivo → [00_VISION_GENERAL.md](00_VISION_GENERAL.md) → la
   etapa que vayas a tocar.
4. La memoria local del agente (`.claude/`) **no viaja**: todo el contexto necesario está
   en estos documentos, a propósito.

---

## 1. Qué es el proyecto (1 párrafo)

Screener de **13 ratios financieros** comparables para 3 universos: **US (S&P 500)** y
**ADR** (vía SEC EDGAR) y **argentinas BYMA-only** (vía yfinance y CNV). Precios de
yfinance. Todo en `data/screener.db`. Los 13 ratios y su origen están en
[00_VISION_GENERAL.md](00_VISION_GENERAL.md) §1.

---

## 2. Estado actual (honesto)

| Universo | Fundamentales (ratios 7-13) | Precios (ratios 1-6) |
|---|---|---|
| US (S&P 500) | ✅ EDGAR → tabla `ratios` | ✅ yfinance → tabla `precios` |
| ADR | ✅ EDGAR → `ratios` | ✅ yfinance |
| BYMA-only | ✅ yfinance → `ratios` | ✅ yfinance |

**De los 13 ratios: 9 ya calculados, 4 son aritmética trivial** sobre datos existentes
(×fx, dif máx/mín 52s, fcf/ce). **Cero cálculos de fondo faltantes.**

**Estamos a ~80% de un primer screener funcional (EDGAR + yfinance).**

### La capa CNV (el trabajo grande) — estado
Pipeline completo, subset extraído 100% (31.626 EEFF + 3.225 dividendos, 124 empresas,
~15 años c/u). **Pero NO está integrada al screener todavía** por un bloqueante (§4).

---

## 3. Decisión clave: yfinance vs CNV (para no repetir la duda)

yfinance **ya cubre** los fundamentales recientes de las BYMA-only → el screener de 13
ratios **no depende de CNV** para existir. CNV es un **upgrade**, no un requisito, y aporta
lo que yfinance NO tiene:
- **Historial ~15 años** (yfinance da ~4) → habilita el ratio #9 (CAGR EPS 5y), que con
  yfinance sale NULL para casi todas las BYMA-only.
- **Números oficiales validados** (NIC 29, RECPAM, identidad contable).
- **Dividendos oficiales** (form 339) para el payout real.
- **~500 empresas que no cotizan** (no están en yfinance) — la expansión futura.

**Camino recomendado:** sacar el screener YA con EDGAR + yfinance; integrar CNV después
como capa de calidad/validación + historial + expansión.

---

## 4. Bloqueante antes de integrar CNV: normalización de clave

`job5` guardó las filas nuevas de `cnv_estados` con `cik`=CUIT y `ticker`=nombre-de-empresa,
distinto del resto de la base (`cik`=`BYMA-{ticker}` o CIK de SEC). No joinean y pueden
duplicar a las 56. Detalle y plan en
[ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md#deuda-técnica-clave).

Diagnóstico pendiente (3 queries) para dimensionarlo:
```sql
SELECT SUM(cik LIKE 'BYMA-%') viejas, SUM(cik GLOB '[0-9]*') nuevas, COUNT(*) tot
FROM cnv_estados WHERE fuente='cnv-aif2';
SELECT COUNT(DISTINCT cik) FROM cnv_estados WHERE fuente='cnv-aif2' AND cik LIKE 'BYMA-%';
SELECT COUNT(DISTINCT cik) FROM cnv_estados WHERE fuente='cnv-aif2' AND cik GLOB '[0-9]*';
PRAGMA table_info(empresas);
```

---

## 5. Próximo paso concreto (elegí uno)

**Opción A (rápida — screener ya):** `armar_screener.py` — selecciona los 9 ratios
directos + deriva los 4 → tabla/CSV `screener` con los 13 × ticker × universo + reporte
de cobertura real (cuántos tickers tienen cada ratio no-nulo). Entregable hoy con
EDGAR + yfinance.

**Opción B (calidad — integrar CNV):** correr el diagnóstico (§4) → `normalizar_cnv_estados.py`
→ revisar/rehacer `calcular_ratios_cnv.py` (ya existe uno en `cnv/scripts/`, verificar que
no opere sobre claves cruzadas) → mergear al screener.

Recomendación: **A primero** (tenés el producto), **B después** (lo mejorás).

---

## 6. Mapa de documentos

- [00_VISION_GENERAL.md](00_VISION_GENERAL.md) — arquitectura, tablas, los 13 ratios, qué sube a git.
- [ETAPA_1_EDGAR.md](ETAPA_1_EDGAR.md) · [ETAPA_2_ADR.md](ETAPA_2_ADR.md) · [ETAPA_3_BYMA_ONLY.md](ETAPA_3_BYMA_ONLY.md) · [ETAPA_4_CNV_PIPELINE.md](ETAPA_4_CNV_PIPELINE.md) — qué/por qué/qué falta por fuente.
- [jobs/README.md](../../scripts/tickets/cnv/jobs/README.md) — manual de los jobs CNV.
- Motor de ratios: `scripts/tickets/sec_edgar/scripts/calcular_ratios_base.py`
- Precios/valuación: `scripts/tickets/sec_edgar/scripts/precios_y_valuacion.py`
- Set de 13 ratios (referencia): `scripts/tickets/cnv/scripts/comparar_13_ratios.py`
