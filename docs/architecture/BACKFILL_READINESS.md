# EVALUACIÓN DE READINESS DEL BACKFILL DE IDENTITY V1

**Fecha:** 2026-08-28 (ciclo 7, fase J) · **No se ejecutó ningún backfill.**

---

## 1. La conclusión, primero

**El backfill NO es una sola operación. Son dos, y una de ellas no escala.**

| capa | universo | ¿automatizable? | por qué |
|---|---|---|---|
| **CIK** (ancla) | 512 emisores | **sí, mecánico** | `SEC_REGISTRY` es autoritativa para CIK. Es el registro que lo asigna |
| **LEI** | los que GLEIF publique | **sí, mecánico** | `GLEIF` es autoritativa para LEI |
| **CUIT** | 18 ADR argentinos | **no. 0% automático** | ninguna fuente publica el puente CIK↔LEI (G5) |
| **CUIT** de BYMA | 56 emisores | **estructuralmente bloqueado** | no tienen CIK sobre el que anclar |

Lanzar «el backfill» como una sola corrida masiva presupone que las cuatro filas
se comportan igual. No lo hacen.

## 2. El universo real

```
dim_entity          573 emisores
  sp500             499   estadounidenses -- NO necesitan CUIT
  adr                18   argentinos CON CIK
  byma_only          56   argentinos SIN CIK
  con CIK             512
  con CUIT             74
  sin CIK ni CUIT       0
```

Estado actual de `identity_v1`: **20 entidades**, 8 con CIK autoritativo, 4 con
LEI, **3 con CUIT**, 3 bridges VERIFIED, 4 bridges propuestos sin ratificar,
11 reviews OPEN, 4 entidades PROVISIONAL.

## 3. Lo que el piloto midió (y es el dato que decide)

El piloto de 4 emisores dejó el mismo evento en **4 de 4**:

```
CUIT via GLEIF -> REVIEW_REQUIRED
  "GLEIF publica CUIT <X> para el LEI <Y>, pero nada demuestra que ese LEI
   corresponda al CIK con el que la entidad está anclada"
```

No es una tasa alta de revisión. Es **100%**. Y no es un defecto del piloto: es
G5 — SEC no publica el LEI del registrante y GLEIF no publica el CIK. El puente
**no existe en ninguna fuente**, así que cada CUIT que llegue por esa vía
requiere una decisión humana, una por empresa.

Los 3 CUIT que hoy existen son exactamente las 3 ratificaciones que Federico
firmó en el ciclo 6. No hay ninguno que haya llegado solo.

## 4. Costo real de la capa CUIT

**Cola de ratificación = 18 ADR**, no 573 ni 8.000:

```
18 ADR argentinos con CIK
 -3 ya ratificados (YPF, CEPU, TGSU2)
 -1 GGAL, excluido explícitamente (GLEIF: RA999999, registeredAs = null)
 --
 14 pendientes de decisión humana
```

14 decisiones es un número tratable. **Ese es el hallazgo operativo:** el
problema que parecía masivo no lo es, porque los 499 del S&P 500 no necesitan
CUIT y los 56 de BYMA no pueden obtenerlo por esta vía.

Cada decisión requiere, como en el ciclo 6: evidencia de **ambos extremos por
separado** (submissions de SEC + registro de GLEIF), domicilio y actividad
cotejados, y motivo escrito. TGSU2 mostró que el nombre legal puede no coincidir
(`GAS TRANSPORTER OF THE SOUTH INC` vs `Transportadora de Gas del Sur S.A.`) y la
decisión se apoyó en domicilio y actividad, no en el nombre.

## 5. El bloqueo estructural: los 56 de BYMA

No tienen CIK. Entonces:

- no hay ancla autoritativa desde la que tender un puente a GLEIF;
- su CUIT viene de `LEGACY_DIM_ENTITY`, que es `CORROBORATING` — **nunca**
  llega a autoritativo (es la causa raíz de F-032, ya cerrada);
- buscar su LEI por razón social es inferencia, y F-024 ya mostró a qué lleva:
  GLEIF devuelve **dos** LEI vigentes para «Banco Macro», y elegir por domicilio
  sería inventar identidad;
- la CNV no cierra el círculo: `CNV_PORTAL` es `DISCOVERY_ONLY` y no declara el
  CUIT del emisor (sólo el del auditor, ciclo 3D) — y además su perfil **se
  consulta por CUIT**, así que usarla para obtenerlo es circular.

**Esto no se resuelve con más código.** Requiere una fuente que hoy no está
conectada (AFIP, que es autoritativa para CUIT pero tiene captcha y no es
automatizable — ciclo 3D) o una decisión de producto sobre qué evidencia se
acepta para estos 56.

Es la pregunta abierta más grande del contrato de datos, y conviene decidirla
antes del backfill, no durante.

## 6. Qué sí está listo

- **Idempotencia**: F-032 cerrada; N ejecuciones no crean entidades nuevas
  (probado con 2, 3 y 5 pasadas).
- **Anti-contaminación**: el error histórico (CUIT de CEPU atribuido a YPF) es
  estructuralmente imposible — lo rechaza `ux_identifier_autoritativo_unico`,
  verificado con objetivos reales y bajo el rol operativo, y mutado.
- **Estado vs identidad**: F-035 cerrada, dos triggers simétricos.
- **Evidencia estructurada**: F-036 y F-037 cerradas.
- **Firma humana**: ningún proceso puede firmar una decisión humana (F-016).
- **Trazabilidad de corridas**: `run_scope()` en SEC; `market_raw_runs` en
  Market (F-038 verificado en esta misma corrida).

## 7. Recomendación

**No lanzar «el backfill». Lanzar tres cosas distintas, en este orden:**

1. **Backfill de la capa CIK** sobre los 512 con CIK. Mecánico, idempotente,
   auditable, sin intervención humana. Es el que hoy se puede correr.
2. **Cola de ratificación de 14 ADR.** Un dossier por empresa, con evidencia de
   ambos extremos, para decisión humana. No automatizable por diseño.
3. **Decisión de producto sobre los 56 de BYMA** antes de escribir nada: qué
   evidencia se acepta como autoritativa para un CUIT sin CIK. Hoy la respuesta
   honesta del sistema es «ninguna disponible», y por eso quedan sin CUIT.

Lo que **no** hay que hacer es correr el backfill completo y dejar que 14 + 56
casos caigan en `REVIEW_REQUIRED` sin plan: eso produce una cola de 70 revisiones
indistinguibles entre «falta una firma» y «falta una fuente», que son problemas
de naturaleza distinta.

## 8. Lo que este ciclo agregó al riesgo conocido

F-039 mostró que **el dominio de un CHECK escrito con una sola empresa no
sobrevive a la segunda**. CEPU no tenía controlante; YPF sí, y el fetch entero
moría. Antes de un backfill de N empresas conviene asumir que hay más dominios
calibrados sobre CEPU, y que el modo de fallo es exactamente ése: una ejecución
real, no un test, encontrándolo.

Es el mismo patrón que F-026 (436 hechos descartados en silencio) y que la
primera versión del constraint de F-038. Los tres los encontró una corrida real.
