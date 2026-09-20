# F-060 — LA COMPARACIÓN DE CONTEXTOS IGNORA LA ENTIDAD

**Detectado:** 2026-08-31, por el ataque A6 del banco adversario de F-055
**Severidad: baja–media** · **Estado: REGISTRADO, NO CORREGIDO**
**No es blocker de F-054 ni de F-055**

> **Nota de numeración.** Este hallazgo se registró primero como F-056 y después
> como F-058. Ambos números fueron tomados en paralelo por otro workstream que
> opera el mismo repositorio (F-056 duplicación de listas de tags, F-057 el
> separador `\x1f` en los auditores, F-058 producto cartesiano en el banco
> adversario de ratios). Se renumera a **F-060** y se reclama también **F-059**
> para el hallazgo de encadenamiento S03→S04. El contenido no cambió.
> **Dos agentes numerando findings en paralelo van a volver a chocar.**

---

## 1. El hallazgo

El banco adversario ataca la regla que decide si dos filas de `parsed.contexts`
con el mismo `(accession_number, context_id)` son el mismo contexto lógico.
Siete ataques, cada uno con su veredicto declarado **antes** de medirlo:

```
A1  permutar el ORDEN de las dimensiones     NO debe conflictuar   equivalentes   OK
A2  duplicado IDENTICO                       NO debe conflictuar   equivalentes   OK
A3  cambiar un MIEMBRO de dimension          DEBE conflictuar      conflicto      OK
A4  cambiar el PERIODO (end_date +1d)        DEBE conflictuar      conflicto      OK
A5  cambiar DURATION por INSTANT             DEBE conflictuar      conflicto      OK
A6  cambiar la ENTIDAD del contexto          DEBE conflictuar      equivalentes   FALLA
A7  agregar una dimension mas                DEBE conflictuar      conflicto      OK
```

**A6 pasa cuando no debería.** Se insertó un contexto idéntico salvo por
`identifier` (`'0000000000'` en vez del CIK del emisor) y la regla lo declaró
equivalente al original.

## 2. La causa

`contextos_deduplicados()` y `C-S04-003` comparan exactamente esta tupla:

```
(start_date, end_date, instant_date, period_kind, dims_c, typed_c)
```

`parsed.contexts` tiene además `scheme` e `identifier` — el
`<xbrli:entity><xbrli:identifier scheme="…">CIK</xbrli:identifier>` del contexto
XBRL. **Ninguno de los dos entra en la comparación.**

Un contexto XBRL identifica a *quién* le pasa *qué* y *cuándo*. La regla actual
compara el qué y el cuándo, y omite el quién.

## 3. Alcance real, medido

```sql
SELECT count(*) FROM (
  SELECT accession_number, context_id FROM parsed.contexts
   GROUP BY 1,2 HAVING count(DISTINCT (scheme, identifier)::text) > 1) x;
-- resultado: 0
```

**Cero casos reales sobre los 8 emisores ingeridos.** El defecto es una omisión
del invariante, no una corrupción observada.

La comparación está acotada a `(accession, context_id)`, así que el escenario
requiere que un mismo filing declare dos veces el mismo `context_id` con
entidades distintas. En la práctica un 20-F o un 10-K no lo hace.

## 4. Por qué igual importa

Los consolidados **sí** declaran contextos de subsidiarias y segmentos. Hoy se
distinguen por sus *dimensiones*, no por la entidad — pero nada garantiza que un
emisor no use el mecanismo de entidad del contexto, que es exactamente para lo
que existe en la especificación XBRL.

Si ocurriera, dos hechos de entidades distintas se colapsarían en uno y
`elegir_ganador` se quedaría con uno de los dos. **Sería pérdida silenciosa**, la
misma familia que F-055.

## 5. Corrección propuesta — NO aplicada

Agregar `scheme` e `identifier` a la tupla comparada, en los dos lugares:

- `contextos_deduplicados()` en `s04_normalize.py`
- el control `C-S04-003`

No se aplica en este ciclo por dos razones:

1. **La regla del ciclo es registrar antes de corregir**, y este hallazgo apareció
   dentro de la validación de otro.
2. Cambiar la clave de deduplicación **altera qué contextos se consideran el
   mismo**, y por lo tanto puede mover el conteo de `derived.fact`. Exige
   re-parsear el universo y volver a medir la conservación; no corresponde
   meterlo dentro del gate de F-054/F-055.

## 6. Cobertura de test

`tests/test_f055_equivalencia_contextos.py::test_cambiar_la_entidad_SI_deberia_generar_conflicto`
lo documenta con `@pytest.mark.xfail(strict=True)`. Si alguien corrige F-060, el
test pasa a XPASS y **falla** — que es la señal para sacarlo de la lista de deuda
en vez de dejarlo mintiendo.

## 7. Relación con F-055

F-055 arregló la comparación por el lado de los **falsos positivos**: contextos
equivalentes declarados contradictorios. F-060 es el lado opuesto: contextos
**distintos** que podrían declararse equivalentes. Una canonización que absorbe
de más es peor que el defecto que vino a arreglar, y por eso el banco adversario
la ataca en las dos direcciones.

De los siete ataques, seis dan el veredicto correcto. El séptimo señala el borde
exacto donde la regla deja de distinguir.
