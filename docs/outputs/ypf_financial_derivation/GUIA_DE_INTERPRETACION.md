# Guía profesional para interpretar la matriz financiera de YPF

## Propósito de esta guía

Esta guía explica cómo leer el archivo `YPF_EDGAR_FINANCIAL_DERIVATION_MATRIX.xlsx` sin conocimientos previos de empresas, finanzas, contabilidad, datos, programación ni regulación bursátil.

El libro no es una recomendación de inversión ni un informe que diga si conviene comprar o vender YPF. Es un mapa auditable de información. Su objetivo es mostrar:

1. qué datos financieros publicó YPF ante la SEC;
2. cómo están identificados esos datos;
3. qué variables económicas pueden representar;
4. qué ratios podrían calcularse;
5. qué fórmulas alternativas existen;
6. cuáles son realmente diferentes y cuáles son la misma fórmula reescrita;
7. qué condiciones deben cumplirse para que un cálculo sea válido;
8. qué datos utiliza hoy Catalaxia y cuáles está desaprovechando;
9. de qué documento y período proviene cada dato.

La pregunta central del libro es:

> Para un ratio financiero determinado, ¿cuántas formas financieramente diferentes existen de calcularlo con la información disponible y qué evidencia requiere cada una?

---

## 1. Conceptos empresariales desde cero

### 1.1 Qué es una empresa

Una empresa es una organización que utiliza recursos para vender productos o servicios. En el caso de YPF, sus actividades incluyen exploración, producción, refinación, transporte y comercialización de energía y combustibles.

La empresa posee recursos, tiene obligaciones, genera ingresos, incurre en gastos y puede obtener ganancias o pérdidas. Esa información se resume en estados financieros.

### 1.2 Qué es una acción

Una acción representa una parte del capital de una empresa. Quien posee acciones participa económicamente en la compañía. El precio de una acción se determina en el mercado y no surge de los estados financieros.

YPF también cotiza mediante ADR en Estados Unidos. Un ADR es un certificado negociable que representa una cantidad determinada de acciones locales. Por eso no se debe combinar un precio ADR con una cantidad de acciones locales sin validar previamente la relación de conversión.

### 1.3 Qué son los estados financieros

Los estados financieros son informes estructurados sobre la situación y desempeño económico de una empresa.

Los principales son:

- **Estado de situación financiera o balance:** muestra lo que la empresa posee y debe en una fecha determinada.
- **Estado de resultados:** muestra ingresos, costos, ganancias y pérdidas durante un período.
- **Estado de flujo de efectivo:** muestra entradas y salidas de dinero durante un período.
- **Estado de cambios en el patrimonio:** explica cómo cambió el capital atribuible a los accionistas.
- **Notas:** explican políticas contables, desgloses, riesgos y detalles que no caben en los estados principales.

### 1.4 La ecuación contable básica

La relación fundamental del balance es:

```text
Activos = Pasivos + Patrimonio
```

- **Activos:** recursos controlados por la empresa, como caja, inventarios, créditos, plantas o equipos.
- **Pasivos:** obligaciones, como deudas, cuentas a pagar o impuestos.
- **Patrimonio o equity:** participación residual de los propietarios después de descontar los pasivos.

### 1.5 Stocks y flujos

Esta diferencia es indispensable para interpretar los ratios:

- Un **stock** se mide en una fecha: caja al 31 de diciembre, deuda al cierre o activos al cierre.
- Un **flujo** se mide durante un intervalo: ventas del año, utilidad del año o flujo operativo del año.

No es correcto tratar una cifra “durante el año” como si fuera una cifra “al cierre”. Para dividir un flujo por un stock, frecuentemente se utiliza el promedio entre el stock inicial y el final.

### 1.6 Conceptos financieros frecuentes

- **Revenue o ingresos:** ventas generadas por la actividad.
- **Gross Profit o ganancia bruta:** ingresos menos costos directos de lo vendido.
- **EBIT u operating income:** resultado operativo antes de intereses e impuestos.
- **EBITDA:** aproximación al resultado operativo antes de intereses, impuestos, depreciación y amortización.
- **Net Income:** resultado final después de gastos, intereses e impuestos.
- **Net Income attributable to owners:** parte del resultado atribuible a los accionistas de la controladora.
- **Cash:** efectivo y equivalentes.
- **Debt:** deuda financiera. No equivale a todos los pasivos.
- **Equity:** patrimonio.
- **CFO u OCF:** flujo de efectivo generado o consumido por operaciones.
- **CapEx:** inversiones en bienes productivos, como plantas y equipos.
- **FCF:** flujo de caja libre. Una definición frecuente es `CFO − CapEx`.
- **EPS:** ganancia por acción.
- **Market Cap:** precio por acción multiplicado por acciones; representa el valor bursátil del capital.
- **Enterprise Value:** market cap más deuda neta; aproxima el valor de las operaciones financiadas por accionistas y acreedores.

### 1.7 Qué es un ratio

Un ratio es una relación entre dos o más magnitudes. Ayuda a comparar empresas, períodos o aspectos financieros.

Ejemplos:

```text
Margen neto = Resultado neto / Ingresos
ROE = Resultado atribuible / Patrimonio promedio
Debt/EBITDA = Deuda financiera / EBITDA
P/E = Precio / Ganancia por acción
```

Una fórmula puede ser correcta matemáticamente y, aun así, ser incorrecta financieramente. Esto ocurre si mezcla monedas, períodos, empresas, perímetros o clases de acciones incompatibles.

---

## 2. De dónde provienen los datos

### 2.1 SEC y EDGAR

La SEC es el regulador del mercado de capitales de Estados Unidos. EDGAR es su sistema público de presentaciones corporativas.

YPF presenta ante EDGAR reportes regulatorios. La matriz analiza principalmente reportes anuales `20-F`, utilizados por determinados emisores extranjeros.

### 2.2 Filing

Un filing es una presentación formal ante la SEC. No es un único número ni necesariamente un solo archivo. Puede contener:

- documento HTML principal;
- estados financieros etiquetados;
- archivos XBRL;
- esquema de conceptos;
- relaciones entre conceptos;
- anexos y documentos auxiliares.

### 2.3 CIK y accession number

- **CIK:** identificador estable de la empresa en la SEC. YPF utiliza `0000904851`.
- **Accession number:** identificador único de una presentación. Cada filing tiene uno diferente.

El CIK responde “¿qué empresa es?”. El accession responde “¿qué presentación específica es?”.

### 2.4 XBRL e iXBRL

XBRL es un lenguaje que etiqueta cada dato financiero. En lugar de guardar solamente “10.000”, permite expresar:

```text
Concepto: Revenue
Valor: 10.000
Moneda: ARS
Período: 2025-01-01 a 2025-12-31
Empresa: YPF
Perímetro: consolidado
Documento: accession determinado
```

iXBRL incorpora esas etiquetas dentro de una página HTML que también puede leer una persona.

### 2.5 Company Facts

Company Facts es una API de la SEC que reúne datos XBRL por empresa, concepto, unidad y período. Facilita analizar series históricas, pero no contiene necesariamente todo lo que aparece en el filing.

La matriz compara Company Facts con los archivos XBRL reales porque:

- algunos conceptos custom pueden aparecer solamente en el filing;
- los desgloses por segmentos pueden depender de dimensiones;
- Company Facts no conserva toda la estructura de presentación y relaciones;
- un dato agregado puede ser útil desde Company Facts, mientras su explicación detallada requiere el filing.

### 2.6 RAW, parsed, normalized y derived

- **RAW:** archivo original descargado. Es la evidencia primaria.
- **PARSED:** contenido leído y separado en facts, contextos, unidades y relaciones.
- **NORMALIZED:** conceptos traducidos a un contrato común entre empresas.
- **DERIVED:** cálculos producidos a partir de datos anteriores.

Un resultado derivado solo es confiable si puede rastrearse hasta sus fuentes RAW.

### 2.7 Provenance y lineage

- **Provenance:** información que identifica la fuente exacta de un dato.
- **Lineage:** recorrido completo desde un ratio hasta cada dato que intervino en la fórmula.

Ejemplo:

```text
P/E
└── método M...
    ├── precio de mercado
    └── EPS
        └── QName XBRL
            └── contexto
                └── archivo
                    └── accession y SHA256
```

---

## 3. Cómo está organizado el archivo

El libro contiene 14 hojas. Los números indican la función lógica de cada hoja, aunque `12_SUMMARY` aparece primero para facilitar la lectura ejecutiva.

### Orden recomendado para un gerente

1. `12_SUMMARY`: entender el alcance general.
2. `09_13_CATALAXIA_RATIOS`: revisar los indicadores actuales.
3. `04_RATIO_CATALOG`: conocer las métricas investigadas.
4. `05_RATIO_METHODS`: estudiar las fórmulas disponibles.
5. `07_COVERAGE` y `08_VALIDITY`: verificar disponibilidad y condiciones.
6. `03_FINANCIAL_VARIABLES`: entender qué tags representan cada variable.
7. `06_METHOD_TAG_MAPPING`: ver qué tags necesita cada fórmula.
8. `11_PROVENANCE`: llegar hasta el dato y documento exactos.
9. `10_EXTRACTOR_GAPS`: detectar oportunidades del extractor.
10. Las demás hojas sirven para auditoría técnica e histórica.

---

## 4. Cómo interpretar cada hoja

## 4.1 Hoja `12_SUMMARY`

### Para qué sirve

Es la portada ejecutiva. Resume el tamaño del análisis, su alcance, advertencias y principales oportunidades.

### Indicadores principales

- **Tags únicos:** conceptos XBRL diferentes identificados.
- **Variables financieras:** conceptos económicos agrupados, como Revenue, Debt o Cash.
- **Ratios/métricas:** indicadores investigados.
- **Métodos totales:** fórmulas o rutas registradas.
- **Métodos distintos:** rutas financieramente diferentes.
- **Equivalencias algebraicas:** fórmulas reescritas que no constituyen métodos independientes.
- **Disponibles EDGAR-only:** métodos cuyos insumos fundamentales aparecen en EDGAR, sujetos a validaciones.
- **RAW-only:** conceptos encontrados en el filing pero no adecuadamente representados en Company Facts.

### Cómo leerla correctamente

Un número elevado de tags no significa que todos sean útiles para ratios. Muchos corresponden a notas, desgloses, miembros dimensionales o conceptos históricos. La cifra importante no es solamente cuántos datos existen, sino cuántos pueden mapearse con seguridad a variables económicas.

---

## 4.2 Hoja `01_TAG_UNIVERSE`

### Para qué sirve

Es el inventario maestro de conceptos XBRL encontrados para YPF. Una fila representa un QName, no una cifra individual.

### Definición de todas las columnas

- **qname:** identificador completo del concepto, como `ifrs-full:Revenue`.
- **taxonomy:** vocabulario contable, por ejemplo IFRS, US-GAAP, DEI o extensión YPF.
- **namespace:** URI que identifica taxonomía y versión de forma inequívoca.
- **tag:** nombre local del concepto sin prefijo.
- **n_obs_filing:** cantidad de facts observados en los filings XBRL.
- **n_contextos:** cantidad de contextos diferentes donde aparece.
- **n_dims_max:** máximo de dimensiones asociadas simultáneamente a una observación.
- **unidades:** unidades encontradas para el concepto.
- **primera_fecha:** primera fecha económica observada en filings.
- **ultima_fecha:** última fecha económica observada en filings.
- **filings:** accessions donde aparece el concepto.
- **n_filings:** cantidad de filings diferentes donde aparece.
- **con_dim_obs:** cantidad de observaciones dimensionales o indicador de su presencia.
- **fact_kinds:** clase de fact, como numérico XBRL o iXBRL.
- **n_nonnumeric:** cantidad de facts no numéricos asociados.
- **n_obs_companyfacts:** cantidad de observaciones en Company Facts.
- **cf_primera:** primera fecha encontrada en Company Facts.
- **cf_ultima:** última fecha encontrada en Company Facts.
- **cf_forms:** formularios SEC asociados en Company Facts.
- **xsd_type:** tipo de dato definido en el esquema.
- **xsd_balance:** naturaleza débito/crédito, cuando corresponde.
- **xsd_period_type:** `instant` o `duration`.
- **abstract:** indica si el concepto es solo un encabezado estructural y no admite un valor.
- **substitution_group:** familia técnica XBRL a la que pertenece.
- **custom_o_standard:** indica si es estándar o creado por YPF.
- **label:** nombre legible obtenido del filing.
- **description:** documentación explicativa del concepto.
- **cf_label:** nombre provisto por Company Facts.
- **cf_description:** descripción provista por Company Facts.
- **n_empresas:** cantidad de empresas dentro del alcance del dataset; en este piloto normalmente se refiere a YPF.
- **n_obs_total:** suma de observaciones inventariadas entre fuentes. No representa necesariamente facts económicos únicos.
- **en_filings_xbrl:** indica si se encontró en los filings XBRL.
- **n_obs_filling_placeholder:** campo técnico histórico. No debe utilizarse como indicador financiero; conserva compatibilidad con el proceso de inventario.
- **fuente_presencia:** señala si el concepto aparece en filing, Company Facts o ambas fuentes.

### Preguntas que responde

- ¿Existe `ifrs-full:Revenue` para YPF?
- ¿Es estándar o custom?
- ¿Desde cuándo aparece?
- ¿Se encuentra en Company Facts, en filings o en ambos?
- ¿Tiene observaciones dimensionales?

### Error frecuente

No interpretar cada tag como una variable distinta. `ifrs-full:Revenue`, un concepto custom de ventas y un desglose de ventas pueden relacionarse con ingresos, pero no son automáticamente intercambiables.

---

## 4.3 Hoja `02_TAG_HISTORY`

### Para qué sirve

Resume la continuidad histórica de cada QName.

### Columnas

- **qname:** concepto analizado.
- **primer_anio:** primer año económico con datos.
- **ultimo_anio:** último año económico con datos.
- **anios_con_datos:** cantidad de años observados.
- **anios_lista:** lista explícita de años disponibles.
- **gaps_internos:** años faltantes entre el primero y el último.
- **tiene_gaps:** indica si existen huecos internos.
- **cambio_unidad_entre_anios:** advierte que la unidad no fue estable.
- **detalle_unidad_por_anio:** unidad observada en cada año.
- **n_observaciones:** cantidad total de observaciones históricas.
- **anios_en_companyfacts:** años que aparecen específicamente en Company Facts.

### Interpretación gerencial

Un concepto con datos entre 2018 y 2025 no necesariamente tiene ocho años continuos. Debe revisarse `anios_lista` y `gaps_internos`. Para calcular crecimiento a cinco años, se necesitan puntos comparables, no solamente un primer y último año cualquiera.

---

## 4.4 Hoja `03_FINANCIAL_VARIABLES`

### Para qué sirve

Traduce lenguaje XBRL a lenguaje económico. Es el puente entre tags técnicos y conceptos comprensibles.

### Columnas

- **economic_variable:** variable financiera, como Revenue, Debt o Cash.
- **candidate_tag:** QName que podría representar la variable.
- **preferred:** indica el candidato seleccionado como primera opción.
- **fallback_rank:** prioridad del candidato alternativo.
- **available_ypf:** confirma si el tag fue observado para YPF.
- **taxonomy:** vocabulario del candidato.
- **label:** nombre legible del tag.
- **unit:** unidad observada.
- **period_type:** instant o duration.
- **coverage_start:** inicio de cobertura histórica.
- **coverage_end:** fin de cobertura histórica.
- **gaps:** períodos internos faltantes.
- **source_presence:** filing, Company Facts o ambos.
- **extractor_class:** situación del tag frente al extractor actual.
- **selection_reason:** justificación de preferencia o fallback.

### Cómo interpretarla

Busque la variable económica y después revise:

1. si existe un candidato preferred;
2. si está disponible para YPF;
3. qué período y unidad posee;
4. qué fallbacks existen;
5. por qué se eligió ese orden.

`preferred = TRUE` no significa “usar siempre”. Significa “primera opción cuando el contexto, período, moneda y perímetro también sean compatibles”.

---

## 4.5 Hoja `04_RATIO_CATALOG`

### Para qué sirve

Es el índice de ratios y métricas investigados.

### Columnas

- **ratio:** nombre del indicador.
- **category:** familia, como valuación, rentabilidad, liquidez o crecimiento.
- **method_count:** cantidad total de rutas registradas.
- **distinct_methods:** cantidad de métodos financieramente diferentes.
- **available_methods:** cantidad de métodos disponibles usando solo EDGAR bajo las condiciones indicadas.
- **requires_yfinance:** señala que requiere precio o datos de mercado externos.
- **requires_external_estimates:** señala que necesita estimaciones de analistas u otra fuente externa.

### Ejemplo de interpretación

Si P/E muestra dos métodos y uno es algebraicamente equivalente, no significa que existan dos ideas financieras independientes. Significa que el mismo resultado puede expresarse mediante precio/EPS o market cap/resultado, siempre que los componentes sean consistentes.

---

## 4.6 Hoja `05_RATIO_METHODS`

### Para qué sirve

Es la hoja principal del libro. Cada fila representa un método para calcular un ratio o una métrica.

### Columnas de identificación

- **category:** categoría financiera.
- **ratio:** ratio o métrica objetivo.
- **method_id:** identificador único del método, como `M001`.
- **method_type:** DIRECT, RECONSTRUCTED, ALTERNATIVE o ALGEBRAIC_EQUIVALENT.

### Columnas de fórmula

- **formula:** fórmula legible.
- **formula_normalized:** fórmula estandarizada para comparación técnica.
- **variables:** lista original de variables involucradas.
- **economic_variables:** lista normalizada de variables económicas.
- **input_count:** cantidad de inputs requeridos.
- **input_1**, **input_2**, **input_3**, **input_4:** inputs principales separados para facilitar filtros.

### Columnas de requisitos

- **required_period:** períodos que deben usarse, como TTM, FY o último cierre.
- **required_unit:** unidad requerida.
- **required_currency:** condición monetaria.
- **required_perimeter:** perímetro contable necesario.

### Columnas de evaluación

- **validity:** estado de validez financiera.
- **limitations:** advertencias y condiciones.
- **recommended:** indica si es la ruta recomendada.
- **source:** EDGAR, EDGAR+yfinance o fuente externa.
- **available_ypf:** YES, NO o CONDITIONAL_EXTERNAL.
- **coverage_start:** primer período común disponible.
- **coverage_end:** último período común disponible.
- **missing_periods:** huecos históricos.
- **missing_inputs:** variables faltantes.
- **requires_yfinance:** requiere datos de mercado.
- **requires_external_estimates:** requiere proyecciones o consenso.

### Tipos de método

- **DIRECT:** el dato requerido está reportado directamente.
- **RECONSTRUCTED:** se calcula sumando o restando componentes.
- **ALTERNATIVE:** definición financiera diferente pero defendible.
- **ALGEBRAIC_EQUIVALENT:** misma lógica económica escrita de otra forma.

### Estados de validez

- **VALID:** método aceptado con las condiciones evaluadas satisfechas.
- **VALID_CONDITIONAL:** puede utilizarse solamente después de controles específicos.
- **NOT_RECOMMENDED:** posible, pero existe una alternativa conceptualmente mejor o menos riesgosa.
- **INVALID:** no representa correctamente el indicador.
- **UNRESOLVED:** falta evidencia para decidir.

### Regla de lectura

No elija un método solo porque `available_ypf` dice YES. Lea también `validity`, `limitations`, período, moneda, unidad y perímetro.

---

## 4.7 Hoja `06_METHOD_TAG_MAPPING`

### Para qué sirve

Explica qué tags concretos necesita cada variable de cada método.

### Columnas

- **ratio:** indicador objetivo.
- **method_id:** método al que pertenece el mapping.
- **economic_variable:** variable económica requerida.
- **taxonomy:** vocabulario XBRL.
- **tag:** nombre local del concepto.
- **qname:** nombre completo.
- **role:** función dentro del método, normalmente input.
- **preferred:** candidato preferido.
- **fallback:** candidato alternativo.
- **unit:** unidad esperada u observada.
- **period_type:** instant o duration.
- **source:** disponibilidad o fuente del concepto.

### Uso práctico

Filtre por `method_id`. Todas las filas resultantes forman la lista de conceptos XBRL que el método puede necesitar.

---

## 4.8 Hoja `07_COVERAGE`

### Para qué sirve

Resume si cada método puede aplicarse a YPF y durante qué período.

### Columnas

- **ratio:** indicador.
- **method_id:** método.
- **available_ypf:** disponibilidad para YPF.
- **coverage_start:** primer año común de los inputs.
- **coverage_end:** último año común.
- **missing_periods:** huecos dentro de la cobertura.
- **missing_inputs:** variables no encontradas.
- **requires_yfinance:** dependencia de mercado.
- **requires_external_estimates:** dependencia de estimaciones.

### Estados de disponibilidad

- **YES:** los inputs EDGAR fueron localizados.
- **NO:** falta al menos un input esencial.
- **CONDITIONAL_EXTERNAL:** los fundamentales pueden estar disponibles, pero falta mercado o estimación externa.

YES significa disponibilidad de insumos, no certificación automática del cálculo.

---

## 4.9 Hoja `08_VALIDITY`

### Para qué sirve

Concentra las condiciones financieras que determinan si un método es aceptable.

### Columnas

- **ratio:** indicador.
- **method_id:** método.
- **method_type:** tipo de ruta.
- **validity:** evaluación financiera.
- **required_period:** ventana temporal requerida.
- **required_unit:** unidad requerida.
- **required_currency:** moneda o compatibilidad monetaria.
- **required_perimeter:** perímetro contable.
- **limitations:** riesgos y restricciones.
- **recommended:** recomendación metodológica.

### Cómo usarla en una decisión

Antes de aprobar un método, el gerente debe exigir respuesta afirmativa a estas preguntas:

1. ¿Todos los inputs pertenecen a YPF?
2. ¿Son del mismo período o de períodos deliberadamente compatibles?
3. ¿Tienen la misma moneda o una conversión documentada?
4. ¿Las unidades son compatibles?
5. ¿El perímetro es el mismo?
6. ¿Se usa la clase de acciones correcta?
7. ¿Las limitaciones están aceptadas y documentadas?

---

## 4.10 Hoja `09_13_CATALAXIA_RATIOS`

### Para qué sirve

Compara los 13 indicadores actuales de Catalaxia con la matriz metodológica.

### Columnas

- **order:** orden de presentación actual.
- **ratio_current:** nombre mostrado actualmente.
- **definition_current:** definición o problema conceptual identificado.
- **matched_matrix_ratio:** métrica equivalente dentro de la matriz.
- **current_status:** diagnóstico del indicador actual.
- **methods_found:** cantidad de métodos relacionados.
- **recommended_method:** método recomendado.
- **recommended_formula:** fórmula aconsejada.
- **method_not_to_use:** práctica o fórmula que debe evitarse.
- **ypf_availability:** disponibilidad del método para YPF.

### Estados frecuentes

- **MARKET_ONLY:** depende de precios o rangos de mercado, no de EDGAR.
- **NEEDS_DEFINITION_FIX:** la definición actual necesita precisión o corrección.
- **REVIEW_INPUTS:** la fórmula puede ser razonable, pero deben revisarse sus inputs.

### Punto gerencial importante

Esta hoja no autoriza por sí sola a cambiar producción. Señala qué definición conviene adoptar y qué evidencia debe comprobarse antes de una migración.

---

## 4.11 Hoja `10_EXTRACTOR_GAPS`

### Para qué sirve

Compara el universo EDGAR con lo que el extractor actual captura y utiliza.

### Columnas

- **qname:** concepto XBRL.
- **taxonomy:** taxonomía.
- **tag:** nombre local.
- **label:** descripción legible.
- **fuente_presencia:** fuentes donde aparece.
- **clasificacion_vs_extractor:** relación con el extractor.
- **con_dimensiones_en_filing:** indica si aparece con desgloses dimensionales.
- **n_obs_filing:** observaciones en filing.
- **n_obs_companyfacts:** observaciones en Company Facts.
- **primera_fecha:** primera fecha disponible.
- **ultima_fecha:** última fecha disponible.

### Clasificaciones

- **YA_EXTRAIDO:** el extractor lo captura.
- **NORMALIZADO_PERO_NO_UTILIZADO:** está disponible internamente, pero no alimenta ratios.
- **EXISTE_PERO_NO_EXTRAIDO:** Company Facts o EDGAR lo ofrecen, pero el extractor no lo captura.
- **EXISTE_EN_RAW_FILING_PERO_NO_NORMALIZADO:** aparece en el filing, pero no en la capa normalizada.
- **SOLO_EN_SCHEMA_SIN_OBS:** el concepto está definido, pero no se observó un fact con valor.

Estas categorías equivalen conceptualmente a EXTRACTED_AND_USED, EXTRACTED_NOT_USED, AVAILABLE_NOT_EXTRACTED, RAW_ONLY y NOT_FOUND, con diferencias de nomenclatura histórica.

### Advertencia

Un gap no es automáticamente una oportunidad. Primero debe probarse que el concepto representa una variable útil, tiene cobertura adecuada y puede generalizarse.

---

## 4.12 Hoja `11_PROVENANCE`

### Para qué sirve

Es la evidencia de auditoría a nivel de observación. Permite identificar el origen exacto de los inputs preferidos.

### Columnas

- **qname:** concepto XBRL del fact.
- **accession_number:** filing que contiene el dato.
- **form:** formulario SEC.
- **filing_date:** fecha de presentación.
- **report_period:** cierre declarado por el filing.
- **start_date:** inicio del período para flows.
- **end_date:** fin del período para flows.
- **instant_date:** fecha puntual para stocks.
- **unit:** moneda o unidad.
- **context_id:** contexto XBRL.
- **dimensions:** ejes y miembros asociados.
- **source_document:** archivo concreto del filing.
- **source_sha256:** huella criptográfica del archivo.
- **source_url:** dirección SEC de la fuente.
- **value:** valor numérico extraído.
- **decimals:** precisión o redondeo declarado.
- **scale:** multiplicador iXBRL aplicado.

### Cómo auditar un dato

1. Obtenga el QName desde `06_METHOD_TAG_MAPPING`.
2. Filtre esta hoja por ese QName.
3. Seleccione el período requerido.
4. Revise unidad y dimensiones.
5. Confirme accession y documento.
6. Use el hash para identificar la versión exacta.

### Diferencia entre fechas

- `filing_date`: cuándo se presentó.
- `report_period`: cierre general declarado.
- `start_date` y `end_date`: intervalo económico del fact.
- `instant_date`: fecha económica puntual.

No deben tratarse como una única fecha.

---

## 4.13 Hoja `13_GENERALIZATION`

### Para qué sirve

Separa las reglas reutilizables de la evidencia específica de YPF.

### Columnas

- **Layer:** capa de arquitectura.
- **Generalizable rule:** regla aplicable a otros emisores.
- **YPF-specific evidence:** evidencia concreta obtenida del piloto.

### Interpretación

Los tags custom de YPF no se copian a otra empresa. Lo que se reutiliza es el proceso: descargar RAW, interpretar XBRL, mapear variables, validar métodos y conservar lineage.

---

## 4.14 Hoja `14_CHECKS`

### Para qué sirve

Contiene controles de integridad del libro.

### Columnas

- **Check:** control realizado.
- **Actual:** valor observado.
- **Expected:** valor esperado.
- **Difference:** diferencia calculada.
- **Tolerance:** desviación admitida.
- **Status:** OK o FAIL.
- **Notes:** explicación del control.

### Interpretación

- **OK:** el control coincide con lo esperado.
- **FAIL:** el libro no debe considerarse íntegro hasta investigar la diferencia.

Los checks verifican estructura y conteos. No sustituyen la validación financiera dato por dato.

---

## 5. Recorridos prácticos

## 5.1 Cómo saber cuántas formas existen de calcular un ratio

Ejemplo: P/E.

1. Abra `04_RATIO_CATALOG`.
2. Filtre `ratio = P/E`.
3. Observe `method_count` y `distinct_methods`.
4. Abra `05_RATIO_METHODS` y filtre `ratio = P/E`.
5. Compare `method_type`, `formula`, `validity` y `limitations`.
6. No cuente `ALGEBRAIC_EQUIVALENT` como método financieramente independiente.

## 5.2 Cómo saber qué tags necesita un método

1. Copie el `method_id` desde `05_RATIO_METHODS`.
2. Abra `06_METHOD_TAG_MAPPING`.
3. Filtre por ese `method_id`.
4. Revise cada `economic_variable`, `qname`, `preferred` y `fallback`.

## 5.3 Cómo saber si YPF tiene los datos

1. Abra `07_COVERAGE`.
2. Filtre por ratio y método.
3. Revise `available_ypf`.
4. Si es YES, revise igualmente `missing_periods`.
5. Si es CONDITIONAL_EXTERNAL, identifique la dependencia externa.
6. Confirme los tags en `03_FINANCIAL_VARIABLES`.

## 5.4 Cómo llegar al filing original

1. Identifique el método.
2. Obtenga sus QNames en `06_METHOD_TAG_MAPPING`.
3. Busque el QName y período en `11_PROVENANCE`.
4. Confirme contexto, unidad y dimensiones.
5. Abra `source_url` si necesita revisar el filing.

## 5.5 Cómo identificar datos desaprovechados

1. Abra `10_EXTRACTOR_GAPS`.
2. Filtre `EXISTE_PERO_NO_EXTRAIDO`.
3. Priorice conceptos standard, con buena cobertura y utilidad económica.
4. Revise si ya están asociados a variables en `03_FINANCIAL_VARIABLES`.
5. No implemente conceptos solo porque existen.

## 5.6 Cómo revisar los 13 ratios actuales

1. Abra `09_13_CATALAXIA_RATIOS`.
2. Busque el ratio actual.
3. Lea `current_status`.
4. Compare `recommended_formula` con `method_not_to_use`.
5. Abra el método recomendado en `05_RATIO_METHODS`.
6. Complete la validación en `08_VALIDITY` y `11_PROVENANCE`.

---

## 6. Ejemplo completo: interpretación de P/E

P/E intenta relacionar el valor de mercado de una acción con las ganancias atribuibles a esa acción.

### Ruta 1

```text
P/E = Price / EPS
```

Requiere:

- precio correspondiente al instrumento correcto;
- EPS del período correcto;
- compatibilidad entre ADR y acción local;
- ausencia de mezcla entre FY y TTM.

### Ruta 2

```text
P/E = Market Cap / Net Income attributable to owners
```

Requiere:

- market cap de la misma clase de capital;
- resultado atribuible a propietarios;
- moneda compatible;
- período de ganancias alineado con la fecha de valuación.

### Por qué pueden ser equivalentes

Si:

```text
Market Cap = Price × Shares
EPS = Net Income / Shares
```

entonces ambas expresiones pueden producir el mismo resultado. No son dos teorías financieras distintas; son controles cruzados útiles para detectar errores de escala, acciones o ADR ratio.

### Qué no debe hacerse

- usar precio ADR con EPS por acción local sin conversión;
- usar net income total cuando el market cap representa solo a propietarios;
- mezclar precio actual con una ganancia histórica sin etiquetar la fecha;
- presentar P/E forward usando solamente EDGAR;
- ocultar un resultado negativo o reemplazarlo por un valor inventado.

---

## 7. Cómo leer fórmulas y símbolos

- `/` significa dividir.
- `+` significa sumar.
- `−` significa restar.
- `average(X)` significa promedio de saldos comparables.
- `Current FY / Prior FY − 1` mide crecimiento interanual.
- `(Ending / Beginning)^(1/n) − 1` es CAGR.
- `TTM` significa últimos doce meses.
- `FY` significa ejercicio fiscal completo.
- `latest instant` significa último saldo puntual disponible.
- `same currency` significa que no pueden combinarse ARS y USD sin conversión documentada.

---

## 8. Preguntas que un gerente debe hacer antes de aprobar un ratio

### Sobre la definición

1. ¿Qué intenta medir el ratio?
2. ¿La fórmula corresponde a esa definición?
3. ¿Existe más de una definición aceptada?
4. ¿Las rutas adicionales son alternativas reales o equivalencias algebraicas?

### Sobre los datos

5. ¿Qué QNames se utilizaron?
6. ¿Son standard o custom?
7. ¿Por qué se eligieron como preferred?
8. ¿Qué fallbacks están permitidos?
9. ¿Qué períodos cubren?
10. ¿Existen gaps?

### Sobre compatibilidad

11. ¿Todos los inputs pertenecen a la misma entidad?
12. ¿Tienen el mismo perímetro?
13. ¿Las monedas y unidades son compatibles?
14. ¿Los flows corresponden al mismo intervalo?
15. ¿Los stocks corresponden a fechas apropiadas?
16. ¿Se utilizó stock promedio cuando corresponde?
17. ¿La clase de acciones y ADR ratio son correctos?

### Sobre auditoría

18. ¿Cada input tiene accession, contexto, documento y hash?
19. ¿La transformación quedó registrada?
20. ¿El estado es VALID o todavía VALID_CONDITIONAL?
21. ¿Los checks del libro están en OK?

---

## 9. Errores de interpretación que deben evitarse

1. **Confundir pasivos con deuda:** liabilities incluye muchas obligaciones que no son préstamos.
2. **Confundir disponibilidad con validez:** encontrar un tag no certifica una fórmula.
3. **Confundir tag con variable económica:** nombres parecidos no garantizan equivalencia.
4. **Mezclar consolidado e individual:** produce ratios sin significado económico.
5. **Mezclar ARS y USD:** puede alterar el resultado por órdenes de magnitud.
6. **Mezclar stocks y flows:** activos al cierre no son activos “del año”.
7. **Usar cierre en lugar de promedio sin advertencia:** puede distorsionar ROE y rotaciones.
8. **Usar acciones outstanding para EPS sin revisar:** EPS normalmente usa weighted-average shares.
9. **Ignorar ADR ratio:** puede generar errores por múltiplos enteros.
10. **Deduplicar por FY:** FY puede identificar el año del filing y no el período económico exacto.
11. **Contar equivalencias como métodos diferentes:** infla artificialmente las opciones.
12. **Asumir que SEC significa USD:** emisores extranjeros pueden reportar en moneda local.
13. **Asumir que Company Facts contiene todo:** los filings pueden aportar conceptos y dimensiones adicionales.
14. **Interpretar un custom como incorrecto:** debe evaluarse; no rechazarse automáticamente.
15. **Interpretar RAW-only como oportunidad automática:** muchos facts son desgloses no aptos para ratios consolidados.
16. **Publicar VALID_CONDITIONAL como certificado:** primero deben ejecutarse las condiciones.
17. **Usar Forward P/E sin estimaciones externas:** EDGAR no contiene consenso futuro.
18. **Corregir silenciosamente un dato:** toda corrección necesita regla, motivo y lineage.

---

## 10. Qué puede concluirse y qué no

### El libro permite concluir

- qué conceptos XBRL fueron encontrados;
- qué variables podrían representar;
- qué métodos financieros fueron considerados;
- qué inputs necesita cada método;
- qué cobertura preliminar existe;
- qué dependencias externas son necesarias;
- qué limitaciones impiden una certificación automática;
- qué conceptos no utiliza actualmente el extractor.

### El libro no permite concluir por sí solo

- que YPF está cara o barata;
- que una acción debe comprarse o venderse;
- que todos los métodos disponibles están certificados;
- que todo concepto RAW-only debe extraerse;
- que un ratio es comparable con otra empresa sin armonizar definiciones;
- que un valor encontrado es correcto sin revisar contexto, unidad y período;
- que un método forward puede calcularse solo con EDGAR.

---

## 11. Proceso profesional de aprobación

Para llevar un método desde investigación hasta producción se recomienda:

```text
1. Definir la métrica
2. Seleccionar el método financiero
3. Identificar variables económicas
4. Seleccionar preferred tags y fallbacks
5. Validar contexto, dimensiones y perímetro
6. Validar período, unidad y moneda
7. Verificar cobertura histórica
8. Reconstruir provenance por input
9. Ejecutar controles cruzados
10. Documentar excepciones
11. Aprobar la definición
12. Implementar sin modificar RAW
13. Comparar resultados pre/post
14. Certificar y monitorear
```

Una fila de la matriz es una propuesta metodológica documentada. Solo se convierte en cálculo certificado después de completar este proceso.

---

## 12. Resumen ejecutivo para el gerente

Si dispone de pocos minutos, utilice esta secuencia:

1. Mire `12_SUMMARY` para entender el alcance.
2. Abra `09_13_CATALAXIA_RATIOS` para identificar problemas actuales.
3. Busque el ratio en `04_RATIO_CATALOG`.
4. Compare métodos en `05_RATIO_METHODS`.
5. Verifique disponibilidad en `07_COVERAGE`.
6. Lea condiciones en `08_VALIDITY`.
7. Consulte tags en `06_METHOD_TAG_MAPPING`.
8. Exija evidencia en `11_PROVENANCE`.
9. Revise `14_CHECKS` antes de aceptar el libro.

La regla principal es:

> Un ratio no es confiable porque la fórmula exista o porque haya números disponibles. Es confiable cuando su definición financiera, sus inputs y su provenance son compatibles, verificables y reproducibles.

---

## 13. Documentos relacionados

- `YPF_EDGAR_FINANCIAL_DERIVATION_MATRIX.xlsx`: matriz principal.
- `REPORT.md`: informe de alcance, hallazgos, límites y glosario técnico.
- `GUIA_DE_INTERPRETACION.md`: esta guía de lectura gerencial.
