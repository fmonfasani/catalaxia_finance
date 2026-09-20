# api/main.py — FICHA DEEP AUDIT (plantilla de referencia)

> FORMATE OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 12_PUBLICACION. [VERIFICADO POR CÓDIGO — solo lectura, sirve datos]
SECUNDARIas: 09/ARTEFACTOS v1 legacy. No calcula ratios.

PLANOS →
- DATOS: lee `screener` (45 columnas fijas), `screener_hist`, `silver_norm`, `validaciones`, `certificacion_nueva`, `mep_actual`. [VERIFICADO POR CÓDIGO — main.py:130-191, 194-247, 309-404]
- CONTROL: columnas FIJAS sin SELECT * (contrato público deliberado); jobs v2 en memoria SIN persistencia; handler global de errores con CORS. NO escribe.
- EJECUCIÓN: entrypoint `uvicorn main:app`; sin checkpoints, sin retries, sin timeouts propios. [NO DETERMINABLE — sin evidencia de ejecución automatizada]
- INFRA: psycopg2→PostgreSQL vía env DB_HOST/PDB_PORT/DB_NAME/DB_USER/DB_PASSWORD con default `catalaxia` (password hardcodeada por default). Docker. Red (API pública).

CICLO →
- DEFINIR: contrato v2 explícito (45 columnas) [VERIFICADO POR CÓDIGO].
- IMPLEMENTAR: respeta capa 12 (solo lectura, sin recálculo).
- VERIFICAR: sin tests de contrato/unitarios en repo. [VERIFICADO POR CÓDIGO — ausencia]
- CERTIFICAR: sin certificación formal registrada. [NO DETERMINABLE]

HOY → Sirve ratios desde `screener` (v2) y desde capas previas (silver_norm, validaciones, certificacion_nueva, mep_actual) por endpoint /v1 legacy. Jobs en memoria.
[OBJETIVO] → Publicar únicamente resultados certificados (CERTIFICACIÓN previa satisfactoria); congelar contrato v2; retirar /v1 legacy o reencaminarlo a capa certificada; test de contrato obligatorio.
[HOY] [VERIFICADO POR CÓDIGO]

DEPENDENCIAS → DB:screener; DB:screener_hist; DB:silver_norm; DB:validaciones; DB:certificacion_nueva; DB:mep_actual; env DB_*.

CONTRATO → INPUT: `grupo`,`sector` (Query), `skip/limit`; OUTPUT: JSON 1 fila=1 empresa, 45 columnas; INVARIANTE: PUBLICACIÓN no recalcula (I-…); PRECONDICIÓN: `screener` validada+certificada; POSTCONDICIÓN: JSON estable entre releases.

RIESGOS →
- /v1 legacy lee `silver_norm` (capa vieja sin certificación clara) [VERIFICADO POR CÓDIGO]
- jobs en memoria: estado perdido si reinicia [VERIFICADO POR CÓDIGO]
- password por defecto hardcodeada (`catalaxia`) [VERIFICADO POR CÓDIGO]
- sin tests de contrato (un ADD COLUMN rompe estabilidad) [VERIFICADO POR CÓDIGO — ausencia]

DECISIÓN → (Fase 1 — SIN EJECUTAR): KEEP. Planificar: tests de contrato → retiro /v1 → certificación de dependencias.

EVIDENCIA →
- VERIFICADO POR CÓDIGO: main.py:53-60 (get_db); main.py:130-191 (v2/screener); main.py:194-247 (hist); main.py:274-303 (stats); main.py:309-404 (legacy /v1).
- NO DETERMINABLE: certificación previa de screener_hist / silver_norm.

ESTADO: NOT_READY (sin tests ni certificación).