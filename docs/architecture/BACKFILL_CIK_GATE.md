# BACKFILL_CIK_GATE — ciclo 8

**Fecha:** 2026-08-28 · **Instancia:** `catalaxia-engine-dev` 127.0.0.1:5433
**Reproducible:** `python scripts/engine/audit_backfill_cik.py`

---

## VEREDICTO: **PASS**

> **Actualizado 2026-08-28 (ciclo 9).** El gate se emitio como
> `PASS_WITH_WARNINGS` por F-041. F-041 quedo **CLOSED_WITH_NOTES**: 6 de las 7
> assertions se re-afirmaron con evidencia estructurada verificada contra su
> artefacto, y la septima (YPF, `SEC_20F`) es deuda explicita porque el
> documento 20-F nunca se archivo. El ancla no se movio: 513 CIK autoritativos,
> cada uno designando la misma entidad. Ver `F041_GATE.md`.
>
> El ciclo 9 tambien encontro y cerro **F-042**: `source_facts` era mutable y
> borrable en assertions historicas porque el trigger de inmutabilidad no la
> cubria. Era el camino de un renglon para "cerrar" F-041 sin evidencia.

### Veredicto original del ciclo 8: PASS_WITH_WARNINGS

El backfill del universo CIK es seguro, idempotente, autoritativamente anclado,
reproducible y auditable, sin inferencias ni duplicaciones. La auditoría
independiente da **PASS** en los 14 controles.

El *WARNINGS* es por **F-041**, un hallazgo nuevo que este ciclo destapó y que
**no introdujo**: 7 CIK de ciclos anteriores no tienen evidencia estructurada.
No bloquea, pero no corresponde declarar PASS liso mientras esté abierto.

---

## Reporte

| | |
|---|---|
| **F-040** | **CLOSED.** C3 migrado a `run_scope()`; 3 huérfanas cerradas como `ABORTED` |
| **universo CIK** | **512 elegibles** de 573 legacy (medido, no supuesto) |
| **entidades creadas** | **505** |
| **entidades reutilizadas** | **7** |
| **identificadores agregados** | **514** (505 CIK + 9 CUIT legacy como `CANDIDATE`) |
| **reviews** | **11** — delta **0**: el backfill no abrió ninguna |
| **conflicts** | **1** — delta **0** (el de BMA, preexistente) |
| **duplicados** | **0** |
| **idempotencia** | **4 corridas**; a partir de la 2ª: 0 creadas, 512 reutilizadas, **hash de contenido idéntico** |
| **auditoría independiente** | **PASS** — 14/14 controles, sin importar código del implementador |
| **BYMA procesados** | **0** |
| **BYMA bloqueados** | **56**, con dossier |
| **CNV ejecutado** | **no** |
| **Market ejecutado** | **no** |
| **SEC modificado** | **no** |
| **Identity** | +505 entidades, +505 CIK autoritativos, **CUIT autoritativos: 3 → 3** |
| **Findings nuevos** | **F-041** — cerrado en el ciclo 9 (`CLOSED_WITH_NOTES`), junto con **F-042** |
| **Próxima acción** | la cola de 9 ratificaciones ADR (F-041 y F-042 ya cerrados) |

---

## 1. Lo que el backfill NO hizo, y es lo que importa

```
cuit_autoritativos    3 -> 3   (+0)
reviews_open         11 -> 11  (+0)
conflicts             1 -> 1   (+0)
```

**Cero CUIT autoritativos producidos.** Los 3 que existen son las ratificaciones
humanas del ciclo 6 y no se tocaron. Los 13 CUIT legacy que el backfill encontró
entraron como `CANDIDATE`/`WEAK` — nunca resolubles, nunca ancla. Es la causa
raíz de F-032, cerrada y ahora ejercitada sobre 512 casos reales.

**Cero bridges automáticos.** Ninguna entidad con CIK y LEI produjo un puente:
G5 sigue vigente y el sistema no finge que alguna fuente lo publica.

---

## 2. Correcciones a premisas del enunciado

El enunciado pedía no dar por buenos los números. Dos no resistieron:

### «no asumir 512: medirlo» → **512**, pero por poco

La primera medición dio **510**, con 2 clasificados como CIK inválido:
**EXXON MOBIL (0000034088)** y **ELECTRONIC ARTS (0000712515)**.

No eran inválidos. Mi clasificador exigía presencia en `company_tickers.json`,
cuando el contrato acepta **cualquiera** de los dos artefactos primarios.
`submissions/CIK0000034088.json` declara `name='EXXON MOBIL CORP'`,
`tickers=['XOM']`.

Lo interesante: el catálogo **actual** mapea XOM al CIK **2115436, «ExxonMobil
Holdings Corp»** — una sucesión societaria. El CIK viejo sigue siendo un CIK real
de SEC; lo que cambió es a quién apunta el *ticker*. **Corregirlo por ticker
habría sido la inferencia prohibida** (es el caso COUR/Coursera). Se ancló la
entidad en su CIK y no se tocó el ticker.

### «18 ADR con CIK» → son **13**

De los 18 ADR del legacy, **5 no tienen CIK**: CAAP, GGALB, SUPVB, YPFLUZ y BMA
(cuyo CIK vive en la columna `cuit`, F-024). Los que sí lo tienen son 13:
`BBAR CEPU CRES EDN GGAL IRSA LOMA PAMP SUPV TECO2 TGSU2 VIST YPFD`.

**Esto corrige el número que di en el ciclo 7.** La cola de ratificación no es de
14: es de **9** (13 − 3 ratificados − GGAL excluido).

---

## 3. Banco adversario (fase E) — 15 ataques

Los 11 del enunciado más 4 controles del contrato. Todos pasan, y **la mutación
demuestra que no son vacíos**.

El ataque 2 (*el mismo CIK contra otra entidad*) tuvo que rehacerse **tres
veces**, y sólo la mutación lo reveló:

1. esperaba una excepción, pero la capa de dominio devuelve `REJECTED` — error del test;
2. reusaba cualquier assertion `VERIFIED`, así que lo rechazaba
   `tg_identifier_autoritativo`, no el índice único;
3. usaba `status='VERIFIED'` en el *identifier*, cuyo dominio es
   `ACTIVE|RETIRED|DISPUTED`, así que moría en `identifier_status_check` antes de
   llegar al índice.

Con el índice borrado, el test **seguía pasando** en las tres versiones. Ahora
`rechaza()` exige que el rechazo nombre **la garantía esperada**, y al borrar
`ux_identifier_autoritativo_unico` el ataque falla como debe.

> Un ataque que pasa por una razón distinta de la que declara no prueba nada.

---

## 4. Fase I — elegibilidad (sin ejecutar nada)

| | |
|---|---|
| entidades con CIK autoritativo | **513** |
| elegibles **Identity → Market** | **512** (499 sp500 + 13 adr) |
| elegibles **Identity → CNV** | **3** |

La brecha entre 512 y 3 **es** G5. Market opera sobre el instrumento y le alcanza
el ancla; CNV se consulta por CUIT, y el CUIT exige una decisión humana por
empresa porque ninguna fuente publica el puente CIK↔LEI.

---

## 5. Fase J — los 56 de BYMA

Ninguno resuelto, ninguno convertido en `VERIFIED`. Dossier completo en
`BYMA_BLOCKED_DOSSIER.json`.

Un dato que cambia el diagnóstico: **los 56 CUIT legacy pasan módulo 11**. Están
bien formados. El problema no es la calidad del dato — es su **procedencia**: la
única fuente que los declara es `LEGACY_DIM_ENTITY`, `CORROBORATING`, sin autor
ni cita, y que ya falló antes con el CIK de YPF.

Sin CIK no hay ancla desde la cual tender un puente a GLEIF; buscar el LEI por
razón social es lo que F-024 mostró que no se puede hacer; y la CNV es circular
(su perfil se consulta *por* CUIT). Queda AFIP —autoritativa pero con captcha— o
una decisión de producto sobre qué evidencia se acepta.

---

## 6. F-041 — el warning

7 CIK autoritativos de ciclos anteriores (`proc:sec_registry` ×6,
`proc:s03_parse` ×1) tienen `source_facts = NULL`. Los 505 del backfill los
tienen todos.

F-037 se llamó «evidencia estructurada **general**» y su materialización efectiva
fue un CHECK sobre CUIT: **el CIK nunca quedó cubierto**. No hay dato inventado —
las 7 tienen provenance completa y fuente autoritativa; falta la forma
estructurada. Corrección propuesta en `F041_HALLAZGO.md`; no aplicada porque
exige re-afirmar assertions inmutables, y esa es una decisión, no un arreglo.

---

## 7. Restricciones respetadas

Sin commits · sin inferir identidad por nombre, ticker, CIK↔LEI ni CIK↔CUIT ·
sin convertir `CORROBORATING` en `AUTHORITATIVE` · sin ratificaciones
automáticas · sin tocar `dim_entity` ni `ticker_canonico` · sin borrar
provenance · sin procesar los 56 BYMA · sin CNV ni Market masivo · sin modificar
SEC, S03 ni S04 · sin re-ejecutar M23.

**67 tests en verde** (backfill 15, F-040 14, F-032 20, F-038 13, CNV↔Identity 5).
El gate no se apoya en eso: se apoya en la auditoría independiente y en la
mutación.
