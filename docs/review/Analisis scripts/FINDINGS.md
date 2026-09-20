# CATALAXIA — FINDINGS

Auditor: **CIAA** · Baseline `catalaxia-baseline-2026-08-25` / `444ee1a`
Ciclos: **AUDIT-01** (2026-08-25 mañana) · **AUDIT-02** (2026-08-25 tarde)

Regla invariante: ningún finding se cierra por declaración del owner. Se cierra
**contra su `acceptance_test`**, verificado por el auditor sobre artefactos reales.

---

## TABLERO — estado tras AUDIT-02

| ID | Sev | Workstream | Estado | Evidencia decisiva |
|---|---|---|---|---|
| F-001 | **HIGH** | MARKET | **OPEN — exposición aumentada** | Sin guarda; `m6_scale.py` existe e importa `m2_fetch_engine` (hereda 5432) |
| F-002 | LOW | GLOBAL | **OPEN — sin cambios** | `engine/config.py:41` sigue `db_port == "5432"` |
| F-003 | MEDIUM | CNV | **OPEN — degradado desde HIGH** | Defecto agudo corregido y verificado; 2 de 3 criterios sin cumplir |
| F-004 | MEDIUM | CNV | **SUPERSEDED** | Decisión de diseño registrada e implementada; residual en F-008 |
| F-005 | LOW | CNV | **OPEN — sin cambios** | El stage report sigue sin embeber el manifest |
| F-006 | MEDIUM | GLOBAL | **PARCIALMENTE CERRADO** | 3 de 4 STATE actualizados; `MARKET_STATE` sigue en 01:34 y falso |
| F-007 | MEDIUM | CNV | **NUEVO** | `C-C3-007` sigue admitiendo PASS vacuo por otras dos vías |
| F-008 | MEDIUM | CNV | **NUEVO** | El RAW creció 152 → 377 archivos; el crecimiento no fue resuelto |
| F-009 | MEDIUM | SEC | **NUEVO** | 5 de 8 corridas de S03 quedaron sin estado terminal |
| F-010 | LOW | GLOBAL | **NUEVO** | `created_at` del checkpoint C3 no se actualiza en el reuse |

---

# ADJUDICACIÓN DE FINDINGS PREVIOS

## F-001 — OPEN · exposición **aumentada**

**Estado anterior:** HIGH, OPEN.
**Estado ahora:** HIGH, OPEN. **No se aplicó ninguna mitigación.**

**Verificación (read-only):**
```
grep 'ALLOW_PROD|EXT-010|is_prod|5433' scripts/market/m6_scale.py scripts/market/m2_fetch_engine.py
   -> sin coincidencias

scripts/market/m6_scale.py:39  ->  import m2_fetch_engine as eng
   (hereda pg_conn: DB_PORT=5432, DB_NAME=catalaxia, sin guarda)
```

**Por qué la exposición aumentó y no sólo persiste:** en AUDIT-01 el riesgo era
prospectivo, con M23 sin código. Ahora `m6_scale.py` existe (197 líneas), su docstring
declara *"orquesta `run_instrument()` sobre el universo completo de instrumentos MAPPED"*,
y su ruta de escritura por defecto es exactamente la base que el engine protege con EXT-010.
La distancia entre la condición y su materialización pasó de "falta escribir el script" a
"falta ejecutar un comando".

**Atenuante verificado — sigue sin ejecutarse:**
```
market_fetch_log   : 2 instrumentos · 21 corridas · última 2026-08-25 04:27:40
market_price_daily : 2 instrumentos
```
Idénticos a AUDIT-01. Cero contaminación.

**`acceptance_test`** (sin cambios): correr un script operativo de Market sin variables de
entorno y verificar que aborta, escribe en destino no-producción, o existe decisión
aceptada que declare 5432 legítimo.

---

## F-002 — OPEN · sin cambios

```python
# engine/config.py:40-41  (verificado 2026-08-25 tarde, sin modificar)
@property
def is_prod(self) -> bool:
    return self.db_port == "5432"
```

Severidad **LOW** sostenida: topología local estable. No hubo intento de resolución ni se
esperaba en este ciclo.

---

## F-003 — OPEN · degradado HIGH → MEDIUM

El defecto agudo **fue corregido y lo verifiqué funcionando**. Pero el `acceptance_test`
de AUDIT-01 tenía **tres** cláusulas y sólo una se cumple.

**Código actual** (`scripts/engine/c3_cnv_fetch.py:549`):
```python
estados = {r.get("review_id") or r.get("review"):
           (r.get("status") or r.get("estado_c2") or r.get("estado")) for r in reviews}
```

**Verificación por simulación sobre el CSV real (4 escenarios):**

| # | Escenario | Resultado | Criterio |
|---|---|---|---|
| 1 | CSV real intacto | PASS, leyendo `OPEN`/`RESOLVED`/`PARTIAL` | **mide de verdad** ✓ |
| 2 | `C1-R-001` cerrada artificialmente | **FAIL** | **cláusula 1 CUMPLIDA** ✓ |
| 3 | columna `status` renombrada | PASS silencioso | cláusula 2 **incumplida** ✗ |
| 4 | CSV ausente (`load_open_reviews` → `[]`) | PASS con "3/3 intactas" | cláusula 2 **incumplida** ✗ |

**Cláusula 3 — test de regresión: incumplida.** `tests/test_engine_cnv.py` aporta 8 tests,
**ninguno cubre `C-C3-007`**:
```
TestCanonicalHash      : cachebust · antiforgery · cambio real detectado · blob no canonicaliza
TestClassifyRelacion   : controlada vs vinculada · sin tipo · eeff propio · texto no financiero
```

**Adjudicación:** el gate ya **no** es un falso PASS en operación normal — eso justifica
bajar de HIGH a MEDIUM y levantar el BLOCK que sostenía. Pero la *clase* de defecto sigue
alcanzable por dos vías (F-007) y sin red de regresión. **No se cierra.**

---

## F-004 — SUPERSEDED

El owner tomó y registró una decisión de diseño que **redefine la premisa** del finding.

**Implementación verificada** (`engine/cnv/rawstore.py:59-79`), reimplementada por el
auditor sin importar el módulo:
```python
_RE_ASSET_CACHEBUST  = rb"(\?v=)[0-9a-f]{8}-[0-9a-f]{4}-...-[0-9a-f]{12}"
_RE_ANTIFORGERY_TOKEN = rb'(name="RequestVerificationToken"\s+value=")[^"]+(")'
CANONICALIZABLE_KINDS = ("EMPRESA_PAGE", "VISOR")
# canonical_sha256: "NOT used for RAW storage/addressing"
```
Acotada a dos patrones y a dos tipos de artefacto. **No toca el direccionamiento del RAW.**

**Pruebas independientes del auditor sobre 75 pares de capturas reales:**
```
P1  hash CRUDO igual     :  0/75
    hash CANÓNICO igual  : 74/75
P3  RAW con token real   : 74/75
    RAW con 'CANON' escrito: 0/75      <- el RAW NO fue reescrito
```

**El 1/75 que no converge es `EMPRESA_PAGE`, y es correcto.** Diff tras canonicalizar:
198 líneas de contenido **real** — una presentación nueva publicada por CNV
("24 ago. 2026 · Banco Comafi S.A."). Es la mejor prueba de sensibilidad disponible:
la canonicalización **dejó pasar un cambio genuino**. Mejor evidencia que cualquier mutación
sintética.

**Resultado del check en la corrida más reciente** (`run6`, `eb05375b…`):
```
C-C3-006 PASS: comparados contra corrida previa=75/75, sin_precedente=0,
identicos en sustancia=75, cambios reales=0 (esperado 0)
```

**Por qué SUPERSEDED y no CLOSED:** el `acceptance_test` original exigía
`escritos=0` sin filas nuevas. El propio reporte declara —con encomiable franqueza—
*"escrituras RAW nuevas=75 de todos modos; eso ya NO es lo que este check mide"*.
La premisa cambió: idempotencia dejó de significar identidad de bytes y pasa a significar
identidad de sustancia. Es una decisión legítima, documentada y bien implementada. El
residual de almacenamiento se traslada a **F-008**.

---

## F-005 — OPEN · sin cambios

Claves de `C3_CNV_STAGE_REPORT_run6_rerun_PASS_fixed.json`:
```
['code','gate','mode','input','nulls','stage','run_id','coverage','integrity',
 'started_at','finished_at']
```
Sin lista de artefactos. La única fuente de los 75 `sha256`/`raw_path` sigue siendo
`fetch_raw.cnv_download_log`@5433.

Contraste que sigue vigente: el paquete golden de Market **sí** incluye `provenance.csv`,
y eso permitió verificarlo íntegro sin tocar la base en ambos ciclos.

---

## F-006 — PARCIALMENTE CERRADO

**Cerrado en 3 de 4:**
```
CNV_C3_STATE.md    2026-08-25 10:57   actualizado
SEC_S03_STATE.md   2026-08-25 11:10   actualizado
WORKSPACE_STATE.md 2026-08-25 11:12   actualizado
MARKET_STATE.md    2026-08-25 01:34   SIN ACTUALIZAR
```

**Abierto en MARKET, y es justamente el caso que motivó el finding.** `MARKET_STATE.md`
sigue afirmando, con el archivo en disco desde las 10:41:
```
:18   "scripts/market/m6_scale.py sigue **sin escribirse**"
:98   "sigue sin código (m6_scale.py no existe)"
:104  NEXT ACTION: "escribir scripts/market/m6_scale.py para M23"
```
`WORKSPACE_STATE.md:143` lo repite: *"between M22 (done) and M23 (scale-out, **locked**)"*.

Un lector del estado concluiría que M23 no tiene código. Tiene 197 líneas listas para correr
contra 584 instrumentos, sin la guarda que el propio `NEXT ACTION #2` de ese archivo exige.

---

# NUEVOS FINDINGS — AUDIT-02

## F-007 · `C-C3-007` conserva dos vías de PASS vacuo

| | |
|---|---|
| **severity** | MEDIUM · **workstream** CNV · **owner** CLAUDE 3 · **status** OPEN |
| **component** | `scripts/engine/c3_cnv_fetch.py:107-110, 545-552` |

**description** Corregidas las claves, la ausencia de datos sigue interpretándose como
ausencia de problema. Dos rutas verificadas:
1. **Renombre de columna** — `.get("status") or .get("estado_c2") or .get("estado")`
   devuelve `None` para todos y `cerradas` queda vacío → PASS.
2. **Archivo ausente** — `load_open_reviews()` devuelve `[]` si `REVIEWS_C2` no existe
   (`:108-109`); `estados = {}` → PASS emitiendo *"reviews no cerrables intactas=3/3"*
   sin haber leído nada.

**impact** La leyenda "3/3" se emite igual con 0 filas leídas. Es el mismo modo de falla de
F-003 alcanzado por otra puerta. Materialidad hoy nula (el CSV existe y tiene `status`).

**required_action** Aserción explícita: si `reviews` está vacío **o** ninguna clave de estado
conocida aparece en el encabezado → `FAIL` con motivo, nunca PASS.

**acceptance_test** Renombrar `status` en una copia del CSV ⇒ `FAIL`. Apuntar `REVIEWS_C2` a
una ruta inexistente ⇒ `FAIL`.

---

## F-008 · El RAW crece sin techo; el residual de F-004

| | |
|---|---|
| **severity** | MEDIUM · **workstream** CNV · **owner** CLAUDE 3 · **status** OPEN |
| **component** | `engine/cnv/rawstore.py` (direccionamiento por sha crudo) |

**description** La canonicalización resolvió la *detección* de cambios, no el
*almacenamiento*. Cada rerun reescribe los 75 artefactos con sha crudo distinto.

**evidence**
```
data/raw/engine/cnv    AUDIT-01: 152 archivos
                       AUDIT-02: 377 archivos · 51 MB
                       (3 corridas nuevas × 75 = 225)

fetch_raw.cnv_download_log — 6 corridas × 75 filas, 75 sha crudos distintos c/u
   3 primeras: canonical_sha256 NULL   (previas al fix)
   3 últimas : canonical_sha256 75/75  (posteriores)
```
El propio reporte lo declara: *"escrituras RAW nuevas=75 de todos modos"*.

**impact** Un CUIT ≈ 17 MB por corrida. Extrapolado a `FINANCIERO`/`TODO` sobre cientos de
empresas y reruns periódicos, el crecimiento es lineal y sin política de retención. No afecta
corrección; afecta operabilidad a escala.

**required_action** Decidir política: (a) direccionar el RAW por hash canónico conservando
una copia cruda por artefacto; (b) retención por antigüedad; (c) aceptar el crecimiento y
dimensionarlo explícitamente. **El auditor no elige.**

**acceptance_test** Tres reruns consecutivos del mismo CUIT sin cambios sustantivos no deben
aumentar el conteo de archivos en más de un margen declarado y justificado.

---

## F-009 · Cinco corridas de S03 sin estado terminal

| | |
|---|---|
| **severity** | MEDIUM · **workstream** SEC · **owner** CLAUDE 1 · **status** OPEN |
| **component** | `engine.stage_runs` / manejo de aborto en `scripts/engine/s03_parse_ypf.py` |

**description** De 8 `run_id` distintos de `S03_parse`, sólo 3 alcanzaron estado terminal.
Cinco quedaron detenidos en `RUNNING`, **sin `FAILED`**.

**evidence**
```
e004ed88…  READY -> RUNNING                                          24-ago 21:37
e65a3c6a…  READY -> RUNNING                                          25-ago 04:13
eccd5fb3…  READY -> RUNNING                                          25-ago 04:17
b4a2b220…  READY -> RUNNING                                          25-ago 04:26
973b7e9e…  READY -> RUNNING                                          25-ago 04:36
a1a37b19…  READY -> RUNNING -> VALIDATING -> PASSED -> CHECKPOINTED   25-ago 04:47
f8b8c389…  READY -> RUNNING -> VALIDATING -> PASSED -> CHECKPOINTED   25-ago 13:41
971ce5d9…  READY -> RUNNING -> VALIDATING -> PASSED -> CHECKPOINTED   25-ago 13:56
```
`S00_bootstrap` y `S01_identity` **sí** registran `FAILED` (9 filas cada uno), de modo que la
máquina de estados contempla el fallo: S03 no lo está usando en el camino de aborto.

**impact** `stage_runs` no permite distinguir *"corriendo ahora"* de *"murió en silencio"*.
Cualquier lógica de reanudación, monitoreo o limpieza que lea ese estado ve 5 corridas
fantasma. Contradice **failure handling**.

**atenuante** El log documenta una de las cinco (`973b7e9e`, "commiteó y crasheó después"),
y su comparación de determinismo se apoya justamente en ella. Las otras cuatro no están
explicadas.

**acceptance_test** Abortar S03 deliberadamente (p. ej. `KeyboardInterrupt` tras `RUNNING`)
debe dejar la corrida en `FAILED` con motivo, no en `RUNNING`.

---

## F-010 · `created_at` del checkpoint C3 no se actualiza en el reuse

| | |
|---|---|
| **severity** | LOW · **workstream** CNV · **owner** CLAUDE 3 · **status** OPEN |
| **component** | upsert de `engine.checkpoints` en `c3_cnv_fetch.py` |

**evidence**
```
checkpoint_id : 8db8692ebce9439c8be69cbaf5c82979   (original de AUDIT-01)
run_id        : eb05375b34434923a69cf34a59591c5c   (corrida run6, ~13:52 UTC)
created_at    : 2026-08-25 04:29:01                (fecha de la corrida ORIGINAL)
```

**description** El reuse actualiza `run_id` pero conserva `created_at`. La fila afirma
haberse creado a las 04:29 mientras referencia una corrida iniciada nueve horas después.

**impact** Bajo, pero es semántica de checkpoint: `created_at` deja de ser utilizable para
fechar el contenido vigente. Quien audite por antigüedad se orientará mal. Debe leerse
`run_id` y cruzarlo contra `stage_runs`.

**required_action** Definir la semántica: si el checkpoint es reusable, agregar `updated_at`;
si debe reflejar la corrida vigente, actualizar `created_at` en el `DO UPDATE`.

---

# Afirmaciones verificadas en AUDIT-02

| Afirmación | WS | Resultado |
|---|---|---|
| 146.028 link_relations | SEC | **EXACTO** |
| 67.084 facts · 23.478 contexts · 369 units | SEC | **EXACTO** los tres |
| 18/18 tests S03 | SEC | **VERIFICADO** — corrida propia, `18 passed in 1.72s` |
| Fix `ON CONFLICT` sobre `engine.checkpoints` | SEC | **VERIFICADO** — índice único `ux_checkpoints_reuse` sobre las 4 columnas |
| S03 gate PASS | SEC | **VERIFICADO** — 9/9 checks, `verdict: READY_FOR_S04` |
| Encadenamiento a S02 | SEC | **VERIFICADO** — `input_checkpoint.run_id = 33d234463f…` |
| 1 sola fila de checkpoint S03 | SEC | **VERIFICADO** — sin duplicar |
| `parse_errors = 0` | SEC | **VERIFICADO** |
| "4 ejecuciones completas deterministas" | SEC | **IMPRECISO** — 3 CHECKPOINTED + 1 commiteada-y-crasheada; 8 iniciadas. Ver F-009 |
| `canonical_sha256` implementado y acotado | CNV | **VERIFICADO** — 2 regex, 2 kinds, no toca el RAW |
| RAW conservado intacto | CNV | **VERIFICADO** — 0/75 con `CANON` escrito; 74/75 con token real |
| C-C3-006 corregido | CNV | **VERIFICADO** — 75/75 idénticos en sustancia, 0 cambios reales |
| C-C3-007 corregido | CNV | **PARCIAL** — detecta el cierre (esc. 2) pero admite PASS vacuo (F-007) |
| 8 tests agregados | CNV | **VERIFICADO** — 8 passed; cubren canonicalización y perímetro, **no** C-C3-007 |
| 3 ejecuciones reales adicionales | CNV | **VERIFICADO** — `39d072db`, `74c2e4f3`, `eb05375b` |
| PASS 10/10 | CNV | **VERIFICADO** — run6 |
| Idempotencia 75/75 | CNV | **VERIFICADO en sustancia**, no en bytes (F-008) |
| Checkpoint original reutilizado | CNV | **VERIFICADO** — con salvedad de `created_at` (F-010) |
| M22 sigue PASS_WITH_WARNINGS | MARKET | **VERIFICADO** — checkpoint intacto, gates 29/6 |
| `m6_scale.py` existe | MARKET | **VERIFICADO** — 197 líneas |
| M23 **no** ejecutado | MARKET | **VERIFICADO** — 2 instrumentos, última corrida 04:27:40 |

---

# Correcciones del propio auditor — AUDIT-02

Registradas porque un auditor que oculta sus errores no es auditable. **Tres sospechas
propias resultaron infundadas y se descartaron antes de emitir finding:**

1. **Artefactos de S03 con fecha ~3 h anterior al checkpoint.** Parecía evidencia
   desalineada. Era diferencia de zona horaria: la base corre en `Etc/UTC` (14:08) y el
   filesystem en local UTC−3 (11:08). Confirmado consultando `current_setting('TIMEZONE')`.
   Además, `S03_MANIFEST.json` y `S03_VALIDATION.json` **sí** declaran el `run_id`
   checkpointeado. Sin discrepancia.
2. **`ON CONFLICT` sobre columnas sin constraint.** `pg_constraint` sólo mostraba la PK, lo
   que en PostgreSQL haría fallar la sentencia. Existe el **índice único**
   `ux_checkpoints_reuse` sobre las cuatro columnas, y un índice único satisface
   `ON CONFLICT`. `pg_constraint` no lista índices que no respalden una constraint formal.
   El fix es real.
3. **`EMPRESA_PAGE` no converge bajo canonicalización.** Parecía fix incompleto. El diff
   mostró 198 líneas de contenido genuinamente nuevo (una presentación publicada por CNV
   entre capturas). La no-convergencia es **el comportamiento correcto**, y terminó siendo
   la mejor prueba de que la canonicalización no enmascara cambios reales.

En AUDIT-01 hubo dos correcciones equivalentes (`manifest_sha256` de Market, y la lectura
de que `engine-dev`@5433 estaba vacío por consultar sólo el esquema `public`).

---

# NUEVOS FINDINGS — AUDIT-02 (transversales)

## F-011 · No existe tipo `CUIT` en el modelo de identidad

| | |
|---|---|
| **severity** | **HIGH** · **workstream** GLOBAL · **owner** ARCHITECTURE · **status** OPEN |
| **component** | `identity.entities`, `identity.identifiers` @5433 |

**description** El modelo canónico de identidad no representa CUITs.
`identity.identifiers` admite `CIK` (7998), `TICKER` (10414) y `YF_SYMBOL` (10414);
`identity.entities.cuit` está poblado en **0 de 7998** filas. La única asociación
CUIT↔CIK vive dentro de `fetch_raw.cnv_download_log` (columnas `entity_key`+`cuit`) y en
el `dim_entity` del SQLite legacy.

**evidence**
```
SELECT id_type, COUNT(*) FROM identity.identifiers GROUP BY 1
   -> YF_SYMBOL 10414 · TICKER 10414 · CIK 7998        (no hay CUIT)

SELECT COUNT(*) FROM identity.entities WHERE cuit IS NOT NULL   -> 0

fetch_raw.cnv_download_log   entity_key='CIK:0001717161'  cuit='33650305499'
identity.entities            CIK:0001717161 | CENTRAL PUERTO S.A. | cuit=NULL
```

**impact** Preguntarle al modelo canónico "¿cuál es el CUIT de esta entidad?" devuelve NULL
para las 7998. Una capa económica que deba unir hechos SEC con documentos CNV no tiene
dónde apoyarse: el puente existe en los datos pero no en el contrato.

**required_action** Decidir si `CUIT` pasa a ser un `id_type` de primera clase o si la
asociación se declara en otro artefacto explícito. **El auditor no elige.**

**acceptance_test** Dada una entidad con presentaciones CNV, resolver su CUIT consultando
únicamente el esquema `identity`.

---

## F-012 · Los reportes atribuyen su código a un commit que ya no describe el árbol

| | |
|---|---|
| **severity** | MEDIUM · **workstream** GLOBAL · **owner** ARCHITECTURE / HUMAN · **status** OPEN |

**description** Los tres workstreams registran `git_commit = 444ee1ad0e…` en sus reportes
(`S03_VALIDATION.json`, `S03_MANIFEST.json`, `C3_CNV_STAGE_REPORT_*`). `HEAD` sigue en
`444ee1a`, pero **todo el trabajo de este ciclo está sin commitear**: `m6_scale.py` (nuevo),
`rawstore.py`, `c3_cnv_fetch.py`, `s03_parse_ypf.py` fueron modificados después del baseline.

**evidence**
```
git log --oneline -1            -> 444ee1a
scripts/market/m6_scale.py       2026-08-25 10:41   (nuevo, sin commitear)
engine/cnv/rawstore.py           2026-08-25 10:44
scripts/engine/c3_cnv_fetch.py   2026-08-25 10:49
scripts/engine/s03_parse_ypf.py  2026-08-25 10:55
```

**impact** `git_commit` deja de identificar el código que produjo la evidencia — que es
justamente su función. Dos corridas con el mismo `git_commit` declarado pueden haberse
ejecutado con código distinto. Compromete la reproducibilidad declarada, no la observada.

**required_action** Commitear el trabajo verificado, o registrar en los reportes un
identificador que distinga árbol-sucio de commit (p. ej. `git describe --dirty` o hash del
árbol).

**acceptance_test** Dos reportes con el mismo `git_commit` deben corresponder a código
idéntico.

---

## F-013 · Tres convenciones divergentes de checkpoint

| | |
|---|---|
| **severity** | MEDIUM · **workstream** GLOBAL · **owner** ARCHITECTURE · **status** OPEN |

**description**
```
SEC     '971ce5d999a2499b-s03'                  derivado del run ganador · en engine.checkpoints
CNV     '8db8692ebce9439c8be69cbaf5c82979'      ID original reusado · created_at congelado
MARKET  'MKT-GOLDEN-20260825-89c2f00f26c0'      con state_digest propio · FUERA de engine.checkpoints
```

**impact** "Checkpoint" no significa lo mismo en las tres capas: difieren en cómo se deriva
el ID, si se reusa o se emite uno nuevo, si `created_at` sigue a la corrida vigente, y si
vive en el registro central. Un consumidor de capa canónica no puede tratarlo como una
unidad de confianza uniforme.

**required_action** Definir el contrato de checkpoint del programa y alinear las tres capas,
o documentar explícitamente que son artefactos distintos con el mismo nombre.

**acceptance_test** Un consumidor debe poder listar el checkpoint vigente de las tres capas
con una sola consulta y obtener semántica equivalente.

---

## F-014 · `market_instruments.ticker_canonico` repite el ticker local en la fila del ADR

| | |
|---|---|
| **severity** | MEDIUM · **workstream** MARKET · **status** OPEN · **detectado en** CICLO 4 (Identity v1) |

**description**
```
instrument_id | entity_id | ticker_canonico | instrument_type | exchange | ticker_yahoo
           83 |        72 | YPFD            | LOCAL           | BUE      | YPFD.BA
           84 |        72 | YPFD            | ADR             | NYSE     | YPF
           65 |        62 | TGSU2           | LOCAL           | BUE      | TGSU2.BA
           66 |        62 | TGSU2           | ADR             | NYSE     | TGS
```
La fila del ADR lleva el ticker de BYMA en `ticker_canonico`. `YPFD` no cotiza en NYSE;
el símbolo de NYSE es `YPF`. Lo mismo con `TGSU2` vs `TGS`. El único lugar donde vive el
símbolo real del mercado extranjero es `market_symbol_mappings.ticker_yahoo`, que es un
campo del proveedor de datos, no del mercado.

**evidencia** `catalaxia-db`@5432, `SELECT instrument_id, ticker_canonico, exchange FROM
market_instruments WHERE entity_id IN ('72','62','70','65')` — verificado 2026-08-25.

**impact** Cualquier consumidor que tome `ticker_canonico` como el símbolo del instrumento
publica un símbolo falso para los ADR. El piloto de Identity v1 lo hizo en su primera
versión y escribió `US/YPFD` y `US/TGSU2`; lo detectó el banco adversario, no un test
unitario. CEPU y GGAL enmascaran el problema porque su ticker local y su ticker de NYSE
coinciden — con esos dos solos el bug es invisible.

**required_action** Decidir la semántica de `ticker_canonico` para instrumentos no-BUE:
o pasa a ser el símbolo del exchange de la fila, o se documenta que es la clave del
emisor local y se agrega un campo con el símbolo del mercado. No se toca el fetcher de
Market en el ciclo 4 (fuera de alcance).

**mitigación aplicada** `scripts/engine/identity_v1_pilot.py` ya no deriva símbolo de
`ticker_canonico` para instrumentos no-BUE: escribe solo el símbolo `YAHOO`, que Market sí
respalda, y abre una review por instrumento declarando la carencia (reviews #1, #2, #4, #5
del piloto).

**acceptance_test** Para todo instrumento con `exchange <> 'BUE'`, el símbolo publicado en
el namespace de ese exchange debe provenir de un campo que la fuente declare como el
símbolo de ese mercado, no de `ticker_canonico`.

---
---

# CICLO 5 — AUDITORÍA INDEPENDIENTE DE IDENTITY V1

## F-015 · Una assertion VIGENTE puede reescribirse sin dejar historia

| | |
|---|---|
| **severity** | **HIGH** · **component** `identity_v1.assertion` / `tg_assertion_inmutable` · **owner** IDENTITY · **status** OPEN |

**evidence** `docs/review/identity_v1_audit.sql`, ataques 13a / 13b / 09c — todos ACEPTADOS:
```
13a  UPDATE assertion SET evidence='evidencia reescrita por el atacante'
      WHERE status='VERIFIED' AND valid_to IS NULL                        -> ACEPTADO
13b  UPDATE assertion SET entity_key=<CEPU> WHERE ... (era de YPF)        -> ACEPTADO
09c  UPDATE assertion SET status='VERIFIED', confidence='AUTHORITATIVE'
      WHERE status='REVIEW_REQUIRED' AND valid_to IS NULL                 -> ACEPTADO
```
`pg_proc.prosrc` de `fn_assertion_inmutable` confirma la causa: la guarda es
`IF OLD.valid_to IS NOT NULL OR OLD.status = 'REJECTED'`. Las filas **vigentes** —que son
todas las que sostienen la identidad en producción— quedan fuera del trigger.

**impact** Invalida la garantía central que `IDENTITY_V1_SCHEMA.md` §4 declara: *"No existe
en identity_v1 un identificador autoritativo sin una cita textual reproducible por un tercero
y sin un responsable nombrado."* La cita puede reemplazarse por cualquier texto, la assertion
puede reapuntarse a otra entidad y un `REVIEW_REQUIRED` puede promoverse a `VERIFIED` sin
revisor, sin conflicto y sin rastro. `ck_verified_exige_evidencia` sólo verifica que los
campos **no sean NULL**, no que digan la verdad.

**required_action** Extender la inmutabilidad a las filas vigentes: sobre una assertion con
`valid_to IS NULL`, prohibir el cambio de `evidence`, `entity_key`, `left_ref`, `right_ref`,
`source_id`, `source_record`, `method`, `confidence` y `status`. El único cambio admisible es
cerrarla (`valid_to`) y encadenarla (`superseded_by`). Corregir una assertion debe ser
supersedencia, nunca edición.

**acceptance_test** Los tres UPDATE de arriba deben devolver error. Reproducible con
`docs/review/identity_v1_audit.sql` (ataques 13a, 13b, 09c): los tres deben pasar de
`[HUECO]` a `[OK]`.

---

## F-016 · El piloto atribuye a una persona nombrada una decisión humana que nunca ocurrió

| | |
|---|---|
| **severity** | **HIGH** · **component** `scripts/engine/identity_v1_pilot.py` · **owner** IDENTITY · **status** OPEN |

**evidence** Los 4 bridges `CIK↔LEI` del piloto:
```
method            | HUMAN_DECISION
confidence        | STRONG
resolved_by       | fmonfasani
resolution_reason | cierre manual de la arista CIK<->LEI (ciclo G5)
valid_from        | 2026-08-25 20:20:17.821262+00   <- idéntico en los 4
evidence          | GLEIF .../lei-records/<LEI> · legalName=... registeredAt=... registeredAs=...
```
`resolved_by="fmonfasani"` está **hardcodeado en el script** y se escribe en bucle para los
cuatro emisores, con el mismo motivo y el mismo microsegundo. Ninguna persona intervino.

Segundo defecto, independiente: la `evidence` cita **sólo el registro GLEIF** (el lado LEI).
No contiene nada del lado CIK, de modo que **no demuestra el puente**: afirma la
correspondencia sin respaldarla. El ciclo G5 concluyó `CIK_LEI_PRIMARY_BRIDGE = NOT_AVAILABLE`
precisamente porque esa demostración no existe en ninguna fuente.

**impact** El sistema construido para no fabricar identidad **fabrica la autoría de la
decisión**, en el golden case y sobre una persona real. Un auditor externo que siga la
procedencia de YPF llega a un nombre propio que no ratificó nada. Es un daño peor que el dato
faltante: un `REVIEW_REQUIRED` se ve; una firma falsa no.

**required_action** Dos caminos, ambos aceptables:
(a) una persona ratifica cada bridge con evidencia propia de **ambos** lados y se registra
esa ratificación; o
(b) los 4 bridges se degradan a `REVIEW_REQUIRED` y `resolved_by` pasa a identificar al
proceso (`proc:identity_v1_pilot`), nunca a una persona. Además, prohibir que un proceso
automático escriba `method='HUMAN_DECISION'`.

**acceptance_test** `SELECT count(*) FROM identity_v1.assertion WHERE method='HUMAN_DECISION'
AND resolved_by NOT LIKE 'proc:%'` sólo debe devolver filas cuya `evidence` cite documentos de
los dos extremos del puente y cuyo `valid_from` no coincida al microsegundo con otras filas
del mismo lote.

---

## F-017 · Procedencia histórica y gobernanza son borrables sin rastro

| | |
|---|---|
| **severity** | **HIGH** · **component** `identity_v1` (política de DELETE) · **owner** IDENTITY · **status** OPEN |

**evidence** `identity_v1_audit.sql` (12c, 12d, 12e) y `identity_v1_audit_pass2.sql` (P2-08):
```
12c  DELETE FROM assertion WHERE status='REVIEW_REQUIRED' AND valid_to IS NULL  -> ACEPTADO
12d  DELETE FROM review    WHERE status='OPEN'                                  -> ACEPTADO
12e  DELETE FROM conflict  WHERE state='OPEN'                                   -> ACEPTADO
P2-08 DELETE FROM assertion WHERE assertion_id=<histórica, superseded>          -> ACEPTADO
```
`fn_no_borrar_vigente` sólo bloquea `valid_to IS NULL AND status IN ('VERIFIED','CANDIDATE')`.
Queda fuera: toda la historia cerrada, las assertions en revisión y las tablas `review` y
`conflict`, que no tienen trigger alguno.

Nota de método: la pasada 1 reportó también 12b y 13c como huecos usando un CTE que cerraba y
borraba en la misma sentencia. Eso era un **falso positivo del banco de ataque** (ambas ramas
del CTE ven el mismo snapshot). Rehecho con sentencias separadas: **13c está correctamente
bloqueado**; 12b/P2-08 se confirma como hueco real.

**impact** Se puede hacer desaparecer un conflicto abierto, una review abierta y la cadena
histórica completa de una entidad. Un sistema cuya propuesta de valor es la auditabilidad
permite borrar la auditoría. Combinado con F-015, un actor puede reescribir el presente y
eliminar el pasado que lo contradice.

**required_action** `DELETE` prohibido sobre `assertion` en cualquier estado —la corrección es
supersedencia—, y sobre `review` y `conflict` una vez creados. Si hace falta descartar algo,
que sea un estado terminal (`REJECTED`, `ACCEPTED_AMBIGUOUS`), no un `DELETE`.

**acceptance_test** Los cuatro DELETE de arriba deben devolver error, y también el borrado de
una assertion `REJECTED`.

---

## F-018 · Sin validación de formato ni checksum en la base para CIK / CUIT / LEI

| | |
|---|---|
| **severity** | MEDIUM · **component** `identity_v1.identifier` · **owner** IDENTITY · **status** OPEN |

**evidence** `identity_v1_audit_pass2.sql`, sobre una entidad limpia — **los 6 ACEPTADOS**:
```
P2-01  CIK  = 'YPF'              P2-04  CUIT = '99999999999'  (checksum inválido)
P2-02  CIK  = '42'               P2-05  LEI  = 'no-es-un-lei'
P2-03  CUIT = 'no-soy-un-cuit'   P2-06  CUIT = '30-54668997-9' (con guiones)
```
Ninguna columna de `identity_v1.identifier` tiene CHECK de formato. `norm_cik`, `norm_cuit`,
`norm_lei` y `cuit_valido` existen **sólo en `engine/identity_v1.py`**.

**impact** Contradice `IDENTITY_V1_IMPLEMENTATION.md`, que presenta el módulo 11 como una
garantía del sistema. Es una garantía de la aplicación: cualquier escritura desde psql, otro
proceso o un backfill que no pase por la capa Python inyecta identificadores basura. P2-06 es
el más peligroso: `'30546689979'` y `'30-54668997-9'` conviven como **dos identificadores
autoritativos distintos**, partiendo la identidad en dos sin disparar
`ux_identifier_autoritativo_unico`. F-024 muestra que este caso ya existe en los datos de origen.

**required_action** Llevar normalización y validación al schema: CHECK de formato por
`id_type` (CIK `^[0-9]{10}$`, CUIT `^[0-9]{11}$` + módulo 11, LEI `^[0-9A-Z]{18}[0-9]{2}$`),
o una columna generada normalizada sobre la que se construya el índice único.

**acceptance_test** Los 6 INSERT de arriba deben devolver error, y `'30-54668997-9'` debe
colisionar con `'30546689979'` en `ux_identifier_autoritativo_unico`.

---

## F-019 · Una review ABIERTA no bloquea la escritura del identificador que gobierna

| | |
|---|---|
| **severity** | MEDIUM · **component** review workflow · **owner** IDENTITY · **status** OPEN |

**evidence** `identity_v1_audit.sql`, ataque 09b — ACEPTADO. Con la review #3 de GGAL abierta
(*"GLEIF no permite derivar CUIT: RA999999 no asigna CUIT"*), se escribió el CUIT autoritativo
`30704962807` para GGAL mediante un INSERT directo. La review siguió `OPEN` y el identificador
quedó `is_authoritative = true`.

**impact** `ck_cierre_exige_reviewer` protege el **cierre** de la review, pero nada vincula la
review con el identificador que la motiva. El flujo de revisión es una convención de la capa
Python, no un control. Cualquier escritura que no pase por `resolve_review()` lo saltea.

**required_action** Vincular `review` con el identificador en disputa (FK o clave lógica
`id_type`+`id_namespace`+`entity_key`) y bloquear por trigger la escritura de un identificador
autoritativo mientras exista una review `OPEN` que lo cubra.

**acceptance_test** Con la review #3 abierta, el INSERT del ataque 09b debe devolver error;
tras cerrarla con `resolve_review()`, debe funcionar.

---

## F-020 · D-I-04 está planteada sobre un conteo equivocado y omite el riesgo real

| | |
|---|---|
| **severity** | MEDIUM · **component** `IDENTITY_V1_MIGRATION_PLAN.md` §Fase 2 · **owner** ARCHITECTURE · **status** OPEN |

**evidence** El plan afirma: *"el backfill produciría del orden de **8.000 REVIEW_REQUIRED**
por el puente CIK↔LEI"*. Población real medida:
```
dim_entity (573)      total  con_CUIT  con_CIK  con_AMBOS
  adr                    18        18       13        13   <- únicas que necesitan puente
  byma_only              56        56        0         0   <- sin CIK: no hay puente que hacer
  sp500                 499         0      499         0   <- el CUIT no aplica
identity.entities   : 7.998 con CIK · 0 con CUIT · LEI: 0 identificadores en todo el catálogo
```
El puente sólo se exige cuando la entidad tiene CIK autoritativo **y** se busca su CUIT:
**13 entidades**, no ~8.000. Error de ~615x.

Riesgo real, no evaluado en el plan:
```
CIK en identity.entities (PostgreSQL) : 7.998
CIK en dim_entity        (SQLite)     :   512
SOLAPAMIENTO                          :   510
```

**impact** La decisión D-I-04 se presenta como bloqueante de la Fase 2 sobre una magnitud
inexistente, mientras el problema que sí escala —510 entidades presentes en ambas fuentes, que
migradas por separado producen 510 conflictos de CIK duplicado, incluidas las 13 que llevan el
CUIT— no tiene regla de fusión definida.

**required_action** Re-presentar D-I-04 sobre la población real y agregar al plan la regla de
fusión `identity.entities` ↔ `dim_entity` para los 510 solapamientos, con su criterio de
resolución de conflictos. La regla propuesta (*LEI opcional para US + CUIT sólo para
argentinos + LEI como puente sólo donde corresponde*) **es consistente con la arquitectura** y
puede adoptarse; simplemente no era el cuello de botella.

**acceptance_test** Un dry-run del backfill sobre las 573 + 7.998 entidades que reporte:
número de entidades creadas, de fusiones, de conflictos y de reviews abiertas — y que las
reviews por puente CIK↔LEI sean <= 18.

---

## F-021 · `instrument.assertion_id` es nullable: instrumentos sin procedencia

| | |
|---|---|
| **severity** | MEDIUM · **component** `identity_v1.instrument` · **owner** IDENTITY · **status** OPEN |

**evidence** Ataque E1 — ACEPTADO: `INSERT INTO identity_v1.instrument (instrument_key,
entity_key, instrument_type, exchange, currency) VALUES ('AUDIT:X', <YPF>, 'EQUITY','BUE','ARS')`.
`information_schema`: `instrument.assertion_id … is_nullable = YES`, frente a
`identifier.assertion_id … is_nullable = NO`. Los 8 instrumentos del piloto tienen
`assertion_id IS NULL`.

**impact** El diseño hace obligatoria la procedencia para identificadores pero no para
instrumentos. Afirmar *"este instrumento pertenece a esta entidad"* es una afirmación de
identidad tan fuerte como cualquier otra —es la que conecta un precio con un emisor— y hoy
entra sin fuente, sin cita y sin autor.

**required_action** `assertion_id NOT NULL` en `instrument`, y backfill de las 8 filas del
piloto con la assertion que las respalde.

**acceptance_test** El INSERT de E1 debe devolver error, y
`SELECT count(*) FROM identity_v1.instrument WHERE assertion_id IS NULL` debe dar 0.

---

## F-022 · `superseded_by` auto-referenciable y `valid_to` retro-fechable

| | |
|---|---|
| **severity** | LOW · **component** `identity_v1.assertion` · **owner** IDENTITY · **status** OPEN |

**evidence** `identity_v1_audit_pass2.sql`:
```
P2-10  UPDATE assertion SET superseded_by = assertion_id WHERE ...   -> ACEPTADO
P2-11  UPDATE assertion SET valid_to = '1900-01-01' WHERE ...        -> ACEPTADO
```

**impact** P2-10 permite un ciclo en la cadena de sucesión: un recorrido de historia
—exactamente lo que un auditor haría— entra en bucle infinito. P2-11 permite antedatar el
cierre de una assertion, alterando qué era cierto en una fecha dada; combinado con F-015
habilita reescribir la línea de tiempo.

**required_action** `CHECK (superseded_by <> assertion_id)` y `CHECK (valid_to IS NULL OR
valid_to >= valid_from)`.

**acceptance_test** Ambos UPDATE deben devolver error.

---

## F-023 · El piloto de Identity v1 no es idempotente ni reproducible

| | |
|---|---|
| **severity** | MEDIUM · **component** `scripts/engine/identity_v1_pilot.py` · **owner** IDENTITY · **status** OPEN |

**evidence**
```
entity_key de YPF, corrida 1 : E01M0X94S5BGQFKYV1BY9TG6B49
entity_key de YPF, corrida 2 : E01M0X99C8F87H9TH9N39H2D1NW
re-ejecución sin --reset     : IntegrityError: duplicate key ... "instrument_pkey" ... (MKT:83)
```
Verificado además que la corrida fallida **revirtió limpio** (4/16/12, 0 entidades sin
identificador): la transacción está bien delimitada. El defecto es de diseño, no de manejo de
errores.

**impact** Dos consecuencias. (1) `new_entity_key()` usa `secrets.token_bytes`, así que la
clave primaria de cada entidad cambia en cada corrida: **no puede construirse un
`state_digest` estable sobre `identity_v1`**, lo que choca con F-013 (semántica de checkpoint)
y hace que "el piloto" no sea un artefacto verificable, sino uno distinto cada vez. (2) La
única forma de re-ejecutar es `--reset`, que destruye las decisiones humanas ya registradas —
inaceptable una vez que haya reviews resueltas de verdad.

**required_action** Hacer el piloto idempotente: buscar la entidad por su identificador
autoritativo antes de crearla, y usar `ON CONFLICT DO NOTHING` en instrumentos y símbolos. La
opacidad de `entity_key` (D-I-B) es correcta y debe conservarse; lo que hace falta es
**resolver antes de crear**, no derivar la clave del CIK.

**acceptance_test** Ejecutar el piloto dos veces seguidas sin `--reset` debe terminar sin
error y dejar 4 entidades, los mismos `entity_key` y el mismo número de assertions.

---

## F-024 · `dim_entity` tiene un CIK guardado en la columna `cuit`

| | |
|---|---|
| **severity** | **HIGH** · **component** `dim_entity` (SQLite legacy) · **owner** DATA / SCREENER · **status** OPEN |

**evidence**
```sql
SELECT * FROM dim_entity WHERE entity_id='572';
-- entity_id=572  ticker_canonico='BMA'  grupo='adr'
-- cuit='0001347426'   <- 10 dígitos, zero-padded: es un CIK
-- cik=NULL
```
Es el único de los 74 CUIT del catálogo legacy que falla el dígito verificador (módulo 11).
Los otros 73 son válidos y no hay CUIT ni CIK duplicados en `dim_entity`.

**impact** Banco Macro tiene su identificador en el campo equivocado: un CIK ocupando el lugar
del CUIT, y el CUIT real ausente. Es exactamente el error de categoría que Identity v1 existe
para impedir, presente **en los datos que la Fase 2 importaría**. Combinado con F-018 (sin
validación en la base), entraría como CUIT autoritativo de BMA si la fuente se declarara
autoritativa, y quedaría además indisponible como CIK.

**required_action** Corregir la fila en origen: mover `0001347426` a `cik` y obtener el CUIT
real de Banco Macro por fuente autoritativa (GLEIF `registeredAt` ∈ {RA000009, RA000010}, o
AFIP). Hasta entonces, el backfill debe marcar la entidad `REVIEW_REQUIRED` y no importar el
valor.

**acceptance_test** Un validador previo al backfill que rechace toda fila de `dim_entity`
cuyo `cuit` no pase el módulo 11, y que reporte 0 filas sobre el catálogo corregido.


---
---

# CICLO 6 — CIERRES Y RECTIFICACIONES

## Cerrados contra su acceptance_test (verificado 2026-08-26)

| ID | Prueba que lo cierra (`docs/review/identity_v1_audit_pass3.sql`) |
|---|---|
| **F-015** | D1-D4: reescribir `evidence`, reapuntar `entity_key`, promover `REVIEW_REQUIRED->VERIFIED`, cambiar `source_id` sobre assertion VIGENTE -> los 4 rechazados por `tg_assertion_inmutable` |
| **F-016** | C1: `resolved_by='proc:...'` con `method='HUMAN_DECISION'` -> rechazado por `ck_humano_no_es_proceso`. `SELECT count(*) ... method='HUMAN_DECISION'` = **0** |
| **F-017** | E1-E7: borrar assertion vigente/historica/`REVIEW_REQUIRED`, review abierta, identifier vigente, conflict abierto (con blanco sembrado) y `TRUNCATE` -> los 7 rechazados |
| **F-018** | B1-B5: CUIT checksum roto, CUIT con guiones, `CIK='YPF'`, `CIK='42'`, `LEI='no-es-un-lei'` -> los 5 rechazados por `ck_formato_identificador` |
| **F-021** | F1: instrumento sin assertion -> rechazado (`assertion_id NOT NULL`, migracion 010) |
| **F-022** | D7/D8: re-fechar el cierre y `superseded_by` auto-referencia -> rechazados |
| **F-023** | 3 corridas seguidas del piloto: `ent=4 assert=33 ident=12 rev=13 sym=12` identico, mismos `entity_key` |

Migraciones: `009_identity_v1_hardening.sql`, `010_identity_v1_instrument_provenance.sql`.
Guardas desplegadas: 13 CHECK `ck_*` + 11 triggers (antes 9 + 3). Suite: `38 passed`.

---

## RECTIFICACION · F-017, parte referida a `conflict`: hallazgo FALSO en el ciclo 5

El ataque 12e del ciclo 5 (*"borrar un conflict abierto"*) se reporto `[HUECO]` **con la
tabla `identity_v1.conflict` vacia**. Un `DELETE` que no matchea ninguna fila no lanza
excepcion, y el arnes lo contaba como aceptado. **Ese ataque nunca probo nada.**

Defecto de mi propio banco de ataque, no del sistema auditado. La pasada 3 lo corrige
exigiendo blanco real: si un ataque toca cero filas se reporta `[NULO]`. Verificado ahora
con un conflicto sembrado a proposito (E6): el `DELETE` es rechazado.

Las otras tres partes de F-017 (assertion historica, assertion `REVIEW_REQUIRED`, review
abierta) si tenian blanco real y eran hallazgos validos.

---

## F-025 · El engine conecta como superusuario y puede desactivar los triggers

| | |
|---|---|
| **severity** | MEDIUM · **component** rol de conexion / `engine/config.py` · **owner** INFRA · **status** OPEN |

**evidence**
```
SELECT rolsuper FROM pg_roles WHERE rolname = current_user;   -->  t

BEGIN; SET LOCAL session_replication_role = replica;
DELETE FROM identity_v1.assertion WHERE assertion_id = (SELECT min(assertion_id) ...);
-->  DELETE 1        (aceptado: los triggers no corrieron)
```

**impact** Las garantias de F-015 (inmutabilidad) y F-017 (no se borra) son **triggers**. Un
superusuario los desactiva con una sentencia. Mientras el engine se conecte como
`catalaxia` (superusuario), las garantias recien certificadas son revocables por accidente:
alcanza con un script que copie el patron de limpieza de los tests.

No se arregla con mas constraints — los CHECK si sobreviven a `session_replication_role`,
pero la inmutabilidad y la prohibicion de borrado no pueden expresarse como CHECK.

**required_action** Crear un rol `catalaxia_engine` sin `SUPERUSER`, con
`SELECT/INSERT/UPDATE` sobre `identity_v1` y **sin** `TRUNCATE`, y apuntar el engine ahi.
Reservar el rol superusuario para migraciones y para el arnes de tests.

**acceptance_test** Con el rol del engine: `SET session_replication_role = replica` debe
fallar con *permission denied*, y el `DELETE` de arriba debe seguir siendo rechazado por el
trigger.


---
---

# CICLO 7 — CIERRE DE F-025 Y F-001

## F-025 · CERRADO · el engine ya no es superusuario

**Migracion** `011_rol_engine_sin_superuser.sql`. Rol `catalaxia_engine`:
`NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`, con
`SELECT/INSERT/UPDATE` en `identity_v1`, `engine`, `fetch_raw`, `parsed`, `identity`;
**sin DELETE, sin TRUNCATE, sin CREATE**. `identity_v1.source` es de solo lectura para la
aplicacion: agregar una fuente es agregar un nivel de autoridad, y eso es una decision de
arquitectura, no de runtime.

`engine/config.py` gana `admin_url`; `engine/db.py` gana `get_admin_engine()`. Migraciones y
arnes de tests usan esa via, explicitamente. La aplicacion, no.

**acceptance_test — cumplido.** Corriendo como `catalaxia_engine`:
```
SET session_replication_role = replica   -> ERROR: permission denied to set parameter
DELETE FROM identity_v1.assertion ...    -> ERROR: permission denied for table assertion
TRUNCATE identity_v1.assertion CASCADE   -> ERROR: permission denied for table assertion
INSERT INTO identity_v1.entity ...       -> OK   (la app hace su trabajo)
```

**Los 32 ataques de la pasada 3 re-ejecutados COMO EL ROL DE LA APLICACION: 32 rechazados.**
Los de la seccion E (borrado) ahora fallan por `permission denied` ANTES de llegar al
trigger: dos barreras independientes donde antes habia una.

Cubierto por `tests/test_identity_v1.py::test_13_el_rol_de_la_app_no_puede_evadir_las_guardas`,
que abre una conexion con las credenciales reales de la aplicacion —no con el fixture
administrativo— y verifica los seis caminos de escape.

---

## F-001 · CERRADO · Market no puede escribir en produccion por accidente

**Dos barreras independientes.** Cada una debe alcanzar sola.

**1 · Codigo** — `scripts/market/market_db.py`, puerta unica.
`connect()` es de SOLO LECTURA por defecto; escribir exige `write=True` en el call site y,
si el destino es 5432, ademas `MARKET_ALLOW_PROD_WRITE=1`. `exigir_dev()` aborta los jobs
masivos antes de empezar. En modo lectura la sesion se abre `readonly=True`, asi que un
INSERT falla del lado cliente.

Los 5 scripts que abrian su propia conexion (`m1`, `m2`, `m4`, `m5`, `m19`) ahora delegan.
Los 3 que escriben declaran `write=True` en el call site. `m5_golden_case` queda en solo
lectura (no tiene sentencias de escritura). `m6_scale` no tiene conexion propia: hereda la
de `m2_fetch_engine`, que es justamente la que hay que blindar.

**2 · Privilegios** — `migrations/market/012_rol_market_readonly.sql`, aplicada en 5432.
Rol `catalaxia_market_ro`: `SELECT` y nada mas, con `default_transaction_read_only = on`.
Aditivo: no revoca nada de `catalaxia`, la API y el dashboard siguen igual.

**acceptance_test — cumplido.**
```
DB_PORT=5432, sin MARKET_ALLOW_PROD_WRITE:
  market_db.connect(write=True)   -> MarketProdWriteBlocked, con la salida indicada
  market_db.exigir_dev('m6_scale')-> MarketProdWriteBlocked
Como catalaxia_market_ro contra PRODUCCION:
  INSERT INTO market_instruments  -> ERROR: cannot execute INSERT in a read-only transaction
  DELETE FROM market_price_daily  -> ERROR: cannot execute DELETE in a read-only transaction
  SELECT count(*) FROM market_price_daily -> 14979   (lee sin problemas)
```

Cubierto por `tests/test_market_prod_guard.py` (9 tests), incluido
`test_ningun_script_de_market_abre_su_propia_conexion`, que falla si alguien vuelve a poner
un `psycopg2.connect` fuera de la puerta.

**Suite completa: 48 passed.**

**Lo que sigue abierto en Market:** F-014 (`ticker_canonico` repite el ticker local en la
fila del ADR) y F-013 (semantica de checkpoint divergente). **M23 masivo NO se ejecuto.**


---
---

# CICLO 8 — F-009 CERRADO · S04 HABILITADO

## F-009 · CERRADO · toda corrida tiene estado terminal

**Auditoria previa, no cierre en bloque.** `pg_stat_activity`: 0 sesiones, ninguna corrida
viva. Las 7 en RUNNING resultaron ser **dos grupos con causas distintas**:

**Grupo A (5)** — `e004ed88`, `e65a3c6a`, `eccd5fb3`, `b4a2b220`, `973b7e9e`: traza completa
`READY | RUNNING`, ultima transicion a milisegundos del arranque, 0 checkpoints, report y
finished_at nulos, 20-27 h sin actividad. Murieron en el arranque.

**Grupo B (2)** — `f8b8c389` (S03_parse) y `39d072db` (C3_CNV_fetch): traza COMPLETA hasta
`CHECKPOINTED` con gate `PASS`, **pero report y finished_at nulos**. Hicieron el trabajo y
murieron al persistir.

**Causa raiz.** En `s03_parse_ypf.py` las transiciones `PASSED` y `CHECKPOINTED` se registran
(~620) ANTES del bloque `with engine.begin()` que persiste el report y el checkpoint (~646) y
ANTES de `finish_run` (~665). El estado de ETAPA quedo adelantado respecto del estado de
CORRIDA. Ademas sus checkpoints fueron reasignados a corridas posteriores por el
`ON CONFLICT ... DO UPDATE SET run_id = EXCLUDED.run_id`.

Se marcaron `ABORTED` y no `OK`: llegar a `CHECKPOINTED` sin persistir el report no es
completar el contrato de la etapa. **Ninguna corrida con evidencia de estar viva fue tocada
— no la habia.**

**acceptance_test — cumplido.**
```
antes : OK 8 · ABORTED 7 · BLOCKED 6 · RUNNING 7   (7 sin finished_at)
despues: OK 8 · ABORTED 14 · BLOCKED 6 · RUNNING 0  (0 sin finished_at)
```

**Prevencion de recurrencia** (`engine/db.py`):
  * `run_scope()` — cierre en `finally`; si el cuerpo explota la corrida queda `ABORTED`.
    **Obligatorio para S04 en adelante.**
  * `corridas_huerfanas()` — detecta RUNNING sin actividad cruzando `pg_stat_activity`.

`migrations/engine/013_f009_cierre_corridas_huerfanas.sql` falla si queda alguna RUNNING sin
auditar. `tests/test_engine_run_lifecycle.py` (5 tests) incluye uno que mata el cuerpo a
proposito y verifica el `ABORTED`.

---

## Cruce CNV -> Identity v1 · VALIDADO

`9.305/9.305` presentaciones (100 %) atribuidas a Central Puerto **por el CIK embebido en la
clave legacy `CIK:0001717161`, no por CUIT** — que es exactamente el acoplamiento que
Identity v1 existe para romper.

`tests/test_cnv_identity_link.py` (9 tests) valida que el cruce no mienta: toda atribucion es
`CANDIDATE`/`WEAK`/no autoritativa, `CNV_PORTAL` sigue `DISCOVERY_ONLY`, **0 bridges
VERIFIED**, **0 CUIT inventados**, 0 decisiones humanas escritas por un proceso, la via
declarada coincide con la evidencia, el resolver es idempotente y no crea entidades, y el
cruce no modifica CNV.

**Suite completa: 63 passed.**

---

## S04 · `S04_ENABLED` — con una salvedad importante

Checkpoint S03 verificado **independientemente**: se reimplemento la spec de `hash_out` desde
`s03_parse_ypf.py:637` y se recalculo contra la base actual.
```
hash_out declarado  = hash_out recalculado = 60ff8e1aecd373acd537c92770038877fc4b2ec6412add648302784a08a4652e
gate PASS 9/9 · cobertura 27/27 · 0 rechazados · 0 violaciones de provenance
corrida duena 971ce5d999a2499ba6af136cb2c87569 status OK
```

**Salvedad: S04 no existe como script.** `scripts/engine/` tiene s00..s03 y nada mas. Lo que
se habilita es el GATE, no una ejecucion. Las 6 condiciones que S04 debe cumplir al
escribirse estan en `docs/review/S04_ENABLEMENT_GATE.md` seccion 4.


---
---

# CICLO 9 — S04 IMPLEMENTADO Y CHECKPOINTED

## F-026 · S03 no extrae numerator/denominator de las unidades DIVIDED

| | |
|---|---|
| **severity** | MEDIUM · **component** `scripts/engine/s03_parse_ypf.py` · **owner** SEC · **status** OPEN |

**evidence** Detectado por el gate de S04 en su primera ejecucion real (BLOCK en C-S04-005:
436 hechos sin representar). Investigado:
```
SELECT unit_type, count(*), count(*) FILTER (WHERE numerator IS NULL AND denominator IS NULL)
  FROM parsed.facts WHERE is_numeric AND NOT is_nil GROUP BY 1;
 DIVIDED |   436 | 436     <- las 436 sin partes
 SIMPLE  | 61119 |   -

SELECT unit_ref, measures, numerator, denominator FROM parsed.units WHERE unit_type='DIVIDED';
 Unit_ARS_per_Share | [] | (null) | (null)
 Unit_USD_per_Share | [] | (null) | (null)
 Unit_USD_bbl       | [] | (null) | (null)
```
Ni `parsed.facts` ni `parsed.units` tienen las partes. El unico dato disponible es el
**nombre** del `unit_ref`.

**impact** 436 hechos (295 grupos canonicos) quedan sin unidad resoluble: precios por accion
y por barril, justamente las magnitudes que un screener necesita. Derivar la moneda del
nombre `'Unit_USD_per_Share'` seria inferir por nombre — el error de categoria que este
proyecto prohibe, el mismo que produjo el CIK de Banco Macro en la columna `cuit` (F-024).

**decision de S04, sin tocar S03** No se descartan ni se les inventa la unidad: se emiten con
`unidad_resuelta = false` (migracion `015`), el conflicto queda registrado en
`derived.normalize_conflict` con su motivo, y `ck_numerico_con_unidad` exige medida solo
cuando la unidad SI se resolvio. El valor esta, la carencia esta declarada, y quien calcule
ratios filtra por `unidad_resuelta`.

**required_action** (SEC) Extraer `<xbrli:divide><unitNumerator><unitDenominator>` en S03 y
poblar `parsed.units.numerator/denominator`. Despues re-correr S04: los 295 pasan a
`unidad_resuelta = true` sin cambiar su `fact_key`.

**acceptance_test** `SELECT count(*) FROM derived.fact WHERE NOT unidad_resuelta` debe dar 0
tras re-correr S03 y S04.

---

## S04_normalize · `CHECKPOINTED`

**checkpoint** `72f2e7c2297d44f0-s04` · corrida `72f2e7c2297d44f08a939c8c2c812ba0` (OK)
**gate PASS 9/9** · contrato `docs/architecture/S04_CONTRACT.md`

```
67.084 facts de entrada -> 47.930 hechos canonicos
desempates: UNICO 29.077 · IDENTICO 18.753 · POR_PRECISION 100 · POR_FACT_ID 0
dimensionales 37.078 / consolidados 10.852
unidad declarada no resuelta: 295 (F-026)
```

**Validacion independiente: 8/8**, reconstruyendo desde la base y el artefacto sin importar
el script — corrida terminal con report, `report` y transicion `CHECKPOINTED` en la MISMA
fila (F-009), `hash_out` recalculado coincide, **sin perdida (67.084 citados de 67.084, 0
inventados)**, `fact_key` reproducible sobre muestra de 500, toda entidad resuelve por CIK
autoritativo en `identity_v1`, y el artefacto en disco coincide con la base.

### Dos bugs propios que los tests y el gate encontraron

1. **Desempate por precision roto con floats.** `elegir_ganador` comparaba
   `str(value_numeric)`: `0.30` y `0.3000` como float son el mismo numero, asi que 2 grupos
   se clasificaban `IDENTICO` y se perdia la version mas precisa. Corregido: la identidad del
   valor es el **texto declarado**, no su interpretacion numerica. Los desempates pasaron de
   98 a 100 `POR_PRECISION` sobre datos reales.
2. **436 hechos descartados en silencio** — lo detuvo el gate (C-S04-005), no un test. Ver
   F-026.

### F-009 validado en condiciones reales, con un fallo genuino

La primera ejecucion murio por `statement_timeout` en C-S04-005. `run_scope()` cerro la
corrida como **`ABORTED` con `finished_at`**, y `corridas_huerfanas()` devolvio 0. La
correccion de F-009 se probo sola, con un crash real y no simulado — que es exactamente lo
que las 7 corridas del ciclo 8 no supieron hacer.


---
---

# CICLO 10 — F-026 CERRADO (S03 corregido, S03→S04 revalidado)

## F-026 · CERRADO · era un bug de S03, no una limitacion de fuente

**Determinacion contra el RAW, antes de tocar codigo.** Se buscaron las 32 unidades
`DIVIDED` en los XBRL originales:
```
unidades DIVIDED a verificar : 32
  RESUELTAS en el RAW        : 32     (0 sin <divide>)
```
```xml
<unit id="iso4217_ARS_per_shares">
  <divide>
    <unitNumerator><measure>iso4217:ARS</measure></unitNumerator>
    <unitDenominator><measure>shares</measure></unitDenominator>
  </divide>
</unit>
```
**El dato existe.** No corresponde `unidad_resuelta=false` como limitacion de fuente.

**Causa raiz — una palabra.** `engine/xbrlparse.py:parse_unit` buscaba `numerator` /
`denominator`; la especificacion XBRL 2.1 los llama **`unitNumerator` / `unitDenominator`**.
`findall` devolvia lista vacia en silencio.

### El test existente validaba el comportamiento equivocado

`test_unidad_dividida` **pasaba** antes de la correccion. Su fixture decia:
```xml
<xbrli:numerator>...</xbrli:numerator>        <- no existe en XBRL 2.1
<xbrli:denominator>...</xbrli:denominator>
```
**Test y parser compartian el error**, asi que el test daba PASS sobre un XML que ningun
emisor produce. Por eso el bug sobrevivio a los 18/18 tests que la auditoria del ciclo 2 dio
por buenos. Un fixture inventado por el mismo autor del parser no detecta un error de
**especificacion**: solo el RAW real lo detecta. El fixture se corrigio a los nombres reales
y se agregaron 3 tests, uno de ellos directamente contra el XBRL original de YPF.

### Acceptance test — 9/9

```
numerator/denominator = lo que dice el XBRL RAW   32 unidades verificadas · 0 discrepancias
todas las unidades DIVIDED pobladas               44/44   (antes 0/44)
todos los facts DIVIDED con numerator            436/436  (antes 0/436)
fact_key SIN CAMBIOS      antes  adf80fd7f3398823076a8f81efd8098e
                          despues adf80fd7f3398823076a8f81efd8098e
0 perdida                 entrada=67.084  citados=67.084  faltan=0
0 inventados              sobrantes=0
los 295 con unidad resuelta                       unidad_resuelta=false: 0  (antes 295)
hash_out de S04 reconstruible desde la base       OK
ambas corridas con estado terminal                S03 OK · S04 OK
```

Composicion resuelta en `derived.fact`:
```
iso4217_ARS_per_shares -> iso4217:ARS/shares        moneda=ARS
iso4217_USD_per_bbl    -> iso4217:USD/utr:bbl       moneda=USD
Unit_ARS_per_Share     -> iso4217:ARS/xbrli:shares  moneda=ARS
```

**S03** `e040bd08d0494621-s03` gate PASS 27/27 filings ·
**S04** `6371a6ce53b046be-s04` gate PASS 9/9 · **0 conflictos** (antes 295).
Suite: **90 passed**.

---

## F-027 · CERRADO · `apply_migrations` aplicaba DDL con el rol de la aplicacion

**Defecto que introduje al cerrar F-025.** Cree `get_admin_engine` pero no reconecte
`apply_migrations`, que siguio usando el engine de la app. S03 murio al arrancar:
`InsufficientPrivilege: permission denied for database catalaxia`.

Solo aparece al correr una etapa que aplica migraciones — no lo detectaba ningun test.

**Corregido** en `engine/db.py`: `apply_migrations` abre su propia conexion administrativa.
Aplicar DDL es administrativo por definicion.

---

## F-028 · OPEN · S03 no hace ANALYZE tras el replace-all

**evidence** Tras vaciar y recargar 67.084 filas, la validacion de integridad
`facts <-> contexts` supera el `statement_timeout` de 120 s:
```
QueryCanceled: canceling statement due to statement timeout
  SELECT count(*) FROM parsed.facts f WHERE ... NOT EXISTS (SELECT 1 FROM parsed.contexts c ...)
```
Un `ANALYZE` sobre los 4 objetos tarda **2,5 s** y el problema desaparece.

**impact** S03 no completa sin intervencion externa. La corrida queda ABORTED tras haber
escrito todo, y el trabajo se pierde.

**mitigacion aplicada** `ENGINE_STATEMENT_TIMEOUT_MS` configurable en `engine/db.py`
(default 120000). Con 900000 S03 completo en ~8 min. **Es una mitigacion, no la solucion.**

**required_action** (SEC) `ANALYZE parsed.facts, parsed.contexts, parsed.units,
parsed.concepts` dentro de S03, despues de la carga y antes de las validaciones.

**acceptance_test** S03 completa con el `statement_timeout` por defecto de 120 s.

---

## F-029 · OPEN · el `hash_out` de S03 es un digest de CONTEOS, no de contenido

**evidence** Tres corridas de S03, una de ellas con el parser corregido (44 unidades y 436
facts con contenido distinto), declaran **el mismo `hash_out`**:
```
a1a37b1986a14f8c...  60ff8e1aecd373ac...
971ce5d999a2499b...  60ff8e1aecd373ac...
e040bd08d0494621...  60ff8e1aecd373ac...   <- parser corregido, datos distintos
```
La especificacion es `sha256(json({facts, contexts, units, concepts, relations}))`: cinco
**cantidades de filas**.

**impact** Un cambio en el parser que altera los valores sin cambiar la cantidad de filas
produce un checkpoint indistinguible del anterior. **Un checkpoint que no distingue contenido
no sirve para detectar regresiones del parser** — que es justo para lo que se lo usa. Si la
correccion de F-026 hubiera sido una regresion en vez de un arreglo, el checkpoint no lo
habria notado.

**required_action** (SEC / ARQUITECTURA) `hash_out` debe cubrir contenido: por ejemplo
`sha256` del agregado ordenado de los hashes de fila, o al menos de los valores. Relacionado
con F-013 (semantica de checkpoint divergente).

**acceptance_test** Dos corridas de S03 con parsers que produzcan valores distintos e igual
cantidad de filas deben declarar `hash_out` distinto.

---

## F-031 · CERRADO · F-009 sigue vivo en S03

Los 3 intentos fallidos de re-correr S03 dejaron 3 corridas en `RUNNING` para siempre,
porque **S03 usa `start_run`/`finish_run` sueltos y no `run_scope()`**. Cada una con su causa
documentada (F-027, la 011 negando DELETE a `parsed`, y F-028). Cerradas como `ABORTED` en
`migrations/engine/018`, con la guarda que falla si queda alguna sin auditar.

**La misma sesion produjo 5 corridas de S04 y ninguna quedo huerfana.** La diferencia no es
la suerte: S04 usa `run_scope()`. Mientras S03 no lo adopte, cada crash suyo deja bitacora
corrupta.

Estado: `ABORTED 24 · BLOCKED 12 · OK 14 · RUNNING 0 · sin finished_at 0`.

**required_action** (SEC) migrar S03 a `run_scope()` y a la escritura consistente de
report + `CHECKPOINTED` en una transaccion, como hace S04.


---
---

# CICLO 11 — F-028 y F-029 CERRADOS (fixes separados)

## F-028 · CERRADO · ANALYZE dentro de S03, sin subir el timeout

**La primera version del fix no servia, y ademas parecia funcionar.** Se agrego `ANALYZE`
tras el replace-all y S03 lo corrio en **0,01 s** sobre 8 tablas de 67k filas. Imposible.
La causa:

```
WARNING:  permission denied to analyze "facts", skipping it
ANALYZE
```

**Postgres NO falla cuando un rol sin privilegio analiza una tabla: la saltea con un warning
y devuelve exito.** El script creia haber actualizado las estadisticas y la validacion de
integridad seguia cayendo por `statement_timeout`.

**Dos correcciones:**

1. `migrations/engine/019_parsed_owner_engine.sql` — el dueño de las 8 tablas y sus
   secuencias pasa a `catalaxia_engine`. Criterio (continuidad de la 016): `parsed.*` es el
   area de trabajo de S03, que la vacia y reconstruye entera desde el RAW en cada corrida.
   `identity_v1`, `engine`, `derived` y `fetch_raw` **siguen siendo de `catalaxia`**.
2. S03 **verifica** contra `pg_stat_user_tables.last_analyze` que el ANALYZE se haya aplicado
   de verdad, y aborta si no. Un skip silencioso ya no puede pasar por exito.

**acceptance_test — cumplido.**
```
[analyze] estadisticas actualizadas y VERIFICADAS sobre 8 tablas t=3.19s
gate = PASS -> READY_FOR_S04     con statement_timeout POR DEFECTO (120 s)
```
`ENGINE_STATEMENT_TIMEOUT_MS` queda como capacidad operativa, **no como solucion**: S03
completa con el default.

---

## F-029 · CERRADO · `hash_out` pasa a ser un digest de CONTENIDO (`hashout-v2`)

Cambio de contrato, documentado en `docs/architecture/HASH_OUT_CONTRACT.md`, implementado en
`engine/hashout.py`.

**Especificacion.** Digest de dos niveles:
```
fila_i   = sha256(campo_1 | campo_2 | …)          campos semanticos, orden fijo
tabla    = sha256(concat(sort(fila_1 … fila_n)))  el sort da la insensibilidad al orden
hash_out = sha256(json_ordenado({tabla: digest, …, _conteos: {…}}))
```
No entran `run_id`, timestamps, claves seriales ni rutas: son circunstancia de la corrida,
no contenido. Excluir las claves seriales es lo que hace que reordenar no mueva el hash.
`NULL` usa un centinela que lo distingue de la cadena vacia, y los `NUMERIC` se serializan
con su **texto declarado** — `0.30` y `0.3000` son declaraciones distintas.

**Pruebas de mutacion — 13 tests** (`tests/test_hashout.py`):

| Propiedad | Prueba | Resultado |
|---|---|---|
| P1 sensible al contenido | cambiar un valor, la precision, agregar/quitar/duplicar fila, mover un valor de columna | hash **distinto** en los 6 casos |
| P2 insensible al orden | permutar (8 semillas), `ORDER BY` ascendente vs descendente en la base, reinsertar con otra clave serial | hash **identico** |
| P3 reconstruible | recalculo independiente sobre la base | **coincide** |

**La prueba decisiva — reproducir la regresion historica.** Se revirtio F-026 en una
transaccion (44 unidades y sus facts vuelven a `numerator = NULL`) y se midio con ambas
especificaciones:

```
                                    hashout-v1                      hashout-v2
F-026 corregido      60ff8e1aecd373ac…              17cec7095c5bfa85…
regresion simulada   60ff8e1aecd373ac…   ← IGUAL    3e1c7db6772dc11f…   ← CAMBIO

conteos identicos en ambos estados : True
hashout-v1 detecto la regresion    : False    <- el defecto
hashout-v2 detecto la regresion    : True
   parsed.facts   CAMBIO      parsed.contexts  igual
   parsed.units   CAMBIO      parsed.concepts  igual
```

v2 no solo detecta: **señala las dos tablas exactas que cambiaron.**

**Compatibilidad.** El reporte declara `integrity.hash_spec`, y `hash_out_v1` se conserva
como campo aparte para poder contrastar con los checkpoints historicos. `C-S04-001` valida
contra la spec **que el reporte declara**, para no comparar hashes de especificaciones
distintas.

---

## Revalidacion S03 -> S04 · auditoria independiente 15/15

```
S03  bf48bb00d1134331-s03  (OK)  gate PASS 27/27 filings
S04  6e03a395756d4933-s04  (OK)  gate PASS 9/9 · 0 conflictos
Suite: 103 passed · corridas RUNNING: 0
```

| Verificado independientemente | |
|---|---|
| ambas corridas con estado terminal · 0 huerfanas | OK |
| 8/8 tablas de parsed analizadas · dueño correcto · timeout por defecto | OK |
| S03 y S04 declaran `hashout-v2`; ambos hashes **recalculados por el auditor coinciden** | OK |
| `hash_out_v1` conservado y sigue siendo `60ff8e1a…` (el que era ciego) | OK |
| F-026 sigue cerrado: 436/436 con numerator · `unidad_resuelta=false: 0` | OK |
| `fact_key` SIN CAMBIOS (`adf80fd7…`) · 0 perdida · 0 inventados (67.084/67.084) | OK |

Los dos hashes de S04 y S03 coinciden con los que se calcularon **antes** de correr las
etapas, en una sesion independiente: determinismo confirmado por dos vias.


---
---

# CICLO 12 — F-031 CERRADO · **SEC S03/S04 CERRADO**

## F-031 · CERRADO · S03 usa `run_scope()`, igual que S04

**El cambio, medido:** 46 lineas de diff, **todas de ciclo de vida, cero de parsing**. El
cuerpo de la etapa se movio entero a `_etapa(engine, settings, run)` sin reindentar ni
reordenar una sola linea; `main()` quedo como envoltorio que hace el setup, chequea huerfanas
y abre `run_scope`.

```diff
-    run = edb.start_run(engine, settings, PIPELINE_VERSION)
+    huerfanas = edb.corridas_huerfanas(engine)
+    if huerfanas: ... return 1
+    with edb.run_scope(engine, settings, PIPELINE_VERSION) as run:
+        return _etapa(engine, settings, run)

-    edb.finish_run(engine, run.run_id, "OK" if gate is GateStatus.PASS else "BLOCKED")
+    run.status = "OK" if gate is GateStatus.PASS else "BLOCKED"
```

### Las dos pruebas exigidas

| Prueba | Resultado |
|---|---|
| **Fallo controlado ANTES de parsear** (`9f32d8cf`) | `ABORTED` con `finished_at`, 0 etapas, 0 huerfanas |
| **Fallo controlado DESPUES del checkpoint** (`79d2c832`) | `ABORTED` con `finished_at`, traza `READY\|RUNNING\|VALIDATING\|PASSED\|CHECKPOINTED`, report escrito |
| **Corrida normal** (`4f12271c`) | `OK`, gate PASS 27/27, checkpoint `4f12271c20a142d8-s03` |

La segunda es la decisiva: **es el escenario exacto del grupo B de F-009**, donde dos corridas
llegaron a `CHECKPOINTED` con gate PASS y se quedaron en `RUNNING` para siempre. Ahora el
mismo fallo deja la corrida cerrada.

`S03_SIMULAR_FALLO` es el mecanismo de prueba del ciclo de vida (dos puntos: `INICIO`, `FIN`).
No altera parsing ni datos.

### Un matiz que la prueba 2 dejo a la vista

La corrida que fallo tras el checkpoint dejo **un checkpoint apuntando a una corrida
`ABORTED`**. No es inconsistencia sin defensa: `C-S04-001` exige `status == 'OK'` de la
corrida dueña y habria bloqueado S04. La corrida normal posterior reclamo el checkpoint por
`ON CONFLICT`. Se agrego el test
`test_f031_ningun_checkpoint_apunta_a_una_corrida_no_OK` para que la invariante quede
vigilada.

**Tests de regresion** (`tests/test_engine_run_lifecycle.py`): S03 no vuelve a tener
`finish_run` ni `start_run` sueltos, ambas etapas comparten el patron, y ningun checkpoint
cuelga de una corrida no-OK.

---

# SEC · S03 + S04 — CERRADO

**Auditoria independiente final: 15/15. Suite: 106 passed.**

```
S03  4f12271c20a142d8-s03   OK   gate PASS 27/27 filings
S04  f86d23ed49bd4854-s04   OK   gate PASS 9/9 · 0 conflictos
corridas: ABORTED 31 · BLOCKED 16 · OK 19 · RUNNING 0 · sin finished_at 0
```

| Verificado independientemente | |
|---|---|
| 0 corridas RUNNING · 0 sin `finished_at` · ningun checkpoint sobre corrida no-OK | OK |
| S03 usa `run_scope` y no cierra a mano; S03 y S04 comparten el patron | OK |
| las dos pruebas de fallo controlado quedaron terminales | OK |
| S04 declara consumir el checkpoint S03 vigente | OK |
| `hash_out` de S03 y S04 **recalculados por el auditor** coinciden con lo declarado | OK |
| ambos declaran `hashout-v2` | OK |
| 0 perdida y 0 inventados (67.084/67.084) | OK |
| `fact_key` estable desde antes de F-026 (`adf80fd7…`) | OK |
| F-026 cerrado: 436/436 con `numerator`, 0 sin unidad resuelta | OK |

### Findings de SEC cerrados en esta serie

| ID | Titular |
|---|---|
| F-009 | corridas sin estado terminal — cerradas con evidencia, dos grupos distintos |
| F-026 | `parse_unit` buscaba `numerator` en vez de `unitNumerator`; el test compartia el error |
| F-027 | `apply_migrations` aplicaba DDL con el rol de la aplicacion |
| F-028 | falta de `ANALYZE` tras el replace-all; el primer fix se salteaba en silencio |
| F-029 | `hash_out` era un digest de conteos: ciego al contenido |
| F-031 | S03 no usaba `run_scope`: cada crash dejaba una huerfana |

### Lo que queda abierto y NO es de SEC

`F-013` (semantica de checkpoint divergente entre las tres capas), `F-014` (Market:
`ticker_canonico` repite el ticker local en la fila del ADR), `F-019`, `F-020`, `F-024`
(Identity / backfill).

**No se hacen mas cambios sobre SEC.**


---
---

# CICLO 13 — BACKFILL PILOTO DE IDENTITY V1

## Premisas del enunciado REFUTADAS con evidencia

| Premisa | Evidencia | Veredicto |
|---|---|---|
| "M23 ejecutado sobre 584 instrumentos: 577 SUCCESS / 7 FAILED" | `market_raw_runs`: **20 filas, todas SUCCESS, 2 instrumentos distintos**. `market_price_daily`: 2 instrumentos. No existe ningun FAILED/PARTIAL/QUARANTINED | **NO ocurrio**. El catalogo tiene 584 instrumentos; la ejecucion masiva no |
| "F-014: cerrado" | `market_instruments`: instrument_id 84 (YPF, ADR, NYSE) sigue con `ticker_canonico='YPFD'`, que es el ticker de BYMA; idem 66 con `TGSU2` | **Cerrada la MITIGACION** en Identity v1 (no persiste `US/YPFD`); **el defecto de origen sigue abierto** |

No se construyo sobre estas premisas.

---

## F-032 · CERRADO · el backfill duplicaba entidades sin ancla autoritativa

**Defecto propio, detectado al medir la idempotencia.** Tres corridas dejaron **tres copias**
de cada emisora argentina sin CIK (CAAP, GGALB, SUPVB, YPFLUZ): 12 entidades donde debia
haber 4.

**Causa raiz.** `resolve_or_create_entity` resuelve por identificador **autoritativo**. El
ancla de esas entidades era el CUIT via `LEGACY_DIM_ENTITY`, que es `CORROBORATING` y por
contrato **nunca llega a autoritativo** -> `entity_of()` devuelve `None` -> crea otra entidad.

**Anclar una entidad en un identificador que la propia politica no permite hacer autoritativo
produce duplicacion silenciosa.** El contrato ya lo prohibia (seccion 7: *"entidad sin ningun
identificador autoritativo posible queda UNRESOLVED, no se crea"*); **la implementacion
violaba el contrato que yo mismo habia escrito**.

**Correccion.** Si la unica fuente de ancla es CORROBORATING, no se crea la entidad: se
reporta `UNRESOLVED` con el CUIT candidato. Verificado: una cuarta corrida ya no duplica.

**Limpieza.** Las 8 copias sobrantes **no se borraron** (la procedencia no se borra): se
marcaron `MERGED` apuntando a la canonica de su grupo. Las 4 canonicas quedaron
`PROVISIONAL` — existen, no tienen identidad establecida, y se cuentan como lo que son.

**Este finding lo encontre yo mismo revisando mi propio codigo. No lo doy por cerrado como
auditoria independiente: requiere una segunda validacion por un revisor distinto.**

---

## Resultado del piloto — 12 emisores, 6 clases de dificultad

```
total_entities          11 ACTIVE + 4 PROVISIONAL + 8 MERGED (residuo de F-032)
VERIFIED (identificadores) 11  (7 CIK + 4 LEI)
REVIEW_REQUIRED         13 reviews abiertas
CONFLICT                 0
REJECTED                 1  (BMA: CUIT invalido -> no se creo la entidad)
identificadores agregados 31 (11 autoritativos + 20 CANDIDATE)
bridges CIK<->CUIT demostrables      0
bridges no demostrables              4  (YPF, CEPU, GGAL, TGSU2)
casos que requieren intervencion humana  8  (4 bridges + 4 anclas PROVISIONAL)
```

**El hallazgo que decide D-I-04:** las 3 emisoras US puras (AAPL, MSFT, NVDA) resolvieron con
**1 identificador autoritativo y 0 reviews cada una**. El universo US no genera trabajo manual.
Las 4 argentinas con CIK generan **13 reviews entre las cuatro**.

---

## Banco adversario sobre el piloto — 10/10 rechazados

| # | Ataque | Mecanismo que lo rechaza |
|---|---|---|
| 1 | CUIT de CEPU asignado a YPF (**el error historico**) | `ux_identifier_autoritativo_unico` |
| 2 | CIK de YPF + CUIT de otra entidad | `ux_entity_un_autoritativo_por_tipo` |
| 3 | LEI correcto + CUIT con checksum roto | `ck_formato_identificador` |
| 4 | CUIT de tercero atribuido al emisor del documento | `ux_identifier_autoritativo_unico` |
| 5 | ticker BYMA usado como ticker NYSE | `ux_symbol_vigente` |
| 6 | ticker NYSE como identidad corporativa | `ck_ticker_no_autoritativo` |
| 7 | conflicto entre dos fuentes (segundo CIK) | `ux_identifier_autoritativo_unico` |
| 8 | ausencia de provenance | `assertion_id NOT NULL` |
| 9 | duplicacion de identificador autoritativo | `ux_identifier_autoritativo_unico` |
| 10 | proceso firmando una decision humana | `ck_humano_no_es_proceso` |

GLEIF con `registeredAs = null` (GGAL) -> `REVIEW_REQUIRED`, **sin inferir del nombre**.

---

## Auditoria independiente — 11/11

0 identificadores autoritativos sin provenance · 0 entidades con dos autoritativos del mismo
tipo · 0 identificadores compartidos entre entidades · **0 CUIT autoritativos (ninguno
inventado)** · 0 bridges VERIFIED · 0 decisiones humanas de proceso · 0 TICKER autoritativos ·
0 instrumentos sin procedencia · **BMA no fue creado** · guardas intactas · 0 huerfanas.

**Suite: 106 passed.**

---

## F-033 · CERRADO · test frágil acoplado al estado de la base

`test_13_el_rol_de_la_app_no_puede_evadir_las_guardas` empezo a fallar tras el piloto: usaba
el CIK `0000320193` (Apple) como "CIK libre" y el piloto lo ocupo. El sistema devolvio
`REJECTED`, que era **el comportamiento correcto**. Se desacoplo el test usando un CIK que
ninguna carga reclama.


---

## F-034 · REGISTRADO (antes de corregir) · los identificadores CANDIDATE se duplican en cada corrida

**evidence** Tres corridas consecutivas del piloto acotado (YPF, CEPU, TGSU2, GGAL):
```
entidades      19 -> 19 -> 19     estables (F-032 corregido)
identificadores 51 -> 55 -> 59    +4 por corrida
assertions      79 -> 83 -> 87    +4 por corrida
```
```sql
SELECT id_type, id_value, is_authoritative, count(*)
  FROM identity_v1.identifier GROUP BY 1,2,3 HAVING count(*) > 1;
 CUIT | 30546689979 | f | 7
 CUIT | 33650305499 | f | 7
 CUIT | 30704962807 | f | 7
 CUIT | 30657862068 | f | 7
```

**causa** `assert_identifier` deduplica por los indices unicos parciales, que estan
condicionados a `WHERE is_authoritative AND valid_to IS NULL`. Un identificador
**CANDIDATE** no cae bajo esa condicion —correctamente, porque dos fuentes pueden proponer
el mismo valor y ambas propuestas son evidencia— pero la capa de dominio tampoco chequea si
la MISMA fuente ya lo propuso. Cada corrida reinserta la propuesta del CUIT legacy.

**impact** No contamina la identidad: ninguno es autoritativo, ninguna entidad se duplica y
la resolucion sigue dando el mismo resultado. Pero rompe la **reproducibilidad**: el estado
de la base depende de cuantas veces se corrio el backfill, y eso invalida cualquier
`state_digest` sobre `identity_v1` (mismo problema de fondo que F-013 y F-029).

**required_action** Deduplicar la propuesta por `(entity_key, id_type, id_namespace,
id_value, source_id)` vigente: la misma fuente proponiendo lo mismo dos veces es **una**
propuesta, no dos. Fuentes distintas proponiendo el mismo valor SI deben quedar como dos
assertions: son dos corroboraciones independientes.

**acceptance_test** Tres corridas seguidas del piloto dejan identificadores y assertions
constantes.


---

## F-035 · REGISTRADO · una entidad MERGED puede seguir adquiriendo identificadores autoritativos

**evidence** Fase B, mutacion M7: se inserto un `CIK` autoritativo sobre una entidad con
`entity_status='MERGED'` y la base **lo acepto**.

**impact** Semanticamente incorrecto: una entidad fusionada en otra no puede adquirir
identidad nueva — su identidad ya migro. No produce contaminacion entre entidades activas
(los indices unicos siguen impidiendo que dos entidades compartan un identificador
autoritativo), pero permite que evidencia quede colgada de una entidad muerta, invisible
para cualquier consulta que filtre por `ACTIVE`.

**required_action** `CHECK` o trigger: `is_authoritative` exige que la entidad este en
`ACTIVE` o `PROVISIONAL`. Alternativamente, migrar automaticamente el identificador a
`merged_into_key`, pero eso es una decision de modelo, no un parche.

**NO se corrige en este ciclo**: el alcance era F-032 y la ratificacion. Queda registrado.

---

# CICLO 4B — CIERRE DE FASES

## F-032 · CLOSED (con auditoria independiente en Fase B)

**Reproduccion antes de corregir** (transaccion revertida, identificadores libres):
```
ESC.1 resolver por el MISMO identificador (CIK)          -> REUTILIZA
ESC.2 resolver por OTRO identificador de la entidad (LEI) -> REUTILIZA
ESC.3 CIK nuevo para la misma empresa                     -> crea entidad nueva
```
ESC.3 **no es un defecto**: un CIK que nadie reclama no puede fusionarse con una entidad
existente por coincidencia de nombre. Crear una entidad nueva es el contrato funcionando.

**Causa raiz confirmada:** el backfill anclaba la entidad en el CUIT via
`LEGACY_DIM_ENTITY`, fuente `CORROBORATING` que por politica **nunca llega a autoritativo**.
`resolve_or_create_entity` resuelve por identificador **autoritativo**, no lo encontraba, y
creaba otra. La duplicacion fue en `entity` **y** en `identifier` (cada copia arrastro su
propio identificador CANDIDATE).

**Correccion (dos partes):**
1. Ciclo 13 — no se crea entidad si el unico ancla posible es CORROBORATING.
2. Este ciclo — `resolver_por_candidatos()`: se resuelve por **cualquiera** de los
   identificadores autoritativos conocidos, de modo que cambiar el orden de las fuentes no
   duplica. Si dos candidatos apuntan a entidades distintas **no se fusiona nada**: es un
   conflicto y lo decide una persona.

**Acceptance:** 6 corridas del piloto acotado -> **4 emisores, 4 entidades, 0 duplicadas**,
`19 entidades · 59 identificadores · 87 assertions` constantes en las ultimas 3.

**Fase B — 7 mutaciones, 6 rechazadas + 1 hueco nuevo (F-035).** 13/13 verificaciones
independientes sobre la base.

## F-034 · CLOSED

Deduplicacion de la propuesta por `(entity_key, id_type, id_namespace, id_value, source_id)`.
Fuentes distintas proponiendo el mismo valor siguen siendo dos corroboraciones.
Verificado: 3 corridas seguidas dejan identificadores y assertions constantes.
**Residuo historico:** los duplicados creados antes del fix (7 copias de cada CUIT legacy)
siguen en la base. No se borran — la procedencia no se borra — y quedan como evidencia.


---
---

# CICLO 4C — F-035 CERRADO

## F-035 · CLOSED · una entidad MERGED/DISSOLVED no adquiere identidad autoritativa

**Reproduccion antes de corregir** (Fase A, escritura DIRECTA a la base, sin pasar por Python):
```
entidad MERGED elegida: E01M13XBTVJZ4PXX9JZ4P8V22T0
INSERT INTO identity_v1.identifier (... 'CIK','SEC','0006666666', true ...)
-> F-035 CONFIRMADO: una entidad MERGED ACEPTO un identificador AUTORITATIVO
   la entidad esta fusionada en E01M13XBSB1SNWTM8WJ512Z329H y adquirio identidad nueva
```
El finding era correcto. No se asumio: se reprodujo.

### Politica de estados (Fase B, documentada en `IDENTITY_V1_SCHEMA.md` seccion 8)

El modelo tiene **cuatro** estados de entidad. `REVIEW_REQUIRED`, `CONFLICT` y `REJECTED`
**no son estados de entidad**: son estados de `assertion` y de `conflict`. No se inventaron
estados que el modelo no define.

| estado | ¿identidad autoritativa nueva? | fundamento |
|---|---|---|
| `ACTIVE` | si | entidad operativa |
| `PROVISIONAL` | si | adquirirla es su transicion esperada |
| `MERGED` | **no** | su identidad ya migro a `merged_into_key` |
| `DISSOLVED` | **no** | conserva los historicos, no adquiere nuevos |

### Correccion (Fase C) — `migrations/engine/021`

**Dos guardas, porque una sola deja la otra puerta abierta.** Ambas son triggers y no
`CHECK`: la condicion depende de otra tabla — y por eso resisten la escritura directa, que
es como se encontro el defecto.

1. `tg_identidad_exige_entidad_viva` sobre `identifier` (INSERT **y** UPDATE): una entidad
   muerta no adquiere identidad. Cubre tambien la via de entrar `CANDIDATE` y promoverse.
2. `tg_no_matar_entidad_con_identidad` sobre `entity`: una entidad que sostiene
   identificadores autoritativos vigentes no puede pasar a `MERGED`/`DISSOLVED` sin
   retirarlos o migrarlos. Sin esta guarda se llega al mismo estado incoherente por el otro
   lado: primero se cargan los identificadores y despues se fusiona.

### Fase D — 13 tests adversarios

MERGED + CIK / LEI / CUIT (los tres rechazados) · MERGED + CANDIDATE (aceptado: evidencia no
es identidad) · DISSOLVED · **escritura directa a la base** · promocion por UPDATE · fusion
de entidad con identidad vigente (rechazada) · fusion tras retirar la identidad (procede) ·
ACTIVE y PROVISIONAL adquiriendo identidad (proceden) · conflicto entre activas (rechazado).

### Fase F — auditoria independiente, 7 mutaciones por SQL crudo

```
A1 MERGED + CIK autoritativo (la M7 original)      RECHAZADO
A2 MERGED + CUIT autoritativo                       RECHAZADO
A3 MERGED: entrar CANDIDATE y promover por UPDATE   RECHAZADO
A4 revivir MERGED -> ACTIVE                         aceptado (deliberado)
A5 matar una ACTIVE que sostiene identidad          RECHAZADO
A6 PROVISIONAL adquiriendo identidad                aceptado (debe poder)
A7 MERGED + CANDIDATE                               aceptado (evidencia, no identidad)
```

**Residual conocido y aceptado:** A4. Revivir una entidad fusionada (`MERGED -> ACTIVE`) es
una operacion legitima —deshacer una fusion equivocada— y por esa via se le puede cargar
identidad. No se bloquea porque revivir es un acto explicito y auditable, no un accidente;
bloquearlo dejaria sin salida a una fusion mal hecha. Queda documentado, no oculto.

---

## Correccion de una afirmacion de la Fase F

La verificacion *"0 duplicados de (entidad, tipo, valor, fuente) vigentes"* dio **FALLA** en
la primera pasada. Investigado: los 8 grupos con copias tienen su ultima insercion a las
**12:42**, anterior al fix de F-034. Mi consulta usaba una ventana temporal ambigua
(`created_at > now() - 30 min` sobre un GROUP BY que abarca filas fuera de la ventana).

Prueba decisiva, sin ventanas: `identificadores antes=59 -> despues=59, delta=0`.
**Es residuo historico; ninguna copia nueva.** La verificacion estaba mal formulada, no el
sistema. Los duplicados previos al fix no se borran —la procedencia no se borra— y quedan
como evidencia del defecto.


---
---

# CICLO 5 — RATIFICACION CONTROLADA · **DETENIDA EN FASE B**

## F-036 · REGISTRADO · la regla "GLEIF sin registeredAs no produce CUIT" vive solo en Python

**evidence** Banco adversario, ataque 5, por las dos vias:
```
5a  CUIT de GGAL por DERIVED_RULE           -> RECHAZADO (ck_authoritative_metodo)
5b  CUIT de GGAL con source_id='GLEIF'      -> ACEPTADO por la base
    via link_cuit_desde_gleif (capa dominio) -> REVIEW_REQUIRED, motivo RA999999
```

**analisis** La base **no puede** saber que GLEIF publica `registeredAt=RA999999` y
`registeredAs=null` para ese LEI: es contenido de un registro externo. Una escritura directa
que declare `source_id='GLEIF'` con una cita fabricada le da un CUIT a GGAL.

Es una **asimetria estructural, no un descuido**: hay reglas que solo pueden vivir en la capa
de dominio porque dependen de contenido que la base no observa. Lo que la base SI garantiza
—y garantiza— es que ese CUIT tendria provenance completa, seria unico, y quedaria atribuido
a una sola entidad. Lo que no puede verificar es si la cita es cierta.

**No se inventa un constraint fragil** para simular una garantia que la base no puede dar.

**required_action** Documentar explicitamente en `IDENTITY_V1_SCHEMA.md` que existe una clase
de reglas "de contenido de fuente" cuya unica barrera es la capa de dominio, y que toda
escritura a `identity_v1` debe pasar por ella. Complementariamente: revocar `INSERT` directo
sobre `identity_v1.identifier` a todo rol que no sea el del pipeline.

**severidad** MEDIUM. No afecta al piloto ni a la ratificacion pendiente.

---

## Fase A — reconstruccion previa: SIN DISCREPANCIAS

| Entidad | CIK | LEI | CUIT (GLEIF) | Fuente CIK | Fuente LEI | Estado |
|---|---|---|---|---|---|---|
| YPF | 0000904851 | 5493003N7447U18U5U53 | 30546689979 | `SEC_20F` | `GLEIF` | ACTIVE |
| CEPU | 0001717161 | 2549005JLIWQ6B7VNR38 | 33650305499 | `SEC_REGISTRY` | `GLEIF` | ACTIVE |
| TGSU2 | 0000931427 | 5299002TRC7IFQYSW596 | 30657862068 | `SEC_REGISTRY` | `GLEIF` | ACTIVE |
| GGAL | 0001114700 | 5299008H3AXIXV5G3C23 | — (RA999999) | `SEC_REGISTRY` | `GLEIF` | ACTIVE |

Los 4 CIK y los 4 LEI coinciden con lo esperado; los LEI provienen de `GLEIF`; ninguna
entidad tiene CUIT autoritativo; **0 bridges VERIFIED preexistentes**.

## Fase B — DETENIDA. Dos bloqueos, ninguno tecnico

El mecanismo funciona (verificado en transaccion revertida): con una persona y evidencia de
ambos extremos, `ratificar_bridge` produce `status=VERIFIED · method=HUMAN_DECISION ·
confidence=STRONG`, y el CUIT consolida a `VERIFIED`. **El bloqueo es de decision.**

**Bloqueo 1 — no hay actor humano identificado.** El sistema exige `resolved_by` sin prefijo
`proc:` (`ck_humano_no_es_proceso`), pero **no tiene registro de usuarios**: `resolved_by` es
un TEXT libre. No existe un mecanismo que diga quien es la persona autorizada a ratificar.
Poner un nombre por mi cuenta seria **repetir exactamente F-016**, donde un script escribio
`resolved_by='fmonfasani'` para una decision que esa persona nunca tomo.

**Bloqueo 2 — no tengo la evidencia que el contrato exige.** `ratificar_bridge` pide
`evidencia_cik` y `evidencia_lei` verificables por un tercero. G5 establecio que **ninguna
fuente primaria publica el par CIK<->LEI**: la ratificacion consiste precisamente en que una
persona compare el documento SEC del registrante con el registro GLEIF y decida. Yo puedo
mostrar ambos registros; no puedo hacer esa comparacion en nombre de nadie y firmarla.

## Nota de contrato — `VERIFIED_BY_HUMAN` no existe

`assertion_status_check` admite `UNRESOLVED | CANDIDATE | REVIEW_REQUIRED | VERIFIED |
REJECTED`. El equivalente contractual de "ratificado por humano" es la terna
`status='VERIFIED'` + `method='HUMAN_DECISION'` + `confidence='STRONG'`, con `resolved_by` de
persona. **No se agrego un estado nuevo para simular el nombre pedido.**

## Fase C — banco adversario: 9 de 10 correctos, 1 hueco (F-036)

```
1  CUIT de CEPU -> YPF                        RECHAZADO  ux_identifier_autoritativo_unico
2  CUIT de YPF -> CEPU                        RECHAZADO  ux_identifier_autoritativo_unico
3  LEI ratificado reutilizado en otra entidad RECHAZADO  ux_identifier_autoritativo_unico
4  bridge por coincidencia de NOMBRE          RECHAZADO  ck_authoritative_metodo
5a GGAL: CUIT por regla derivada              RECHAZADO  ck_authoritative_metodo
5b GGAL: CUIT con cita GLEIF fabricada        ACEPTADO   -> F-036
6  bridge CANDIDATE -> VERIFIED por UPDATE    RECHAZADO  tg_assertion_inmutable
7  segunda entidad para un CIK ratificado     RECHAZADO  ux_identifier_autoritativo_unico
8a modificar provenance de la ratificacion    RECHAZADO  tg_assertion_inmutable
8b eliminar provenance de la ratificacion     RECHAZADO  DELETE prohibido
```

El ataque 5 fallo primero por un **error de sintaxis mio** y se conto como OK falso. Rehecho
correctamente por las dos vias, revelo F-036.

## Fase D — estado real

```
entidades 19 (7 ACTIVE · 8 MERGED · 4 PROVISIONAL) · identifiers 59 (11 autoritativos)
assertions 87 · reviews OPEN 13 · conflicts 0
bridges: CANDIDATE 4 · VERIFIED 0 · REVIEW_REQUIRED 0
YPF/CEPU/TGSU2 -> CANDIDATE, sin CUIT     GGAL -> CANDIDATE, sin CUIT
BMA sin modificacion · F-024 OPEN
```


---
---

# CICLO 5B — F-036 CERRADO

## Reproduccion (Fase A) — con el ROL DE LA APLICACION, no con el admin

```
INSERT ... source_id='GLEIF', evidence='GLEIF publica registeredAs 30-70496280-7 bajo RA000009'
-> ACEPTADO. GGAL adquirio un CUIT que GLEIF NO publica (el registro real
   dice registeredAt=RA999999, registeredAs=null).
```

## Modelo de seguridad (Fase B)

Solo dos roles pueden conectarse y ambos escribian directo. `PUBLIC` no tiene nada.

| tabla | rol | ANTES | DESPUES |
|---|---|---|---|
| `identifier` | `catalaxia_engine` | INSERT, SELECT, **UPDATE (todas)** | INSERT, SELECT, **UPDATE (`valid_to`, `status`)** |
| `assertion` | `catalaxia_engine` | INSERT, SELECT, **UPDATE (todas)** | INSERT, SELECT, **UPDATE (`valid_to`, `superseded_by`)** |
| `entity` | `catalaxia_engine` | INSERT, SELECT, **UPDATE (todas)** | INSERT, SELECT, **UPDATE (`preferred_name`, `country`, `updated_at`)** |
| las tres | `catalaxia` (superusuario/owner) | todo | todo — es el rol administrativo, sin cambios |

## Correccion (Fase C) — `022` + `023`

**Por que no un CHECK sobre la cita.** La base no observa GLEIF. Parsear `evidence` —texto
libre— para adivinar si la cita es cierta seria el CHECK artificial que el contrato prohibe.

**Lo que si puede exigir la base.** No que la cita sea CIERTA, sino que quien afirma
**declare la prueba de forma estructurada**. Nueva columna `assertion.source_facts JSONB`, y
un CHECK: un CUIT afirmado por GLEIF con `status='VERIFIED'` exige
`source_facts->>'registeredAt' IN ('RA000009','RA000010')` y `registeredAs` no vacio.

El atacante ya no puede colar una frase: tiene que declarar un dato estructurado,
**falsificable pero contrastable contra GLEIF por cualquier auditor en un solo request**. Se
pasa de una afirmacion inverificable a una verificable. Eso es lo que la base puede
garantizar, y es lo que garantiza.

**`NOT VALID`**: hay 3 assertions historicas (4, 8, 16) que declaran la autoridad correcta
pero en texto libre, porque `source_facts` no existia. Son inmutables por
`tg_assertion_inmutable` y **no se reescribe el pasado para que encaje en un contrato nuevo**.
`NOT VALID` no toca lo existente y valida todo INSERT/UPDATE futuro.

### Un hueco propio, encontrado por el test

La version de la migracion `022` tenia logica trivaluada:
`source_facts->>'registeredAt' IN ('RA000009','RA000010')`. Con el campo ausente, `->>`
devuelve NULL, `NULL IN (...)` evalua a NULL, y **un CHECK trata NULL como satisfecho**:
omitir el campo pasaba, declararlo mal no — al reves de lo necesario. Lo encontro el test
parametrizado con `{"registeredAt": null}`. Corregido con `COALESCE` en la migracion `023`.

## Auditoria independiente (Fase F) — el ataque original y 6 caminos alternativos

Todo ejecutado **como `catalaxia_engine`**, el rol real de la aplicacion:

```
ataque original F-036                       RECHAZADO  ck_gleif_cuit_declara_autoridad
B1 CUIT GLEIF sin source_facts              RECHAZADO  ck_gleif_cuit_declara_autoridad
B2 CUIT GLEIF con registeredAt=null         RECHAZADO  ck_gleif_cuit_declara_autoridad
B3 CUIT GLEIF con RA999999 (el real de GGAL) RECHAZADO ck_gleif_cuit_declara_autoridad
B4 promover assertion por UPDATE            RECHAZADO  permission denied for table assertion
B5 promover is_authoritative por UPDATE     RECHAZADO  permission denied for table identifier
B6 cambiar source_id de GLEIF a SEC_20F     RECHAZADO  permission denied for table assertion
```

Las tres ultimas son la barrera de privilegios: sin `UPDATE` sobre esas columnas, los caminos
de esquive no existen para el rol operativo.

## Regresion (Fase E)

`entidades 19 · identifiers 59 · assertions 87 · reviews 13 · conflicts 0` — sin cambios tras
correr el piloto. **GGAL sigue sin CUIT · BMA sin tocar · 0 bridges VERIFIED · 0 CUIT
autoritativos · 0 identificadores sin provenance · 0 duplicados nuevos.**

**Suite: 144 passed** (134 + 10 regresiones de F-036).


---
---

# CICLO F-024 — DICTAMEN

## F-024 · CLOSED_WITH_NOTES

**Reproduccion.** `dim_entity#572`: `ticker='BMA'`, `grupo='adr'`, `cuit='0001347426'`,
`cik=NULL`. Es la **unica** fila del catalogo con un `cuit` de longitud distinta de 11.

**Que es `0001347426` — dos fuentes primarias, no inferencia:**
```
data/raw/catalogo_edgar/company_tickers_2026-08-23.json
   {"cik_str": 1347426, "ticker": "BMA", "title": "Macro Bank Inc."}
data/raw/submissions/CIK0001347426.json
   name 'Macro Bank Inc.' · sic 6029 Commercial Banks · exchanges ['NYSE']
   domicilio AV. EDUARDO MADERO 1182, BUENOS AIRES · 1000 filings (941 6-K, 19 20-F)
```
Corroborado en catalogos derivados: el mismo valor figura como **`cik`** en `empresas`
(fuente `edgar`), `tickers`, `precios`, `ratios` y `cnv_estados`, y sostiene 1.473 filas en
`facts` y 4.101 en `facts_xbrl`.

**Es el CIK de Macro Bank Inc.** No es un CUIT: 10 digitos, no pasa el modulo 11.

### El vinculo NO es por nombre ni por ticker

La fila legacy **contiene** el valor `0001347426`, y SEC declara ese valor como CIK. El
identificador correcto ya estaba en la fila, en la columna equivocada. No se infiere nada de
la razon social: se lee el dato que la fila trae y se lo tipa bien. Esa distincion es lo que
separa esta correccion de una inferencia por nombre.

### Causa raiz

Un proceso de ingesta escribio el CIK en la columna `cuit`. El error se **propago**:
`adr_dividendos.cuit` tiene 25 filas con el mismo valor. No se corrige aguas abajo en este
ciclo (fuera de alcance), pero queda documentado.

## Identidad demostrable de BMA

| Identificador | Valor | Fuente | Autoridad | Estado |
|---|---|---|---|---|
| **CIK** | `0001347426` | `company_tickers.json` + `submissions` | `SEC_REGISTRY` | **VERIFIED** |
| **LEI** | ambiguo | GLEIF (por nombre = DISCOVERY) | — | **REVIEW_REQUIRED** |
| **CUIT** | no demostrable | — | — | **ausente** |

**Por que el LEI queda ambiguo.** GLEIF devuelve **DOS** registros vigentes para
`BANCO MACRO SOCIEDAD ANONIMA`:

| LEI | status | registeredAs | domicilio |
|---|---|---|---|
| `579100KKDKKIFEBKK040` | ACTIVE | `30-50001008-4` | MADERO EDUARDO AV. 1182, BUENOS AIRES |
| `579100KKDKKIFEBKK058` | NULL | `30500010084` | 447 SARMIENTO, CAPITAL FEDERAL |

El domicilio del primero coincide con el que SEC declara. **Es corroboracion, no autoridad**:
ninguno menciona el CIK, y elegir por domicilio seria exactamente la inferencia que el
contrato prohibe. El CUIT `30500010084` pasa el modulo 11, pero llega por una cadena
`nombre -> LEI -> CUIT` cuyo primer eslabon es DISCOVERY. **No se establece.**

## Tratamiento — conservar la evidencia, corregir la interpretacion

`scripts/engine/f024_bma.py`, contrato en `docs/architecture/F024_CONTRATO.md`.

1. Entidad BMA creada, anclada en su **CIK autoritativo** con provenance de SEC.
2. El error del legacy queda como **`conflict` abierto** citando `dim_entity#572`.
3. La ambiguedad del LEI queda como **`review` abierta** con los dos candidatos.
4. **`dim_entity` no se toca**: es el registro historico del error.

## Banco adversario — 8 ataques, 8 correctos (rol operativo)

```
1 interpretar el CIK como CUIT              RECHAZADO  ck_formato_identificador
2 insertarlo como CUIT aunque sea CANDIDATE RECHAZADO  ck_formato_identificador
3 CIK sin evidencia                         RECHAZADO  ck_verified_exige_evidencia
4 resolver BMA por NOMBRE                   RECHAZADO  ck_authoritative_metodo
5 segunda entidad para el mismo CIK         RECHAZADO  ux_identifier_autoritativo_unico
6 modificar la provenance                   RECHAZADO  permission denied
7 borrar el conflicto que documenta el error RECHAZADO permission denied
8 establecer el CUIT via el LEI ambiguo     aceptado -> ver F-037
```

El ataque 5 fallo primero por un `entity_key` invalido mio —**un OK falso**— y se rehizo con
una clave valida.

## Auditoria independiente — 10/10, contra los 8 acceptance del contrato

Incluye la lectura de `dim_entity` **desde el archivo**, no desde mi codigo, para verificar
que quedo intacta. Suite: **144 passed**.

---

## F-037 · REGISTRADO · la exigencia de evidencia estructurada cubre solo a GLEIF

**evidence** Ataque 8: un CUIT afirmado con `source_id='SEC_20F'` y una cita fabricada entra
sin `source_facts`. El CHECK `ck_gleif_cuit_declara_autoridad` que cerro F-036 esta
condicionado a `source_id='GLEIF'`.

**impact** Asimetria en mi propio fix de F-036. `SEC_20F` y `AFIP` son autoritativas para
CUIT y no exigen evidencia estructurada. La superficie es menor —requiere INSERT sobre
`identifier`, que solo tienen dos roles— pero la asimetria es real.

**required_action** Extender la exigencia de `source_facts` a toda fuente autoritativa para
CUIT, con el campo estructurado que corresponda a cada una (para `SEC_20F`: el accession y
la seccion del documento donde figura).

**NO se corrige en este ciclo**: el alcance era F-024 y corregirlo seria reabrir F-036.


---
---

# CICLO F-037 — DICTAMEN

## F-037 · CLOSED

### Reproduccion — el finding era MAS ANCHO de lo que decia

Con `catalaxia_engine`, el rol operativo:

```
A1  SEC_20F           + source_facts NULL  -> ACEPTADO
A2  AFIP              + source_facts NULL  -> ACEPTADO
A3  GLEIF             + source_facts NULL  -> RECHAZADO (F-036)
A4  SEC_REGISTRY      + CUIT autoritativo  -> ACEPTADO   <-- authoritative_for = {CIK}
A5  LEGACY_DIM_ENTITY + CUIT autoritativo  -> ACEPTADO   <-- es CORROBORATING
A6  ataque completo: BMA adquiere un CUIT autoritativo con evidencia arbitraria
```

No era solo que faltara `source_facts` para `SEC_20F`. **La matriz fuente x tipo de
identificador vivia unicamente en Python** (`source_authority()`): la base guardaba
`identity_v1.source.authoritative_for` y no la usaba para nada. Cualquier fuente podia
establecer cualquier identificador por SQL directo — incluida una `CORROBORATING`.

### Correccion — `migrations/engine/024`

Dos mecanismos, porque son dos preguntas distintas:

1. **`tg_fuente_autoritativa_para_el_tipo`** (trigger, porque depende de otra tabla).
   Una assertion `VERIFIED` que establece un identificador exige que su fuente sea
   `AUTHORITATIVE` **y** tenga ese `id_type` en `authoritative_for`. Es **general**: aplica a
   CIK, LEI y CUIT. `HUMAN_DECISION` esta exento — una persona ratifica, no publica un
   registro; eso ya lo gobiernan `ck_humano_exige_autor` y `ck_humano_no_es_proceso`.

2. **`ck_cuit_exige_evidencia_estructurada`** (CHECK, porque depende solo de la fila).
   Reemplaza a `ck_gleif_cuit_declara_autoridad` **sin relajarlo**: conserva la regla de
   GLEIF y le suma `SEC_20F` (accession + seccion), `AFIP` (constancia) y `HUMAN`
   (reviewer + decision_ref). Cualquier otra fuente: `false`.

La base valida **la estructura declarada de la evidencia, nunca la verdad externa**. No sabe
si el 20-F dice lo que la assertion afirma; si exige que la assertion diga *en que accession
y en que seccion* lo dice, para que un tercero lo abra.

`NOT VALID` por las 3 assertions `GLEIF VERIFIED` historicas sin `source_facts`, inmutables
por `tg_assertion_inmutable`. Se midieron antes: son exactamente 3, las mismas de F-036.

### Banco adversario — 15 casos, 15 con el resultado esperado

```
1  SEC_20F sin facts                    RECHAZADO  ck_cuit_exige_evidencia_estructurada
2  SEC_20F con facts = {}               RECHAZADO  idem
3  SEC_20F sin 'seccion'                RECHAZADO  idem
4  GLEIF sin registeredAs               RECHAZADO  idem
5  GLEIF con registeredAt invalido      RECHAZADO  idem
6  LEGACY_DIM_ENTITY (CORROBORATING)    RECHAZADO  tg_fuente_autoritativa_para_el_tipo
6b SEC_REGISTRY (solo CIK)              RECHAZADO  idem
6c CNV_PORTAL (DISCOVERY_ONLY)          RECHAZADO  idem
7  promover is_authoritative por UPDATE RECHAZADO  permission denied
8  cambiar source_id                    RECHAZADO  permission denied
9  modificar source_facts               RECHAZADO  permission denied
12 el F-037 original completo           RECHAZADO  ck_cuit_exige_evidencia_estructurada
L1 SEC_20F con accession y seccion      aceptado
L2 GLEIF con RA000009 y registeredAs    aceptado
L3 AFIP con constancia                  aceptado
L4 propuesta CANDIDATE desde LEGACY     aceptado
```

**Dos falsos resultados propios, corregidos y repetidos:** el ataque 12 fallo primero por un
error de sintaxis mio (`INSERT` dentro de `VALUES`) y conto como OK falso; L4 estaba mal
construido —una propuesta es `status='CANDIDATE'`, no `'VERIFIED'`— y aparecio como HUECO
falso. Ambos rehechos.

### Regresion

Suite **144 passed**. Nueve tests se adaptaron porque el contrato cambio, no porque el
comportamiento fallara: `ev_20f` y los helpers ahora declaran evidencia estructurada, y
`test_12` refleja que el ticker tiene ahora **dos** barreras — el trigger de autoridad actua
antes que `ck_ticker_no_autoritativo`.

Capa de dominio adaptada: `resolve_review` y `ratificar_bridge` declaran
`{reviewer, decision_ref}`.

### Auditoria independiente — 9/9

`CIK de BMA VERIFIED` · `44 CANDIDATE de LEGACY intactos` · `3 assertions GLEIF historicas
intactas` · `0 CUIT autoritativos` · `0 bridges VERIFIED` ·
`entidades 20 · identifiers 60 · assertions 88 · reviews 14 · conflicts 1`.

El pipeline real (`f024_bma.py`, `identity_v1_backfill_piloto.py`) corre sin cambios.


---
---

# CICLO 6 — RATIFICACION HUMANA + CROSS-WORKSTREAM

## Las 3 ratificaciones · reviewer **Federico** · 2026-08-28

```
assertion 342  CIK:SEC:0000904851 <-> LEI:GLEIF:5493003N7447U18U5U53  HUMAN_DECISION/STRONG/VERIFIED
assertion 343  CIK:SEC:0001717161 <-> LEI:GLEIF:2549005JLIWQ6B7VNR38  HUMAN_DECISION/STRONG/VERIFIED
assertion 344  CIK:SEC:0000931427 <-> LEI:GLEIF:5299002TRC7IFQYSW596  HUMAN_DECISION/STRONG/VERIFIED
```

Cada una cita evidencia **de los dos extremos por separado** y declara explicitamente que
**ninguna de las dos fuentes publica la correspondencia CIK<->LEI**: la decision se basa en
razon social, jurisdiccion y **domicilio legal coincidente**, verificado uno por uno:

| | SEC | GLEIF |
|---|---|---|
| YPF | MACACHA GUEMES 515, BUENOS AIRES | Guemes Macacha Boulevard 515, Buenos Aires |
| CEPU | AV. TOMAS ALVA EDISON 2701, BUENOS AIRES | Av. Thomas Edison 2701 Darsena, Buenos Aires |
| TGSU2 | CECILIA GRIERSON 355 26TH FLR | Cecilia Grierson 355, 26th floor, Buenos Aires |

En TGSU2 la razon social **difiere** (`GAS TRANSPORTER OF THE SOUTH INC` vs
`Transportadora de Gas del Sur S.A.`): la decision se apoyo en domicilio identico y actividad
coincidente, y eso quedo escrito en el motivo.

**GGAL NO se ratifico.** `RA999999`, `registeredAs=null`: no hay CUIT publicado, no hay
bridge que ratificar. Sigue `CANDIDATE`, sin CUIT.

## Efecto: la cadena se cerro

```
YPF    CUIT 30546689979  VERIFIED via GLEIF (RA000009)
CEPU   CUIT 33650305499  VERIFIED via GLEIF (RA000009)
TGSU2  CUIT 30657862068  VERIFIED via GLEIF (RA000010)
GGAL   sin CUIT
```

## Smoke SEC -> Identity -> CNV — 4/4

El CUIT se obtiene **solo de `identity_v1`, exigiendo bridge VERIFIED**. No se usa
`dim_entity`, ni join legacy, ni ticker, ni nombre, ni hardcode.

```
CEPU   CUIT 33650305499 -> 9305 presentaciones CNV · 0 de otros CUIT atribuidas
YPF    CUIT 30546689979 -> 0 presentaciones (CNV no las fetcheo) · aislamiento correcto
TGSU2  CUIT 30657862068 -> 0 presentaciones (idem)
GGAL   BLOQUEADO: sin bridge VERIFIED no se consulta CNV
```

Los 0 de YPF y TGSU2 **no son una falla de identidad**: `fetch_raw.cnv_presentation` solo
tiene el CUIT de CEPU. La identidad resuelve; el dato no esta.

## Banco adversario post-ratificacion — 11/11

CIK/LEI/CUIT de CEPU sobre YPF, mover un LEI o CIK ratificado, eliminar o modificar
provenance, reviewer, decision o evidencia, segundo bridge firmado por un proceso, y
ratificar GGAL con el CUIT que GLEIF no publica: **todos rechazados**.

---

## F-038 · REGISTRADO · M23 no persiste sus corridas en `market_raw_runs`

### La contradiccion, resuelta con evidencia — y mi conclusion previa era INCORRECTA

En ciclos anteriores afirme, mirando `market_raw_runs`, que **M23 no se habia ejecutado**.
Reconstruido ahora desde el filesystem:

```
outputs/docs/fase_market/scale/m23-full-2026-08-28.json
   stage             smoke-real-2026-08-28
   corrio            2026-08-28 08:16:47 -> 09:30:22 UTC  (4415 s)
   universo_total    584
   procesados        574   ·  saltados por resume  10
   por_estado        SUCCESS 567 · FAILED 7
data/raw/market/     577 directorios por instrumento · 1154 archivos desde el 27-08
                     cada uno con meta.json: run_id, config_hash, batch_hash, raw_sha256
```

**M23 SI ocurrio.** La respuesta es **C: ocurrio pero no quedo persistido en la base.**
`market_raw_runs` sigue con 20 filas `golden-*` sobre 2 instrumentos (83 y 84), del 24-25 de
agosto — son corridas del golden case, no de M23.

**Mi error de metodo:** confundi *"no esta en la tabla"* con *"no ocurrio"*. Mire una fuente
y concluí sobre el hecho. Es exactamente la inferencia que vengo señalando en otros. La
afirmacion correcta era: *"M23 no dejo rastro en `market_raw_runs`"* — que sigue siendo
cierta, y es el finding.

Los 7 FAILED son legitimos y homogeneos: `EMPTY: la fuente devolvio 0 filas` en
`DGCE.BA, SATS, CAAP.BA, VIST.BA, GGALB.BA, SUPVB.BA, YPFLUZ.BA`. Hubo 1 ronda de reintento
sobre los 7. Son instrumentos ilíquidos del panel local: coherente con el hallazgo previo de
que 12/56 BYMA casi no operan.

**impact** La bitacora de Market y su RAW estan desacoplados: el artefacto de disco tiene
`run_id`, `config_hash`, `batch_hash` y `raw_sha256` por instrumento, pero nada de eso llega
a `market_raw_runs`. Un auditor que consulte solo la base concluye —como concluí yo— que la
corrida no existio.

**required_action** (MARKET) `m6_scale` debe persistir cada instrumento en `market_raw_runs`
con su estado y sus hashes, o declarar explicitamente que el reporte JSON es el registro
canonico y que `market_raw_runs` solo cubre el golden case.

**NO se corrige en este ciclo**: Market no se toca.

---

## F-048 · El release no estaba capturado en ningún commit — **CLOSED** (2026-08-29)

`444ee1ad0e1b` ("establish core baseline", 25/08) era el punto de partida, no el
release: le faltaban 108 de los 133 archivos del manifiesto, 27 de 32 migraciones y
`engine/identity_v1.py`.

**Causa doble:** la restricción «NO hacer commits» rigió todos los ciclos y se
respetó; y `release_baseline.py` escribía `git rev-parse HEAD` bajo la clave
`git_commit` sin verificar que el worktree estuviera limpio.

**Cerrado** con el commit `25756e1a` y el tag `v1.0.0`: 148 archivos clasificados por
rol (no por extensión), 413 excluidos por decisión explícita
(`docs/release/_clasificacion.json`). Ver `docs/release/RELEASE_FREEZE_AUDIT.md`.

## F-049 · El runner de migraciones no puede aplicar sus migraciones — **OPEN**

Desde una base limpia, `engine.db.apply_migrations` falla en `008_identity_v1.sql`
con `duplicate key`: 16 de las 29 migraciones se auto-registran en
`engine.schema_migrations` con `ON CONFLICT`, y el runner las registra otra vez sin
`ON CONFLICT`. Como corre en una sola transacción, **revierte todo**.

Nunca se había visto porque esas 16 siempre se aplicaron a mano con `psql -f`. La
base homologada está correcta; llegó ahí por el camino manual.

**No afecta el sistema homologado** — no hay corrupción, pérdida ni bypass. **Bloquea
la distribución**: un `git checkout v1.0.0` no reconstruye el schema.

Registrado sin corregir. Detalle y correcciones propuestas en
`docs/review/F049_FINDING.md`.

## F-049 — **CLOSED** (2026-08-29)

Corregido eligiendo la opción B del contrato: se retiró el auto-registro de las 16
migraciones. `engine.schema_migrations` lo escribe **únicamente el runner**.

**Por qué B y no añadir `ON CONFLICT` al runner:** el auto-registro existía para
soportar `psql -f`, que **no funciona sobre base limpia** — la tabla de registro la
crea el runner. Mantenerlo era sostener una promesa que el sistema no cumple. Y
`001`–`007` y `026`–`031` nunca se auto-registraron: el patrón histórico ya había
elegido dueño único.

**Verificado desde cero** sobre base descartable: 29/29 migraciones, 0 duplicados,
estructura idéntica a la homologada (15 triggers, 27 CHECKs, 11 índices únicos).
Banco adversario **14/14**, auditoría independiente **9/9**. Base homologada
**DELTA = 0**. Suite **198/198**.

`v1.0.0` no se movió; el release distribuible es **`v1.0.1`**.
Contrato: `docs/architecture/MIGRATIONS_CONTRACT.md`.
