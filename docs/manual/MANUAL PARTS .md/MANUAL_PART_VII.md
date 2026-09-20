# PARTE VII — RATIO ENGINE

Este capítulo cubre la etapa que convierte hechos económicos de
`derived.fact` en métricas persistidas en `derived.ratio`. Con YPF como
piloto y KO como prueba de que el motor **no sabe** ni debería saber si
trabaja con IFRS o US-GAAP.

**Principio rector** (`RATIO_CONTRACT.md`, `CATALAXIA_RATIO_PRODUCT.md`): el
Ratio Engine recibe **conceptos económicos**, no emisores. El camino es
`ratio → registry → tags candidatos → fact`, y ningún `if issuer == ...`
puede existir. Cada dato de este capítulo fue verificado contra el código y
contra `derived.ratio` en vivo el 2026-09-04 — nada es hipotético.

**Qué entender antes de seguir.** El motor implementa **cuatro** ratios hoy:
`eps`, `pe`, `pb`, `ev_sales`. Es un *vertical slice* elegido a propósito.
Los demás ratios del contrato (los de `ratio_defs.py`) **no los persiste el
motor**: los consumen `matriz_producto.py` (análisis) y la API. Ver Paso 5.

---

## Paso 1 — Correr el motor, sin persistir primero

**OBJETIVO**
Calcular los ratios de YPF y **leerlos antes** de escribir nada.

**PREREQUISITOS**
Parte V, Paso 1 (S04) con gate `PASS` — el motor come de `derived.fact`.

**COMANDO** — primero sin persistir (no escribe nada):
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851
```

**QUÉ HACE**
Dispara la guarda de pertenencia de provenance (**F-061**), evalúa los cuatro
ratios soportados para el CIK y muestra el resultado. Sin `--persist` no
escribe una sola fila.

**RESULTADO ESPERADO** — salida real verificada (2026-09-04):

```
catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False
F-061 · punteros de provenance ajenos: 0

4 ratios soportados · checkpoint=74914949e5efc71634f06ac0fe565d84

CIK          entidad              ratio     win  periodo     estado            valor   moneda
0000904851   YPF SOCIEDAD ANONIMA eps       FY   2025-12-31  CALCULADO        -2.11   USD
0000904851   YPF SOCIEDAD ANONIMA pb        PIT  2025-12-31  CALCULADO        1.83599 USD
0000904851   YPF SOCIEDAD ANONIMA pe        FY   2025-12-31  NOT_CALCULABLE       -   USD
             motivo: REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin valor por
             decision financiera, no por falta de dato: el EPS esta y su provenance tambien
0000904851   YPF SOCIEDAD ANONIMA ev_sales  FY   2025-12-31  CALCULADO        1.59922 USD

(sin --persist: no se escribio nada)
```

Los cuatro ratios de YPF, en forma de tabla:

| `canonical_id` | ventana | período | estado | valor | moneda | fórmula |
|---|---|---|---|---|---:|---|---|
| `eps` | FY | 2025-12-31 | CALCULADO | **-2.11** | USD | EPS básico reportado por el emisor |
| `pe` | FY | 2025-12-31 | **NOT_CALCULABLE** | — | USD | `(close / ratio_adr) / eps_basico` |
| `pb` | PIT | 2025-12-31 | CALCULADO | **1.835993** | USD | `(close/ratio_adr) / (patrimonio_controladora/acciones_circulacion)` |
| `ev_sales` | FY | 2025-12-31 | CALCULADO | **1.599221** | USD | `(market_cap + deuda_financiera - efectivo) / ingresos` |

Notá el detalle: `pe` aparece como `NOT_CALCULABLE` **con motivo**, no como
una celda vacía (Paso 3).

**VERIFICACIÓN**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
  "SELECT canonical_id, period_window, period_end, status, value, currency, motivo
     FROM derived.ratio WHERE cik='0000904851' AND valid_to IS NULL"
```
Coincide fila por fila con lo que imprime el motor.

**SI FALLA**
- `F-061 · punteros de provenance ajenos: N` con `N > 0` → el motor **se
  niega a seguir** (exit `1`): algún hecho de `derived.fact` apunta a un
  `parsed.facts` ajeno al emisor/filing/concepto. Es un incidente de datos,
  no un ajuste de cálculo.
- *"el CIK X no resuelve a una entidad con assertion VERIFIED"* → la
  identidad no quedó sembrada/verificada: Parte III, Paso 2.
- *"la entidad no tiene instrumento ligado"* → el enlace de mercado no está
  (ver Paso 5, límite de Market).
- *NOT_CALCULABLE sin motivo leíble* → sería un bug de reporte; el contrato
  exige que toda fila sin valor lleve su motivo.

---

## Paso 2 · Los cuatro ratios que el motor sí implementa

**OBJETIVO**
Saber exactamente qué se persiste, con qué contrato — porque **ninguna de las
cuatro ventanas se inventa**.

Contrato real (`ratio_engine.py`, `SPECS`):

| `canonical_id` | `formula_version` | ventana | basis | fórmula |
|---|---|---|---|---|
| `ev_sales` | `ev_sales_v1` | **FY** | n/a | `(market_cap + deuda - efectivo) / ingresos` |
| `eps` | `eps_v1` | **FY** | AVERAGE | EPS básico reportado por el emisor |
| `pb` | `pb_v1` | **PIT** | CLOSING | `(close/ratio_adr) / (patrimonio_controladora/acciones_circulacion)` |
| `pe` | `pe_v1` | **FY** | n/a | `(close/ratio_adr) / eps_basico` |

**Asimetría que importa entender** (`RATIO_CONTRACT.md`, Regla 1):
`ev_sales` se emite con `period_window = 'FY'` de forma **explicita y
honesta**. El motor **no sabe sumar cuatro trimestres**: emitirlo como TTM
sería mentir sobre el período. `pe` también es FY, porque el EPS que usa es
el del último ejercicio anual — no una suma de trimestres, y se publica
diciéndolo. **Un ratio `instant` nunca se trata como flujo ni se agrega.**

**Cómo se elige el tag de cada concepto** (`ratio_defs.CONCEPTOS`): una lista
**ordenada** por concepto; el primero que exista en la base gana, y el tag
elegido queda en la provenance del ratio. Con una salvedad declarada por el
propio código: `deuda_financiera` usa `Borrowings` (IFRS) o `LongTermDebt`
(US-GAAP) — el comentario en `ratio_defs.py` aclara que **no son el mismo
perímetro** y se usan igual porque es la mejor aproximación disponible.
`eps_basico` va por `BasicEarningsLossPerShare` / `EarningsPerShareBasic` /
`BasicAndDilutedEarningsPerShare` — el nombre del tag cambia entre ejercicios
dentro de IFRS.

---

## Paso 3 · `NOT_CALCULABLE`, nunca `0`

**OBJETIVO**
Que el operador entienda por qué "sin dato" y "sin valor" son respuestas
correctas, y a qué precio de diseño.

**El caso vivo (YPF `pe`)** — el motivo completo:

> `REGLA: EPS = -2.11 <= 0 (ejercicio con perdida). El P/E queda sin valor por
> decision financiera, no por falta de dato: el EPS esta y su provenance
> tambien`

Leélo con atención: el EPS **existe** (-2.11, con provenance), pero un P/E
sobre un EPS negativo no es un número que el sistema publique como válido.
Ésa es la diferencia entre `NOT_CALCULABLE` (motivo explícito) y un `0`
(invento).

**Reglas del contrato que lo hacen posible:**
- **R6/R7** — falta un insumo → se persiste `NOT_CALCULABLE` con el motivo.
  La fila queda, con el motivo, y cuando falta un eslabón se guarda **qué
  conceptos sí se resolvieron** y en cuál se cortó.
- **R2** — precio y fundamentals **deben** estar en la misma moneda. El motor
  **no convierte**: si los fundamentals están en USD y no hay precio en USD,
  no calcula.
- **R10** — sin provenance completa no hay valor: cada fila guarda, por
  insumo, el tag elegido, la cadena evaluada, el `fact_key`, los
  `source_fact_ids` y el hash del archivo fuente.
- **EPS** — orden de prioridad: (1) EPS básico reportado compatible, (2) NI
  atribuible / weighted average shares, (3) fallback documentado. **Nunca**
  usar `Shares Outstanding` automáticamente como `Weighted Average Shares`.

---

## Paso 4 · El registry multi-taxonomía — la prueba de que no hay ramas

**EVIDENCIA (KO, Golden Run en `kogolden`):** los **20 conceptos** del
registry resolvieron contra tags **us-gaap** — `Assets`,
`StockholdersEquity`, `InventoryNet`, `Revenues`,
`EarningsPerShareBasic` — sin una sola condición por fuente. Primera salida:
**EPS = 3.05 USD**, calculado, con US-GAAP puro. El resto de los ratios
contables de KO quedaron `NOT_CALCULABLE` por falta de insumos, y eso es
**correcto**: `NOT_CALCULABLE` no es un error.

La cadena demostrada:
```
ratio definition → registry → taxonomy mapping → US-GAAP → EPS 3.05
```
con el mismo motor que calcula el EPS de YPF (-2.11) desde **ifrs-full**.
**Ese es el punto de la Parte VII**: el ratio no debería saber si trabaja con
YPF o con KO — y no lo sabe.

---

## Paso 5 · Límites conocidos

**`KNOWN_LIMITATION` (L-12)** — `ratio_engine.py` sigue siendo **SEC-first**:
toma `--cik` y, si no se lo pasás, itera `ciks_del_universo()`. La
arquitectura declara que el motor debe consumir el Financial Model (`d2_*`),
no un CIK; hoy no es así (medido en el inventario, `ARQ-03`). No es una
opinión: es el estado del código.

**`KNOWN_LIMITATION` — dependencia de Market para cálculos contables.** El
motor necesita el esquema de mercado y un instrumento ligado en
`identity_v1.instrument` **incluso para ratios sin componente de precio**
(la guarda de pertenencia y la resolución de entidad obligan al pipeline de
mercado). Por eso el Golden Run de KO tuvo que instalar el esquema Market
vacío en su base aislada. Lo deseable —ratios contables sin Market— está
documentado como mejora, no implementado.

**`KNOWN_LIMITATION` — el motor persiste cuatro de los ratios del contrato.**
`derived.ratio` tiene exactamente cuatro `canonical_id` (verificado). Los
otros ratios definidos en `ratio_defs.py` los consume
`matriz_producto.py` (un script de **análisis**, no una etapa del pipeline):
en el entorno de referencia su matriz arroja **66 `CALCULADO` / 12
`NO_CALCULABLE` / 24 `NO_IMPLEMENTADO` / 1 `BLOQUEADO`** sobre 104 filas. Los
ratios con prefijo `CNV_` que la CNV publica ella misma son **control
cruzado**, nunca sustituto.

**`KNOWN_LIMITATION` (menor, de documentación)** — el encabezado del script
todavía dice *"Primer ratio: EV/Sales … un solo ratio"* mientras que el
ejecutable soporta los cuatro del `SPECS` (líneas 289-301). El código corrió
adelante del comentario.

---

## Resumen de la Parte VII

| paso | qué | evidencia |
|---|---|---|
| 1 · correr sin persistir | 4 ratios calculados, nada escrito | salida verificada + consulta `derived.ratio` |
| 2 · contrato de los 4 | FY/PIT explícitos, sin TTM inventado, tags por `ratio_defs.CONCEPTOS` | `SPECS` en código |
| 3 · `NOT_CALCULABLE` | motivo obligatorio, nunca `0` | `pe` YPF: EPS≤0 |
| 4 · registry multi-taxonomía | IFRS y US-GAAP con el mismo motor | KO: 20/20, EPS 3.05 |
| 5 · límites | L-12 SEC-first, dependencia de Market, 4 de N ratios | inventario + código |

**GATE de la Parte VII:** el motor sale con todas las etapas de cálculo
`CALCULADO` o `NOT_CALCULABLE` **con motivo** (nunca `REVIEW_REQUIRED` ni
violaciones de pertenencia F-061), y los cuatro estados coinciden con
`derived.ratio`. Sin `--persist` no se escribe nada; con `--persist`, cada
corrida nueva versiona la fila anterior por `ratio_key` — no la borra.

**Lo que sigue:** la traza hacia atrás de cualquiera de estos números
(Parte X, Provenance) y el procedimiento de Golden Run completo (Parte XVI).

---

*Los comandos de este capítulo fueron ejecutados y sus salidas verificadas en
vivo (2026-09-04). `ratio_engine.py --cik` sin `--persist` no escribe nada;
ninguna operación toca producción (5432).*