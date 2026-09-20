# F-046 — SEIS ASSERTIONS HISTÓRICAS SIN `left_ref`

**Estado: DEUDA DOCUMENTADA, NO CORREGIDA** · 2026-08-28

---

## 1. Qué son

```
assertion_id   source_id      resolved_by                          fecha        CIK
1387           SEC_REGISTRY   proc:f041_reafirmacion@c7816d47085d  2026-08-28   0001717161  Central Puerto
1388           SEC_REGISTRY   proc:f041_reafirmacion@c7816d47085d  2026-08-28   0001114700  Grupo Galicia
1389           SEC_REGISTRY   proc:f041_reafirmacion@c7816d47085d  2026-08-28   0000931427  TGS
1390           SEC_REGISTRY   proc:f041_reafirmacion@c7816d47085d  2026-08-28   0000320193  Apple
1391           SEC_REGISTRY   proc:f041_reafirmacion@c7816d47085d  2026-08-28   0000789019  Microsoft
1392           SEC_REGISTRY   proc:f041_reafirmacion@c7816d47085d  2026-08-28   0001045810  NVIDIA
```

Las 6 tienen `left_ref = NULL` y sostienen identificadores **autoritativos vigentes**.

Son las re-afirmaciones del ciclo 9 (F-041): `f041_reafirmacion.py` insertó la
assertion con SQL directo y omitió `left_ref`. **Atravesaron
`tg_fuente_autoritativa_para_el_tipo` sin ser verificadas** — el trigger hace
`RETURN NEW` cuando `left_ref IS NULL`.

## 2. Por qué no hay daño material

Las 6 declaran `source_id = 'SEC_REGISTRY'` y sostienen identificadores de tipo
`CIK`. `SEC_REGISTRY` **es** autoritativa para `CIK`. Con `left_ref` poblado
habrían pasado la verificación igual.

Verificado además que no hay incoherencia de contenido en toda la base:

```
identificadores VIGENTES ....................................... 574
  ...cuya assertion tiene left_ref NULL ........................ 6    <-- estas
  ...cuyo left_ref NO coincide con el identificador ............ 0
identificadores RETIRADOS ....................................... 9
  ...que no cumplirian el nuevo contrato ....................... 0
```

**El defecto es de procedimiento, no de contenido.**

## 3. Qué demuestra

Que F-045 no era teórico: la ruta de bypass **ya se había tomado**, por el propio
proyecto, sin intención y sin que nada lo notara — ni el escritor, ni la auditoría
independiente del ciclo 9, que sólo verificaba `source_facts`.

## 4. Por qué NO se corrigen en este ciclo

1. **`assertion.left_ref` es inmutable** (`tg_assertion_inmutable`). No hay UPDATE
   posible, y ese trigger no se toca.
2. Corregirlas exigiría **re-afirmar otra vez** las mismas 6, o sea volver a
   operar sobre F-041 — que este ciclo tiene **explícitamente prohibido tocar**.
3. El riesgo residual es **nulo** (§2).

## 5. Efecto del cierre de F-045 sobre ellas

`tg_identifier_coherente_con_assertion` es un trigger: **no revisa filas
existentes**. Las 6 quedan como están.

Y siguen siendo operables: el trigger permite explícitamente el `UPDATE` que las
retira (`valid_to IS NOT NULL → RETURN NEW`). Sin esa excepción habrían quedado
imposibles de retirar, y el mecanismo de supersede de F-041 se habría roto.

**A partir de ahora, ninguna assertion nueva puede repetirlo.**

## 6. Cierre propuesto (para un ciclo futuro, cuando F-041 sea tocable)

Re-afirmar las 6 por el mismo mecanismo del ciclo 9, esta vez con
`left_ref = 'CIK:SEC:<valor>'`. Conserva la cadena histórica, no reescribe nada, y
elimina la deuda. Requiere autorización explícita para volver sobre F-041.
