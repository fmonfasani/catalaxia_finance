# 24 — Estado pre-F13 (baseline, solo lectura)

F10 cerrado (gap #11 CERRADO, #12 cerrado por decisión; resto de la matriz
intacto). Gap #5 asignado a F13 por `22_F10_GAP_UPDATE.md`. Este documento es
solo lectura + snapshot: no modifica código, datos ni configuración.
Evidencia `[CÓDIGO]`/`[EJECUCIÓN]`.

## 1. Git

- HEAD `aa02df9f80352b6492b87e05de0d148822c90b9b` — `docs(checkpoint): registrar
  resultado del checkpoint F5-F10 (b1d61f2)`.
- Branch `fix/ttm-ratios-cnv`.
- `git status --porcelain`: 237 entradas (modificados + sin versionar). Incluye
  todo F5–F10 (`docs/review/16_*` a `23_*`, `scripts/engine/c10_evaluate.py`,
  `tests/test_f5_multisource.py` …). **Nada de F5–F10 está commiteado.**
  `[EJECUCIÓN: git]`.

## 2. Alcance de F13 (desde la matriz)

Gap #5 (`21_F9_GAP_MATRIX.md`, `22_F10_GAP_UPDATE.md`):

> S03 replace-all / `NO_DANGLING` · CAPA PARSER / provenance · BLOCKER
> condicional · bloquea producción SÍ cuando se manifiesta (gate C10) ·
> evidencia existente: gate `NO_DANGLING` + 2 mediciones (90.398, curado) ·
> evidencia faltante: auto-mitigación.

Mitigación prevista por F6 (`17_F6_VALIDATION.md` §Gap S03): "no reemplazar si
0 filings". Nunca implementada: el gate C10 detecta el daño, no lo evita.

## 3. Contrato actual de S03 (pre-F13)

Fuente: `scripts/engine/s03_parse_ypf.py` (`[CÓDIGO]`, ~1000 líneas).

- Capa primaria C4 PARSED (ficha `06_EXECUTABLE_DEEP_AUDIT/S03.md`).
- Entrada: última corrida S02 con gate PASS **del mismo CIK**
  (`find_s02_input_run`, filtro por CIK — F-054), archivos verificados por
  sha256 contra `fetch_raw.download_log` (C-S03-002).
- Salida: `parsed.facts/contexts/units/concepts/link_relations/
  pre_xbrl_filings/companyfacts_compare/parse_errors` + artefactos
  `outputs/docs/fase_s03/` (XLSX + md + MANIFEST + VALIDATION).
- Gates bloqueantes C-S03-001…C-S03-008 (C-S03-009 informativo):
  conciliación filings, integridad RAW, provenance completa de facts,
  cobertura XBRL (`MIN_XBRL_FILINGS`, default 9), era pre-XBRL declarada,
  integridad referencial facts↔contexts/units, comparación CompanyFacts,
  outputs no vacíos. Resultado: `READY_FOR_S04` / `BLOCKED_S04`.
- Contrato S04 (consumidor): `docs/architecture/S04_CONTRACT.md` —
  `derived.fact.source_fact_ids` cita `parsed.facts.fact_id`; S04 hace upsert
  por `fact_key`, NUNCA borra parsed ni derived.

### 3.1. Secuencia de escritura de S03 (relevante para F13)

Orden actual en `_etapa` (`[CÓDIGO]`):

1. `DELETE FROM parsed.facts WHERE cik = X`
   `DELETE FROM parsed.pre_xbrl_filings WHERE cik = X`
   + `DELETE ... WHERE run_id = ANY(runs_previos)` sobre las otras seis tablas
   (`s03_parse_ypf.py:441-461`). Alcance por CIK (F-054); secuencia NO
   reiniciada.
2. Parse + `INSERT` por filing (`:463-521`).
3. `raw.commit()` (`:545`).
4. Gates C-S03-001… (`:613-731`) — **después del commit**.
5. Checkpoint S03 solo si gate PASS (`:796-804`).

Consecuencia: si el lote nuevo no produce hechos (re-parse vacío), el borrado
del paso 1 ya quedó commiteado en el paso 3; los gates del paso 4 BLOCKean la
corrida pero no restauran lo borrado.

## 4. Estado DEV (baseline de datos) — `catalaxia_engine@127.0.0.1:5433/catalaxia`

Medido `[EJECUCIÓN]` antes de cualquier reproducción:

| tabla | filas |
|---|---|
| `parsed.facts` | 157.482 (KO `0000021344`: 90.398 / 17 acc · YPF `0000904851`: 67.084 / 9 acc) |
| `parsed.contexts` | 47.486 |
| `parsed.units` | 550 |
| `parsed.concepts` | 28.346 |
| `parsed.link_relations` | 357.629 |
| `parsed.pre_xbrl_filings` | 32 |
| `parsed.companyfacts_compare` | 24.205 |
| `parsed.parse_errors` | 0 |
| `derived.fact` (vigentes, `valid_to IS NULL`) | 93.043 (YPF: 47.930 · KO: 45.113; 0 cerradas) |
| `derived.ratio` | 0 |
| `engine.runs` / `engine.stage_runs` / `engine.checkpoints` | 1.589 / 4.676 / 210 |

- `NO_DANGLING` (query idéntica a `c10_evaluate.py:107-111`): **0** `[EJECUCIÓN]`.
- Nota: los 90.398 facts de KO coinciden con la medición histórica del
  incidente F6 ("90.398 medidos dos veces, curados con re-run").

## 5. Cadena de provenance bajo análisis

`derived.fact.source_fact_ids` (bigint[]) → `parsed.facts.fact_id`
(escrito por S04, `s04_normalize.py:414,434-476`). Detectores:

- C10 `inv_no_dangling` (`c10_evaluate.py:105-114`, SOLO LECTURA):
  `dangling>0 → BLOCK`, `0 → PASS`.
- `ratio_inputs.py:32-42` (`INVARIANTE_PERTENENCIA`) + vista
  `derived.v_fact_pertenencia` (migración 032): exige además mismo CIK,
  mismo accession y mismo qname.
- Tests: `test_f054_aislamiento_emisores.py`
  (`test_ningun_source_fact_id_queda_colgado`), `test_f6_validation.py`.

## 6. Hipótesis a determinar en F13

> El replace-all de S03 borra `parsed.*` del CIK **antes** de conocer el
> resultado del parse y **commitea** antes de evaluar los gates; un re-parse
> vacío deja `derived.fact` vigente citando `fact_id` inexistentes
> (`NO_DANGLING > 0`). C10 lo convierte en BLOCK, pero solo detecta.

Responsabilidad candidata (a confirmar por reproducción): S03 (C4 PARSED),
bloque `_etapa` líneas 438-545. C10/C11/C12, Identity, Market y CNV quedan
fuera de alcance salvo que la evidencia demuestre lo contrario.

## 7. Reglas de F13 (recordatorio operativo)

RAW inmutable · PARSED ≠ NORMALIZED · todo derivado conserva provenance ·
no modificar C10/C11/C12 salvo necesidad demostrada · no tocar Identity,
Market, CNV · no tocar producción (DEV = puerto 5433, `is_prod=False`) ·
no borrar históricos · no reconciliar residuos automáticamente ·
no corregir síntomas en otra capa · si no se reproduce: clasificar
NO DETERMINABLE / GAP CONDICIONAL sin inventar implementación ·
no iniciar F14 ni F15.
