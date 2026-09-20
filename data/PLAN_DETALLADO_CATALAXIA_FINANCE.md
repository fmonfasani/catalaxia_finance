# PLAN DETALLADO — CATALAXIA FINANCE

## Objetivo
Construir un dataset financiero histórico de 5–6 años mínimos (objetivo 7 años), con precios diarios, 13 métricas, provenance completo, quality gates, certificación y snapshots reproducibles.

## Arquitectura
Universo/Identidad → RAW inmutable → Normalización → Modelo financiero histórico → Market Data → Motor de métricas → Quality/Certification → Snapshot → Publicación.

## Fases
1. Congelar metodología de las 13 métricas.
2. Congelar universo e identidad.
3. Extraer RAW con hashes, timestamps y `download_log`.
4. Normalizar unidades, moneda y calendario sin perder valores originales.
5. Construir modelo histórico FY/Q/TTM.
6. Construir histórico diario de mercado.
7. Implementar motor determinista de 13 métricas.
8. Unificar s5/s6/s8/s9/b0-b9 en Quality Engine.
9. Implementar provenance de documento/hecho/transformación/cálculo/publicación/snapshot/código.
10. Comparar contra TIKR como benchmark, sin usarlo como fuente primaria.
11. Generar snapshot inmutable.
12. Publicar snapshot a PostgreSQL/API.
13. Automatizar con un único entry point.

## Política de faltantes
- Nunca inventar ni convertir NULL en 0.
- Si falta un input: `MISSING`/`NOT_CERTIFIED`.
- Si la empresa tiene menos de 5 años: no certificar métricas 5Y.
- Si falta FX: bloquear conversiones dependientes.
- Si yfinance falla: conservar último dato con `STALE`, no parchear silenciosamente.
- Si hay ticker ambiguo: bloquear instrumento afectado.
- Si TIKR no está disponible: no afecta el cálculo propio; benchmark queda `MISSING`.
- Si hay contradicción metodológica: bloquear la métrica hasta resolverla.
- RAW siempre inmutable; correcciones se versionan.

## Snapshot
Cada snapshot debe registrar `snapshot_id`, `snapshot_at`, `data_as_of`, `market_as_of`, `universe_version`, `pipeline_version`, `git_commit`, versiones de fuentes y estado general.

## Gates
Universe → RAW → Normalización → Cobertura histórica → Market → Métricas → Quality → Provenance → Snapshot → Publicación.

## Piloto
Antes de migrar todo el universo, probar 6–10 empresas representativas: industrial BYMA, banco, energética, ADR argentino, empresa con faltantes, empresa con unidad problemática, empresa con dividendos y empresa con cambios de ticker.

## Entry points
```bash
python pipeline.py snapshot
python pipeline.py snapshot --as-of YYYY-MM-DD
python pipeline.py rebuild --from YYYY-MM-DD
python pipeline.py validate
python pipeline.py benchmark
python pipeline.py publish --snapshot SNAP-ID
```

## Definición de éxito
Una corrida genera una foto reproducible, histórica, trazable y certificada; los faltantes degradan explícitamente el resultado y no contaminan silenciosamente el dataset.
