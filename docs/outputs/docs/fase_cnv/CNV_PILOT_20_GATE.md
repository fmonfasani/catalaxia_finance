# CNV_PILOT_20_GATE

**Fecha:** 2026-09-01 · **Rol:** Orquestador de homologación
**Ciclo:** CNV-PILOT-20 — validación multiempresa
**No se escribió en la base. No se modificó código, schema ni `data/raw`.**

---

# GATE = **BLOCKED**

El piloto **no se ejecutó**, por dos causas independientes. La primera es
temporal; la segunda es estructural y no se resuelve esperando.

---

## 1. Fase 0 — concurrencia: BLOQUEO ACTIVO

La Fase 0 exige detenerse si hay otro agente operando la base. Lo hay:

```
PID 5592  03:41  psql -U catalaxia -d postgres -v ON_ERROR_STOP=1
                 -c CREATE DATABASE "adversario_ratios_mut" TEMPLATE "catalaxia"
PID 5598  03:41  postgres: catalaxia postgres [local] CREATE DATABASE   [estado Ds]
```

Es el banco adversario del **workstream de ratios**, corriendo su propia copia
descartable. `CREATE DATABASE … TEMPLATE` exige que **nadie** esté conectado a la
plantilla, de modo que bloquea toda conexión nueva a `catalaxia` mientras dura.

Consecuencia medida: una lectura directa **expira**.

```
timeout 90 docker exec … psql -c "SELECT count(*) FROM parsed.facts …"
→ Terminated (rc=143)
```

`docker exec echo` responde al instante; lo bloqueado es PostgreSQL aceptando
conexiones nuevas, no el contenedor.

### El bloqueo es INTERMITENTE, con ventanas entre iteraciones

Un reintento en bucle sí entró:

```
intento 1  → bloqueado
intento 2  → bloqueado
intento 3  → LECTURA OK · CUIT VERIFIED | total = 3 | 56
```

Y a los pocos segundos arrancó otra instancia (`PID 5705`), confirmando que el
otro agente corre su banco **en ciclo**. Hay ventanas de segundos entre
iteraciones.

**Lo que esto habilita y lo que no:**

| tipo de trabajo | ¿cabe en una ventana? |
|---|---|
| lectura corta (fingerprint, conteos) | **sí**, con reintento |
| ejecución de casos **bloqueados** (§7 opción A) | **sí** — `load_identity()` corta antes de abrir corrida: no escribe |
| copia descartable propia + fetch real | **no** — necesita acceso sostenido, y competiría por la misma plantilla |

Por eso el fingerprint de §6 **sí** pudo tomarse, y el piloto completo no.

---

## 2. El bloqueo estructural: el universo no tiene la población que el piloto pide

Esto es lo importante, y **no depende de la concurrencia**. Medido **en vivo**
durante este ciclo, aprovechando una ventana entre iteraciones del otro agente:

```sql
SELECT count(*) FILTER (WHERE a.status='VERIFIED') || '|' || count(*)
  FROM identity_v1.identifier i
  JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
 WHERE i.id_type='CUIT' AND i.valid_to IS NULL;
-- resultado: 3|56
```

```
identificadores CUIT vigentes en identity_v1 ......... 56
  con assertion VERIFIED ............................  3
  con assertion CANDIDATE ........................... 53
```

Los tres `VERIFIED` son exactamente:

| empresa | CIK | CUIT | assertion |
|---|---|---|---|
| CENTRAL PUERTO S.A. | 0001717161 | 33650305499 | VERIFIED · REGISTRY |
| YPF SOCIEDAD ANONIMA | 0000904851 | 30546689979 | VERIFIED · REGISTRY |
| TRANSPORTADORA DE GAS DEL SUR | 0000931427 | 30657862068 | VERIFIED · REGISTRY |

**Son las tres que el ciclo quiere superar.**

### Lo que el piloto pide vs. lo que existe

| grupo del encargo | requiere | disponible |
|---|---:|---:|
| 5 con CUIT VERIFIED y actividad CNV esperable | 5 | — |
| 5 VERIFIED de sectores diferentes | 5 | — |
| 4 VERIFIED con distinto volumen histórico | 4 | — |
| **subtotal VERIFIED** | **14** | **3** |
| 3 con riesgo de ambigüedad ticker/nombre | 3 | abundante |
| 3 que NO deberían poder ejecutar CNV | 3 | 53 |

**Faltan 11 empresas con CUIT VERIFIED**, y no hay forma legítima de obtenerlas
dentro de las restricciones de este ciclo:

- **«No realizar ratificaciones humanas»** — y ratificar es, por diseño, el único
  camino a `VERIFIED`.
- **«No inventar CUIT»**.
- **«No usar ticker/nombre como autoridad»**.

### Por qué no es un defecto, sino el modelo funcionando

El hallazgo **G5** del ciclo de Identity ya lo estableció: *ninguna fuente
primaria publica el puente CIK↔CUIT*. Por eso cada CUIT autoritativo exige una
**ratificación humana** con evidencia citada, y por eso hay 3 y no 56.

El piloto, tal como está especificado, le pide al sistema que generalice por un
camino que el modelo de identidad **deliberadamente cierra**. No se puede validar
la generalización del camino positivo más allá de 3 sin ratificar 11 puentes — y
ratificar es una decisión humana, no una operación de pipeline.

---

## 3. Lo que sí quedó demostrado, y no es poco

De ciclos anteriores, con evidencia reproducible en
`outputs/docs/fase_cnv/cnv_identity_bench.json` (**15/15 controles**):

| qué | evidencia |
|---|---|
| El mecanismo **no** nombra a CEPU | se eliminó el CUIT hardcodeado y el seed `cnv_identity_seed_cepu.csv` dejó de decidir (F-053) |
| La elegibilidad es **una regla, no una lista** | `resolver_en_identity_v1()` exige `assertion.status = 'VERIFIED'`; no hay condicional por empresa |
| Se entra por CIK **o** por CUIT y dan lo mismo | verificado en las 3 empresas |
| GGAL queda bloqueada por `CANDIDATE` | **antes de abrir corrida y antes del primer request** |
| AAPL queda bloqueada por `SIN_CUIT` | ídem |
| Un CUIT inexistente no obtiene clave provisional | `NO_ESTA_EN_IDENTITY_V1` |
| Sin atribución cruzada | `C-C3-010` al 100 % en YPF y TGS |

**El mecanismo ya es general.** Lo que no es general es la *población habilitada*,
y eso es una consecuencia querida del modelo de identidad, no un defecto del
fetcher.

---

## 4. Lo que NO está demostrado

| | por qué |
|---|---|
| Que el camino positivo funcione en emisores con volumen o estructura distinta | sólo 3 habilitados, todos ya probados |
| Que el bloqueo funcione **a escala** | probado en 2 casos negativos (GGAL, AAPL) de 53 disponibles |
| Idempotencia sobre fuente viva en más de 1 empresa | sólo YPF/TGS con alcance mínimo |
| Que la provenance CNV sea verificable | **91,7 % de los artefactos no están en disco** (316 de 3.829) |

---

## 5. Artefactos no producidos, y por qué

| artefacto | estado |
|---|---|
| `CNV_PILOT_20_REPORT.md` | **no producido** — no hay corridas que reportar |
| `CNV_PILOT_20_MATRIX.csv` | **no producido** — la matriz tendría 3 filas ejecutables de 20 |
| `CNV_PILOT_20_ADVERSARIAL.json` | **no producido** — requiere base descartable, bloqueada |
| `CNV_PILOT_20_AUDIT.json` | **no producido** — la auditoría independiente no puede leer la base |

Producir cualquiera de ellos con datos parciales sería exactamente lo que el
criterio del ciclo prohíbe: **convertir una limitación de evidencia en un PASS.**

---

## 6. Estado de la base

| | |
|---|---|
| antes | `135077 \| 88789 \| 8 \| 47684` (medido con baseline limpio en este ciclo) |
| después | **NO VERIFICABLE** — lectura bloqueada por el `CREATE DATABASE` ajeno |
| DELTA | **0 por construcción**: no se ejecutó ninguna escritura |
| RUNNING | no verificable ahora; era 0 en la última lectura exitosa |
| SEC / Market | **sin cambios** — no se ejecutó ninguna etapa de ninguno |

---

## 7. Recomendación sobre ampliar a 50 / 100 empresas

**No corresponde plantear la ampliación todavía**, y la razón no es técnica.

Ampliar de 20 a 50 o 100 empresas exige 50 o 100 CUIT `VERIFIED`. Hoy hay **3**.
El cuello de botella no es el fetcher —que ya demostró ser general— sino el
**ritmo de ratificación humana**, que es una decisión de producto sobre cuánta
evidencia se exige por puente y quién la firma.

### Las tres opciones reales, en orden de honestidad

**A · Validar el camino NEGATIVO a escala.** Es ejecutable **hoy**, sin ratificar
nada: tomar 20 de los 53 `CANDIDATE`, intentar CNV en los 20, y demostrar que los
20 se bloquean antes de abrir corrida, sin escribir una fila ni gastar un
request. Eso prueba que el gate de identidad es una regla general y no una lista
de tres empresas. **Es la mitad del criterio de éxito del ciclo, y es alcanzable.**

**B · Ratificar un lote acotado y después validar.** Elegir 5–10 emisores,
ratificar sus puentes con evidencia citada por una persona, y recién entonces
correr el piloto positivo. Requiere decisión y firma humana: fuera del alcance de
un ciclo de validación.

**C · Revisar la política de ratificación.** Si 3 de 56 es demasiado lento para
el producto, la pregunta no es del pipeline sino del contrato de identidad: qué
evidencia se considera suficiente para un puente CIK↔CUIT. **Es una decisión de
producto y este ciclo no debe tomarla.**

---

## 8. Findings nuevos

**Ninguno.** No se ejecutó nada que pudiera revelar uno.

Se registra una **observación operativa**, no un finding del sistema:

> Dos agentes operan la misma PostgreSQL sin mecanismo de exclusión. El banco
> mutacional del workstream de ratios usa `CREATE DATABASE … TEMPLATE catalaxia`,
> que bloquea toda conexión nueva a la plantilla durante minutos. Cualquier otro
> ciclo que necesite leer o escribir queda detenido sin aviso. Conviene que los
> bancos descartables usen `pg_dump | psql` —que no exige exclusividad— en lugar
> de `TEMPLATE`, o que se coordine una ventana.

---

## Dictamen

# CNV_PILOT_20_GATE = **BLOCKED**

Dos bloqueos, uno temporal y uno estructural:

1. **Concurrencia activa** impidió incluso leer el fingerprint. Se respetó la
   regla y no se escribió nada.
2. **El universo tiene 3 CUIT `VERIFIED` y el piloto necesita 14.** Los tres son
   las mismas empresas que el ciclo quería superar.

El criterio de éxito —*«demostrar que CNV no es un caso especial de CEPU/YPF/TGSU2
sino un mecanismo general»*— **ya está demostrado por el lado del mecanismo**: la
elegibilidad es una regla sobre `assertion.status`, sin ninguna condición por
empresa. Lo que falta es población habilitada, y eso se consigue ratificando, no
validando.

**La opción A de §7 permite cerrar la mitad restante del criterio hoy mismo, sin
ratificar nada y sin escribir una sola fila.** Es la que recomiendo.
