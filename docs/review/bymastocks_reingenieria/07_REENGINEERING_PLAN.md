# 07 — RE-ENGINEERING PLAN (orden recomendado) — BYMAStocks
Estado: FASE 1 (auditoría) + definición de contratos objetivo. Sin ejecución.

## 0. Orden de trabajo responde a la fase 1 solicitada

Dado que la orden de prioridad del harness dice: Execution Graph → Dependency Graph → Data Ownership → Pipeline Real → Duplication Map → Deep Audit → definición de contratos → reingeniería → verificación → certificación → recién DELETE/MERGE, **en esta entrega concluimos 01-05 y deep audit (06)**. El plan 07 es el mapa de la fase DEFINIR hacia adelante.

## 1. Hallazgos que gobiernan el orden

1. **No hay capa 11 real**: validar_suite y f6_sec autocertifican. Es el bloqueante arquitectónico nº1 de PUBLICACIÓN.
2. **3 dominios paralelos** (engine, pipeline legacy, screener tickets) duplican identidad y ratios.
3. **RAW es borrable** en run_update (I-001 violado).
4. **41 % del código fuera de git** (253 archivos) → fijar baseline primero.
5. **API y run_all no gatean certificación** → riesgo de publicar incompleto como ok.
6. **Secretos en deploy.py**:27 y sincronizar:63-64.

## 2. Prioridad de reingeniería propuesta

### P0 — gobierno (sin estos no hay reingeniería segura)
- R1. Fijar baseline de tracking git (git add de los 253; proteger `.env`, `data/`, documentos). **REQUIERE decisión del owner**.
- R2. Sanear secretos sin lógica: reemplazar credenciales hardcodeadas por env/secret manager (deploy.py:26-27, sincronizar:63-64).
- R3. Hacer I-001 no negociable: eliminar path de borrado de RAW en run_update.py:297-300; convertir a re-descarga versionada.

### P1 — capa de certificación (gate de PUBLICACIÓN)
- R4. Crear la capa 11 independiente: lee `engine.stage_runs` + assertions; emite certificación por corrida. Esto desacopla a validadores del cálculo.
- R5. Gatear `api` (publica screener solo con certificación satisfactoria) y `gen_screener_html`.

### P2 — consolidación de dominios
- R6. Unificar identidad: hacer `engine/identity_v1.py` fuente de verdad; deprecar f1_identidad y construir_*.
- R7. Unificar ratios: `scripts/engine/ratio_engine` como único; retirar f4_ratios.
- R8. Unificar pipeline: engine s00..s04 como único flujo; retirar pipeline legacy (f1..f6).

### P3 — nivelación por capas (07/08/09)
- R9. Completar FINANCIAL MODEL (07) y PROVENANCE (09) en el engine; documentar `ratio_inputs`/`ratio_defs` como contrato de capa 08.

### P4 — higiene
- R13. Ya en fase 08/09: DELETE de duplicados nominales; MERGE de duplicados de dominio.

## 3. Orden sugerido de tareas (secuencia)

```
1. R1 git baseline           (owner + git)
2. R2 y R3 secretos + RAW    (solo con permiso del owner)
3. R4 capa 11                (bloqueante lógico)
4. R5 gate publicación
5. R6 identidad unificada
6. R7 ratios unificados
7. R8 pipeline unificado
8. R9 07/08/09 contrato
9. R13 DELETE/MERGE
```

## 4. Riesgos del propio plan

- Consolidar identidad antes de tener la capa 11 puede dejar datos sin certificar.
- Retirar pipeline legacy sin migrar sus 6 outputs rompe `api /v1`.
- Cambiar `engine/config.py` (hub 67 in) sin tests rompe decenas de consumidores.

## 5. Regla de no-ejecución

Este plan NO se ejecuta en esta fase. Cada R tiene un checklist con: contratos, evidencia, verificabilidad, y gates de paso. Ver 08_DELETE y 09_MERGE para lo específico de eliminación/fusión.