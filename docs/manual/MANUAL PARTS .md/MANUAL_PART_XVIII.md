# PARTE XVIII — QUÉ FALTA

El cierre honesto: decisiones, certificaciones, gaps de software y prioridades
concretas. **Este manual no debe declararse terminado todavía.**

**Material de base:** `docs/manual/MANUAL_SCOPE.md` §4-§6;
`docs/manual/MANUAL_TOC.md` §4-§5; `outputs/runbook/
RUNBOOK_READINESS_REPORT.md` §16-§18; plan maestro §40 y §3466-3495.

---

## Paso 1 · Decisiones abiertas (D-1…D-4) — bloquean cuatro capítulos

| id | decisión | bloquea | impacto |
|---|---|---|---|
| **D-1** | ¿Econ Facts / Financial Model / tramo C de CNV / homologación TIKR viven en el repo principal, en el worktree, o en los dos? | Caps. 6, 7, 10-C, 17 | los cuatro quedan `NOT_IMPLEMENTED` hoy; es una decisión de producto, no de documentación |
| **D-2** | ¿el manual absorbe `docs/runbooks/` o lo envuelve? | la forma física del manual | estructural; este manual está escrito para servir a las dos opciones |
| **D-3** | ¿KO se certifica tras corregir sus hallazgos, o se cambia de piloto? | Caps. 2-5, 8, 11, 14, 16 | afecta 8 de 17 capítulos |
| **D-4** | ¿vocabulario de homologación del encargo (`METHODOLOGY_DIFFERENCE`, `DATE_DIFFERENCE`) o el implementado (12 estados)? | Cap. 17 | no mezclar vocabularios en un reporte |

---

## Paso 2 · Certificaciones pendientes (C-1…C-6) — precondición de escritura

| id | qué | bloquea |
|---|---|---|
| **C-1** | creación del entorno desde cero | Cap. 1 |
| **C-2** | Economic Facts / Financial Model | Caps. 6, 7 |
| **C-3** | correr y certificar **KO** (única excepción a "no ejecutar pilotos") | Caps. 2, 3, 4, 5, 8, 11, 14, 16 |
| **C-4** | tramo C de CNV / homologación TIKR | Caps. 10-C, 17 |
| **C-5** | idempotencia de `job5` (tramo B) — hoy solo "alta" sin procedimiento | Cap. 14 |
| **C-6** | E2E de Market — 9 de 11 scripts sin documentar | Cap. 9 |

---

## Paso 3 · Las prioridades (P0 → P1 → P2)

**P0 — nada se vuelve a certificar hasta acá:**
1. **Idempotencia de S00** — refutada hoy; una segunda corrida contamina.
2. **Idempotencia de S02** — refutada hoy; causa directa de la `RUNNING`
   huérfana acumulada (F-009 / `SG-11`).
3. **`is_custom` (W-2)** del golden run de KO — un hecho de KO no se puede
   volver a emitir con el mismo hash si la clasificación depende del orden de
   las tags.

**P1:**
4. Generalizar **S01** (multi-emisor) — `C-S01-004` está clavado a YPF
   (`SG-05`).
5. Entorno reproducible desde cero (`C-1`).
6. Integrar el **reporte del golden run de KO** al manual (`C-3`, `D-3`).
7. CNV ejecutable **desde el repo principal** (resolver `SG-01` + `D-1`).
8. **Árbol de diagnóstico** generalizado por GUID/CUIT (Cap. 15, PARCIAL).
9. **Gate agregado** con exit code (`L-4`/`GAT-02`).

**P2:**
10. Economic Facts completo (Cap. 6) y Financial Model persistido (Cap. 7,
    `L-11`/`L-12`).
11. Market E2E con puente `instrumento→entidad` (`SG-10`) y 11/11 scripts
    documentados (`C-6`).
12. Provenance E2E también para Market (hoy bloqueada por `L-5`).
13. CapEx (la CNV no lo publica — caen FCF y 6 métricas más; `L-8`).
14. Homologación TIKR generalizada y desde el repo principal (`C-4`, D-1-D-4).

---

## Paso 4 · Los software gaps y su remediación

`RUNBOOK_READINESS_REPORT.md` §16 documenta 11: `SG-01` (no hay E2E CNV),
`SG-02` (no se almacena el SHA CNV — `C-C3-008` nunca compara nada),
`SG-03` (14 ratios contables sin persistir), `SG-04` (no hay reconciliación
descargado→procesado→con datos), `SG-05` (`C-S01-004` clavado a YPF),
`SG-06` (dos `stage_id` para C3), `SG-07` (sin vocabulario de códigos
operativos), `SG-08` (no existe cuarentena), `SG-09` (S04 no persiste
checkpoint), `SG-10` (enlace instrumento↔emisor roto), `SG-11` (huérfanas se
detectan, no se cierran), `SG-12` (no se valida que una descarga contenga un
documento).

**Remediación priorizada (§18)** — la más barata y de mayor impacto es la
primera, y es lo que hoy impide el gate `PASS`:

1. **Reconciliación de cobertura** como check bloqueante (`SG-04`).
2. **Tabla de rechazos por documento** en CNV y que `_mark_done` distinga
   éxito de fracaso (`SG-04`/`SG-07`).
3. **Persistir el SHA256** de cada documento CNV y poblar `hash_cnv`
   (`SG-02`) — habilita `C-C3-008` ya escrito.
4. **Puente instrumento→entidad** (`SG-10`) — desbloquea todos los múltiplos.
5. **Decidir el camino CNV oficial** (`SG-01`) — decisión de arquitectura.
6-11. Persistir los 14 ratios (`SG-03`), unificar `C3_CNV_fetch`/`C3_CNV_FETCH`
(`SG-06`), cerrar huérfanas (`SG-11`), parametrizar `C-S01-004` (`SG-05`),
checkpoint en S04 (`SG-09`), cuarentena (`SG-08`, depende de 2).

---

## Paso 5 · Los limitaciones que se documentan, no se arreglan

`L-1` (sin `--resume`), `L-2` (`QUARANTINED` no existe), `L-3` (sin rollback
fuera de Market), `L-4` (sin gate agregado), `L-5` (enlace roto), `L-6` (job5
sin ledger), `L-7` (CNV oficial no baja EEFF), `L-8` (CNV no publica CapEx),
`L-9` (226/286 son cáscaras), `L-10` (perímetro no computable del formulario),
`L-11` (FM no persistido), `L-12` (ratio_engine SEC-first), `L-13` (serie ARS
no comparable sin deflactar, IAS 29), `L-14` (9 códigos / 374 scripts),
`L-15` (5 tests en rojo), `L-16` (9 de 7.998 entidades con hechos).

Una limitación no se elimina editando este catálogo: se elimina cuando su
causa deja de existir.

---

## GATE de la Parte XVIII

```
EL MANUAL NO ESTÁ TERMINADO.
```

El cierre de este manual es una **decisión de producto**, no de
documentación: publicar los cuatro capítulos partidos por el worktree
(Economic Facts, Financial Model, tramo C, TIKR) con rótulo `NOT_IMPLEMENTED`
cubre la forma pero no la función. El único criterio honesto de cierre es la
resolución de **D-1 … D-4**, la ejecución de **C-1 … C-6** y el cierre de la
gaps que el gate del sprint marcó — encabezadas por `SG-04`/`SG-12`: **una
corrida incompleta que nadie detecta no se declara terminada, se instrumenta
para que no pueda volver a pasar.**

---

*Todo lo que este manual puede prometer está escrito: cómo operar lo que
existe. Todo lo que no, está en este capítulo con su código exacto.*