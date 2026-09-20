# Metodología de Transformación y Certificación de Datos Financieros
### (la "T" del ETL — de datos crudos a datos con confiabilidad demostrable)

> **Qué es esto.** No es un screener. Es el **proceso que convierte estados contables crudos
> —de cualquier fuente— en fundamentals CERTIFICADOS, con un puntaje de calidad auditable por
> empresa y por dato.** El screener es un cliente de este proceso; el proceso se vende solo.
>
> **Regla de oro que lo hace confiable:** *marcar antes que fabricar.* Nunca se inventa un número.
> Si no se puede verificar, se dice. Esto es lo que lo diferencia de todo proveedor de datos que
> presenta todo como cierto.
>
> Todo lo que sigue está **probado con datos reales** de este proyecto (56 empresas argentinas +
> 13 ADR). No hay afirmación sin evidencia verificable en la base.

---

## 1. El problema que resuelve (por qué existe)

Los datos financieros crudos están **silenciosamente corruptos**, y ninguna fuente es la verdad
absoluta. Lo comprobamos, no lo suponemos:

| Tipo de corrupción | Evidencia real que encontramos |
|---|---|
| **Escala/unidad** | GCLA: un trimestre con etiqueta "Millones de $" pero valor en pesos base → inflado ×1.000.000 (quedó 5 mil billones). |
| **Consolidación** | GCLA individual (holding sola) = ~5.000M vs consolidado (grupo) = ~119.000M. 16× de diferencia. |
| **Identidad** | La misma empresa bajo dos tickers/razones sociales → "9 ADRs perdidos" que en realidad estaban. |
| **Documento mezclado** | CVH: activo de un doc, patrimonio de otro → el balance no cerraba (31% de brecha). |
| **Minoritario** | Holdings: el PN atribuible a la controladora ≠ PN total (incluye no-controlantes). |
| **Fuente externa errada** | Investing daba ROE de LOMA en 3,4% cuando el balance auditado y la SEC decían ~19%. |

**Conclusión fundamental (comprobada):** no alcanza con una fuente ni con un chequeo. La confianza
viene de que **múltiples restricciones independientes coincidan sobre el mismo número.**

---

## 2. Arquitectura: las tres capas (medallion)

```
  BRONZE (crudo, inmutable)  →  SILVER (normalizado + validado)  →  GOLD (derivado + certificado)
  estados tal cual              identidad, unidad, período,          ratios + puntaje de calidad
  (sin tocar)                   consolidado, RECPAM                  auditable por dato
```

La "T" del ETL vive en **SILVER** (normalización + validación) y produce **GOLD** (certificación).
Esta metodología documenta esas dos capas.

---

## 3. El proceso paso a paso — con el fundamento de cada uno

Cada paso es un script reproducible e idempotente. Todo se reconstruye con un comando
(`run_pipeline.py`, ~70 segundos para 56 empresas).

### Paso 1 — Resolución de identidad canónica  · `f1_identidad`, `fix_mapeo`
**Qué hace:** una entidad legal = un ticker canónico (por CUIT/CIK). Une razón social, tickers y
variantes.
**Fundamento (data engineering — *entity resolution*):** si la clave de una empresa no es única y
estable, todo join aguas abajo se rompe. **Evidencia:** el bug de "9 ADRs perdidos" era esto — los
ADR estaban bajo razón social ("Pampa Energía S A") y los locales bajo ticker.

### Paso 2 — Re-extracción de estados consolidados  · `f2_reextract_batch`, `cnv_codes`
**Qué hace:** parsea el XBRL crudo, mapea códigos de taxonomía → conceptos canónicos, **elige
CONSOLIDADO sobre individual**, valida la etiqueta de unidad, maneja dos formatos de número.
**Fundamento (contable):** el estado **consolidado** refleja el grupo económico; el **individual**
solo la sociedad tenedora. Un analista siempre usa el consolidado. **Evidencia:** GCLA individual
(~5.000M) vs consolidado (~119.000M).
**Fundamento (data):** un solo `regex` captura todos los pares (código, monto) → determinista y
auditable, no scraping frágil.

### Paso 3 — Consistencia de documento único  · `fix_single_doc`
**Qué hace:** todos los conceptos de un período salen del **mismo documento** (no se mezclan docs).
**Fundamento (contable — *cuadratura*):** dentro de un mismo estado, todas las líneas comparten
unidad y alcance, así que **Activo = Pasivo + PN cierra por construcción**. Al mezclar documentos,
se mezclan escalas/alcances. **Evidencia:** CVH pasó de 31% de brecha a **0%** con esta sola regla.

### Paso 4 — De-acumulación (YTD → trimestre standalone)  · `f3b_from_reextract`
**Qué hace:** los estados CNV son **acumulados** (YTD). Se des-acumulan a trimestres standalone
usando el calendario fiscal de cada empresa: `standalone(Q) = YTD(Q) − YTD(Q−1)`, con el Q1 fiscal
como base.
**Fundamento (contable):** comparar peras con peras. Un trimestre standalone vs uno acumulado da
cualquier cosa. **Fundamento (fiscal):** el Q1 se identifica por el mes de cierre de ejercicio
(no todas cierran en diciembre — RIGO cierra en agosto, LEDE distinto, A3 cambió de ejercicio).

### Paso 5 — RECPAM en doble variante  · `f3b_from_reextract`
**Qué hace:** cada concepto afectado por RECPAM (resultado por posición monetaria) se guarda **con
y sin** el efecto (`incluye_recpam` true/false).
**Fundamento (contable — NIC-29 / IAS-29):** en economías de alta inflación, los estados se ajustan
por inflación y el RECPAM entra en el resultado. Distorsiona comparaciones. Guardar ambas variantes
deja al usuario elegir el lente. **Evidencia:** era el corazón del problema del PER argentino.

### Paso 6 — Corrección de escala anclada en EPS  · `fix_escala_anchor`
**Qué hace:** detecta y corrige errores de escala (×1.000) **solo cuando es seguro**.
**Fundamento (financiero + estadístico — el hallazgo más fino):** el **EPS viene por-acción, sin
escala de unidad**. Entonces `acciones = NetIncome / EPS` debe ser **constante** en el tiempo. Si
las acciones son constantes salvo en unos períodos → esos tienen error de escala per-documento →
se corrigen. Si las acciones saltan (corrupción no-uniforme) → **NO se toca** (se marca).
**Evidencia:** INVJ tenía acciones constantes en 708.000 → corregido y certificado. GCDI saltaba de
892M a 172B → no-uniforme → **no se fabricó**, quedó marcado.

### Paso 7 — Correcciones verificadas (minoritario, precios, recuperación)  · `fix_manual`
**Qué hace:** correcciones puntuales **verificadas independientemente**, no inventadas.
**Fundamento (contable — participación no controladora):** en un holding, PN total = PN de la
controladora + interés no controlante (código 2211300). **Evidencia:** en CVH la brecha del balance
(3,4 billones) era **exactamente** el minoritario 2211300 — verificado antes de aplicar.

### Paso 8 — Derivación de ratios  · `f4_ratios`, `fix_escala_mcap`
**Qué hace:** PER, ROE, márgenes, deuda/EBITDA, con flags de confianza.
**Fundamento (financiero):** `PER = precio / EPS` (auto-consistente, sin depender de un market cap
posiblemente errado); `market cap = precio × (NI/EPS)` como ancla independiente; ROE = NI/PN.
**Evidencia:** el PER vía market cap del screener daba absurdos (AGRO 0,7); vía precio/EPS y market
cap derivado, quedó sano (AGRO ~14).

---

## 4. El marco de validación — el activo central (la IP)

Esto es lo vendible. **Toda transformación produce un dato; solo la validación produce confianza.**

### 4.1 — Los 7 tipos de error que puede tener un dato
Identidad · Escala/unidad · Signo · Período/timing · Extracción · Vintage (reexpresión) · Completitud.

### 4.2 — Los cruces, en 4 capas (cada uno ataca tipos de error específicos)

**Capa 1 — Identidades contables (leyes que SIEMPRE se cumplen):**
- `Activo = Pasivo + Patrimonio Neto`
- `Ganancia Bruta = Ventas − Costo`
- `Resultado Neto = Result. antes de Impuestos − Impuesto`
- `Δ Caja = Flujo Operativo + Inversión + Financiación`
> **Fundamento:** son invariantes de la contabilidad de partida doble (US-GAAP / IFRS). Si no
> cierran, el dato está mal. **Esto es, literalmente, auditoría automatizada.**

**Capa 2 — Continuidad temporal:**
- YTD monótono creciente dentro del ejercicio; roll-forward de patrimonio (PN(t) = PN(t−1) + Resultado − Dividendos).
> **Fundamento:** el negocio es continuo; saltos imposibles delatan errores de período o escala.

**Capa 3 — Fuentes externas independientes:**
- **SEC EDGAR** (20-F) vs **CNV** (AIF) vs **ratio auto-reportado por la empresa** (código 8000009).
> **Fundamento:** dos fuentes independientes que coinciden es la validación más fuerte posible.
> **Evidencia:** CRES, IRSA, TECO2 → SEC y CNV dan ROE **idéntico al decimal**. Y descubrimos que
> investing NO es la verdad (LOMA: balance auditado 19% vs investing 3,4%).

**Capa 4 — Anclas de mercado (cierran el punto ciego de escala):**
- `P/B = MarketCap / PN` y `P/S = MarketCap / Ventas` en rangos sanos.
> **Fundamento (el punto ciego crítico):** las identidades contables y los ratios son **invariantes
> a un error de escala UNIFORME** (si todo está ×1.000, el balance igual cierra). El único control
> que lo agarra es un ancla **independiente de los estados** — el precio de mercado. **Evidencia:**
> GCDI/INVJ saltaron por P/B absurdo; ahí estaba el error de escala.

### 4.3 — Regla de certificación
Un dato queda **CERTIFICADO** cuando pasa: **todas las identidades duras (Capa 1) + continuidad
(Capa 2, si aplica) + al menos un ancla independiente (Capa 3 o 4).** Con eso, cada uno de los 7
tipos de error queda cubierto — incluida la escala uniforme.

### 4.4 — Niveles de confianza (lo honesto)
`CERTIFICADO` (multi-cruce) → `alto` → `interno-ok` (identidades sí, ancla no) → `REVISAR`.
**Cada dato lleva su nivel y qué cruce falló.** No es "confío / no confío": es un semáforo auditable.

---

## 5. La evidencia (resultados reales, comprobables)

- **52 de 56** empresas argentinas **CERTIFICADAS** de forma multi-fuente y auditable.
- **0** en "no sé qué le pasa" (REVISAR). Las 4 que no certifican tienen **causa exacta y honesta**
  (A3: cambió de ejercicio; GCDI/REGE: escala no-uniforme → no se fabrica; POLL: PN negativo real).
- **3 coincidencias exactas al decimal SEC↔CNV** (CRES, IRSA, TECO2) — dos fuentes independientes.
- **Reproducible:** un comando reconstruye todo en ~70 segundos, determinista.

---

## 6. Cómo se vende (el enfoque comercial)

### 6.1 — Qué es, en una frase
> "No te damos datos financieros. Te damos datos que podés **probar** que son correctos —
> con el recibo de cada uno."

### 6.2 — El nombre / posicionamiento
**Motor de Validación y Certificación de Fundamentals (multi-fuente).** El entregable no es una
tabla de números: es una tabla de números **con un puntaje de calidad y trazabilidad por dato.**

### 6.3 — Quién lo compra y por qué
| Cliente | Dolor que le resolvés |
|---|---|
| **Fondos / asset managers** | No tomar decisiones sobre fundamentals corruptos (un ROE mal cargado mueve un ranking). |
| **Fintechs / screeners / roboadvisors** | Data confiable sin armar un equipo de data-quality. |
| **Auditoras / rating agencies** | Auditoría automatizada por invariantes contables — a escala. |
| **Áreas de riesgo / compliance** | Saber qué dato es confiable y cuál no, con trazabilidad para el regulador. |
| **Proveedores de datos** | Un sello de calidad sobre su propio feed. |

### 6.4 — Los diferenciadores (lo que nadie más ofrece)
1. **Triangulación multi-fuente** (SEC + CNV + mercado + auto-reporte), no una sola fuente.
2. **Validación por identidades contables** — los números tienen que obedecer las leyes de la
   contabilidad. Es auditoría, no scraping.
3. **Detección del punto ciego de escala** (ancla de mercado) — el error silencioso que corrompe
   todo y que nadie chequea.
4. **Puntaje de certificación auditable por dato**, con la causa de cada falla.
5. **Determinista y reproducible** — un comando, mismo resultado siempre.
6. **Honestidad como feature**: marca la incertidumbre en vez de esconderla. **Esto es también
   protección legal** — no fabricás un dato del que después te hacen responsable.

### 6.5 — Cómo se explica el fundamento a un cliente no técnico
- "Verificamos que los números **cierren como tienen que cerrar** por contabilidad (Activo = Pasivo
  + Patrimonio, siempre)."
- "Cruzamos **lo que dice la empresa a EE.UU., lo que dice a Argentina, y lo que vale en el
  mercado** — si coinciden, es sólido; si no, te decimos cuál miente."
- "Cuando no podemos estar seguros, **te lo marcamos** — nunca te damos un número inventado."

---

## 7. Perspectivas que quizás no estás viendo (el "pensá vos")

1. **Es auditoría automatizada, no solo data-cleaning.** Las identidades contables son las mismas
   que revisa un auditor. Vendido a auditoras/reguladores, el ángulo es *assurance a escala*.
2. **Es agnóstico de fuente y de mercado.** El marco (identidades + triangulación + ancla) sirve
   para cualquier fuente XBRL/estados contables (SEC, CNV, ESMA europea, B3 Brasil…). Lo probamos
   con las dos peores (CNV con inflación + SEC), que son el caso difícil.
3. **El punto ciego de escala es un secreto de la industria.** Casi nadie chequea escala uniforme
   porque las identidades la dejan pasar. Que vos lo cubras con el ancla de mercado es un
   diferencial técnico real y demostrable.
4. **La certificación es un activo tipo "rating".** Igual que una nota crediticia, un *data quality
   score* con metodología pública y auditable es un producto en sí — licenciable.
5. **La reproducibilidad es un argumento regulatorio.** Poder reconstruir cualquier dato desde el
   crudo, determinísticamente, es lo que pide un regulador o un due diligence. La mayoría de los
   proveedores no puede.
6. **El costo de un dato malo es asimétrico.** Un ROE de 26.000% (que teníamos) en un ranking
   automático manda plata al lugar equivocado. Vender "evitamos ese error" es vender gestión de
   riesgo, no data.
7. **La inflación argentina es tu ventaja competitiva.** Resolver RECPAM, reexpresión y vintage te
   hace competente en el mercado más difícil del mundo para esto. Si funciona acá, funciona en
   cualquier lado.

---

## 8. Cómo documentarlo para vender (estructura sugerida del material)

1. **One-pager comercial** — secciones 1, 6.1–6.4 (el dolor, el qué, quién compra, diferenciadores).
2. **Deck técnico-comercial** — este documento resumido, con la tabla de evidencia (sección 5) como
   prueba.
3. **Ficha metodológica pública** — secciones 3 y 4 (el procedimiento y los fundamentos), estilo
   "metodología de rating": transparente y auditable genera confianza.
4. **Demo reproducible** — el `run_pipeline.py` corriendo en vivo: "en 70 segundos reconstruyo 56
   empresas certificadas desde el dato crudo, mirá el semáforo por empresa."

> **Principio para todo el material:** cada afirmación va con su evidencia. Es lo que separa esto
> de un pitch vacío — y es, justamente, lo que el proceso mismo predica: *no afirmar sin poder
> probarlo con datos.*
