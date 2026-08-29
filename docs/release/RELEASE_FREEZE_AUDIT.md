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
