# CICLO DE PRODUCTO — estado final

**Fecha:** 2026-08-31 · **Rol:** Product Integration Lead / Financial Data Engineer
**Sin commits. Sin homologación final. Base homologada, sin cambios de schema.**

> **Superado por el ciclo del 2026-09-01.** Este documento queda como
> registro histórico del estado en que terminó ese día (1 de 8 empresas con
> cadena completa). Al día siguiente se ingirieron los filings de las 7
> empresas restantes y se corrigió F-056 (fallback multi-taxonomía no
> cableado en dos scripts de cálculo): el estado actual es **7 de 8**
> cadenas completas. Ver `RATIO_COVERAGE_MATRIX.md`, `RATIO_CONTRACT.md`,
> `RATIO_VALIDATION_REPORT.md` y `PRODUCT_DEMO_GATE.md` para el estado
> vigente.

---

# Veredicto: **el motor financiero funciona; el producto tiene una fila**

El flujo `EMPRESA → IDENTITY → SEC/XBRL → MARKET → MÉTRICAS → RATIOS → SCREENER →
PROVENANCE` está **demostrado de punta a punta** — pero para **una sola empresa
de ocho**. No es una falla del cálculo: es cobertura de ingesta.

---

## 1. Fases

| fase | resultado |
|---|---|
| **A · CNV** | **blocker encontrado y corregido** — F-053. Banco 15/15, gate C3 10/10 en YPF y TGS |
| **B · Inventario** | 14 ratios definidos con tags, unidades, fallback y condiciones de NO_CALCULABLE |
| **C · Multi-camino** | sólo el EPS tiene 2 caminos genuinamente independientes; el P/E tiene 1.5 |
| **D · Matriz** | `RATIO_COVERAGE_MATRIX.md` — ningún ratio en `IMPLEMENTED` |
| **E · Datos reales** | 126/126 calculados en YPF; 7/8 empresas con corte identificado |
| **F · Contrato** | `SCREENER_CONTRACT_V1.md` — **PROPUESTO**, precondiciones 1 y 2 sin cumplir |
| **G · Auditoría** | **17/17**, sin importar código del implementador |

---

## 2. Lo que quedó demostrado

**126 ratios calculados** (14 × 9 ejercicios), **0 NO_CALCULABLE**, cada uno con
insumos, moneda, período y accession. Los 126 fueron **recalculados por un
auditor independiente** que habla con PostgreSQL por `psql`, usa `Decimal` en vez
de `float` y no importa un solo módulo del implementador: **0 divergentes**.

**El auditor demostró que audita.** Al agregar `quick_ratio` —numerador compuesto
`CurrentAssets − Inventories`— el auditor, que recalculaba sin la resta, marcó
**9 divergencias** antes de que se le enseñara la forma compuesta. Un control que
sólo sabe aprobar no vale; éste rechazó.

**Semántica verificada, no supuesta.** El EPS publicado coincide con
`ProfitLoss / WeightedAverageShares` en **9/9 ejercicios** (dif. máx 0.72 %). Eso
confirma de un tiro la semántica de tres nombres distintos de EPS, la de
`WeightedAverageShares` y la de `ProfitLossAttributableToOwnersOfParent`.

**El tag del EPS cambia de nombre tres veces** entre 2017 y 2025. Un solo tag da
3 ejercicios; la cadena de fallback da **9/9**. Triplica la cobertura sin ingerir
nada nuevo.

---

## 3. Lo que quedó medido, y no gusta

| | |
|---|---|
| emisores con fundamentals | **1 de 513 CIK** = 0.19 % |
| instrumentos ligados a una entidad | **15 de 584** = 2.6 % |
| cadenas E2E completas en la muestra | **1 de 8** |
| CUIT ratificados | 3 de 56 |
| instrumentos con precio | 577 de 584 = **98.8 %** |

**Market está lleno, fundamentals está vacío, y el enlace entre ambos cubre el
2.6 %.** BMA no es una excepción: es lo normal. La muestra deliberada tomó 7 de
los 15 instrumentos que sí tienen enlace.

---

## 4. El blocker de la Fase A

C3 resolvía la identidad con un **CUIT de CEPU hardcodeado** como default, un
seed CSV específico de CEPU, y fallback al schema legacy. Si nada resolvía,
seguía con clave provisional. `identity_v1` no se consultaba.

En la base quedaron **tres formatos de clave distintos** y una fila con CUIT
`99999999999`, que llegó a hacer el request y fue rechazada por la validación de
**contenido** — no por la de identidad, que no existía.

Corregido: `resolver_en_identity_v1()` exige `assertion.status = 'VERIFIED'`,
deriva el CUIT desde el CIK, devuelve el ULID real y no admite clave provisional.
GGAL queda bloqueada **antes del primer request**. Detalle en
[F053_FINDING.md](../../../docs/review/F053_FINDING.md).

**Las 3.517 filas históricas no se reescribieron a propósito**: ocurrieron bajo un
binding provisional y el registro debe decirlo. Deuda explícita.

---

## 5. Dos ratios correctos que no son publicables

| ratio | YPF 2025 | por qué |
|---|---:|---|
| `effective_tax_rate` | 1.8780 | tasa efectiva del 188 % |
| `ocf_to_net_income` | −6.0036 | flujo positivo sobre resultado negativo: el signo invierte la lectura |

Aritméticamente correctos, financieramente inútiles sin banda de sanidad. Quedan
en `REVIEW_REQUIRED` y **fuera del screener**. Es la diferencia entre dato y
métrica publicable.

---

## 6. Estado de la suite

**226 passed · 1 failed · 1 skipped.** El único fallo es
`test_f038_traza_corrida::test_el_hash_de_la_base_es_el_del_artefacto_en_disco`,
que verifica los 577 hashes de Market contra `data/raw/market/`, perdido en el
incidente y cuya redescarga este ciclo prohíbe. **Idéntico a antes de estos
cambios: sin regresión.**

---

## 7. Para poder mostrarlo a un cliente

En orden de impacto:

1. **Ingerir filings de las 7 empresas de la muestra** (S02→S03→S04). Pasa el
   screener de 1 fila a 8. Es el único paso que cambia el orden de magnitud.
2. **Completar `identity_v1.instrument`** para los 569 instrumentos sin enlace.
   Sin esto, un precio no se une a un fundamental aunque los dos existan.
3. Definir bandas de sanidad → habilita los 2 `REVIEW_REQUIRED`.
4. Implementar `price_to_book` — sin ingesta nueva, los facts están 9/9.
5. Ingerir D&A, capex y dividendos → habilita EV/EBITDA, FCF, dividend yield.

Nada de esto es investigación: los cuatro primeros son ejecución con mecanismos
que ya funcionan y están probados.

---

## 8. Lo que NO se hizo, según lo pedido

Sin commit · sin homologación final · sin modificar SEC, Identity ni Market ·
sin backfill masivo · sin descarga masiva de CNV (**4 artefactos en total**) ·
sin cambios de schema · sin reescribir la atribución histórica.

Se modificó **CNV**, que es lo que la Fase A pedía validar, y sólo por el blocker
de F-053.

---

## 9. Artefactos

**Documentos**
`RATIO_COVERAGE_MATRIX.md` · `RATIOS_MULTIPATH.md` · `SCREENER_CONTRACT_V1.md` ·
`../fase_cnv/FASE_A_CNV_IDENTITY.md` · `../../../docs/review/F053_FINDING.md`

**Evidencia**
`ratios_calculados.json` (126) · `multipath.json` · `e2e_producto.json` ·
`auditoria_independiente.json` (17/17) · `../fase_cnv/cnv_identity_bench.json` (15/15)

**Scripts** — solo-lectura salvo el fetcher
`ratios_inventario.py` · `ratios_multipath.py` · `e2e_producto.py` ·
`ratios_auditoria.py` · `cnv_identity_bench.py` · `c3_cnv_fetch.py` (modificado)
