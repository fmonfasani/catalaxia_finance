# CNV_VALIDATION_GATE

Objeto: mecanismo CNV multi-empresa (Identity V1 → CNV fetch → persistencia →
auditoría independiente). Universo: CEPU, YPF, TGSU2 (fetch real); GGAL, BMA
(dry-run/exclusión justificada). Fecha: 2026-09-01.

```
CNV_VALIDATION_GATE = PASS_WITH_WARNINGS
```

## Segmentos

### IDENTITY_VALIDATION — PASS

- YPF, CEPU, TGSU2: CIK VERIFIED (SEC_REGISTRY/SEC_20F) + CUIT AUTHORITATIVE/VERIFIED
  (GLEIF, condicionado a `registeredAt` ∈ {RA000009 AFIP, RA000010 IGJ/RNS}) +
  LEI VERIFIED. Confirmado en vivo contra `identity_v1`, no asumido del enunciado.
- GGAL: CIK VERIFIED, LEI VERIFIED, CUIT solo CANDIDATE/WEAK — correcto y
  esperado (`registeredAt=RA999999` no cruza a AFIP/IGJ; review 3/14 OPEN lo
  documentan). No se promovió nada indebidamente.
- BMA: CIK VERIFIED, **cero** CUIT o LEI vigente (LEI ambiguo, F-024/review 17
  OPEN). Correctamente sin identidad para CNV — no se inventó nada.
- 0 CUIT inventados en toda la sesión. 0 decisiones humanas firmadas por un
  proceso (verificado: los 3 assertion autoritativos usan `method=REGISTRY`,
  no `HUMAN_DECISION`, y pasan `ck_authoritative_metodo`/`ck_humano_exige_autor`).

### FETCH_VALIDATION — PASS

- 3 fetches reales ejecutados con el mecanismo oficial (`c3_cnv_fetch.py`), sin
  scraper paralelo: YPF (53 artefactos), TGSU2 (126 + 126 en rerun). CEPU ya
  tenía 9.305 presentaciones de una sesión anterior, re-confirmadas vía
  `c3_identity_link.py`.
- Gate interno del fetcher: **PASS 10/10** en las 3 corridas nuevas.
- Idempotencia (Fase G) confirmada en una SEGUNDA entidad (TGSU2), no solo
  CEPU: 0 cambios reales en el rerun, checkpoint reutilizado.
- 9/10 ataques adversariales con barrera confirmada (Fase F).

### PERSISTENCE_VALIDATION — PASS_WITH_WARNINGS

- Para las corridas de HOY (YPF, TGSU2×2): 100% de los archivos existen en
  disco, 100% de los hashes recalculados coinciden, 0 duplicados, 0 mezcla
  entre CUIT.
- **Warning real**: la mayoría del RAW de corridas ANTERIORES a esta sesión
  (incluidas 5 corridas propias de CEPU y 2 corridas de mayor alcance de
  YPF/TGSU2) ya no existe físicamente en disco, aunque la base sigue
  declarando esas filas como `DOWNLOADED`. No hay corrupción (0 mismatch en lo
  que sí sobrevive) — hay ausencia, con un patrón consistente con una limpieza
  de retención no reconciliada contra la DB (F-008, ya abierto antes de esta
  sesión). No degrada el veredicto sobre lo fetcheado hoy; sí impide certificar
  la reproducibilidad física del histórico completo.

### PROVENANCE_VALIDATION — PASS_WITH_WARNINGS

- Provenance completa y coherente (entidad→cuit→endpoint→sha→raw_path→run) en
  el 100% de las filas de HOY y en el 100% de las filas históricas (la
  metadata sobrevive aunque el archivo no) — `AUD-PROV-001`/`002` PASS en los
  4 CUIT auditados.
- **Warning real, nuevo, no reportado en ciclos anteriores**: `fetch_raw.*`
  permite `UPDATE` sin ninguna barrera (a diferencia de `identity_v1`, que
  tiene triggers de inmutabilidad). Un hash persistido podría falsificarse sin
  que la escritura misma lo impida — solo una auditoría posterior (como esta)
  lo detectaría, comparando contra el archivo físico. DELETE sí está
  bloqueado por privilegios de rol.

### MULTI_COMPANY_VALIDATION — PASS

- **Esto es lo que este ciclo vino a demostrar y quedó demostrado**: el
  mecanismo no es una solución especial para CEPU. Corrió sin cambios de
  código para YPF y TGSU2, con CUIT resueltos por Identity V1, gates
  idénticos, y `c3_identity_link.py` confirma **3 emisores, 36.136
  presentaciones, 100% atribuidas por CUIT autoritativo** (no por CIK-en-clave-legacy
  como era el único caso — CEPU — en ciclos anteriores).
- Los 2 casos deliberadamente NO fetcheados (GGAL, BMA) demuestran la otra
  mitad de la garantía: el mecanismo se **niega** a operar sin identidad
  demostrable, en vez de inventar una para completar el universo.

## Veredicto y motivo

**PASS_WITH_WARNINGS**, no PASS liso: dos hallazgos reales (RAW histórico sin
retención reconciliada; `fetch_raw` sin protección de UPDATE) son genuinos,
verificados con evidencia, y no bloqueantes para lo que esta sesión fetcheó y
puede reproducir hoy. No se los suavizó a PASS ni se escaló innecesariamente a
BLOCKED — ninguno invalida la conclusión central (el mecanismo generaliza a
múltiples empresas usando Identity V1 sin inventar identidad).

## Blockers para escalar a CNV masivo

Ver sección homónima en `CNV_VALIDATION_REPORT.md` (5 ítems: retención de RAW,
UPDATE sin protección en `fetch_raw`, GGAL/BMA sin identidad resuelta, volumen
lineal sin techo, infraestructura compartida bajo estrés).

## Evidencia

- `CNV_VALIDATION_REPORT.md` (narrativa completa, Fases A–I)
- `CNV_VALIDATION_MATRIX.csv` (empresa → CUIT → provenance → resultado)
- `CNV_VALIDATION_ADVERSARIO.json` (10 ataques, resultado y barrera)
- `CNV_VALIDATION_AUDITOR_REPORT.json` (auditoría independiente, 4 CUIT)
- `scratchpad/c3_runs/run{7,8,9}_*.log`, `identity_link_informe.log` (logs
  crudos de las corridas)
- `C3_CNV_STAGE_REPORT_run1_PASS.json`, `_run6_rerun_PASS_fixed.json` (sesión
  previa, CEPU) — no repetidos, referenciados
