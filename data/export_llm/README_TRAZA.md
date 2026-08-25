# Traza 13 ratios — generada 2026-08-22 21:29

Una fila por (empresa x ratio): 728 filas, 56 empresas.
Fuente: data/byma_pipeline.db (pipeline v3, snapshot certificado).

## Columnas (capas del pipeline)
- L0_fuente_cruda: dato tal como lo declara la fuente (ratio CNV anual, partida EPS, o heredado v2)
- L1_normalizado: tras normalizacion de unidades/tickers (b1)
- L2_ttm_cobertura_ok: si la ventana TTM de la empresa esta completa (b3)
- L3_valor_final / inputs / flags: metrica calculada con formula e inputs registrados (b5)
- L4_validacion / desvio_pct: chequeo matematico independiente (b6). OK/WARN/INFO/FAIL/n/a
- L5_status / motivos: CERTIFIED o NOT_CERTIFIED + causa (b7)
- anomalias_empresa: detectores de b2 que tocan la empresa
- staleness_dias: antiguedad del precio usado

## Como detectar anomalia paso a paso
1. L4=FAIL o L5=NOT_CERTIFIED -> mirar motivo exacto
2. Si L0 existe -> comparar L3 contra L0 (ej: margen propio vs CNV declarado)
3. anomalias_empresa no vacio -> contexto de escala/identidad
4. Los 13 ratios son los de Seguimiento_original.xlsx (mismos nombres)

## Regla del proyecto
Nada se corrige a mano: anomalia -> se marca -> se decide. La certificacion
atestigua consistencia interna y provenance, no veracidad externa.
