# PRE_HOMOLOGATION_GATE

**2026-08-28 · `catalaxia-engine-dev` 127.0.0.1:5433**
**Reproducible:** `python scripts/engine/audit_pre_homologacion.py`
Evidencia: `docs/review/PRE_HOMOLOGATION_FINDINGS.md` ·
`outputs/docs/homologacion/pre_homologacion.json`

**No se implementó ningún fix. No se homologa en este ciclo.**

---

## Matriz de decisión

| | estado técnico | riesgo actual | corrupción nueva | identidad | provenance | reproducibilidad | operación | clasificación final |
|---|---|---|---|---|---|---|---|---|
| **F-041** | 1 assertion sin `source_facts` | nulo | **no** | intacta | completa (falta forma estructurada) | sin efecto | sin efecto | **NON-BLOCKING** · deuda histórica |
| **F-043** | `EMPTY` nunca emitido; 7 instrumentos mal tipificados | bajo | **no** | sin efecto | sin efecto | sin efecto | **re-pide 7 por corrida** | **PRODUCT LIMITATION** + DOCUMENTATION DEBT |
| **F-044** | `source` sin trigger ni historial | **residual, sólo owner** | no por `engine` | **sí, CIK, con owner** | sin efecto | sin efecto | ninguno | **NON-BLOCKING** con riesgo residual |
| **F-046** | 6 assertions con `left_ref NULL` | nulo | **no** (F-045 lo impide) | intacta | completa | sin efecto | sin efecto | **NON-BLOCKING** · deuda histórica |
| **F-047** | 3 pares `CANDIDATE`+`VERIFIED` | nulo | **no** | intacta | **correcta**: son actos distintos | sin efecto | sin efecto | **DOCUMENTATION DEBT** |

Regla aplicada: `BLOCK` **sólo** si existe un camino reproducible que produzca
corrupción, identidad incorrecta, provenance incorrecta, duplicación o pérdida en
operación normal o mediante `catalaxia_engine`.

---

## Las cinco respuestas

### 1. ¿Existe algún blocker técnico real? **No.**

Ninguno de los cinco es alcanzable por `catalaxia_engine` ni se produce en operación
normal. Verificado ruta por ruta, no inferido:

- **F-041 y F-046**: no hay camino operativo para modificarlas. `catalaxia_engine`
  choca con GRANT de columna; el owner choca con `tg_assertion_inmutable` y
  `tg_no_borrar_assertion`. Y F-045 impide que se creen casos nuevos.
- **F-044**: `catalaxia_engine` tiene sólo `SELECT` sobre `source`. Las tres rutas
  (UPDATE/INSERT/DELETE) dan `permission denied`.
- **F-043**: 0 filas `FAILED` con datos, 0 precios escritos, 0 RAW en disco. No hay
  pérdida ni corrupción.
- **F-047**: 0 bridges `VERIFIED` contradictorios, 0 mal formados.

### 2. ¿Qué findings pueden aceptarse sin corregir?

**Los cinco**, con distinto fundamento:

- **F-041, F-046** — deuda histórica **no reproducible**. Corregirlas exigiría volver
  sobre assertions inmutables, y el riesgo residual es nulo: las 6 declaran
  `SEC_REGISTRY` sobre `CIK`, para el que esa fuente **es** autoritativa.
- **F-047** — **no es un defecto.** Reproducido, la coexistencia de propuesta y
  ratificación es intencional, está documentada en el código, y ningún consumidor la
  confunde. Corrige mi propio informe de homologación, que la registró como defecto de
  higiene.
- **F-043** — limitación de producto. El comportamiento del fetcher es correcto (la
  fuente no cubre esos símbolos); lo que falta es representar esa categoría.
- **F-044** — riesgo residual acotado al rol owner, documentado abajo.

### 3. ¿Qué findings deben corregirse antes de homologar?

**Ninguno es condición necesaria** bajo la regla dada. Pero para una homologación
integral *con garantía completa* —no sólo con estado sano— hay un orden recomendado:

1. **F-044** primero, y no por su severidad sino por su posición: es la **raíz de
   confianza**. Todas las demás garantías consultan `source`, y `source` es la única
   tabla de `identity_v1` sin trigger ni historial. Un CHECK que enumere las fuentes
   válidas para `CIK` —como ya existe para `CUIT`— cerraría la asimetría demostrada.
2. **F-043** después, porque tiene costo operativo recurrente (7 requests inútiles por
   corrida) y es un cambio pequeño y contenido.
3. **F-041/F-046** sólo si se decide que la deuda no debe existir; no aportan
   seguridad.
4. **F-047**: nada que corregir; a lo sumo documentar.

### 4. ¿Qué alcance exacto puede homologarse?

**Homologable hoy, con las notas de la matriz:**

| | condición |
|---|---|
| Identity V1 como sistema de garantías | F-045 cerrado y verificado por auditoría independiente |
| Backfill CIK — 513 anclas | 0 duplicados, 0 incoherencias de tipo |
| Provenance histórica | inmutable frente a ambos roles; 1 deuda declarada (F-041) |
| SEC S03/S04 | cobertura del universo EDGAR no auditada |
| Identity → CNV | **sólo las 3 empresas ejecutadas**; no extrapolable |
| Identity → Market | 584 instrumentos; deuda semántica de `ticker_canonico` (F-014) |
| Reproducibilidad / hash | sin reservas |
| Lifecycle de corridas | 0 `RUNNING`, sin reservas |
| Aislamiento de producción y de roles | verificado: Market no escribe en 5432; `catalaxia_engine` no accede a tablas de Market |

**No homologable:** CNV a escala (G5, limitación de fuente) · los 56 BYMA (limitación
de producto) · la política de autoridad como raíz protegida (F-044).

### 5. ¿Qué riesgo residual queda?

**Uno solo, y conviene enunciarlo sin suavizar:**

> Con el rol **owner** —el que corre las migraciones— es posible elevar
> `LEGACY_DIM_ENTITY` a `AUTHORITATIVE` y, a partir de ahí, **establecer un CIK
> autoritativo desde una fuente que no lo es**. Demostrado en transacción revertida.
>
> El **CUIT no** es alcanzable por esa vía: `ck_cuit_exige_evidencia_estructurada`
> enumera las fuentes literalmente (`ELSE false`) y por eso es inmune a una política
> adulterada. El CIK no tiene esa red.
>
> Los dos triggers de F-045 **no cierran** este camino: ambos consultan `source`, así
> que una política adulterada los convence a los dos. F-045 agrega una segunda
> barrera, no una independiente.

Riesgos menores: 7 requests inútiles por corrida de Market (F-043); 7 assertions
históricas que no cumplen contratos posteriores pero sí el de su momento (F-041,
F-046); y un modelo que no distingue «supersedido» de «confirmado» (F-047).

---

## Findings nuevos de este ciclo

**Ninguno como defecto.** Dos observaciones que quedan registradas:

1. **La asimetría CIK/CUIT frente a una política adulterada** no es un finding nuevo
   sino la caracterización precisa de F-044, que hasta ahora se había reportado sin
   determinar si F-045 lo mitigaba. Ahora está medido: **no lo cierra**.
2. **F-047 no era un defecto.** Se reclasifica de «higiene de supersession» a
   documentación, corrigiendo mi propio informe de homologación.

---

## Estado de la base al cerrar

```
entidades .......................... 525      CIK autoritativos ........ 513
assertions ......................... 614      CUIT autoritativos ....... 3
identifiers vigentes ............... 574      bridges VERIFIED ......... 3
corridas RUNNING ................... 0        CUIT CANDIDATE ........... 53
```

**Ninguna fila fue modificada en este ciclo.** Todas las pruebas mutacionales
corrieron en transacciones revertidas.
