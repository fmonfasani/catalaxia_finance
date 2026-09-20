# PARTE XIII — CERTIFICACIÓN

Este capítulo define, con la máquina de estados real, **cuándo una corrida se
puede declarar buena y con qué evidencia** — y aplica el criterio a los tres
pilotos para que nadie tenga que interpretar "está en verde".

**Material de base:** `docs/runbooks/07_CERTIFICATION.md` completo,
`docs/manual/ANNEX_YPF.md` §12/§14 y el Golden Run de KO.

---

## Paso 1 · La máquina de estados real

**OBJETIVO**
Saber los estados que existen — y los que **no existen** aunque se los pidió.

La máquina real vive en `engine/states.py` (`assert_transition` valida cada
salto; un salto no permitido levanta `ValueError`):

```
PLANNED → READY → RUNNING → VALIDATING → PASSED → CHECKPOINTED → CERTIFIED
                                 ↓
                              FAILED → FIXING → RERUNNING → VALIDATING
```

Gates: `PASS`, `WARNING`, `BLOCK`. Nada más.

**`KNOWN_LIMITATION` (L-2)** — estados pedidos que **no existen**:

| pedido | estado real |
|---|---|
| `NOT_STARTED` | es **`PLANNED`** |
| `PASS` | es **`PASSED`** (etapa) / `GateStatus.PASS` (gate) |
| `PASS_WITH_WARNINGS` | es **`GateStatus.WARNING`**, a nivel gate, no de etapa |
| `BLOCKED` | es **`GateStatus.BLOCK`**, a nivel gate |
| `QUARANTINED` | **NO EXISTE** |
| `RECOVERED` | **NO EXISTE** — `FIXING`/`RERUNNING` se le acercan pero no lo son |
| `SKIPPED` | no es estado de etapa; existe como `result` de un check en `--dry-run` de S04 |
| `NOT_CALCULABLE` | es `derived.ratio.status`, a nivel dato, no de etapa |

`CERTIFIED` es el estado terminal y **sólo** se alcanza desde `CHECKPOINTED`.

---

## Paso 2 · Criterios de etapa y de corrida completa

**Criterios por etapa** — las cuatro condiciones de la Parte XII (gate
`PASS`, `report` válido, `expected == parsed + rejected`, `checks` no vacío).

**Criterios de corrida completa** (`07_CERTIFICATION.md` §3):

| # | criterio | cómo se verifica |
|---|---|---|
| 1 | Todas las etapas con gate `PASS` | consulta de la Parte XII, por `run_id` |
| 2 | `engine.runs.status = 'OK'` | ninguna corrida en `RUNNING` ni `ABORTED` |
| 3 | Idempotencia demostrada | segunda corrida: mismo `hash_out`, 0 inserts vigentes |
| 4 | Provenance completa | Parte X §2 sobre una muestra |
| 5 | Producción intacta | `01_COMMON_OPERATIONS.md` §1.4 (sólo `public`) |
| 6 | `screener.db` intacto | huella antes/después, salvo tramo B de CNV |

**Evidencia mínima a archivar** — sin el `run_id` no se reconstruye nada:
1. `run_id` de cada etapa.
2. Salida de consola completa.
3. El `report` JSON de cada etapa.
4. `hash_in` / `hash_out` de S03 y S04.
5. El resultado de las dos verificaciones de no contaminación.
6. La fecha y el `git_commit` (queda en `engine.runs`).

**Lo que NO habilita a certificar** (`07_CERTIFICATION.md` §6):
- terminar con `exit 0` **sin checks** (lo rechaza `validate()`);
- que los números "se vean bien", sin `expected == parsed + rejected`;
- que una segunda corrida "no rompa" — idempotencia es **mismo digest**, no
  ausencia de excepción;
- que la etapa anterior haya pasado **en otra corrida** sin verificar el
  encadenamiento (`C-S04-001` existe justamente porque S04 llegó a correr
  sobre un S03 que no reproducía su `hash_out`).

---

## Paso 3 · Estado de certificación real de los pilotos

**Clasificación usada** (plan maestro §40/§49): los estados de diagnóstico
son `PASS`, `PASS_WITH_WARNINGS`, `BLOCKED`, `NOT_READY`,
`NOT_IMPLEMENTED`, `KNOWN_LIMITATION`, `DECISION_REQUIRED` — nunca sólo
`PASS`/`FAIL`.

### YPF · `PASS_WITH_WARNINGS` — evaluación en vivo (2026-09-04, §14 del anexo)

| # | criterio (corrida completa) | YPF hoy |
|---|---|---|
| 1 | Todas las etapas con gate `PASS` | **Sí**, 6/6 — pero de corridas en fechas distintas, no de una sesión única |
| 2 | `engine.runs.status = 'OK'` | **No, sin matiz** — hay `ABORTED` (intentos S00/S02 de hoy, H-1/H-2) y `RUNNING` huérfanas de la verificación |
| 3 | Idempotencia demostrada | **Parcial** — S04 sí; S03 por diseño de código; **S00 y S02 refutada** |
| 4 | Provenance completa | **Muestra de 1** — `Assets` 2025-12-31 cierra hasta SHA256; no exhaustiva |
| 5 | Producción intacta | **Sí** — `pg_namespace` de 5432 devuelve sólo `public` |
| 6 | `screener.db` intacto | **No verificado** — no se tomó huella antes/después |

### KO · `PASS_WITH_WARNINGS` — Golden Run en `kogolden`

Demostrado: US-GAAP de punta a punta sin tocar el core, **20/20 conceptos del
registry**, 45.113 hechos, 17 XBRL + 14 pre-XBRL, EPS 3.05, S03/S04
idempotentes con `hash_out` idéntico, provenance hasta el SHA256 del archivo.
Pendiente (los seis hallazgos del reporte, incluido **W-2 `is_custom`**):
generalización de S01, corrección de `is_custom`, idempotencia de S00/S02.

### METR · `PASS_WITH_WARNINGS` — **único E2E completo certificado, con salvedad**

`outputs/docs/fase_cnv/METR_FY2024_E2E_REPORT.md`: 7 documentos con SHA256
recomputado, 203 hechos con 0 fallas de auditoría, 70/77 ratios (7
`NO_INPUT` con causa), 10 mutaciones adversariales todas detectadas, segunda
corrida sin inserts y digests idénticos, producción con 0 cambios. **Salvedad
(`07_CERTIFICATION.md` §5):** se produjo con el adaptador del worktree
`catalaxia-cnvmig`, no con el repo principal (tramo C, `DECISION_REQUIRED`
D-1).

---

## GATE de la Parte XIII

Un piloto está certificado cuando demuestra la cadena completa y repetible:
`IDENTIDAD → RAW → PARSED → NORMALIZED → RATIO`, más `PROVENANCE`, más
`IDEMPOTENCIA`, más `SEGURIDAD DE PRODUCCIÓN`. Con la evidencia de hoy,
**ninguno de los tres está certificado de punta a punta en una sola sesión**;
YPF es el que tiene la cadena de datos más sólida, KO es el que probó la
generalización, y METR es el único con un E2E completo — proveniente del
worktree.

**`DECISION_REQUIRED` (D-3)** — si KO no se certifica tras corregir sus seis
hallazgos, hay que decidir su rol de piloto. La certificación honesta se
declara con la matriz de arriba, no con "todas las etapas en verde alguna
vez".

---

*La evaluación de este capítulo es una medición del 2026-09-04 (YPF) y de los
Golden Runs existentes (KO, METR). No se corrigió código para que nada de
esto fuera verdad: se documentó la verdad.*