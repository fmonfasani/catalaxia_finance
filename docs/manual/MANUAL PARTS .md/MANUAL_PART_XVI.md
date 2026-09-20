# PARTE XVI — GOLDEN RUN

Un **Golden Run** es la ejecución completa y aislada del pipeline sobre un
piloto, con estado explícito por artefacto, verificación independiente y un
veredicto. **No es "correrlo y que termine": es correrlo y poder probar qué
pasó con cada documento.**

**Material de base:** `docs/runbooks/appendices/GOLDEN_RUNS.md` completo;
`outputs/docs/fase_cnv/METROGAS_GOLDEN_RUN_REPORT.md` completo;
`outputs/docs/fase_cnv/METR_FY2024_E2E_REPORT.md` y
`METR_FY2024_SNAPSHOT.json` (digests reproducibles).

---

## Paso 1 · El procedimiento estándar

1. **Aislar el entorno.** Fixture de base de datos propio
   (`metr_golden.db` / base `metrgolden`@5433, `kogolden`, etc.). Nunca la
   base homologada ni producción.
2. **Verificar el entorno** → Parte II: puerto `5433` (nunca 5432),
   `EXT-010`, `s.describe()` con `prod=False`, producción en solo `public`.
3. **Verificar la identidad** → S01 / tramo CNV A: la entidad existe y no se
   inventa ningún ancla.
4. **Correr la cadena** `S00 → S01 → S02 → S03 → S04` (SEC) o
   `C3 → job5 → normalización → adaptador canónico` (CNV).
5. **Modelo y ratios**: Financial Model (si está en rama) y ratio engine,
   sin persistir primero.
6. **Provenance**: por cada fact, `hecho → documento → RAW → SHA256`.
7. **Segunda (y tercera) corrida**: misma entrada → mismo `hash_out`, 0
   inserts, digests idénticos.
8. **Comparar hashes y conteos** antes/después, incluida la huella de
   `data/screener.db` y de producción.
9. **Auditar por un camino independiente** (parser y motor propios), y
   **mutar** un valor para demostrar que la verificación lo detecta.
10. **Escribir el reporte** con el veredicto y los entregables.

**Caso YPF, los comandos en orden** (`GOLDEN_RUNS.md` §1):
`ENGINE_DB_PORT=5433` para S00, S01, `s02_fetch_ypf.py`, `s03_parse_ypf.py`,
`S04 --dry-run` (obligatorio) y `S04`, y `ratio_engine.py --cik 0000904851`.

---

## Paso 2 · Qué se exige de un Golden Run

**La verificación determinística** (no los conteos, que dependen de cuántos
filings tenga EDGAR hoy):

| señal | valor exigido |
|---|---|
| los gates de las etapas | **6/6 en `PASS`** |
| `rows_failed` | **0** |
| `filings_rejected` | **0** |
| segunda corrida de S03 | **checkpoint hit + el mismo `hash_out`** |
| S04 | `hash_in` / `hash_out` impresos e iguales al de S03 |
| producción | **intacta** (`public` y nada más) |

**`RUNBOOK GAP (RG-01):`** no hay valores canónicos publicados para los
conteos (filings de YPF en EDGAR crecen con el tiempo). Lo que sí es
determinístico es lo de arriba — se exige eso, no un número de filas.

---

## Paso 3 · Casos existentes — qué esperar de cada uno

| caso | estado | veredicto | referencia |
|---|---|---|---|
| **YPF** (SEC) | completo | `PASS_WITH_WARNINGS` | `GOLDEN_RUNS.md` §1: 6 gates PASS, primer uso del pipeline fuera de un fixture |
| **KO** (SEC, US-GAAP puro) | golden run en `kogolden` | `PASS_WITH_WARNINGS` (6 hallazgos pendientes, ver Parte XIII) | primera generalización fuera del golden case |
| **METR** (CNV) | golden run CNV completo (worktree) | `PASS_WITH_WARNINGS` | `METROGAS_GOLDEN_RUN_REPORT.md` |
| **METR FY2024** (E2E certificado, worktree) | snapshot certificado | `PASS` con salvedad de origen | `METR_FY2024_E2E_REPORT.md` + digests en `METR_FY2024_SNAPSHOT.json` |
| **METR FY2025** (homologación TIKR) | comparación 152 métricas | `PASS_WITH_WARNINGS` | Parte XIV |
| **METR 30/09/2024** (diagnóstico) | caso obligatorio | 9/10 preguntas | Parte XV, `GOLDEN_RUNS.md` §3 |

**El reporte de METR (referencia de estructura):** veredicto; resumen con 10
métricas (`documentos con estado 286/286 · reconciliación cierra · SHA 286/286
· hechos canónicos 2.795 · violaciones 0 · idempotencia 0 inserts · auditoría
PASS · tests 18/18 · producción sin cambios`); census; provenance del RAW;
extracción; semántica; canonical; ratios; auditoría independiente; tests;
problemas encontrados; aislamiento; gate.

**El veredicto de METR, para calibrar:** `PASS_WITH_WARNINGS`, **no** `PASS` —
el criterio "ratios pasan donde existen inputs" falla (14/14 insumos
disponibles, 0 calculados, porque el motor homologado excluye CNV por diseño),
y **no es `BLOCKED`** porque ninguna condición de integridad falla. Las tres
advertencias en orden de impacto: P1 (el 79 % de las descargas no trajo el
documento — el techo real de cobertura es 60 documentos, no 286), P4 (sin
motor homologado CNV no hay ratios), P2 (dos hechos económicos existen en el
RAW y no caben en el modelo: la PK económica de `cnv_estados_v2` pierde
ocurrencias).

---

## Paso 4 · La prueba que certifica un Golden Run

Dos corridas de **cualquier** etapa deben producir el mismo digest; dos
corridas de todo el pipeline deben producir los mismos digests de las matrices
de salida y **0 inserts vigentes**. Ejemplo documentado (METR canonical):

```
derived_metr  2795   63b9ce0e874153c4558e8c75acdaca45
valores       2795   c5fd623fca726dd54f909f6b3b0bc177
parsed_metr   2795   3d69ed07e07e059659f4116ca9d44630
sec_intacto  133902  63629c0fc2ee76ad8038660c4815b443   ← SEC no se tocó
```

**Todo Golden Run termina con una auditoría independiente** (parser y motor
propios, con su propia transcripción del plan de cuentas) y **con una mutación
adversarial** que demuestre que el sistema detecta el cambio. El reporte de
METR: `c5_metr_golden_auditoria.py`, 0 fallas, y `tests/test_metr_golden_run.py`
18/18, donde la mutación del coverage guard rompe la reconciliación en los tres
casos.

---

## GATE de la Parte XVI

Un Golden Run está bien hecho cuando: (1) se corrió en aislamiento; (2) cada
documento tiene estado con motivo; (3) la reconciliación de cobertura cierra;
(4) el SHA se recomputó y la provenance llega al archivo; (5) la segunda corrida
da digests idénticos y 0 inserts; (6) la auditoría independiente no encontró
fallas; (7) una mutación fue detectada; (8) producción y `screener.db` quedaron
intactos salvo el tramo que se está ejercitando; y (9) el veredicto se declara
con `PASS_WITH_WARNINGS` si algún criterio no se cumple — **se enumera, no se
esconde**.

**`KNOWN_LIMITATION (L-4):`** no hay un gate agregado con exit code que
automatice (3) y (5): se leen de los reportes. `GOLDEN_RUNS.md` §1 advierte:
**si estos casos no dan lo esperado, no sigas con datos reales.**

---

*Ninguno de estos veredictos documentados se obtuvo corrigiendo código para
que la corrida pasara: se obtuvo corriendo el pipeline existente y midiéndolo.*