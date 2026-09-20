# PIPELINE VALIDATION SPECIFICATION

## 1. Objetivo

Establecer un mecanismo sistemático y uniforme de medición, validación, control de calidad y trazabilidad para todas las etapas del pipeline financiero de Catalaxia.

El pipeline no debe limitarse a transformar datos. Cada etapa debe demostrar que su resultado es suficientemente confiable para ser entregado a la siguiente.

Principio rector:

> **EXTRACT → TRANSFORM → MEASURE → VALIDATE → GATE → CHECKPOINT → NEXT STAGE**

El objetivo final es poder construir una foto financiera reproducible al último dato disponible y un historial mínimo de 5–6 años, pudiendo explicar de dónde proviene cada métrica, qué validaciones superó y qué limitaciones tiene.

---

## 2. Contrato común de una etapa

Toda etapa del pipeline debe implementar conceptualmente:

1. **Input** — identificar exactamente qué recibe.
2. **Process** — ejecutar la transformación.
3. **Measure** — medir cantidad, cobertura e integridad.
4. **Validate** — ejecutar controles de calidad.
5. **Report** — generar resultados legibles y estructurados.
6. **Gate** — decidir PASS, WARNING o BLOCK.
7. **Provenance** — registrar huellas y referencias.
8. **Checkpoint** — persistir un resultado reutilizable.
9. **Output** — entregar el artefacto a la siguiente etapa.

No se debe exigir que todas las etapas hagan los mismos cálculos, pero sí que utilicen el mismo contrato operacional.

---

## 3. Gates

### PASS

La etapa cumple los criterios establecidos y puede continuar.

### WARNING

Existe una anomalía o falta de cobertura que no impide continuar. El problema debe quedar registrado y afectar la certificación de los datos correspondientes.

### BLOCK

Existe un problema que compromete la integridad del resultado o impide justificarlo. La etapa no debe continuar hasta resolverlo o aceptar explícitamente una excepción documentada.

---

## 4. Dimensiones de medición

Cada etapa debe medir como mínimo:

### 4.1 Cobertura

¿Cuánto de lo esperado se obtuvo?

Ejemplo:

- expected = 73
- downloaded = 71
- coverage = 97,26%

### 4.2 Integridad

¿Los datos requeridos están completos?

Ejemplo:

- Revenue: 100%
- EBITDA: 97%
- EPS: 95%
- Dividendos: 89%

### 4.3 Consistencia

¿Los datos cumplen relaciones y reglas internas?

Ejemplos:

- Activo = Pasivo + Patrimonio.
- Fechas coherentes.
- Unidades consistentes.
- Monedas válidas.
- TTM construido con períodos compatibles.

### 4.4 Provenance

¿Podemos explicar de dónde salió cada dato?

Como mínimo debe existir:

- referencia RAW;
- referencia del hecho/input;
- transformación;
- cálculo;
- versión del código;
- identificador de corrida.

---

## 5. Reconciliación de extracción

Toda extracción debe poder seguir la cadena:

**expected → downloaded → parsed → rejected → normalized → derived → published**

El reporte de la etapa debe mostrar cantidades y diferencias.

Ejemplo:

```text
Expected:     73
Downloaded:   71
Parsed:       70
Rejected:      1
Normalized:   70
Derived:      68
Published:    68
```

Las diferencias deben poder explicarse mediante un identificador o categoría de error.

---

## 6. Checkpoints

Cada etapa debe guardar un artefacto reutilizable.

Ejemplo:

```text
RAW
  ↓ checkpoint
NORMALIZED
  ↓ checkpoint
FUNDAMENTALS
  ↓ checkpoint
MARKET DATA
  ↓ checkpoint
METRICS
  ↓ checkpoint
QUALITY
  ↓ checkpoint
SNAPSHOT
```

Si una etapa posterior cambia, no se deben repetir las etapas anteriores cuyos inputs y código no cambiaron.

Esto es obligatorio para controlar costo y tiempo de procesamiento.

---

## 7. Modos de ejecución

### FAST

Para desarrollo y ejecución incremental:

- procesa solamente cambios;
- ejecuta validaciones básicas;
- reutiliza checkpoints;
- genera reportes.

```bash
python pipeline.py run
```

### FULL

Para reconstrucción completa:

- RAW;
- normalización;
- histórico;
- fundamentals;
- precios;
- métricas;
- quality;
- snapshot.

```bash
python pipeline.py rebuild
```

### AUDIT

Para certificación profunda:

- reconstrucción desde RAW;
- reconciliaciones contables;
- provenance;
- regresión;
- benchmark externo;
- comparación con TIKR;
- validaciones profundas.

```bash
python pipeline.py audit --snapshot SNAPSHOT_ID
```

---

## 8. Validación por capa

El pipeline objetivo debe medir y validar cada capa.

| Capa | Validación principal |
|---|---|
| Universo | expected vs encontrado, duplicados |
| RAW | documentos esperados vs descargados, hashes |
| Identidad | CUIT/CIK/ticker, colisiones |
| Unidades | unidad conocida, cambios de escala |
| Moneda/FX | cobertura y trazabilidad de conversión |
| Calendario | períodos y fiscal year correctos |
| Fundamentals | cobertura histórica, períodos faltantes |
| Precios | cobertura diaria, stale data, rangos |
| Métricas | inputs completos y fórmulas reproducibles |
| Quality | anomalías y reglas de negocio |
| Benchmark | comparación independiente |
| Snapshot | reproducibilidad e inmutabilidad |
| Publicación | snapshot vs PostgreSQL |

---

## 9. Comparación con fuente externa

TIKR debe utilizarse como benchmark independiente, no como autoridad automática.

Cada comparación debe registrar:

- valor Catalaxia;
- valor TIKR;
- diferencia absoluta;
- diferencia relativa;
- fecha de cada dato;
- metodología conocida;
- estado de comparabilidad.

Estados posibles:

- MATCH
- CLOSE
- METHODOLOGY_DIFFERENCE
- DATE_DIFFERENCE
- SOURCE_DIFFERENCE
- ANOMALY
- INCOMPARABLE

Una diferencia no implica automáticamente que Catalaxia esté equivocada.

---

## 10. Regression testing

Cada corrida debe poder compararse con la anterior.

Ejemplo:

```text
Normalization coverage
Previous: 98,72%
Current:  99,64%
Delta:    +0,92 pp
```

Debe detectarse automáticamente cuando una modificación empeora:

- cobertura;
- integridad;
- cantidad de errores;
- cantidad de warnings;
- provenance;
- coincidencia con benchmarks.

Ejemplo:

```text
REGRESSION DETECTED

Previous coverage: 99,64%
Current coverage:  96,21%
Difference:        -3,43 pp

Affected:
LEDE
FIPL
CAAP
GCLA
```

---

## 11. Reporte estándar de etapa

Cada etapa debe generar un reporte con:

1. nombre y versión de etapa;
2. run_id;
3. timestamp;
4. input;
5. output;
6. expected;
7. downloaded/processed/rejected cuando corresponda;
8. cobertura;
9. integridad;
10. consistencia;
11. errores;
12. warnings;
13. anomalías;
14. provenance;
15. comparación con corrida anterior;
16. gate;
17. motivo del gate.

Ejemplo:

```text
NORMALIZATION — RUN 2026-08-23-001

INPUT
Facts recibidos: 125.430

OUTPUT
Facts normalizados: 124.981
Rechazados: 449

COBERTURA: 99,64%

VALIDACIONES
Identity: PASS
Units: PASS
Currency: PASS
Calendar: WARNING

ANOMALÍAS
Critical: 0
Warnings: 17

GATE: PASS
```

---

## 12. Quality Score

Puede existir un score agregado para facilitar la lectura, pero nunca debe ocultar los estados individuales.

Dimensiones:

- Coverage;
- Integrity;
- Consistency;
- Provenance;
- External Match.

Ejemplo:

```text
Coverage:        98,7%
Integrity:       96,2%
Consistency:     99,1%
Provenance:     100,0%
External Match:  87,0%
```

Cada métrica individual debe conservar su propio estado.

---

## 13. Certificación por métrica

El producto final debe permitir responder:

> ¿Puedo confiar en este ratio?

Ejemplo:

```text
BIIB
PER = 8,34

STATUS: CERTIFIED

INPUTS:
- Price → yfinance
- EPS → SEC XBRL
- Shares → SEC XBRL
- FX → N/A

CALCULATION:
PER = Price / EPS

PROVENANCE:
- raw_ref
- input_ref
- calculation_version
- pipeline_run

VALIDATION:
- Internal: PASS
- RAW reconciliation: PASS
- TIKR: +0,4%
- Final: CERTIFIED
```

---

## 14. Principio de eficiencia

La validación no debe reconstruir innecesariamente todo el dataset.

Por defecto:

- checks simples sobre resultados ya producidos;
- conteos;
- null checks;
- rangos;
- reconciliaciones;
- consistencia;
- comparación con resultados previos.

Las validaciones costosas se reservan para `AUDIT`.

El costo de validación debe ser pequeño frente al costo de extracción de CNV/SEC.

---

## 15. Objetivo de arquitectura

La arquitectura debe evolucionar desde múltiples scripts aislados hacia capacidades agrupadas:

```text
01_identity
02_raw
03_normalization
04_financial_model
05_market_data
06_metrics
07_quality
08_benchmark
09_snapshot
10_publish
```

Los scripts existentes no deben eliminarse automáticamente. Primero deben mapearse a estas capacidades y conservarse cualquier control que todavía sea necesario.

---

## 16. Principio de no regresión

Ninguna simplificación puede eliminar un control existente sin reemplazar explícitamente su función.

Antes de retirar una capa o script se debe demostrar:

1. qué problema resolvía;
2. qué control implementaba;
3. dónde queda implementado ese control en la arquitectura nueva;
4. qué pruebas demuestran equivalencia;
5. qué documentación queda actualizada.

---

## 17. Resultado final esperado

El pipeline debe producir:

```text
FUENTES
   ↓
RAW INMUTABLE
   ↓
NORMALIZACIÓN
   ↓
HISTORIAL 5–6 AÑOS
   ↓
FUNDAMENTALS + MARKET DATA
   ↓
13 MÉTRICAS
   ↓
MEASURE
   ↓
VALIDATE
   ↓
GATE
   ↓
BENCHMARK
   ↓
QUALITY
   ↓
SNAPSHOT INMUTABLE
   ↓
POSTGRES / API
```

La salida final no debe ser solamente una tabla de ratios.

Debe ser un dataset donde cada métrica pueda responder:

- de dónde proviene;
- qué inputs utilizó;
- qué transformación recibió;
- qué versión de código la produjo;
- qué validaciones superó;
- qué fuente independiente la contrastó;
- qué problemas tuvo;
- por qué fue certificada o no certificada.

---

## 18. Criterio de éxito

El sistema se considera exitoso cuando puede:

1. reconstruir al menos 5–6 años históricos;
2. generar la foto al último dato disponible;
3. ejecutar incrementalmente sin reprocesar innecesariamente;
4. medir cada etapa;
5. detenerse ante errores críticos;
6. continuar con warnings documentados;
7. comparar cada corrida con la anterior;
8. reutilizar checkpoints;
9. comparar las métricas contra TIKR u otra fuente independiente;
10. mantener provenance completa;
11. producir snapshots reproducibles;
12. publicar solamente datos que hayan superado los gates correspondientes.
