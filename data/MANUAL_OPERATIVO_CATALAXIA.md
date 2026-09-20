# MANUAL OPERATIVO DE CATALAXIA

## SEC / EDGAR · CNV · MARKET · FINANCIAL MODEL · RATIOS · PROVENANCE · CERTIFICATION

**Versión:** 1.0  
**Estado:** Manual operativo en construcción  
**Pilotos:** YPF · KO · METR

---

# 1. Objetivo

Catalaxia transforma información financiera pública en datos financieros trazables y utilizables para cálculo de ratios.

Flujo:

```text
FUENTES
├── SEC / EDGAR
├── CNV
└── MARKET
      ↓
IDENTITY
      ↓
RAW
      ↓
PARSED
      ↓
NORMALIZED
      ↓
ECONOMIC FACTS
      ↓
FINANCIAL MODEL
      ↓
RATIOS
      ↓
MARKET RATIOS
      ↓
PROVENANCE
      ↓
VALIDATION
      ↓
CERTIFICATION
      ↓
TIKR HOMOLOGATION
```

Propiedad fundamental: cada número publicado debe poder rastrearse hasta su fuente primaria.

---

# 2. Reglas operativas fundamentales

## 2.1 No tocar producción

Las pruebas deben utilizar PostgreSQL `5433` o una base aislada.

Antes de ejecutar:

```bash
echo $ENGINE_DB_PORT
echo $ENGINE_DB_NAME
```

Resultado esperado:

```text
5433
<base aislada>
```

Si aparece `5432`, detener la operación.

## 2.2 No borrar RAW

RAW es evidencia. Un problema se resuelve mediante diagnóstico, corrección y rerun, no eliminando evidencia.

## 2.3 No fabricar datos

Si falta un input financiero, devolver `NULL`/`NOT_CALCULABLE` con motivo documentado. Nunca sustituir silenciosamente por cero.

## 2.4 No mezclar perímetros

No mezclar `CONSOLIDATED` con `INDIVIDUAL`.

## 2.5 No asumir equivalencias

No asumir automáticamente:

- Liabilities = Debt
- Total Equity = Equity attributable to owners
- Weighted Average Shares = Shares Outstanding

---

# 3. Entornos y configuración

## 3.1 Engine

Variables:

```bash
ENGINE_DB_HOST
ENGINE_DB_PORT
ENGINE_DB_NAME
```

Ejemplo:

```bash
export ENGINE_DB_HOST=localhost
export ENGINE_DB_PORT=5433
export ENGINE_DB_NAME=ypfgolden
```

PowerShell:

```powershell
$env:ENGINE_DB_HOST="localhost"
$env:ENGINE_DB_PORT="5433"
$env:ENGINE_DB_NAME="ypfgolden"
```

## 3.2 Market

Market utiliza:

```bash
DB_HOST
DB_PORT
DB_NAME
```

Actualmente no utiliza `ENGINE_DB_*`.

## 3.3 Dependencias

El `requirements.txt` actual no garantiza todas las dependencias utilizadas por Engine. Entre las utilizadas aparecen:

```text
sqlalchemy
psycopg
lxml
requests
openpyxl
yfinance
pytest
```

Por ello instalar únicamente `requirements.txt` no garantiza todavía un entorno completamente reproducible.

---

# 4. Identidad

SEC utiliza `CIK`.

CNV utiliza `CUIT`.

La abstracción común es `entity_id`.

SEC:

```text
CIK:<cik>
```

CNV:

```text
CUIT:<cuit>
```

No inventar CIK para entidades CNV.

---

# 5. Identity V1

Un identificador tiene, entre otros:

```text
status
is_authoritative
valid_to
```

Para utilizar un CUIT como identidad canónica CNV debe existir:

```text
id_type = CUIT
status = ACTIVE
is_authoritative = true
valid_to IS NULL
```

y exactamente uno.

---

# 6. Pilotos

## 6.1 YPF

```text
CIK = 0000904851
Forms = 20-F / 20-F/A
```

Referencia:

```text
27 filings
67.084 parsed facts
47.930 normalized facts
```

Ratios conocidos:

```text
EPS ≈ -2,11 USD
P/B ≈ 1,836
EV/Sales ≈ 1,599
P/E = NOT_CALCULABLE
```

## 6.2 KO

```text
CIK = 0000021344
Forms = 10-K / 10-K/A
Taxonomía = US-GAAP
```

Golden Run:

```text
45.113 facts
17 XBRL filings
14 pre-XBRL filings
12.061 qnames
```

Desempate:

```text
IDENTICO       26.172
POR_PRECISION  12.746
POR_FACT_ID     3.113
UNICO           3.082
```

EPS:

```text
3,05 USD CALCULADO
```

## 6.3 METROGAS

```text
CUIT = 30657863676
entity_id = CUIT:30657863676
```

Golden Run:

```text
286 documentos censados
58 procesados
2 rechazados
2.795 canonical facts
```

---

# 7. Pipeline SEC

Secuencia:

```text
S00
 ↓
S01
 ↓
S02
 ↓
S03
 ↓
S04
 ↓
Financial Model
 ↓
Ratios
```

---

# 8. S00 — Smoke

## Objetivo

Validar condiciones iniciales y preparar la ejecución.

## Ejecución

Primero:

```bash
python <script-S00> --help
```

Luego ejecutar el comando documentado para el emisor.

## Resultado esperado

```text
PASS
exit 0
```

## Estado conocido

La primera ejecución funciona.

La segunda actualmente puede fallar por:

```text
UniqueViolation
ux_checkpoints_reuse
```

Causa: inserción incondicional de checkpoint.

Por tanto:

```text
S00 funcional:     SI
S00 idempotente:   NO
S00 certificado:   NO
```

---

# 9. S01 — Identity

## Objetivo

Resolver:

```text
CIK
 ↓
SEC identity
 ↓
identity_v1
```

Para YPF:

```text
0000904851
```

Para KO:

```text
0000021344
```

## Problema conocido

La implementación actual contiene validaciones específicas de YPF, incluyendo comparación del nombre legal con YPF SOCIEDAD ANONIMA.

Esto impide considerar S01 completamente multi-emisor.

## Backfill

Existe:

```bash
python backfill_cik.py --aplicar
```

Este paso fue necesario para KO.

Hasta generalizar S01, el backfill debe tratarse como parte explícita del procedimiento para emisores que lo necesiten.

---

# 10. S02 — RAW

## Objetivo

Obtener filings SEC y persistir sus artefactos RAW.

```text
SEC
 ↓
filings
 ↓
RAW
```

Primero:

```bash
python <script-S02> --help
```

Luego ejecutar el comando correspondiente al CIK.

## Resultado esperado

Debe existir:

```text
filing
artifact
SHA/hash
checkpoint
report
```

## Idempotencia

La primera ejecución funciona.

La segunda actualmente puede producir:

```text
UniqueViolation
```

por la problemática de checkpoints.

---

# 11. S03 — Parser

## Objetivo

Transformar:

```text
RAW
 ↓
parsed
```

preservando:

- facts
- contexts
- units
- decimals
- scale
- qnames
- namespaces
- períodos
- instant/duration
- dimensiones
- entity
- metadata

El parser no debe convertir todavía tags directamente en conceptos económicos.

## YPF

Referencia:

```text
27 filings
67.084 parsed facts
```

## KO

Referencia:

```text
31 filings
0 rechazados
17 XBRL
14 pre-XBRL
```

---

# 12. S03 — Idempotencia

S03 utiliza el patrón correcto de checkpoint y KO demostró:

```text
hash_out corrida 1
=
hash_out corrida 2
```

La prueba debe ser secuencial:

```text
RUN 1
esperar finalización
RUN 2
esperar finalización
RUN 3
```

Nunca ejecutar dos S03 concurrentes para el mismo CIK.

---

# 13. Bug `is_custom`

La implementación actual utilizaba una extracción equivalente a:

```python
tax = qn.split("#")[0].rsplit("/", 1)[-1]
```

Esto falla con:

```text
.../us-gaap/2024
.../srt/2019-01-31
.../dei/2025
```

porque devuelve:

```text
2024
2019-01-31
2025
```

en lugar de:

```text
us-gaap
srt
dei
```

## Consecuencia

Los 45.113 hechos de KO fueron clasificados como `is_custom=True`.

## Solución

S03 debe utilizar:

```text
_taxonomy_of()
```

como fuente común para determinar taxonomía.

## Regresión

Después del fix comprobar:

```text
YPF
KO
METR
```

especialmente:

```text
us-gaap
srt
dei
ifrs-full
```

---

# 14. S04 — Normalización

## Objetivo

Transformar:

```text
parsed
 ↓
normalized
```

y seleccionar el hecho económico correcto mediante las reglas de desempate.

## KO

Referencia:

```text
persistidos = 45.113
recomputados = 45.113
huella_igual = True
```

## Idempotencia

KO demostró:

```text
hash_out idéntico
huella_igual=True
```

---

# 15. Registry y multi-taxonomía

El Ratio Engine debe trabajar sobre conceptos económicos, no sobre emisores.

Ejemplos:

```text
Assets
StockholdersEquity
InventoryNet
Revenues
EarningsPerShareBasic
```

YPF resuelve mediante IFRS.

KO resuelve mediante US-GAAP.

KO demostró:

```text
20/20 conceptos del registry resueltos
```

sin crear una rama específica para KO.

---

# 16. Financial Model

El Financial Model transforma Economic Facts en series financieras utilizables.

Debe distinguir:

```text
INSTANT
DURATION
```

y:

```text
CONSOLIDATED
INDIVIDUAL
```

y preservar:

```text
FY
Quarter
YTD
TTM/LTM
```

Ejemplos:

```text
Assets → INSTANT
Revenue → DURATION
CFO → DURATION
EPS → DURATION
```

Nunca sumar un dato instantáneo como si fuera un flujo.

---

# 17. Ratio Engine

Ratios contratados actualmente:

1. P/E
2. EPS
3. P/B
4. P/S
5. ROE
6. ROA
7. D/E
8. Current Ratio
9. Quick Ratio
10. Gross Margin
11. Operating Margin
12. Net Margin
13. EV/EBITDA

Algunos todavía no están implementados o no son calculables.

---

# 18. EPS

Prioridad conceptual:

```text
EPS reportado compatible
        ↓
NI atribuible / weighted average shares
        ↓
fallback documentado
```

No sustituir automáticamente Weighted Average Shares por Shares Outstanding.

KO:

```text
EPS = 3,05 USD CALCULADO
```

---

# 19. NOT_CALCULABLE

Si falta un input:

```text
NOT_CALCULABLE
```

con un motivo explícito.

Nunca devolver `0` cuando en realidad falta el dato.

---

# 20. Dependencia Market

Actualmente `ratio_engine.py` aborta si no existe el esquema Market, incluso para ratios contables.

Durante KO fue necesario instalar el esquema Market vacío en la base aislada.

Arquitectura deseada:

```text
ACCOUNTING RATIOS
        ↓
financial facts
```

y:

```text
MARKET RATIOS
        ↓
financial facts + market
```

---

# 21. Market

Producción contiene aproximadamente:

```text
4,8 millones de precios
```

en `public` de `catalaxia`.

Market utiliza:

```text
DB_HOST
DB_PORT
DB_NAME
```

El modelo debe mantener separados:

```text
issuer
instrument
ticker
exchange
security type
currency
shares
price
date
ADR
ADR ratio
```

---

# 22. Market Cap y valoración

La homologación con TIKR mostró una buena reconciliación de Market Cap.

FY2025:

```text
P/E Catalaxia ≈ 11,09
P/E TIKR ≈ 11,10
```

y:

```text
P/B Catalaxia ≈ 1,51
P/B TIKR ≈ 1,51
```

Esto constituye evidencia favorable para la interacción:

```text
price
+
shares
+
financial fundamentals
```

pero TIKR continúa siendo benchmark, no oracle.

---

# 23. CNV

CNV utiliza CUIT y el `entity_id`:

```text
CUIT:<cuit>
```

Para METROGAS:

```text
CUIT:30657863676
```

---

# 24. CNV Golden Run

Referencia METROGAS:

```text
286 documentos censados
58 procesados
2 rechazados
2.795 canonical facts
```

La extracción preserva:

```text
period
perimeter
unit
scale
measurement date
```

---

# 25. CNV units

Ejemplos:

```text
ARS × 10^6
ARS × 10^3
ARS × 10^0
ARS/share
pure
```

La escala forma parte del significado económico.

---

# 26. CNV NIL

CNV utiliza:

```text
-
```

para NIL.

No convertir automáticamente:

```text
- → 0
```

Debe distinguirse:

```text
NIL
ZERO
MISSING
```

---

# 27. F-062 / F-063

F-062 encontró:

```text
81 tags declarados
51 reconocidos
25 no reconocidos
```

y:

```text
4.028 observaciones con valor
2.891 extraídas
1.137 perdidas
```

La causa principal fue:

```text
NO_ESTA_EN_CODIGOS
```

F-063 debe:

```text
baseline
 ↓
clasificar códigos
 ↓
agregar códigos válidos
 ↓
NIL handling
 ↓
shell validation
 ↓
60 documentos
 ↓
loss audit
 ↓
regression
 ↓
independent audit
```

No modificar Ratio Engine durante esta etapa.

---

# 28. Economic Identity

CNV debe distinguir:

```text
econ_key
```

de:

```text
fact_key
```

`econ_key` representa:

```text
entity
+
concept
+
perimeter
+
period
+
unit
+
measurement date
```

`fact_key` representa la ocurrencia documental:

```text
entity
+
accession
+
qname
+
context
+
unit
```

Esto permite representar restatements, republicaciones, comparativos e IAS 29 sin colapsar hechos diferentes.

---

# 29. Provenance

Cadena esperada:

```text
RATIO
 ↓
FORMULA
 ↓
INPUT
 ↓
ECONOMIC FACT
 ↓
OCCURRENCE
 ↓
FILING
 ↓
RAW
 ↓
FILE
 ↓
SHA256
```

KO verificó:

```text
SHA almacenado en DB
=
SHA calculado sobre archivo en disco
```

---

# 30. Prueba de provenance

Para cada muestra:

1. localizar ratio;
2. localizar fórmula;
3. localizar inputs;
4. localizar fact;
5. localizar filing;
6. localizar RAW;
7. localizar archivo;
8. calcular SHA256;
9. comparar con SHA persistido.

Resultado esperado:

```text
SHA_DB == SHA_DISK
```

---

# 31. Prueba de idempotencia

Para cada etapa:

```text
RUN 1
RUN 2
RUN 3
```

Comprobar:

```text
hash1 == hash2 == hash3
rows1 == rows2 == rows3
```

Además:

```text
duplicados = 0
foreign pointers = 0
RUNNING residuales = 0
```

---

# 32. Estado actual de idempotencia

| Etapa | Estado |
|---|---|
| S00 | NO |
| S01 | NO CERTIFICADO |
| S02 | NO |
| S03 | DEMOSTRADO en KO |
| S04 | DEMOSTRADO en KO |

---

# 33. Troubleshooting

## 33.1 `UniqueViolation ux_checkpoints_reuse`

Probablemente S00 o S02 se ejecutó por segunda vez.

No borrar el checkpoint.

Registrar:

```text
run_id
stage
database
error
```

Tratar como bug de idempotencia.

## 33.2 `C-S04-004: CIK sin entidad en identity_v1`

Verificar Identity.

Si corresponde:

```bash
python backfill_cik.py --aplicar
```

Después repetir S04.

Registrar que el flujo S01 todavía necesita generalización.

## 33.3 Todos los hechos KO aparecen como custom

Verificar `is_custom`.

Si ocurre con:

```text
us-gaap
srt
dei
```

revisar la lógica de `_taxonomy_of()`.

No modificar manualmente los datos persistidos.

## 33.4 Ratio Engine no arranca

Verificar:

```bash
echo $DB_HOST
echo $DB_PORT
echo $DB_NAME
```

y comprobar que exista el esquema Market.

## 33.5 Hay un proceso RUNNING

No iniciar otro proceso inmediatamente.

Identificar:

```text
PID
run_id
CIK
stage
```

Comprobar si sigue activo.

Si es huérfano, detenerlo controladamente y registrar el incidente.

Nunca ejecutar simultáneamente S03 para el mismo CIK.

---

# 34. Golden Run — procedimiento completo

Para cada emisor:

```text
1. Crear/seleccionar base aislada
2. Verificar puerto 5433
3. Verificar Identity
4. Ejecutar S00
5. Ejecutar S01
6. Ejecutar backfill si corresponde
7. Ejecutar S02
8. Ejecutar S03
9. Ejecutar S04
10. Ejecutar Financial Model
11. Ejecutar ratios
12. Validar provenance
13. Segunda ejecución
14. Tercera ejecución
15. Comparar hashes
16. Comparar counts
17. Validar punteros
18. Verificar RUNNING
19. Generar reporte
20. Emitir veredicto
```

---

# 35. Datos que registrar

Cada ejecución debe registrar:

```text
entity
CIK/CUIT
database
port
run_id
timestamp
filings
RAW artifacts
parsed facts
normalized facts
qnames
contexts
hash_in
hash_out
ratios
provenance
errors
warnings
```

---

# 36. Reporte Golden

Nombre:

```text
<COMPANY>_GOLDEN_RUN_REPORT.md
```

Debe contener:

```text
Identity
Environment
Input
Discovery
RAW
Parsed
Normalized
Economic Facts
Financial Model
Market
Ratios
Provenance
Idempotence
Validation
Known Limitations
Final Verdict
```

---

# 37. Estados de certificación

Utilizar:

```text
PASS
PASS_WITH_WARNINGS
BLOCKED
NOT_READY
NOT_IMPLEMENTED
KNOWN_LIMITATION
DECISION_REQUIRED
```

No utilizar PASS para ocultar warnings estructurales.

---

# 38. Estado de los tres pilotos

## YPF

```text
PASS_WITH_WARNINGS
```

Demostrado:

- Identity
- SEC discovery
- RAW
- S03
- S04
- ratios
- provenance
- gates

Pendiente:

- S00 idempotencia
- S02 idempotencia
- prueba S03 limpia en una única sesión
- cleanup formal de RUNNING
- Golden Run E2E completo

## KO

```text
PASS_WITH_WARNINGS
```

Demostrado:

- US-GAAP
- 20/20 conceptos registry
- 45.113 facts
- 17 XBRL
- 14 pre-XBRL
- EPS 3,05 USD
- S03 idempotencia
- S04 idempotencia
- provenance

Pendiente:

- S01 multi-emisor
- `is_custom`
- S00 idempotencia
- S02 idempotencia

## METR

```text
PASS_WITH_WARNINGS
```

Demostrado:

- CNV
- CUIT
- canonical entity
- units
- periods
- facts
- Golden Run parcial

Pendiente:

- F-063
- extracción completa
- PDF CapEx
- Financial Model completo
- integración completa de ratios

---

# 39. TIKR Homologation

TIKR es benchmark externo, no oracle.

Clasificar diferencias como:

```text
MATCH
CLOSE
METHODOLOGY_DIFFERENCE
DATE_DIFFERENCE
PERIMETER_DIFFERENCE
SOURCE_DIFFERENCE
ANOMALY
INCOMPARABLE
```

Nunca modificar Catalaxia sólo para hacer coincidir TIKR.

---

# 40. IAS 29

TIKR parece reexpresar comparativos de años anteriores.

La arquitectura debe distinguir:

```text
AS_REPORTED
```

de:

```text
COMPARATIVE_REEXPRESSED
```

No sobrescribir el dato original.

---

# 41. FX

Catalaxia utiliza:

```text
MEP
```

TIKR utiliza:

```text
A3500 wholesale
```

Las diferencias observadas no justifican cambiar Catalaxia automáticamente.

---

# 42. Perímetro de resultado

TIKR utiliza valores atribuibles a los propietarios.

Catalaxia debe diferenciar conceptualmente:

```text
resultado_neto
```

de:

```text
resultado_neto_controladora
```

Esto afecta especialmente:

```text
EPS
ROE
P/E
```

---

# 43. EBITDA

Cuando la fórmula externa no está demostrada:

```text
TIKR_FORMULA_UNKNOWN
```

No forzar una fórmula para conseguir coincidencia.

---

# 44. CapEx

CNV HTML presenta cash flow agregado.

El detalle de CapEx se encuentra en documentación PDF referenciada por los estados financieros.

Hasta procesar ese detalle quedan limitados:

```text
FCF
FCF Yield
EV/FCF
P/FCF
FCF/NI
CapEx/Sales
CapEx/EBITDA
```

---

# 45. Checklist operativo de cierre

## SEC

```text
[ ] S00 PASS
[ ] S01 PASS
[ ] S02 PASS
[ ] S03 PASS
[ ] S04 PASS
```

## Idempotencia

```text
[ ] S00 ×3
[ ] S01 ×3
[ ] S02 ×3
[ ] S03 ×3
[ ] S04 ×3
```

## Integridad

```text
[ ] no duplicados
[ ] no foreign pointers
[ ] no pérdida inexplicada
[ ] no RUNNING residual
```

## Provenance

```text
[ ] ratio → formula
[ ] formula → inputs
[ ] inputs → facts
[ ] facts → filing
[ ] filing → RAW
[ ] RAW → file
[ ] file → SHA256
```

## Multi-taxonomía

```text
[ ] IFRS
[ ] US-GAAP
[ ] us-gaap correctamente identificado
[ ] srt correctamente identificado
[ ] dei correctamente identificado
```

## CNV

```text
[ ] CUIT
[ ] entity_id
[ ] units
[ ] periods
[ ] NIL
[ ] F-063
```

## Market

```text
[ ] precios
[ ] shares
[ ] currency
[ ] instrument
[ ] Market Cap
```

## TIKR

```text
[ ] CapEx
[ ] FCF
[ ] segments
[ ] IAS29
[ ] perimeter
[ ] shares
[ ] EBITDA
```

---

# 46. Secuencia recomendada de trabajo

```text
1. Corregir S00
2. Corregir S02
3. Corregir is_custom
4. Generalizar S01
5. Regresión YPF
6. Regresión KO
7. F-063 METR
8. Golden Run METR
9. Separar accounting ratios de Market dependency
10. Completar provenance
11. Financial Model
12. CapEx / FCF
13. TIKR
14. Congelar Manual 1.0
```

**No cerrar el manual como certificado hasta completar las pruebas de regresión.**
