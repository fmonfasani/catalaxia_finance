# CNV_NEGATIVE_PILOT_20_GATE

**Fecha:** 2026-09-01 · **Rol:** Orquestador de homologación
**Ciclo:** camino negativo a escala — 20 CANDIDATE

---

# GATE = **BLOCKED**

El piloto **no cumplió su criterio de éxito**, y además **escribió en la base
homologada**, que era exactamente lo que no debía pasar.

Ambas cosas son consecuencia del mismo error de mi parte, y del hallazgo que ese
error destapó.

---

## 1. Lo que salió mal — escritura no intencionada

```
DELTA medido:
  cnv_artifact         3.955 → 3.957    +2
  cnv_download_log     3.956 → 3.958    +2
  cnv_runs                49 →     50   +1
  raw cnv archivos       443 →    445   +2
  raw cnv bytes    83.987.980 → 89.953.920   +5.965.940
```

**Se abrió una corrida CNV real y se descargaron 2 artefactos de YPF**
(1 `EMPRESA_PAGE` + 1 `VISOR`, 5,9 MB).

### Por qué pasó

Mi consulta de universo pidió «CUIT con assertion `status <> VERIFIED`». Devolvió
20 filas — pero **no 20 empresas**. Devolvió filas de **3 CUIT distintos**
(YPF, CEPU, GGAL), repetidos, porque cada CUIT tiene varias filas vigentes en
`identity_v1.identifier`, cada una con su propia assertion.

Entre esas filas había assertions `CANDIDATE` **de YPF**, cuyo CUIT **sí está
VERIFIED por otra fila**. Al atacarlo con el mecanismo oficial, el resolver
respondió `VERIFIED` —correctamente, según su propia lógica— y el fetcher
**hizo su trabajo**: abrió corrida y descargó.

### Qué tan grave es

| | |
|---|---|
| ¿Se corrompió algo? | **No.** Es una ingesta legítima de una empresa legítimamente VERIFIED, por el mecanismo oficial |
| ¿Se borró algo? | **No.** Es puramente aditivo |
| ¿Quedó corrida huérfana? | **No** — `runs_running = 0` antes y después |
| ¿Se modificó Identity? | **No** — `entities`, `identifiers`, `assertions`, `cuit_verified`: delta 0 |
| ¿Se modificó SEC o Market? | **No** — no se ejecutó ninguna etapa de ninguno |
| ¿Se violó la instrucción del ciclo? | **Sí.** «No escribir en la base homologada» |

**No se revierte.** El ciclo prohíbe borrar provenance histórica, y deshacer una
descarga legítima sería peor que registrarla. Queda documentada acá.

---

## 2. El hallazgo que el error destapó

Es más importante que el piloto.

### F-06x · Un CUIT tiene múltiples filas vigentes con estados contradictorios

```sql
SELECT i.id_value, count(*) filas, string_agg(DISTINCT a.status::text, ',') estados
  FROM identity_v1.identifier i
  JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
 WHERE i.id_type='CUIT' AND i.valid_to IS NULL
 GROUP BY 1 HAVING count(*) > 1 ORDER BY 2 DESC;

 33650305499 | 8 | CANDIDATE,VERIFIED     <- CEPU
 30546689979 | 8 | CANDIDATE,VERIFIED     <- YPF
 30657862068 | 8 | CANDIDATE,VERIFIED     <- TGS
 30704962807 | 7 | CANDIDATE              <- GGAL
 30500001735 | 4 | CANDIDATE
 …
```

**Ocho filas vigentes para el mismo CUIT**, siete `CANDIDATE` y una `VERIFIED`.
La pregunta «¿este CUIT está VERIFIED?» **no tiene una respuesta única en el
modelo**: depende de qué fila se lea.

### Cómo lo resuelve hoy el sistema — por accidente

`resolver_en_identity_v1()`, en `c3_cnv_fetch.py:68`:

```sql
max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)  AS cuit_status
```

**`max()` alfabético sobre el texto del estado.** Con el vocabulario actual:

```
CANDIDATE  <  REVIEW_REQUIRED  <  VERIFIED
```

`max()` devuelve `VERIFIED` si **alguna** fila lo es. El resultado es el deseado
—«basta una ratificación para habilitar»— pero **no está declarado en ningún
contrato**: es una consecuencia del orden alfabético de tres cadenas.

**Si mañana se agregara un estado como `WITHDRAWN` o `SUPERSEDED`**, `max()` lo
elegiría por encima de `VERIFIED` y la empresa quedaría bloqueada —o al revés,
según la letra. La regla de elegibilidad de CNV colgaría de una coincidencia
lexicográfica.

**Registrado, no corregido.** Requiere decisión: ¿la regla es «alguna VERIFIED
habilita», «la más reciente manda», o «debe haber exactamente una vigente»?
Es una definición del modelo de identidad, no un ajuste de código.

---

## 3. Lo que sí quedó demostrado, pese al error

De las 20 invocaciones al mecanismo oficial:

```
  CUIT          rc  abrió corrida  hizo request
  30546689979    0       SI             SI        <- YPF, VERIFIED: corrió (correcto)
  30546689979    1       NO             NO
  … (18 más)     1       NO             NO
  33650305499    1       NO             NO
  30704962807    1       NO             NO
```

**19 de 20 invocaciones fueron rechazadas sin abrir corrida y sin un solo request
HTTP.** El corte ocurre en `load_identity()`, antes de `run_scope`.

Eso es evidencia real de la barrera, aunque el universo no fuera el que yo quería.

### Lo que NO quedó demostrado

| | |
|---|---|
| 20 empresas **distintas** bloqueadas | el universo tenía 3 CUIT repetidos |
| El motivo exacto de cada rechazo | mi parser de la salida falló: `motivo` vacío en los 20 |
| Los 5 ataques adversariales | todos dieron `rc=1` pero sin motivo extraíble |
| La mutación causal (Fase 7) | **no se ejecutó** |

---

## 4. Por qué el universo no tenía 20 empresas

El propio hallazgo de §2 lo explica: hay **56 filas de CUIT** vigentes, pero
**no 56 CUIT distintos**. Con 4 a 8 filas por CUIT, el universo real de CUIT
distintos es sustancialmente menor que 56.

**La consulta correcta debe deduplicar por `id_value` y excluir todo CUIT que
tenga alguna assertion `VERIFIED`** — no filtrar fila por fila. Ése es el arreglo
del piloto, y no se aplicó porque el error se descubrió al leer los resultados.

---

## 5. Estado de la base

| métrica | antes | después | delta |
|---|---:|---:|---:|
| entities | 525 | 525 | **0** |
| identifiers vigentes | 574 | 574 | **0** |
| assertions vigentes | 608 | 608 | **0** |
| CUIT VERIFIED | 3 | 3 | **0** |
| cnv_artifact | 3.955 | 3.957 | **+2** |
| cnv_download_log | 3.956 | 3.958 | **+2** |
| corridas CNV | 49 | 50 | **+1** |
| corridas RUNNING | 0 | 0 | **0** |

**Identity intacta. SEC y Market intactos. CNV +1 corrida y +2 artefactos.**

---

## 6. Criterio de éxito

| requisito | resultado |
|---|---|
| 20/20 CANDIDATE bloqueados | **NO** — el universo tenía 3 CUIT distintos |
| 0 runs creados | **NO** — 1 |
| 0 requests CNV | **NO** — 1 empresa descargó |
| 0 filas CNV nuevas | **NO** — 2 |
| 0 modificaciones de Identity | **SÍ** |
| 0 CUIT inventados | **SÍ** |
| 0 bypass del gate VERIFIED | **SÍ** — el único que pasó, pasó porque *está* VERIFIED |

---

## 7. Qué hace falta para repetirlo bien

1. **Corregir la consulta de universo**: deduplicar por `id_value` y excluir todo
   CUIT con alguna assertion `VERIFIED`. Verificar además que los CUIT
   seleccionados sean **distintos entre sí**.
2. **Corregir el parser del motivo**: hoy devuelve vacío en los 20 casos, de modo
   que la Fase 3 —la barrera causal— no se puede acreditar.
3. **Añadir una salvaguarda al piloto**: antes de invocar el fetcher, verificar
   que el resolver devuelve `ok=False`. Si devuelve `ok=True`, **no invocar** —
   ésa es la protección que faltó y que habría evitado la descarga.
4. **Ejecutar la Fase 7** (mutación), que quedó pendiente.

---

## Dictamen

# CNV_NEGATIVE_PILOT_20_GATE = **BLOCKED**

No por un defecto del sistema —la barrera rechazó 19 de 20 invocaciones sin abrir
corrida ni hacer un request— sino por **dos errores de la prueba**: un universo
mal construido y la ausencia de una salvaguarda antes de invocar el fetcher.

El costo fue una escritura no intencionada de 2 artefactos y 1 corrida sobre una
empresa que legítimamente podía descargarlos. Se documenta y no se revierte.

**El hallazgo de §2 vale más que el piloto**: la elegibilidad de CNV depende hoy
de un `max()` alfabético sobre el texto del estado de la assertion, sobre un
identificador que tiene ocho filas vigentes con estados contradictorios. Funciona
por coincidencia lexicográfica, no por regla declarada.
