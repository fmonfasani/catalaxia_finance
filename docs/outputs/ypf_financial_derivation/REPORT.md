# YPF EDGAR Financial Derivation Matrix

## Alcance

Se analizaron los 16 filings 20-F inventariados de YPF (CIK `0000904851`), Company Facts y los XBRL/iXBRL reales disponibles en el cache RAW. Nueve filings FY2017–FY2025 contienen XBRL procesable, con comparativos desde 2015. Se preservaron accession, contexto, dimensiones, unidad, período, documento y SHA256; no se modificó producción ni `run_all.py`.

## Resultado cuantitativo

- 3,019 tags únicos: 555 standard y 2,464 custom YPF.
- 46,111 facts numéricos, 5,390 observaciones Company Facts y 61,847 relaciones XBRL.
- 40 variables financieras conceptuales.
- 82 ratios/métricas, 92 métodos totales, 88 financieramente distintos y 4 equivalencias algebraicas.
- 66 rutas disponibles solo con EDGAR bajo validaciones de compatibilidad.
- 289 conceptos disponibles en Company Facts no pedidos por el extractor; 1441 conceptos RAW-only. No todos son económicamente útiles.

## Hallazgos principales

1. El extractor actual tiene un gap estructural IFRS: busca nombres US-GAAP y para YPF solo encuentra 4 de 32 métricas solicitadas.
2. `liabilities` no es deuda financiera. No debe usarse como numerador de Debt/Equity o Debt/EBITDA.
3. Para ratios del accionista corresponde priorizar beneficio y equity atribuibles a propietarios, no totales con NCI.
4. ROE y ROA deben usar stocks promedio; cierre es un fallback condicional.
5. EBITDA reconstruido exige EBIT y D&A compatibles en período y perímetro.
6. CapEx no puede sustituirse silenciosamente por flujo total de inversión.
7. Company Facts no reemplaza al filing: los desgloses dimensionales y custom requieren instance/iXBRL + XSD/linkbases.
8. P/E por precio/EPS y MarketCap/NI son equivalentes solo si share class, ADR ratio, período y perímetro empatan.
9. Forward P/E y métricas de consenso no son EDGAR-only; requieren estimaciones externas.
10. Precio, market cap y rangos 52 semanas requieren mercado externo; quedan separados de fundamentales EDGAR.
11. El FCF heredado debe explicitar si usa CFO−CapEx o CFO+CFI; no son definiciones intercambiables.
12. FCFonCE debe fijar una definición única de capital empleado; FCF/market cap es FCF yield, no FCFonCE.
13. EPS directo es preferible cuando la clase/ADR coincide; NI/shares es reconstrucción y control cruzado.
14. Payout exige dividendos y NI del mismo período, base cash vs declared explícita y beneficio atribuible correcto.
15. Las equivalencias algebraicas deben almacenarse como relaciones entre métodos para evitar inflar el conteo.

## Incidencia y límite de completitud

El agregador inicial falló porque el CSV de relaciones tomaba las columnas de la primera fila y descartaba silenciosamente `label_role`, `lang` y `label_text`. La corrección quedó documentada y limitada al parser del piloto; después se reejecutaron las nueve instancias. Los filings 2010–2016 no ofrecen XBRL procesable dentro del material descargado, por lo que el universo exhaustivo de tags de filing cubre FY2017–FY2025, no toda la historia de 20-F. Las rutas `VALID_CONDITIONAL` no deben publicarse como certificadas hasta ejecutar controles dato-a-dato de período, moneda, unidad, perímetro y dimensiones.

## Generalización

La arquitectura separa RAW → QName → variable económica → método → ratio y puede reutilizarse para otros emisores IFRS y US-GAAP. La selección de QName permanece por emisor/taxonomía, mientras las variables, métodos, reglas dimensionales y validaciones son generalizables.

## Glosario: qué significa cada elemento del análisis

### SEC EDGAR y documentos

**SEC:** Securities and Exchange Commission, el regulador del mercado de valores de Estados Unidos.

**EDGAR:** sistema público de la SEC donde las compañías presentan sus estados financieros, reportes y demás documentos regulatorios. EDGAR es la fuente; XBRL es uno de los formatos contenidos en sus presentaciones.

**Filing:** presentación formal realizada por una compañía ante la SEC. Un filing no es solamente un PDF o una página: es un expediente compuesto por un documento principal y distintos archivos auxiliares. En este informe se utiliza *filing*; “filling” es una escritura incorrecta del término.

**Form 20-F:** reporte anual que presentan ante la SEC determinados emisores extranjeros, como YPF. Es comparable en función a un 10-K estadounidense, aunque responde a requisitos específicos para foreign private issuers.

**Accession number:** identificador único que EDGAR asigna a cada filing. Por ejemplo, `0001193125-25-067155`. Permite localizar inequívocamente la presentación, su directorio y todos sus archivos. No identifica a la empresa ni al período contable: identifica al acto de presentación.

**CIK:** Central Index Key. Identidad numérica estable de una entidad dentro de SEC EDGAR. El CIK de YPF es `0000904851`. El ticker puede cambiar o reutilizarse; el CIK es la clave de identidad utilizada por este análisis.

**Filing date:** fecha en la que el filing fue presentado ante la SEC. No debe confundirse con el cierre del estado financiero.

**Report period:** fecha de cierre del período informado por el filing. Un 20-F presentado en 2026 puede corresponder al ejercicio terminado el 31 de diciembre de 2025.

**Form:** tipo regulatorio del filing, por ejemplo `20-F`, `6-K`, `10-K` o `10-Q`.

**Filing index/directory:** índice y directorio de archivos de un accession. Permiten identificar el documento principal, instancia XBRL, esquemas, linkbases, imágenes y anexos realmente presentados.

**Primary document:** documento principal declarado en el filing. Puede ser HTML tradicional o iXBRL.

**Company submissions:** JSON de EDGAR con metadata de la compañía y su historial de presentaciones. Sirve para identificar accessions, formularios, fechas y documentos; no es la fuente de los importes financieros.

**Company Facts:** API de SEC que agrupa facts XBRL de una compañía por taxonomía, concepto y unidad. Facilita consultar series históricas normalizadas con campos como valor, unidad, inicio, fin, accession, formulario y fecha de presentación. Es muy útil, pero no reemplaza al filing: puede omitir o representar de manera insuficiente facts custom, contextos dimensionales y relaciones entre conceptos.

### XBRL, iXBRL y taxonomías

**XBRL:** eXtensible Business Reporting Language. Lenguaje estructurado utilizado para etiquetar datos financieros. Permite expresar que un valor es, por ejemplo, ingresos, en pesos argentinos, correspondiente a un período concreto y a un perímetro determinado.

**iXBRL o Inline XBRL:** documento HTML legible por una persona que incorpora las etiquetas XBRL dentro de la misma página. Combina presentación visual y datos estructurados.

**XBRL instance:** archivo que contiene los facts, contextos y unidades reportados. Es la capa que vincula cada valor con un concepto, un período, una entidad y, cuando corresponde, dimensiones.

**XSD o schema:** archivo de esquema que define los conceptos disponibles para un filing: nombre, tipo de dato, `periodType`, balance, sustitución y namespace. También importa taxonomías estándar y define conceptos custom del emisor.

**Taxonomía:** vocabulario contable XBRL. `ifrs-full` representa conceptos IFRS; `us-gaap`, conceptos US-GAAP; `dei`, información de identidad/documento; `srt`, conceptos regulatorios compartidos. YPF también utiliza extensiones propias.

**Namespace:** URI que identifica de forma inequívoca el vocabulario al que pertenece un concepto y, habitualmente, su versión. Dos tags con el mismo nombre local pero namespaces diferentes no son necesariamente equivalentes.

**Tag o concept:** nombre local de un concepto XBRL, por ejemplo `Revenue` o `ProfitLoss`. Un tag no es todavía una variable económica universal: su definición, taxonomía, contexto y período deben validarse.

**QName:** nombre calificado formado por taxonomía o prefijo y tag, por ejemplo `ifrs-full:Revenue`. Es más preciso que guardar solamente `Revenue`.

**Concepto standard:** concepto definido por una taxonomía pública como IFRS o US-GAAP.

**Concepto custom:** concepto creado en la extensión XBRL del emisor. No es inválido por ser custom, pero requiere revisar su definición, relaciones y continuidad histórica antes de generalizarlo.

**Label:** nombre legible asociado al concepto, normalmente obtenido del label linkbase.

**Description/documentation label:** explicación más extensa del significado contable del concepto, cuando está disponible.

**XBRL type:** tipo de dato definido por el esquema, por ejemplo monetario, acciones, porcentaje, texto o fecha.

**Balance:** atributo que indica la naturaleza contable `debit` o `credit` de ciertos conceptos. Ayuda a validar signos y relaciones, pero no define por sí solo cómo debe presentarse el valor.

**periodType:** define si el concepto corresponde a un instante (`instant`) o a una duración (`duration`). Activos al cierre son normalmente instant; ingresos del ejercicio son duration.

**Linkbase:** archivo o sección XBRL que expresa relaciones entre conceptos.

- **Label linkbase:** nombres y descripciones legibles.
- **Presentation linkbase:** orden y jerarquía de presentación.
- **Calculation linkbase:** relaciones aritméticas declaradas, con sus pesos.
- **Definition linkbase:** relaciones dimensionales y otras definiciones estructurales.

Una relación de calculation no demuestra automáticamente que una fórmula sea adecuada para un ratio financiero: todavía deben coincidir período, unidad, moneda, dimensiones y perímetro.

### Facts, observaciones y contextos

**Fact:** afirmación reportada en XBRL. Combina concepto, valor y contexto; para facts numéricos también incluye unidad y atributos de precisión.

**Observación:** una aparición concreta de un fact. El mismo QName puede tener muchas observaciones por períodos comparativos, segmentos, unidades, filings o reexpresiones. Por eso no se deduplica simplemente por `fy`.

**Contexto XBRL:** estructura que indica a qué entidad, período y dimensiones corresponde un fact. Dos valores con el mismo QName no son intercambiables si tienen contextos incompatibles.

**contextRef/context ID:** identificador interno que conecta el fact con su contexto dentro del filing.

**Entidad del contexto:** identificador de la compañía a la que pertenece el fact. Debe ser compatible con el CIK o identidad analizada.

**Instant:** fecha puntual aplicable a un stock, como caja o activos al cierre.

**Duration:** intervalo con fecha de inicio y fin aplicable a un flujo, como ingresos, utilidad o CFO.

**Start date / end date:** límites del período de duración. En facts instant, la fecha relevante se conserva separadamente como `instant_date`.

**FY:** fiscal year informado por Company Facts. Puede ser el año asignado por el filing y no es una clave histórica segura. La deduplicación temporal debe basarse en el período económico real, especialmente `end`.

**FP:** fiscal period, como `FY`, `Q1`, `Q2` o `Q3`.

**Frame:** período estandarizado que SEC asigna a algunos facts comparables. No todos los facts poseen frame y no debe emplearse como sustituto del contexto original.

**Dimensión:** eje adicional que desagrega un fact. Puede representar segmento, producto, geografía, clase de acción, subsidiaria o componente contable.

**Axis:** dimensión o pregunta del desglose, por ejemplo “segmento operativo”.

**Member:** miembro concreto de la dimensión, por ejemplo “Exploración y Producción”.

**Typed dimension:** dimensión cuyo miembro se expresa mediante un valor definido por el emisor, en lugar de un miembro enumerado estándar.

**Consolidado vs individual:** perímetro de los estados financieros. No se debe dividir un numerador consolidado por un denominador individual, ni mezclar operaciones continuadas con totales sin documentarlo.

**NCI o non-controlling interests:** participación de accionistas minoritarios en subsidiarias. Para ratios del accionista de YPF suele ser necesario priorizar utilidad y equity atribuibles a propietarios de la controladora.

### Unidades, monedas y precisión

**Unit:** unidad XBRL del fact, por ejemplo ARS, USD, acciones, ARS por acción o una unidad pura para ratios.

**Moneda por fact:** la moneda se determina para cada observación. No se asume que un filing SEC está expresado en USD; YPF puede reportar facts en ARS y otros emisores extranjeros en sus monedas funcionales.

**Measure:** medida elemental que forma una unidad XBRL.

**Numerator/denominator de unidad:** componentes de unidades divididas, por ejemplo moneda por acción.

**Decimals:** precisión declarada del fact XBRL. No significa necesariamente cantidad de decimales visuales; también puede indicar redondeo a miles o millones.

**Scale:** multiplicador utilizado especialmente en iXBRL para convertir el texto mostrado al valor numérico real.

**Sign:** atributo que puede invertir el signo del número mostrado en iXBRL.

### Capas del pipeline

**RAW:** copia inmutable de la respuesta o archivo original descargado. Es la fuente de verdad y conserva hash, URL y fecha de descarga. Un RAW no debe ser corregido silenciosamente ni reemplazado por una ventana histórica menor.

**PARSED:** representación obtenida al leer el RAW: facts, contextos, dimensiones, unidades, conceptos y relaciones. Todavía conserva la semántica del documento original.

**NORMALIZED:** datos transformados a un contrato común para comparar emisores y taxonomías. Normalizar no significa perder QName, unidad, moneda, período, perímetro o provenance.

**DERIVED:** valor calculado a partir de otros inputs, como EBITDA reconstruido, FCF o un ratio. Todo DERIVED debe indicar exactamente qué inputs y reglas utilizó.

**Snapshot:** fotografía identificable del conjunto de fuentes utilizado antes de un procesamiento importante. Permite reproducir el análisis aunque EDGAR incorpore filings nuevos posteriormente.

**SHA256/hash:** huella criptográfica del archivo. Permite demostrar qué versión exacta del documento se utilizó y detectar cambios.

**Provenance:** información necesaria para demostrar de dónde salió un dato: CIK, accession, filing, archivo, hash, QName, contexto, unidad, período y fecha de pipeline.

**Lineage:** cadena de dependencias desde un resultado DERIVED hasta cada fact RAW que participó en el cálculo.

**Dato, tiempo de fuente y tiempo de pipeline:** tres planos diferentes. El período del dato, la fecha de presentación/descarga de la fuente y la fecha de procesamiento no deben almacenarse como si fueran una única fecha.

### Variables económicas y métodos

**Economic variable:** concepto financiero independiente de una taxonomía concreta, por ejemplo Revenue, Debt o Net Income attributable to owners.

**Candidate tag:** QName potencialmente capaz de representar una variable económica. Ser candidato no implica equivalencia automática.

**Preferred tag:** tag seleccionado como primera opción para una variable y un tipo de emisor, con justificación contable y evidencia de cobertura.

**Fallback tag:** alternativa utilizada únicamente cuando el preferred no está disponible y se cumplen condiciones explícitas de equivalencia o compatibilidad.

**DIRECT:** método que utiliza un valor reportado directamente con la definición requerida.

**RECONSTRUCTED:** método que construye una variable a partir de componentes, por ejemplo `EBITDA = EBIT + D&A`.

**ALTERNATIVE:** definición financieramente válida pero conceptualmente diferente, como ROIC basado en NOPAT frente a una variante basada en beneficio ajustado.

**ALGEBRAIC_EQUIVALENT:** reescritura matemática de otro método que no debe contarse como una forma financieramente independiente. Por ejemplo, `Market Cap / Net Income` y `Price × Shares / Net Income` son equivalentes si precio y acciones reconstruyen exactamente el mismo market cap.

**Formula text:** fórmula expresada de manera legible.

**Formula normalized:** representación estandarizada utilizada para comparar fórmulas y detectar duplicados algebraicos o estructurales.

**Required period:** ventana temporal necesaria, por ejemplo FY, TTM, dos cierres consecutivos o último instante.

**Required perimeter:** perímetro contable exigido para que los inputs sean compatibles.

**Available YPF:** indica si los inputs fueron encontrados para YPF. No garantiza por sí solo que cualquier combinación de observaciones sea válida.

**Coverage:** intervalo histórico realmente cubierto por los tags requeridos para el método.

**Gap:** período interno faltante entre el primer y último año observado. Un gap puede impedir un CAGR o reducir la posibilidad de formar promedios.

### Estados de validez

**VALID:** método respaldado por una definición financiera adecuada y con condiciones de aplicación satisfechas por la evidencia evaluada.

**VALID_CONDITIONAL:** método razonable cuya validez depende de controles de período, unidad, moneda, dimensiones, share class, perímetro u otra condición indicada.

**NOT_RECOMMENDED:** método matemáticamente posible pero inferior, ambiguo o con riesgo evitable frente a una alternativa disponible.

**INVALID:** método que mezcla conceptos incompatibles o no representa la métrica declarada.

**UNRESOLVED:** la evidencia disponible no permite decidir. Debe permanecer sin certificar hasta obtener el dato o definición faltante.

### Comparación con el extractor

**EXTRACTED_AND_USED:** el concepto es capturado y participa en un cálculo.

**EXTRACTED_NOT_USED:** el concepto se captura, pero actualmente no alimenta ratios.

**AVAILABLE_NOT_EXTRACTED:** EDGAR expone el concepto, pero el extractor no lo solicita o normaliza.

**RAW_ONLY:** el concepto aparece en el filing real, pero no está disponible o no resulta adecuadamente utilizable desde Company Facts.

**NOT_FOUND:** el extractor busca el concepto, pero no se encontró en el universo observado.

**ALTERNATIVE_TO_CURRENT:** tag o método no utilizado hoy que puede mejorar o sustituir al actual después de su validación.

En las hojas técnicas pueden aparecer nombres históricos equivalentes, como `YA_EXTRAIDO`, `NORMALIZADO_PERO_NO_UTILIZADO`, `EXISTE_PERO_NO_EXTRAIDO` y `EXISTE_EN_RAW_FILING_PERO_NO_NORMALIZADO`. Representan, respectivamente, conceptos extraídos, normalizados sin uso, disponibles no extraídos y RAW-only.

### Convenciones financieras temporales

**FY:** ejercicio fiscal completo.

**TTM:** trailing twelve months, suma o acumulación de los doce meses terminados en una fecha determinada. No debe confundirse con el último FY.

**Forward:** estimación futura, normalmente proveniente de consenso de analistas. EDGAR publica información reportada y no ofrece por sí solo un Forward P/E de consenso.

**Stock:** variable medida en una fecha, como activos, deuda o equity.

**Flow:** variable medida durante un intervalo, como revenue, net income o CFO.

**Promedio de stock:** promedio entre saldos inicial y final utilizado como denominador en ratios como ROE, ROA y rotaciones. Usar solamente el cierre es un fallback y puede distorsionar el resultado.

**Shares outstanding:** acciones existentes en una fecha puntual.

**Weighted-average shares:** promedio ponderado de acciones durante el período; es el denominador apropiado para EPS.

**ADR ratio/share class:** relación entre ADR y acciones locales y clase concreta de acciones. Debe validarse antes de combinar precio ADR, EPS, market cap y cantidades de acciones.
