# PARTE V — NORMALIZACIÓN (S04)

Este capítulo cubre la etapa que transforma **`parsed` → `derived`**: S04 toma
los hechos estructurales de la Parte IV y los convierte en hechos
normalizados en `derived.fact`, resolviendo **unidad, desempate y
pertenencia**. Con YPF como piloto y KO como segunda fuente de evidencia.

**Ningún número de este capítulo es hipotético.** Lo verificado en vivo el
2026-09-04 o citado de `engine.stage_runs.report` persistido con su `run_id`.
Fuente primaria: `docs/manual/ANNEX_YPF.md` y el Golden Run KO.

**La regla del capítulo, antes de los comandos:**

- **La primera corrida es SIEMPRE `--dry-run`.** SIEMPRE. S04 escribe
  `derived.fact`; el dry‑run te muestra qué va a resolver sin tocar nada.
- **Ver `SKIP` en el dry-run no es un error** — `C-S04-005..009` están
  diseñados para saltarse en ese modo.
- **La normalización no fuerza equivalencias.** El sistema se niega a asumir
  `Liabilities = Debt`, `Total Equity = Equity atribuible a la controladora`,
  `Weighted Average Shares = Shares Outstanding`, ni a mezclar perímetros
  `CONSOLIDADO`/`INDIVIDUAL`. Lo que no resuelve queda como
  `sin_unidad`/`sin_entidad`/`sin_contexto` NO silencioso — y en YPF eso dio
  exactamente **0**, porque las fichas lo verifican, no lo asumen.

---

## Paso 1 — S04 · normalizar YPF

**OBJETIVO**
Llevar los 67.084 facts parseados de YPF a hechos normalizados vigentes en
`derived.fact`, sin pérdida y sin duplicados.

**PREREQUISITOS**
Parte IV, Paso 1 (S03) con gate `PASS` — S04 consume la corrida certificada
del parser, no cualquier otra.

**COMANDO** — los dos, en este orden:
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py --dry-run
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s04_normalize.py
```

**QUÉ HACE**
Recorre `parsed.facts` de la última corrida certificada de S03, agrupa por
hecho económico (qname + contexto + unidad), resuelve el desempate entre
representaciones, y escribe `derived.fact` con versionado por
`valid_to` (la versión vieja se cierra, no se borra).

**RESULTADO ESPERADO**
`gate = PASS`. Corrida certificada de referencia — `run_id=dc67d06fc5454b0984
f4bb95e7ee565b` (2026-08-31, 22:37:19Z → 22:39:02Z), ligada exactamente al
S03 de la Parte IV:

```json
"gate": {"status": "PASS"},
"input": {"rows": 67084, "stage": "S03_parse",
          "run_id": "d86bb4fe0cca4dd8a843a6069dc00c5b",
          "checkpoint_id": "d86bb4fe0cca4dd8-s03"},
"coverage": {
  "grupos": 47930, "emitidos": 47930,
  "desempates": {"UNICO": 29077, "IDENTICO": 18753, "POR_PRECISION": 100},
  "sin_unidad": 0, "sin_entidad": 0, "sin_contexto": 0, "unidad_no_resuelta": 0
},
"integrity": {
  "hash_in":  "f02684d9278252273b4a6cd843b60126772c5b0ed026b9b2bafd3cae1582597c",
  "hash_out": "a896b8251d1111f2bb84aae3791f7eee66a4833a33bdcc670ee0a52d67bf7811"
}
```

Los 9 checks (`C-S04-001..009`) en `PASS`. `C-S04-001` recalcula el
`hash_out` de S03 y lo iguala; `C-S04-002` certifica que ningún CIK tenga
hechos vigentes de más de una corrida; `C-S04-004` certifica que todo CIK
resuelve a una entidad.

**VERIFICACIÓN**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT count(*) FROM derived.fact WHERE cik='0000904851' AND valid_to IS NULL"
```
Debe dar **47.930** — coinciden exactamente con `emitidos` de la corrida de
referencia. Ni uno más ni uno menos.

**SI FALLA**

- *"CIK sin entidad" sobre un emisor:* la identidad no quedó sembrada → Parte
  III, Paso 3 (backfill). **Registrá el incidente**: documenta que el flujo
  S01 todavía no es genérico.
- *`sin_unidad`/`sin_entidad`/`sin_contexto` distinto de 0:* S04 da el
  conteo explícito. No lo escondas: cada uno tiene un motivo que la
  provenance debe explicar, no un silencio.
- *`C-S04-002` en rojo:* hay hechos vigentes de más de una corrida — ese sí
  es un incidente de datos, no una limitación conocida.

---

## Paso 2 · Cómo se elige el fact (el desempate)

**OBJETIVO**
Leer el campo `desempates` del reporte y entender qué mide cada regla.

**QUÉ SIGNIFICA CADA REGLA**, con la evidencia de cada piloto:

| regla | qué decide | YPF (47.930) | KO (45.113) |
|---|---:|---:|
| `UNICO` | hay una sola representación: no hay nada que desempatar | 29.077 | 3.082 |
| `IDENTICO` | varias representaciones con el **mismo valor**: se quedan con la primera | 18.753 | 26.172 |
| `POR_PRECISION` | representaciones con **distinto valor**: gana la más precisa | 100 | 12.746 |
| `POR_FACT_ID` | representaciones con distinto valor sin precisión disponible: gana el menor `fact_id` | — | 3.113 |

**POR QUÉ IMPORTA LEERLO BIEN:** la distribución de desempate es parte de la
referencia del sistema. **Si una corrida nueva produce una distribución
distinta para el mismo conjunto de entrada, no la ignores**: es señal de que
cambió algo en el parser, el orden de presentación, los contextos, los facts
o la selección. Investigá antes de avanzar, no después.

---

## Paso 3 · S04 · idempotencia

**OBJETIVO**
Confirmar — con evidencia, no con afirmaciones — que una segunda corrida no
duplica nada.

**QUÉ HACE EL SISTEMA**
S04 no borra: **versiona**. Una corrida nueva cierra la versión vigente
(`valid_to` = ahora) y emite la nueva. Por eso la pregunta correcta de
idempotencia es *"¿hay hechos vigentes de más de una corrida?"*
(`C-S04-002`), no *"¿cambiaron las filas?"*.

**EVIDENCIA**
- **YPF** (indirecta, verificada el 2026-09-04): el conteo de vigentes
  (47.930) coincide exactamente con `emitidos` de la corrida certificada —
  no hay duplicados residuales.
- **KO** (Golden Run, base aislada `kogolden`): **45.113 entrada = 45.113
  recomputados, `huella_igual = True`** — misma salida recalculada
  digest por digest.

**VERIFICACIÓN** — el digest que no cambia:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT count(*), count(DISTINCT (cik, tag, report_period, value_numeric, currency))
     FROM derived.fact WHERE cik='0000904851' AND valid_to IS NULL"
```
El `count(*)` debe ser igual o mayor que el `count(DISTINCT …)` **sólo** por
factores legítimos de cardinalidad (p. ej. dimensionales). Un desfasaje que
no se explica es contaminación de la segunda corrida.

---

## Resumen de la Parte V

| paso | qué | corrida de referencia | estado |
|---|---|---|---|
| 1 · S04 | `parsed` → `derived.fact` | `dc67d06f…` (2026-08-31) | ✅ **PASS 9/9**, 67.084 → 47.930, 0 pérdida |
| 2 · desempate | reglas `UNICO`/`IDENTICO`/`POR_PRECISION` (+`POR_FACT_ID` en KO) | YPF 29.077/18.753/100 · KO 3.082/26.172/12.746/3.113 | ✅ parte de la referencia |
| 3 · idempotencia | versionado `valid_to`, sin duplicados | KO `huella_igual=True` | ✅ demostrada |

**GATE de la Parte V:** `gate = PASS` con 9/9 checks, `grupos == emitidos`
(sin pérdida), 0 en los cuatro contadores de *sin algo*, y el conteo de
vigentes de `derived.fact` coincide con `emitidos`. **`--dry-run` primero,
siempre.**

**Lo que sigue:** quienes consumen estos hechos — ratios (Parte VII), y si se
quiere la traza hacia atrás de cualquier número, provenance (Parte X). El
`econ_key` de estos hechos SEC es NULL por diseño (Parte IX CNV lo puebla):
ver `ANNEX_YPF.md` §9 — es alcance, no omisión.

---

*Los comandos de este capítulo fueron ejecutados y sus salidas verificadas
(2026-09-04) o citadas de `engine.stage_runs.report` persistido con su
`run_id` exacto. Ninguna operación escribe en producción (5432).*