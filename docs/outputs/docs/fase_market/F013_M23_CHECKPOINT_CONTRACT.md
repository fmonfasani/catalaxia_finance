# F-013 (recorte MARKET) — Contrato de checkpoint/reanudación de M23

**Estado: DISEÑADO, IMPLEMENTADO, VALIDADO EMPÍRICAMENTE Y AUDITADO INDEPENDIENTEMENTE
— veredicto `ACCEPT`. M23 NO se ejecutó contra instrumentos reales.** 2026-08-28, rama
`fix/ttm-ratios-cnv`. Ver §9 para el veredicto completo y las limitaciones nombradas que
quedan documentadas (no bloqueantes).

## 0 · Alcance — qué parte de F-013 resuelve este documento

`docs/review/FINDINGS.md` F-013 ("Tres convenciones divergentes de checkpoint") es
`workstream GLOBAL`: pide alinear (o documentar como distintos) el significado de
"checkpoint" en SEC, CNV y MARKET. **Este documento NO hace eso.** El pedido de esta
sesión fue específicamente el contrato de checkpoint/reanudación de **M23** (el
escalamiento por lotes de Market) — una precondición necesaria antes de correr el batch
de 584 instrumentos, no la unificación cross-workstream completa. Queda explícito para
que no se lea como "F-013 cerrado": el finding GLOBAL sigue abierto; lo que sigue es la
pieza MARKET que ese finding necesitaba de todos modos.

---

## 1 · Cómo se decide completado / fallido / a reintentar (auditado, no asumido)

Tres piezas, todas ya existentes antes de esta sesión — este documento no inventó
estado nuevo, lo caracterizó:

### `market_raw_runs` — una fila por intento de fetch

`status IN ('SUCCESS','EMPTY','PARTIAL','FAILED')`. Escrita por `_registrar_run()` en
`m2_fetch_engine.py`. `PARTIAL` es el status real de una **cuarentena** (regresión de
cobertura, `run_instrument()` línea ~331) — el `RunReport.status` en memoria dice
`QUARANTINED`, pero eso nunca se persiste tal cual en esta tabla.

### `market_fetch_log` — una fila por request lógico

`status IN ('REQUESTED','SUCCESS','SIN_CAMBIOS','PARTIAL','FAILED','RATE_LIMITED',
'NOT_FOUND','INVALID_SYMBOL')`. `RATE_LIMITED`/`NOT_FOUND`/`INVALID_SYMBOL` están en el
`CHECK` del esquema pero **ningún código los escribe hoy** — reservados, no usados
(verificado por grep en los 6 `.py` de `scripts/market/`; no es un bug, es contrato
declarado por delante de la implementación).

### `m6_scale.py::ya_exitosos()` — el checkpoint real

```sql
SELECT DISTINCT instrument_id FROM market_raw_runs
WHERE stage_run_id=%s AND status='SUCCESS'
```

Ya existía (sesión anterior). Es la decisión de "completado, no re-fetchear". El resto
de este documento es: **por qué esta única condición alcanza**, y **qué le faltaba
alrededor** para que "reanudación sin perder provenance" fuera cierto de punta a punta.

---

## 2 · El hallazgo central: los límites de transacción de `run_instrument()`

Lectura línea por línea de `m2_fetch_engine.run_instrument()` (no un diagrama abstracto):

```
market_fetch_log INSERT 'REQUESTED'  -> conn.commit()          [TXN A, propia, ya cerrada]
   ... gates, fetch, normalize ...
_archivar_raw()                       -> escribe en DISCO (no en la txn de Postgres)
_registrar_run() (status='SUCCESS')   -> INSERT market_raw_runs      \
_registrar_files()                    -> INSERT market_raw_files      | TXN B,
core.classify_batch() + UPSERT precios/cambios/acciones/snapshot      | sin commit
_cerrar_log() (status final)                                          | intermedio
                                       -> conn.commit()               /  [UN SOLO COMMIT]
```

**Consecuencia, verificada empíricamente en `test_crash_a_mitad_de_camino_no_deja_SUCCESS_a_medias`**:
un proceso matado en CUALQUIER punto entre el fetch exitoso y el commit final dejacero
filas en `market_raw_runs`/`market_price_daily`/etc. para esa corrida (Postgres revierte
TXN B completa) — **pero dos cosas sí sobreviven**, porque no son parte de TXN B:

1. **El RAW en disco** (`_archivar_raw()` corre ANTES de TXN B, es I/O de filesystem, no
   se revierte con la base). Queda un `data/raw/market/<iid>/<run_id>/` completo, sin
   ninguna fila en `market_raw_files` que lo referencie.
2. **La fila `market_fetch_log` 'REQUESTED'** (TXN A, ya comiteada al principio). Queda
   parada ahí para siempre — sin `completed_at`, sin status final. Es la firma exacta de
   "esto murió a mitad de camino": mismo patrón que F-009 encontró en SEC (corridas
   `RUNNING` huérfanas), pero Market nunca lo había caracterizado para sí mismo.

**Por qué `ya_exitosos()` es seguro de todos modos**: como TODO el trabajo de negocio
vive en TXN B (una sola transacción, un solo commit), no existe un estado intermedio
donde `market_raw_runs.status='SUCCESS'` diga la verdad a medias. La condición
`status='SUCCESS'` es binaria y atómica por construcción — el checkpoint que ya existía
era correcto en el núcleo. Lo que faltaba era todo lo que rodea esa certeza: visibilidad
de los huérfanos que deja atrás, y visibilidad de la cuarentena entre invocaciones.

---

## 3 · Contrato de checkpoint/reanudación de M23 (formal)

| Estado del instrumento (para este `--stage`) | Cómo se determina | Acción del resume |
|---|---|---|
| **Completado** | `market_raw_runs` tiene una fila `status='SUCCESS'` | Se saltea |
| **Nunca intentado** | Ninguna fila en `market_raw_runs` bajo este stage | Se procesa |
| **Murió a mitad de camino** | `market_fetch_log` tiene una fila `'REQUESTED'` sin fila `SUCCESS` correspondiente en `market_raw_runs` | Se procesa igual que "nunca intentado" (mismo resultado práctico) — pero ahora es **auditable** vía `auditar_raw_huerfano()` (§4) |
| **Falló (fetch)** | `market_raw_runs.status='FAILED'` | Se reintenta (dentro de la misma invocación, pasada extra de `main()`; entre invocaciones, automático porque no está en `ya_exitosos()`) |
| **Cuarentena** | `market_raw_runs.status='PARTIAL'` (regresión de cobertura) | Se reintenta igual que un fallido, pero **ahora se avisa explícitamente** antes de hacerlo (§4) — no es un error transitorio, es una señal de integridad |

**Invariantes que este contrato garantiza (probadas en §5, no solo declaradas)**:
- Nunca se pisa RAW: cada intento usa un `run_id` con timestamp propio; un reintento
  después de un crash usa un directorio nuevo, nunca el del intento muerto.
- Nunca se duplica RAW *contado*: `market_raw_files` termina con exactamente 2 filas
  (history.csv + meta.json) por corrida `SUCCESS`, sin importar cuántos intentos
  murieron antes.
- Nunca se pierde provenance: todo intento, exitoso o muerto, deja rastro (en la base,
  en disco, o en ambos) — nada desaparece en silencio.
- Todo instrumento termina, tarde o temprano, en un estado terminal
  (`SUCCESS`/`SIN_CAMBIOS`/`FAILED`/`PARTIAL`) — nunca se queda indefinidamente en
  `REQUESTED` sin que quede *visible* que eso pasó.

---

## 4 · Qué se agregó a `m6_scale.py` (mínimo, para sostener el contrato de arriba)

Dos funciones nuevas, ninguna toca el motor de fetch ni cambia su comportamiento:

1. **`cuarentenados_previamente(cur, stage)`** — antes de un `--resume`, consulta
   `market_raw_runs` por `status='PARTIAL'` bajo ese stage y **avisa** (no bloquea) si
   va a reintentar instrumentos que quedaron en cuarentena en una corrida anterior. Sin
   esto, un `--resume` los reintentaba en silencio, indistinguibles de "nunca
   intentados" — exactamente el vacío de visibilidad cross-invocación que F-013 pedía
   cerrar.
2. **`auditar_raw_huerfano(iids, conn=None)`** — solo lectura, nunca borra nada (RAW es
   inmutable). Compara `data/raw/market/<iid>/<run_id>/` en disco contra
   `market_raw_files.rel_path`; reporta archivos sin fila que los referencie. Expuesto
   como `python m6_scale.py --audit-raw-orphans` (modo diagnóstico, no corre el batch).
   El parámetro `conn` es inyectable a propósito: sin eso, la función no se podía probar
   contra una base aislada sin arriesgar apuntar a producción por accidente.

Ninguno de los dos cambia `ya_exitosos()`, el motor de fetch, ni el criterio de qué se
considera "completado" — son observabilidad añadida sobre un contrato que ya era
correcto en su núcleo.

---

## 5 · Validación empírica (no solo diseño en prosa)

Toda esta sección corre contra el motor **real** (`m2_fetch_engine.run_instrument`,
`m6_scale.correr_lote`), con `FixtureSource` (cero red) sobre la base de test descartable
(dev, puerto 5433 — ver `F001_REGRESION_TEST_MATRIX.md`, que este mismo trabajo dejó
funcionando). El "crash" se simula interrumpiendo la función real con
`unittest.mock.patch` justo después de que el RAW ya se escribió y las filas de
provenance ya se insertaron sin commit — el punto exacto donde moriría un proceso matado
ahí — seguido de `conn.rollback()`, que es exactamente lo que Postgres hace solo cuando
la conexión se cae.

`scripts/market/tests/test_m23_checkpoint.py` — **9 tests, 9/9 PASS**:

| Test | Qué prueba |
|---|---|
| `test_ya_exitosos_incluye_solo_SUCCESS_de_ese_stage` | El checkpoint no confunde éxito con fallo |
| `test_ya_exitosos_no_mezcla_stages_distintos` | Aislamiento entre corridas con distinto `--stage` |
| `test_cuarentena_no_cuenta_como_exitosa` | `PARTIAL` no es `SUCCESS`; y sí aparece en `cuarentenados_previamente()` |
| `test_crash_a_mitad_de_camino_no_deja_SUCCESS_a_medias` | Las 4 consecuencias del crash: 0 filas de negocio, `market_fetch_log` huérfano en `REQUESTED`, RAW sobrevive en disco |
| `test_crash_luego_reintento_no_duplica_raw_ni_pisa_nada` | El reintento usa un `run_id` nuevo; el directorio muerto queda intacto y aparte |
| `test_auditar_raw_huerfano_detecta_el_crash` | La auditoría encuentra exactamente los 2 archivos huérfanos |
| `test_auditar_raw_huerfano_no_marca_corridas_sanas` | 0 falsos positivos sobre una corrida sana |
| `test_resume_no_duplica_ni_pierde_provenance` | 2 invocaciones simuladas: la 2da solo re-fetchea lo que falló |
| `test_lote_interrumpido_y_reanudado_control_completo` | **Prueba de lote controlada, pedida explícitamente** — ver abajo |

### La prueba controlada pedida explícitamente

4 instrumentos sintéticos (`L1`..`L4`, sin red, sin tocar compañías reales) corridos a
través de `m6_scale.correr_lote()` (el orquestador real). `L2` muere a mitad de camino;
el proceso completo se cae ahí — `L3`/`L4` nunca se llegan a pedir. Salida real de la
corrida:

```
== INVOCACION 1: procesa L1..L4, L2 muere a mitad de camino ==
  [1/4] [L1] TST.BA       SUCCESS      5 ruedas new=5 changed=0 escritas=5
   proceso 'murio' -- L3 y L4 nunca se tocaron
   market_fetch_log tras el crash: [('L1', 'SUCCESS'), ('L2', 'REQUESTED')]
   RAW huerfano de L2 tras el crash: 2 archivo(s)

== INVOCACION 2: --resume ==
   ya_exitosos()=['L1'] -> resume selecciona: ['L2', 'L3', 'L4']
  [1/3] [L2] TST.BA       SUCCESS      5 ruedas new=5 changed=0 escritas=5
  [2/3] [L3] TST.BA       SUCCESS      5 ruedas new=5 changed=0 escritas=5
  [3/3] [L4] TST.BA       SUCCESS      5 ruedas new=5 changed=0 escritas=5

   ya_exitosos() final: ['L1', 'L2', 'L3', 'L4']
   RAW huerfano final (deuda tecnica del crash, no duplicacion): ['L2', 'L2']
   ultimo status por instrumento: [('L1', 'SUCCESS'), ('L2', 'SUCCESS'), ('L3', 'SUCCESS'), ('L4', 'SUCCESS')]
```

Las tres propiedades pedidas, verificadas con `assert`, no solo leídas del log:

1. **El resume selecciona exactamente los instrumentos pendientes** —
   `['L2', 'L3', 'L4']`, ni uno de más ni de menos.
2. **Cero duplicación de RAW** — cada instrumento termina con exactamente 1 corrida
   `SUCCESS` y exactamente 2 archivos registrados en `market_raw_files` (no 4). El
   directorio huérfano del intento muerto de `L2` sigue en disco (nunca se borra RAW),
   pero nunca se cuenta ni se confunde con el RAW válido.
3. **Todo estado de ejecución final es terminal** — el último `market_fetch_log` de
   cada uno de los 4 instrumentos es `SUCCESS`; ninguno queda en `REQUESTED`.

---

## 6 · Suite completa, corrida junto con todo lo demás

```
cd scripts/market && python -m pytest tests/ -q
40 passed in 22.91s
```

18 de `test_market_matrix.py` (regresión F-001, corregida en esta misma sesión — ver
`F001_REGRESION_TEST_MATRIX.md`) + 13 de `test_f014_venue_ticker.py` (F-014, sin
regresión) + 9 de `test_m23_checkpoint.py` (F-013, nuevos). Nada se rompió cruzando los
tres.

---

## 6.1 · La auditoría corrida contra datos reales encontró huérfanos genuinos

Smoke test de `python m6_scale.py --instruments YPFD.BA,YPF --stage golden-v5-retest5
--audit-raw-orphans` (solo lectura) contra `catalaxia`@5432 real, no contra la base de
test: **16 archivos huérfanos** en `data/raw/market/{83,84}/`, de corridas golden
anteriores de esta misma rama de trabajo (`golden-83-*`, `golden-v3-83-*`,
`golden-retest*-83-*`, y sus pares en 84). Exit code 1, como corresponde.

No es un hallazgo de esta sesión sobre esta sesión — son artefactos de trabajo previo
(sesiones anteriores de este mismo hilo, antes de F-013) que la auditoría nunca había
podido ver porque la herramienta no existía. Queda como evidencia de que
`auditar_raw_huerfano()` funciona sobre datos reales, no solo sobre el universo
sintético de los tests — y como un hallazgo menor, colateral, que se deja señalado (no
se borra ni se limpia: RAW es inmutable) para quien decida la política de retención.

---

## 7 · Qué NO se hizo

* **M23 no corrió contra instrumentos reales** — `m6_scale.py` no se invocó con
  `YahooSource` real en ningún momento de esta sesión. Toda la validación usa
  `FixtureSource` e instrumentos sintéticos (`L1`..`L4`, `CA`..`CX`, etc.), nunca YPF ni
  ningún ticker real.
* **No se resolvió F-013 GLOBAL** — SEC (`engine.checkpoints`) y CNV (ID original
  reusado) no se tocaron; sus convenciones de checkpoint siguen divergentes de la de
  Market. Ver §0.
* **No se implementó limpieza automática de RAW huérfano** — `auditar_raw_huerfano()`
  es deliberadamente solo lectura. Decidir si/cuándo archivar o purgar esos directorios
  es una decisión de retención de datos, no algo para resolver de paso.
* **No se cambió el criterio de `ya_exitosos()`** — ya era correcto; se le agregó
  observabilidad alrededor, no se le tocó la lógica central.

---

## 8 · Próximo paso

Auditoría independiente de este documento y del código — ver §9. Con eso resuelto, M23
queda con su contrato de checkpoint validado — la decisión de cuándo correr el batch de
584 instrumentos reales sigue siendo del owner, no de esta sesión.

---

## 9 · Auditoría independiente (2026-08-28) — veredicto `ACCEPT`

Agente separado, sin memoria de esta sesión: re-leyó `run_instrument()` línea por línea
y confirmó los límites de transacción exactos citados en §2 (incluidos los números de
línea); confirmó que `auditar_raw_huerfano()` es genuinamente de solo lectura (grep de
`DELETE|UPDATE|DROP|INSERT|conn.commit` sobre todo `m6_scale.py`: 0 coincidencias fuera
del resto del archivo); corrió `test_m23_checkpoint.py` él mismo y confirmó que la
transcripción impresa de la prueba de lote controlada coincide **carácter por carácter**
con la citada en §5; corrió la suite completa (40 passed) y el smoke test de
`--audit-raw-orphans` contra producción real (mismos 16 huérfanos, `git status`
idéntico antes/después — cero escrituras); confirmó por `git diff` que
`run_instrument()` no tiene ningún cambio de esta sesión más allá del wrapper de F-001
en `pg_conn()`.

**Dos hallazgos menores, no bloqueantes — ya resueltos o documentados:**

1. **Corregido**: `main()`'s `--audit-raw-orphans` no le pasaba la conexión ya abierta a
   `auditar_raw_huerfano()`, abriendo una segunda conexión redundante (inofensiva, pero
   no aprovechaba el `conn` inyectable). Arreglado (`auditar_raw_huerfano(..., conn=conn)`),
   re-verificado: smoke test + suite completa (40/40) siguen en verde.
2. **Limitación nombrada, no arreglada — a propósito**: la simulación de crash
   (`unittest.mock.patch` + `conn.rollback()`) reproduce fielmente lo que Postgres hace
   cuando una conexión se cae a mitad de una transacción, pero **no** ejercita un proceso
   matado literalmente a mitad de la escritura de un archivo (`history.csv`/`meta.json`
   truncados a medio escribir dentro de `_archivar_raw()`). `auditar_raw_huerfano()`
   marcaría un archivo truncado como huérfano igual que uno completo, pero nada distingue
   hoy "huérfano completo" de "huérfano truncado" — un futuro consumidor que quiera
   reusar RAW huérfano debería verificar su sha256 antes de confiar en él. Se deja
   documentado, no implementado (fuera del alcance pedido).

**Otras dos observaciones del auditor, también nombradas y no bloqueantes:**
- `cuarentenados_previamente()` avisa en CADA `--resume` mientras el instrumento siga en
  cuarentena, sin manera de marcar "un humano ya lo revisó" — sobre un batch de 584 con
  reintentos, esto puede volverse ruidoso. No es un defecto; es una funcionalidad futura
  razonable (un campo de "revisado por" en algún lado) que esta sesión no construyó.
- El costo de `auditar_raw_huerfano()` a escala real (584 instrumentos × el historial de
  `run_id` que se acumule bajo `data/raw/market/`) no se midió — se probó contra 2
  instrumentos reales y 4 sintéticos, no contra el universo completo. No es un riesgo de
  corrección, es una característica de performance sin verificar todavía.

**Conclusión del auditor, citada**: *"la simulación de crash es un proxy fiel... el
mecanismo es sólido: el commit único y atómico para toda escritura de negocio hace que
`ya_exitosos()` sea seguro por construcción; los dos sobrevivientes fuera de esa
transacción (RAW en disco, fila REQUESTED) ahora son visibles vía
`auditar_raw_huerfano()` y la firma de huérfano en el log — cerrando exactamente el
vacío de observabilidad que F-013 (recorte MARKET) tenía que cerrar."*
