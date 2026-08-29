# F-041 — GATE

**Fecha:** 2026-08-28 (ciclo 9) · **Instancia:** `catalaxia-engine-dev` 127.0.0.1:5433
**Reproducible:** `python scripts/engine/audit_f041.py`

---

## VEREDICTO: **CLOSED_WITH_NOTES**

6 de las 7 assertions tienen evidencia estructurada verificada contra su
artefacto primario. **La séptima queda como deuda explícita**, no fabricada.

---

## Reporte

| | |
|---|---|
| assertions inspeccionadas | **7** |
| estructurables (clase A) | **0** — vacía por contrato, ver §2 |
| reafirmables (clase B) | **6** |
| no estructurables (clase C) | **1** |
| conflictos (clase D) | **0** |
| **modificadas** | **0** — ninguna assertion histórica fue editada |
| nuevas | **6** assertions + 6 identifiers |
| duplicadas | **0** |
| provenance perdida | **0** |
| auditoría independiente | **15/15 OK**, sin importar código del implementador |
| tests | **12** adversariales (F-041) · 56 en la suite de regresión |
| findings nuevos | **F-042** (encontrado y **cerrado** en este ciclo) |

---

## 1. Las 7, una por una

| assertion | CIK | fuente | entidad | clase | resultado |
|---|---|---|---|---|---|
| 1 | 0000904851 | `SEC_20F` | YPF | **C** | **deuda** |
| 5 | 0001717161 | `SEC_REGISTRY` | Central Puerto | B | → #1387 |
| 10 | 0001114700 | `SEC_REGISTRY` | Grupo Galicia | B | → #1388 |
| 13 | 0000931427 | `SEC_REGISTRY` | TGS | B | → #1389 |
| 205 | 0000320193 | `SEC_REGISTRY` | Apple | B | → #1390 |
| 207 | 0000789019 | `SEC_REGISTRY` | Microsoft | B | → #1391 |
| 209 | 0001045810 | `SEC_REGISTRY` | NVIDIA | B | → #1392 |

Verificadas históricas: las 4 primeras son del **2026-08-25 20:20**, las 3
últimas del **2026-08-28 10:06**. El primer backfill CIK corrió a las **18:36**
del 28. Ninguna es suya.

## 2. Por qué la clase A quedó vacía

Clase A significa *poblar `source_facts` en la assertion existente*. Eso exige
editarla, y editar una assertion histórica es exactamente lo que la regla
fundamental prohíbe. El propio mensaje del trigger lo dice: *«cree una assertion
nueva y supersédala; no la edite.»*

Llamar A a alguno de estos casos habría sido usar el hueco de F-042 y presentarlo
como una clase legítima. **Las 6 con evidencia suficiente son B, no A** — la
diferencia no es la evidencia, es el mecanismo.

## 3. F-042 — el hallazgo que este ciclo destapó y cerró

`fn_assertion_inmutable` enumeraba 16 columnas y **`source_facts` no estaba entre
ellas**: la columna se agregó en F-036, después de escribirse el trigger.
Verificado empíricamente contra la base real:

```
UPDATE identity_v1.assertion SET source_facts = '{"inventado":"x"}'
 WHERE assertion_id = 5;              -->  ACEPTADO
UPDATE ... SET source_facts = NULL;   -->  ACEPTADO  (borrar evidencia)
```

Ese era el camino de un renglón para «cerrar» F-041, y la fila resultante habría
sido **indistinguible de una legítima**. Mientras el hueco existiera, toda la
disciplina de re-afirmación era decorativa.

**Alcance real:** el rol de aplicación `catalaxia_engine` no llegaba —su GRANT
sobre `assertion` es sólo `(valid_to, superseded_by)`. El agujero estaba en el
trigger, que es la capa que debería ser la última.

Cerrado en `migrations/engine/029`. La supersession sigue permitida, que es lo
que la re-afirmación necesita, y hay un test que lo verifica: tapar el hueco no
podía romper el mecanismo legítimo.

## 4. El mecanismo, y por qué no reescribe nada

Cuatro pasos en una transacción:

```
1. INSERT assertion nueva   -- mismo hecho, source_facts completos
2. UPDATE identifier viejo  -- valid_to = now(), status = 'RETIRED'
3. INSERT identifier nuevo  -- mismo id_value, apunta a la nueva
4. UPDATE assertion vieja   -- valid_to = now(), superseded_by = nueva
```

El orden importa: `ux_identifier_autoritativo_unico` es parcial sobre
`valid_to IS NULL`, así que el viejo se retira antes de insertar el nuevo.

`identifier.assertion_id` no es repuntable por el rol de aplicación (su GRANT es
`status, valid_to`), y por eso hacen falta los pasos 2 y 3 en vez de un UPDATE.

**El ancla no se movió.** La auditoría verifica, CIK por CIK, que cada uno
designa la misma `entity_key` que antes. Y verifica que ninguna re-afirmación
cambió fuente, registro, entidad ni método: sólo agregó la evidencia estructurada.

## 5. La deuda: YPF, assertion #1

La assertion declara `SEC_20F`, accession `0001193125-17-115552`. **El documento
20-F nunca se archivó.** Bajo
`data/raw/engine/CIK0000904851/filings/000119312517115552/` sólo existe
`index.json`, que lista los archivos del directorio y **no declara el CIK ni el
form**: el CIK vive en la *ruta* de SEC, no en el contenido.

Estructurar desde ahí sería inferir.

El hecho **sí** está corroborado: `data/raw/submissions/CIK0000904851.json`
declara que ese accession es un `20-F` del `2017-04-07` para el CIK 0000904851.
Eso quedó **registrado** en `f041_clasificacion.json` como
`corroboracion_independiente` — y deliberadamente **no se usó** para estructurar
esta assertion, porque cambiaría cuál es la fuente que la sostiene.

> Es una fuente distinta de la declarada. Usarla acá haría que la assertion
> dijera una cosa y se apoyara en otra.

## 6. Idempotencia

Tres corridas. La 2ª y la 3ª: *«assertions sin evidencia estructurada: 1 · nada
que re-afirmar»*. La condición de entrada es `source_facts IS NULL`, y la
operación la deja de cumplir. Cero duplicaciones, cero assertions espurias, cero
cambios semánticos.

## 7. Estado final

| | antes | después |
|---|---|---|
| CIK autoritativos vigentes | 513 | **513** |
| de esos, sin `source_facts` | 7 | **1** |
| entidades | 525 | **525** |
| CUIT autoritativos | 3 | **3** |
| identifiers `RETIRED` | 0 | 6 |
| assertions supersedidas | 0 | 6 |
| assertions totales | 608 | 614 |

## 8. Restricciones respetadas

Sin commits · sin tocar `data/raw` · sin SEC, CNV, Market ni M23 · sin BYMA ·
sin backfill adicional · sin tocar bridges CIK↔LEI ni CUIT autoritativos · sin
inventar evidencia · sin editar una sola assertion histórica.

El gate no se cierra porque los tests pasen: se cierra porque la auditoría
independiente recalcula el sha256 de cada artefacto y coteja cada campo, y porque
la mutación del trigger hace fallar los ataques 7 y 8 — prueba de que no son
vacíos.
