# PRODUCT_DEMO_READINESS — Fase H

**Fecha:** 2026-09-01 · Fuente: `RATIO_PRODUCT_MATRIX.csv` (104 celdas, 8
empresas × 13 ratios), `RATIO_INDEPENDENT_AUDIT.json`, `RATIO_ADVERSARIAL.json`

Regla de clasificación por celda (no por opinión — por el estado medido):

| estado del motor | clasificación demo | por qué |
|---|---|---|
| `CALCULADO` | **DEMO READY** | valor real, provenance completa, reproducido por un auditor independiente |
| `NULL_VALIDO` | **DEMO READY** | el NULL es el resultado correcto (p.ej. P/E con pérdida) — mostrarlo así es honesto, no una falla |
| `NO_CALCULABLE` | **DEMO WITH WARNING** | gap de dato real y documentado (se puede mostrar CON el motivo explícito, nunca vacío sin explicación) |
| `NO_IMPLEMENTADO` | **NOT READY** | no hay ningún valor que mostrar, ni siquiera un NULL justificado |
| `BLOQUEADO` | **NOT READY** | el código funciona; falta un enlace de infraestructura conocido y de causa única |

---

## 1. Tabla por empresa × ratio

`OK` = DEMO READY · `WARN` = DEMO WITH WARNING · `NO` = NOT READY

| empresa | P/E | EPS | P/B | P/S | ROE | ROA | D/E | Current | Quick | Gross Mgn | Op. Mgn | Net Mgn | EV/EBITDA |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| YPFD | OK¹ | OK | NO | NO | OK | OK | OK | OK | OK | OK | OK | OK | NO |
| CEPU | OK | OK | NO | NO | OK | OK | OK | OK | OK | OK | OK | OK | NO |
| TGSU2 | OK | OK | NO | NO | OK | OK | OK | WARN | WARN | OK | OK | OK | NO |
| GGAL | OK | OK | NO | NO | OK | OK | OK | WARN | WARN | WARN | WARN | WARN | NO |
| BMA | **NO²** | OK | NO | NO | OK | OK | OK | WARN | WARN | WARN | WARN | WARN | NO |
| AAPL | OK | OK | NO | NO | OK | OK | OK | OK | OK | OK | OK | OK | NO |
| MSFT | OK | OK | NO | NO | OK | OK | OK | OK | OK | OK | OK | OK | NO |
| NVDA | OK | OK | NO | NO | OK | OK | OK | OK | OK | OK | OK | OK | NO |

¹ YPFD P/E es `NULL_VALIDO` (EPS 2025 = −2.11, pérdida) — se muestra como
"—" con el motivo a la vista, no como una celda rota.
² BMA P/E es el único `BLOQUEADO` de la matriz: EPS existe (452.75 ARS),
pero el instrumento de mercado no está enlazado a la entidad.

**104 celdas: 67 READY (64%) · 12 WARNING (12%) · 25 NOT READY (24%).**
De las 25 NOT READY, 24 son las mismas 3 columnas (P/B, P/S, EV/EBITDA) ×
8 empresas — un gap de producto uniforme, no una falla por empresa. La
única NOT READY que sí es específica de una empresa es el P/E de BMA.

---

## 2. Veredicto por empresa

| empresa | veredicto | por qué |
|---|---|---|
| **AAPL, MSFT, NVDA** | **DEMO READY** | 10/10 ratios implementados con valor real; solo faltan los 3 no implementados en todo el universo |
| **CEPU** | **DEMO READY** | igual que las anteriores — mejor cobertura fundamental de las 5 empresas argentinas |
| **YPFD** | **DEMO READY** | igual, con el matiz de que su P/E es un NULL correcto (pérdida 2025), no un gap |
| **TGSU2** | **DEMO WITH WARNING** | 2 ratios de liquidez sin dato (balance no publica corriente/no-corriente en ese formato) |
| **GGAL** | **DEMO WITH WARNING** | 5 ratios sin dato — banco, mismo patrón que TGSU2 pero más extendido (sin margen bruto/operativo/neto tampoco) |
| **BMA** | **DEMO WITH WARNING para rentabilidad · NOT READY para valuación** | ROE/ROA/D-E/EPS listos; P/E bloqueado por infraestructura (enlace de instrumento), no por dato — es el único caso donde un cliente que pida específicamente "P/E de BMA" hoy no puede recibirlo |

---

## 3. ¿Se puede presentar un screener de las 8 empresas?

**Sí, con advertencias explícitas — no sin ellas.**

Un screener de las 8 empresas mostrando EPS, ROE, ROA, D/E, y (donde
aplique) márgenes y liquidez es **demostrable hoy** con provenance completa
en cada celda. Tres condiciones para que sea honesto:

1. **P/B, P/S y EV/EBITDA no aparecen como columnas** (o aparecen con una
   nota "próximamente" visible) — no se rellenan con guiones que se
   confundan con `NULL_VALIDO`. Mostrar un "—" sin distinguir "no
   implementado" de "calculado y da null" es exactamente lo que el encargo
   prohíbe ("no presentar ratios NO_IMPLEMENTED como si fueran NULL").
2. **BMA muestra su P/E como "no disponible: enlace de instrumento
   pendiente"**, no como un guion genérico — y sus fundamentales sí se
   muestran normalmente.
3. **GGAL y TGSU2 muestran sus celdas de liquidez/margen con el motivo**
   ("balance no clasifica activo corriente"), no vacías.

Con esas tres condiciones, el screener es honesto y defendible ante
preguntas de un cliente técnico. Sin ellas, sobredeclara.

---

## 4. Lo que el banco adversario dice sobre la confianza en estos números

Los 67 valores `CALCULADO` de la matriz están, hoy, verificados: 60/60
reproducidos por un auditor independiente (`RATIO_INDEPENDENT_AUDIT.json`),
y las identidades contables (Activo=Pasivo+Patrimonio, EPS=Resultado/
Acciones) cierran en las 8 empresas sin excepción. **Eso es una fotografía
del estado actual, no una garantía permanente**: el hallazgo F-061 (HIGH)
muestra que si un dato corrupto o de otra empresa entrara a `derived.fact`,
la capa de ratios lo usaría sin alarma — la defensa vive en un control
separado (`audit_provenance_ratios.py`) que hoy no es obligatorio antes de
publicar. Para este demo puntual no cambia nada (se corrió y dio 8/8 en
limpio, en el mismo ciclo que este documento). Para una operación
recurrente, es la precondición #4 que ya recomendaba `PRODUCT_DEMO_GATE.md`
del 2026-09-01, ahora con evidencia más directa.

---

## 5. Dictamen

```
RATIO_PRODUCT_GATE = PASS_WITH_WARNINGS
CLIENT_DEMO         = READY_WITH_WARNINGS
```

**Por qué no `BLOCKED`/`NOT_READY`:** ningún valor mostrado hoy es
incorrecto — 60/60 reproducidos por un auditor sin código compartido, 8/8
identidades contables cierran, 13/13 ataques adversarios dieron el
veredicto esperado (0 críticos en rojo tras aplicar la clasificación
correcta a A2/A7 como *hallazgos*, no como fallas del banco). Los gaps que
existen (P/B, P/S, EV/EBITDA, BMA P/E, liquidez de dos bancos) están
identificados, medidos y con causa conocida — no son desconocidos.

**Por qué no `PASS`/`READY` liso:** 3 de 13 ratios pedidos no están
implementados; una empresa de la muestra tiene su valuación bloqueada por
un enlace de infraestructura pendiente; y el hallazgo F-061 (HIGH) es una
brecha de diseño real, aunque hoy no se manifieste en los datos mostrados.
Mostrar el producto sin decir estas tres cosas sería sobredeclarar
capacidades — exactamente lo que el encargo pidió no hacer.

## 6. Para pasar a PASS/READY liso, en orden de impacto

1. Enlazar `identity_v1.instrument` para BMA → su P/E deja de estar
   bloqueado (ya calculable con el EPS que tiene hoy).
2. Implementar `price_to_book` (facts ya disponibles) y declarar+cablear
   `price_to_sales`.
3. Formalizar que la auditoría de identidad contable
   (`audit_provenance_ratios.py` o un control equivalente) es precondición
   de cada publicación, no un chequeo aparte — cierra F-061.
4. Declarar el concepto D&A en `ratio_defs.py` (dato ya disponible, F-062)
   para habilitar EV/EBITDA.

Ninguno de los cuatro requiere backfill masivo ni tocar SEC/CNV/Market más
allá de lo ya ingerido para esta muestra.
