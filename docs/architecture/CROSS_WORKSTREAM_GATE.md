# CROSS_WORKSTREAM_GATE — ciclo 7

**Fecha:** 2026-08-28 · **Instancia:** `catalaxia-engine-dev` 127.0.0.1:5433
**Evidencia:** `outputs/docs/fase_identity/audit_cross_cnv.json`
**Reproducible:** `python scripts/engine/audit_cross_cnv.py`

---

## VEREDICTO: **PASS**

La cadena SEC → Identity v1 → CNV funciona de extremo a extremo y **gobierna** el
fetch: el CUIT con el que se consulta a la CNV sale exclusivamente de
`identity_v1`, y sólo si hay un bridge CIK↔LEI ratificado por una persona.

Con dos hallazgos abiertos que no bloquean el gate: **F-039** (corregido) y
**F-040** (registrado, no corregido).

---

## 1. El resultado

| ticker | CUIT | ratificó | RAW | DB | gates | clase |
|---|---|---|---|---|---|---|
| YPF | 30546689979 | Federico | 4919 | **4919** | 10/10 PASS | cargada |
| TGSU2 | 30657862068 | Federico | 2385 | **2385** | 10/10 PASS | cargada |
| CEPU | 33650305499 | Federico | 1861 | **1861** | (ciclo previo) | cargada |
| GGAL | — | — | 0 | 0 | — | **D — bloqueado** |

RAW y DB reconcilian **exacto** por dos vías independientes: el auditor cuenta
GUIDs con su propio regex sobre el HTML crudo; el pipeline los cuenta con su
parser. Coinciden en los tres casos.

Descargas: YPF 1.782 artefactos / 114 MB · TGSU2 692 / 46,9 MB. Integridad RAW
re-verificada **releyendo el disco**: `mismatch=0, faltantes=0` en ambos.

## 2. GGAL es la prueba, no una omisión

GGAL no se bloqueó por una lista negra. Se bloqueó porque **no hay entidad
anclada en su CIK autoritativo**, y el resolver se detiene antes de consultar la
CNV. Es el control negativo del gate: si el CUIT saliera de `dim_entity` o de un
CSV, GGAL habría fetcheado igual.

## 3. Controles transversales

| control | resultado |
|---|---|
| CUITs en CNV sin identidad autoritativa | `[]` |
| relaciones fuera del dominio observado | `[]` |
| autorreferencias sin marcar | `0` |
| CUIT autoritativo sin assertion VERIFIED | `0` |

## 4. Clasificación de los ceros

Un resultado de 0 documentos nunca se reporta como «sin datos». Se clasifica:

- **A** — el perfil respondió y no declara presentaciones (ausencia real)
- **B** — el CUIT resuelve pero nunca se fetcheó (ausencia de ejecución)
- **C** — hay RAW con presentaciones y la base tiene 0 (defecto del cargador)
- **D** — Identity v1 bloqueó antes de consultar (comportamiento correcto)

TGSU2 estuvo en **B** durante este ciclo y pasó a cargada. GGAL está en **D** y
debe seguir ahí hasta que exista una decisión humana sobre su identidad.

## 5. Hallazgos de este ciclo

### F-038 — el hallazgo era mío, no de Market · **CERRADO**

M23 **sí** dejó traza: 591 filas en `market_raw_runs` de la instancia dev. Yo
consulté producción, donde Market no escribe por diseño (F-001). Reconciliación
exacta contra el reporte, y 40/40 hashes verificados contra disco.

Segunda vez que cometo el mismo error de inferencia: antes fue *«no está en la
tabla» ≠ «no ocurrió»*; ahora *«no está en la base que miré» ≠ «no está
registrado»*. La causa raíz es de método, no de código: **toda auditoría de
Market declara primero contra qué instancia consulta.**

Se agregó `ck_estado_coherente_con_artefacto` (migración 025) y 13 tests. Mi
primera versión del constraint exigía `row_count IS NULL` en `FAILED` y **habría
roto la próxima corrida de M23** — el escritor real inserta `0`. Se detectó
contrastando contra las filas reales.

### F-039 — el dominio se escribió con una sola empresa · **CORREGIDO**

`cnv_presentation_relacion_check` admitía sólo `CONTROLADA|VINCULADA`. YPF
declara además `CONTROLANTE`, y el fetch entero moría. El parser ya lo preveía
(`CLASE_EEFF_RELAC_OTRA`); el CHECK no.

Lo importante no era el valor: en esas filas `cuit_relacionado` es el CUIT del
propio perfil — la arista va al revés. Migraciones 026 y **027**, porque *mi
primer fix se quedó corto por la misma razón que el bug*: lo definí como
`relacion='CONTROLANTE'` y los datos mostraron 32 filas `CONTROLADA` que también
autorreferencian. Cubría 4 de 36 casos. El invariante es `cuit_relacionado = cuit`.

También se corrigió el desglose del gate C-C3-007, que informaba
`declaradas=584 (244 + 338)` = 582: los 2 `CONTROLANTE` desaparecían del informe
sin que nada fallara. Ahora se deriva de un `Counter`, así que no puede volver a
no cerrar contra su propio total.

### F-040 — C3 deja corridas huérfanas · **REGISTRADO, NO CORREGIDO**

`engine.runs` tiene 3 filas en `RUNNING` sin nada corriendo: los tres fetch de
CNV que murieron hoy. `c3_cnv_fetch.py` tiene **cero** usos de `run_scope()`.
F-031 migró S03; C3 nunca se migró. No corrompe datos: corrompe el relato.
Detalle y corrección propuesta en `F040_HALLAZGO.md`.

## 6. Lo que este gate NO certifica

- **No certifica el backfill masivo.** Ver `BACKFILL_READINESS.md`: la capa CIK
  es mecánica; la capa CUIT requiere **14 decisiones humanas** pendientes y los
  56 de BYMA están estructuralmente bloqueados.
- **No certifica que no haya más dominios calibrados sobre CEPU.** F-039 apareció
  con la segunda empresa. Hay que asumir que habrá más, y que los encontrará una
  corrida real, no un test.
- **No certifica GGAL.** Sigue sin identidad resuelta, por decisión explícita.
- **No toca producción.** Todo ocurrió en 5433. Market no escribió en 5432.

## 7. Restricciones respetadas

Sin commits · sin backfill masivo · sin re-ejecutar M23 · sin modificar SEC,
S03, S04, `ticker_canonico` ni `dim_entity` · sin borrar evidencia histórica ·
sin inventar CUIT · GGAL no ratificado · escrituras en `data/raw/` únicamente
por operaciones CNV que el contrato de C3 establece.
