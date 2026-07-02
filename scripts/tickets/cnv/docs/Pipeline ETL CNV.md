Pipeline actual del ETL de Estados Financieros de
la CNV
Objetivo
El objetivo del proyecto es construir un pipeline completamente automático capaz de descargar y
transformar todos los Estados Financieros publicados por la Comisión Nacional de Valores (CNV)
Argentina en un dataset estructurado.
El resultado final será una base histórica propia de balances argentinos, almacenada en formato
Parquet y lista para análisis financieros, screening de empresas, modelos cuantitativos y futuros
productos de Catalaxia Finance.
¿Qué publica realmente la CNV?
La CNV no publica un archivo único con todos los balances.
Lo que existe es un sistema web compuesto por:
Empresas
Presentaciones realizadas por cada empresa
Distintos tipos de documentos
Estados financieros
Comunicados
Actas
Nóminas
Prospectos
Informes varios
Los Estados Financieros son solamente una pequeña parte de todas esas presentaciones.
Por eso el principal desafío del proyecto fue descubrir cuáles documentos corresponden realmente a
balances.
Pipeline completo
Paso 1 — Obtener todas las empresas
La CNV posee un endpoint denominado AutoComplete.
https://www.cnv.gov.ar/SitioWeb/Empresas/AutoComplete
• 
• 
• 
• 
• 
• 
• 
• 
• 
1


Este endpoint devuelve todas las empresas registradas en la CNV.
Para cada empresa se obtiene información como:
nombre
CUIT
ticker
identificadores internos
Esta información se almacena en:
datos/empresas.csv
En la actualidad se obtienen aproximadamente 556 empresas.
Paso 2 — Descubrir todas las presentaciones
Cada empresa posee una página pública:
https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/{CUIT}
Dentro del HTML de esa página aparecen todos los identificadores (GUID) de las presentaciones
históricas realizadas por esa empresa.
Estos GUID identifican de manera única cualquier documento presentado ante la CNV.
Mediante una expresión regular se extraen todos esos GUID.
El resultado actual es aproximadamente:
79.772 presentaciones
Cada presentación queda registrada en:
datos/links.csv
Cada registro contiene:
ticker
empresa
CUIT
GUID
URL pública
Hasta este punto todavía no sabemos cuáles son balances.
• 
• 
• 
• 
• 
• 
• 
• 
• 
2


Paso 3 — Analizar cada presentación
Cada GUID puede abrirse mediante la URL:
https://aif2.cnv.gov.ar/presentations/publicview/{GUID}
Esta página contiene el documento presentado.
Durante la ingeniería inversa se descubrió que el HTML posee variables JavaScript extremadamente
importantes.
Entre ellas:
presentationIdGlobal
formTypeId
formTypeName
Estos tres datos permiten identificar el tipo de documento sin necesidad de descargar archivos PDF.
Para cada presentación se extraen:
presentationId
formTypeId
formTypeName
Paso 4 — Construcción del catálogo de formularios
Al analizar miles de documentos comenzaron a aparecer distintos tipos de formularios.
Por ejemplo:
Estados Contables NIIF
Estados Contables Comerciales
Balance Consolidado
Balance Subsidiaria
Prospectos
Nómina de Directores
Hechos Relevantes
Avisos
Comunicados
Cada formulario posee un identificador propio ( formTypeId ).
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
3


Con esta información se construyó automáticamente un catálogo:
catalogo_formtypes.csv
El objetivo del catálogo es indicar cuáles formularios corresponden realmente a Estados Financieros.
Cada tipo queda marcado como:
es_eeff = 1
o
es_eeff = 0
Este catálogo evita tener que inspeccionar nuevamente miles de documentos en futuras ejecuciones.
Paso 5 — Filtrar únicamente los Estados Financieros
Una vez construido el catálogo, se realiza un cruce entre:
links.csv
y
catalogo_formtypes.csv
De esta forma se eliminan automáticamente todas las presentaciones que no son balances.
El resultado es un nuevo archivo:
links_eeff.csv
Este archivo contiene únicamente documentos financieros.
Actualmente existen aproximadamente:
5.400 Estados Financieros
correspondientes a las empresas ya analizadas.
Este número crecerá a medida que finalice el análisis de todos los GUID históricos.
4


Paso 6 — Descargar los HTML
Una vez identificados los Estados Financieros comienza la descarga real.
Para cada registro de:
links_eeff.csv
se realiza una solicitud HTTP a:
publicview/{GUID}
Cada documento descargado se valida automáticamente.
La validación verifica:
HTML vacío
errores internos
mantenimiento
captcha
presencia de presentationId
Si el documento es válido se almacena localmente.
La estructura será:
eeff/
    ALUA/
        3523703.html
    TXAR/
    LEDE/
    ...
El nombre del archivo no será el GUID.
Será el:
presentationId.html
porque es el identificador estable del documento.
• 
• 
• 
• 
• 
5


Paso 7 — Auditoría automática
Una vez descargados los HTML comienza una etapa de análisis masivo.
Cada documento será inspeccionado automáticamente.
La auditoría detectará:
cantidad de tablas HTML
cantidad de filas
cantidad de columnas
scripts JavaScript
blobs
JSON embebido
XML
PDFs
modelos de datos
otros recursos presentes
El objetivo es comprender completamente cómo están construidos los documentos de la CNV antes de
desarrollar el extractor definitivo.
No se harán suposiciones sobre la estructura.
La auditoría se basa exclusivamente en los HTML reales descargados.
Paso 8 — Extracción de información financiera
Conociendo ya la estructura real de los documentos se implementará un extractor capaz de identificar
automáticamente:
Balance General
Estado de Resultados
Estado de Flujo de Caja
Estado de Evolución del Patrimonio Neto
Notas a los Estados Contables
El extractor deberá adaptarse a diferencias entre empresas y entre distintos años.
No se utilizarán reglas específicas para una empresa determinada.
El objetivo es que funcione con cualquier sociedad que publique información mediante la CNV.
Paso 9 — Normalización
Los datos extraídos de todos los documentos tendrán estructuras distintas.
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
6


Esta etapa unificará toda la información en un único modelo de datos.
Se resolverán diferencias como:
nombres de cuentas
formatos numéricos
fechas
monedas
versiones de presentación
cambios regulatorios
El resultado será una estructura uniforme para todas las empresas.
Paso 10 — Dataset final
Finalmente toda la información será almacenada en formato Parquet.
El pipeline completo producirá una base histórica similar a:
Empresa
↓
Ejercicio
↓
Balance
↓
Estado de Resultados
↓
Flujo de Caja
↓
Patrimonio Neto
↓
Notas
↓
• 
• 
• 
• 
• 
• 
7


Parquet
Este dataset será la base de Catalaxia Finance y podrá utilizarse para:
análisis financiero
indicadores
valuación de empresas
series históricas
modelos cuantitativos
machine learning
APIs
dashboards
productos financieros futuros
Estado actual del proyecto
Actualmente se encuentran terminadas las etapas de:
Descubrimiento de empresas.
Descubrimiento de presentaciones.
Clasificación automática de documentos.
Identificación de Estados Financieros.
La siguiente etapa consiste en construir un descargador robusto que obtenga automáticamente todos
los HTML de los Estados Financieros y siente las bases para la extracción automática de la información
contable.
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
• 
8
