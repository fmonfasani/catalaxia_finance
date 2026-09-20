# PARTE XVII — ESTADO REAL DEL SISTEMA

Un informe único que responde **qué produce el sistema hoy**, con qué
veredicto y qué queda pendiente. Es una medición del 2026-09-04 sobre las bases
`catalaxia`@5433 y los artefactos publicados — no una promesa.

**Material de base:** las Partes II–XVI de este manual; `outputs/runbook/
RUNBOOK_READINESS_REPORT.md`; los reportes E2E/golden de `outputs/docs/fase_cnv/`.

---

## Paso 1 · El estado por piloto

| piloto | fuente | veredicto | cadena demostrada | deuda principal |
|---|---|---|---|---|
| **YPF** | SEC EDGAR XBRL (ifrs-full) | `PASS_WITH_WARNINGS` | IDENTIDAD → RAW → PARSED → NORMALIZED → RATIO, + provenance de muestra | idempotencia S00/S02 refutada; 6 gates de corridas en fechas distintas, no de una sesión |
| **KO** | SEC EDGAR XBRL (us-gaap puro) | `PASS_WITH_WARNINGS` | US-GAAP de punta a punta sin tocar el core; 20/20 registry; 45.113 hechos; S03/S04 idempotentes | generalización de S01; **`is_custom`** (W-2); idempotencia S00/S02 |
| **METR** | CNV (formulario, sin XBRL) | `PASS_WITH_WARNINGS` | E2E completo **vía worktree**: 2.795 hechos, 0 violaciones, auditoría 0 fallas | el tramo C no está en el repo principal (D-1); ratios no se calculan (motor SEC-first, ver L-12) |

**Ninguno está certificado `PASS` de punta a punta en una sola sesión desde el
repo principal** (Parte XIII, GATE).

---

## Paso 2 · El estado por área funcional

### SEC E2E — operativo
S00→S04 con gates; 241 corridas en `engine.runs` (`OK` 61 · `ABORTED` 132 ·
`BLOCKED` 48 · `RUNNING` 0 — F-009 cerrado). 34 migraciones aplicadas.
**Deudas:** S00 y S02 no son idempotentes; S01 tiene `C-S01-004` clavado a YPF
(`SG-05`); no existe gate agregado (`L-4`).

### CNV E2E — parcial
Tramo A con gates pero **sin EEFF** (`SG-01`, `L-7`); tramo B legacy sin gate
ni ledger (`L-6`), con descarte silencioso (`CNV-EX-001/002`) y sin SHA
persistido (`SG-02`, `hash_cnv` NULL en 4.005/4.005); tramo C en worktree
(D-1). **Cobertura real de METR: 60 documentos** (58 con datos + 2 rechazados
por colisión de PK), no 286 (`SG-04`, `SG-12`).

### Market — operativo, sin enlace con la contabilidad
4.799.938 precios, 584 instrumentos, 51.917 acciones corporativas,
8.322 filas de calidad. **`market_instruments.entity_id` es entero legacy vs.
`CIK:`/`CUIT:`** (`SG-10`): ningún múltiplo precio+contable es trazable para un
emisor arbitrario; `derived.ratio` tiene 36 filas / 9 emisores sobre 584
instrumentos (`L-5`). 9 de 11 scripts documentados (`C-6`).

### Ratios — parcial
`derived.ratio` persiste **4** `canonical_id` (`eps`, `pe`, `pb`, `ev_sales`);
los **14 contables definidos no los persiste ninguna etapa** (`SG-03`), aunque
los insumos están completos para METR (14/14). La CNV publica 576 ratios
`CNV_*` como dato — control cruzado futuro, no sustituto.

### Homologación TIKR — un solo benchmark
METR FY2025: 152 métricas, 33,6 % coincidencias, 18,4 % diferencias explicadas
con aritmética exacta, **0 errores de Catalaxia**, 43,4 % sin insumo (desglose
no publicado por la CNV). `PASS_WITH_WARNINGS`. Procedimiento solo en worktree
(`N-8`, `D-4`, `C-4`).

### Provenance e Idempotencia
Los 9 eslabones hasta SHA256 funcionan para SEC y CNV; **Market no tiene
provenance** por `L-5`. Idempotencia demostrada con digests para S03/S04 y
para los adaptadores del worktree; **`job5` (tramo B) queda sin procedimiento
escrito** (`C-5`) y S00/S02 son el punto débil conocido.

### Pruebas
Suite completa citada en el ciclo TIKR: **378 passed · 3 failed (F-038,
preexistentes) · 1 skipped** (`L-15`). Universo de entidades: 9 de 7.998 con
hechos en la capa canónica (`L-16`).

---

## Paso 3 · El estado del manual

El índice define 17 capítulos + apéndices. Esta serie de Partes cubre la
materia entera; los rótulos dicen exactamente lo que cada pieza es:

| estado del rótulo | capítulos | decisión que los desbloquea |
|---|---|---|
| `NOT_IMPLEMENTED` | 6 (Economic Facts), 7 (Financial Model), 17 (TIKR), 10-C | **D-1** (repo principal vs. worktree) |
| `KNOWN_LIMITATION` | 9 (Market, `L-5`) | remoción de `SG-10`, no de este documento |
| `PARCIAL` | 10 (CNV), 15 (Troubleshooting) | árbol de diagnóstico por escribir; tramo C |
| `DECISION_REQUIRED` | 6, 7, 10-C, 17; también **D-3** (KO), **D-4** (vocabulario TIKR) | decisión de producto, no de documentación |
| ejecutables | el resto | — |

La serie **Partes I–XVIII** está escrita completa: la Parte I es el
arranque / "empezá acá" y esta Parte XVII el estado real; el mapeo
capítulo → Parte está en `MANUAL_TOC.md` §6.

---

## GATE de la Parte XVII

```
ESTADO REAL DEL SISTEMA = OPERATIVO CON DEUDAS CONOCIDAS
```

El sistema **produce datos correctos en los tres pilotos** — cero errores de
Catalaxia en la homologación, cero violaciones semánticas en 2.795 hechos,
auditorías independientes con 0 fallas — **y sin embargo el gate final del
sprint no es `PASS`**: la causa principal son las gaps de cobertura CNV
(`SG-04`/`SG-12`, una corrida incompleta que nadie detecta). Ese gate no se
cierra declarándolo; se cierra con la remediación de la Parte XVIII.

---

*Ninguna fila de este capítulo se corrigió para ser verdad: se midió. Las
fuentes citadas son las del 2026-09-04; re-medir es re-verificar, no re-leer.*