# CNV_AUTHORITY_TEST_REPORT

**Fecha:** 2026-09-01 · **Alcance:** T1–T8 + adversarial + mutación + E2E +
idempotencia + auditoría independiente

---

# CNV_AUTH_GATE = **PASS_WITH_WARNINGS**

Las seis baterías dan verde. Los *warnings* son **dos hallazgos de datos**, ambos
preexistentes, ninguno introducido por este cambio y ninguno capaz de producir
una ingesta no autorizada.

---

## 1. Resumen

| # | batería | resultado |
|---|---|---|
| 1 | Unit / adversarial / mutación — `test_cnv_authority.py` | **11 passed** |
| 2 | Banco adversario de identidad — `cnv_identity_bench.py` | **15/15** |
| 3 | Mutación causal (T6) | **incluida y verde** |
| 4 | E2E CNV positivo — 3 CUIT autoritativos | **3/3 gate PASS** |
| 5 | Idempotencia — `--rerun` sobre los mismos 3 | **3/3 PASS**, `C-C3-006` 2/2 |
| 6 | Auditoría independiente — `cnv_auth_audit.py` | **16/16** |

---

## 2. T1–T8, uno por uno

| test | qué prueba | resultado |
|---|---|---|
| **T1** | autoritativo + `ACTIVE` + vigente ⇒ elegible | **PASS** — los 3, con `motivo = AUTORITATIVO` |
| **T2** | candidato no autoritativo ⇒ bloqueado | **PASS** — 14 CUIT, ninguno elegible |
| **T2b** | el corte ocurre en `load_identity`, antes de `run_scope` | **PASS** — `SystemExit` con `CUIT_NO_AUTORITATIVO` |
| **T3** | autoritativo pero `DISPUTED` ⇒ bloqueado | **PASS** — schema temporal |
| **T4** | autoritativo con `valid_to` cerrado ⇒ bloqueado | **PASS** — schema temporal |
| **T5** | dos autoritativos vigentes ⇒ la consulta expone la ambigüedad | **PASS** — devuelve 2 filas, no elige |
| **T5b** | control positivo del fixture: el caso válido **sí** es elegible | **PASS** |
| **T6** | **mutación**: quitar `is_authoritative` hace elegible a un no-autoritativo | **PASS** |
| **T7** | los cuatro invariantes estructurales | **PASS** — 0 en todos |
| **T8** | reproducción del incidente con espía: `fetch_calls == 0` | **PASS** |
| **C1** | guarda literal: si vuelve `max(a.status::text)`, cae | **PASS** |

### T3, T4 y T5 usan schema temporal — y por qué importa

Los tres estados que prueban **no existen en la base homologada**, porque son
precisamente los que sus invariantes prohíben. Crearlos ahí para poder probarlos
habría sido fabricar el defecto que se dice prevenir.

Se replican las tres tablas de `identity_v1` en un schema `cnvauth_tmp` y se
ejecuta **el SQL real del resolver**, importado del módulo con
`identity_v1.` → `cnvauth_tmp.`. Si alguien cambia la consulta, los tests cambian
de resultado: ése es el vínculo causal.

**T5b existe para que T3 y T4 no puedan pasar por accidente**: si el fixture
estuviera roto, la consulta devolvería vacío siempre y T3/T4 pasarían sin probar
nada. T5b exige que el caso válido **sí** devuelva una fila.

### T6 — la mutación identifica la garantía, no observa un fallo

```python
mutado = SQL_CUIT_AUTORITATIVO.replace("AND i.is_authoritative", "")
_ins(c, is_authoritative=False)          # un candidato, NO autoritativo

real          -> []          con la barrera, NO es elegible
con_mutacion  -> [1 fila]    sin la barrera, PASA
```

Si la mutación **no** hiciera pasar el caso, T2 estaría pasando por otra
condición —`status`, `valid_to`— y no por la que dice probar.

### T8 — el incidente, reproducido sin descargar nada

```
universo construido con la consulta VIEJA (fila por fila, a.status <> 'VERIFIED')
  -> incluye CUIT autoritativos: sí, verificado
  -> con la salvaguarda, los detenidos == exactamente los contaminados
  -> fetch_calls sobre contaminados == 0
```

El test **falla si el universo viejo deja de incluir autoritativos**, para no
quedar como un test que ya no reproduce nada.

---

## 3. Banco adversario — 15/15

```
YPF   por CUIT / por CIK   AUTORITATIVO           E01M0X99C8F87H9TH9N39H2D1NW
TGS   por CUIT / por CIK   AUTORITATIVO           E01M0X99G29RBSSFSGAM5S1QZMT
CEPU  por CUIT / por CIK   AUTORITATIVO           E01M0X99DQ7P5TQ4Z6Z58RC5PB3
GGAL  por CUIT / por CIK   CUIT_NO_AUTORITATIVO   bloqueada
CUIT inexistente           NO_ESTA_EN_IDENTITY_V1
CIK sin CUIT (AAPL)        SIN_CUIT
```

Las dos puertas de entrada —`--cuit` y `--cik`— dan la misma entidad y el mismo
CUIT en las tres empresas. GGAL corta **antes de abrir corrida**.

---

## 4. E2E positivo — 3/3

```
CIK  904851  YPF   binding=IDENTITY_V1_AUTORITATIVO  assertion 345  gate PASS
CIK  931427  TGS   binding=IDENTITY_V1_AUTORITATIVO  assertion 347  gate PASS
CIK 1717161  CEPU  binding=IDENTITY_V1_AUTORITATIVO  assertion 346  gate PASS
```

`C-C3-003` (provenance completa entidad→cuit→url→sha→raw→run→padre):
**2/2 filas persistidas, 0 incompletas, 0 sin padre** en cada una.

Las tres resolvieron por las assertions **autoritativas vigentes** (345/346/347),
no por ninguna de las 7 candidatas que cada CUIT arrastra.

---

## 5. Idempotencia — semántica, no de filas

```
CIK  904851  gate PASS  checkpoint 0e66272e…  C-C3-006  2/2
CIK  931427  gate PASS  checkpoint 93d6ae56…  C-C3-006  2/2
CIK 1717161  gate PASS  checkpoint 279e19c4…  C-C3-006  2/2
```

**Mismo checkpoint que la primera pasada.** Pero la huella crece:

```
ANTES    3957 | 3958 | 50 corridas | 0 RUNNING | 574 identifiers
DESPUES  3969 | 3970 | 56          | 0         | 574
delta     +12   +12    +6            0           0
```

Medido:

```
cuit | kind         | filas | sha256 crudos | canonical_sha256
 …   | EMPRESA_PAGE |   2   |       2       |        1
 …   | VISOR        |   2   |       2       |        1
```

CNV sirve bytes distintos en cada pedido (cache-busting / anti-forgery): el hash
crudo cambia, se inserta fila nueva, **el canónico es idéntico**. Eso es lo que
`C-C3-006` compara, y por eso pasa.

**Es comportamiento preexistente**, no efecto de C1. Se registra como *warning*:
contar filas de `cnv_artifact` como «documentos ingeridos» sobreestima.

---

## 6. Auditoría independiente — 16/16

`cnv_auth_audit.py` no importa `c3_cnv_fetch`: habla con PostgreSQL por `psql` y
reconstruye la elegibilidad con SQL propio escrito desde el contrato.

| bloque | resultado |
|---|---|
| **A** · el código no decide por `max(a.status::text)`; filtra por los tres campos | 5/5 |
| **B** · elegibilidad recalculada: 3 elegibles, y coinciden con los `VERIFIED` | 2/2 |
| **C** · los cuatro invariantes estructurales | 4/4, todos en 0 |
| **D** · todo artefacto pertenece a un CUIT hoy autoritativo; provenance completa; 0 `RUNNING` | 4/4 |
| **E** · Identity sin modificar — `525\|574\|608` | 1/1 |

**Control D1** es el más relevante: **ningún artefacto CNV existente pertenece a
un CUIT que hoy no sea autoritativo.** Incluidos los 2 del incidente.

---

## 7. Warnings

### W1 · 4 CUIT resuelven a 3 entidades cada uno

```
30500001735  BANCO DE GALICIA Y BUENOS AIRES S.A.
30696170580  Aeropuertos Argentina 2000 S.A.
30714128309  YPF ENERGÍA ELÉCTRICA S.A.
33500005179  Banco Supervielle S.A.
```

Entidades duplicadas con el mismo `preferred_name`. El resolver bloquea con
`AMBIGUO` — correcto. **No se corrigió**: familia D2.

Consecuencia operativa: el universo negativo se parte en **dos** motivos
(`AMBIGUO` 4, `CUIT_NO_AUTORITATIVO` 10), no uno.

### W2 · La idempotencia no es de filas

Ver §5. Cada rerun agrega 2 filas por perfil con contenido canónico idéntico.

---

## 8. Criterio de salida

| requisito | resultado |
|---|---|
| `max(assertion.status::text)` eliminado | **sí**, con guarda de regresión |
| Elegibilidad por `is_authoritative + ACTIVE + vigente` | **sí** |
| `>1` fila ⇒ `AMBIGUO` sin desempatar | **sí** |
| Motivos `CUIT_NO_AUTORITATIVO` y `AMBIGUO` | **sí** |
| Docstring y contrato actualizados | **sí** |
| T1–T8 verdes | **sí**, 11 passed |
| Mutación detecta la barrera correcta | **sí** (T6) |
| E2E positivo sólo sobre los 3 autoritativos | **sí**, 3/3 |
| Idempotencia | **sí**, semántica — ver W2 |
| Auditoría independiente | **sí**, 16/16 |
| Identity, Market, SEC sin modificar | **sí** |
| Piloto negativo 20 **no** ejecutado | **correcto**, no se ejecutó |
| Empresas nuevas incorporadas | **ninguna** |

---

## Dictamen

# CNV_AUTH_GATE = **PASS_WITH_WARNINGS**

El cambio hace **explícita una garantía que antes se cumplía por coincidencia
lexicográfica**. No altera ningún resultado observable —los 3 elegibles son los
mismos— y por eso el riesgo de la implementación fue mínimo; el valor está en que
ahora la regla es la del contrato y hay una mutación que lo demuestra.

**No es `PASS` limpio** por W1: cuatro CUIT del universo tienen entidades
duplicadas. No compromete la barrera —el resolver las bloquea— pero es un estado
de datos que ninguna decisión de este ciclo resolvió, y que hay que mirar antes
de cualquier piloto de escala.
