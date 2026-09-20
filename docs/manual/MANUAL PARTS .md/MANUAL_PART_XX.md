# ANEXO C · PLANTILLAS DE DIAGRAMAS (MERMAID)

Este anexo contiene **plantillas editables** de diagramas para usar en cualquier
documento del proyecto (manual, runbooks, presentaciones, propuestas). Cada plantilla
está en formato **Mermaid** (`.mmd`), listo para editar y versionar, y se renderiza a
imagen con la paleta de marca (navy/azul/naranja).

## Carpeta y comando de regeneración

Las plantillas fuente viven en `docs/diagramas/plantillas/`:

```text
plantilla_pipeline.mmd       → pipeline E2E
plantilla_proceso.mmd        → proceso con decisiones
plantilla_flujo.mmd          → flujo temporal (secuencia)
plantilla_estados.mmd        → diagrama de estados
plantilla_arquitectura.mmd   → arquitectura por capas
plantilla_bloques.mmd        → diagrama de bloques / módulos
```

Para regenerar las imágenes del manual (PNG en `docs/manual/images/plantillas/` y SVG
junto a la fuente) con **mermaid-cli** usando el Edge del sistema:

```bash
mmdc -i plantilla_proceso.mmd -o ../manual/images/plantillas/plantilla_proceso.png \
     -p puppeteer-config.json -b white -w 1600
mmdc -i plantilla_proceso.mmd -o plantilla_proceso.svg \
     -p puppeteer-config.json -b white -w 1600
```

También se pueden editar online en <https://mermaid.live> pegando el contenido `.mmd`
y exportar a PNG/SVG directamente.

> **Tipo de plantilla → cuándo se usa:** elegí `pipeline` cuando el foco es la
> cadena de etapas; `proceso` cuando hay decisiones y gates; `flujo` para
> interacción temporal entre actores/sistemas; `estados` para ciclos de vida de
> una corrida o un job; `arquitectura` para capas; `bloques` para módulos y sus
> interfaces.

## Plantilla pipeline — Figura 6

Cadena de etapas de un proceso E2E (fuentes → ingesta → proceso → salida). Útil para
Secuencia de jobs tipo S00 → S04 → ratios, o tramos CNV.

![Figura 6 · Plantilla pipeline E2E](images/plantillas/plantilla_pipeline.png)

```mermaid
%% plantilla_pipeline.mmd
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#1A2744","primaryTextColor":"#FFFFFF","lineColor":"#3B82F6","secondaryColor":"#DCEAFF","tertiaryColor":"#E7F7EC","fontFamily":"Calibri","fontSize":14}}}%%
flowchart LR
    subgraph FUENTES["1 · Fuentes"]
        A1["SEC / EDGAR (XBRL)"]
        A2["CNV (HTML)"]
        A3["Market / TIKR"]
    end
    subgraph INGESTA["2 · Ingesta"]
        B1["Descarga + hash"]
        B2["RAW + metadatos"]
    end
    subgraph PROCESO["3 · Proceso"]
        C1["Parsing"]
        C2["Normalización"]
        C3["Ratios"]
    end
    subgraph SALIDA["4 · Salida"]
        D1["Gobernanza / provenance"]
        D2["Certificación"]
        D3["Consumidores"]
    end
    FUENTES --> INGESTA --> PROCESO --> SALIDA
```

## Plantilla proceso — Figura 7

Flujo con decisiones (`¿Permiso?`, `¿Gate PASS?`) y ciclos de rollback. Útil para
explicar cualquier procedimiento operativo del manual.

![Figura 7 · Plantilla proceso con decisiones](images/plantillas/plantilla_proceso.png)

```mermaid
%% plantilla_proceso.mmd
flowchart TD
    ST(("Inicio")) --> P1["Instrucción / evento"]
    P1 --> Q1{"¿Permiso para correr?"}
    Q1 -- "Sí" --> P2["Ejecutar paso"]
    Q1 -- "No" --> E1[("Bloqueado")]
    P2 --> P3["Validar resultados"]
    P3 --> Q2{"¿Gate PASS?"}
    Q2 -- "Sí" --> P4["Certificar"]
    Q2 -- "No" --> P5["Rollback / troubleshooting"]
    P4 --> FIN(("Fin"))
    P5 --> P2
```

> **Regla del permiso:** el nodo `¿Permiso para correr?` representa el parámetro
> `--permiso` / la regla de no escribir en 5432 sin `ENGINE_ALLOW_PROD=1`.

## Plantilla flujo (secuencia) — Figura 8

Interacción temporal entre actores y sistemas. Útil para explicar cómo orquesta un
paso del engine, con lecturas/escribas y fallbacks.

![Figura 8 · Plantilla flujo secuencial](images/plantillas/plantilla_flujo.png)

```mermaid
%% plantilla_flujo.mmd
sequenceDiagram
    actor U as Usuario / Orquestador
    participant M as Motor
    participant DB as PostgreSQL
    participant C as Caché / TIKR
    U->>M: Paso del pipeline
    M->>DB: Leer estado / fixtures
    DB-->>M: Datos de entrada
    M->>M: Parsear + normalizar
    M->>C: Pedir dato externo
    C-->>M: Respuesta (o fallback)
    M->>DB: Escribir resultado + provenance
    M->>U: Reporte de salida (gate)
```

## Plantilla estados — Figura 9

Ciclo de vida de una corrida o un job. Útil para los estados de `engine.runs`
(Pendiente → Corriendo → OK / Abortado / Bloqueado) o de los tramos CNV.

![Figura 9 · Plantilla diagrama de estados](images/plantillas/plantilla_estados.png)

```mermaid
%% plantilla_estados.mmd
stateDiagram-v2
    direction LR
    PENDIENTE: Pendiente
    CORRIENDO: Corriendo
    OK: OK (PASS)
    ABORTADO: Abortado
    BLOQUEADO: Bloqueado
    [*] --> PENDIENTE
    PENDIENTE --> CORRIENDO: arranca
    CORRIENDO --> OK: gate PASS
    CORRIENDO --> ABORTADO: error / timeout
    CORRIENDO --> BLOQUEADO: falta permiso
    OK --> [*]
    ABORTADO --> [*]
    BLOQUEADO --> [*]
```

## Plantilla arquitectura — Figura 10

Arquitectura por capas (fuentes → ingesta → persistencia → lógica → salida). Útil para
los capítulos de arquitectura y despliegue.

![Figura 10 · Plantilla arquitectura por capas](images/plantillas/plantilla_arquitectura.png)

```mermaid
%% plantilla_arquitectura.mmd
flowchart TB
    subgraph CAPA1["Capa 1 · Fuentes"]
        A1["SEC EDGAR"]
        A2["CNV"]
        A3["Market"]
    end
    subgraph CAPA2["Capa 2 · Ingesta"]
        B1["Descarga"]
        B2["RAW"]
    end
    subgraph CAPA3["Capa 3 · Persistencia"]
        C1[("PostgreSQL 5432 prod / 5433 dev")]
        C2[("SQLite")]
    end
    subgraph CAPA4["Capa 4 · Lógica"]
        D1["Engine + jobs"]
        D2["Ratios"]
    end
    subgraph CAPA5["Capa 5 · Salida"]
        E1["API / Reportes"]
        E2["Golden runs"]
    end
    CAPA1 --> CAPA2 --> CAPA3 --> CAPA4 --> CAPA5
```

## Plantilla bloques — Figura 11

Módulos y sus interfaces (entradas/salidas). Útil para explicar el flujo de datos
entre componentes sin entrar en la secuencia temporal.

![Figura 11 · Plantilla diagrama de bloques](images/plantillas/plantilla_bloques.png)

```mermaid
%% plantilla_bloques.mmd
flowchart LR
    M1["Módulo Ingesta"]
    M2["Módulo Parser"]
    M3["Módulo Normalizador"]
    M4["Módulo Ratios"]
    M5["Módulo Market"]
    I1["(datos crudos)"] --> M1 --> M2 --> M3 --> M4
    M3 -. ratios base .-> M4
    M5 --> M4
    M4 --> O1["(dataset final)"]
```