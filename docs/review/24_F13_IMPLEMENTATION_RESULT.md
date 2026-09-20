# 24 — F13: S03 replace-all / provenance / NO_DANGLING — resultado

FASE F13 (gap #5 de `21_F9_GAP_MATRIX.md` / `22_F10_GAP_UPDATE.md`).
CAPA: PARSED (+ impacto en PROVENANCE). PLANOS: DATOS + CONTROL.
CICLO: DEFINIR → IMPLEMENTAR → VERIFICAR. Evidencia
`[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`.

## 1. Veredicto

**PASS_WITH_WARNINGS.**

- PASS: el defecto existe, se reprodujo, se corrigió en la capa responsable
  (PARSED/S03) con la mínima intervención, y quedó verificado por ejecución
  real (2 E2E completos), tests nuevos (16/16) y suites objetivo (114 green).
  `NO_DANGLING = 0`, provenance bit-idéntica, C10 sec PASS, higiene latest-2
  restaurada.
- WARNINGS: la regresión completa (1036 tests) deja 58 fallos + 12 errores,
  **todos triados como externos a F13** (§10): pre-existentes/stale
  (51) o fragilidad de fixtures expuesta por operación legítima del pipeline
  (19, familia cert-linkage f2/f8/f3). Ninguno indica pérdida de provenance,
  corrupción o incumplimiento del objetivo F13. No se corrigió ninguno
  (regla: no corregir fallos ajenos a F13).

## 2. Escenario reproducido [EJECUCIÓN]

`s03-replace + re-parse vacío ⇒ dangling`, en DEV (puerto 5433), dentro de
UNA transacción con ROLLBACK (0 residuo):

```
ANTES  dangling=0 parsed_ko=90398 derived_ko=45113 punteros_ko=90398
DESPUES dangling=90398 parsed_ko=0     (borrado S03 réplica exacta, sin re-inserción)
ROLLBACK ejecutado → RESTAURADO dangling=0 parsed_ko=90398
```

- La réplica ejecuta literalmente el bloque de borrado de S03
  (`parsed.facts` + `pre_xbrl_filings` por CIK + 6 satélites por `run_id`,
  `s03_parse_ypf.py` pre-F13 líneas 441-461) para KO (`0000021344`).
- `NO_DANGLING` medido con la query exacta de C10
  (`c10_evaluate.py:107-111`).
- **Los 90.398 coinciden exactamente con la medición histórica de F6**
  ("90.398 medidos dos veces"): son los punteros de provenance de los
  45.113 `derived.fact` vigentes de KO. El incidente queda re-explicado:
  un re-parse vacío borró esos 90.398 facts y los 90.398 punteros colgaron.

## 3. Causa raíz [CÓDIGO]

`_etapa` de S03 ejecutaba, en este orden:

1. `DELETE` del parsed previo del CIK (siempre, incondicional);
2. parse + `INSERT` del lote nuevo;
3. `raw.commit()` — el borrado queda persistido;
4. gates C-S03-001… — **después** del commit.

Un lote nuevo vacío (S02 sin filings, o filings sin hechos) commiteaba la
destrucción y los gates BLOCKeaban la corrida sin restaurar nada. S04 no
puede recuperar ese estado (sin facts fuente no hay de dónde re-derivar);
solo un re-run manual S03+S04 lo curaba. C10 detectaba (`NO_DANGLING → BLOCK`)
pero no podía evitarlo: el daño ya estaba commiteado.

## 4. Responsabilidad determinada

- **Responsable: S03 (C4 PARSED)** — único escritor de `parsed.*`, dueño del
  reemplazo destructivo y del orden commit-antes-que-gates.
- **Exonerados con evidencia:**
  - S04 (C5 NORMALIZED): solo genera provenance (`source_fact_ids`,
    `s04_normalize.py:414`), hace upsert por `fact_key`, nunca borra parsed
    ni derived (migración 016 se lo prohíbe al rol app).
  - C10 (C10 VALIDACIÓN): SOLO LECTURA; su BLOCK ante dangling es el
    comportamiento correcto (verificado: sigue BLOCKeando lo que debe, §8).
  - Identity / Market / CNV: no participan en la cadena del defecto.
- **Sin cambios en:** C10, C11, C12, Identity, Market, CNV, producción,
  runtime, deploy, Dockerfiles. RAW inmutable (solo añade archivos nuevos;
  `fetch.py` bloquea overwrite).

## 5. Implementación (mínima, solo PARSED)

Archivo: `scripts/engine/s03_parse_ypf.py` (único archivo productivo tocado).

1. **`decidir_reemplazo(previas_con_hechos, filing_results)` (nueva, pura):**
   el borrado solo procede si el lote nuevo reproduce TODOS los filings que
   ya tenían hechos Y trae hechos nuevos. Devuelve
   `(reemplazo_ok, faltantes_ordenados, hechos_nuevos)`.
2. **Reorden parse-first:** todo el parse ocurre en memoria sin escribir;
   borrado + inserción ocurren en la MISMA transacción y SOLO si
   `reemplazo_ok` (bajo `if reemplazo_ok:`, mismo predicado F-054 por CIK,
   sin `setval`). Si no: cero DELETE/INSERT, se conserva el parsed anterior,
   el checkpoint S03 no se actualiza (S04 sigue consumiendo el parsed previo
   intacto) y la corrida BLOCKea.
3. **Check `C-S03-010` (bloqueante, primero de la lista):** documenta
   `ejecutado / filings_previos_con_hechos / hechos_nuevos / faltantes`.
4. **ANALYZE (F-028) omitido cuando no hubo reemplazo** (tablas sin cambios);
   resto del flujo (gates, `StageReport`, checkpoint, outputs, validación)
   intacto. `StageReport.validate()` sigue cerrando (conciliación
   `expected == parsed + rejected` invariante por construcción).
5. Clave `reemplazo` agregada a `S03_VALIDATION.json` y al resumen JSON.

La guarda cubre los tres modos de vacío: lote sin filings, filings previos
ausentes del lote, y filing presente pero degradado a 0 hechos (REJECTED).
Un retiro legítimo de un filing también rehúsa (BLOCK ruidoso con la lista
exacta) antes que perder provenance en silencio — I-006 por encima de
conveniencia.

## 6. Ejecuciones reales (DEV 5433, solo DEV) [EJECUCIÓN]

| run_id | tipo | S00 | S01 | S02 | S03 | S04 | estado |
|---|---|---|---|---|---|---|---|
| `70a4ba8a…` | E2E YPF (interrumpido) | PASS | PASS | PASS | — (corte en parse, pre-writes) | — | ABORTED limpio, 0 huérfanas |
| `8ea68966…` | S03 standalone YPF | — | — | — | PASS 67.084 facts, C-S03-010 PASS | — | OK (intermedio verificación) |
| `3f0fecf1…` | S04 standalone YPF | — | — | — | — | PASS 47.930, 9/9 | OK (intermedio verificación) |
| `facdc35c…` | **E2E YPF** | PASS | PASS | PASS 187 (184 SIN_CAMBIOS+3 DOWNLOADED) | PASS 67.084, reemplazo 9/9, `hash_out 69e4dc87…` | PASS 47.930, `checkpoint facdc35c868040dc-s04`, `hash_out 3c4b8e30…` | OK, exit 0 |
| `9d5cbc1a…` | **E2E KO** | PASS | PASS | PASS 536/541 (532 SIN_CAMBIOS+4 DOWNLOADED, 5 FAILED 404 headers pre-XBRL) | PASS 90.398, reemplazo 17/17, C-S03-010 PASS | PASS 45.113, `checkpoint 9d5cbc1a10c54209-s04`, `hash_out eedb7af3…` | OK, exit 0 |

- `hash_out` S03 idéntico entre corridas con mismo RAW (determinismo I-007;
  el digest v2 excluye `run_id`/seriales/rutas por diseño).
- S02 KO: 5 `FAILED` son HTTP 404 de `index-headers.html` de filings
  2008-2011 (era pre-XBRL, SEC ya no los sirve); gate S02 PASS por diseño
  pre-existente, sin impacto en facts (verificado: 90.398 = baseline).
- S02 re-descargó 3 (YPF) + 4 (KO) archivos sin cambio semántico
  (digests de contenido y derived idénticos, §7).

## 7. Métricas NO_DANGLING + provenance + idempotencia [EJECUCIÓN]

| momento | NO_DANGLING | nota |
|---|---|---|
| pre-F13 | 0 | baseline |
| reproducción (tx+rollback) | **90.398** | defecto confirmado; DEV intacto tras rollback |
| tras S03 standalone YPF | 67.084 (todo YPF) | **transitorio por diseño**: fact_ids nuevos, derived aún cita viejos; KO=0 |
| tras S04 | 0 | pipeline normal lo resuelve (el incidente F6 era irrecuperable por S04: parsed vacío) |
| tras E2E YPF + E2E KO | **0** | estado final |

Provenance antes/después (huellas `md5` sobre `derived.fact` vigente):

| CIK | derived_n | md5(fact_keys) | md5(clave=valor) |
|---|---|---|---|
| YPF pre → post | 47.930 → 47.930 | `25d585e1…` = | `ae8933d8…` = |
| KO pre → post | 45.113 → 45.113 | `1b497519…` = | `c7b9872b…` = |

- Idénticas bit a bit tras 2 re-parse + 2 re-normalize completos:
  **idempotencia semántica (I-008) verificada por ejecución.**
- `parsed.facts`: YPF 67.084/9 accs/1 corrida; KO 90.398/17 accs/1 corrida
  (mismos volúmenes, nuevas corridas).
- Pertenencia F061 (`ratio_inputs.violaciones_pertenencia`): **0**.
- Cobertura de la guarda: toda accession citada por derived vigente existe
  en parsed del mismo CIK (verificado por query; test regresivo).

## 8. C10 continúa comportándose correctamente [TEST+EJECUCIÓN]

- `c10_evaluate.py`: **0 líneas modificadas.**
- Evaluación sec-scope sobre los 2 runs E2E nuevos
  (`9d5cbc1a`, `facdc35c`): `SEC_GATES/IDENTITY/PROVENANCE/NO_DANGLING/
  NO_ORPHAN_ENTITY` = **PASS**, veredicto **PASS**.
- La detección que originó el gap sigue operativa: la misma query contó
  90.398 en la reproducción (§2) y 0 en el estado final.
- Suite `test_f6_validation.py`: PASS (incl. A/B tras restaurar higiene, §9).

## 9. Higiene latest-2 [EJECUCIÓN]

Últimos S04-PASS: `9d5cbc1a` (e2e, completo) y `facdc35c` (e2e, completo),
status OK. El S04 standalone intermedio de verificación (`3f0fecf1`,
`engine-v1`, cadena incompleta por diseño) quedó 3º por antigüedad,
desplazado de forma append-only (nada borrado). `_pass_runs(n=2)` vuelve a
seleccionar solo cadenas E2E completas.

## 10. Tests y regresión [TEST]

- **Nuevos `tests/test_f13_no_reemplazo.py`: 16/16 PASS** — 7 puros de
  `decidir_reemplazo` (vacío/parcial/degradado/fiel/primer-parse/
  vacío-total/determinismo), 3 guardas de código (decisión precede al
  borrado, alcance CIK F-054 intacto, C-S03-010 bloqueante), 3 causales en
  schema temporal (defecto sin guarda → 6/6 colgados detectados por query
  C10; con guarda → 0 escrituras + 0 dangling; lote fiel → permitido), 3
  invariantes sobre el universo DEV real (lote fiel aceptado incl. 9+17
  accessions, cobertura derived⊆parsed, NO_DANGLING=0).
- **Suites objetivo: 114 passed, 1 skipped** (f13, f6/C10, f054, c11, s04,
  s03-xbrlparse).
- **Regresión completa: 942 passed, 23 skipped, 1 xfailed; 58 failed +
  12 errors, todos triados como externos a F13** (ninguno se corrigió):

| cluster | n | causa verificada | relación F13 |
|---|---|---|---|
| CNV/identidad stale (cnv_authority T8, cnv_identity_link, f038×5, f040×3, f041×2) | 12 | Sin M23 market en DEV; sin artefactos CNV en PG (C10 CNV_SCOPE=WARN lo declara); CUITs ya verificados; assertions F-041 en estado distinto. f041 falla igual aislado. Tablas no tocadas por F13 (S01 escribió 0 filas) | NINGUNA (gap #13 pre-existente) |
| Fixtures cert-linkage (f2×7, f8×12 errors, f3×10) | 29 | Fixtures exigen CERTIFICADA con derived del mismo `run_id`; S04 (upsert por `fact_key`, pre-existente) refresca `run_id` en cada re-ejecución. Evidencia: acta `47ee85a1`/CERTIFICADA 2026-09-08 apuntaba al S04 vigente al iniciar F13 (fixture entonces satisfacible); mis E2E de verificación —operación legítima, igual que cron— movieron el linkage. Actas intactas, datos intactos. Toda acta CERTIFICADA histórica (cientos, 06→09/09) tiene hoy 0 derived del mismo run: el fixture solo pasa en universos congelados tras certificar | INDIRECTA-procedimiento, NO código (cualquier S03+S04, con o sin F13, lo provoca). Fragilidad del fixture → mantenimiento futuro (endurecer a contenido o re-certificar en el test). No se tocó C11 |
| ratio_ev_sales | 19 | Requieren AAPL/GGAL/CEPU: 0 filas parsed/derived en DEV (nunca ingeridos). YPF/KO bit-idénticos | NINGUNA (pre-existente) |
| r2_secretos | 7 | Esperan `deploy.py`/`deploy_production.sh` que nunca existieron en el repo (`git ls-files`: solo `deploy.sh`) | NINGUNA (pre-existente; territorio F12) |
| r3_raw | 1 | PASS aislado y en subconjuntos; FAIL solo en orden de suite completa → escritor mid-suite a `data/raw` (mtimes 01:37:24 dentro de la suite; otro a 01:42:22 post-suite sugiere actividad paralela externa, coherente con runs 00:02 ajenos). F13: 0 escrituras a disco verificadas por código | NINGUNA (aislamiento de tests pre-existente) |
| f5_market | 1 | Guarda `MARKET_ALLOW_PROD_WRITE` del script market | NINGUNA (Market prohibido) |
| runbook | 1 | Falta `outputs/runbook/` (directorio inexistente en el checkout) | NINGUNA (pre-existente) |

## 11. Observaciones externas registradas (no F13, no tocadas)

- Runs `25aa6a2e/bce425c7` (s1 BLOCKED) y `736f337d` (s2 ABORTED) a las
  00:02 UTC: actividad ajena a F13, terminales, no tocados.
- Escrituras `data/raw/engine` 01:37:24 (en ventana de suite) y 01:42:22
  (post-suite): re-fetch S02 YPF ajeno a las suites F13 (ningún test F13
  escribe a disco); posible actividad paralela externa.
- `outputs/docs/fase_s03/*` y `fase_s04/*` fueron re-escritos por las
  corridas de verificación (artefactos operativos DEV, ya modificados en el
  árbol antes de F13).

## 12. Archivos modificados por F13

1. `scripts/engine/s03_parse_ypf.py` — hunks F13: `decidir_reemplazo()`,
   parse-first + `if reemplazo_ok:` (borrado/inserciones), C-S03-010,
   `reemplazo` en validación/resumen, ANALYZE condicional. (El archivo ya
   traía cambios no commiteados pre-F13 —multiemisor F-054, `--cik`,
   E2E— sobre los que F13 se apoya; ver `24_PRE_F13_STATE.md`.)
2. `tests/test_f13_no_reemplazo.py` — nuevo, 16 tests.
3. `docs/review/24_PRE_F13_STATE.md` — nuevo (baseline pre-cambio).
4. `docs/review/24_F13_IMPLEMENTATION_RESULT.md` — este documento (nuevo).

No-touch verificado: C10/C11/C12, Identity, Market, CNV, producción
(puerto 5433 en todas las ejecuciones), runtime, deploy, Dockerfiles,
históricos (cero borrados; higiene restaurada append-only).

## 13. Cierre

- Gap #5 (S03 replace-all / NO_DANGLING): **defecto real → corregido →
  verificado**. Mitigación "no reemplazar si 0 filings" (F6) implementada
  como guarda condicional atómica en PARSED. Recomendación: darlo por
  CERRADO en la próxima matriz (este documento no modifica históricos).
- Estado F13: **PASS_WITH_WARNINGS** (warnings = §10, todos externos).
- Blockers restantes para F13: **ninguno**.
- STOP. No se inició F14 ni F15.
