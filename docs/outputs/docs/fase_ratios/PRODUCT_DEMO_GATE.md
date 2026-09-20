# PRODUCT_DEMO_GATE — Fase J

**Fecha:** 2026-09-01 · **Rol:** Financial Data Architect + Product Validation Auditor
**Ámbito auditado:** capa de ratios sobre la muestra deliberada (YPFD, CEPU,
TGSU2, GGAL, BMA, AAPL, MSFT, NVDA). Sin commits. Sin backfill masivo. No se
modificó SEC/CNV/Market (solo se leyó).

> **ACTUALIZACIÓN registrada, 2026-09-01 (mismo día, ciclo de auditoría de
> producto posterior).** El veredicto de abajo **se mantiene sin cambio**
> (`PASS_WITH_WARNINGS`), pero su base de evidencia se amplió con un
> segundo ciclo de trabajo — matriz de 13 ratios × 8 empresas
> (`RATIO_PRODUCT_MATRIX.csv`), auditoría independiente enfocada en esa
> matriz (`RATIO_INDEPENDENT_AUDIT.json`, 60/60 OK), y un banco adversario
> ampliado a 13 ataques (`RATIO_ADVERSARIAL.json`). Dos hallazgos nuevos:
> **F-061 (HIGH)** — la capa de ratios no verifica el origen de sus
> insumos (un fact de otra empresa insertado con el CIK/tag correctos se
> usa sin alarma); y **F-062 (MEDIUM)** — la clasificación previa de
> EV/EBITDA como `NOT_CALCULABLE` por "falta de D&A" era incorrecta, el
> dato existe. Detalle completo, con el refinamiento de que **BMA sí tiene
> fundamentales calculables** (14 valores, solo su P/E está bloqueado por
> el enlace de instrumento), en `RATIO_PRODUCT_AUDIT.md` y
> `PRODUCT_DEMO_READINESS.md`. El resto de este documento es el original
> del ciclo anterior, sin editar.

---

## Veredicto

```
RATIOS_PRODUCT_GATE = PASS_WITH_WARNINGS
```

El motor de cálculo está probado, es reproducible por dos auditores
independientes y sobrevivió un banco adversario dirigido a sus reglas de
NULL, signo, moneda y período. **No está en `PASS`** porque el producto,
para mostrarse a un cliente, todavía tiene una fila bloqueada dentro de la
propia muestra deliberada (BMA) por una causa de identidad, no de cálculo, y
porque dos de los trece ratios pedidos (P/B, P/S) no están implementados
pese a tener los datos disponibles. **No está en `BLOCKED`** porque nada de
lo auditado indica un cálculo incorrecto, un valor inventado, o una
violación de las reglas de NULL/signo/moneda/período — todo lo contrario:
el banco adversario encontró que las reglas existentes se sostienen, y
donde no había protección (ATK2), la corrupción quedó **calculada** pero
**detectable** por un control independiente, nunca **silenciosa e
indetectable**.

---

## 1. Dimensiones

### DATA_COVERAGE — ⚠️ ADVERTENCIA

| medida | valor |
|---|---:|
| CIK conocidos con fundamentals | 8 / 513 (1.56%) |
| Instrumentos con precio | 577 / 584 (98.8%) |
| Instrumento enlazado a entidad | 15 / 584 (2.6%) |
| Cadenas E2E completas en la muestra deliberada | 7 / 8 (87.5%) |
| CUIT ratificados (VERIFIED) | 3 / 56 (5.4%) |

La muestra deliberada del encargo (8 empresas) está **ingerida en 8/8** y
**enlazada en 7/8**. Fuera de esa muestra, la cobertura es la de un piloto,
no la de un producto: es una decisión de alcance explícita del encargo
("no hacer backfill masivo"), documentada, no un descubrimiento sorpresivo.

### FORMULA_CORRECTNESS — ✅ VERDE

| control | resultado |
|---|---|
| Recalculado por un auditor sin código compartido (`ratios_auditoria.py`) | 274/274, 0 divergentes |
| EPS publicado == resultado/acciones (verificación semántica, no léxica) | 8/8 empresas, dif. máx. 0.12% |
| Activo = Pasivo + Patrimonio (identidad, no comparación de tags) | 8/8 empresas, desvío 0.0000% |
| Ingresos − Costo de ventas = Resultado bruto | 6/6 empresas con los 3 conceptos, 0.00% |
| P/E: los dos caminos concuerdan | 2/2 ejercicios comparables, ≤0.36% (con la salvedad de independencia parcial, ver `RATIOS_MULTIPATH.md`) |
| Banco adversario — moneda, signo, NULL-como-cero, basic/diluted, período, duración | ver §2 |

### MULTI_TAXONOMY — ✅ VERDE (tras corregir F-056)

Antes de este ciclo, dos de los cuatro scripts que producen la evidencia de
cobertura (`ratios_inventario.py`, `e2e_producto.py`) declaraban sus propias
listas de tags **solo-IFRS**, ignorando el fallback multi-taxonomía ya
definido en `ratio_defs.py`. Efecto: 0/9 ratios calculados en las 3 empresas
`us-gaap` de la muestra pese a tener los facts completos. Corregido
(**F-056**); verificado con las 8 empresas tras el fix: `ifrs-full` y
`us-gaap` producen los mismos ratios con la misma lógica, y la identidad
contable (Activo=Pasivo+Patrimonio) cierra en 0.0000% en ambas taxonomías.

### PROVENANCE — ✅ VERDE

| control | resultado |
|---|---|
| Toda accession citada existe en `derived.fact` | 22 accessions, 0 inexistentes |
| Todo fact derivado tiene accession y `source_fact_ids` | 0 huérfanos |
| Cadena `derived.fact -> parsed.facts -> archivo -> SHA256` | 6/6 hechos de muestra (3 empresas, con y sin dimensiones), SHA256 coincide en 6/6 |
| Numerador y denominador del mismo filing | 0 cruces en 274 ratios |

### MULTI_COMPANY — ⚠️ ADVERTENCIA

7 de 8 empresas de la muestra deliberada con cadena completa, en **dos
taxonomías contables** y **dos monedas de reporte** (ARS/USD según el
emisor y el ejercicio). El octavo caso (BMA) tiene sus fundamentals
correctamente ingeridos — el corte es de enlace de identidad
(`identity_v1.instrument`), un problema ya conocido y del mismo tipo que
bloquea al 97.4% del universo de instrumentos, no un caso nuevo.

### PRODUCT_READINESS — ⚠️ ADVERTENCIA

No listo para publicar sin editorializar las siguientes ausencias:

1. `price_to_book` y `price_to_sales` — de los 13 ratios pedidos, son los
   únicos 2 sin implementar, y los datos ya están disponibles.
2. `effective_tax_rate` y `ocf_to_net_income` — calculados y correctos,
   pero sin banda de sanidad definida; hoy quedan fuera del screener por
   diseño (`REVIEW_REQUIRED`), no por defecto.
3. `EV/EBITDA` — `NOT_CALCULABLE` en las 8 empresas: falta D&A, no es un
   problema de fórmula.
4. BMA no puede publicarse hasta que se enlace su instrumento.

Ninguna de las cuatro requiere rediseñar el motor: son ejecución
(`RATIO_COVERAGE_MATRIX.md` §7), no investigación.

---

## 2. El banco adversario — qué se atacó y qué pasó

`scripts/engine/adversario_ratios.py`, sobre una copia descartable de la
base (nunca la homologada). Cada ataque predice su veredicto antes de
correr, como exige el encargo ("atacar" no es "confirmar que todo está
bien").

| ataque | predicción | resultado |
|---|---|---|
| **A1** moneda incorrecta en el denominador | `current_ratio` → NO_CALCULABLE, motivo monedas distintas | **confirmado** — 0.870214 (CALCULADO) → NO_CALCULABLE, "monedas distintas: CurrentAssets=USD vs CurrentLiabilities=ARS" |
| **A2a** signo de `Equity` invertido | el ratio SE CALCULA igual, con un valor distinto y sin señal de error — el motor de ratios no puede detectar un insumo corrupto por sí solo | **confirmado** — ROE 0.027388 → **CALCULADO** −0.027388, sin ninguna alarma |
| **A2b** el mismo ataque, visto por la identidad contable | Activo=Pasivo+Patrimonio SÍ detecta la corrupción (el desvío deja de ser 0%) | **confirmado** — desvío 0 → 15,519,248,728,000 (magnitud ≈ 2×Equity, exactamente lo esperado de invertir el signo) |
| **A3** `Equity=0` explícito (no ausente) | NO_CALCULABLE "denominador = 0", nunca un ROE infinito | **confirmado** — "denominador StockholdersEquity = 0" |
| **A4** se inserta un resultado "diluted" con otro valor, compitiendo con el básico | el básico sigue ganando porque está antes en la cadena de fallback declarada | **confirmado** — ROA sin cambios (−0.028058) pese al duplicado |
| **A5** un "comparativo" con `report_period` que no coincide con su `instant_date` | el filtro de período lo excluye automáticamente; el ratio no cambia | **confirmado** — current_ratio sin cambios (0.870214) pese a la fila con valor ×999 |
| **A6** duración trimestral coladndose como anual (la trampa de suite-validacion-edgar) | 0 casos en las 8 empresas para los tags de ingresos/resultado | **confirmado** — 0 filas sospechosas |

**8/8 ataques con el veredicto predicho, 0 críticos en rojo.** La base
homologada se verificó bit a bit idéntica antes y después del banco completo
(control Z, hash `88789|bae5c8cb...`). Evidencia completa:
`outputs/docs/fase_ratios/adversario_ratios.json`.

El propio banco adversario encontró dos defectos en sí mismo durante su
desarrollo — un producto cartesiano sin filtrar (**F-058**, 38 MB de salida
y un crash antes de terminar A2) y una restricción de formato de
`fact_key` (64 hex, `CHECK fact_fact_key_check`) que su primer intento de
mutación no respetaba. Ambos corregidos antes de la corrida final. Se
documentan porque la auditoría adversaria auditándose a sí misma, y
encontrando algo, es exactamente la señal de que está mirando con cuidado.

**Lectura del conjunto:** el motor de ratios en sí mismo **no** tiene
defensa contra un dato de entrada corrupto en valor (A2a lo confirma
deliberadamente) — su contrato es "calcular fielmente lo que hay en
`derived.fact`", no "auditar lo que hay en `derived.fact`". Esa auditoría
existe, pero es una **capa separada**: las identidades contables
(`audit_provenance_ratios.py`) y los controles de reproducibilidad
(`ratios_auditoria.py`). El hallazgo útil de A2 no es "el sistema está roto"
— es "la defensa contra datos corruptos vive en la capa de auditoría, no en
la capa de cálculo, y hay que seguir corriendo la primera para confiar en la
segunda". Es una separación de responsabilidades razonable, pero **implícita
hasta este documento**: nada obligaba a correr `audit_provenance_ratios.py`
antes de publicar un ratio.

---

## 3. Hallazgos de este ciclo (nuevos, no heredados)

| id | qué | severidad | estado |
|---|---|---|---|
| F-056 | `ratios_inventario.py`/`e2e_producto.py` ignoraban el fallback multi-taxonomía declarado en `ratio_defs.py` | alta (cobertura) | corregido |
| F-057 | el parser `sql()` de los dos auditores independientes perdía el último campo NULL de la última fila (bug de `str.strip()` sobre `\x1f`) | media (robustez del auditor) | corregido |
| F-058 | el banco adversario nuevo (`adversario_ratios.py`) tenía un producto cartesiano sin filtrar por `is_dimensional` en su propia consulta de identidad contable — crasheaba con 38 MB de salida al tocar GGAL | media (robustez de la herramienta) | corregido |

Detalle en `docs/review/F056_FINDING.md` y `F057_FINDING.md`.

---

## 4. Qué movería el veredicto a PASS

En orden de impacto, sin requerir rediseño:

1. Enlazar `identity_v1.instrument` para BMA → 8/8 cadenas completas en la
   muestra deliberada.
2. Implementar `price_to_book` (facts ya disponibles) y declarar+implementar
   `price_to_sales`.
3. Definir bandas de sanidad para `effective_tax_rate` y `ocf_to_net_income`.
4. Formalizar que `audit_provenance_ratios.py` (o un control equivalente de
   identidad contable) es **precondición de publicación**, no un chequeo
   opcional — es la única defensa demostrada contra un insumo con signo o
   tag corrupto (§2, ataque A2).

Ninguno de los cuatro requiere backfill masivo ni tocar SEC/CNV/Market más
allá de lo ya ingerido para esta muestra.

---

## 5. Lo que NO se hizo en este ciclo, según las restricciones del encargo

Sin commits · sin homologación final · sin modificar SEC/CNV/Market (solo
lectura, salvo las correcciones de código de cálculo/auditoría descritas en
F-056/F-057, que no tocan datos) · sin backfill masivo · sin implementar
ratios nuevos antes de fijar el contrato (`RATIO_CONTRACT.md` se escribió
primero, y P/B y P/S quedan explícitamente `NOT_IMPLEMENTED` en vez de
implementados sobre la marcha).
