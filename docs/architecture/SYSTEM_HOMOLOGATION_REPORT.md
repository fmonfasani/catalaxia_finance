# SYSTEM_HOMOLOGATION_REPORT — Catalaxia

**Fecha:** 2026-08-28 · **Rol:** auditor principal de homologación
**Instancia:** `catalaxia-engine-dev` 127.0.0.1:5433 (Identity/SEC/CNV/Market) ·
`catalaxia-db` 127.0.0.1:5432 (producción, verificada en modo lectura)
**Método:** reconstrucción desde PostgreSQL, `data/raw` y artefactos. No se usaron
los reportes del implementador como evidencia.
**Nada fue modificado.** Toda prueba mutacional corrió dentro de una transacción
revertida y está documentada en la matriz, Gate 10.

---

## La respuesta

> **¿Qué parte de Catalaxia puede homologarse hoy?**
>
> Se homologa la **capa de datos**: SEC S03/S04, el backfill CIK, la ingesta CNV de
> las 3 empresas ejecutadas, la persistencia de Market, la reproducibilidad por hash
> y el ciclo de vida de corridas. Todo eso verifica de forma independiente.
>
> **No se homologa la capa de identidad como sistema de garantías**, porque su
> invariante central —*la autoridad es propiedad de la fuente, por tipo de
> identificador*— **no la hace cumplir la base de datos**. La hace cumplir Python.
>
> **Homologación integral: BLOQUEADA por F-045.**

---

## 1. Por qué la distinción importa

El estado actual de los datos **está sano**. Lo verifiqué reconstruyéndolo:

```
CIK autoritativo designando dos entidades ................  0
Entidad con dos CIK autoritativos ........................  0
Identificador huérfano ...................................  0
VERIFIED sin evidencia, fuente o autor ...................  0
Entidad MERGED/DISSOLVED con identidad autoritativa ......  0
HUMAN_DECISION firmada por un proceso ....................  0
CUIT autoritativo desde fuente no autoritativa ...........  0
Identificador cuyo tipo no coincide con su assertion .....  0
```

Ese es el resultado de homologar *un estado*. Homologar *un sistema* es otra cosa:
es afirmar que ese estado **no puede degradarse**. Y ahí es donde falla.

---

## 2. F-045 — el bloqueo

Con el rol **`catalaxia_engine`** —el que corre en producción, no admin— sobre una
entidad limpia, en una transacción revertida:

| | |
|---|---|
| CUIT autoritativo desde `LEGACY_DIM_ENTITY` (CORROBORATING) | **entró** |
| CUIT autoritativo desde `DERIVED_RULE` / `CNV_PORTAL` (DISCOVERY_ONLY) | **entró** |
| CUIT autoritativo desde `SEC_REGISTRY` (autoritativa, pero **no para CUIT**) | **entró** |
| Assertion que declara `CIK:SEC:…` reutilizada para establecer un **CUIT** | **entró** |

La última es, literalmente, una de las rutas que el encargo pide impedir:
**transformar un CIK en un CUIT**. Dos INSERT, sin privilegios especiales.

La causa está en tres líneas del trigger:

```sql
IF ... OR NEW.left_ref IS NULL THEN RETURN NEW; END IF;
tipo := split_part(NEW.left_ref, ':', 1);
```

`left_ref` es nullable, y **nada liga** `assertion.left_ref` con
`identifier.id_type`. La garantía vive en `assertion`, donde el tipo es una
*declaración*; el tipo real se decide al insertar en `identifier`, donde nadie lo
vuelve a mirar.

El control (`C1`) confirma que el trigger **sí funciona** cuando la assertion declara
honestamente qué establece. O sea: la garantía protege contra el error, no contra la
omisión.

### Ya fue eludida — F-046

No es hipotético. Las **6 re-afirmaciones del ciclo 9** (assertions 1387–1392, F-041)
tienen `left_ref = NULL` y sostienen identificadores autoritativos vigentes.
Atravesaron el trigger sin ser verificadas.

Sin daño: la fuente era `SEC_REGISTRY`, autoritativa para `CIK`. Con `left_ref`
habrían pasado igual. **Lo que falla es que nadie lo notó** — ni el escritor, ni la
auditoría independiente de ese ciclo, que sólo miraba `source_facts`.

### Por qué esto es exactamente lo que el proyecto decidió no aceptar

Ciclo 4C, instrucción textual: *«No permitir que Python sea la única barrera si la
garantía puede expresarse mediante constraint, trigger o mecanismo equivalente de
DB.»*

Hoy, para la garantía más importante del modelo, Python es la única barrera.

---

## 3. Lo que sí se homologa, y con qué evidencia

### Reproducibilidad — el gate más sólido

`hashout` recalculado **en vivo, dos veces por tabla**: 5/5 idénticos
(`parsed.facts`, `parsed.contexts`, `parsed.units`, `parsed.concepts`,
`derived.fact`). Los hashes de artefactos coinciden con el disco: 40/40 en Market,
6/6 en las re-afirmaciones de F-041.

### Provenance histórica — inmutable, verificado

Cinco variantes de ataque, todas rechazadas por la base: editar `evidence`, mutar
`source_facts`, **borrar** `source_facts`, borrar la assertion, reabrirla.

**F-042 confirmado cerrado por evidencia independiente**, no por el reporte.

### Lifecycle — sin huérfanas

**0 corridas en `RUNNING`** sobre 202. F-040 se verificó en la práctica: el dry-run
del ciclo 8 crasheó por un bug de transacción y la corrida cerró `ABORTED` con
`finished_at` sin que nadie interviniera.

### F-038 — la persistencia de M23 es correcta

**591 filas, 584 instrumentos, 577 SUCCESS** bajo `smoke-real-2026-08-28`, en 5433.
Producción tiene sólo las 10 filas `golden-*` del 24-25/08, que es **lo correcto**:
F-001 impide que Market escriba en 5432. La ausencia en producción no es una falla,
es el diseño.

### F-024 — BMA correcto

`0001347426` figura como **`CIK`/`SEC`**, autoritativo, `ACTIVE`, sobre «Macro Bank
Inc.». **No existe como CUIT.** El valor que el legacy traía en la columna
equivocada quedó bien tipado, y el conflicto histórico sigue registrado.

### F-014 — mitigado, con deuda semántica

`venue_ticker` poblado **584/584** en ambas instancias, divergente de
`ticker_canonico` en **exactamente 6** filas, todas ADR en NYSE:
`CRES→CRESY`, `TGSU2→TGS`, `PAMP→PAM`, `IRSA→IRS`, `TECO2→TEO`, `YPFD→YPF`.

La mitigación es correcta. **El defecto de origen sigue abierto**: la columna llamada
«canónico» contiene, en la fila del ADR, el ticker del *otro* venue.

---

## 4. Lo que NO es un fallo del sistema

El encargo pide distinguir. Estas cuatro cosas se ven como carencias y no lo son:

### Falta de cobertura de la fuente

**Identity → CNV = 3 elegibles** frente a 512 en Market. La brecha **es G5**: ni SEC
publica el LEI del registrante ni GLEIF publica el CIK, así que el puente CIK↔LEI
no existe en ninguna fuente primaria y cada CUIT exige una decisión humana. Los 3
que hay son las ratificaciones de Federico. **No hay defecto que corregir.**

### Limitación de producto

**Los 56 emisores BYMA sin identidad autoritativa.** Verificado: **0** CUIT
autoritativos desde `LEGACY_DIM_ENTITY`. Sin CIK no hay ancla; su CUIT legacy es
`CORROBORATING` y nunca llega a autoritativo; buscar el LEI por razón social es la
inferencia que F-024 mostró que no se puede hacer. Requiere AFIP —no automatizable— o
una decisión de producto sobre qué evidencia se acepta. **El sistema se comporta como
debe: los deja afuera.**

### Deuda histórica

**F-041: 1 assertion sin `source_facts`** — YPF, `SEC_20F`, accession
`0001193125-17-115552`. El documento 20-F nunca se archivó; sólo existe un
`index.json` que no declara el CIK. Estructurarlo sería inferir. **Dejarlo como deuda
es la conducta correcta**, y está documentado con su corroboración independiente
registrada pero deliberadamente no usada.

### Alcance no auditado

La cobertura de `parsed` frente al universo EDGAR completo, y si los 7 `EMPTY` de M23
son ausencias reales de Yahoo. Ambas requerirían ejecutar fetchers, fuera de alcance.
Se marcan `NOT_TESTED`, **no** `BLOCK`.

---

## 5. Los 7 «FAILED» de M23 — sí hay un defecto, pero no el que parece

Los 7 (`DGCE.BA SATS CAAP.BA VIST.BA GGALB.BA SUPVB.BA YPFLUZ.BA`) tienen los tres
marcadores de ausencia: `error_type='EMPTY'`, `row_count=0`, `sha256 NULL`. La fuente
respondió y no trajo filas.

Se registran como **`FAILED`**. El esquema admite `EMPTY` por CHECK y **el código
nunca lo emite** (`m2_fetch_engine.py:229` escribe `FAILED` y manda «EMPTY» al log).

Consecuencia mecánica: `m6_scale.ya_exitosos()` filtra por `SUCCESS`, así que **los 7
se re-piden en toda corrida futura del mismo stage**, sin posibilidad de éxito si la
ausencia es real.

Es **F-043**: el sistema tipifica *falta de cobertura* como *defecto técnico* — la
misma distinción que esta homologación exige hacer.

---

## 6. Alcance homologable hoy

| se homologa | condición |
|---|---|
| SEC S03/S04 | cobertura del universo EDGAR no auditada |
| Backfill CIK — 513 anclas | hereda F-045; el estado actual es correcto |
| Identity → CNV | **sólo las 3 empresas ejecutadas**; no extrapolable |
| Identity → Market | 584 instrumentos; `ticker_canonico` con deuda semántica (F-014) |
| Provenance histórica | 1 deuda declarada (F-041) |
| Reproducibilidad / hash | sin reservas |
| Lifecycle de corridas | sin reservas |
| Aislamiento de producción | sin reservas |

| **no se homologa** | |
|---|---|
| **Identity V1 como sistema de garantías** | **F-045** |
| Banco adversario / garantías de base | **F-045**, **F-044** |
| CNV a escala | no ejecutado (G5) |
| Los 56 BYMA | limitación de producto, no defecto |

---

## 7. Qué impide declarar homologación integral

**Una sola cosa: F-045.** Mientras la autoridad por tipo de identificador dependa de
que quien escribe recuerde poblar `left_ref`, no puede afirmarse que el sistema
impide inventar un CUIT ni transformar un CIK en CUIT. Hoy no lo impide: lo evita.

Los otros cuatro hallazgos (F-044, F-043, F-046, F-047) son acotados y documentados;
ninguno bloquea por sí solo.

**Ninguno fue corregido.** Registrados en `SYSTEM_HOMOLOGATION_BLOCKERS.md`, y me
detengo acá.

---

## 8. Nota de método

En la primera pasada del banco adversario, **5 ataques se rechazaron por una garantía
distinta de la que declaraban** — el objetivo ya tenía un identificador de ese tipo, o
el valor no pasaba `ck_formato_identificador`. Rehechos sobre una entidad limpia y con
un CUIT válido por módulo 11 (`30999999995`), **5 de ellos entraron**.

Sin ese rehacer, este informe habría declarado `PASS` en la ruta «inventar CUIT», por
la razón equivocada. Es la misma lección que el ciclo 8 dejó escrita, y aplicada acá
evitó certificar un sistema que no lo merece todavía.

Ningún `PASS` de este informe se apoya en cantidad de tests verdes.
