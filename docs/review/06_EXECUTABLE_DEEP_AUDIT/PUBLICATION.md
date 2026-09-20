# Ficha: PUBLICATION — s5, sync, migrate, publicar_v2, api

### COMPONENTE: s5_exportar.py (EXPORT a CSV/JSON)
- Lee `screener` (SQLite, env SCREENER_DB); validación final (cross-checks cobertura/rangos); escribe `data/screener_export.csv` + `.json` (OUT/OUT_JSON). Entry `build` (invocado por `__import__` en rebuild/assemble).
- Destructividad: overwrite de artefactos (reversible por re-ejecución). Idempotencia: VERIFICADA (mismo input → mismo CSV).
- PRODUCTIVO CONFIRMADO (artefacto 256 KB en disco). Riesgo R1 (export sin gate de certificación — ver §15 índice).

### COMPONENTE: sincronizar_a_produccion.py (SQLite→PG, 7 tablas)
- PLAN reemplazo transaccional (DELETE+INSERT vía staging COPY) para cnv_estados_norm, cnv_estados_v2, ratios_cnv, silver_norm, validaciones, certificacion_nueva, dolarito_cotizaciones. **No toca `screener` ni `facts`** (:212). SSH+docker+psql (sh con shell=True, scp de SQL temporal).
- Seguridad: acceso SSH a producción con usuario/host de config; SQL por archivo temporal (unlink tras uso). Credenciales por env (DB_PASSWORD/POSTGRES_PASSWORD referenciados, no hardcodeados). Riesgo R2 (acceso prod + shell=True localizado).
- PRODUCTIVO PROBABLE (manual). **Riesgo: R3 — ALTO** (escribe PG prod con reemplazo; sin dry-run verificado en extracto; mitigation: transacción única por tabla).

### COMPONENTE: migrate_sqlite_to_pg.py (full copy, TRUNCATE+swap)
- Copia TODAS las tablas screener.db→PG con precondición (aborta si falta tabla/columna en destino; swap atómico). Docstring de sync lo desaconseja (tabla vacía en prod si falla el INSERT).
- Único writer verificado de PG `screener` → PRODUCTIVO PROBABLE (por necesidad, no por schedule). **Riesgo: R4 — CRÍTICO** (TRUNCATE en producción + único camino al producto API; cualquier fallo deja `screener` vacía; mitigación parcial: precondición + swap).

### COMPONENTE: publicar_screener_v2.py (+ publicar_v2_cagr_roe.py)
- Lee screener.db (RO en cagr_roe: `mode=ro`); escribe PG `screener_v2` (DESTINO fijo :63, CREATE+execute_values) con `--dry-run`. cagr_roe escribe staging `_carga`.
- `screener_v2` sin lector en api → publicado-sin-lector. PRODUCTIVO: NO-DETERMINABLE (capacidad verificada, uso no). Riesgo R1 (dry-run disponible; destino separado).

### COMPONENTE: api/main.py (lectura PG prod)
- FastAPI + psycopg2; lee `screener`, `screener_hist` (writer ND), `silver_norm`; env API_HOST/PORT; CORS middleware. Sin escritura.
- Seguridad: solo lectura; superficie HTTP (auth `[NO-DETERMINABLE]` en extracto — verificar ante Paso 7). Riesgo R2 (sirve `screener_hist` sin producer conocido + auth no verificada).

### ANEXO: load_screener_ratios.py / materia_prima sync
- load: `screener_ratios(_hist)` en SQLite (histórico local). materia_prima produce silver/validaciones/certificación (ver C11.md anexo). Complementarios, no duplicados (D8).

### Contratos / Ocultas / Ownership / Duplicación
- s5: contratos IMPLEMENTADOS. sync: ERROR PARCIAL (sin dry-run verificado). migrate: STATE con precondición (PARCIAL). api: AUTH ND.
- Ocultas: SSH/host prod en config de sync; `SCREENER_DB` redirige origen; swap atómico en migrate.
- Ownership coherente con 03 §11/§12. Duplicación 05 G5/G17: CONFIRMA D6 parcial + D8.
