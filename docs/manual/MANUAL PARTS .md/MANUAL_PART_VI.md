# PARTE VI — ECONOMIC FACTS Y FINANCIAL MODEL

Este capítulo documenta los dos eslabones que separan el dato extraído del dato
utilizable: **qué es un hecho económico** (`econ_key`) y **qué forma tiene el
modelo financiero** que consume el motor de ratios.

**Estado:** `NOT_IMPLEMENTED` en el repo principal + `DECISION_REQUIRED (D-1)`
+ `KNOWN_LIMITATION (L-11, L-12)`. La migración `036_economic_identity`, el
script `d2_metr5y_model.py` y los estados modelo viven **solo en el worktree**
`catalaxia-cnvmig`.

**Material de base:** `docs/runbooks/06_PROVENANCE.md` §4 (lo único que se
puede afirmar desde el repo principal); `docs/manual/MANUAL_SCOPE.md` §0, §1.1
fila 6-7, `C-2`, `D-1`, `L-11`, `L-12`, `L-10`; `MANUAL_KNOWLEDGE_INVENTORY.md`
§5 (`ARQ-03`, `DIR-01`, `DEC-03`); `outputs/docs/fase_cnv/METROGAS_GOLDEN_RUN_REPORT.md` §5-§6.

---

## Paso 1 · fact_key vs. econ_key — la ocurrencia y el hecho

Todo lo que el pipeline toca tiene dos identidades, y confundirlas es el error
de modelado más caro del proyecto.

| | `fact_key` | `econ_key` |
|---|---|---|
| qué identifica | **la ocurrencia** — el valor tal como un documento lo declaró | **el hecho económico** — independiente del documento que lo declaró |
| serialización | componente de `(entity, documento, qname, context, unidad)` | serialización canónica del hecho económico (entidad, concepto, contexto, unidad, medición) |
| disponible en | repo principal | **solo en el worktree** (`036_economic_identity`) |
| NULL hoy | nunca en la capa normalizada | **sí para SEC** — alcance, **no** omisión |
| poblado | los tres pilotos | **solo METR** (vía el adaptador del worktree) |

**Varias ocurrencias pueden compartir `econ_key` sin ser un duplicado.** Ejemplo
real, del `METR_TIKR_2025_REPORT.md` §8 — `Revenue` FY2025 CONSOLIDADO:

```
documento   d96fd259-…-17af592b99f9.html · Presentación #3487124
código      3000100 · impreso 1.217.305,00 · escala 10⁶
fact_key    e270dfb8681a133b088b38a677bdc3bb0e828d1072f208a50c6df247160a57f3
econ_key    9b0c12ce7825100d46e6c61bd80a26cd40f563064472e3ba56eb67be18e1a7c6
```

**Lo que `econ_key` habilita, y por qué exige `measurement_date`:** bajo IAS 29
el mismo período puede tener **dos mediciones legítimas** — el cierre en moneda
del propio ejercicio y el comparativo re-expresado a moneda del ejercicio
siguiente. Eso **no** es un duplicado: es el mismo hecho económico, dos veces
medido. `econ_key` + `measurement_date` es el par que las distingue. El defecto
está cuantificado en el reporte TIKR: por eso `ROE` TIKR = 14,80 % solo
reproduce si el patrimonio de apertura se re-expresa con el factor 1,3155.

---

## Paso 2 · La frontera arquitectónica declarada

El plan maestro declara una cadena de cuatro eslabones:

```
Source Adapter → Canonical Model → Financial Model → Ratio Engine
```

**`KNOWN_LIMITATION (L-11)`** — el **Financial Model no está persistido**: se
arma **en memoria** y el script que lo implementa (`d2_metr5y_model.py`) vive
solo en el worktree. El repo principal termina en el Canonical Model
(`derived.fact`) y el Ratio Engine construye sus estados ad hoc.

**`KNOWN_LIMITATION (L-12)`** — pese a la arquitectura declarada,
`ratio_engine.py` **sigue siendo SEC-first** (`ARQ-03` en el inventario de
conocimiento): toma `--cik` e itera `ciks_del_universo()`. **El Ratio Engine no
consume hoy lo que la arquitectura dice que debería consumir.** Es un hecho
medido, no una opinión: `ratio_engine.py:556-562` lo declara — el motor está
homologado solo para el universo SEC y su cadena de fallback son tags
us-gaap/ifrs.

---

## Paso 3 · Qué forma tiene el Financial Model

Cuando exista, el modelo financiero organiza los hechos en **estados** y en
**series**:

| estado | qué contiene | regla de período |
|---|---|---|
| **Balance** | activos, pasivos, patrimonio | INSTANT (*stock*) |
| **Resultado** | ingresos, costos, resultados | DURATION (*flujo*) |
| **Flujo de efectivo** | CFO, CFI, CFF y desglose | DURATION |
| **Capital** | acciones emitidas, promedio, diluidas | INSTANT (count) |

**Reglas que el modelo no puede romper** (todas con evidencia en datos):

1. **Nunca sumar un INSTANT como si fuera DURATION**, ni al revés. Verificado en
   los 2.795 hechos canónicos de METR: flujos → 1.038 `DURATION`, saldos → 1.070
   `INSTANT`, **ninguno cruzado**.
2. **La unidad nunca se pierde.** La escala vive en `unit_ref`; `decimals` es
   NULL por decisión certificada (desacople precisión/escala). Un hecho sin
   unidad no entra en ningún ratio: `NOT_CALCULABLE`.
3. **Consolidado y standalone son perímetros distintos, no variantes.**
   Codificado en `PARENTESCO` del `context_id`. Para METR: 1.398 hechos
   CONSOLIDADO y 1.397 INDIVIDUAL — los dos lados del mismo emisor.
4. **La moneda es la del hecho**, no la del emisor, no la del usuario.
5. **Series FY / Quarterly / YTD / TTM se declaran, no se infieren.** La CNV
   acumula YTD: un "Q3" son nueve meses, y todo `DURATION` arranca el 1 de
   enero (verificado en los 1.038 + 111).
6. **Stock vs. flujo ≠ INSTANT vs. DURATION como sinónimos reemplazables:**
   la CNV misma publica ratios (prefijo `CNV_`, unidad `xbrli:pure`) que son
   INSTANT (liquidez) o DURATION (margen) según su naturaleza.

**`KNOWN_LIMITATION (L-10)`** — el perímetro no es computable desde el
formulario: el documento declara `tipo_balance`, no de qué consolidación
proviene. No se inventa.

---

## Paso 4 · La realidad verificable desde el repo principal

Desde el repo principal **no hay comandos ejecutables** para este capítulo.
Lo que sí se puede afirmar (fuente `06_PROVENANCE.md` §4):

- `econ_key` es una **columna real del modelo canónico**, no un concepto de
  pizarra; su documento de identidad es un contrato aparte
  (`outputs/docs/fase_cnv/W1_1_FACT_IDENTITY_CONTRACT.md`).
- Aunque se documente "en rama", la verificación es explícita: **comparar
  `ratio_engine.py` contra `d2_metr5y_model.py`**. El operador debe poder decir
  en qué momento el motor de ratios consume un estado construido por el modelo
  y no volvió a armar todo sobre `derived.fact`.
- **METR es el único piloto con `econ_key` poblado** — por el adaptador del
  worktree, `c4_cnv_adapter.py`. Cualquier ejemplo que se documente es
  necesariamente CNV, no SEC.

---

## GATE de la Parte VI

Este capítulo queda **sin ejecución y sin verificación hasta que se resuelva
D-1** (¿repo principal, worktree, o los dos?). Hasta entonces:

- `fact_key`: usable, documentado en la Parte XI.
- `econ_key`: **no** usable desde el repo principal.
- Financial Model: **no** persistido (`L-11`); motor de ratios SEC-first
  (`L-12`).
- Certificación pendiente: **C-2** (Economic Facts + Financial Model).

No está permitido declarar que el sistema "tiene un modelo financiero" mientras
el Financial Model se arme en memoria dentro de un trabajo aparte.

---

*Este capítulo describe una frontera, no una implementación: documenta lo que
la arquitectura declara y lo que el código del repo principal realmente hace.*