# CNV W-1.4 — AUDITORÍA INDEPENDIENTE

**Fecha:** 2026-09-02 · **Auditor:** `scripts/engine/c4_auditoria_w14.py`
**Resultado:** **11 verificaciones OK · 0 fallas · 0 avisos**

---

## 1 · Qué lo hace independiente

No importa `c4_w14_clasificador`, ni el adaptador, ni el módulo semántico. Y no
se limita a repetir el mismo cálculo: **usa un método distinto** para la pieza
que más pesa.

| | inferencia de perímetro |
|---|---|
| clasificador | mediana de los dos períodos vecinos |
| **auditor** | **interpolación lineal entre los períodos que enmarcan** |

Si dos métodos distintos llegan a la misma conclusión sobre los mismos
documentos, la conclusión es del dato y no del método. Y donde discrepan, hay
que decirlo.

---

## 2 · Resultado

### A · Preservación

| | |
|---|---|
| ocurrencias intactas | **OK** — 103.268 |
| identidades económicas intactas | **OK** — 102.976 |
| identidades con más de una ocurrencia | **OK** — 292 |
| pares de documentos | **OK** — 7 |
| ninguna identidad perdió ocurrencias | **OK** — multiplicidad 2 en todas |

### B · Orden documental

| | |
|---|---|
| todos los documentos tienen ordinal | **OK** — 14/14 |
| el ordinal es único | **OK** — 14 valores distintos |

### C · Clasificación reconstruida

```
LONG       2018-12-31 INDIVIDUAL   36/36 difieren · IAS29 f=0,019 disp=52,2%  -> UNKNOWN
LONG       2019-03-31 INDIVIDUAL   35/35 difieren · IAS29 f=0,017 disp=64,3%  -> PERIMETER_CONFLICT
LONG       2020-12-31 INDIVIDUAL   36/36 difieren · IAS29 f=105,7 disp=77,0%  -> PERIMETER_CONFLICT
INTR       2021-12-31 CONSOLIDADO  42/46 difieren · IAS29 f=1,218 disp=26,1%  -> UNKNOWN
FIPL       2025-06-30 CONSOLIDADO   3/48 difieren · IAS29 f=1,000 disp= 0,0%  -> PROBABLE_RESTATEMENT
_ADR_0580  2019-12-31 CONSOLIDADO  34/46 difieren · IAS29 f=0,999 disp= 0,2%  -> UNKNOWN
BYMA       2021-12-31 CONSOLIDADO  40/45 difieren · IAS29 f=0,518 disp=65,8%  -> PERIMETER_CONFLICT
```

| clasificación del auditor | pares | identidades |
|---|--:|--:|
| `UNKNOWN` | 3 | 128 |
| `PERIMETER_CONFLICT` | 3 | 116 |
| `PROBABLE_RESTATEMENT` | 1 | 48 |

### D · IAS 29

| | |
|---|---|
| ningún par tiene la firma de una re-expresión | **OK** |

Verificado midiendo, no por ausencia de búsqueda: una re-expresión multiplica
todos los conceptos por el mismo factor, y en los 7 pares la dispersión del
cociente va del 0 % (factor 1 = sin cambio) al 80 %.

### E · Caso BYMA

| | |
|---|---|
| las dos ocurrencias siguen preservadas | **OK** — `863efe00` = 11.060.815 · `ee3e755d` = 1.593.406.319 |
| el auditor lo clasifica como conflicto de perímetro **por su cuenta** | **OK** — con interpolación lineal, método distinto |

Dos métodos independientes, sin ninguna regla especial para BYMA, llegan a la
misma conclusión.

### F · No se creó ninguna supersesión

| | |
|---|---|
| la tabla no declara ninguna relación de reemplazo | **OK** — 15 columnas, ninguna es `supersedes`, `effective_from`, `effective_to`, `es_vigente` ni `reemplaza_a` |

---

## 3 · La discrepancia, dicha sin maquillar

Los dos métodos coinciden en **6 de 7 pares**. Discrepan en **LONG 2020-12-31**:

```
clasificador (mediana de vecinos)      -> UNKNOWN
auditor      (interpolación lineal)    -> PERIMETER_CONFLICT
```

El clasificador no encontró inferencia concluyente porque su referencia —la
mediana de los dos períodos vecinos— quedó a 1,75 y 2,00 órdenes de magnitud
del documento, por encima del umbral de encaje. El auditor, interpolando entre
los períodos que enmarcan, sí obtuvo un ajuste utilizable.

**No se ajustó ningún umbral para que coincidieran.** La regla —decidida antes
de saber cuál método preferiría— es que donde dos métodos independientes
discrepan, el caso queda `UNKNOWN`: una clasificación que depende del método no
es una clasificación.

---

## 4 · Lo que el auditor NO verifica

- **No valida contra la realidad económica.** Que la serie de BYMA indique cuál
  documento es el correcto es un argumento del informe, no una comprobación
  automática, y **ningún dato de origen se modificó** por él.
- **No decide qué debería leer un consumidor.** Esa política está especificada
  en el informe y **no implementada**.
- **No cubre los 89 documentos sin RAW** en disco.
