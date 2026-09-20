# ENGINE_INTEGRITY_GATE — F-054 / F-055

**Fecha:** 2026-09-01 · **Rol:** Engine Integrity Auditor + Implementer
**Alcance:** exclusivamente la cadena SEC → S02 → S03 → `parsed` → S04 → `derived`
**Base:** `catalaxia` (5433), 8 emisores · **Sin commits** · Market y CNV intactos

---

# DICTAMEN: **PASS_WITH_WARNINGS**

**F-054 = CLOSED.** **F-055 = CLOSED.**

Las dos garantías están demostradas causalmente: revertidas por separado, cada
defecto reaparece con la firma que le corresponde, y restauradas desaparece. La
auditoría independiente reconstruye los invariantes con SQL propio y da limpio
sobre 135.077 punteros de provenance.

Los *warnings* son **tres hallazgos nuevos**, registrados y no corregidos, y
**dos limitaciones de evidencia**. Ninguno reabre F-054 ni F-055.

---

## 1. F-054 — la provenance de un emisor apuntaba a hechos de otro

### Causa raíz

`s03_parse_ypf.py` hacía, antes de parsear:

```python
for table in PARSED_TABLES:          # las OCHO tablas de `parsed`
    cur.execute(f"DELETE FROM {table}")
cur.execute("SELECT setval(pg_get_serial_sequence('parsed.facts','fact_id'), 1, false)")
```

Con un emisor era un staging correcto. Con dos, cada corrida borraba la
provenance del anterior **y reutilizaba sus ids**, de modo que los
`source_fact_ids` que `derived.fact` ya tenía guardados pasaban a resolver
contra filas de otra empresa. No quedaban colgados: **devolvían una fila ajena,
en silencio**.

### Por qué ningún gate lo vio

`C-S04-005` compara `derived.fact WHERE run_id = <corrida actual>` contra
`parsed.facts WHERE run_id = <S03 actual>`. Ambos lados acotados a la corrida en
curso. Dentro de una corrida todo cierra; la corrupción aparece en la siguiente.

> El control verificaba la ejecución, no el estado del sistema.

### Corrección

| garantía | qué hace | dónde |
|---|---|---|
| **G1** · borrado con alcance | `DELETE FROM parsed.facts WHERE cik = %s`; `pre_xbrl_filings` ídem; las otras seis por `run_id` de corridas previas del mismo CIK | `s03_parse_ypf.py` |
| **G2** · la secuencia no se reinicia | se **eliminó** el `setval(…, 1, false)` | ídem |
| **G3** · insumo filtrado | `find_s02_input_run(engine, cik)` con `d.cik = :cik` | ídem |
| **G4** · invariante del gate | `C-S04-002` pasa de «una sola corrida» a «ningún CIK mezcla corridas» | `s04_normalize.py` |

Sin schema, sin migraciones: `git status -- migrations/` está vacío.

### Evidencia — estado actual

```
punteros de provenance verificados (todos los elementos del array):  135.077
  que resuelven a un hecho de OTRA empresa ..............................  0
  que quedan colgados ...................................................  0
  que cruzan a otro accession ...........................................  0
  que cambian de concepto (qname) .......................................  0
rangos de fact_id por emisor ........................ 8 emisores, 0 solapes
secuencia de fact_id ................. last_value 232.357 = max(fact_id)
fact_id repetidos .....................................................  0
corrida S02 elegida por CIK sin emisores ajenos ......... 8/8 verificados
```

### Mutación — qué invariante bloquea qué

El banco no se conforma con «falló»: revierte **cada garantía por separado** y
exige la firma correspondiente.

| escenario | predicción | resultado real | veredicto |
|---|---|---|---|
| **G1 + G2** (código actual) | re-parsear CEPU no toca a los otros 7 | `ajenos=0 colgados=0` | OK |
| **sin G1 ni G2** | contaminación | **2.791 punteros de CEPU caen en hechos de TGS** | OK |
| **sin G1, con G2** | pérdida, no mezcla | `ajenos=0 colgados=135.077` | OK |
| **con G1, sin G2, franja libre** | ~~la PK rechaza~~ | **no falla**: rc=0, la PK no interviene | ver §1.1 |
| **con G1, sin G2, rangos que se pisan** | la PK rechaza | `rc=1`, `facts_pkey` violada | OK |
| escenario histórico | un replace-all de GGAL no cambia el dueño de un `fact_id` de YPF | `0000904851 → 0000904851` | OK |

**Reproducción fiel del defecto histórico:** una sola corrida mutada no alcanza.
Hay que recorrer la secuencia entera — A parseado con la secuencia en 1, S04 fija
sus punteros en 1..N, B parseado reiniciando otra vez, y entonces los punteros de
A caen en filas de B. Así se obtuvieron los 2.791.

### 1.1 · Una premisa previa era falsa, y se corrige

Yo había afirmado: *«con G1 sin G2, la PK rechaza el id reutilizado; el fallo es
ruidoso»*. **Es falso en general.**

Los `fact_id` vivos de esta base arrancan en **12.841**, y
`punteros_bajo_12841 = 0`. Al reiniciar la secuencia con el borrado acotado, los
ids nuevos caen en una franja libre: **sin choque, sin error**, y con el
invariante *«un `fact_id` designa un hecho para siempre»* ya roto para las
corridas futuras.

**La PK protege sólo donde los rangos se pisan.** Forzando el solape
(`setval` a 15.632) la violación aparece, `rc=1`. La seguridad la da **G2**, no
la clave primaria.

### Auditoría independiente

`scripts/engine/audit_f054_f055.py` — no importa `engine.*` ni ningún módulo del
implementador; habla con PostgreSQL por `psql` y reconstruye cada invariante con
SQL propio escrito desde el contrato. **16/16 controles OK, 0 críticos en rojo.**

Una corrida intermedia dio 15/16: el rojo era `0.1 · ningún pipeline en vuelo`,
porque **otra sesión estaba corriendo CNV** en paralelo. Es correcto que falle —
el auditor se niega a declarar baseline limpio mientras otro proceso escribe— y
al terminar esa corrida el control pasó. La medición definitiva se tomó con
`RUNNING = 0`.

### Impacto residual

**F-059** (§4): S04 normaliza el último checkpoint de S03 sin filtrar por CIK.
La corrección de F-054 convirtió la contaminación en pérdida recuperable, pero
la ventana entre S03 y S04 **no se cierra sola** si se parsean varios emisores
antes de normalizar.

---

## 2. F-055 — contextos equivalentes declarados contradictorios

### Causa raíz

SEC publica dos representaciones del mismo filing: el documento inline (`.htm`)
y la instancia extraída (`_htm.xml`). S03 parsea ambas, y cada una serializa la
lista de dimensiones del contexto **en distinto orden**. La comparación era
`dimensions::text`, sensible al orden.

`contextos_deduplicados()` no se limita a reportar lo contradictorio: **lo
descarta**. Un hecho cuyo contexto no entra en el mapa no llega a
`derived.fact`.

Un segundo nivel, más fino: las dimensiones **tipadas** guardan el fragmento XML
crudo, que arrastra los `xmlns` vigentes en ese punto del documento — distintos
dentro de un XHTML que dentro de una instancia XBRL. El mismo valor tipado
(`2024-09-29` en AAPL) se serializaba distinto.

### Corrección

Canonizar antes de comparar, en los dos lugares que comparaban:
`contextos_deduplicados()` y el control `C-S04-003`.

- la lista de dimensiones se **ordena** (es un conjunto, no una secuencia);
- del fragmento tipado se **quitan los `xmlns`** antes de comparar.

Es el mismo criterio que `hashout-v2` ya había adoptado para las filas y que no
se había aplicado acá.

### Evidencia

```
contextos contradictorios con comparación INGENUA .................  3.562
contextos contradictorios con comparación CANÓNICA ................      0
hechos que dependen de un contexto descartable ....................      0

conservación — un hecho derivado por grupo canónico de parsed:
  cik            grupos parsed     derived    diferencia
  0000320193             2.085       2.085             0
  0000789019             3.460       3.460             0
  0000904851            47.930      47.930             0
  0000931427             7.301       7.301             0
  0001045810             2.505       2.505             0
  0001114700            14.111      14.111             0
  0001347426             8.737       8.737             0
  0001717161             2.660       2.660             0
```

**El control de conservación es el que más vale**: no depende de ningún conteo
declarado por el pipeline. `derived.fact` debe tener exactamente un hecho por
grupo `(cik, accession, qname, context_id, unit_ref)` de `parsed.facts`. Si la
deduplicación pierde algo, la diferencia deja de ser cero; si duplica, también.

Esto responde la pregunta abierta sobre GGAL: el salto de **9.196 → 14.111**
hechos **no es duplicación artificial**. 14.111 es exactamente el número de
grupos canónicos distintos; los 4.915 que faltaban eran los que se descartaban.

### Banco adversario — atacado en las dos direcciones

Una canonización que absorbe de más es peor que el defecto que vino a arreglar.

| # | ataque | esperado | real |
|---|---|---|---|
| A1 | permutar el **orden** de las dimensiones | no debe conflictuar | equivalentes ✓ |
| A2 | duplicado **idéntico** | no debe conflictuar | equivalentes ✓ |
| A3 | cambiar un **miembro** de dimensión | debe conflictuar | conflicto ✓ |
| A4 | cambiar el **período** (+1 día) | debe conflictuar | conflicto ✓ |
| A5 | cambiar **duration por instant** | debe conflictuar | conflicto ✓ |
| A6 | cambiar la **entidad** del contexto | debe conflictuar | **equivalentes ✗** |
| A7 | **agregar** una dimensión | debe conflictuar | conflicto ✓ |

**6 de 7 correctos.** A6 es el hallazgo nuevo **F-060**.

### Impacto residual

**F-060** (§4): la comparación omite `scheme` e `identifier`. Cero casos reales
hoy, medido.

---

## 3. Tests nuevos

Antes de este ciclo, `grep -rl "F-054\|F-055" tests/` devolvía **vacío**. Las
correcciones no tenían red de seguridad.

| archivo | tests | qué cubre |
|---|---:|---|
| `tests/test_f054_aislamiento_emisores.py` | 13 | invariantes del sistema + las tres combinaciones de garantías, en schema temporal propio |
| `tests/test_f055_equivalencia_contextos.py` | 13 | invariantes + los siete ataques, en tabla temporal sembrada con un contexto real |

```
25 passed, 1 xfailed
```

El `xfail` es `test_cambiar_la_entidad_SI_deberia_generar_conflicto`, marcado
`strict=True` con el número de F-060: si alguien lo corrige, el test pasa a
**XPASS y falla**, que es la señal para sacarlo de la lista de deuda en vez de
dejarlo mintiendo.

**Los tests causales identifican la garantía, no observan que «algo falló»:**

```
test_sin_G1_ni_G2_reaparece_la_CONTAMINACION     -> ajenos > 0, colgados == 0
test_sin_G1_pero_con_G2_hay_perdida_no_mezcla    -> ajenos == 0, colgados > 0
test_con_G1_pero_sin_G2_la_PK_rechaza_el_id      -> IntegrityError
```

Más dos guardias de código que caen antes de que nadie corra el pipeline si
reaparece el `DELETE` sin predicado, el `setval`, o la comparación ingenua.

---

## 4. Findings nuevos

| # | qué | severidad | estado |
|---|---|---|---|
| **F-060** | la comparación de contextos ignora `scheme` e `identifier` | baja–media | REGISTRADO, no corregido · 0 casos reales medidos |
| **F-059** | S04 normaliza el último checkpoint de S03 sin filtrar por CIK | media | REGISTRADO, no corregido · 0 punteros colgados hoy |
| **F-061** | el conteo congelado de `test_f038` quedó obsoleto | baja | ver §6 |

Los tres se registraron **antes** de tocar nada, como pide la regla del ciclo.
Ninguno se corrigió: F-060 y F-059 cambian el comportamiento de la
deduplicación o del encadenamiento de etapas, y eso exige re-parsear el universo
y volver a medir la conservación — no corresponde meterlo dentro de este gate.

### Nota de numeración

El hallazgo de contextos se registró **dos veces con un número que otro
workstream tomó en paralelo**: primero F-056 (allí: duplicación de listas de
tags en los scripts de inventario), después F-058 (allí: producto cartesiano en
el banco adversario de ratios). También existe un F-057 ajeno (el separador
`\x1f` en los auditores). Ambos documentos míos fueron sobrescritos. Quedó
finalmente como **F-060**, y se reclama **F-059** para el de encadenamiento
S03→S04.

**Hay dos sesiones operando el mismo repositorio simultáneamente.** Mientras
esta auditoría corría, la otra ingirió los ratios de 8 empresas, corrió CNV y
corrió Market. La numeración de findings no tiene mecanismo de exclusión: va a
volver a chocar. Conviene reservar rangos por workstream, o prefijarlos
(`ENG-`, `RAT-`), antes del próximo ciclo en paralelo.

---

## 5. Idempotencia

Tres corridas de `S03 → S04` sobre CEPU en base descartable, comparando
**contenido**, no filas. Los `fact_id` cambian entre corridas por diseño —esa es
la garantía G2— así que un digest que los incluyera daría distinto siempre sin
significar nada. Lo que debe ser estable es el contenido y la **forma** de la
provenance: para cada hecho derivado, el contenido de los hechos que lo
respaldan, no sus ids.

```
baseline en la copia : parsed=2.791  derived=2.660  ids 12841-15631
corrida 1            : parsed=2.791  derived=2.660  ids 232358-235148
corrida 2            : parsed=2.791  derived=2.660  ids 235149-237939
corrida 3            : parsed=2.791  derived=2.660  ids 237940-240730
```

| control | resultado |
|---|---|
| **E0** · el re-parseo reproduce lo que ya estaba en la base | `2.791→2.791`, `2.660→2.660` |
| **E1** · contenido de `parsed.facts` estable | `0dabd424…` = `0dabd424…` |
| **E1** · contenido de `parsed.contexts` estable | `7196bf82…` = `7196bf82…` |
| **E1** · contenido de `derived.fact` estable | `e65aa058…` = `e65aa058…` |
| **E1** · **forma de la provenance** estable | `2438fbb4…` = `2438fbb4…` |
| **E2** · sin crecimiento espurio | `2.791 = 2.791`, `2.660 = 2.660` |
| **E3** · sin contaminación ni colgados en ninguna corrida | `0/0, 0/0, 0/0` |
| **E4** · los `fact_id` **avanzan** en cada corrida | 232358 → 235149 → 237940 |
| **E5** · la base homologada no cambió | `135077\|88789\|8` idéntica |

**9/9.**

**E0 es el control que zanjó una duda real.** Una primera versión de esta prueba
reportó `parsed = 11.821` para CEPU contra 2.791 en la base, lo que parecía
no-determinismo. No lo era: la métrica contaba **líneas de salida de `psql`**, y
116 de los 2.791 hechos de CEPU llevan saltos de línea en `value_text`
(text-blocks XBRL), de modo que 2.791 filas producen 20.928 líneas. Corregido el
conteo a `count(*)` y agregado E0, el re-parseo reproduce el contenido exacto.

La copia se hace por `pg_dump`, no por `CREATE DATABASE … TEMPLATE`: la segunda
exige que nadie esté conectado a la plantilla, y con otro workstream operando el
mismo repositorio eso no se puede garantizar. `pg_dump` da un snapshot
transaccionalmente consistente sin pedir exclusividad.

---

## 6. Regresiones — suite completa

```
248 passed · 4 failed · 1 skipped · 1 xfailed
```

| test que falla | clasificación | causa |
|---|---|---|
| `test_f038::test_la_corrida_esta_registrada` | **TEST OBSOLETO** | espera 591 filas en `market_raw_runs`, hay **601**: otra sesión corrió Market. El conteo está congelado en el test |
| `test_f038::test_market_no_escribe_en_produccion` | **TEST OBSOLETO** | misma causa, mismo conteo |
| `test_f038::test_el_hash_de_la_base_es_el_del_artefacto_en_disco` | **LIMITACIÓN DE EVIDENCIA** | `data/raw/market/` se perdió en el incidente del 2026-08-31; los 577 hashes siguen en la base |
| `test_f040_lifecycle_c3[…_persist_inventory]` | **INFRAESTRUCTURA** | colisión con la corrida CNV de la otra sesión. **Pasa aislado: 3 passed** |

**Ninguna es regresión real, y ninguna toca el Engine.** No se modificó ningún
test para conseguir verde: los conteos congelados de `test_f038` pertenecen a
Market, fuera del alcance de este ciclo, y se registran como **F-061**.

---

## 7. Limitaciones de evidencia

1. **La reproducción histórica es sobre una copia, no sobre el estado original.**
   El baseline que produjo F-054 ya no existe: fue reparseado. La reproducción
   recrea la *secuencia* del defecto sobre una copia actual, y obtiene la misma
   firma (2.791 punteros cruzados). No es el incidente original: es su mecanismo.

2. **Dos sesiones operando el mismo repositorio.** Durante este ciclo otra
   sesión ingirió ratios, corrigió F-056/F-057, corrió CNV y corrió Market. La
   base cambió bajo la auditoría. Los controles de F-054/F-055 se tomaron con
   `parsed`/`derived` estables (huella `135077|88789|8` verificada antes y
   después del banco), pero el control `0.1` del auditor y una falla de la suite
   son consecuencia directa de esa concurrencia.

3. **Docker Desktop se cayó a mitad del ciclo.** No fue el contenedor: el daemon
   se detuvo y `catalaxia-engine-dev`, que **no está definido en
   `docker-compose.yml`**, no tenía política de reinicio y quedó abajo. Al
   volver, el reenvío de puertos del host quedó degradado: el socket TCP en
   `127.0.0.1:5433` aceptaba la conexión pero el handshake de PostgreSQL no
   completaba, y **los 26 tests pasaron a 22 errores de `connect timeout`** con
   la base intacta y 6 conexiones de 100 en uso. `docker exec psql` —socket
   interno— funcionaba todo el tiempo.

   Se resolvió reiniciando el contenedor: **25 passed, 1 xfailed en 12,5 s**.
   Vale registrarlo porque el modo de falla es engañoso: parece un defecto de
   los tests o de la base, y no es ninguno de los dos. La medición se repitió
   después de restaurar la conectividad; ningún resultado de este gate proviene
   de la ventana degradada.

---

## 8. Blockers restantes

**Para el gate de Engine: ninguno.** F-054 y F-055 cierran.

Para la homologación general, que **no** es el alcance de este ciclo:

| # | blocker | por qué |
|---|---|---|
| 1 | **F-059 sin corregir** | la ventana entre S03 y S04 depende de que el operador respete el orden; nada en el código lo obliga |
| 2 | **F-060 sin corregir** | la regla de contextos no distingue por entidad; latente, no activo |
| 3 | **`data/raw/market/` perdido** | impide verificar 577 hashes de F-038 contra disco |
| 4 | **Contratos desactualizados** | `S04_CONTRACT.md` no menciona ni el borrado por CIK, ni la canonización de contextos, ni la dependencia de orden de F-059 |

El punto 4 es el más barato de cerrar y el que más deuda evita: hoy las tres
garantías nuevas viven en comentarios de código y en estos findings, no en el
contrato contra el cual se audita.

---

## 9. Evidencia

| archivo | contenido |
|---|---|
| `outputs/docs/auditoria/F054_F055_PLAN.md` | qué se iba a verificar, escrito **antes** de medir |
| `outputs/docs/auditoria/f054_f055_auditoria.json` | 16 controles independientes |
| `outputs/docs/auditoria/f054_f055_mutacional.json` | 15 escenarios mutacionales y adversarios |
| `outputs/docs/auditoria/idempotencia.json` | fase E |
| `docs/review/F054_FINDING.md`, `F055_FINDING.md` | causa raíz y corrección |
| `docs/review/F060_FINDING.md`, `F059_FINDING.md` | hallazgos nuevos |
| `tests/test_f054_aislamiento_emisores.py`, `test_f055_equivalencia_contextos.py` | 26 tests |

Scripts: `audit_f054_f055.py` (solo lectura, SQL propio) ·
`mut_f054_f055.py` (base descartable) · `idempotencia_engine.py` (base
descartable, copia por `pg_dump`).

La base homologada no se modificó: huella `135077|88789|8|47684` idéntica antes
y después del banco mutacional.
