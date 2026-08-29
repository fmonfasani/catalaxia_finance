# RELEASE FREEZE AUDIT — CATALAXIA V1.0

**Fecha:** 2026-08-29 · **Alcance:** auditoría de release. No se modificó código, schema,
datos, `data/raw` ni se hizo ningún commit.

---

# DICTAMEN: **RELEASE_BLOCKED**

**Por una sola causa, y no es funcional:** el commit declarado como release
**no contiene V1**.

El sistema homologado está intacto y verificado: baseline == PostgreSQL sin un solo
delta, los 8 controles de integridad en cero, findings post-V1 preservados. Lo que
falla es el **artefacto de distribución**, no el software.

---

## 1. ¿El commit de release contiene realmente V1? **NO**

```
commit  444ee1ad0e1b092c79ce055ded0b993fbc55822d
fecha   Tue Aug 25 01:01:51 2026 -0300
autor   fmonfasani
mensaje chore: establish Catalaxia core baseline
rama    fix/ttm-ratios-cnv   ·   HEAD == este commit
```

Su propio mensaje lo dice: **«establish core baseline»**. Es el punto de partida del
trabajo, no su resultado. Es del **25 de agosto**; todo V1 se construyó entre el 25 y
el 29.

### Qué falta

| sección del manifiesto | declarados | en el commit | **faltan** |
|---|---:|---:|---:|
| migraciones | 32 | 5 | **27** |
| código `engine/` | 16 | 14 | **2** |
| scripts `scripts/engine/` | 27 | 5 | **22** |
| tests | 14 | 1 | **13** |
| contratos | 11 | **0** | **11** |
| auditorías | 20 | **0** | **20** |
| evidencia | 7 | **0** | **7** |
| documentos de release | 6 | **0** | **6** |
| **TOTAL** | **133** | **25** | **108 (81 %)** |

Faltan **todas** las migraciones de Identity V1 (`008`–`031`), incluidas las garantías
homologadas: `030_f045_coherencia_assertion_identifier.sql` y
`031_f044_politica_estructural_cik_lei.sql`.

Y falta el núcleo del software:

```
NO   engine/identity_v1.py          <- Identity V1 entero
NO   engine/hashout.py              <- hashout-v2
NO   scripts/engine/backfill_cik.py
NO   scripts/engine/s04_normalize.py
NO   tests/…                        <- 13 de 14
SI   engine/db.py                   (versión anterior a run_scope)
```

Un `git checkout 444ee1ad0e1b` limpio no puede **importar** `engine.identity_v1`, menos
aplicar las migraciones o correr los tests.

### La inconsistencia documental, resuelta

El encargo pide explicar por qué antes se declaró *«sin commit»* y ahora aparece
`444ee1ad0e1b` como commit de release.

**Ambas afirmaciones son ciertas y no se contradicen:**

- **No existe un commit de release.** Todos los ciclos corrieron bajo la restricción
  explícita «NO hacer commits», que se respetó.
- `444ee1ad0e1b` es simplemente **HEAD**. `release_baseline.py` lo obtiene con
  `git rev-parse HEAD` y lo escribe bajo la clave `git_commit`, **sin verificar que el
  worktree esté limpio**.

Ese es un defecto de mi generador de baseline del ciclo anterior: llamó *«commit del
release»* a *«el commit en el que está parado el worktree»*. Se registra como
**F-048**, y no se corrige en este ciclo.

## 2. ¿El manifest coincide con el repositorio? **SÍ — con el worktree, no con el commit**

Los **sha256 de los 133 archivos coinciden con el disco**. El manifiesto es una
fotografía fiel del árbol de trabajo.

Clasificación de la diferencia contra el commit:

| | clasificación |
|---|---|
| 108 archivos ausentes del commit | **REAL** — impide reproducir |
| conteos del manifiesto (32/16/27/14/11/20/7) | **verificados**, recalculados desde el filesystem |
| 179 untracked totales, de los cuales **74 pertenecen a V1** | **REAL** los 74; el resto (`.vscode/`, `*.xlsx`, `DEPLOY_*.md`, dashboards) son **ARTEFACTO**, fuera del release |
| 48 tracked modificados · 3 borrados · **0 staged** | **REAL** — cambios de V1 sin registrar |

## 3. ¿El baseline coincide con PostgreSQL? **SÍ — 14/14, cero deltas**

```
entities 525 · assertions 614 · identifiers vigentes 574
CIK 513 · LEI 4 · CUIT 3 · bridges VERIFIED 3
reviews OPEN 11 · conflicts 1 · RUNNING 0
triggers 15 · CHECKs 27 · unique indexes 11 · migraciones aplicadas 29
```

El baseline **es** una fotografía reproducible del estado homologado. Ese entregable
está correcto.

## 4. ¿El release es reproducible? **NO desde el commit; SÍ desde el worktree**

No se ejecutó ninguna instalación destructiva ni se creó base temporal: **la pregunta
se responde sin necesidad de intentarlo**. Faltan el 84 % de las migraciones y el
módulo central de Identity; no hay nada que reconstruir.

Desde el worktree actual sí es reproducible —es lo que la homologación verificó— pero
un worktree no es distribuible.

## 5. ¿Hay algún blocker real? **SÍ, uno**

**F-048 — el release no está capturado en ningún commit.**

Es exactamente el criterio del encargo: *«RELEASE_BLOCKED sólo si existe una
inconsistencia que impida reproducir o distribuir V1»*. Impide ambas.

**No es un defecto funcional.** No hay corrupción, ni bypass, ni regresión, ni pérdida
de provenance, ni inconsistencia de identidad. La homologación sigue siendo válida
sobre el estado que auditó.

### Integridad — sin cambios respecto de la homologación

```
RUNNING ............................. 0     VERIFIED sin evidencia ......... 0
identifiers huérfanos ............... 0     HUMAN firmada por proceso ...... 0
CIK duplicados ...................... 0     contaminación de tipos ......... 0
entidades muertas con identidad ..... 0     bridges VERIFIED contradictorios 0
```

### Findings post-V1 preservados, no resueltos accidentalmente

```
F-041  CIK sin source_facts ......... 1   (esperado 1)
F-046  assertions sin left_ref ...... 6   (esperado 6)
F-047  bridges CANDIDATE vigentes ... 4   (esperado 4)
```

Documentación presente: `POST_V1_BACKLOG.md` · `F046_FINDING.md` ·
`HOMOLOGATION_FINDINGS.md` · `F044_GATE.md`.

## 6. ¿Qué queda explícitamente fuera de V1?

El release **no afirma** ninguna de estas cosas, y así consta en
`CATALAXIA_V1_RELEASE.md` §4:

| | |
|---|---|
| CNV universo completo | 3 de 512 elegibles · limitación G5 |
| cobertura BYMA completa | 56 emisores sin ancla autoritativa |
| GGAL con CUIT | bridge propuesto, **no ratificado** |
| BMA con CUIT | dos LEI para la razón social; elegir sería inferencia |
| ratificaciones automáticas | por diseño: las firma una persona |
| EDGAR completo | sólo el CIK piloto auditado |
| F-043 / F-041 / F-046 / F-044 / F-047 / F-014 | **siguen abiertos o con notas**; ninguno se declara eliminado |

Los cuatro niveles están separados en el release: **HOMOLOGADO** (§3) ·
**CON NOTAS** (§5) · **FUERA DE ALCANCE** (§4) · **POST-V1** (`POST_V1_BACKLOG.md`).

---

## F-048 — el release no está capturado en ningún commit

**Severidad:** bloqueante para la distribución · **No funcional**
**Estado: REGISTRADO, NO CORREGIDO** (el encargo prohíbe hacer commits)

**Causa raíz doble:**

1. La restricción «NO hacer commits» rigió todos los ciclos y se respetó. Correcta en
   su momento —evitaba consolidar trabajo no auditado— pero nadie levantó la
   restricción al llegar al release.
2. `release_baseline.py` escribe `git rev-parse HEAD` bajo la clave `git_commit` **sin
   comprobar que el worktree esté limpio**, produciendo un artefacto que parece señalar
   un commit de release y en realidad señala el punto de partida.

**Corrección propuesta (no aplicada):** crear el commit de release con los 74 archivos
untracked de V1 más los 48 tracked modificados, excluyendo los artefactos
(`.vscode/`, `*.xlsx`, dashboards, `DEPLOY_*`); etiquetarlo `v1.0.0`; regenerar
baseline y manifiesto contra ese commit; y hacer que `release_baseline.py` **falle** si
`git status --porcelain` no está vacío.

**Requiere autorización explícita para commitear.**

---

# ADENDA — 2026-08-29 · Construcción del release y dictamen final

## F-048 = **CLOSED**

Con autorización explícita, se construyó el release:

```
commit  25756e1a  release: Catalaxia V1.0.0            148 archivos, +32.702 líneas
commit  73fb000   release: metadata del commit real y F-049
tag     v1.0.0 -> 73fb000
rama    fix/ttm-ratios-cnv
```

### Clasificación: 148 RELEASE / 413 EXCLUDE / **0 sin clasificar**

Por rol y por ruta, no por extensión. Cada regla lleva su motivo
(`docs/release/_clasificacion.json`). Lo que no matchea una regla explícita queda
`SIN_CLASIFICAR` y obliga a detenerse — no se incluye por defecto. No hubo ninguno.

| RELEASE | | EXCLUDE | |
|---|---:|---|---:|
| `migrations/` | 27 | raíz (dashboards, deploys, xlsx, tmp) | 42 |
| `scripts/engine` | 25 | `scratchpad/` | 107 |
| `docs/architecture` | 25 | `outputs/` de fase | 80 |
| `docs/review` | 23 | `docs/` no técnicos | 119 |
| `tests/` | 14 | `scripts/` legacy, tickets, docgen | 45 |
| `scripts/market` | 12 | `data/`, `lib/`, `_legacy/`, `.vscode/` | 20 |
| `docs/release` | 9 | | |
| `outputs/docs/homologacion` | 7 | | |
| `engine/` | 6 | | |

### Fase B — los 12 requisitos: **12/12 PASS**

29/29 migraciones engine registradas · 3 de market · `identity_v1.py` ·
`hashout.py` · garantías F-035/036/037/044/045 · 11 contratos · 23 auditorías ·
14 tests · baseline · manifest · release doc · sin artefactos ajenos.

### Fase D — pre-commit gate: **PASS**

8 controles de integridad en 0 · baseline == PostgreSQL · 148 archivos existen ·
ningún EXCLUDE en la lista · nada staged previamente.

### Fase G — post-commit

`HEAD == v1.0.0 == 73fb000` · ningún RELEASE fuera del commit · ningún RELEASE aún
modificado · **mis dos commits agregaron 135 archivos y ninguno es EXCLUDE ni de
raíz** (los 23 que matchean el patrón ya estaban en `444ee1a`).

**Los 3 borrados** (`data/log_bloque1.txt`, `log_bloque2.txt`, `log_precios.txt`) **no
se incluyeron**: son logs de `data/`, ajenos al release. Quedan pendientes en el
worktree por decisión, no por olvido.

---

## Fase H — reproducibilidad: **FALLA → F-049**

Se creó un worktree aislado sobre `v1.0.0` y una base **descartable** (`v100_check`,
eliminada al terminar). **La base homologada no se tocó**: 525/614/29/0 al cerrar,
idéntica.

El checkout contiene todo: 29 migraciones engine, 3 market, 14 tests, 11 contratos,
`identity_v1.py`, `hashout.py`.

**Pero el runner del propio tag no puede aplicarlas.**

```
sqlalchemy.exc.IntegrityError: duplicate key value violates unique constraint
DETAIL:  Key (filename)=(008_identity_v1.sql) already exists.
```

16 de las 29 migraciones se auto-registran en `engine.schema_migrations` con
`ON CONFLICT`, y `engine/db.py:94` las registra otra vez **sin** `ON CONFLICT`. Como
`_apply_migrations` corre en una sola transacción, **revierte todo**: la base quedó
sin `engine.schema_migrations` siquiera.

Nunca se había visto porque esas 16 siempre se aplicaron a mano con `psql -f`. La
base homologada llegó a su estado correcto por el camino manual; el automático nunca
se ejercitó hasta ahora.

### Nota de método

El primer intento aplicó las migraciones con `psql -f` suelto y falló con
`relation "engine.schema_migrations" does not exist` — **error de mi procedimiento**,
no del release: esa tabla la crea el runner. Rehecho con el runner del tag sobre base
limpia, el fallo es real y reproducible.

---

# DICTAMEN: **RELEASE_BLOCKED** — F-049

| pregunta | respuesta |
|---|---|
| 1. ¿el commit contiene V1? | **SÍ** — 148 archivos, F-048 cerrado |
| 2. ¿tag apunta al commit? | **SÍ** — `v1.0.0 == HEAD == 73fb000` |
| 3. ¿worktree limpio respecto del release? | **SÍ** — 0 RELEASE fuera, 0 modificados |
| 4. ¿manifest consistente? | **SÍ** — apunta al commit real, 148/148 |
| 5. ¿baseline consistente? | **SÍ** — 14/14 contra PostgreSQL, sin deltas |
| 6. **¿checkout reproducible?** | **NO** — **F-049** |
| 7. ¿suite pasa? | contra la base homologada **sí** (198/198); contra una base reconstruida **no evaluable** |
| 8. ¿blocker funcional? | **ninguno** |
| 9. ¿alcance delimitado? | **SÍ** — §3 y §4 del release |

**F-049 no se corrigió**, según la regla del ciclo: *«No parchear silenciosamente el
release.»* Dos correcciones propuestas en `docs/review/F049_FINDING.md`; la decisión
de cuál aplicar es de producto, porque cambia dónde vive la responsabilidad del
registro.
