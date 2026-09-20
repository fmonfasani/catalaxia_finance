*# E2E_RELEASE_GATE — Catalaxia V1.0.1

**Fecha:** 2026-08-31 · **Rol:** Release Recovery + E2E Auditor
**Base E2E:** `e2e_final` (descartable) · **Base homologada:** intacta, DELTA = 0
**Sin commits. Sin junctions. Sin `worktree remove --force`. Worktree oficial.**

---

# DICTAMEN: **PASS_WITH_WARNINGS**

El E2E completo corre de punta a punta sobre instalación limpia y reproduce el
baseline. F-050 y F-051 quedan **cerrados**. Queda **una** verificación imposible por
pérdida de RAW y **un finding nuevo** sobre el modelo de provenance.

---

## A. PASS

| control | evidencia |
|---|---|
| **Instalación limpia** | **30 migraciones** (29 engine + `market/012`), luego +2 de market tras `m19_apply_schema` = **32**, **0 duplicados** |
| **F-051 · Market instalado** | `ck_estado_coherente_con_artefacto` **= 1** · `venue_ticker` **= 1** · rol `catalaxia_market_ro` **= 1** |
| **Banco de migraciones** | **14/14** — incluye rollback total (ni tabla de registro ni objetos huérfanos) |
| **S00** | gate PASS, 2/2 |
| **S01** | gate PASS, 4/4 checks |
| **S02** | gate PASS, **187/187**, 0 fallidos |
| **S03** | **27/27 filings** = 9 XBRL + 18 PRE_XBRL, 0 rechazados |
| **S04** | **9/9 checks**, **47.930** facts, `huella_igual=True` |
| **F-026 no reaparece** | units `DIVIDED` **44**, sin `numerator`/`denominator`: **0** |
| **F-028 no reaparece** | S03 completó sin timeout |
| **F-029 hashout-v2** | `C-S04-001` declarado = recalculado |
| **F-031 / F-040 no reaparecen** | S03 y C3 con `run_scope`, 0 huérfanas |
| **F-050 · lifecycle** | **0 RUNNING** · estados sólo `OK`/`BLOCKED` · S00/S01/S02 sin `finished_at` nulo · banco **19/19** con mutación |
| **Identity backfill** | **512 elegibles**, 512 creadas, **0 CUIT autoritativos**, **0 bridges automáticos** |
| **Idempotencia Identity** | 0 creadas en la 2ª corrida, hash de identidad estable |
| **Checkpoints** | **0** en corridas ≠ OK; los 5 stages con checkpoint |
| **Provenance** | 0 facts sin `source_hash` · 0 derived sin `source_fact_ids` |
| **Auditoría independiente** | **22/22**, reconstruida desde PostgreSQL sin helpers del implementador |
| **No regresión** | base homologada `525\|614\|67084\|47930\|584\|0` — **sin cambios** |
| **Suite** | **226 passed**, 1 failed (ver §D), 1 skipped |

### Reconstrucción mínima ejecutada — 10 requests

| artefacto | requests | resultado |
|---|---:|---|
| `catalogo_edgar/company_tickers_2026-08-31.json` | 1 | 795.179 B · 10.391 filas · 8.004 CIK |
| `submissions/` EXXON + ELECTRONIC ARTS | 2 | validados por `cik` y `name`, no por nombre de archivo |
| `submissions/` los 6 de F-041 | 6 | descargados y **comparados contra su hash histórico** |
| `submissions/CIK0000904851.json` (YPF) | 1 | contiene el accession de 2017 |
| filings + submissions de YPF para S02/S03 | 0 | los bajó **S02**, mecanismo oficial |

**No se descargó Market ni CNV. No se ejecutó M23.**

---

## B. PASS_WITH_WARNINGS

### B.1 · Regresión introducida por F-051, detectada y corregida en este ciclo

El cambio de formato de registro (`engine/001_…` en vez de `001_…`) **rompió
`C-S00-001`**, que consultaba el nombre desnudo. S00 dio **BLOCK** en la primera
ejecución del E2E.

Corregido en `s00_smoke.py` y `f049_bench.py`: ambos aceptan los dos formatos, igual
que `_ya_aplicada`. **Es parte necesaria de F-051**, no un cambio de alcance.

Vale registrar cómo apareció: no lo encontró un test, lo encontró el E2E al correr la
etapa real contra una base nueva.

### B.2 · El catálogo de SEC es un recurso vivo

`company_tickers.json`: **10.403 filas el 23/08 → 10.391 el 31/08**; 7.998 → 8.004 CIK
únicos. El E2E **no puede ser byte-idéntico** al anterior por esta razón, y aun así el
inventario del backfill dio **512 elegibles**, exactamente igual.

### B.3 · Dependencia de orden no documentada: S04 requiere Identity poblado

S04 falló con `C-S04-004: CIK sin entidad en identity_v1` porque el backfill no había
corrido. **No es defecto**: es una dependencia real del pipeline que ningún contrato
declara. Corriendo el backfill primero, S04 dio 9/9.

Conviene documentarlo en el contrato de S04. No se hizo en este ciclo.

### B.4 · EXXON ya no declara ticker en SEC

`submissions/CIK0000034088.json`: `tickers: []`, `exchanges: []` — antes
`['XOM']`/`['NYSE']`. Confirma la sucesión societaria detectada en el ciclo 8
(`ExxonMobil Holdings Corp`, CIK 2115436, tomó el ticker). **Cambio de la fuente, no
del sistema.**

---

## C. BLOCKED

**Ninguno.** No hay defecto técnico que impida la operación.

---

## D. LIMITATIONS_OF_EVIDENCE

### D.1 · `test_f038_traza_corrida::test_el_hash_de_la_base_es_el_del_artefacto_en_disco`

**FALLA, y es correcto que falle.** Verifica los 577 `sha256` de `market_raw_runs`
contra `data/raw/market/`, que se perdió y cuya descarga este ciclo **prohíbe
explícitamente**.

La base conserva los 577 hashes: **la verificación es posible en el futuro**, no hoy.
**No se cuenta como PASS.**

### D.2 · F-052 — la provenance depende de artefactos que el sistema no custodia

**Finding nuevo.** Al re-descargar los 6 `submissions` de las re-afirmaciones de F-041
y compararlos contra el `sha256` que declaran:

```
0/6 byte-identicos
```

`submissions/CIK<n>.json` es un **recurso vivo**: cambia con cada presentación del
emisor. El hash hizo su trabajo —detectar el cambio— pero **el artefacto original no
estaba archivado en ningún lado**, así que esas 6 assertions citan un hash que ya no
puede reproducirse.

**No lo causó el incidente**: aunque `data/raw` no se hubiera borrado, esos hashes
habrían dejado de coincidir igual. El borrado sólo adelantó el descubrimiento.

**No es blocker**: los datos persistidos están intactos y la provenance conserva
fuente, cita y autor. Lo que caducó es la verificabilidad byte a byte.

Detalle y correcciones posibles en `docs/review/F052_FINDING.md`. **No corregido.**

### D.3 · No verificable por pérdida definitiva

| | |
|---|---|
| `data/raw/market/` (577 artefactos) | verificación de F-038 contra disco |
| `data/raw/engine/cnv/` (3.514) | verificación de CNV contra disco |
| 8.014 de los 8.021 `submissions` | sólo se recuperaron 7 |
| `company_tickers_2026-08-23.json` | el catálogo exacto del baseline |

---

## Criterio de cierre

| condición | estado |
|---|---|
| E2E reproducible PASS | **sí** — S00→S04 completo sobre instalación limpia |
| Auditoría independiente PASS | **sí** — 22/22 |
| Banco mutacional PASS | **sí** — F-050 19/19, F-051 11/11, migraciones 14/14 |
| Cero RUNNING | **sí** — en E2E y en la homologada |
| Migraciones correctas | **sí** — 32, 0 duplicados, orden determinista |
| Sin regresiones | **sí** — la de B.1 se detectó y corrigió dentro del alcance |
| PostgreSQL intacta salvo cambios esperados | **sí** — DELTA = 0; sólo +3 registros de migración |
| Evidencia RAW suficiente para lo afirmado | **parcial** — ver §D |

# **F-050 = CLOSED** · **F-051 = CLOSED**

Ambos cumplen todas las condiciones. Su evidencia **no depende** del RAW perdido: se
verifican contra PostgreSQL, el catálogo de constraints y los bancos mutacionales.

Lo que queda sin verificar (§D) **no pertenece a F-050 ni a F-051**: son controles de
integridad de F-038, de CNV y del modelo de provenance (F-052).
