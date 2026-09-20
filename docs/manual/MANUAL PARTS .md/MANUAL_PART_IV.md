# PARTE IV — PARSER (S03)

Este capítulo cubre la etapa que transforma **RAW → `parsed`**: el parser
XBRL de S03, con YPF como piloto. Aquí los tags XBRL se vuelven hechos
estructurales (`parsed.facts`, `parsed.contexts`, …) **sin** convertirse
todavía en conceptos económicos — esa conversión es la Parte V (S04).

**Ningún número de este capítulo es hipotético.** Lo verificado en vivo el
2026-09-04 o citado de `engine.stage_runs.report` persistido con su `run_id`.
Fuente primaria: `docs/manual/ANNEX_YPF.md` y
`outputs/docs/fase_s04/KO_GOLDEN_RUN_REPORT.md`.

**Lo que S03 debe preservar, operativamente** (toda esta lista sale de la
especificación del parser, no de una observación): namespaces, conceptos,
valores, unidades, decimals, escala, signo, contextos, entidad, períodos,
`instant`/`duration`, dimensiones, ejes, miembros, segmentos y relaciones.

**Regla para leer este capítulo** — S03 es **la excepción feliz** del bloque
de idempotencia: es la única etapa de este tramo cuyo `INSERT` de checkpoint
está bien escrito. El Paso 2 explica por qué, y sirve como la referencia de
cómo deberían estar escritos S00 y S02 (Parte III, hallazgos H-1/H-2).

---

## Paso 1 — S03 · parsear YPF

**OBJETIVO**
Parsear el RAW de YPF descargado en la Parte III y persistir los hechos
inventariados en `parsed`.

**PREREQUISITOS**
Parte III, Paso 4 (S02) con gate `PASS` — S03 lee el RAW que S02 dejó listo.

**COMANDO**
```bash
ENGINE_DB_NAME=catalaxia ENGINE_DB_PORT=5433 python scripts/engine/s03_parse_ypf.py --cik 0000904851
```

Antes de copiar: `python scripts/engine/s03_parse_ypf.py --help`. La sintaxis
exacta sale del `--help`, no de la memoria. Los argumentos conocidos hoy:
`--cik` y `--min-xbrl`.

**QUÉ HACE**
Recorre los 27 filings de YPF (2002–2026), parsea los paquetes XBRL de los
últimos 9 (2017 en adelante) y declara la era pre-XBRL de los anteriores
(`C-S03-005`), persiste facts/contextos/unidades/conceptos, y cierra con un
checkpoint real bajo el esquema `hashout-v2`.

**RESULTADO ESPERADO**
`filings_rejected = 0`, `gate = PASS`, exit `0`. Corrida certificada de
referencia — `run_id=d86bb4fe0cca4dd8a843a6069dc00c5b` (2026-08-31, 22:31:25Z
→ 22:37:11Z, unos 5m46s):

```json
"gate": {"status": "PASS"},
"input": {"rows": 187, "checkpoint_id": "S02:711c2d1a478845df98551663632728fb"},
"coverage": {"parsed": 27, "expected": 27, "rejected": 0,
             "by_reason": {"BAD_INPUT": 0, "REJECTED_FILING": 0}},
"integrity": {
  "hash_in":  "a5f05ee9e4e58a8882a9ee838077973243b9513fc4759f47b5ffe7d851855f04",
  "hash_out": "a05cb59cb412d49022238128bb6d0f10de8695b38e059f50dcdd777915ed70c4",
  "hash_spec": "hashout-v2"
}
```

Los 9 checks (`C-S03-001..009`) en `PASS`. Los que importan leer bien:

| check | qué certificó esa corrida |
|---|---|
| `C-S03-003` | **0** violaciones de provenance sobre el conjunto parseado |
| `C-S03-005` | era pre-XBRL declarada para los filings sin XBRL |
| `C-S03-006` | **0** `context_refs` colgantes: todo contexto referenciado existe |

**VERIFICACIÓN**
```bash
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT count(*) FROM parsed.facts WHERE cik='0000904851'"
docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -tAc \
  "SELECT count(*) FROM parsed.contexts WHERE run_id IN
     (SELECT DISTINCT run_id FROM parsed.facts WHERE cik='0000904851')"
```
En el entorno de referencia: **67.084** facts y **23.478** contextos, ambos
de la corrida `d86bb4fe…` — coinciden exactamente con la corrida certificada.

**SI FALLA**
- `filings_rejected > 0` y el `by_reason` muestra `REJECTED_FILING`/`BAD_INPUT`
  → hay un filing que S03 no pudo parsear; no se inventa ni se omite: el
  rechazo queda declarado (`rejected_count`), no silencioso.
- timeout o lentitud → S03 puede tardar ~6 minutos en el caso completo; es
  esperado. **No relances en paralelo** mientras otro S03 del mismo CIK siga
  corriendo (ver Paso 2).

---

## Paso 2 — S03 · idempotencia (la correcta)

**OBJETIVO**
Saber por qué S03 es la referencia de idempotencia que S00/S02 **no** siguen.

**QUÉ DICE EL CÓDIGO** (`scripts/engine/s03_parse_ypf.py`, líneas 793-797):

```sql
INSERT INTO engine.checkpoints (...) VALUES (...)
ON CONFLICT ON CONSTRAINT ux_checkpoints_reuse
  DO UPDATE SET checkpoint_id=EXCLUDED.checkpoint_id, run_id=EXCLUDED.run_id, ...
```

Con un comentario explícito en el código: *"re-corrida con mismo input+code+
contract es un 'checkpoint hit' por diseño"*. A diferencia de S00 y S02
(INSERT incondicional, hallazgos H-1/H-2), aquí una segunda corrida con la
misma configuración **no choca**: reusa el checkpoint.

**EVIDENCIA EXTERNA (KO)** — el Golden Run del segundo piloto (base aislada
`kogolden`) demostró `hash_out` idéntico en corridas secuenciales. KO es la
prueba de que el patrón generaliza fuera de YPF.

**`KNOWN_LIMITATION`** — **no revertificado en vivo el 2026-09-04.** Durante
la verificación de `ANNEX_YPF.md`, dos invocaciones de S03 quedaron corriendo
en paralelo por un error operativo de la sesión (un primer intento que alcanzó
su timeout y un relanzamiento que no confirmó que el primero hubiera muerto);
se las terminó con `kill -TERM`. **La propiedad de idempotencia de S03 queda
respaldada por lectura de código en esa verificación, no por una segunda
corrida en vivo.** El dato certificado no se tocó (`derived.fact` siguió en
47.930 filas vigentes después de terminar los procesos), pero las dos
terminaciones dejaron corridas huérfanas en `engine.runs`:

```
d3f94f7931be4f14b237280b7d820d91
4213c4b981ae4e76839aeddc22dec45e
```

en estado `RUNNING`. No se intervino (no hay procedimiento de limpieza
documentado — `L-3`).

**SI FALLA** (esto aplica al operador, no a S03):
1. **Nunca** corras dos S03 simultáneos sobre el mismo CIK. La demostración
   correcta de idempotencia es secuencial: correr → esperar finalización →
   correr → esperar → correr.
2. Antes de lanzar una corrida, comprobá que no haya `RUNNING` huérfanas:
   ```bash
   docker exec catalaxia-engine-dev psql -U catalaxia -d catalaxia -c \
     "SELECT run_id, stage_id, status FROM engine.runs WHERE status='RUNNING'"
   ```
   Si hay, es el escenario que `s00_smoke.py` (`corridas_huerfanas`) y
   `s04_normalize.py` (guard `F-009`) están diseñados para detectar. No lances
   encima: registrá el incidente.

---

## Paso 3 — Bug `is_custom` · `KNOWN_LIMITATION` (severidad P0)

**OBJETIVO**
Que el operador reconozca el defecto de taxonomía más importante del parser —
porque no se ve en YPF y sí va a verlo al correr cualquier emisor US-GAAP.

**QUÉ ES**
En `scripts/engine/s03_parse_ypf.py:483` el parser decide si un concepto es
`is_custom` con:

```python
tax = qn.split("#")[0].rsplit("/", 1)[-1]
```

Eso toma el **último segmento de la URI**. Funciona para IFRS **por
casualidad** (las URIs IFRS terminan con el nombre de la taxonomía) y rompe
con las taxonomías de FASB/SEC, que terminan con la **versión**:

| URI | resultado correcto | línea 483 | `is_custom` |
|---|---|---|---|
| `…/ifrs-full` | `ifrs-full` | `ifrs-full` | `False` ✓ |
| `http://fasb.org/us-gaap/2024` | `us-gaap` | **`2024`** | `True` ✗ |
| `http://fasb.org/srt/2019-01-31` | `srt` | **`2019-01-31`** | `True` ✗ |
| `http://xbrl.sec.gov/dei/2025` | `dei` | **`2025`** | `True` ✗ |

**Evidencia medida:** en KO, **los 45.113 hechos tienen `is_custom = True`**;
en YPF, solo ~44%. En filosofía de proyecto: un `is_custom` falso marca como
"extensión propia" a us-gaap, srt y dei, que son taxonomías estándar.

**Por qué no se ve en YPF:** la estructura de namespace IFRS hace que la
lógica funcione accidentalmente. Es el mismo patrón de "bug que un solo piloto
no puede revelar".

**ACCIÓN OBLIGATORIA** (documentada, no hecha todavía — esta Parte no
corrige código): el parser de S03 debe usar la función común
`_taxonomy_of()` de `engine/xbrlparse.py` como **única** fuente de
determinación de taxonomía, en lugar de duplicar la lógica con `rsplit`.
Después, regresión YPF + KO. Clasificación de prioridad: **P0**.

**DÓNDE ESTÁ DOCUMENTADO** — `outputs/docs/fase_s04/KO_GOLDEN_RUN_REPORT.md`
§5, hallazgo **W-2** (commiteado en `3e85c10`, `docs(ko)`).

**SI FALLA** (*"este emisor aparece casi todo como custom"*):
Probablemente es este bug, no un dato raro. **No corrijas la base a mano:**
se corrige la lógica de S03 y se regenera. (Ver `MANUAL_SCOPE.md`, regla: los
datos derivados se regeneran, no se parchan.)

---

## Resumen de la Parte IV

| paso | qué | corrida de referencia | estado |
|---|---|---|---|
| 1 · S03 | RAW → `parsed` | `d86bb4fe…` (2026-08-31) | ✅ **PASS 9/9**, 27/27 filings, 67.084 facts, 23.478 contextos |
| 2 · idempotencia S03 | `ON CONFLICT…DO UPDATE` | `kogolden` (KO) | ✅ patrón correcto; ⚠️ no revertificado en vivo (2 huérfanas `RUNNING`) |
| 3 · `is_custom` | lectura de taxonomía | KO | 🔴 **`KNOWN_LIMITATION` P0** — `s03_parse_ypf.py:483` duplica mal `_taxonomy_of()`; sin corregir |

**GATE de la Parte IV:** S03 da `PASS` con 27/27 y `filings_rejected = 0`, y
el `hash_out` de la corrida es verificable contra `engine.stage_runs`. El bug
`is_custom` **no invalida el gate** de YPF (el registry resuelve por `tag`,
no por `is_custom`), pero **impide certificar** el atributo `is_custom` de
cualquier emisor US-GAAP hasta corregirse.

**Lo que sigue:** la normalización (Parte V, S04 — lleva estos 67.084 facts a
47.930 hechos en `derived.fact`, con el desempate y el digest).

---

*Los comandos de este capítulo fueron ejecutados y sus salidas verificadas
(2026-09-04) o citadas de `engine.stage_runs.report` persistido. Ninguna
operación escribe en producción (5432). Los hallazgos H-1/H-2/H-3 (Parte III)
y W-2/P0 (este capítulo) se documentan, no se corrigen.*