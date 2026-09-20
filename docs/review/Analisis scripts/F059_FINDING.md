# F-059 — S04 NORMALIZA EL ÚLTIMO S03, NO EL DEL EMISOR QUE SE ACABA DE PARSEAR

**Detectado:** 2026-09-01, en la Fase A del gate de integridad del Engine
**Severidad: media** · **Estado: REGISTRADO, NO CORREGIDO**
**No invalida F-054 ni F-055; es la ventana que la corrección de F-054 dejó abierta**

---

## 1. El hallazgo

`s04_normalize.py` elige su insumo así:

```python
def checkpoint_s03(conn) -> dict:
    row = conn.execute(text("""
        SELECT c.checkpoint_id, c.run_id, ...
          FROM engine.checkpoints c JOIN engine.runs r ON r.run_id = c.run_id
         WHERE c.stage_id = :s ORDER BY c.created_at DESC LIMIT 1
        """), {"s": INPUT_STAGE}).mappings().first()
```

**El último checkpoint de S03, sin filtrar por CIK.**

S03 sí filtra: F-054 le agregó `find_s02_input_run(engine, cik)`. S04 no recibió
el tratamiento equivalente.

## 2. La secuencia peligrosa

```
S03(A)   ->  borra las filas de A, inserta las nuevas con ids frescos
             (los ids VIEJOS de A quedan libres; derived de A los sigue citando)
S03(B)   ->  idem para B
S04      ->  normaliza SOLO B  (es el ultimo checkpoint)

estado: A quedo con derived apuntando a fact_id que ya no existen
```

Es exactamente la ventana que menciona el contrato de S03: *«entre S03 y S04 los
`source_fact_ids` de ese emisor apuntan a filas borradas»*. Lo que F-059 agrega
es que **la ventana no se cierra sola**: correr S04 una vez no alcanza si se
parsearon varios emisores.

## 3. Por qué no es F-054

F-054 era **contaminación**: un puntero resolvía a un hecho de otra empresa y
devolvía una fila ajena, en silencio. Aquí el puntero **no resuelve a nada**: la
garantía G2 (la secuencia no se reinicia) impide que el id sea reutilizado, así
que el resultado es un dato ausente, no un dato equivocado.

Es la diferencia que el banco mutacional midió:

```
M2  sin G1 ni G2  ->  2.791 punteros de CEPU caen en hechos de TGS   CONTAMINACION
M3  sin G1, con G2 ->  135.077 punteros colgados, 0 ajenos            PERDIDA
```

F-059 produce el escenario de M3 por un camino distinto: no por revertir G1,
sino por no correr S04 tantas veces como S03.

## 4. Por qué ningún control lo detecta

Los tres controles que podrían verlo están acotados a la corrida en curso:

| control | alcance |
|---|---|
| `C-S04-005` | `derived WHERE run_id = <S04 actual>` vs `parsed WHERE run_id = <S03 actual>` |
| `C-S04-006` | hechos sin fila de origen, dentro del run |
| `C-S04-008` | huella de lo persistido en ese run |

Ninguno mira los emisores que no participaron de la corrida. Es la misma familia
que F-054: **el control verifica la ejecución, no el estado del sistema**.

## 5. Alcance real, medido

Sobre la base actual, con los 8 emisores:

```sql
SELECT count(*) FROM derived.fact d
 CROSS JOIN LATERAL unnest(d.source_fact_ids) s(fid)
 LEFT JOIN parsed.facts p ON p.fact_id = s.fid
WHERE d.valid_to IS NULL AND p.fact_id IS NULL;
-- resultado: 0
```

**Cero punteros colgados hoy**, porque el orden de trabajo fue siempre
`S03(X) → S04` de a un emisor por vez. El defecto es latente, no activo.

## 6. Correcciones posibles — ninguna aplicada

1. **`checkpoint_s03(conn, cik)`**: filtrar el checkpoint por el CIK que se va a
   normalizar, con un `--cik` en S04 simétrico al de S03. Es el arreglo directo
   y el más chico.
2. **Que S03 dispare S04**: acoplar las dos etapas para que la ventana no exista.
   Contradice el diseño de etapas independientes con checkpoint.
3. **Un control de sistema, no de corrida**: agregar a `C-S04-005` la
   verificación de que *ningún* emisor —no sólo el de la corrida— quedó con
   punteros colgados. No cierra la ventana, pero la vuelve visible.

La 1 y la 3 son complementarias: la primera evita el estado, la segunda lo
detecta si vuelve a producirse por otra vía.

## 7. Mitigación operativa mientras tanto

Correr **S03 y S04 pegados, un emisor por vez**. Está escrito en el manual
operativo de validación (§3 y §15), pero hoy depende de que el operador lo
respete: nada en el código lo obliga.

## 8. Cobertura de test

`tests/test_f054_aislamiento_emisores.py::test_ningun_source_fact_id_queda_colgado`
detecta el estado si llega a producirse. No previene la secuencia que lo genera.
