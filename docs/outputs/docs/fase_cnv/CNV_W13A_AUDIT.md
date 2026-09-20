# CNV W-1.3A — AUDITORÍA INDEPENDIENTE DE PRESERVACIÓN

**Fecha:** 2026-09-02
**Auditor:** `scripts/engine/c4_auditoria_w13a.py`
**Resultado:** **13 verificaciones OK · 0 fallas · 1 aviso**

---

## 1 · Qué lo hace independiente

No importa `job5_v2_extract_eeff`, ni `c4_cnv_adapter`, ni `c4_cnv_semantica`.
Tiene:

- **su propio parser** del RAW, con sus propias expresiones regulares;
- **su propia lista** de los 51 códigos CNV, escrita aparte;
- **su propia definición** de qué es una ocurrencia.

Recorre la cadena desde el extremo crudo:

```
documentos RAW  ->  ocurrencias parseadas  ->  ocurrencias canónicas
```

Si el job y el auditor coinciden sobre 103.268 filas, es porque el resultado es
reproducible por dos implementaciones escritas por separado.

---

## 2 · Resultado por sección

### A · Del RAW a la ocurrencia

| | |
|---|---|
| cada documento de la tabla tiene su RAW en disco | **OK** — 2.364 documentos · 0 sin archivo |
| ningún documento RAW quedó sin ocurrencia | **OK** — 0 documentos vacíos |
| **0 ocurrencias descartadas** | **OK** — el auditor leyó 103.268 conceptos del RAW · faltan **0** |
| 0 ocurrencias sin respaldo en el RAW | **OK** — 0 filas inventadas |

El auditor leyó, por su cuenta, exactamente los mismos 103.268 conceptos que el
job insertó.

### B · Unicidad de la ocurrencia

| | |
|---|---|
| un documento declara un valor por concepto | **OK** — 0 pares `(documento, concepto)` repetidos |
| cardinalidad = pares `(documento, concepto)` | **OK** — 103.268 filas = 103.268 pares |

### C · Ocurrencias por identidad económica

```
identidades económicas          102.976
con más de una ocurrencia           292   (584 ocurrencias)
    valores distintos               226
    mismo valor                      66
```

| | |
|---|---|
| la capa preserva ocurrencias múltiples | **OK** — 292 identidades con 2 ocurrencias; antes eran 0 |
| relación ocurrencias → identidades bien formada | **OK** — 103.268 → 102.976, **1,0028 a 1** |

La reducción está **explícitamente modelada como muchos-a-uno**: cada ocurrencia
conserva su `accn`, y la identidad económica se obtiene agrupando, no
sobrescribiendo.

### D · Divergencias entre ocurrencias

226 identidades con valores divergentes. El auditor, **sin conocer las
conclusiones de W-1.3**, marcó por su cuenta las divergencias de perímetro
probables: pares donde más de la mitad de los conceptos comunes difieren pese a
declarar el mismo `TipoBalance`.

| CUIT | período | perímetro declarado | conceptos que difieren |
|---|---|---|---|
| 30696170580 | 2019-12-31 | CONSOLIDADO | 34 / 46 |
| 30500833781 | 2018-12-31 | INDIVIDUAL | 36 / 36 |
| 30715471953 (BYMA) | 2021-12-31 | CONSOLIDADO | 40 / 45 |
| 30501290323 | 2021-12-31 | CONSOLIDADO | 42 / 46 |
| 30500833781 | 2020-12-31 | INDIVIDUAL | 36 / 36 |
| 30500833781 | 2019-03-31 | INDIVIDUAL | 35 / 35 |

**Encontró 6 de los 7 pares.** El séptimo —FIPL 2025-06-30, con 45 de 48
conceptos idénticos— **no** fue marcado, que es lo correcto: ese es el único par
compatible con una republicación real.

### E · Caso BYMA 2021-12-31

| | |
|---|---|
| las dos ocurrencias están preservadas | **OK** — `863efe00` = 11.060.815 · `ee3e755d` = 1.593.406.319 |
| los dos valores son los que W-1.3 identificó | **OK** |

El auditor **no decide cuál es correcto**. Solo exige que estén los dos.

### F · Orden de publicación

| | |
|---|---|
| todos los documentos tienen ordinal | **OK** — 2.364 / 2.364 |
| el ordinal es único | **OK** — 2.364 valores distintos |
| las ocurrencias de cada identidad se pueden ordenar entre sí | **OK** — 292 / 292 grupos |

---

## 3 · Aviso

**Divergencia de perímetro probable en 6 pares.** No es una falla del pipeline
—las ocurrencias están preservadas, que es lo que este ciclo exige— sino un
problema de calidad en origen que W-1.4 tendrá que resolver: el documento
declara un `TipoBalance` que su contenido contradice.

---

## 4 · Lo que el auditor NO verifica

- **No decide** si un par es republicación, corrección, re-expresión o error.
  Esa es la pregunta de W-1.4 y este auditor está construido para no
  responderla.
- **No valida el valor contra la realidad económica.** Que la serie de BYMA
  sugiera cuál de los dos es correcto es un argumento del informe, no una
  comprobación automática.
- **No cubre los 89 documentos sin RAW en disco** (2.453 conocidos − 2.364 con
  archivo). Esos quedan fuera de toda la cadena.
