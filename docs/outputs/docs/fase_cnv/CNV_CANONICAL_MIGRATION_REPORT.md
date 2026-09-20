# CNV CANONICAL — INFORME DE MIGRACIÓN CONTROLADA

**Fecha:** 2026-09-02
**Worktree:** `D:/Software Development/Porfolio/catalaxia-cnvmig` · rama `feat/cnv-canonical` · base `e9d794b`
**Base de datos:** `cnvmig` (fixture aislado, puerto 5433)
**Base homologada `catalaxia`:** **no modificada** — prueba en §7
**Caso de regresión obligatorio:** Metrogas S.A. · CUIT 30657863676 · FY2025

---

## 1 · Qué hacía falta y por qué

Metrogas no tiene CIK. No lo tiene, no se puede inventar, y la capa canónica
entera estaba claveada por `cik`. Ese era el bloqueo: no un problema de
cobertura sino de identidad.

El detalle que lo hacía peligroso, medido en `CNV_CANONICAL_IDENTITY_GATE.md`
§3 y reproducido aquí como test: con `cik` NULL, **los dos operadores fallan**.

```
NULL <>               NULL   ->  NULL    ->  el WHERE no se cumple  ->  PASA
NULL IS DISTINCT FROM NULL   ->  false   ->  el WHERE no se cumple  ->  PASA
```

La guarda de F-061 —la que impide que un hecho de un emisor entre al ratio de
otro— hubiera dejado pasar hechos ajenos **en silencio** en cuanto conviviera
más de un emisor sin CIK. Cambiar `<>` por `IS DISTINCT FROM` no arregla nada:
dos NULL siguen viéndose iguales.

**La solución no es el operador. Es la columna.**

## 2 · La columna que ya existía

`parsed.facts.entity_id` guardaba `CIK:0000021344` desde S03: namespaced, con
el registro de origen adentro. La escribía el parser y **no la leía nadie** —
ni el motor de ratios, ni hashout, ni las guardas. Sobre las 225.475 filas SEC:

```
entity_id = 'CIK:' || cik    ->    225.475 / 225.475    ·    0 desviaciones
```

Para SEC el cambio de columna es una identidad matemática: no cambia ningún
resultado. Para CNV es la única forma de distinguir dos emisores sin CIK. Por
eso la migración es barata: la abstracción ya estaba, faltaba usarla.

---

## 3 · FASE 1 — Guarda F-061 generalizada

### Estado ROJO previo (obligatorio)

Antes de aplicar nada, la prueba adversarial falló como tenía que fallar:

```
3 failed  ·  T3 (dos cik NULL con entity distinto)
             T4 (entity_id NULL)
             T5 (mutación: sin la cláusula, el ajeno vuelve a pasar)
```

### El cambio

**`migrations/engine/034_cnv_canonical_entity_id.sql`** — aplicada solo a `cnvmig`:

| # | Qué hace | Por qué así |
|---|---|---|
| 1 | `derived.fact.entity_id` NOT NULL, backfill `'CIK:'\|\|cik` | espejo de `parsed.facts`; la equivalencia está demostrada |
| 2 | `cik` deja de ser NOT NULL, **pero** `ck_cik_obligatorio_en_xbrl` | un hecho SEC sin CIK sigue siendo un error, dicho explícito en vez de librado a la nulabilidad |
| 3 | `ck_entity_id_namespaced`: `^(CIK\|CUIT\|LEI\|CNV):[A-Za-z0-9._-]+$` | sin esto un `entity_id` vacío pasaría y la guarda compararía basura contra basura |
| 4 | `ck_entity_id_coherente_con_cik` | impide actualizar una representación y no la otra |
| 5 | `derived.v_fact_pertenencia` recreada sobre `entity_id` | `CREATE OR REPLACE` no renombra columnas de vista |

**`scripts/engine/ratio_inputs.py`** — `INVARIANTE_PERTENENCIA` y
`GUARDA_PERTENENCIA` pasan de `cik` a `entity_id`, con `IS DISTINCT FROM` en
las tres comparaciones. Es el único punto de selección de insumos, así que el
cambio alcanza a todo el motor.

### Estado VERDE

`tests/test_f061_entity_ownership.py` — 8 tests:

| Test | Verifica |
|---|---|
| T1 | `entity_id` igual → permite (SEC y CNV) |
| T2 | `entity_id` distinto → bloquea |
| **T3** | **dos `cik` NULL, `entity_id` distinto → bloquea** ← el caso que motiva todo |
| T4 | `entity_id` NULL → bloquea, no pasa en silencio |
| **T5** | **mutación:** con la guarda vieja (`cik <>`) el ajeno **debe** pasar |
| T5b | `IS DISTINCT FROM` sobre `cik` tampoco alcanza |
| T6 | regresión SEC: las dos guardas dan lo mismo sobre los hechos reales |
| **T7** | contracara de T6: ningún hecho no-SEC finge un `CIK:` |

T5 es el que sostiene el resto: si quitar la cláusula **no** reabriera el
agujero, la protección la estaría dando otra condición y T3 no probaría lo que
dice. T7 existe para que acotar T6 por `source_kind` no sea una forma elegante
de dejar de mirar.

El escenario aísla la comparación de identidad: los cinco hechos comparten
`accession_number` y `qname`, así que lo único que puede bloquear es el emisor.

Más `tests/test_f061_ownership.py` (6, adaptado al nuevo esquema): **14/14**.

---

## 4 · FASE 2 — Adaptador CNV → canónico

**`scripts/engine/c4_cnv_adapter.py`**. Decisiones y su fundamento:

| Campo | Valor | Por qué |
|---|---|---|
| `cik` | **NULL** | no existe; inventarlo sería falsificar identidad |
| `entity_id` | `CUIT:30657863676` | namespaced, igual que `CIK:` en SEC |
| `entity_key` | `EY9TRR9RPRVSV916PD0CB9Z93NT` | ULID derivado de `sha256("CUIT:<cuit>")`; determinista |
| `qname` | `cnv:<concepto>` | prefijo propio: no se finge taxonomía XBRL |
| `context_id` | `<tipo_balance>@<period_end>` | el perímetro es dimensión de primera clase, no un atributo |
| `measure` | `iso4217:ARS` de `dim_entity.moneda_funcional` | **no** el `'7'` que devuelve `extraer_moneda()` |
| `decimals` | `-6 / -3 / 0` según escala | semántica XBRL nativa: potencia negativa de diez |
| `source_kind` | `CNV_EEFF` | discrimina de `XBRL%` en los CHECK |
| `fact_key` | `sha256(entity_key\|accn\|qname\|ctx\|unit)` | **sin la escala**, según P1 del gate previo |

### Sobre el valor y la escala

`cnv_estados_norm.valor` ya viene en magnitud absoluta: `Assets = 1.511.087.000.000`
con `escala = 1.000.000` (el documento reportó 1.511.087 en millones). Guardar
ese valor con `decimals = -6` **es** la semántica XBRL correcta: el número es
exacto al millón. La escala queda preservada como provenance sin duplicar el
dato ni entrar en la clave.

### Guardas del adaptador

- se niega a correr si `db_name == "catalaxia"`
- se niega a correr contra producción (EXT-010)
- omite documentos sin RAW en disco: sin archivo no hay `source_hash`, y
  `parsed.facts` lo exige

### El censo — lo que se decidió no callar

La primera versión filtraba en el `WHERE` las filas sin `tipo_balance` y
reportaba 2.697 como si fuera el total. Eran 2.747. **50 filas desaparecían sin
que nada las nombrara**, y una fila descartada por un `WHERE` es indistinguible
de una fila que nunca existió: así la conservación deja de ser verificable.

Ahora `leer_cnv()` devuelve `(admitidas, censo)`, cada fila del origen cae en
exactamente un balde, y un `assert` verifica que el censo cierre:

```
filas CNV en origen: 2,747
  admitidas               2,697
  EXCLUIDAS · sin perimetro declarado  50  (1 documento/s)
```

Las 50 son **un solo documento** cuyo perímetro no se puede determinar.
Asignarlas a INDIVIDUAL o a CONSOLIDADO sería inventar de qué estado vienen.
Se excluyen y se declara.

### Idempotencia

La primera versión chocaba contra la PK de `fact_key` en la segunda corrida.
Chocar es *seguro* (la transacción revierte, verificado: 2.697/2.697 intactos)
pero no es *idempotente*. Ahora el adaptador censa el estado previo y clasifica:

```
2ª corrida:  parsed.facts insertados: 0  ·  reusados: 2,697
             derived.fact insertados: 0  ·  sin cambio: 2,697
```

Y no es un "saltear a ciegas" — mutando un valor a mano:

```
CONFLICTO: 1 hechos ya presentes con OTRO valor bajo la misma fact_key.
           No se sobrescriben.
  002c73de3b6d  cnv:Receivables CONSOLIDADO@2021-09-30  ...001 -> ...000
```

Reporta y no pisa. Ver la advertencia W-3 en §6.

---

## 5 · FASE 3 y 4 — Conservación y hashes

Verificado por un auditor independiente (`scripts/engine/c4_auditoria_cnv.py`)
que **no importa el adaptador**: vuelve al SQLite y a los HTML en disco y
reconstruye por su cuenta lo que la capa canónica debería contener.

```
A · CONSERVACION
  OK  sin perdidas en parsed                    2,697 de 2,697
  OK  sin perdidas en derived                   2,697 de 2,697
  OK  biyeccion origen <-> derived              multiplicidad identica
  OK  0 duplicados indebidos                    cada clave una vez
  OK  0 colisiones de fact_key                  2,697 hechos -> 2,697 claves
  OK  0 hechos sin respaldo en el origen        ninguno

B · FIDELIDAD DEL DATO
  OK  valor normalizado exacto                  0 desvios sobre 2,697
  OK  escala preservada como decimals           0 desvios
  OK  period_end exacto                         0 desvios
  OK  concepto exacto                           0 desvios
  OK  moneda ISO correcta                       iso4217:ARS / ars / ARS
  OK  perimetro de primera clase                INDIVIDUAL 1.397 · CONSOLIDADO 1.300
  OK  0 hechos con perimetro ambiguo            0 casos

C · IDENTIDAD
  OK  entity_id unico y namespaced              CUIT:30657863676
  OK  cik NULL: no se invento ninguno           0 con cik
  OK  0 hechos CNV apuntando a evidencia SEC    0
  OK  identidad con identificador autoritativo  1

D · HASHES Y TRAZA AL ARCHIVO
  OK  cada documento apunta a un archivo        56 documentos · 0 sin archivo
  OK  sha256 recomputado HOY coincide           56/56
  OK  un documento, un hash                     0 inconsistentes
  OK  n_fuentes coincide con la evidencia       0 desvios

E · F-061 · PERTENENCIA
  OK  0 violaciones · CNV                       0 sobre 2,697
  OK  0 violaciones · SEC                       0 sobre 133,902
  OK  la vista canonica no reporta violaciones  0 filas en rojo
```

**24 verificaciones OK · 0 fallas · 1 aviso** (las 50 filas declaradas).

---

## 6 · Lo que se corrigió y lo que quedó abierto

### Corregido durante la migración

**El motor de ratios crasheaba con un emisor sin CIK.** `ciks_del_universo()`
hacía `SELECT DISTINCT cik FROM derived.fact` — que ahora devuelve NULL. Se
acotó a `cik IS NOT NULL`, con el motivo escrito en el código: el motor está
homologado solo para SEC (sus cadenas de fallback son tags us-gaap/ifrs y
`derived.ratio.cik` es NOT NULL). Traer un emisor CNV ahí no sería ampliar la
cobertura: sería producir un ratio que nadie homologó.

**Secuencias sin resetear tras el `COPY` masivo** del fixture: `assertion_id`,
`identifier_id`, `fact_id`, `stage_runs.id`. Reseteadas las 21.

**`identity_v1.identifier` exige `id_namespace`** y el trigger F-045 exige que
el `left_ref` de la assertion sea `CUIT:AFIP:<valor>`, no `CUIT:<valor>`.

### Advertencias abiertas

**W-1 · Re-expresión IAS 29 no tiene desempate.** `fact_key` incluye el `accn`,
así que si un balance posterior re-expresa un período anterior, el hecho
re-expresado entra como un **segundo** hecho en vez de suceder al primero, y
nada declara cuál manda. Hoy no ocurre —verificado: `(concepto, period_end,
tipo_balance)` nunca aparece en más de un `accn`, 0 casos— pero el diseño no lo
previene. Debe resolverse antes de ampliar cobertura.

**W-2 · Los 14 conceptos `CNV_*` y `EPS_*` llevan `measure = iso4217:ARS`** y no
son montos en pesos: son ratios adimensionales publicados por la CNV. Entraron
con la unidad del emisor. No afecta la conservación pero es una unidad
incorrecta que hay que separar antes de exponerlos.

**W-3 · El adaptador es INSERT-only.** Ante un valor cambiado bajo la misma
clave reporta CONFLICTO y no escribe. Es lo correcto para una migración; no
alcanza para un job de actualización.

**W-4 · El worktree quedó desfasado del árbol de trabajo principal.** Ambos en
`e9d794b`, pero el repo principal tiene sin commitear ~66 líneas nuevas en
`s03_parse_ypf.py`, cambios en `s04_normalize.py` y 5 archivos de test
(`test_cnv_authority`, `test_f050_*`, `test_f051_*`, `test_f054_*`,
`test_f055_*`) que ejercitan ese código. Se copiaron al worktree para probarlos
y se retiraron: fallan por versión, no por la migración (evidencia en
`CNV_CANONICAL_VALIDATION_REPORT.md` §4). **Antes de integrar hay que rebasar.**

---

## 7 · La base homologada no se tocó

```
                migraciones   034   entity_id   hechos CNV   cik nullable
  catalaxia          34         0        0            0           NO
  cnvmig             35         1        1        2,697          YES
```

`catalaxia` no tiene la migración 034, no tiene la columna `entity_id` en
`derived.fact`, no tiene un solo hecho CNV y su `parsed.facts.cik` sigue siendo
NOT NULL. Las únicas operaciones contra ella fueron `pg_dump` de lectura para
completar el fixture.

---

## 8 · Archivos

| Archivo | Estado |
|---|---|
| `migrations/engine/034_cnv_canonical_entity_id.sql` | nuevo · aplicado solo a `cnvmig` |
| `scripts/engine/ratio_inputs.py` | guarda migrada a `entity_id` |
| `scripts/engine/ratio_engine.py` | universo acotado a `cik IS NOT NULL` |
| `scripts/engine/c4_cnv_adapter.py` | nuevo · adaptador CNV → canónico |
| `scripts/engine/c4_auditoria_cnv.py` | nuevo · auditor independiente |
| `tests/test_f061_entity_ownership.py` | nuevo · 8 tests (T1–T7) |
| `tests/test_f061_ownership.py` | fixture adaptado a `entity_id` |
| `tests/test_ratio_engine_ev_sales.py` | fixture adaptado a `entity_id` |

Nada de esto está en la base homologada ni en la rama `main`.
