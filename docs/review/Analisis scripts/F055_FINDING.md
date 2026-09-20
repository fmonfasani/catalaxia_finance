# F-055 — CONTEXTOS "CONTRADICTORIOS" QUE NO LO SON, Y HECHOS PERDIDOS EN SILENCIO

**Detectado:** 2026-08-31, al ingerir los primeros emisores con formulario 10-K
**Severidad: alta** (pérdida silenciosa de datos) · **Estado: CORREGIDO**

---

## 1. Cómo apareció

Tras ingerir MSFT y NVDA, S04 dio `BLOCK` con dos controles en rojo:

```
C-S04-002  corridas distintas en parsed.facts: 2      FAIL
C-S04-003  contextos contradictorios: 224             FAIL
```

`C-S04-002` era esperable: es la invariante del golden case («una sola corrida
en `parsed`»), que deja de valer cuando `parsed` acumula un emisor por corrida
(F-054). `C-S04-003` no era esperable.

## 2. Los contextos no eran contradictorios

```
context_id C_038d32c1-52b4-41a1-9188-049deaa7765e

 source_file             start_date  end_date    period_kind
 msft-20250630.htm       2024-07-01  2025-06-30  DURATION
 msft-20250630_htm.xml   2024-07-01  2025-06-30  DURATION
```

Mismo período, mismo tipo. La diferencia estaba en el **orden** de la lista de
dimensiones:

```
.htm       [ DebtInstrumentAxis , RangeAxis ]
_htm.xml   [ RangeAxis , DebtInstrumentAxis ]
```

SEC publica el documento **inline** (`.htm`) y la **instancia extraída**
(`_htm.xml`) del mismo filing; S03 parsea ambos, y cada uno serializa las
dimensiones en distinto orden.

La comparación era `dimensions::text`, **sensible al orden**. Una lista de
dimensiones es un conjunto, no una secuencia.

## 3. Por qué es pérdida de datos, no sólo un gate en rojo

`contextos_deduplicados()` no se limita a reportar: **descarta**.

```python
for f in filas:
    if f["variantes"] > 1:
        contradictorios.append(dict(f))
        continue          # <- el contexto NO entra en `ctx`
```

Un hecho cuyo contexto no está en `ctx` no llega a `derived.fact`. Los 224
contextos falsamente contradictorios se llevaron consigo los hechos que los
usaban.

Medido en MSFT: **3.698 hechos por representación**, y sólo **3.180** llegaron a
`derived`. La diferencia no es toda por esta causa —parte es la deduplicación
legítima entre las dos representaciones— pero la porción atribuible a contextos
descartados **se perdía sin que ningún control lo dijera**: `C-S04-005` cuenta
los hechos «sin representar» dentro de lo que sí entró.

## 4. Por qué no apareció antes

YPF presenta 20-F con una sola representación XBRL relevante por filing. El
patrón inline + instancia extraída, con dos serializaciones distintas del mismo
contexto, aparece en los **10-K**. El sistema nunca había ingerido uno.

> No es que el control fuera débil: es que el universo era de un solo emisor y
> de un solo formulario. La segunda taxonomía trajo el caso.

## 5. Corrección

Se canoniza la lista de dimensiones **ordenando sus elementos** antes de
comparar, en los dos lugares donde se comparaba como texto:

- `contextos_deduplicados()` — el que descartaba;
- el control `C-S04-003` — el que reportaba.

```sql
CASE WHEN jsonb_typeof(dimensions) = 'array'
     THEN (SELECT jsonb_agg(e ORDER BY e::text)
             FROM jsonb_array_elements(dimensions) e)
     ELSE dimensions END
```

Es el mismo criterio que `hashout-v2` ya había adoptado para las filas
—ordenar antes de agregar— y que no se había aplicado acá.

`C-S04-002` pasa a verificar la invariante que corresponde a `parsed`
acumulativo: **ningún CIK mezcla corridas**, en lugar de «una sola corrida en la
tabla».

## 6. Dos defectos vecinos, encontrados al corregir éste

### 6.1 · Las dimensiones tipadas arrastran los `xmlns` del documento

Corregido el orden, quedaban contradicciones en un filing de AAPL. La causa era
más fina: una dimensión **tipada** guarda el fragmento XML crudo, y con él **las
declaraciones de namespace vigentes en ese punto del documento**.

```
_htm.xml   <us-gaap:...StartDateAxis.domain xmlns:us-gaap="..." xmlns="http://www.xbrl.org/2003/instance" ...>2024-09-29</...>
.htm       <us-gaap:...StartDateAxis.domain xmlns:us-gaap="..." xmlns="http://www.w3.org/1999/xhtml"     ...>2024-09-29</...>
```

Misma dimensión, mismo valor (`2024-09-29`), mismo contenedor. Distinto conjunto
de prefijos, porque uno vive dentro de un XHTML y el otro dentro de una
instancia XBRL. Se comparan ahora **sin ese ruido**: los atributos `xmlns` se
eliminan antes de comparar.

### 6.2 · La conciliación sumaba filings con archivos

`StageReport.validate()` exige `expected == parsed + rejected`. S03 pasaba:

```python
rejected = outcomes["REJECTED"] + len(files_bad)
```

`expected` y `parsed` cuentan **filings**; `files_bad` cuenta **archivos**.
Mientras no faltó ningún archivo, la suma cerró por casualidad. Al re-parsear
YPF con tres archivos globales ausentes (`COMPANYFACTS`, `SUBMISSIONS`,
`SUBMISSIONS_PAGE`, perdidos en el incidente de `data/raw`) y un `index.json`
cuyo hash cambió, la etapa murió con:

```
ValueError: Conciliacion invalida: expected(27) != parsed(27) + rejected(4)
```

Los cuatro archivos ni siquiera entraban en `filings_expected` —los globales se
excluyen de los buckets—, así que sumarlos era incorrecto por construcción.
`rejected` cuenta ahora sólo filings; los archivos corruptos siguen bloqueando
el gate por `C-S03-001` y `C-S03-002`, que es donde corresponde.

## 7. Relación con F-054

Son dos defectos distintos que la misma acción destapó —ingerir un segundo y un
tercer emisor— y que comparten origen: **controles escritos para un universo de
una sola empresa y un solo formulario**. F-054 rompía la provenance entre
corridas; F-055 descartaba datos dentro de una corrida.

Ninguno de los dos lo habría encontrado un test unitario: el primero lo encontró
la auditoría independiente al exigir que la cadena hasta la evidencia cerrara, y
el segundo apareció al correr el pipeline real sobre un emisor nuevo.
