*# F-050 — S00, S01 y S02 DEJAN CORRIDAS HUÉRFANAS

**Detectado:** 2026-08-31, durante el E2E de v1.0.1 (Fase 2 / Fase 7)
**Estado: CORREGIDO (2026-09-04)** — migración a `run_scope()` en S00/S01/S02 + tests
`tests/test_f050_lifecycle_s00_s02.py` (19/19 verdes). Ver sección 8.
**Severidad: media.** No corrompe datos; corrompe el relato de qué corrió.

---

## 1. El hallazgo

Sobre la instalación limpia `e2e_v101`, tras dos fallos reales de la propia prueba
(S01 abortó por `FileNotFoundError` antes de tener `data/raw`; S02 lo maté con
`timeout`), la base quedó con:

```
run_id                            pipeline_version  status   started_at           finished_at
e2eb736dd449480a8cd05e0e3acd0272  s1-identity-v1    RUNNING  2026-08-31 15:59:07  (vacío)
ef005a5cda6d41e4b5f65ded5fd6655f  s1-identity-v1    RUNNING  2026-08-31 15:59:14  (vacío)
0a9b7028267e44e4ac1ea7441a40f492  s2-fetch-v1       RUNNING  2026-08-31 16:01:06  (vacío)
c2bbf9bbb6094275be054f0254d06644  s2-fetch-v1       RUNNING  2026-08-31 16:06:06  (vacío)
```

## 2. La causa

```
s00_smoke.py      run_scope=0   start_run=1
s01_identity.py   run_scope=0   start_run=1
s02_fetch_ypf.py  run_scope=0   start_run=1
s03_parse_ypf.py  run_scope=3   (F-031)
s04_normalize.py  run_scope=3
c3_cnv_fetch.py   run_scope=3   (F-040)
```

**Tres etapas nunca se migraron a `run_scope()`.** Abren la corrida con `start_run()`
y la cierran con `finish_run()` en el camino feliz; si el proceso muere antes, la fila
queda en `RUNNING` para siempre.

Es **exactamente** el defecto de F-009, cerrado en S03 por F-031 y en C3 por F-040. La
migración se hizo etapa por etapa y **S00/S01/S02 quedaron fuera**.

## 3. Por qué la homologación no lo vio

La homologación verificó **`0 RUNNING` sobre la base homologada** — y era cierto. Pero
en esa base S01 y S02 nunca habían fallado: sus corridas siempre terminaron bien.

**Se midió el estado, no la capacidad.** El E2E con inyección de fallos lo reveló en
minutos: bastó que dos etapas murieran.

Es la misma lección que dejaron F-038, F-040 y F-049: *un mecanismo que existe, se
supone funcionando, y nadie había ejercitado*.

## 4. Lo que NO es

- **No corrompe datos.** Las corridas huérfanas no escriben nada a medias: S01 y S02
  usan transacciones propias por unidad de trabajo.
- **No invalida la homologación de SEC.** S03 y S04 —las etapas que producen
  `parsed` y `derived`— **sí** usan `run_scope()` y quedan correctas.
- **No es un blocker de release.** El release instala y corre; lo que falla es la
  higiene del registro de corridas cuando una etapa temprana muere.

## 5. Lo que sí es

Un auditor que consulte `engine.runs` en una instalación donde S01/S02 hayan fallado
alguna vez ve corridas en curso que no existen. Y `corridas_huerfanas()` (F-009) las
detectaría, pero **ninguna de las tres etapas la invoca al arrancar** — como sí hace
C3 desde F-040.

## 6. Corrección propuesta (no aplicada)

Migrar `s00_smoke.py`, `s01_identity.py` y `s02_fetch_ypf.py` al patrón de F-031/F-040:

1. envolver el cuerpo en `edb.run_scope(...)`;
2. que el cuerpo fije `run.status` en vez de llamar a `finish_run()`;
3. invocar `corridas_huerfanas()` al arrancar, como hace C3.

Sin tocar parsing, fetch ni contratos de datos. Es el mismo cambio que ya se hizo dos
veces y está probado.

**Y cerrar las 4 huérfanas de la base E2E** — que es descartable, así que se eliminan
con ella.

## 7. Nota de alcance

`v1.0.1` **no incluye `data/raw`** (correcto: los datos no se versionan). Una
instalación limpia necesita adquirir los artefactos antes de correr S01/S02. Eso es
una **limitación de alcance del paquete**, no un defecto — pero conviene que el
procedimiento de despliegue lo diga.
