# GUÍA DE ESTILO WEBSHOOKS
## Sistema visual y biblioteca de plantillas para documentos, diagramas, mapas, figuras y presentaciones

> **Versión 2.0 — 2026-09-09**
>
> Esta guía es la **fuente única de verdad visual y estructural** de webshooks.
> Define cómo diseñar documentos, presentaciones, PDFs, diagramas, mapas, flujos,
> arquitecturas, tablas, métricas, figuras y demás piezas visuales.
>
> **Principio central:** no diseñar cada documento desde cero. Elegir una plantilla,
> completar contenido y reutilizar el mismo sistema visual.

---

# 1. Identidad de marca

## 1.1 Wordmark

El wordmark oficial es:

**webshooks.**

Composición:

| Fragmento | Color | Hex |
|---|---|---|
| `web` | Azul webshooks | `#3B82F6` |
| `shooks` | Navy webshooks | `#1A2744` |
| `.` | Naranja webshooks | `#F5821F` |

Reglas:
- No deformar ni estirar el wordmark.
- No cambiar el orden ni los colores.
- No usar sombras, degradados ni contornos sobre el wordmark.
- En portada puede utilizarse grande.
- En documentos internos puede utilizarse en header o footer.
- Cuando no sea posible representar el wordmark con color, usar `webshooks.` en Navy.

## 1.2 Concepto verbal

webshooks comunica:

> **Evidencia → Datos → Información económica → Decisiones**

La identidad visual debe transmitir:
- precisión;
- trazabilidad;
- estructura;
- claridad;
- confiabilidad;
- tecnología;
- análisis;
- auditabilidad.

Evitar una estética:
- excesivamente decorativa;
- corporativa genérica;
- saturada;
- tipo dashboard de trading;
- futurista sin función;
- basada en gradientes fuertes o efectos 3D.

---

# 2. Sistema cromático

## 2.1 Paleta principal

| Rol | Nombre | Hex | Uso |
|---|---|---|---|
| Primario | Navy | `#1A2744` | títulos, estructura, texto principal |
| Acento | Blue | `#3B82F6` | acciones, conectores, títulos secundarios |
| Marca | Orange | `#F5821F` | acento, llamadas, divisores |
| Éxito | Green | `#43A047` | OK, PASS, estado activo |
| Cuerpo | Body Gray | `#3A4458` | texto corriente |
| Secundario | Gray | `#6B7589` | metadata, notas, leyendas |
| Fondo azul | Blue BG | `#DCEAFF` | contenedores y tarjetas |
| Fondo verde | Green BG | `#E7F7EC` | validación, éxito, procesos |
| Fondo suave | Zebra | `#F4F8FE` | filas alternas, superficies |
| Borde | Line | `#D6E2F2` | bordes, divisores |

## 2.2 Colores semánticos adicionales

Cuando una figura necesite estados diferenciados, mantener la paleta webshooks y utilizar tintes suaves:

| Semántica | Color principal | Uso |
|---|---|---|
| Información | Blue | datos, flujo normal, componentes |
| Atención | Orange | revisión, warning, decisión |
| Éxito | Green | OK, aprobado, publicado |
| Error | Rojo suave | error/rechazo/bloqueo |
| Estado neutro | Gray/Navy claro | pendiente, inactivo |
| Modelo | Violeta suave | capa analítica/modelado |
| Datos | Rosa suave | capa de datos/economic facts |

**Regla:** los colores adicionales son semánticos, no decorativos. No introducir una paleta arbitraria en cada documento.

---

# 3. Tipografía

## 3.1 Fuente estándar

**Calibri**.

Fallback:
1. Segoe UI
2. Arial
3. system sans

Para código y fórmulas:
- Consolas;
- Cascadia Mono;
- Courier New como fallback.

## 3.2 Jerarquía

Valores verificados 2026-09-09 contra los tres artefactos reales (ver §25):
`theme_webshooks.json` (fuente que consume el generador Python),
`Webshooks_Template_Master.docx` (estilos Word reales, vía `python-docx`) y
`Webshooks_Template_Master.pptx` (shapes reales, vía `python-pptx`). Los
rangos de abajo **reemplazan** una versión anterior que no estaba anclada a
ningún artefacto medido — ver §25.1 para el detalle fuente por fuente.

| Nivel | Tamaño verificado | Peso | Color |
|---|---:|---|---|
| Portada — título (DOCX) | 34 pt | Bold | Navy |
| Portada — título (PPT, fondo Navy) | 38 pt | Bold | White |
| Portada — subtítulo (PPT, fondo Navy) | 22 pt | Regular | Blue claro (`#AECAFF`) |
| H1 / título de sección (DOCX) | 18–22 pt | Bold | Navy |
| H1 / título de sección (PPT) | 24–30 pt | Bold | Navy |
| H2 (DOCX) | 14–16 pt | Bold | Blue |
| H3 (DOCX) | 12–12.5 pt | Bold | Navy |
| Cuerpo — documento (DOCX) | 10.5–12 pt | Regular | Body |
| Cuerpo — presentación (PPT, bullets) | 15–16 pt | Regular | Body |
| Caption / footer | 8.5–10 pt | Regular | Gray |
| KPI principal (PPT) | 22–32 pt | Bold | semántico |
| KPI label (PPT) | 9–12 pt | Semibold | Gray |
| Código | 9–10.5 pt | Regular | Navy/Body |

**Regla nueva, antes implícita:** el cuerpo de texto en **presentación** es
más grande que en **documento** (15–16 pt vs. 10.5–12 pt) porque una
diapositiva se lee a distancia y un documento se lee de cerca. No es la misma
fila; son dos filas distintas con el mismo rol semántico ("Cuerpo").

La jerarquía relativa importa más que el punto exacto — pero el punto exacto
debe salir de un artefacto medido, no de una estimación. Si se cambia un
tamaño acá, hay que volver a medir el artefacto que corresponda (§25) y
actualizar esta tabla en el mismo cambio.

---

# 4. Principios de composición

## 4.1 Regla 70/20/10

Como orientación:
- **70%** superficie neutra/blanca;
- **20%** superficies suaves de marca;
- **10%** color fuerte/acento.

No saturar una página con bloques de color.

## 4.2 Espaciado

Utilizar una escala consistente:

`4 / 8 / 12 / 16 / 24 / 32 / 48`

Evitar valores aleatorios.

## 4.3 Alineación

Prioridad:
1. misma línea de inicio;
2. misma anchura de columnas;
3. misma separación;
4. misma altura en elementos comparables.

La sensación de calidad proviene principalmente de la alineación.

## 4.4 Bordes

- Preferir bordes finos `#D6E2F2`.
- Radio de esquinas moderado.
- No utilizar bordes gruesos salvo para diferenciar estados.
- Evitar cajas dentro de cajas dentro de cajas.

## 4.5 Iconografía

Usar iconos lineales, simples y consistentes.

Familias recomendadas:
- documento;
- base de datos;
- nube;
- engranaje;
- búsqueda;
- descarga;
- validación;
- escudo;
- gráfico;
- usuarios;
- API/integración;
- reloj;
- enlace;
- alerta;
- check;
- error.

Reglas:
- mismo grosor visual;
- tamaño consistente;
- un icono representa una función;
- no usar emojis como iconografía profesional.

---

# 5. Arquitectura universal de una figura

Toda figura webshooks debe poder describirse con esta estructura:

```text
TÍTULO
Subtítulo / mensaje principal

┌───────────────────────────────────────────────┐
│ CONTEXTO / ENTRADAS                           │
├───────────────────────────────────────────────┤
│                                               │
│ FIGURA PRINCIPAL                              │
│                                               │
├───────────────────────────────────────────────┤
│ LEYENDA / PRINCIPIOS / NOTAS                  │
└───────────────────────────────────────────────┘

Fuente / versión / fecha
```

## 5.1 Componentes reutilizables

Una figura puede componerse con:
- título;
- subtítulo;
- kicker;
- tarjetas;
- nodos;
- contenedores;
- conectores;
- flechas;
- decisiones;
- badges;
- KPIs;
- tablas;
- leyendas;
- notas;
- callouts;
- captions;
- footer;
- versión.

## 5.2 Regla de lectura

Toda figura debe tener **un recorrido de lectura dominante**:
- izquierda → derecha;
- arriba → abajo;
- centro → periferia;
- capas de abajo → arriba.

Si hay más de un recorrido, debe existir una leyenda explícita.

---

# 6. Catálogo maestro de plantillas visuales

Esta sección es la biblioteca conceptual que debe utilizarse para cualquier documento webshooks.

## T01 — Portada

**Uso:** documentos técnicos, manuales, propuestas, informes, SDD, runbooks.

Estructura:

```text
webshooks.

TÍTULO
Subtítulo

Descripción de una línea

[metadata]
Proyecto · versión · fecha · clasificación
```

Variantes:
- portada clara;
- portada Navy;
- portada ejecutiva;
- portada técnica.

---

## T02 — Resumen ejecutivo

**Uso:** presentar 3–6 mensajes principales.

Estructura:

```text
Título
Subtítulo

┌────────┐ ┌────────┐ ┌────────┐
│ KPI 01 │ │ KPI 02 │ │ KPI 03 │
└────────┘ └────────┘ └────────┘

• Hallazgo
• Hallazgo
• Decisión
```

Reglas:
- máximo 6 KPIs;
- máximo 5 bullets;
- cada KPI debe tener unidad y contexto.

---

## T03 — Arquitectura end-to-end

**Uso:** mostrar desde fuentes hasta usuario.

Patrón:

```text
FUENTES → INGESTA → PROCESAMIENTO → MODELO → PUBLICACIÓN
```

Cada bloque puede contener:
- nombre;
- propósito;
- componentes;
- tecnologías;
- outputs.

**Regla:** el flujo principal se dibuja horizontalmente.

---

## T04 — Arquitectura por capas

**Uso:** software, datos, CPaaS, seguridad, infraestructura.

Patrón:

```text
┌───────────────────────────┐
│ CAPA DE CONSUMO           │
├───────────────────────────┤
│ CAPA DE APLICACIÓN        │
├───────────────────────────┤
│ CAPA DE MODELO            │
├───────────────────────────┤
│ CAPA DE DATOS             │
├───────────────────────────┤
│ CAPA DE INGESTA           │
└───────────────────────────┘
```

Puede complementarse con:
- infraestructura;
- gobierno transversal;
- seguridad;
- observabilidad.

---

## T05 — Arquitectura de sistemas

**Uso:** componentes físicos/lógicos y relaciones.

Patrón:

```text
CLIENTES
   ↓
PRESENTACIÓN
   ↓
SERVICIOS
   ↓
DATOS

MONITOREO / SEGURIDAD / CI-CD
        ↓
     transversal
```

Cada componente debe mostrar:
- nombre;
- tecnología opcional;
- responsabilidad.

---

## T06 — Diagrama de procesos

**Uso:** procedimientos operativos y BPM.

Patrón:

```text
ETAPAS
1 INGESTA → 2 TRANSFORMACIÓN → 3 CÁLCULO → 4 VALIDACIÓN → 5 PUBLICACIÓN
```

Filas recomendadas:
- fuentes;
- extracción;
- transformación;
- cálculo;
- validación;
- publicación.

Elementos:
- tarea;
- decisión;
- flujo principal;
- flujo condicional;
- retorno;
- control.

---

## T07 — Procedimiento paso a paso

**Uso:** SOP, runbooks, onboarding, procedimientos funcionales.

Patrón:

```text
1 → 2 → 3 → 4 → 5 → 6

Cada paso:
- objetivo
- acción
- output
```

Debajo:

```text
CRITERIOS DE ÉXITO | DOCUMENTACIÓN | ERRORES COMUNES
```

---

## T08 — Diagrama de estados

**Uso:** lifecycle de entidades, documentos, jobs, procesos.

Patrón:

```text
NUEVA → EN EXTRACCIÓN → ACTIVA
                  ↓
              EN REVISIÓN
                  ↓
             APROBADA / ERROR
```

Reglas:
- estados como nodos;
- transiciones como flechas;
- condición encima o junto a la flecha;
- estados de error claramente diferenciados;
- transiciones condicionales en línea discontinua.

---

## T09 — Máquina de estados de pipeline

**Uso:** documentos dentro de un pipeline.

Estados típicos:
- inicial;
- extracción;
- procesamiento;
- validación;
- publicado;
- rechazado;
- corrección/reintento.

Debe distinguir:
- transición normal;
- transición condicional;
- rollback/reproceso.

---

## T10 — Capas / stack conceptual

**Uso:** explicar un producto o plataforma sin entrar en infraestructura.

Ejemplo:

```text
Consumo
Aplicación
Modelo
Datos
Ingesta
```

Cada capa:
- nombre;
- responsabilidad;
- ejemplos.

---

## T11 — Contrato de cálculo

**Uso:** ratios, métricas, reglas financieras, APIs de cálculo.

Plantilla:

```yaml
ratio_id:
version:
formula:
inputs:
frequency:
scope:
currency:
validations:
output:
```

A la derecha:

```text
Descripción
Insumos
Reglas y validaciones
Salida
```

**Regla:** un cálculo debe ser reproducible y auditable.

---

## T12 — Familia de ratios / taxonomía

**Uso:** agrupar métricas por dominio.

Patrón:

```text
RENTABILIDAD
ROE · ROA · ROIC · MARGEN

VALUACIÓN
P/E · P/B · EV/EBITDA

SOLVENCIA
DEUDA/PATRIMONIO · DEUDA/EBITDA

EFICIENCIA
ROTACIÓN · DÍAS

CRECIMIENTO
CAGR · CRECIMIENTO EPS
```

---

## T13 — Trazabilidad / lineage

**Uso:** explicar de dónde sale un número.

Patrón:

```text
RAW
 ↓
PARSED
 ↓
NORMALIZED
 ↓
ECONOMIC FACT
 ↓
FINANCIAL MODEL
 ↓
RATIO
 ↓
CERTIFICATION
```

Cada etapa puede incluir:
- fuente;
- transformación;
- versión;
- hash;
- timestamp;
- regla.

---

## T14 — Flujo de datos

**Uso:** integración, ETL/ELT, data pipelines.

Patrón:

```text
Fuente → Ingesta → Validación → Transformación → Storage → Consumo
```

Tipos de conectores:
- sólido = flujo principal;
- discontinuo = control;
- doble sentido = sincronización.

---

## T15 — Gobierno de datos transversal

**Uso:** data governance.

Barra transversal:

```text
IDENTIDAD | TAXONOMÍA | REGLAS | METADATOS | AUDITORÍA | SEGURIDAD
```

Debe cruzar visualmente las capas del sistema.

---

## T16 — Matriz 2×2

**Uso:** priorización, riesgo, decisión, posicionamiento.

Ejemplos:
- impacto vs esfuerzo;
- riesgo vs probabilidad;
- valor vs complejidad.

Reglas:
- ejes claramente etiquetados;
- cuadrantes nombrados;
- máximo 12 elementos;
- no abusar de colores.

---

## T17 — Matriz de trazabilidad

**Uso:** requisito → diseño → implementación → prueba.

Columnas posibles:

| ID | Requisito | Componente | Evidencia | UAT | Estado |
|---|---|---|---|---|---|

---

## T18 — Roadmap / timeline

**Uso:** planes, releases, documentación, proyectos.

Patrón:

```text
FASE 1 → FASE 2 → FASE 3 → FASE 4 → FASE 5
```

Cada fase:
- período;
- objetivo;
- entregables;
- criterio de salida.

---

## T19 — Ciclo continuo

**Uso:** mejora continua, operación, observabilidad.

Patrón:

```text
MEDIR → ANALIZAR → CORREGIR → VALIDAR → PUBLICAR → MEDIR
```

Utilizar flechas circulares o un loop.

---

## T20 — KPI / scorecard

**Uso:** estado de un sistema o proyecto.

Componentes:
- KPI;
- valor;
- unidad;
- objetivo;
- tendencia;
- estado;
- fuente.

Nunca mostrar un número sin contexto.

---

## T21 — Tabla técnica

**Uso:** especificaciones, contratos, inventarios, comparaciones.

Reglas:
- header Navy;
- texto blanco;
- filas zebra;
- columnas alineadas;
- unidades explícitas;
- no más de 8–10 columnas cuando sea posible.

---

## T22 — Comparación

**Uso:** alternativa A vs B, AS-IS vs TO-BE, fuente A vs fuente B.

Patrón:

```text
                 A                 B
Costo            ...               ...
Riesgo           ...               ...
Complejidad      ...               ...
Decisión         ...               ...
```

---

## T23 — AS-IS / TO-BE

**Uso:** procesos y transformación.

Patrón:

```text
AS-IS                    TO-BE
Proceso actual     →     Proceso objetivo
Problemas                Automatización
Controles manuales      Quality gates
```

---

## T24 — Decisión / árbol

**Uso:** reglas de negocio, troubleshooting, arquitectura.

Patrón:

```text
¿CONDICIÓN?
 ├─ Sí → acción A
 └─ No → acción B
```

Decisiones: rombos.
Acciones: rectángulos.
Resultado: estado/callout.

---

## T25 — Swimlane

**Uso:** procesos con múltiples actores.

Lanes típicos:
- Usuario;
- Aplicación;
- API;
- Base de datos;
- Operaciones;
- Auditoría.

Regla: un actor = una lane.

---

## T26 — Secuencia

**Uso:** APIs, autenticación, integración.

Patrón:

```text
Cliente → Gateway → Servicio → DB
   ←        ←          ←
```

Debe mostrar:
- request;
- response;
- error;
- timeout;
- retry si aplica.

---

## T27 — Mapa conceptual

**Uso:** explicar relaciones entre conceptos.

Reglas:
- un concepto central;
- máximo 6–8 conceptos de primer nivel;
- conectores etiquetados cuando la relación no sea obvia.

---

## T28 — Mapa de ecosistema

**Uso:** stakeholders, sistemas, fuentes, proveedores.

Centro:
- producto/plataforma.

Periferia:
- usuarios;
- fuentes;
- sistemas;
- integraciones;
- terceros.

---

## T29 — Embudo

**Uso:** reducción de universo, pipeline, funnel operativo.

Ejemplo:

```text
Documentos
↓
Documentos válidos
↓
Facts
↓
Modelos
↓
Ratios
↓
Publicación
```

---

## T30 — Pirámide / jerarquía

**Uso:** niveles de madurez, gobernanza, arquitectura.

Regla:
- base = volumen/infraestructura;
- niveles superiores = abstracción/decisión.

---

## T31 — Círculo de ciclo de vida

**Uso:** lifecycle y operación continua.

Estados alrededor de un círculo:
- crear;
- procesar;
- validar;
- publicar;
- mantener;
- retirar.

---

## T32 — Certificación / quality gate

**Uso:** controles de calidad.

Patrón:

```text
INPUT
 ↓
VALIDACIONES
 ↓
PROVENANCE
 ↓
CERTIFICATION

PASS | PARTIAL | BLOCKED
```

---

## T33 — Error / troubleshooting

**Uso:** manuales operativos.

Estructura:

```text
SÍNTOMA
 ↓
CAUSA POSIBLE
 ↓
VERIFICACIÓN
 ↓
ACCIÓN
 ↓
CRITERIO DE RESOLUCIÓN
```

---

## T34 — Before / After

**Uso:** mejora de procesos, refactor, migración.

Dos paneles:
- Antes;
- Después.

Abajo:
- impacto;
- beneficio;
- riesgo residual.

---

## T35 — Figura libre controlada

Cuando ninguna plantilla encaja:
1. reutilizar componentes existentes;
2. mantener grid;
3. mantener paleta;
4. mantener tipografía;
5. mantener leyenda;
6. documentar la nueva variante en esta guía.

**No crear una nueva estética sin agregarla al catálogo.**

---

# 7. Sistema de conectores

## 7.1 Tipos

| Línea | Significado |
|---|---|
| Continua | flujo principal |
| Continua con flecha | dependencia/transición |
| Discontinua | control o condición |
| Doble flecha | sincronización |
| Línea fina | relación conceptual |
| Línea resaltada | camino crítico |

## 7.2 Flechas

La flecha siempre debe responder:

> ¿Qué pasa después?

Evitar conectores:
- cruzados innecesariamente;
- sin dirección;
- demasiado largos;
- con múltiples significados.

## 7.3 Decisiones

Usar rombo:

```text
      ◇
   ¿Condición?
   /        \
 Sí          No
```

Nunca usar un círculo como decisión si existe ambigüedad.

---

# 8. Estados y semántica visual

## 8.1 Estado operativo

Blue / fondo azul suave.

## 8.2 Estado de revisión

Orange / fondo naranja suave.

## 8.3 Estado activo / OK

Green / fondo verde suave.

## 8.4 Estado de error

Rojo suave / fondo rojo muy claro.

## 8.5 Estado inactivo

Gray / fondo gris azulado.

## 8.6 Estado publicado

Green, pero visualmente distinto de "activo" mediante icono o label.

---

# 9. Reglas para gráficos cuantitativos

## 9.1 Elegir el gráfico correcto

| Necesidad | Gráfico |
|---|---|
| Comparar categorías | barras |
| Ranking | barras horizontales |
| Evolución temporal | línea |
| Composición | barras apiladas / pie con pocas categorías |
| Correlación | scatter |
| Distribución | histograma/boxplot cuando corresponda |
| Evolución de etapas | funnel |
| Relación causal/flujo | diagrama, no chart |

## 9.2 Reglas

- No decorar.
- Etiquetar unidades.
- No truncar ejes sin indicarlo.
- No usar 3D.
- No utilizar pie para series temporales.
- No mezclar unidades incompatibles en un mismo eje.
- Si hay pocos datos, priorizar legibilidad sobre sofisticación.
- La fuente debe aparecer cuando el gráfico utilice datos externos.

---

# 10. Reglas para mapas

"Mapa" puede significar mapa geográfico o mapa conceptual.

## 10.1 Mapa geográfico

Debe contener:
- título;
- territorio;
- escala si aplica;
- leyenda;
- fuente;
- fecha;
- norte cuando sea necesario.

Usar color únicamente para comunicar una variable.

## 10.2 Mapa conceptual

Debe contener:
- concepto central;
- agrupaciones;
- relaciones;
- dirección cuando exista;
- leyenda si hay varios tipos de relación.

---

# 11. Reglas para tablas

## Tabla estándar

```text
Header Navy / texto blanco
Fila impar blanca
Fila par #F4F8FE
Borde #D6E2F2
```

## Reglas

- Una columna = una variable.
- No usar saltos de línea innecesarios.
- Números alineados a la derecha.
- Texto alineado a la izquierda.
- Estados como badges.
- Unidades en header cuando sea posible.
- No usar color para transmitir información que también puede expresarse con texto.

---

# 12. Reglas para fórmulas y contratos

Toda fórmula importante debe ser representable como contrato:

```yaml
id:
version:
purpose:
formula:
inputs:
assumptions:
scope:
frequency:
validation:
output:
provenance:
```

Debe poder responder:
- qué calcula;
- con qué datos;
- bajo qué perímetro;
- con qué frecuencia;
- qué validaciones ejecuta;
- de dónde provienen los insumos;
- cómo se reproduce.

---

# 13. Reglas de trazabilidad

En documentos de datos financieros, la figura debe privilegiar:

```text
Fuente
→ Documento
→ Extracción
→ Normalización
→ Economic Fact
→ Modelo
→ Métrica
→ Validación
→ Publicación
```

Cuando sea posible, cada dato derivado debe conservar:
- source;
- document_id;
- period;
- entity;
- currency;
- scope;
- transformation;
- formula;
- version;
- timestamp;
- hash;
- quality status.

---

# 14. Plantillas para documentos

## DOC-01 — Documento técnico

```text
Portada
Resumen ejecutivo
1. Contexto
2. Objetivo
3. Alcance
4. Arquitectura
5. Diseño
6. Flujos
7. Validaciones
8. Seguridad
9. Observabilidad
10. Operación
11. Riesgos
12. UAT
Anexos
```

## DOC-02 — Runbook

```text
Propósito
Precondiciones
Procedimiento
Validaciones
Errores frecuentes
Rollback
Evidencias
Escalamiento
Checklist
```

## DOC-03 — SDD

```text
Contexto
Decisiones de arquitectura
AS-IS
TO-BE
Componentes
Interfaces
Modelo de datos
Flujos
Seguridad
Observabilidad
Performance
Testing
Deployment
Riesgos
ADRs
```

## DOC-04 — Procedimiento

```text
Objetivo
Frecuencia
Responsable
Entradas
Pasos
Outputs
Criterios de éxito
Errores comunes
Evidencias
```

## DOC-05 — Especificación funcional

```text
Problema
Objetivo
Actores
AS-IS
TO-BE
Reglas de negocio
Validaciones
Excepciones
Datos
Interfaces
UAT
```

---

# 15. Plantillas de presentación

## PPT-01 — Ejecutiva

Secuencia:

```text
01 Portada
02 Problema
03 Propuesta
04 Arquitectura
05 Proceso
06 Resultados
07 Riesgos
08 Roadmap
09 Decisión requerida
10 Cierre
```

## PPT-02 — Técnica

```text
01 Portada
02 Contexto
03 Requisitos
04 Arquitectura
05 Componentes
06 Datos
07 Flujos
08 Seguridad
09 Observabilidad
10 Testing
11 Deployment
12 Operación
13 Riesgos
14 Próximos pasos
```

## PPT-03 — Demo / evidencia

```text
01 Qué demostramos
02 Arquitectura
03 Golden run
04 Evidencia
05 Trazabilidad
06 Métricas
07 Hallazgos
08 Limitaciones
09 Próximos pasos
```

---

# 16. Sistema de PDF

El PDF no tiene una estética distinta.

Debe ser una **salida fiel** del documento Word o de un renderer PDF basado en el mismo sistema.

Fuentes de verdad:

```text
Contenido → Markdown
Estilo → brand-kit
Documento → DOCX
Presentación → PPTX
Distribución → PDF
```

Regla:
> No corregir visualmente un PDF a mano. Corregir la fuente y regenerar.

---

# 17. Sistema de generación

## 17.1 Fuente única de contenido

Markdown:

```text
.md
```

## 17.2 Word

Motor:
- `python-docx`;
- `reference.docx`;
- Pandoc cuando sea necesario.

El `reference.docx` debe concentrar:
- estilos;
- tipografía;
- colores;
- encabezados;
- tablas;
- footer;
- wordmark.

## 17.3 PPT

Motor:
- `python-pptx`.

Debe existir un generador reutilizable con funciones para:
- `header()`;
- `footer()`;
- `wordmark()`;
- `card()`;
- `kpi_card()`;
- `table()`;
- `node()`;
- `connector()`;
- `badge()`;
- `section_header()`;
- `legend()`;
- `process_step()`;
- `state_node()`;
- `layer()`;
- `architecture_block()`.

## 17.4 PDF

Preferencias:
1. PDF generado desde DOCX;
2. PDF generado directamente con ReportLab para figuras/control total;
3. conversión desde HTML/Pandoc cuando corresponda.

---

# 18. Estructura recomendada del brand-kit

```text
brand-kit/
├── GUIA_ESTILO_WEBSHOOKS.md
├── plantilla_webshooks.md
├── reference.docx
├── Webshooks_Template_Master.docx
├── Webshooks_Template_Master.pptx
├── Webshooks_Template_Master.pdf
├── webshooks_docx.py
├── webshooks_pptx.py
├── webshooks_pdf.py
├── build_docx.py
├── build_pptx.py
├── build_pdf.py
└── templates/
    ├── documents/
    │   ├── tecnico.md
    │   ├── runbook.md
    │   ├── sdd.md
    │   ├── procedimiento.md
    │   └── funcional.md
    ├── diagrams/
    │   ├── architecture.md
    │   ├── process.md
    │   ├── state.md
    │   ├── sequence.md
    │   ├── swimlane.md
    │   ├── layers.md
    │   ├── data-flow.md
    │   ├── lineage.md
    │   ├── roadmap.md
    │   ├── matrix.md
    │   └── ecosystem.md
    └── charts/
        ├── kpi.md
        ├── comparison.md
        ├── trend.md
        └── composition.md
```

---

# 19. Convención de nombres

Formato:

```text
WS_<tipo>_<nombre>_v<version>
```

Ejemplos:

```text
WS_ARCH_DATA_v1
WS_PROCESS_INGESTA_v1
WS_STATE_DOCUMENT_v1
WS_RATIO_PE_v1
WS_ROADMAP_2026_v1
WS_KPI_SYSTEM_HEALTH_v1
```

Para documentos:

```text
WS_<DOCUMENTO>_<PROYECTO>_v<version>
```

---

# 20. Control de versiones visual

Una modificación visual que afecte a más de un documento debe realizarse en:
- la guía;
- el componente;
- la plantilla.

No corregir el mismo problema documento por documento.

Ejemplo incorrecto:

```text
PPT A → corregido a mano
PPT B → corregido a mano
PPT C → corregido a mano
```

Ejemplo correcto:

```text
webshooks_pptx.py
       ↓
plantilla
       ↓
PPT A / B / C
```

---

# 21. Checklist de calidad

Antes de publicar cualquier documento:

### Marca
- [ ] Wordmark correcto.
- [ ] Paleta correcta.
- [ ] Tipografía correcta.
- [ ] Footer consistente.

### Estructura
- [ ] Existe una jerarquía clara.
- [ ] El título explica la figura.
- [ ] La figura tiene un mensaje principal.
- [ ] La lectura es evidente.

### Visual
- [ ] Alineación consistente.
- [ ] Espaciado consistente.
- [ ] No hay elementos superpuestos.
- [ ] No hay conectores ambiguos.
- [ ] No hay exceso de color.
- [ ] Los iconos pertenecen a la misma familia.

### Datos
- [ ] Unidades visibles.
- [ ] Fuente indicada.
- [ ] Fecha/versionado cuando corresponde.
- [ ] No se presentan estimaciones como datos medidos.
- [ ] Fórmulas y reglas importantes son reproducibles.

### Técnica
- [ ] Documento regenerable.
- [ ] No existen correcciones manuales que se pierdan al regenerar.
- [ ] La fuente de verdad está versionada.

---

# 22. Regla maestra

> **webshooks no debe tener "dibujos bonitos"; debe tener un lenguaje visual reutilizable.**

Cada nueva figura debe responder:

1. ¿Qué quiero comunicar?
2. ¿Qué plantilla del catálogo corresponde?
3. ¿Qué componentes reutilizo?
4. ¿Cuál es el recorrido de lectura?
5. ¿Qué evidencia soporta la figura?
6. ¿Cómo se regenerará?
7. ¿Dónde queda documentada la variante?

Si una figura no puede responder estas preguntas, todavía no está lista para incorporarse al sistema.

---

# 23. Referencia visual consolidada

Las figuras de referencia ya utilizadas por webshooks establecen el lenguaje visual para:

- arquitectura end-to-end;
- arquitectura de datos;
- arquitectura de sistemas;
- modelo de capas;
- diagramas de procesos;
- procedimientos paso a paso;
- diagramas de estados;
- contratos de cálculo;
- familias de ratios;
- trazabilidad;
- gobierno de datos;
- validación y certificación;
- KPIs;
- tablas;
- roadmap;
- ciclo de mejora continua.

Estas piezas deben considerarse **variantes del mismo sistema**, no estilos independientes.

---

# 24. Estado de la guía

**Fuente única de verdad:** este archivo.

Las plantillas Word/PPT/PDF son implementaciones del sistema definido aquí.

Cuando una plantilla y esta guía entren en conflicto:
1. se preserva la intención visual de la guía;
2. se actualiza la plantilla;
3. no se introduce una excepción local.

---

# 25. Verificación cruzada 2026-09-09 — inconsistencias detectadas

Esta sección existe porque la regla del encargo original es explícita: *"si
detectás inconsistencias entre archivos, documentalas y determiná cuál debe
considerarse canónica según la propia estructura y uso de los archivos. No
inventes una solución silenciosamente."* Lo que sigue es esa verificación,
hecha leyendo los artefactos reales (no la prosa que los describe):
`theme_webshooks.json` con `json`, `Webshooks_Template_Master.docx` con
`python-docx`, `Webshooks_Template_Master.pptx` con `python-pptx`.

## 25.1 · Jerarquía tipográfica — tres fuentes, tres valores distintos

| Nivel | Guía (versión anterior a hoy) | `theme_webshooks.json` | `Master.docx` (estilo Word real) | `Master.pptx` (shape real) |
|---|---|---|---|---|
| H1 | 24–30 pt | `h1.size = 18` | `Heading 1` = **22 pt**, Navy | título de sección = **28 pt**, Navy |
| H2 | 17–21 pt | `h2.size = 14` | `Heading 2` = **16 pt**, Blue | — |
| H3 | 13–16 pt | `h3.size = 12` | `Heading 3` = **12.5 pt**, Navy | — |
| Portada — subtítulo | 16–22 pt | `cover.subtitle.size = 14` | `Subtitle` = **12 pt**, color `#4F81BD` | **22 pt**, `#AECAFF` |

**Ninguna de las tres fuentes coincidía exactamente con la guía anterior, y
las tres tampoco coincidían entre sí.** Resolución canónica, por uso real:

- Para lo que genera el pipeline Python (`webshooks_docx.py`,
  `webshooks_pptx.py`), la fuente de verdad es `theme_webshooks.json` — es
  el input que ese código realmente lee. Si un documento generado por script
  no coincide con el JSON, el bug está en el script, no en el JSON.
- Para lo que un humano arma a mano abriendo `Master.docx`/`Master.pptx` en
  Office y usando la galería de estilos, la fuente de verdad son **los
  estilos reales del archivo Master**, porque eso es lo que Office aplica al
  tipear — no lo que diga esta guía en prosa.
- La tabla de §3.2 se corrigió para reflejar **rangos que sí contienen** los
  valores medidos de `Master.docx` y `Master.pptx` (las dos fuentes con las
  que un operador interactúa directamente). `theme_webshooks.json` queda
  **por debajo** de esos rangos en H1/H2/H3/subtítulo de portada — ver
  DEFECTO-01 abajo: no es una variante válida, es un desvío del JSON
  respecto de lo que el propio Master ya adoptó.

## 25.2 · DEFECTO-01 — `theme_webshooks.json` quedó desactualizado

`theme_webshooks.json` declara tamaños de encabezado (H1=18, H2=14, H3=12,
subtítulo de portada=14) sistemáticamente **más chicos** que los que el
Master real usa (H1=22, H2=16, H3=12.5, subtítulo de portada=12 en DOCX / 22
en PPT). La hipótesis más simple, y la que mejor explica el patrón parejo
(el JSON es más chico en los cuatro casos, no al azar), es que el JSON se
escribió **antes** de que se afinara el Master, y no se volvió a sincronizar.

**No se corrigió el JSON en este pase** (está fuera del alcance "actualizar
la guía"; tocarlo es tocar un input real de un generador productivo). Queda
registrado como pendiente: si `webshooks_docx.py`/`webshooks_pptx.py` alguna
vez generan directo desde el JSON sin pasar por el Master como base, van a
producir encabezados más chicos que los del Master. **Acción recomendada
para quien mantenga el código:** actualizar `theme_webshooks.json.headings`
a `{h1: 22, h2: 16, h3: 12.5}` y `cover.subtitle.size` según el medio
(12 para DOCX, 22 para PPT — dos valores, no uno, ver regla nueva de §3.2).

## 25.3 · DEFECTO-02 — estilos de Word sin rebrandear dentro de `Master.docx`

`Master.docx` trae, además de los estilos ya migrados a la paleta webshooks
(`Normal`, `Heading 1/2/3`, `Title`), un resto de estilos que conservan los
colores **default de Office** (no son colores webshooks, no están en §2):

| estilo Word | color detectado | es un color de Office, no de webshooks |
|---|---|---|
| `Subtitle` | `#4F81BD` | sí — "Accent 1" del tema Office clásico |
| `Heading 8` | `#4F81BD` | sí |
| `Heading 9` | `#404040` | sí |
| `Heading 1 Char` | `#365F91` | sí |
| `Heading 2 Char` | `#4F81BD` | sí |
| `Title Char` | `#17365D` | sí |

**Esto no es una variante de marca a documentar: es un defecto a corregir en
el archivo.** Estos estilos existen en cualquier plantilla Word nueva por
default y quedaron sin tocar cuando se armó el Master — no porque alguien
haya decidido usarlos. Ningún documento webshooks debe aplicar `Subtitle`,
`Heading 8` o `Heading 9` tal como están hoy en `Master.docx`; si hace falta
un subtítulo de portada en Word, usar el tamaño/color de §3.2 (12 pt,
Blue `#3B82F6`) aplicado manualmente hasta que se corrija el estilo en el
archivo.

## 25.4 · Confirmado correcto (sin acción)

- Wordmark: los tres fragmentos (`web`/`shooks`/`.`) con sus tres colores
  coinciden **exactamente** entre §1.1, `theme_webshooks.json` y los shapes
  reales del PPTX (`3B82F6` / `1A2744` / — el punto no se verificó como
  shape separado, pero el patrón de portada usa blanco sobre Navy, que es
  una variante de contraste válida, no una desviación).
- Paleta principal completa (§2.1): los 10 colores con sus 10 hex coinciden
  exactamente entre la guía y `theme_webshooks.json.colors` — cero
  discrepancias.
- Tipografía base: Calibri en las tres fuentes, sin excepción.
- Portada — título: 34 pt Navy en DOCX coincide con el rango 32–40 de la
  guía; 38 pt Bold en PPT también coincide, con la variante válida de color
  blanco sobre fondo Navy (no contemplada explícitamente en la letra de §3.2
  pero consistente con la regla de contraste de §4 y con el propio Master).
- KPI (`00`, PPT): 24 pt Navy con label 10 pt Gray — ambos dentro de los
  rangos de §3.2 sin necesidad de corrección.
- Footer (PPT): 8.5 pt Gray, coincide con el rango de Caption.
- Tablas del `Master.docx` (§11): la tabla de estilo `Table Grid`
  ("04. Tabla técnica", 4×4) tiene header en texto blanco bold — coincide
  con "header Navy / texto blanco" — y cuerpo en `#3A4458`, que es
  exactamente el color `Body` de §2.1. La tabla de KPIs (2×3, estilo
  `Normal Table`) usa `#1A2744` bold para el valor y `#6B7589` regular para
  el label, igual que §3.2. **No se verificó el color de relleno (fill) del
  header** — `python-docx` no lo expone de forma directa y no se bajó a XML
  crudo en este pase — así que "header Navy" queda confirmado solo en el
  texto (blanco), no en el fondo.

## 25.5 · Cobertura real del catálogo T01–T35 en `Master.pptx`

El Master tiene 12 diapositivas. Mapeadas contra el catálogo de §6:

| slide | template | ¿coincide con el patrón descrito? |
|---|---|---|
| 1 | T01 Portada | sí |
| 2 | T02 Resumen ejecutivo | sí — 3 KPIs (máximo permitido: 6) |
| 3 | T03 Arquitectura end-to-end | sí — patrón exacto "Fuentes → Ingesta → Procesamiento → Modelo → Publicación" |
| 4 | T04 Arquitectura por capas | sí — Consumo/Aplicación/Modelo/Datos/Ingesta + barra "Gobierno transversal" |
| 5 | T06 Diagrama de procesos | sí — 5 etapas + filas Fuentes/Extracción/Cálculo/Validación |
| 6 | T08 Diagrama de estados | sí — Nueva→En extracción→En revisión→Activa/Error/Inactiva |
| 7 | T11 Contrato de cálculo | sí — `ratio_id: PE` + Descripción/Insumos/Validaciones/Salida |
| 8 | T12 Familia de ratios | sí — Rentabilidad/Valuación/Solvencia/Eficiencia/Crecimiento, coincide literal con el ejemplo de §6 |
| 9 | T20 KPI / scorecard | sí — 4 KPIs con label + "unidad · objetivo · fuente" |
| 10 | T18 Roadmap / timeline | sí — 5 fases con período |
| 11 | T23 AS-IS / TO-BE | sí — dos paneles + bullets |
| 12 | (cierre, PPT-01 paso 10) | no es un template T-xx; es el cierre de la secuencia PPT-01 §15 |

**11 de 35 templates tienen una diapositiva real construida y verificable.**
Los otros 24 (T05, T07, T09, T10, T13–T17, T19, T21, T22, T24–T35) existen
**solo como especificación en prosa** en esta guía — nunca se construyeron
como diapositiva, nunca se verificaron visualmente. Esto no los invalida,
pero cambia su nivel de confianza: un template con slide real es
*implementado y observado*; un template solo en prosa es *especificado, no
construido*. Dato adicional: **ninguna de las 12 diapositivas usa una tabla
nativa de PPT** (`shape.has_table` = 0 en las 12) — T21 (Tabla técnica) y
T17 (Matriz de trazabilidad), ambos inherentemente tabulares, no tienen
ningún precedente real en presentación, solo en Word.

**Acción recomendada, no ejecutada en este pase:** marcar en el catálogo de
§6 cuáles de los T01–T35 están `IMPLEMENTADO (slide real en Master.pptx)`
vs `ESPECIFICADO (solo prosa)`, para que quien use la guía sepa cuáles
puede copiar de un archivo real y cuáles tiene que construir desde cero
siguiendo la descripción.

## 25.6 · Qué sigue sin auditarse

Iconografía (§4.5) contra qué iconos existen realmente en
`docs/webshooks/brand/` (no se abrió esa carpeta en este pase); el
contenido de `Webshooks_Template_Master.pdf` (no se pudo renderizar en este
entorno — falta `poppler-utils`); el color de **relleno** del header de
tabla en DOCX (ver nota en §25.4); y la coherencia de `DOC-01`…`DOC-05` y
`PPT-01`…`PPT-03` (§14–15) contra las secciones reales del `Master.docx`
más allá de las 6 secciones muestreadas al abrir el archivo. Quedan como
verificación pendiente, no como "ya confirmado".

---

**webshooks. — datos con sentido**
