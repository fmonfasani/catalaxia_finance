# CNV PILOT 2 — validación multi-emisor

**Fecha:** 2026-09-01 · **Rol:** auditor/ingeniero independiente
**DB:** `catalaxia_engine@127.0.0.1:5433/catalaxia` · mode FAST · **prod=False**
**Sin commits. Identity, Market y SEC sin modificar.**

---

# CNV_PILOT_GATE = **PASS_WITH_WARNINGS**

14 casos ejecutados, los 4 elegibles descargaron, los 10 no elegibles **no
invocaron el fetcher ni una vez**, provenance completa en los 8 eslabones,
idempotencia semántica demostrada. Los *warnings* son **dos dimensiones que no
pude probar por falta de casos reales** y **dos hallazgos de datos preexistentes**.

---

## 1. Comandos ejecutados

```bash
# §4 · verificacion previa
python -c "from engine.config import load_settings; print(load_settings().describe())"
  -> catalaxia_engine@127.0.0.1:5433/catalaxia mode=FAST prod=False   [5433, no 5432]
docker exec … psql -c "SELECT count(*) FROM engine.schema_migrations"   -> 32
docker exec … psql -c "SELECT count(*) FROM engine.runs WHERE status='RUNNING'" -> 0

# smoke / unit
python -m pytest tests/test_cnv_authority.py tests/test_engine_cnv.py \
                 tests/test_cnv_identity_link.py -q          -> 29 passed

# piloto, dos pasadas
python scripts/engine/cnv_pilot2.py                          # SOLO LECTURA
python scripts/engine/cnv_pilot2.py --fetch --repeticiones 2 # con autorizacion
```

`--fetch` es **autorización explícita y separada**: sin él, el piloto no puede
descargar. Es la barrera que faltaba en `CNV_NEGATIVE_PILOT_20`.

---

## 2. Casos seleccionados y por qué

Ninguno inventado. El universo real de `identity_v1` son **17 CUIT distintos**;
la muestra cubre sus tres clases más los casos sin CUIT.

| cat | caso | CUIT / CIK | por qué se eligió |
|---|---|---|---|
| **A** | CEPU | 33650305499 | positivo conocido: CUIT autoritativo, entidad única |
| **B** | YPF | 30546689979 | bridge CIK→LEI→CUIT; mayor volumen (2.498 artefactos) |
| **B** | TGSU2 | 30657862068 | bridge; volumen intermedio (1.076) |
| **B\*** | YPF por CIK | 0000904851 | el mismo positivo por la **otra puerta de entrada** |
| **D** | Banco Galicia y Bs.As. | 30500001735 | AMBIGUO: el CUIT resuelve a **3 entidades** |
| **D** | Aeropuertos Argentina 2000 | 30696170580 | AMBIGUO: 3 entidades |
| **D** | YPF Energía Eléctrica | 30714128309 | AMBIGUO + **comparte nombre** con un positivo |
| **D** | Banco Supervielle | 33500005179 | AMBIGUO + coexiste con «Grupo Supervielle» aparte |
| **E** | GGAL | 30704962807 | no autoritativo, entidad única: negativo canónico |
| **E** | Telecom Argentina | 30639453738 | no autoritativo; emisor grande con ADR |
| **E** | Pampa Energy | 30526552659 | no autoritativo; nombre en inglés en `identity_v1` |
| **E** | Vista Energy | 33515950899 | no autoritativo; domicilio en México (S.A.B. de C.V.) |
| **F** | AAPL | 0000320193 | identidad válida **sin CUIT**: no puede tener perfil CNV |
| **F/J** | BMA / «Macro Bank Inc.» | 0001347426 | sin CUIT **y** nombre histórico: cubre F y J |
| **H/I** | instrumentos BUE vs ADR | — | auditado aparte: el ticker **no participa** |

### Casos que NO pude construir — se declaran, no se fabrican

**C · CUIT autoritativo por otra provenance.** **NO EXISTE.** Los 3 autoritativos
son `REGISTRY / GLEIF / proc:gleif_fetch`. Ninguno por `SEC_20F`, `AFIP` ni
`HUMAN`, que el CHECK admite pero nadie usó todavía.

**G · Identidad válida sin correspondencia CNV.** **NO EXISTE.** Los 3 elegibles
tienen perfil CNV con 2.498 / 1.076 / 395 artefactos. No hay un elegible sin
datos.

Ambos quedan **`NOT_TESTED`**, no `PASS`.

---

## 3. Tabla de resultados

| cat | caso | entidades | CUIT auth | elegibilidad | fetch | http | artefactos | prov. |
|---|---|---:|---:|---|---|---|---:|---|
| A | CEPU | 1 | 1 | **AUTORITATIVO** | sí ×2 | 200 | 395+ | completa |
| B | YPF | 1 | 1 | **AUTORITATIVO** | sí ×1 | 200 | 2.498+ | completa |
| B | TGSU2 | 1 | 1 | **AUTORITATIVO** | sí ×2 | 200 | 1.076+ | completa |
| B\* | YPF por CIK | 1 | 1 | **AUTORITATIVO** | sí ×1 | 200 | ídem | completa |
| D | Banco Galicia | **3** | 0 | AMBIGUO | **no** | — | 0 | n/a |
| D | AA2000 | **3** | 0 | AMBIGUO | **no** | — | 0 | n/a |
| D | YPF Energía El. | **3** | 0 | AMBIGUO | **no** | — | 0 | n/a |
| D | Banco Supervielle | **3** | 0 | AMBIGUO | **no** | — | 0 | n/a |
| E | GGAL | 1 | 0 | CUIT_NO_AUTORITATIVO | **no** | — | 0 | n/a |
| E | Telecom Argentina | 1 | 0 | CUIT_NO_AUTORITATIVO | **no** | — | 0 | n/a |
| E | Pampa Energy | 1 | 0 | CUIT_NO_AUTORITATIVO | **no** | — | 0 | n/a |
| E | Vista Energy | 1 | 0 | CUIT_NO_AUTORITATIVO | **no** | — | 0 | n/a |
| F | AAPL | 1 | 0 | SIN_CUIT | **no** | — | 0 | n/a |
| F/J | BMA | 1 | 0 | SIN_CUIT | **no** | — | 0 | n/a |

Detalle completo por columna en `CNV_PILOT2_MATRIX.csv`
(entity_id, LEI, `identifier.status`, `is_authoritative`, `valid_to`,
`assertion_id`, `source`, run_id, hashes).

---

## 4. Resumen cuantitativo

```
total casos ....................... 14
  FETCH ...........................  4   (3 CUIT distintos + 1 por la otra puerta)
  BLOCKED ......................... 10
    AMBIGUO .......................  4
    CUIT no autoritativo ..........  4
    sin CUIT ......................  2
  errores .........................  0
CNV con datos ......................  3 CUIT   (2.498 / 1.076 / 395 artefactos)
CNV sin datos ......................  0
provenance completa ................  4 / 4 casos FETCH
provenance incompleta ..............  0
```

**Delta de la base:**

```
                antes    después   delta
artefactos       3969      3981     +12
logs             3970      3982     +12
corridas CNV       56        62      +6
RUNNING             0         0       0
identifiers       574       574       0     <- Identity INTACTA
assertions        608       608       0     <- Identity INTACTA
```

---

## 5. Provenance — cadena completa, sin huecos

Caso CEPU, corrida `82a4a34003654fd28b6cdb83432df180`:

```
1 ENTITY       E01M0X99DQ7P5TQ4Z6Z58RC5PB3 · CENTRAL PUERTO S.A.
2 IDENTIFIER   215 · cuit 33650305499 · is_authoritative=t · status=ACTIVE
3 ASSERTION    346 · VERIFIED · REGISTRY
4 SOURCE       GLEIF · "AFIP (RA000009) registeredAs=33-65030549-9"
5 CNV REQUEST  https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/33650305499 · http 200
6 RAW ARTIFACT CUIT33650305499/empresa/dabf09428e2ba8dd.html · sha256 dabf09428e2ba8dd…
7 CANONICAL    5f44ddd02d1fe95df2ce…
8 PERSISTED    run 82a4a34003654fd28b6cdb83432df180 · 2.263.788 bytes
```

**Los 8 eslabones existen.** Ninguno se completó por inferencia.

El eslabón 4 cierra el círculo con el modelo de identidad: la evidencia cita
`RA000009`, que es exactamente uno de los dos códigos que
`ck_cuit_exige_evidencia_estructurada` admite para la rama GLEIF.

---

## 6. Idempotencia

Dos positivos (CEPU, TGSU2) ×2 corridas, más el AMBIGUO (Galicia) resuelto en
las dos pasadas del piloto.

```
cuit         | kind         | filas | raw_sha distintos | canonical distintos
30546689979  | EMPRESA_PAGE |   2   |         2         |          1
30546689979  | VISOR        |   2   |         2         |          1
30657862068  | EMPRESA_PAGE |   2   |         2         |          1
30657862068  | VISOR        |   2   |         2         |          1
33650305499  | EMPRESA_PAGE |   2   |         2         |          1
33650305499  | VISOR        |   2   |         2         |          1
```

### A · Idempotencia semántica — **SÍ**

`canonical_sha256` **idéntico** en las dos corridas de los tres perfiles. Gate
`PASS` y `C-C3-006` **2/2** en cada una. Mismo checkpoint.

### B · Identidad física del artefacto/request — **NO, y es correcto**

`sha256` crudo **distinto** en cada pedido: CNV inyecta tokens de cache-busting y
anti-forgery. Cada corrida inserta una fila nueva.

**No es fallo de idempotencia**, tal como el encargo anticipa. Es la razón por la
que existe `canonical_sha256`. Se registra como **W2**: contar filas de
`cnv_artifact` como «documentos ingeridos» sobreestima.

### El AMBIGUO

Resuelto dos veces, **misma decisión** en ambas: `AMBIGUO`, sin fetch, sin
escritura. Delta 0 en la pasada de sólo lectura.

---

## 7. Auditoría negativa

| condición | resultado |
|---|---|
| 0 CUIT autoritativos ⇒ no dispara fetch | **verificado** — 4 casos E, 2 casos F |
| >1 CUIT autoritativos ⇒ no dispara fetch | **verificado por construcción**: la consulta devuelve >1 fila y el resolver bloquea. **Sin caso real** — control 5 de la auditoría de identidad = 0. Cubierto por `test_T5` en schema temporal |
| CUIT no autoritativo ⇒ no dispara fetch | **verificado** — 4 casos |
| entidad sin CUIT ⇒ no dispara fetch | **verificado** — 2 casos |
| **¿existe algún camino que elija arbitrariamente un CUIT entre varios?** | **NO** |

### Prueba de que no hay tie-breaker

```bash
grep "max(CASE WHEN i.id_type = 'CUIT' THEN a.status::text END)" c3_cnv_fetch.py
  -> sin coincidencias   (eliminado en C1)

grep -cE '\-\-ticker|ticker_canonico|venue_ticker' c3_cnv_fetch.py
  -> 0                   (el ticker no es entrada del sistema)
```

La consulta ordena por `identifier_id` sólo para que el resultado sea
determinista al **reportar**; si devuelve más de una fila, el resolver **no toma
la primera**: devuelve `AMBIGUO`.

**Resultado medido: 10 casos no elegibles, 0 invocaciones al fetcher.**

---

## 8. Casos H / I — el ticker no participa

```
CENTRAL PUERTO   MKT:80  EQUITY/BUE  venue=CEPU   canonico=CEPU    ratio -
CENTRAL PUERTO   MKT:81  ADR/NYSE    venue=CEPU   canonico=CEPU    ratio 10:1
TGS              MKT:65  EQUITY/BUE  venue=TGSU2  canonico=TGSU2   ratio -
TGS              MKT:66  ADR/NYSE    venue=TGS    canonico=TGSU2   ratio 5:1   <- difieren
YPF              MKT:83  EQUITY/BUE  venue=YPFD   canonico=YPFD    ratio -
YPF              MKT:84  ADR/NYSE    venue=YPF    canonico=YPFD    ratio 1:1   <- difieren
```

**H** (BYMA/ticker local) e **I** (ADR con ticker distinto) están presentes en los
datos: el ADR de TGS cotiza `TGS` mientras el canónico es `TGSU2`, y el de YPF
`YPF` vs `YPFD`.

**Y no pueden afectar la elegibilidad**, porque el fetcher tiene **cero
ocurrencias** de `ticker`. No es que el ticker se ignore: es que no es una
entrada del sistema.

---

## 9. Fallas reales

**Ninguna.** No se encontró ningún bug en esta corrida.

---

## 10. Warnings

### W1 · 4 CUIT resuelven a 3 entidades cada uno

```
30500001735  BANCO DE GALICIA Y BUENOS AIRES S.A.
30696170580  Aeropuertos Argentina 2000 S.A.
30714128309  YPF ENERGÍA ELÉCTRICA S.A.
33500005179  Banco Supervielle S.A.
```

Entidades duplicadas con el mismo `preferred_name`. El resolver bloquea con
`AMBIGUO` — correcto. **Preexistente**, familia D2, no corregido.

Consecuencia: 4 de 17 CUIT del universo son **inelegibles por duplicación de
entidad**, no por falta de ratificación. Sin resolverlo, ratificar sus CUIT no
alcanzaría para habilitarlos.

### W2 · La idempotencia no es de filas

Ver §6.B. Preexistente. Cada rerun agrega 2 filas por perfil con contenido
canónico idéntico.

### W3 · Cobertura del universo: 3 de 17

Sólo el 17,6 % de los CUIT conocidos es elegible. **No es defecto del pipeline**:
es el ritmo de ratificación, gobernado por el modelo de identidad.

---

## 11. Cuestiones que NO son bugs

| | por qué |
|---|---|
| `sha256` crudo distinto en cada fetch | tokens anti-forgery de CNV; `canonical_sha256` es estable |
| 4 CUIT bloqueados por `AMBIGUO` | el resolver se niega a elegir: es el comportamiento correcto |
| 10 CUIT no autoritativos | requieren ratificación, que es decisión humana por diseño |
| AAPL y BMA sin CUIT | emisores no argentinos / sin CUIT publicado por GLEIF |
| Los 3 autoritativos vienen todos de GLEIF | es una de las 4 fuentes que el CHECK admite |
| El seed C1 declara otro `entity_key` para CEPU | hallazgo informativo; manda `identity_v1` |

---

## 12. Homologación por dimensión

| dimensión | estado | evidencia |
|---|---|---|
| **CNV_INFRASTRUCTURE** | **PASS** | 5433 verificado, 32 migraciones, 0 RUNNING, entrypoint oficial, 29 tests |
| **CNV_IDENTITY** | **PASS_WITH_WARNINGS** | resolución correcta en 14/14; W1: 4 CUIT con entidades duplicadas |
| **CNV_ELIGIBILITY** | **PASS** | contrato exacto de §2; 0 tie-breakers; 10 bloqueos correctos, 0 fetch |
| **CNV_FETCH** | **PASS** | 6 corridas, http 200, gate PASS, 0 errores |
| **CNV_PERSISTENCE** | **PASS_WITH_WARNINGS** | 12 artefactos con provenance completa; W2: crecimiento de filas |
| **CNV_PROVENANCE** | **PASS** | 8/8 eslabones demostrados, sin inferencia |
| **CNV_IDEMPOTENCY** | **PASS** | semántica demostrada; física correctamente distinguida |
| **CNV_COVERAGE** | **PASS_WITH_WARNINGS** | 3 de 17 CUIT elegibles (17,6 %); W3 |
| **CNV_PROVENANCE_ALT** (categoría C) | **NOT_TESTED** | no existe ningún CUIT autoritativo por SEC_20F/AFIP/HUMAN |
| **CNV_SIN_DATOS** (categoría G) | **NOT_TESTED** | no existe un elegible sin perfil CNV |

---

## Dictamen

# CNV_PILOT_GATE = **PASS_WITH_WARNINGS**

**Lo que la evidencia demuestra:** el pipeline CNV funciona como mecanismo
general. La elegibilidad sigue exactamente el contrato aprobado, no hay ningún
camino que elija arbitrariamente entre varios CUIT, los 10 casos no elegibles no
llegaron al fetcher, y la cadena de provenance cierra en sus 8 eslabones con la
evidencia de GLEIF citando el código de registro que el CHECK exige.

**Por qué no es PASS limpio:**

1. **W1** — 4 de 17 CUIT tienen entidades duplicadas. No compromete la barrera,
   pero significa que ratificarlos no bastaría para habilitarlos: primero hay que
   resolver la duplicación.
2. **Dos dimensiones `NOT_TESTED`** por ausencia de casos reales (C y G). No se
   fabricaron, y no se cuentan como PASS.
3. **W3** — la cobertura es del 17,6 %, y el límite no es técnico.

**Lo que este piloto sí cierra**, y el anterior no pudo: que CNV **no es un caso
especial de CEPU/YPF/TGSU2**. Las 4 empresas AMBIGUAS y las 4 no autoritativas
fueron bloqueadas por la misma regla, sin una sola línea que las nombre.
