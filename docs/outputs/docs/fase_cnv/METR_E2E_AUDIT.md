# METR E2E — AUDITORÍA INDEPENDIENTE

**Auditor:** `scripts/engine/c4_auditoria_metr_e2e.py`
**Resultado:** **2.697 facts · 56 documentos · 0 fallas**

---

## 1 · Qué reconstruye por su cuenta

No importa `c4_metr_e2e`, ni `c4_cnv_adapter`, ni `c4_cnv_semantica`, ni el
motor de ratios. Tiene su propia transcripción del plan de cuentas de la CNV,
sus propias expresiones regulares y su propia implementación de las dos claves.

| pieza | cómo la obtiene |
|---|---|
| SHA-256 de cada documento | recomputado del archivo en disco |
| escala | releída de `UnidadMedida` en el HTML |
| **valor esperado** | **número impreso × escala**, comparado contra lo persistido |
| cierre de ejercicio | releído de los documentos con `PeriodoBalance = 1` |
| `period_kind` | del primer dígito del código de cuenta (1,2 = saldo · 3 = flujo) |
| unidad | del mismo código: ratios → `pure`, EPS → `ARS/shares`, resto → `ARS` |
| `measurement_date` | releída de `FechaCierre` |
| `fact_key` | rehaciendo `sha256(entity_key\|accn\|qname\|context_id\|unit)` |
| `econ_key` | con su propia serialización de los 8 campos |
| el ratio | recalculado **desde el RAW**, no desde la base |

---

## 2 · Lo que verifica, sobre los 2.697 facts

```
identidad         entity_id = CUIT:30657863676 · entity_key = el de identity_v1
hashes            56/56 documentos: sha256 recomputado == almacenado
valores           2.697/2.697 reproducen  numero_impreso × escala
period_kind       coincide con el código de cuenta en los 2.697
periodos          DURATION con inicio 01-01 derivado de los 16 anuales
                  INSTANT sin start_date
unidades          iso4217:ARS · xbrli:pure · iso4217:ARS/xbrli:shares
decimals          NULL en los 2.697 (la escala vive en unit_ref)
measurement_date  == FechaCierre del documento, en los 2.697
perimetro         declarado y conservado en el context_id
fact_key          2.697/2.697 reproducen la fórmula
econ_key          2.697/2.697 reproducen la fórmula
ocurrencias       2.697 facts = 2.697 fact_key distintas
ratio             el margen neto se reproduce desde el RAW
```

**0 fallas.**

---

## 3 · Mutaciones adversariales

Cada una corre dentro de una transacción que se revierte. La base queda intacta.

| | mutación | resultado del auditor |
|---|---|---|
| **M1** | duplicar el valor de `Revenue` | **FALLA** — "valor no reproduce el RAW" |
| **M2** | `unit_measure` → `iso4217:USD` | **FALLA** — "unidad incorrecta" |
| **M2b** | poner la escala en `decimals` (−6) | **FALLA** — "decimals no debe llevar la escala" |
| **M3** | `start_date` → 2025-10-01 | **FALLA** — "inicio de ejercicio incorrecto" |
| **M3b** | convertir un flujo en instante | **FALLA** — "period_kind incorrecto" |
| **M4** | atribuir el fact a otro emisor real | **FALLA** — "entity_key no coincide" |
| **M4b** | `entity_key` inventado | **rechazado por la clave foránea**, antes de llegar al auditor |
| **M5** | alterar `fact_key` | **FALLA** — "fact_key no reproduce la fórmula" |
| **M5b** | alterar `econ_key` | **FALLA** — "econ_key no reproduce la fórmula" |
| **M6** | alterar el SHA-256 del RAW | **FALLA** — "sha256 no coincide con el archivo" |
| **M7** | invertir numerador y denominador | **FALLA** — deja de reproducirse desde el RAW |
| **M8** | poner el valor de Q3 en el FY | **FALLA** — "valor no reproduce el RAW" |

**Ninguna mutación sigue produciendo PASS.**

M4b es un hallazgo lateral que conviene dejar escrito: la clave foránea de
`derived.fact` sobre `identity_v1.entity` rechaza un `entity_key` inexistente
**antes** de que el auditor lo vea. Es una protección más fuerte que la
auditoría, porque impide el estado en vez de detectarlo.

---

## 4 · Lo que el auditor NO verifica

- **No valida contra la realidad económica.** Que 1.217.305 millones sea el
  ingreso "verdadero" de Metrogas es lo que dice el documento; el auditor
  verifica que Catalaxia dice lo mismo que el documento, no que el documento
  tenga razón.
- **No audita los 89 documentos CNV sin RAW en disco** — fuera de METR.
- **No cubre los ratios `CNV_*` publicados por la CNV**, sólo el margen neto y
  el ROE promedio que este piloto calcula.
- **No verifica el segundo perímetro contra el primero.** INDIVIDUAL y
  CONSOLIDADO se auditan por separado, como corresponde.
