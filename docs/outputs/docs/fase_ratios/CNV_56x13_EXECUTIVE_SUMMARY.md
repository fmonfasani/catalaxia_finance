# CNV 56 × 13 — RESUMEN EJECUTIVO

**2026-09-01** · auditoría independiente, solo lectura · detalle en
[`CNV_56x13_COVERAGE_AUDIT.md`](CNV_56x13_COVERAGE_AUDIT.md)

---

## El número

```
CANONICAL_COMMERCIAL_COVERAGE  =     0 / 728      0,0 %
LEGACY_ONLY_COVERAGE           =   486 / 728     66,8 %
IDENTITY_BLOCKED               =   242 / 728     33,2 %
```

**Ninguna de las 728 celdas del universo CNV puede mostrarse hoy como dato
canónico de Catalaxia.**

La causa es una y es anterior a todas las demás: **ninguno de los 56 CUIT existe
en `identity_v1`**. No pocos — cero.

---

## Las nueve preguntas

**1 · ¿Cuántas de las 728 son CALCULADO?**
**0.** El universo `byma_only` son, por definición, las empresas **sin ADR**:
sin ADR no hay presentación ante la SEC, sin SEC no hay CIK, y sin CIK no hay
fundamentals en la superficie canónica.

**2 · ¿Cuántas tienen provenance completa?**
**0.** Las 486 con valor legacy **tienen número y no tienen cadena**: ni
`screener_gold` ni `screener` guardan puntero al hecho de origen, ni hash, ni
número de presentación.

**3 · ¿Cuántas están homologadas?**
**0.** La homologación del vertical slice —25/25 con desvío 1,59e-7— cubre 8
emisores que **no pertenecen a este universo**. Extrapolarla sería inventar
respaldo.

**4 · ¿Cuántas están bloqueadas correctamente?**
**Las 728.** Y es el hallazgo positivo del informe: el motor se niega a atribuir
un ratio a una entidad que no puede identificar, y se niega a usar un precio que
no puede probar que le pertenece — **aunque lo tenga delante en 53 de los 56
casos**. Un sistema que uniera por ticker mostraría hoy 486 celdas con aspecto
canónico.

**5 · ¿Cuántas existen sólo en legacy?**
**486 (66,8 %).** Mejor cubiertas: ROA 56/56, margen neto 55/56, ROE 52/56, P/S
52/56. Tres de los 13 —current ratio, quick ratio, deuda/patrimonio— **no
existen en ninguna superficie** para este universo.

**6 · ¿Cuántas tienen discrepancias?**
**0 — y no significa acuerdo.** Los conjuntos son disjuntos: no hay una sola
celda con valor canónico y legacy a la vez, así que no hay dónde discrepar.

**7 · ¿Principales blockers?**

| | | alcance |
|---|---|---:|
| B1 | los 56 CUIT no están en `identity_v1` | 728 |
| B2 | 0 de 54 instrumentos ligados a su entidad | los 4 de mercado |
| B3 | sin fundamentals canónicos: la vía es CNV, y `fetch_raw` tiene 3 CUIT de 56 | 728 |
| B4 | 10 de los 13 ratios no están implementados en el motor | 560 |
| B5 | decisiones D3, D4 y D5 abiertas | 168 |

**8 · ¿Qué porcentaje puede mostrarse hoy?**
**0 % como canónico.** **66,8 % sólo si se etiqueta explícitamente como legacy**,
sin procedencia y advirtiendo que viene de otro pipeline. Las dos cifras no se
mezclan.

**9 · ¿Qué porcentaje requiere trabajo adicional?**
**100 %.**

---

## Dos correcciones a la premisa del encargo

**«Los 13 ratios del contrato vigente»** — el contrato vigente tiene **20
`canonical_id`**, no 13. Hay tres listas de 13 distintas en el proyecto. Se
usaron los 13 de `RATIO_CONTRACT_v0_13ratios.md`, el único documento de contrato
con esa cantidad; 12 de ellos tienen `canonical_id` vigente. No se inventó
ninguno.

**«56 empresas CNV»** — son 56 y el conteo es consistente en seis tablas. Lo que
no es evidente en el nombre: `byma_only` significa **sin ADR**, y de ahí se
sigue toda la ausencia. Los tres CUIT autoritativos del sistema (YPF, TGS, CEPU)
están en el grupo ADR, **fuera** de este universo.

---

## El dato que más conviene mirar

**53 de los 56 tienen precio en la superficie canónica de Market. Ninguno tiene
su instrumento ligado a una entidad.**

El dato de mercado ya está ingerido. Lo que falta es la prueba de a qué entidad
pertenece cada especie cotizante — y sin esa prueba, atribuirle el precio sería
un join por ticker: el mismo que en una etapa anterior hizo aparecer precios de
Coursera como argentinos.

Ligar esos 54 instrumentos es trabajo de identidad, no de ingesta pesada. Junto
con promover los 56 CUIT, es el mejor retorno por esfuerzo de toda la lista de
blockers.

---

## Dictamen

# CNV_56x13_COVERAGE_GATE = **FAIL**

El `FAIL` califica la **cobertura**, no la auditoría: ésta se ejecutó completa,
sólo con `SELECT`, y es reproducible.

Se emite `FAIL` y no `PASS_WITH_WARNINGS` porque convertir 0/728 en «pasa con
advertencias» sería la misma operación que el encargo prohíbe tres veces:
`NULL → 0`, `NOT_CALCULABLE → 0`, `LEGACY_ONLY → CANONICAL`. **Cero no es un
warning.**

### Para el discurso comercial

- **No presentar este universo como cobertura de Catalaxia.** Hoy no lo es.
- La demo y el piloto siguen siendo los 8 emisores del vertical slice.
- Si un prospecto pregunta por las 56 empresas argentinas: existen en una capa
  anterior, con 486 valores y **sin procedencia verificable** — y decirlo así,
  antes de que lo descubra.

### Lo que este FAIL confirma

Que el sistema prefiere no mostrar nada antes que mostrar algo que no puede
respaldar. Es incómodo de leer en una matriz de cobertura y es exactamente la
propiedad que el producto vende.
