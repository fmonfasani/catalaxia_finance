# PARTE XII — VALIDACIÓN

Este capítulo enseña a **leer un gate y validar una etapa** sin lugar a la
interpretación. La pregunta que responde: *"¿puedo avanzar a la etapa
siguiente, o tengo que parar?"*

**Material de base:** `docs/runbooks/01_COMMON_OPERATIONS.md` §5 y
`docs/runbooks/07_CERTIFICATION.md` §2. La consulta modelo de este capítulo
fue ejecutada en vivo (2026-09-04) contra la corrida de referencia.

---

## Paso 1 · Leer un gate: `PASS`, `WARNING`, `BLOCK`

**OBJETIVO**
Saber qué significa cada valor de gate y qué acción dispara.

**PREREQUISITOS**
Una corrida que haya terminado (Parte XII se aplica a `engine.stage_runs`,
no al medio de una corrida).

**QUÉ SIGNIFICA CADA GATE** (`engine/states.py` — son exactamente estos
tres, nada más):

| gate | exit code del script | qué significa | qué hacer |
|---|---|---|---|
| `PASS` | `0` | todos los checks bloqueantes pasaron | seguí a la etapa siguiente |
| `WARNING` | según el script | hay observaciones no bloqueantes | leé `gate_reasons`; podés seguir |
| `BLOCK` | `1` | un check bloqueante falló | **no sigas**; ERROR_CATALOG |

**COMANDO** — la consulta modelo, ejecutada en vivo:
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c "
SELECT stage_id, gate_status,
       report->'coverage'->>'expected' AS expected,
       report->'coverage'->>'parsed'   AS parsed,
       report->'coverage'->>'rejected' AS rejected,
       jsonb_array_length(report->'gate'->'checks') AS n_checks
  FROM engine.stage_runs
 WHERE run_id='d86bb4fe0cca4dd8a843a6069dc00c5b' AND report IS NOT NULL"
```

**RESULTADO ESPERADO** — salida real verificada:

```
 S03_parse | PASS | 27 | 27 | 0 | 9
```

Una sola fila: `gate = PASS`, `expected == parsed + rejected`
(27 = 27 + 0) y **9 checks** — la etapa no "terminó": **certificó**.

---

## Paso 2 · Las tres reglas que `StageReport.validate()` impone

**OBJETIVO**
Entender por qué una etapa puede fallar **al cerrar** aunque no haya lanzado
ninguna excepción.

`engine/report.py::StageReport.validate()` exige, y conviene conocerlo porque
explica fallas al cerrar la etapa:

1. **Campos obligatorios no vacíos** → si falta uno, *"Reporte incompleto…"*.
2. **`checks` no puede estar vacío** → *"terminó sin excepción nunca es
   PASS"* es una norma codificada del proyecto, no una opinión.
3. **Conciliación** `expected == parsed + rejected` → si no cierra, la etapa
   levanta *"Conciliacion invalida"* aunque no haya habido ningún error.

La regla 2 es la que más vale la pena memorizar: **un script que sale con
`exit 0` sin checks NO es una etapa certificada.**

**VERIFICACIÓN** — la consulta del Paso 1 te da los cuatro campos a la vez:
si `n_checks` es `0` o `expected != parsed + rejected`, la etapa no está
certificada, venga con el gate que venga.

---

## Paso 3 · La cascada de conteos que no se puede romper

**OBJETIVO**
Registrar, para cada Golden Run, los mismos conteos en el mismo orden, para
que una pérdida sea un número y no una sensación.

**Conteos a registrar siempre:**

```
expected  →  discovered  →  downloaded  →  parsed → rejected
         →  normalized  →  derived  →  published
```

**Regla:** si `expected != published`, **tiene que existir una explicación
con su número**. Sin explicación, es una pérdida de datos hasta que se
demuestre lo contrario.

**En el piloto YPF, esta cascada cierra hoy así** (de las Partes III-V con
sus `run_id`):

| eslabón | valor | de dónde |
|---|---|---|
| expected (filings) | 27 | S03 `d86bb4fe…` |
| parsed (filings) | 27 | ídem |
| rejected | 0 | ídem |
| facts parseados | 67.084 | `parsed.facts` |
| hechos normalizados | 47.930 | S04 `dc67d06f…` |
| ratios | 4 | `derived.ratio` |

---

## Paso 4 · Punteros foráneos = 0

**OBJETIVO**
Verificar, tras cada etapa crítica, que **ningún hecho apunte fuera de su
origen** — la propiedad que F-054 dejó limpia para el dataset SEC actual.

**QUÉ ES UN PUNTERO AJENO:** un `derived.fact.source_fact_ids` que apunta a
un `parsed.facts.fact_id` de otro emisor, otro filing u otro concepto — la
causa raíz original de F-061.

**CÓMO VERIFICARLO:**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/ratio_engine.py --cik 0000904851
```
la primera línea del motor es la guarda:
```
F-061 · punteros de provenance ajenos: 0
```
`0` es lo único que habilita a calcular. Cualquier número distinto → el motor
se niega (exit `1`) y es un incidente de datos, no un ajuste.

---

## GATE de la Parte XII

Una etapa está **certificada** cuando se cumplen **las cuatro condiciones**
(`07_CERTIFICATION.md` §2), aplicables a cualquier `run_id`:

1. `gate_status = 'PASS'` en `engine.stage_runs`.
2. `report` presente y válido: pasa `StageReport.validate()`.
3. `expected == parsed + rejected`.
4. **`checks` no vacío.**

Y toda corrida se guarda con su evidencia mínima (ver Parte XIII): `run_id`,
salida de consola, `report` JSON, `hash_in`/`hash_out` de S03/S04, las dos
verificaciones de no contaminación, fecha y `git_commit`. **Sin el `run_id`
no se reconstruye nada.**

---

*Las consultas de este capítulo se ejecutaron en vivo (2026-09-04). Ninguna
escribe en producción (5432).*