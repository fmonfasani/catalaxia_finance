# FASE A — CNV anclado en identity_v1

**Fecha:** 2026-08-31 · Evidencia: `cnv_identity_bench.json`
**Resultado: 15/15 controles · gate C3 PASS 10/10 en YPF y en TGS**

---

## 1. El blocker que apareció al validar

El encargo pide que el CUIT venga de `identity_v1`, sin joins por nombre,
ticker, legacy ni hardcode. **No era el caso.** `load_identity()` resolvía así:

1. CUIT tomado de `--cuit`, con **default `33650305499` (CEPU) hardcodeado**;
2. `entity_key` buscado en un seed CSV llamado `cnv_identity_seed_cepu.csv`;
3. si no aparecía, fallback al schema **legacy** `identity.entities`;
4. si tampoco, clave provisional `CUIT:{cuit}` y **se seguía igual**.

`identity_v1` no se consultaba en ningún punto.

### Lo que eso produjo, medido en la base

```
cuit          entity_key                     filas
30546689979   CUIT:30546689979               2437     <- YPF, clave provisional
30657862068   CUIT:30657862068                692     <- TGS, clave provisional
33650305499   CIK:0001717161                  388     <- CEPU, otro formato
99999999999   CUIT:99999999999                  1     <- CUIT inexistente
```

Tres formatos de clave distintos, **ninguno** un `entity_key` de `identity_v1`, y
una fila con un CUIT que no existe: llegó a hacer el request a CNV y lo frenó
recién la validación de contenido (`V-EXPECTED-ENTITY(HARD)`).

> Que otra barrera lo haya rechazado no prueba que la barrera de identidad
> funcione. Probaba que **no existía**.

### Lo que `identity_v1` sí sabía

```
CENTRAL PUERTO S.A.                  CIK 0001717161  CUIT 33650305499  VERIFIED
TRANSPORTADORA DE GAS DEL SUR S.A.   CIK 0000931427  CUIT 30657862068  VERIFIED
YPF SOCIEDAD ANONIMA                 CIK 0000904851  CUIT 30546689979  VERIFIED
GRUPO FINANCIERO GALICIA S.A.        CIK 0001114700  CUIT 30704962807  CANDIDATE
```

La respuesta correcta y el gate correcto estaban ahí. C3 no preguntaba.

---

## 2. La corrección

`resolver_en_identity_v1(engine, cuit, cik)` es ahora la **única** fuente de
identidad de C3:

- resuelve por CUIT **o por CIK** — entrando por CIK el CUIT se **deriva**, no se
  escribe a mano;
- **exige `assertion.status = 'VERIFIED'`** en el identificador CUIT. Un CUIT
  `CANDIDATE` bloquea aunque sea correcto;
- devuelve el `entity_key` opaco real;
- si el identificador resuelve a más de una entidad → `AMBIGUO`, no elige;
- **desapareció la clave provisional**: sin entidad, no hay corrida.

El seed C1 y `identity.entities` se siguen leyendo, pero sólo para **contrastar**:
si divergen emiten un hallazgo; si el CIK se contradice, cortan. Ninguno decide.

También se quitó el default de `--cuit`: un CUIT hardcodeado en el fetcher es
exactamente el atajo que el ciclo prohíbe.

---

## 3. Banco — 15/15

| caso | esperado | obtenido |
|---|---|---|
| YPF por CUIT / por CIK | VERIFIED | `E01M0X99C8F87H9TH9N39H2D1NW` |
| TGS por CUIT / por CIK | VERIFIED | `E01M0X99G29RBSSFSGAM5S1QZMT` |
| CEPU por CUIT / por CIK | VERIFIED | `E01M0X99DQ7P5TQ4Z6Z58RC5PB3` |
| **GGAL** por CUIT / por CIK | CUIT_NO_VERIFICADO | bloqueada |
| CUIT inexistente | NO_ESTA_EN_IDENTITY_V1 | bloqueada |
| AAPL (CIK sin CUIT) | SIN_CUIT | bloqueada |
| `--cuit` ≡ `--cik` (×3) | misma entidad, mismo CUIT | sí |
| `load_identity` con GGAL | corta antes de abrir corrida | `SystemExit` |
| `load_identity` con YPF | ULID + binding VERIFIED | sí |

`load_identity()` se llama **antes** de `run_scope`: GGAL no abre corrida, no
escribe log y no hace un solo request. Verificado: `0` filas de GGAL en
`cnv_download_log`, `0` corridas en `RUNNING`.

---

## 4. Mecanismo oficial, corrido de verdad

```
YPF  --cik 904851  --scope EEFF_PROPIO --max-visores 1
  [identity] E01M0X99C8F87H9TH9N39H2D1NW | YPF SOCIEDAD ANONIMA
             binding=IDENTITY_V1_VERIFIED | cuit=30546689979 (assertion 345, REGISTRY)
  gate = PASS   10/10

TGS  --cik 931427  --scope EEFF_PROPIO --max-visores 1
  [identity] E01M0X99G29RBSSFSGAM5S1QZMT | TRANSPORTADORA DE GAS DEL SUR S.A.
             binding=IDENTITY_V1_VERIFIED | cuit=30657862068 (assertion 347, REGISTRY)
  gate = PASS   10/10
```

Controles relevantes en ambas corridas:

- **C-C3-003** provenance completa entidad→cuit→url→sha→raw→run→padre:
  `0 incompletas, 0 sin padre`
- **C-C3-010** scope: `100 % de las descargas pertenecen al perfil del CUIT;
  0 requests a SEC/mercado/otras empresas` → **sin atribuciones cruzadas**
- **C-C3-007** identidad no inventada: reviews no cerrables intactas 3/3

**Alcance deliberadamente mínimo — 2 artefactos por empresa.** El ciclo prohíbe
descargar CNV masivamente y los perfiles ya tienen 2.437 y 692 artefactos
registrados de ciclos previos.

---

## 5. Lo que NO se hizo, y por qué

**Las 3.517 filas históricas conservan su clave provisional.** Reescribirlas para
que digan `IDENTITY_V1_VERIFIED` sería **reescribir el pasado para satisfacer un
contrato nuevo**: esas descargas ocurrieron bajo un binding provisional, y el
registro debe seguir diciéndolo.

Atenuantes medidos:

- la atribución por **CUIT** siempre fue correcta — cada artefacto está bajo el
  CUIT del perfil del que se bajó, y C-C3-010 lo confirma corrida a corrida;
- **nada río abajo consume `cnv_artifact.entity_key`** (verificado por búsqueda
  en todo el repo), así que la clave provisional no contamina ningún cálculo;
- las filas nuevas ya llevan el ULID, y las dos poblaciones se distinguen a
  simple vista.

**Queda como deuda explícita (F-053):** resolver la atribución histórica por
`cuit → identity_v1`, en una vista de sólo lectura o en una migración con
contrato, sin tocar el registro original.

---

## 6. Estado

| condición del encargo | estado |
|---|---|
| YPF y TGSU2 resuelven CUIT vía identity_v1 | **sí**, por assertion VERIFIED |
| sin joins por nombre / ticker / legacy / hardcode | **sí** |
| CEPU sigue funcionando | **sí** |
| GGAL sigue bloqueada | **sí**, y ahora antes del primer request |
| provenance correcta | **sí** — C-C3-003 en ambas corridas |
| sin atribuciones cruzadas | **sí** — C-C3-010 al 100 % |
| sin descarga masiva | **sí** — 4 artefactos en total |
| atribución histórica | **deuda F-053**, no reescrita a propósito |
