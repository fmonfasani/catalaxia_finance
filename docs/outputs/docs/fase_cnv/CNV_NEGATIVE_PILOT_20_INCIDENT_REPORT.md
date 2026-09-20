# CNV_NEGATIVE_PILOT_20 — INFORME DE INCIDENTE

**Fecha:** 2026-09-01 · **Rol:** Incident Recovery / Orquestador
**Estado del piloto: BLOCKED / INVALIDATED**
**Clasificación del incidente: INCIDENTE_CONTROLADO_SIN_CORRUPCIÓN**

Forense de sólo lectura, con SQL propio, **sin reutilizar el script que provocó
el incidente**. No se ejecutó CNV, Market ni SEC. No se creó ninguna base. No se
borró ni revirtió nada.

---

## 1. Causa

El piloto estaba diseñado para probar **únicamente casos `CANDIDATE`**. Un caso
`VERIFIED` llegó al fetcher. La causa tiene tres capas, y la tercera es la que
convirtió un error de selección en una escritura.

### Capa 1 — la consulta filtra fila por fila, no por CUIT

```sql
WHERE i.id_type='CUIT' AND i.valid_to IS NULL AND a.status <> 'VERIFIED'
```

`identity_v1.identifier` tiene **entre 4 y 8 filas vigentes por CUIT**, cada una
con su propia assertion, y en los tres CUIT ratificados los estados están
**mezclados**. El filtro descarta *filas* `VERIFIED`, no *CUIT* verificados: las
siete filas `CANDIDATE` de YPF entraron al universo aunque su CUIT esté
`VERIFIED` por la octava.

### Capa 2 — sin deduplicar por `id_value`

`LIMIT 20` devolvió 20 **filas**, que resultaron ser **3 CUIT distintos**
repetidos (YPF, CEPU, GGAL). El universo nunca tuvo 20 empresas.

### Capa 3 — el control existía, disparó, y no tenía consecuencia

```python
159:  solapa = [u for u in universo if u["cuit"] in POSITIVOS]
160:  print(f"  ninguno es un control positivo: {'OK' if not solapa else 'FALLA ' + str(solapa)}")
…
165:  for u in universo:            # ← corre igual
166:      r = atacar(u["cuit"])
```

**El piloto detectó que YPF y CEPU estaban en el universo, imprimió `FALLA`, y
siguió adelante.** No fue un control ausente: fue un `print` donde correspondía
un `return`.

> Es exactamente el patrón que este proyecto viene señalando en el sistema
> —controles que observan en vez de garantizar— cometido esta vez en la
> herramienta de prueba.

---

## 2. Alcance — reconstruido, no declarado

| métrica | antes | ahora | delta |
|---|---:|---:|---:|
| `cnv_artifact` | 3.955 | 3.957 | **+2** |
| `cnv_download_log` | 3.956 | 3.958 | **+2** |
| corridas CNV | 49 | 50 | **+1** |
| `identity_v1.entity` | 525 | 525 | 0 |
| `identity_v1.identifier` vigentes | 574 | 574 | 0 |
| `identity_v1.assertion` vigentes | 608 | 608 | 0 |
| CUIT `VERIFIED` | 3 | 3 | 0 |
| corridas `RUNNING` | 0 | 0 | 0 |

**El cambio fue EXACTAMENTE +1 run, +2 artefactos, +2 logs. Sin desvíos.**

Otros workstreams, sin tocar:

```
parsed.facts 135.077 · derived.fact 88.789 · market_price_daily 4.799.938
fetch_raw.download_log (SEC) 1.027
```

### La corrida

```
run_id      d63aba1b809c429ba2952d20ac90620f
pipeline    cnv-fetch-v1        status  OK
inicio      2026-09-01 17:59:44 UTC
fin         2026-09-01 18:00:38 UTC        (53 s)
```

### Los artefactos

| tipo | CUIT | entity_key | bytes | sha256 |
|---|---|---|---:|---|
| `EMPRESA_PAGE` | 30546689979 | `E01M0X99C8F87H9TH9N39H2D1NW` | 5.902.281 | `33a658641a4140ae…` |
| `VISOR` | 30546689979 | `E01M0X99C8F87H9TH9N39H2D1NW` | 63.140 | `8ed1146358d69ccd…` |

`download_log`: 2 filas, 1 CUIT, `result=DOWNLOADED`, `http=200`.

---

## 3. Integridad — 14/14 controles independientes

| # | control | resultado |
|---|---|---|
| 1.1 | el cambio es exactamente +1/+2/+2 | **OK** — sin desvíos |
| 2.1 | la corrida cerró correctamente | **OK** — `status=OK`, con `finished_at` |
| 2.2 | no quedan corridas `RUNNING` | **OK** — 0 |
| 2.3 | Identity **no** fue modificada | **OK** — 0 en las cuatro métricas |
| 2.4 | todos los artefactos son del mismo CUIT | **OK** |
| 2.5 | todos comparten el mismo `entity_key` | **OK** |
| 2.6 | sin artefactos duplicados en toda la tabla | **OK** — 0 |
| 2.7 | cada artefacto tiene su fila de descarga | **OK** — 0 huérfanos |
| 2.8 | provenance completa en los nuevos | **OK** — 0 incompletos |
| 2.9 | el sha256 coincide con el archivo en disco | **OK** — **2/2 verificados** |
| 3.1 | el CUIT tenía assertion `VERIFIED` vigente | **OK** |
| 3.2 | el `entity_key` coincide con Identity | **OK** |
| 3.3 | ninguna descarga es de otro CUIT | **OK** — 0 ajenas |
| 3.4 | todos los endpoints son de CNV | **OK** |

---

## 4. Impacto

**Ninguno sobre la corrección de los datos.**

El dato agregado es una ingesta legítima: CUIT con assertion `VERIFIED` vigente,
mecanismo oficial, provenance completa, hashes verificados contra disco,
atribución correcta, corrida cerrada. Es *exactamente lo que el sistema debe
hacer* con una empresa habilitada.

**El impacto es sobre el contrato del ciclo, no sobre el dato**: el piloto se
declaró read-only y escribió.

**No se revierte.** Borrar los 2 artefactos eliminaría provenance legítima y
dejaría una corrida `OK` sin sus filas — un estado peor que el actual. El ciclo
prohíbe explícitamente el rollback destructivo y la compensación con otras
escrituras.

---

## 5. Salvaguarda propuesta — DISEÑADA, NO IMPLEMENTADA

Tres barreras, en orden de contundencia:

### 5.1 · El piloto no puede invocar el fetcher sin verificar primero

```python
r = resolver_en_identity_v1(eng, cuit, None)          # lectura pura
assert r["ok"] is False,                 f"{cuit}: el resolver lo AUTORIZA"
assert r["motivo"] == "CUIT_NO_VERIFICADO"
assert caso["status"] == "CANDIDATE"
# sólo entonces, y sólo con autorización explícita, se invoca el fetcher
```

La diferencia con lo que había: **`assert`, no `print`**. Un caso que no cumpla
las tres condiciones **aborta**, no se reporta y continúa.

### 5.2 · `DRY_RUN` obligatorio por defecto

El piloto debe correr sin tocar el fetcher salvo que reciba una autorización
separada y explícita (`--ejecutar-fetcher`, ausente por defecto). En modo seco
sólo consulta el resolver, que no escribe.

### 5.3 · La consulta de universo, corregida

```sql
SELECT i.id_value
  FROM identity_v1.identifier i
 WHERE i.id_type='CUIT' AND i.valid_to IS NULL
 GROUP BY i.id_value
HAVING bool_and(
    (SELECT a.status FROM identity_v1.assertion a
      WHERE a.assertion_id = i.assertion_id) <> 'VERIFIED')
```

Agrupa **por CUIT** y exige que **ninguna** de sus filas sea `VERIFIED`.
Deduplicado por construcción.

---

## 6. Estado de la base

**Íntegra, con el cambio acotado y documentado.**

```
Identity        sin cambios
SEC / parsed    sin cambios
Market          sin cambios
CNV             +1 corrida (OK, cerrada) · +2 artefactos (verificados) · +2 logs
RUNNING         0
```

La base sólo puede declararse íntegra porque una auditoría independiente
—`cnv_incidente_forense.py`, que no reutiliza el script del incidente— confirmó
que **los únicos cambios fueron los descritos**.

---

## 7. Finding sobre `status`

### 7.1 · La elegibilidad depende del orden lexicográfico

`c3_cnv_fetch.py:68`:

```sql
max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)  AS cuit_status
```

`max()` **alfabético sobre texto**. Con el vocabulario actual:

```
CANDIDATE  <  REVIEW_REQUIRED  <  VERIFIED
```

devuelve `VERIFIED` si **alguna** fila lo es. El comportamiento resultante es el
deseado, pero **no está declarado en ningún contrato**: sale del orden alfabético
de tres cadenas. Un estado futuro —`WITHDRAWN`, `SUPERSEDED`, `REVOKED`— lo
invertiría sin que nada avise.

### 7.2 · La regla semántica que corresponde

```
Un CUIT es elegible para CNV si EXISTE al menos una assertion vigente,
sobre ese identificador, con status = 'VERIFIED'.
```

Explícita, inmune al vocabulario, y expresable como
`bool_or(a.status = 'VERIFIED')` en vez de `max(a.status::text)`.

**No se implementa.** Primero hay que documentar el contrato, porque hay una
pregunta previa sin responder.

### 7.3 · La pregunta previa: ¿por qué 8 filas vigentes por identificador?

```
33650305499 | 8 filas vigentes | CANDIDATE,VERIFIED
30546689979 | 8 filas vigentes | CANDIDATE,VERIFIED
30657862068 | 8 filas vigentes | CANDIDATE,VERIFIED
30704962807 | 7 filas vigentes | CANDIDATE
```

Un identificador con ocho filas `valid_to IS NULL` y estados contradictorios
sugiere que las assertions sucesivas **se acumulan en vez de superseder**. Si el
modelo pretendía «una vigente a la vez, las anteriores con `valid_to`», esto es
un defecto de datos, no de la consulta.

**Sin resolver esa pregunta, cualquier regla de elegibilidad es provisional.**

### 7.4 · Observación adicional, para verificar en otro ciclo

La assertion `VERIFIED` que autorizó esta descarga tiene:

```
method = REGISTRY        resolved_by = proc:gleif_fetch
```

Es decir, **un proceso, no una persona**. Los tres puentes CIK↔LEI del ciclo
F-041 sí eran `HUMAN_DECISION` firmados por Federico. Conviene verificar si la
ratificación del **CUIT** sigue el mismo criterio o si un proceso automatizado
puede producir un `VERIFIED`. **No se investiga acá**: excede el alcance del
incidente, y podría afectar el principio G5.

---

## 8. Decisión sobre repetición

**El piloto NO se repite en este ciclo.**

Antes hacen falta, en orden:

| # | requisito | estado |
|---|---|---|
| 1 | Implementar las tres salvaguardas de §5 | **no hecho** |
| 2 | Test con espía del fetcher: `fetch_calls = 0` para `CANDIDATE` **y** para un `VERIFIED` incluido por error | **no hecho** |
| 3 | Mutación que revierta la exclusión `VERIFIED` y que el test la detecte | **no hecho** |
| 4 | Decidir la regla de §7.2 y resolver §7.3 | **decisión de producto** |

Los puntos 2 y 3 son la condición que el ciclo exige: *el piloto debe ser
incapaz de ejecutar CNV para un `VERIFIED`*, y eso debe estar **probado por un
test que falle si la barrera se quita**, no confiado a la disciplina de quien lo
escribe.

---

## Dictamen

```
PILOTO CNV_NEGATIVE_PILOT_20 = BLOCKED / INVALIDATED
INCIDENTE                    = INCIDENTE_CONTROLADO_SIN_CORRUPCIÓN
BASE HOMOLOGADA              = ÍNTEGRA, con +1 corrida y +2 artefactos legítimos
```

El piloto queda invalidado porque **no respetó su propio contrato read-only**,
con independencia de que el dato resultante sea correcto. Un resultado válido
obtenido por un camino que no debía recorrerse no convierte la prueba en válida.
