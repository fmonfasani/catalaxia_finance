# PARTE XI — IDEMPOTENCIA

Este capítulo no describe cómo **debería** ser la idempotencia del sistema:
describe cómo **es**, etapa por etapa, medida en vivo — y cuál es la prueba
que un operador tiene que hacer para creerla.

**Definición operativa:** una etapa es idempotente si puede volver a
ejecutarse sobre el resultado de sí misma **sin alterar el resultado
certificado**. Prueba mínima:

```
RUN 1  →  RUN 2  →  RUN 3
```

y debe cumplirse, para cada corrida:

```
hash1 == hash2 == hash3
rows1 == rows2 == rows3
```

**Regla del capítulo, antes de cualquier comando:** **nunca** dos corridas de
la misma etapa sobre el mismo emisor en paralelo. La demostración correcta es
siempre secuencial: correr → esperar finalización → correr. (La verificación
de este manual dejó dos corridas huérfanas por violar esta regla — Paso 3.)

---

## Paso 1 · El estado real por etapa — medido, no creído

Tabla medida el 2026-09-04 (fuente: `ANNEX_YPF.md` §13) y cruzada con el
Golden Run de KO:

| etapa | mecanismo real | resultado en segunda corrida | estado |
|---|---|---|---|
| **S00** | `INSERT` de checkpoint **incondicional**, sin `ON CONFLICT` (`s00_smoke.py`) | **falla**: `UniqueViolation` sobre `ux_checkpoints_reuse`, exit `1`, corrida `ABORTED` | 🔴 **refutada** (H-1) |
| **S01** | seed + links + resoluciones | no verificada en vivo en esta sesión; esperado según runbook: `identificadores nuevos = 0` | ⚠️ **no demostrada** |
| **S02** | `INSERT` incondicional, mismo defecto que S00 (`s02_fetch_ypf.py`) | **falla**: `UniqueViolation` — y **pierde el `report`** de una corrida cuyo fetch sí completó | 🔴 **refutada** (H-2) |
| **S03** | `ON CONFLICT ON CONSTRAINT ux_checkpoints_reuse DO UPDATE` (correcto) | checkpoint hit por diseño; **KO** demostró `hash_out` idéntico secuencialmente | ✅ **correcta** (KO); YPF sin reverificación en vivo (incidente, Paso 3) |
| **S04** | versionado por `valid_to` (cierra la versión, no borra) | no duplica: `C-S04-002` exige 0 hechos vigentes de más de una corrida; **KO**: `huella_igual = True` | ✅ **demostrada** |

**La lectura honesta:** hoy **dos** etapas del tronco SEC son activamente no
idempotentes (S00, S02), una está bien construida y probada fuera de YPF
(S03), una está demostrada (S04) y una no está demostrada (S01). El runbook
actual afirma lo contrario para S00 y S02 — este manual lo corrige con la
evidencia encima.

---

## Paso 2 · Las dos etapas refutadas — el defecto exacto

**S00** (ver Parte III, Paso 1): cuando el gate da `PASS`, el script hace un
`INSERT INTO engine.checkpoints` **incondicional**. La restricción única
`ux_checkpoints_reuse` es sobre
`(stage_id, input_hash, code_version, contract_version)` — **no** sobre
`checkpoint_id` (que es aleatorio cada vez). Como `input_hash` es
`sha256(settings.describe())`, la segunda corrida con la misma configuración
siempre produce el mismo hash y choca contra la primera. Reproducido en vivo:

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique
constraint "ux_checkpoints_reuse"
DETAIL: Key (stage_id, input_hash, code_version, contract_version)=
(S00_bootstrap, 5e9be1c9…, s0-bootstrap-v1, engine-state-v1) already exists.
```

**S02** (ver Parte III, Paso 4): el mismo patrón, con un matiz que lo hace
peor. El **trabajo de la etapa sí se ejecuta y se persiste antes** de llegar
al `INSERT` que falla: `fetch_raw.download_log` pasó de 740 a **927** filas
durante la corrida fallida de hoy (187 artefactos nuevos, 2002–2013). El
`report` y el checkpoint de esa corrida se pierden porque el `INSERT` que
falla está en la **misma transacción** que el `UPDATE` del report: al
revertirse, se cae el report pero sobrevive el fetch (que ya había hecho
commit). **Los datos quedan bien; la auditoría de esa corrida, no.**

**Qué NO hacer al encontrarse cualquiera de las dos:** no borrar el
checkpoint, no borrar RAW, no "arreglar a mano" la base. Registrar `run_id`,
etapa, error y base, y tratarlo como bug de idempotencia. La referencia de
cómo debe estar escrito ese `INSERT` es S03 (Paso 4).

---

## Paso 3 · El incidente que este manual no oculta

Durante la verificación del anexo (2026-09-04) dos invocaciones de S03
quedaron corriendo **en paralelo** sobre el mismo CIK por un error operativo
(un primer intento llegó a su timeout sin terminar y un relanzamiento no
confirmó que el primero hubiera muerto). Se las terminó con `kill -TERM`.

**Evidencia que queda registrada:** dos corridas huérfanas en `engine.runs`:

```
d3f94f7931be4f14b237280b7d820d91
4213c4b981ae4e76839aeddc22dec45e
```

en estado `RUNNING`. El sitio que las detecta existe (`s00_smoke.py` →
`edb.corridas_huerfanas`, `s04_normalize.py` → guard `F-009`), pero **no hay
procedimiento formal de limpieza** (`L-3`, sin rollback). No se intervino
sobre esas filas: `engine.runs` es un registro de eventos.

**Procedimiento del operador ante un `RUNNING`:**
1. No lanzar nada encima.
2. Identificar PID y `run_id`; verificar si el proceso está realmente activo.
3. Si es huérfano, detenerlo de forma controlada y **registrar el incidente**.
4. Recién entonces volver a correr.

---

## Paso 4 · Qué es lo correcto — y qué falta demostrar

**El patrón correcto (S03,** `s03_parse_ypf.py` líneas 793-797**):**
```sql
INSERT INTO engine.checkpoints (...) VALUES (...)
ON CONFLICT ON CONSTRAINT ux_checkpoints_reuse
  DO UPDATE SET checkpoint_id=EXCLUDED.checkpoint_id, run_id=EXCLUDED.run_id, ...
```
Con el comentario en el código: *"re-corrida con mismo input+code+contract es
un 'checkpoint hit' por diseño"*. KO demostró el `hash_out` idéntico en
corridas secuenciales. **Es la plantilla para arreglar S00 y S02.**

**Lo que hay que demostrar, en vivo, después del fix** (por emisor, nunca
simultáneamente, y en base aislada si se quiere sacrificar):

```
YPF    KO
S00×3  S00×3
S01×3  S01×3
S02×3  S02×3
S03×3  S03×3
S04×3  S04×3
```

y los cinco invariantes de cierre:

```
hash1 == hash2 == hash3
0 duplicados
0 pérdida
0 foreign pointers
0 RUNNING residuales
```

**GATE de la Parte XI:** ninguna etapa se declara idempotente **por lectura
de código**. La evidencia mínima es la de la definición: `RUN 1` y `RUN 2`
con hash idéntico y cero filas nuevas vigentes. Hasta hoy, **sólo S04 la
tiene en vivo para YPF** (indirecta) y **S03+S04 la tienen para KO**. S00,
S01 y S02 quedan sin marca de idempotente — con el defecto de las dos
primeras caracterizado a nivel de línea.

---

*El contenido de este capítulo es una medición, no una promesa. Los defectos
de S00/S02 se documentan, no se corrigen (Partes III-IV ya los citan como
H-1/H-2/H-3). Ninguna operación de este capítulo escribe en producción
(5432).*