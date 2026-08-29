# SYSTEM_HOMOLOGATION_MATRIX

**2026-08-28 · Instancia auditada: `catalaxia-engine-dev` 127.0.0.1:5433**
Cada criterio se reconstruyó desde PostgreSQL, `data/raw` y artefactos —
**no** desde los reportes del implementador.

Leyenda: `PASS` · `PASS_WITH_NOTES` (PWN) · `BLOCK` · `NOT_APPLICABLE` (N/A) ·
`NOT_TESTED` (NT)

---

## Gate 1 — SEC / S03 / S04

| criterio | estado | evidencia reconstruida |
|---|---|---|
| S03 materializó hechos | `PASS` | `parsed.facts` = **67.084** filas |
| S04 produjo derivados | `PASS` | `derived.fact` = **47.930**, `derived.normalize_conflict` = **1.180** |
| Checkpoints registrados | `PASS` | `engine.checkpoints`: S03 ×1, S04 ×4, contract `derived-v1` |
| Conflictos de normalización explícitos | `PASS` | 1.180 registrados, no resueltos en silencio |
| Cobertura del universo SEC | `NT` | no se auditó qué fracción del universo EDGAR cubre `parsed` |

**Gate 1 = `PASS`** en lo verificable. La cobertura no se midió: no es fallo, es
alcance no auditado.

---

## Gate 2 — Identity V1

| criterio | estado | evidencia |
|---|---|---|
| CIK autoritativo duplicado en 2 entidades | `PASS` | **0** |
| Entidad con 2 CIK autoritativos | `PASS` | **0** |
| Identificador huérfano (sin entidad) | `PASS` | **0** |
| `VERIFIED` sin evidencia/fuente/autor | `PASS` | **0** |
| Entidad `MERGED`/`DISSOLVED` con identidad autoritativa | `PASS` | **0** |
| `HUMAN_DECISION` firmada por un proceso | `PASS` | **0** |
| **Autoridad por tipo, exigida por la base** | **`BLOCK`** | **F-045** — eludible desde el rol de aplicación |
| Estado actual libre de contaminación de tipo | `PASS` | `id_type ≠ left_ref`: **0** |
| Entidades sin ancla autoritativa | `PWN` | **12** — provisionales del piloto, declaradas |
| Bridges CIK↔LEI | `PWN` | **4 `CANDIDATE/WEAK`** (proc) + **3 `VERIFIED/STRONG`** (Federico). GGAL propuesto, **no ratificado**. F-047: el candidato no se supersedió |

**Gate 2 = `BLOCK`** por F-045. Todo lo demás verifica.

---

## Gate 3 — Backfill CIK

| criterio | estado | evidencia |
|---|---|---|
| Universo anclado | `PASS` | **513** CIK autoritativos vigentes |
| Entidades | `PASS` | **525** = 513 con CIK + 12 sin ancla |
| Duplicados por reejecución | `PASS` | 0 CIK duplicados, 0 entidades con 2 CIK |
| CUIT producidos por el backfill | `PASS` | **3** CUIT autoritativos, los 3 ratificados por Federico; 0 firmados por `proc:backfill_cik` |
| CUIT legacy contenido | `PASS` | **53** `CUIT` `CANDIDATE` no autoritativos; **0** autoritativos desde `LEGACY_DIM_ENTITY` |
| Fusión por nombre/ticker | `PASS` | ataques 3 y 4 del banco: entidades distintas conservadas |

**Gate 3 = `PASS`.** El backfill no introdujo F-045; lo hereda.

---

## Gate 4 — Identity → CNV

| criterio | estado | evidencia |
|---|---|---|
| CUIT gobernado por Identity | `PASS` | 3 elegibles = 3 con bridge `VERIFIED`+`HUMAN_DECISION` firmado por persona |
| Cobertura ejecutada | `PASS` | **3** empresas, **9.165** GUIDs únicos, **3.508** artefactos |
| GGAL bloqueado por diseño | `PASS` | sin CUIT autoritativo, sin bridge `VERIFIED` → el resolver se detiene antes de consultar |
| Escala | `N/A` | CNV masivo fuera de alcance por decisión de producto |

**Gate 4 = `PASS`** en el alcance ejecutado (3 de 3). La brecha 512→3 **no es defecto**:
es G5, limitación de fuente (ninguna publica el puente CIK↔LEI).

---

## Gate 5 — Identity → Market

| criterio | estado | evidencia |
|---|---|---|
| Instrumentos con ancla | `PASS` | 584 instrumentos; 513 CIK autoritativos |
| **F-014 `venue_ticker`** | `PWN` | mitigado: `venue_ticker` poblado **584/584** en ambas instancias; difiere de `ticker_canonico` en **exactamente 6** (CRES→CRESY, TGSU2→TGS, PAMP→PAM, IRSA→IRS, TECO2→TEO, YPFD→YPF), todos ADR/NYSE. **El defecto de origen sigue**: `ticker_canonico` del ADR contiene el ticker de BYMA |
| Aislamiento de producción | `PASS` | Market escribe en 5433; 5432 sólo tiene las 10 filas `golden-*` del 24-25/08 |
| Datos escritos en prod por M23 | `PASS` | **0** |

**Gate 5 = `PASS_WITH_NOTES`.** La mitigación es correcta y trazable; la semántica de
`ticker_canonico` sigue siendo deuda.

---

## Gate 6 — Provenance

| criterio | estado | evidencia |
|---|---|---|
| Todo identificador autoritativo tiene assertion `VERIFIED` con fuente, cita y autor | `PASS` | 0 incompletas sobre 520 |
| `DELETE` de provenance | `PASS` | rechazado por `tg_no_borrar_assertion` (ataque 6d) |
| Edición de provenance histórica | `PASS` | rechazado por `tg_assertion_inmutable` (ataque 6) |
| **F-042** `source_facts` inmutable | `PASS` | mutar y **borrar** rechazados (ataques 6b, 6c) — **verificado independientemente** |
| Reapertura de assertion cerrada | `PASS` | rechazado (ataque 6e) |
| **F-041** deuda declarada | `PWN` | **1** CIK autoritativo sin `source_facts`: assertion #1, YPF, `SEC_20F`, accession `0001193125-17-115552`. El documento no está en disco |
| `left_ref` que respalde el tipo | `BLOCK` | **F-046**: 6 assertions autoritativas con `left_ref NULL` |

**Gate 6 = `PASS_WITH_NOTES`** para lo histórico y `BLOCK` para la garantía estructural
(ver Gate 2).

---

## Gate 7 — Idempotencia

| criterio | estado | evidencia |
|---|---|---|
| Reejecución no duplica entidades | `PASS` | 525 entidades = 513 + 12; 0 CIK duplicados |
| Reejecución no duplica identificadores | `PASS` | 583 totales / 574 vigentes / 9 retirados = exactamente los 6 de F-041 + 3 previos |
| CNV versionado por corrida | `PASS` | UNIQUE `(run_id, guid)`: 9.165 GUIDs únicos sobre múltiples corridas — versionado, no duplicación |
| M23 resume | `PWN` | funciona, pero **F-043** hace que los 7 `EMPTY` se re-pidan siempre |

**Gate 7 = `PASS_WITH_NOTES`.**

---

## Gate 8 — Reproducibilidad / hash

| criterio | estado | evidencia |
|---|---|---|
| `hashout` determinista | `PASS` | recalculado en vivo, 2× cada tabla, **5/5 idénticos**: `parsed.facts`, `parsed.contexts`, `parsed.units`, `parsed.concepts`, `derived.fact` |
| Hash de artefactos Market vs disco | `PASS` | muestra previa 40/40 coincidentes (`market_raw_runs.sha256` vs `history.csv`) |
| Hash de artefactos F-041 vs disco | `PASS` | 6/6 recalculados coinciden con `submissions/CIK*.json` |
| Checkpoints con `input_hash` distinto por corrida | `PASS` | S04: 4 corridas, 4 hashes |

**Gate 8 = `PASS`.** Es el gate con evidencia más fuerte.

---

## Gate 9 — Lifecycle de corridas

| criterio | estado | evidencia |
|---|---|---|
| Corridas huérfanas | `PASS` | **0** en `RUNNING` sobre **202** corridas |
| Estados terminales | `PASS` | `ABORTED` 103 · `OK` 56 · `BLOCKED` 43 |
| C3 cierra ante crash (F-040) | `PASS` | verificado en vivo: el dry-run del ciclo 8 crasheó y dejó `ABORTED` con `finished_at` |
| **F-038** persistencia M23 | `PASS` | **591 filas / 584 instrumentos / 577 SUCCESS** bajo `smoke-real-2026-08-28` en 5433. Prod tiene sólo `golden-*` — **correcto por diseño (F-001)** |
| Tipificación de estados Market | `PWN` | **F-043**: `EMPTY` nunca se emite |

**Gate 9 = `PASS_WITH_NOTES`.**

---

## Gate 10 — Banco adversario y garantías de base

Prueba mutacional sobre transacción revertida. **23 ataques** (15 con rol admin +
8 reejecutados sobre entidad limpia, de los cuales 3 con el rol de aplicación).

| ruta prohibida | estado | detalle |
|---|---|---|
| Inventar CUIT | **`BLOCK`** | **entró** desde `LEGACY_DIM_ENTITY`, `DERIVED_RULE`, `CNV_PORTAL` y `SEC_REGISTRY` con assertion sin `left_ref` (F-045) |
| Transformar CIK en CUIT | **`BLOCK`** | **entró** (ataque B1, rol de aplicación) |
| `CORROBORATING` → `AUTHORITATIVE` | `PWN` | promover un identificador: rechazado. Elevar la **fuente**: **entró** con rol owner (F-044) |
| Fusionar sin identificador autoritativo | `PASS` | rechazado por `tg_no_matar_entidad_con_identidad` y `tg_identidad_exige_entidad_viva` |
| Duplicar al reejecutar | `PASS` | rechazado por `ux_identifier_autoritativo_unico` y `ux_entity_un_autoritativo_por_tipo` (aislados sobre entidad limpia) |
| Modificar provenance histórica | `PASS` | rechazado en 5 variantes, incl. `source_facts` (F-042) |
| Datos de una entidad atribuidos a otra | `PASS` | el CUIT de CEPU sobre otra entidad: rechazado por `ux_identifier_autoritativo_unico` |
| Ticker como identidad jurídica | `PASS` | `ck_ticker_no_autoritativo` |
| Bridge `VERIFIED` firmado por proceso | `PASS` | `ck_authoritative_metodo` |

**Gate 10 = `BLOCK`.**

### Nota de método

En la primera pasada, 5 ataques se rechazaron **por una garantía distinta de la que
declaraban** (`ux_entity_un_autoritativo_por_tipo` o `ck_formato_identificador`, porque
el objetivo ya tenía un identificador de ese tipo o el valor estaba mal formado).
Se rehicieron sobre una entidad limpia y con un CUIT válido por módulo 11
(`30999999995`) — y entonces **5 de ellos entraron**. Sin ese rehacer, esta auditoría
habría reportado `PASS` por la razón equivocada.
