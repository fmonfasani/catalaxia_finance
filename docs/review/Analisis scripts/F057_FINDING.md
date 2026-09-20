# F-057 — EL PARSER `sql()` DE LOS DOS AUDITORES INDEPENDIENTES PERDÍA EL ÚLTIMO CAMPO CUANDO VENÍA NULL

**Detectado:** 2026-09-01, al correr `audit_provenance_ratios.py` sobre el
universo ampliado a 8 emisores (ver F-056)
**Severidad: media** (robustez del auditor, no del dato) · **Estado: CORREGIDO**

---

## 1. El hallazgo

`ratios_auditoria.py` y `audit_provenance_ratios.py` consultan PostgreSQL por
`psql -t -A -F "\x1f"` (separador ASCII "Unit Separator") y parsean así:

```python
return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]
```

`str.strip()` sin argumentos, en Python, elimina **whitespace** — y Python
clasifica `\x1c`–`\x1f` (los cuatro separadores de control ASCII) como
whitespace. Cuando el **último campo de la última fila** del resultado venía
NULL (cadena vacía), la salida de psql terminaba en
`"...valor\x1f\n"`, y `.strip()` sobre el bloque completo se comía **tanto
el `\n` como el `\x1f` precedente**, dejando `"...valor"` sin el separador
que marcaba el campo vacío. El `split("\x1f")` resultante tenía un elemento
de menos.

## 2. Efecto medido

```
IndexError: list index out of range
  File "audit_provenance_ratios.py", line 96, in valor
    return t, Decimal(r[0][0]), r[0][1]
```

Disparado al consultar `acciones` (conteo de acciones) de AAPL: la fila
`WeightedAverageNumberOfSharesOutstandingBasic | 14948500000 | (NULL)` — el
conteo de acciones no tiene moneda, así que `currency` es legítimamente NULL.
Cualquier concepto cuyo **último** campo consultado pudiera ser NULL en la
**última** fila devuelta disparaba el mismo error. No ocurría antes porque
el único emisor auditado (YPF) nunca produjo esa combinación exacta en las
consultas ejecutadas hasta ahora.

## 3. Por qué es un hallazgo de Fase G y no solo un bug

El encargo pide explícitamente atacar "dato NULL tratado como cero" y
casos límite de robustez. Este no es ese caso — aquí el NULL no se trató
como cero, **tumbó el proceso** — pero es la misma familia de riesgo: un
control que no sobrevive a un valor NULL legítimo en una posición que el
camino feliz no ejercitaba. Un auditor que se cae ante un NULL válido no
puede terminar de auditar, que es peor que dar un resultado silenciosamente
incorrecto para ese caso puntual: **al menos no miente**, pero tampoco cubre.

## 4. Corrección aplicada

Se reemplazó `p.stdout.strip().splitlines()` por `p.stdout.splitlines()` en
los dos scripts. `splitlines()` ya separa por salto de línea sin tocar el
resto de cada línea; el filtro `if ln.strip()` se conserva porque ahí
`.strip()` solo se usa para la prueba de verdad (línea no vacía), no para el
contenido que se parsea.

## 5. Verificación

`audit_provenance_ratios.py` completo tras el fix: **8/8 controles OK**,
incluyendo la equivalencia EPS = resultado/acciones en las 8 empresas (que
es justamente la consulta que antes crasheaba en el camino de AAPL).
`ratios_auditoria.py` completo: **17/17** tras alinear también los
controles H1/H2 a la cobertura real (ver commit de este ciclo — no eran un
efecto de este bug, sino un número congelado de una corrida anterior).

## 6. Lección

El separador `\x1f` es la elección correcta para evitar colisiones con datos
reales (a diferencia de `,` o `|`), pero interactúa mal con `str.strip()`
sin argumentos, que en Python no es "quita espacios y saltos de línea": es
"quita todo lo que el estándar Unicode marca como espacio en blanco",
categoría que incluye a los separadores de control ASCII. Un auditor que
usa un separador no imprimible para blindarse de colisiones necesita blindar
también su propio parser contra ese mismo separador.
