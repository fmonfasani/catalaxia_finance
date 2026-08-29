# F-039 — EL DOMINIO DE `cnv_presentation.relacion` SE ESCRIBIÓ CON UNA SOLA EMPRESA

**Detectado:** 2026-08-28, en el smoke cross-workstream de YPF (ciclo 7, fase F)
**Severidad:** bloqueante para CNV — ninguna empresa con controlante puede cargarse

---

## 1. El síntoma

El fetch de YPF llega bien hasta el final y muere al insertar:

```
psycopg2.errors.CheckViolation: new row for relation "cnv_presentation"
violates check constraint "cnv_presentation_relacion_check"
```

Lo previo funcionó: HTTP 200, 5.9 MB de RAW, `validacion=VALID`,
**4.919 GUIDs únicos** descubiertos. YPF está en la CNV y el parser la lee bien.

## 2. La causa

```sql
CHECK (relacion = ANY (ARRAY['CONTROLADA', 'VINCULADA']))
```

Ese dominio se escribió mirando **una sola empresa**: Central Puerto, la única
jamás fetcheada. Los valores reales que la CNV declara en el perfil de YPF:

| `RELAC.:` | ocurrencias | ¿pasa el CHECK? |
|---|---|---|
| `VINCULADA` | 347 | sí |
| `CONTROLADA` | 252 | sí |
| **`CONTROLANTE`** | **2** | **no** |

CEPU no tiene controlante que presente ante la CNV. YPF sí. El dominio no era
el de la CNV: era el de CEPU.

**El parser no tiene el defecto.** `engine/cnv/discovery.py` ya lo anticipaba:
`CLASE_EEFF_RELAC_OTRA` es exactamente el caso "un tercer valor", y su docstring
dice *«Asumirla CONTROLADA sería inventar identidad»*. El parser preserva lo que
la CNV declara; **el CHECK lo rechaza**. La garantía y el parser estaban en
desacuerdo, y ganó la que no sabía.

## 3. Lo que importa más que el valor faltante: el sentido es inverso

Los dos títulos crudos son idénticos:

```
RELAC.: CONTROLANTE - CUIT: 30-54668997-9 - YPF S.A. - NORMA CONT.: NIIF
  - PERIODO BAL.: OTROS - TIPO BAL.: CONSOLIDADO - CONCILIACION
```

`30-54668997-9` **es el CUIT de la propia YPF**. En una fila `CONTROLADA` o
`VINCULADA`, `cuit_relacionado` es *la otra* empresa. En una fila `CONTROLANTE`
es **la empresa del perfil**: la fila la presenta la controlada, y nombra a su
controlante.

Por eso **ampliar el CHECK a secas sería el error caro**. Cualquier consumidor
que lea `relacion IS NOT NULL` como «esta es una subsidiaria nuestra» tomaría a
YPF como subsidiaria de YPF. La dirección de la arista está invertida y hay que
declararlo, no sólo admitir el string.

## 4. La corrección

1. **El dominio se amplía al observado**, no a «cualquier cosa»:
   `CONTROLADA | VINCULADA | CONTROLANTE`, y `NULL` sigue siendo válido —
   `relacion_origen='AUSENTE'` es un estado real (8.915 filas), no una omisión.
2. **Una fila `CONTROLANTE` cuyo `cuit_relacionado` sea el CUIT del propio
   perfil es una auto-referencia** y se marca como tal, para que ningún
   consumidor la lea como subsidiaria.
3. **No se reescribe ninguna fila existente**: las 9.305 de CEPU no tienen
   `CONTROLANTE` y no se tocan.

## 5. Lo que este hallazgo dice del método

El dominio de un CHECK **no se infiere de la primera empresa que se carga**. Se
infiere del RAW de una muestra que incluya casos estructuralmente distintos —
aquí, una empresa con controlante y una sin él. CEPU y YPF difieren justamente
en eso, y el gate lo encontró recién en la segunda.

Es el mismo patrón que F-026 (436 hechos descartados en silencio) y que la
primera versión del constraint de F-038 (que exigía `row_count IS NULL` en
`FAILED` y habría roto la próxima corrida): **una garantía escrita contra lo que
supuse que produce el sistema, en vez de contra lo que el sistema produce.**

En los tres casos lo detectó una ejecución real, no un test.
