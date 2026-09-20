# 08 — DELETE PLAN (candidatos, SIN ejecutar) — BYMAStocks

> Fase 1: solo se documentan candidatos. Nada se borra. Cada borrado futuro debe cumplir los 10 pasos de la regla de seguridad (dependencia real, ownership, duplicación semántica, comportamiento, consumidores, impacto, alternativa, plan de migración, verificación, certificación).

## 1. Candidatos "duplicación nominal" (confirmar con diff)

Estos requieren diff real (B> neutral): si el contenido es idéntico o es solo referencia-readme, pasa a DELETE; si es fork con divergencia, pasa a MERGE.

| Grupo | Archivos | Riesgo si no se verifica |
|---|---|---|
| ref de cálculo | docs/calculos-financieros/codigo-referencia/{ratios,sec_edgar,02_descargar_datos,03_calcular_ratios,03_descargar_financials_sec,05_calcular_ratios,07_calcular_ratios}.py | pueden ser snippets informativos |
| research | _research/scripts/{03_descargar_financials_sec,05_calcular_ratios}.py vs ref igual | duplicado |
| tickets dedup | tickets/{cnv,screener}/_diag_db.py, _diagnostico.py | util repetida |
| schema research | _research/schema/001_initial_schema.sql vs migrations/001 | copia |

`VERIFICADO POR CÓDIGO` (búsqueda nominal). **NO tratado como certeza de idénticos.**

## 2. Candidatos "legacy superado" (depende de consolidación R6-R8)

- `scripts/pipeline/f1_identidad.py` (si identity_v1 ocupa) → DEPRECATE.
- `scripts/pipeline/f3_normalizar_cnv.py` (dead por fuentes) → ARCHIVE.
- `scripts/pipeline/f4_ratios.py` (duplicado ratio_engine) → DEPRECATE/MERGE.
- `scripts/pipeline/f6_sec.py` (mezcla 3 capas) → REWRITE, no delete.
- `scripts/screener/07_calcular_ratios.py` pruebs vs tickets.

## 3. Candidatos de infraestructura peligrosa (decision owner)

- `deploy.py` (secretos root): NO elimina: sanear credenciales; solo borrar si se deduplica con `deploy.sh`/`sync_prod`.
- `tmp_byma3.py`, `tmp_byma_audit.py` (rutas D:\): ARCHIVE (basura).
- `audit_cnv_coverage.py`, `test_local.py`: herramientas internas; mantener en 09.

## 4. Aplicando regla de seguridad a cada borrado

Antes de que un ítem entre en DELETE definitivo, debe tener completos los 10 pasos. Esta tabla es el checklist y queda VACIA hasta fase 8:

| Ítem | 1 dep | 2 ownership | 3 dup sem | 4 comportamiento | 5 consumidores | 6 impacto | 7 alternativa | 8 plan mig | 9 verif | 10 cert | DECISIÓN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _diag_db.py | PEND | PEND | PEND | N/D | N/D | N/D | N/D | N/D | N/D | N/D | NO |

## 5. Conclusión

El DELETE es el ÚLTIMO paso (fase 8), nunca ahora. Solo queda registrado como backlog con evidencia de riesgo.