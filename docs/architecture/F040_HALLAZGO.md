# F-040 — C3 (CNV) DEJA CORRIDAS HUÉRFANAS: F-009 SOBREVIVE EN ESE WORKSTREAM

**Detectado:** 2026-08-28, ciclo 7 fase H, auditando la salud de `engine.runs`
**Estado:** **registrado, no corregido** — la corrección es un refactor de C3,
fuera del alcance declarado del ciclo 7
**Severidad:** media. No corrompe datos; corrompe el relato de qué pasó.

---

## 1. El hallazgo

```
engine.runs por estado
   ABORTED    55      terminal, correcto
   OK         44      terminal, correcto
   BLOCKED    38      terminal, correcto
   RUNNING     3      <-- nada está corriendo
```

Las tres son de hoy y son mías:

| run_id | inicio UTC | qué fue |
|---|---|---|
| `b01395aa…` | 15:00:29 | primer fetch de YPF, muerto por la CheckViolation de F-039 |
| `021cb5dc…` | 15:01:23 | el fetch que lancé para leer el error completo |
| `50251c19…` | 15:04:49 | el fetch que maté con `timeout 560` |

Las tres `pipeline_version = cnv-fetch-v1`. Ninguna tiene `finished_at`.

## 2. La causa

```
grep -c run_scope scripts/engine/c3_cnv_fetch.py  ->  0
```

C3 administra su corrida a mano: escribe el estado terminal en el camino feliz y
no lo escribe si el proceso muere antes. `run_scope()` existe justamente para
eso — cierra el estado terminal en un `finally`, de modo que un crash deja
`ABORTED` en vez de un `RUNNING` eterno.

**F-031 migró S03 a `run_scope()`. C3 nunca se migró.** El defecto que se cerró
en SEC sigue abierto en CNV. No es una regresión: es alcance que no se cubrió, y
que sólo se ve cuando algo falla — hoy falló tres veces seguidas.

## 3. Por qué importa, aunque no rompa datos

Es exactamente el problema del que trata este ciclo. Un auditor que consulte
`engine.runs` hoy ve tres corridas de CNV en curso. No hay ninguna. La base
afirma algo que no es cierto sobre el pasado, que es la misma clase de defecto
que F-038 (donde el que se equivocó fui yo leyendo la base equivocada) y que la
razón de existir de `run_scope()`.

`corridas_huerfanas()` (F-009) **existe y las detectaría**, pero:

- es un **detector**, no un cierre: informa, no marca terminal;
- corre **al arrancar una etapa**, y C3 no la llama;
- su umbral es de **6 horas**, así que estas tres todavía no calificarían.

O sea: el mecanismo está construido y este workstream no lo usa.

## 4. Corrección propuesta (no aplicada)

1. Envolver el cuerpo de `c3_cnv_fetch.main()` en `edb.run_scope()`, como hizo
   F-031 con S03. Sin tocar parsing, normalización ni contratos de datos.
2. Llamar `corridas_huerfanas()` al arrancar C3, como hacen las demás etapas.
3. Cerrar las 3 huérfanas de hoy como `ABORTED` — **no borrarlas**: registran
   que hubo tres intentos fallidos, que es información real y es la evidencia de
   F-039.

## 5. Qué NO hacer

No bajar el umbral de `corridas_huerfanas()` para que las detecte antes. El
umbral no es el problema: el problema es que C3 no cierra su propia corrida.
Ajustar el detector en vez del emisor es la misma tentación que en F-028, donde
la solución fácil era subir el `statement_timeout` en vez de correr `ANALYZE`.
