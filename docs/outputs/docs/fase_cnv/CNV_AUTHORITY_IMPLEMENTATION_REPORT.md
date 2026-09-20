# CNV_AUTHORITY_IMPLEMENTATION_REPORT

**Fecha:** 2026-09-01 · **Alcance:** C1, C2, C3, C4 · **Sin commits**
**Decisiones aplicadas:** D1 APROBADO · D2 NO TOCAR · D3 APROBADO · D4 POSTERGADO ·
D5 docstring no normativo, actualizado junto con C1

---

## 1. Qué se cambió

Un solo archivo: `scripts/engine/c3_cnv_fetch.py`. **Ninguna migración, ningún
cambio de schema, ninguna assertion tocada.**

### C1 · La elegibilidad ya no depende del estado de la assertion

**Antes:**

```sql
max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)  AS cuit_status
...
if r["cuit_status"] != "VERIFIED": bloquear
```

Sin filtrar `is_authoritative`, sin mirar `identifier.status`, y decidiendo por
el **máximo alfabético** del texto del estado. Acertaba porque `VERIFIED` es el
mayor de `{UNRESOLVED, CANDIDATE, REVIEW_REQUIRED, VERIFIED, REJECTED}` en orden
lexicográfico — una propiedad del alfabeto, no una regla.

**Ahora:**

```sql
SELECT i.id_value AS cuit, i.identifier_id, i.assertion_id, i.status, ...
  FROM identity_v1.identifier i
  LEFT JOIN identity_v1.assertion a ON a.assertion_id = i.assertion_id
 WHERE i.entity_key = :ek
   AND i.id_type = 'CUIT'
   AND i.is_authoritative
   AND i.status = 'ACTIVE'
   AND i.valid_to IS NULL
 ORDER BY i.identifier_id
```

- **0 filas** → bloqueado
- **1 fila** → elegible
- **>1 filas** → `AMBIGUO` y bloqueado, **sin desempatar**

`max(a.status::text)` fue **eliminado por completo**. La assertion se lee para la
provenance (`cuit_assertion`, `cuit_method`, `cuit_confidence`), nunca para
decidir.

### C2 · Motivo `CUIT_NO_AUTORITATIVO`

Distingue «la entidad no tiene CUIT» (`SIN_CUIT`) de «tiene CUIT pero ninguno
autoritativo». El detalle explica **por qué** —cuántos identificadores hay,
cuántos autoritativos, qué estados— usando una consulta de contexto que **no
participa de la decisión**.

### C3 · Motivo `AMBIGUO`, en dos niveles

1. el identificador resuelve a **más de una entidad**;
2. la entidad tiene **más de un CUIT autoritativo vigente**.

En ambos casos se bloquea. Elegir uno sería inventar cuál manda.

### C4 · Docstring y contrato

El docstring declaraba la regla en términos de `assertion.status`, contradiciendo
la «Regla de autoridad» de `IDENTITY_ARCHITECTURE_V1`. Se reescribió con el
contrato correcto y una nota explícita de no volver a describirlo por el estado
de la assertion. `binding` pasó de `IDENTITY_V1_VERIFIED` a
`IDENTITY_V1_AUTORITATIVO`.

---

## 2. Efecto medido sobre el universo

Recalculado por la auditoría independiente, con SQL propio:

```
CUIT distintos vigentes ................. 17
  ELEGIBLES (1 autoritativo) ............  3   30546689979 · 30657862068 · 33650305499
  bloqueados por AMBIGUO ................  4   30500001735 · 30696170580 · 30714128309 · 33500005179
  bloqueados por NO AUTORITATIVO ........ 10
```

**Los 3 elegibles coinciden exactamente con los que tienen assertion `VERIFIED`.**
El cambio **no altera ningún resultado observable hoy** — que es precisamente el
argumento para hacerlo: acertar por coincidencia deja de ser suficiente cuando la
coincidencia no está garantizada.

---

## 3. Hallazgo nuevo — 4 CUIT resuelven a 3 entidades cada uno

Apareció al correr los tests: dos fallaron, y **no era error del test**.

```sql
SELECT id_value, count(DISTINCT entity_key), preferred_name
  FROM identity_v1.identifier i ... GROUP BY 1 HAVING count(DISTINCT entity_key) > 1;

 30500001735 | 3 | BANCO DE GALICIA Y BUENOS AIRES S.A.
 30696170580 | 3 | Aeropuertos Argentina 2000 S.A.
 30714128309 | 3 | YPF ENERGÍA ELÉCTRICA S.A.
 33500005179 | 3 | Banco Supervielle S.A.
```

**Entidades duplicadas en `identity_v1`**, con el mismo `preferred_name`. El
resolver las bloquea con `AMBIGUO` — correcto: se niega a elegir.

**No se corrigió.** Es de la misma familia que D2 (duplicados históricos), que
esta fase no toca. Se registra porque cambia una premisa operativa: **el universo
negativo se parte en dos motivos**, no uno, y cualquier piloto futuro debe
contemplarlo.

Los tests se ajustaron a la realidad medida, no al revés, con el motivo escrito
en el propio test.

---

## 4. Observación sobre la idempotencia

La segunda pasada con `--rerun` da `gate = PASS` y `C-C3-006` **2/2** en las tres
empresas, con el **mismo checkpoint**. Pero la huella crece:

```
ANTES    3957 artefactos | 3958 logs | 50 corridas
DESPUES  3969            | 3970      | 56
         +12               +12         +6
```

Medido en detalle:

```
cuit | kind          | filas | sha256 crudos | canonical_sha256
-----|---------------|-------|---------------|------------------
 …   | EMPRESA_PAGE  |   2   |       2       |        1
 …   | VISOR         |   2   |       2       |        1
```

**La idempotencia es semántica, no de filas.** CNV sirve bytes distintos en cada
pedido —tokens de cache-busting y anti-forgery— así que el `sha256` crudo cambia
y se inserta una fila nueva; el `canonical_sha256` es **idéntico**, y es lo que
`C-C3-006` compara.

Es comportamiento **preexistente**, no introducido por C1. Se documenta porque
importa para quien cuente filas de `cnv_artifact` como «documentos ingeridos»:
6 corridas del mismo perfil producen 12 filas con el mismo contenido canónico.

---

## 5. Lo que NO se modificó

| | |
|---|---|
| assertions históricas | intactas |
| los 30 duplicados de candidatos | intactos (D2) |
| importadores | sin tocar |
| `ck_cuit_exige_evidencia_estructurada` | sigue `NOT VALID` (D4) |
| statuses, `valid_to`, Identity histórica | sin cambios — huella `525\|574\|608` verificada |
| Market, SEC | sin ejecutar |
| RAW histórico | sin borrar; sólo artefactos nuevos del E2E autorizado |

---

## 6. Archivos

| archivo | qué |
|---|---|
| `scripts/engine/c3_cnv_fetch.py` | C1–C4 |
| `tests/test_cnv_authority.py` | T1–T8, **nuevo** |
| `scripts/engine/cnv_auth_audit.py` | auditoría independiente, **nuevo** |
| `scripts/engine/cnv_identity_bench.py` | banco adversario, actualizado a los motivos nuevos |
