# PROMPT_CONTRATO_EXTRACCION.md

> Prompt guardado el 2026-08-22. Define la tarea "preparar el contrato técnico de la
> extracción y del pipeline ANTES de ejecutar nuevas descargas". Se guarda textual;
> su ejecución vive en `CONTRATO_TECNICO_EXTRACCION.md`.

---

# Contexto y Rol

Actúa como Data Architect financiero.

## Consulta/Tarea

Preparar el contrato técnico de la extracción y del pipeline antes de ejecutar nuevas descargas.

Analiza el repositorio completo y la documentación existente, especialmente:

- EXTRACTION_SPECIFICATION.md
- PROVENANCE_SPECIFICATION.md
- DATA_CONTRACT_EXTRACTION.md
- EXTRACTION_CHECKLIST.md
- DO_NOT_REPEAT.md
- EXTRACTION_KNOWLEDGE_BASE.md
- PIPELINE_VALIDATION_SPECIFICATION.md

También analiza los scripts actuales de extracción, transformación y auditoría.

## Especificaciones

Determina:

1. Universo objetivo.
2. Empresas objetivo.
3. Identificadores canónicos.
4. Fuentes por tipo de dato.
5. Datos necesarios para cada uno de los 13 ratios.
6. Historial requerido.
7. Fecha de corte.
8. Periodicidad.
9. Moneda.
10. Unidad.
11. Calendario fiscal.
12. Política de datos faltantes.
13. Política de restatements.
14. Política de fuentes contradictorias.
15. Provenance requerida.
16. RAW requerido.
17. Checkpoints necesarios.

Construye una matriz:

```
ratio → inputs → fuente primaria → fuente secundaria → período → unidad → moneda → fórmula → validación → benchmark externo
```

No programes extracción todavía si algún contrato crítico está indefinido.

## Criterios de Calidad

No asumir que TIKR, SEC, CNV o yfinance tienen exactamente la misma metodología.

Identificar explícitamente diferencias metodológicas.

## Formato de Respuesta

Entregar:

1. contrato final;
2. matriz de inputs;
3. gaps;
4. riesgos;
5. decisiones necesarias;
6. criterio GO / NO-GO para comenzar extracción.
