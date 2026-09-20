# F-054 — S03 DESTRUYE LA PROVENANCE DE LAS EMPRESAS YA INGERIDAS

**Detectado:** 2026-08-31, por la auditoría independiente del screener (control E1)
**Severidad: alta** · **Es blocker de la vertical de producto**
**Estado: CORREGIDO + re-parseo** (ver §6)

---

## 1. El hallazgo

La auditoría del screener verifica que cada insumo de cada ratio llegue hasta
`parsed.facts` y coincida con su `source_hash`. Falló:

```
E1 · cada insumo llega a parsed.facts con su source_hash
     53 cadenas completas, 36 rotas
     ['CEPU/effective_tax_rate: parsed.fact 696 sin ese source_hash', ...]
```

Al mirar qué era realmente el `fact_id` 696:

```
fact_id | cik        | tag                                    | source_file
    696 | 0001114700 | YieldUsedToDiscountCashFlows...        | ggal-20251231_htm.xml
```

**Pertenecía a GGAL**, no a CEPU.

## 2. La causa

`s03_parse_ypf.py`, antes de parsear:

```python
for table in PARSED_TABLES:
    cur.execute(f"DELETE FROM {table}")
cur.execute("SELECT setval(pg_get_serial_sequence('parsed.facts','fact_id'), 1, false)")
```

**Borra las cinco tablas de `parsed` enteras y reinicia la secuencia de
`fact_id` en 1.** Es un diseño de *staging* de un solo emisor: correcto mientras
el sistema tuviera un único golden case, destructivo en cuanto se ingiere un
segundo.

El reseteo de la secuencia es lo que convierte el borrado en **corrupción
silenciosa**: los `fact_id` se reutilizan, así que los `source_fact_ids` que
`derived.fact` guardó para una empresa pasan a resolver contra las filas de
otra. No quedan colgados: **apuntan a datos ajenos y el join devuelve una fila.**

## 3. Alcance medido

Tras ingerir CEPU, TGSU2 y GGAL:

```
parsed.facts:  30.898 filas, TODAS de CIK 0001114700 (GGAL)
               (antes del ciclo: 67.084 filas, de YPF)

derived.fact -> parsed.facts, siguiendo source_fact_ids[1]:

  cik_derived  hechos  sin_origen  origen_de_OTRA_empresa
  0000904851    47930      19308                   28622
  0000931427     7301          0                    7301
  0001717161     2660          0                    2660
```

**Ni un solo hecho derivado de YPF, TGS o CEPU conserva su origen correcto.**

## 4. Por qué no lo detectó ningún gate

`C-S04-006` («hechos sin fila de origen: 0») y `C-S04-005` («fact_ids citados
que no existen en el insumo: 0») se evalúan **dentro de la misma corrida**, con
`parsed` recién poblado por ese S03. En ese instante todo cierra.

La corrupción aparece en la corrida **siguiente**, cuando otro emisor vuelve a
resetear la secuencia. Ningún control mira la coherencia *entre* corridas.

> Los gates verificaban la consistencia de la corrida, no la del sistema. Es la
> misma familia que F-053: el control confirmaba la ejecución, no la premisa.

## 5. Segundo defecto de la misma familia

`find_s02_input_run(engine)` toma **la última corrida S02 con gate PASS**, sin
filtrar por CIK:

```python
SELECT r.run_id FROM engine.runs r
 WHERE EXISTS (... stage_id='S02_fetch' AND gate_status='PASS')
 ORDER BY r.started_at DESC LIMIT 1
```

Con un solo emisor era inequívoco. Con varios, re-parsear la empresa A después
de haber hecho el fetch de B toma **los archivos de B** y los escribe bajo el
CIK de A, porque `parse_filing` etiqueta las filas con `GOLDEN_CIK`. Es
atribución cruzada, y ocurre sin error.

## 6. Corrección

1. **Borrado con alcance.** S03 elimina sólo lo que pertenece al CIK que va a
   re-parsear: las filas de `parsed.facts` con ese `cik`, y las de las otras
   cuatro tablas cuyo `run_id` pertenece a corridas previas de ese mismo CIK.
2. **La secuencia no se reinicia.** Los `fact_id` siguen creciendo, así que un
   id nunca designa dos hechos distintos. Ésta es la parte que impedía que el
   borrado fuera recuperable.
3. **`find_s02_input_run(engine, cik)`** filtra por el CIK, usando
   `fetch_raw.download_log.cik` para saber a qué emisor pertenece cada corrida
   de S02.
4. **Re-parseo** de las empresas ya ingeridas, para que sus `source_fact_ids`
   vuelvan a apuntar a sus propias filas.

## 7. Lo que esto no es

- **No es pérdida de datos contables.** `derived.fact` conserva valor, tag,
  moneda, período, accession y filing date de cada hecho. Lo que se rompió es el
  puntero al renglón del XBRL del que salió.
- **No lo causó la parametrización por CIK** de este ciclo. El defecto estaba en
  el diseño desde que `parsed` se concibió como staging de un solo emisor; la
  ingesta de un segundo emisor simplemente lo hizo visible.
- **No se detectó por tests unitarios.** Lo encontró la auditoría independiente
  al exigir que la cadena hasta la evidencia cerrara de verdad.
