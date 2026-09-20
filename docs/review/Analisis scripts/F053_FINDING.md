# F-053 — LA INGESTA CNV NO ESTABA ANCLADA EN IDENTITY_V1

**Detectado:** 2026-08-31, al validar la Fase A del ciclo de producto
**Estado: CORREGIDO hacia adelante · atribución histórica ABIERTA**
**Severidad: alta** (identidad) · **no es blocker de datos**

---

## 1. El hallazgo

`c3_cnv_fetch.py` resolvía la identidad de la empresa sin consultar `identity_v1`:

| paso | fuente | problema |
|---|---|---|
| CUIT | `--cuit`, default `33650305499` | **hardcode de CEPU** en el fetcher |
| `entity_key` | `data/catalogo/cnv_identity_seed_cepu.csv` | seed específico de una empresa |
| fallback | `identity.entities` (schema **legacy**) | join por CUIT sobre la tabla vieja |
| último recurso | `CUIT:{cuit}` provisional | **seguía adelante igual** |

El docstring afirmaba «ninguna regla del código nombra a CEPU». El nombre del
archivo de seed y el default del argumento sí lo hacían.

## 2. Efecto medido

```sql
SELECT cuit, entity_key, count(*) FROM fetch_raw.cnv_download_log GROUP BY 1,2;

30546689979 | CUIT:30546689979 | 2437   -- YPF, provisional
30657862068 | CUIT:30657862068 |  692   -- TGS, provisional
33650305499 | CIK:0001717161   |  388   -- CEPU, tercer formato
99999999999 | CUIT:99999999999 |    1   -- CUIT inexistente
```

Tres formatos de clave, ninguno un `entity_key` de `identity_v1`, y un CUIT
inexistente que llegó a hacer el request.

La fila del CUIT `99999999999` **fue una prueba deliberada** de un ciclo anterior
—existe su reporte, `C3_CNV_STAGE_REPORT_run3_invalid_cuit_BLOCK.json`— y
efectivamente terminó en `BLOCK`. Pero el `BLOCK` lo emitió **`C-C3-001`**, que
valida el **contenido** de la página descargada (`V-MIN-SIZE`,
`V-EXPECTED-ENTITY`, `V-HAS-PRESENTATIONS`, `V-GENERIC-PAGE`). Es decir: el
sistema abrió corrida, hizo el request a CNV y recién después descubrió que la
empresa no existía.

**Ese rechazo no cuenta como prueba de la barrera de identidad**: la barrera no
existía. Cualquier CUIT sintáctamente válido abría una corrida y gastaba un
request contra CNV.

## 3. Lo que hacía más grave el asunto

`identity_v1` **tenía la respuesta correcta y el gate correcto**:

```
YPF   CIK 0000904851  CUIT 30546689979  VERIFIED
TGS   CIK 0000931427  CUIT 30657862068  VERIFIED
CEPU  CIK 0001717161  CUIT 33650305499  VERIFIED
GGAL  CIK 0001114700  CUIT 30704962807  CANDIDATE   <- debía bloquear
```

No faltaba el dato. Faltaba la consulta.

## 4. Corrección aplicada

`resolver_en_identity_v1()` es ahora la única fuente de identidad de C3:

- resuelve por CUIT **o por CIK** (por CIK, el CUIT se **deriva**);
- exige `assertion.status = 'VERIFIED'` sobre el identificador CUIT;
- devuelve el `entity_key` opaco real;
- `AMBIGUO` si el identificador resuelve a más de una entidad — no elige;
- **sin clave provisional**: sin entidad verificada, no hay corrida;
- `--cuit` sin default.

El seed C1 y `identity.entities` pasan a ser contraste: emiten hallazgo si
divergen, cortan si el CIK se contradice, y no deciden nada.

**Banco:** `scripts/engine/cnv_identity_bench.py` — **15/15**, incluyendo los
casos negativos (GGAL por CUIT y por CIK, CUIT inexistente, CIK sin CUIT) y la
equivalencia de las dos puertas de entrada.

**Corridas reales:** YPF y TGS por `--cik`, gate **10/10 PASS**, C-C3-010 al
100 % sin atribuciones cruzadas.

## 5. Lo que queda ABIERTO

Las **3.517 filas históricas** conservan su clave provisional. **No se
reescribieron**: esas descargas ocurrieron bajo un binding provisional y el
registro debe seguir diciéndolo. Reescribirlas sería reescribir el pasado para
satisfacer un contrato nuevo.

Atenuantes verificados:

- la atribución por **CUIT** siempre fue correcta (C-C3-010, corrida a corrida);
- **ningún consumidor río abajo lee `cnv_artifact.entity_key`** (búsqueda en todo
  el repo: sólo lo escribe C3 y lo cuenta `release_baseline.py`);
- las filas nuevas ya llevan el ULID.

**Corrección propuesta (no aplicada):** una vista de sólo lectura que resuelva
`cnv_artifact.cuit → identity_v1` y exponga el `entity_key` vigente, dejando
intacta la columna histórica. Requiere contrato de schema.

## 6. Lección

El fetcher tenía diez controles de gate en verde y ninguno miraba de dónde salía
el CUIT. **Los controles verificaban la ejecución, no la premisa.** El caso del
CUIT `99999999999` estaba en la base desde antes y ningún gate lo señaló, porque
para todos ellos era una descarga fallida más.
