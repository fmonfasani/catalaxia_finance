# PARTE XIV — HOMOLOGACIÓN TIKR

TIKR es **benchmark secundario, no autoridad primaria.** Catalaxia se nutre de
SEC EDGAR (XBRL) y CNV; TIKR de hecho toma sus datos de la misma SEC. Ir
directo a la fuente elimina un intermediario: **TIKR no se usa en ningún punto
del pipeline** (`docs/06-decisiones-tecnicas.md`). Se usa para **homologar**
— para medir qué tan bien reproduce Catalaxia lo que un proveedor reconocido
publica.

**Estado:** `NOT_IMPLEMENTED` en el repo principal. El procedimiento
(`h1_tikr_metr_homologacion.py`) vive solo en el worktree `catalaxia-cnvmig`.

**Material de base:** `outputs/docs/fase_cnv/METR_TIKR_2025_REPORT.md`
completo (447 líneas); `docs/runbooks/appendices/GOLDEN_RUNS.md` §2;
`docs/review/HOMOLOGATION_FINDINGS.md`;
`docs/manual/MANUAL_SCOPE.md` `C-4`, `D-4`, `N-8`;
`docs/manual/MANUAL_KNOWLEDGE_INVENTORY.md` §5 (`TIKR-03`), §2 (`DEC-04`).

---

## Paso 1 · Cómo se homóloga — el método

Cada métrica de TIKR se compara contra **una métrica de Catalaxia derivada de
evidencia primaria**, y el resultado se clasifica. La regla del método, sacada
de `HOMOLOGATION_FINDINGS.md`: *no volver a declarar algo que los artefactos
desmienten* — cada finding se verifica contra la base, ninguno se da por
cerrado por haber sido mencionado antes.

**El enunciado general (implementado en el worktree)** clasifica en estos 12
estados:

```
DIFFERENT_DEFINITION · PERIOD_MISMATCH · CURRENCY_MISMATCH · UNIT_MISMATCH
PERIMETER_MISMATCH · SOURCE_MISMATCH · TIKR_ONLY · CATALAXIA_ONLY
CATALAXIA_MISSING · TIKR_MISSING · ANOMALY · UNRESOLVED
```

**`KNOWN_LIMITATION (D-4):`** un encargo anterior pedía usar
`METHODOLOGY_DIFFERENCE` y `DATE_DIFFERENCE`. **No están implementados** — el
set que existe es el de 12 estados de arriba. Nadie mezcla los dos vocabularios
en un mismo reporte.

**FX (más `DEC-04`):** Catalaxia usa MEP; TIKR usa el mayorista. La brecha
entre ambos está **medida** (0,0–0,3 % en general, 85 % en 2021) y es **una
metodología, no un error**. Ante una diferencia de ese orden se la clasifica
`CURRENCY_MISMATCH`, no se corrige el dato.

---

## Paso 2 · El resultado medido — METR FY2025

Caso: METR, fixture aislado `cnvmig`, catalaxia intacta, sin commits.

```
Métricas TIKR evaluadas                     152
  estados financieros                        95
  ratios                                     39
  segmentos                                  18

MATCH_EXACT                                  35   (23,0 %)
MATCH_DERIVED                                 8   ( 5,3 %)
MATCH_ROUNDING                                8   ( 5,3 %)
COINCIDENCIAS                                51   (33,6 %)

DEFINITION_DIFFERENCE                        27   (17,8 %)
INPUT_DIFFERENCE                              1
DIFERENCIAS EXPLICADAS                       28   (18,4 %)

CATALAXIA_MISSING_INPUT                      66   (43,4 %)
TIKR_DEFINITION_UNVERIFIED                    2
TIKR_DERIVED_NOT_REPRODUCIBLE                 2
UNRESOLVED                                    4
CATALAXIA_ERROR                               0
```

**Cero errores de Catalaxia.** Además de las coincidencias, **28 diferencias
quedan explicadas con aritmética exacta** (no con narrativa) y el 43 % restante
es desglose que la CNV no publica en el EEFF resumido — un problema de ingesta,
no de modelo.

Los totales estructurales coinciden:

| métrica | TIKR | Catalaxia | Δ |
|---|--:|--:|--:|
| Total Assets | 1.390.076 | 1.390.076 | **0** |
| Total Liabilities | 429.731 | 429.731 | **0** |
| Total Equity | 960.345 | 960.345 | **0** |
| CFO / CFI / CFF | 89.042 / −58.733 / −42.338 | idénticos | **0** |
| Net Income (ambos perímetros) | 130.656 / 132.483 | ídem | **0** |

---

## Paso 3 · Los hallazgos que explican las diferencias

**1 · El hallazgo que resuelve la mitad de las diferencias: el perímetro
INDIVIDUAL de la CNV es, exactamente, el segmento "MetroGAS Distribution" de
TIKR.** Cuatro métricas independientes con diferencia **cero**; la minoritaria
sale sin residuo:

```
NetIncome INDIVIDUAL − CONSOLIDADO = 130.656 − 132.483 = −1.827  EXACTO
Equity    CONSOLIDADO − INDIVIDUAL = 960.345 − 958.465 = + 1.880  EXACTO
```

**2 · Operating Income** — `196.311` coincide exactamente con el "Segment
Total" de TIKR; TIKR reporta `188.583` porque reclasifica **7.728** a gasto
operativo. *Qué* renglón reclasifica no se puede determinar del EEFF resumido
→ `DEFINITION_DIFFERENCE`, no error.

**3 · EBITDA — consistente en su diferencia:**
```
Catalaxia  256.694 = OperatingIncome 196.311 + D&A 60.383
TIKR       231.071  parte de SU operativo (188.583) y de SU D&A (42.554)
D&A CNV (3011600) = 42.554 + 17.829 (amort. cargos diferidos) = 60.383  EXACTO
```

**4 · Total Debt — la diferencia mayor del balance:** Catalaxia 144.559
(71.079 + 73.480) vs TIKR 86.550. Los códigos 2322200 y 2312300 agregan más
que la deuda financiera de TIKR, y arrastran a Net Debt, Debt/Equity,
Debt/Capital, Debt/EBITDA y Net Debt/EBITDA.

**5 · Net Change in Cash:** `CFO+CFI+CFF = −12.029 = CashFlowNeto` de
Catalaxia; `−12.029 + ajuste cambiario (−32.698) = −44.727` = Net Change TIKR.
**Catalaxia excluye el ajuste cambiario del subtotal; TIKR lo incluye.** El
ajuste se deriva por diferencia, exacto.

**6 · Cash Beginning y el factor 1,3155:** Catalaxia tiene el cierre 2024 en
moneda de diciembre de 2024; TIKR usa el comparativo **re-expresado** a moneda
de diciembre de 2025. 160.859 / 122.280 = **1,3155** → el ROE (14,80 %) solo
reproduce re-expresando el patrimonio de apertura. **Lo que falta no es la
fórmula: es el comparativo re-expresado.** El defecto está cuantificado ahora.

**7 · Dos definiciones de TIKR que no se pudieron verificar** — ROA 8,3 % y
Operating Income Margin 10,9 % (ninguna variante los reproduce). **No se
inventó una definición para cerrarlos.** Además, TIKR es inconsistente consigo
mismo: usa saldo *promedio* en el ROE y saldo *de cierre* en el Asset Turnover.

**8 · Segmentos:** 10 de 18 exactos. `Segment Total` = CONSOLIDADO;
`MetroGAS Distribution` = INDIVIDUAL; MetroENERGY y eliminaciones solo son
derivables **en conjunto** (CONSOLIDADO − INDIVIDUAL).

---

## Paso 4 · La verificación no es opcional

- **Auditoría independiente** `c4_auditoria_metr_tikr.py`: 22 facts + 8
  identidades + 3 márgenes, **0 fallas**. No importa el adaptador ni el módulo
  semántico: tiene su propio parser del RAW y re-verifica desde el archivo
  (SHA-256, número impreso, escala). El auditor encontró y corrigió un error de
  la propia comparación (márgenes de distinto perímetro).
- **Mutaciones adversariales** (`tests/test_metr_tikr_2025.py`): las 10
  mutaciones (valor, unidad, escala, período, perímetro, entidad, SHA, num/den,
  atribución, documento equivocado) **fallan donde deben**.
- **Idempotencia y regresión:** 3 matrices con `sha256` idéntico en 2ª corrida;
  suite completa 378 passed · 3 failed (F-038, preexistentes) · 1 skipped; el
  proceso es de solo lectura — **no escribió una fila**.

---

## GATE de la Parte XIV

```
METR_TIKR_2025_GATE = PASS_WITH_WARNINGS
```

**PASS** porque 51/152 coinciden (33,6 %), las diferencias explicadas cierran
con aritmética exacta, hay **cero errores de Catalaxia**, el auditor
independiente reproduce cada match, las 10 mutaciones fallan, y SEC/CNV/
`catalaxia` quedaron intactos. **WITH_WARNINGS** porque el 43,4 % de la
superficie TIKR no tiene insumo, dos definiciones de TIKR quedaron sin
verificar y el Operating Income solo se explicó a medias.

**Lectura que responde la pregunta del ciclo:** Catalaxia reproduce hoy
**un tercio** de la superficie TIKR de METR desde evidencia primaria de la CNV,
y explica con aritmética exacta **otro quinto**. El 43 % restante no es un
problema de modelo — es desglose que no está ingestado.

**Pendiente para generalizar:** el único benchmark que existe es el de METR
(N-8) y el procedimiento vive en el worktree. Homologar no es "hacer que las
cifras coincidan": es **producir el mismo estado por un camino independiente
y clasificar la diferencia**.

---

*`N-8`: no hay benchmarks distintos de TIKR. `C-4`: tramo C de CNV +
homologación TIKR, pendiente de resolución D-1.*