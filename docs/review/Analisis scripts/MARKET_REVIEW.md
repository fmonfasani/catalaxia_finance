# MARKET — AUDIT REVIEW

Auditor: **CIAA** · Ciclo **AUDIT-02** · Baseline `444ee1a`
Objeto: **M22** (`MKT-GOLDEN-20260825-89c2f00f26c0`) + estado de **M23**

## VEREDICTO

**PASS_WITH_WARNINGS — sostenido.** El checkpoint M22 está intacto y su evidencia,
verificada exhaustivamente en AUDIT-01, no cambió.

**M23 NO está validado.** Existe el código, no la ejecución ni la precondición.

---

## M22 — intacto

```
checkpoint_id : MKT-GOLDEN-20260825-89c2f00f26c0
veredicto     : PASS_WITH_WARNINGS
gates         : 35 total · VALID 29 · WARNING 6
batch_hash 83 : 192aa57329485470b2e91ba7e520bb47…      (idéntico a AUDIT-01)
```

No se re-verificó la cadena completa: en AUDIT-01 quedó comprobada de punta a punta
(paquete 11/11, RAW 26/26, `full_hash` sobre 14.979 filas con 0 mismatch, `batch_hash`
reproducido con reimplementación propia del spec, 3 registros de cambio con un único
`CHANGED` genuino, 18/18 tests). Los artefactos no cambiaron; re-hashear todo otra vez sería
gasto sin información nueva.

---

## M23 — código sí, validación no

`scripts/market/m6_scale.py` existe: **197 líneas**, creado 2026-08-25 10:41.

### No fue ejecutado — verificado

```
market_fetch_log    : 2 instrumentos · 21 corridas · última 2026-08-25 04:27:40
market_price_daily  : 2 instrumentos
```

Idénticos a AUDIT-01. La última corrida (04:27:40) es **anterior** a la creación del script
(10:41). **Cero contaminación de datos.** La instrucción de no ejecutar M23 masivo se
respetó, y el auditor tampoco lo ejecutó.

### La precondición que su propio plan exige sigue sin cumplirse

`MARKET_STATE.md` NEXT ACTION #2 dice:

> *"Decidir si Market necesita una guarda anti-prod propia (tipo EXT-010) **antes de correr
> `m6_scale.py` sobre las 584 instrumentos** contra `catalaxia`@5432."*

Verificado: **la guarda no existe.**

```
grep 'ALLOW_PROD|EXT-010|is_prod|5433'  m6_scale.py  m2_fetch_engine.py
   -> sin coincidencias

m6_scale.py:39   import m2_fetch_engine as eng
   -> hereda pg_conn(): DB_PORT=5432 · DB_NAME=catalaxia · sin guarda
```

El script **importa el motor de M22**, de modo que hereda su ruta de escritura por defecto:
exactamente la base que `engine/config.py:41` clasifica como producción y protege con
`EXT-010` para SEC/CNV.

Docstring del propio script: *"orquesta `run_instrument()` sobre el universo completo (o un
subconjunto) de instrumentos MAPPED"* — **584 instrumentos**.

---

## F-001 — OPEN, exposición aumentada

No es que el finding persista: **empeoró en exposición sin empeorar en materialidad.**

| | AUDIT-01 | AUDIT-02 |
|---|---|---|
| Guarda anti-prod | ausente | **ausente** |
| Código de escalamiento | no existía | **197 líneas listas** |
| Distancia a materializarse | "falta escribir el script" | **"falta ejecutar un comando"** |
| Contaminación real | ninguna | **ninguna** |

La condición pasó de prospectiva a inminente. Sigue sin materializarse, y por eso no bloquea
M22 — pero **es precondición de M23** y el propio plan de Market así lo establece.

---

## Calidad del diseño de `m6_scale.py` — observación favorable

No corresponde auditar código no ejecutado, pero su docstring declara decisiones que merecen
registro porque anticipan problemas reales de escala:

- **RESUME** reutilizando `market_raw_runs` en vez de inventar un estado nuevo —
  *"no se inventa un estado nuevo: se reusa el que el motor ya escribe"*.
- **QUARANTINED nunca se reintenta automáticamente** — *"es una señal de integridad, no un
  error transitorio, y re-intentar a ciegas podría taparla"*.

Ese segundo criterio es el correcto y es exactamente el sesgo —flag antes que arreglo
automático— que Market ya demostró en M22 al marcar como no benigno un cambio de volumen del
0,002 %. **No auditado en ejecución.**

---

## Contribución a los hallazgos transversales

Market es la capa con **mejor provenance del programa**: su paquete golden incluye
`MANIFEST.json` y `provenance.csv` con hashes por archivo, lo que permitió verificarlo
íntegro **sin tocar la base** en ambos ciclos. Es el estándar que CNV todavía no alcanza
(F-005).

Y es la capa **más aislada de las otras dos**: vive en `catalaxia`@5432 mientras SEC y CNV
viven en `catalaxia-engine-dev`@5433. Ningún join SQL puede cruzarlas. Su `entity_id`
(entero, `72`) pertenece a un espacio de identidad distinto del `'CIK:0000904851'` del
engine, y **no tiene foreign key** (verificado: `pg_constraint` devuelve 0 filas) porque la
tabla que referencia —`dim_entity`— sólo existe en el SQLite legacy. Ver **F-011** y el
`CROSS_WORKSTREAM_REVIEW`.

Aspecto positivo del modelado: los instrumentos 83 (YPFD/BUE/ARS) y 84 (YPF/NYSE/USD)
comparten `entity_id=72` con `ratio_adr=1.0`. **Separa correctamente instrumento de emisor**
y no usa el ticker como identidad.

## Evidencia consultada

- `outputs/docs/fase_market/golden/CHECKPOINT.json`
- `catalaxia`@5432 · `market_fetch_log`, `market_price_daily`, `market_instruments`,
  `pg_constraint`
- `scripts/market/m6_scale.py` (lectura, sin ejecución) · `m2_fetch_engine.py`
- `.claude/state/MARKET_STATE.md` (contrastado contra disco — ver F-006)
