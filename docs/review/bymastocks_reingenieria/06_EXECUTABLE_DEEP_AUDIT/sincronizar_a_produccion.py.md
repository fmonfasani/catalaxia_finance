# scripts/deploy/sincronizar_a_produccion.py — FICHA DEEP AUDIT

> FORMATE OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 18_INFRA / PLANO EJECUCIÓN (sincronización local→producción). [VERIFICADO POR CÓDIGO — sincronizar_a_produccion.py:130-168, sube a PostgreSQL de producción vía ssh/docker; census CDD031].
SECUNDARIAS: 12_PUBLICACION (las tablas que sirve la API: validaciones, certificacion_nueva, ratios_cnv, etc.) [VERIFICADO POR CÓDIGO — PLAN 73-83 incluye silver_norm, validaciones, certificacion_nueva]; capa DATOS vía DELETE+INSERT [VERIFICADO POR CÓDIGO — 141-144].

PLANOS →
- DATOS: lee SQLite local `screener.db` [61]; exporta CSV con centinel NULL `@@NULL@@` [69, 104-127]; escribe en PostgreSQL de producción las tablas del PLAN (reemplazo o upsert) [73-83, 141-151].
- CONTROL: verificación POR CONTEO local vs producción tras commit [VERIFICADO POR CÓDIGO — 145-168]; dry-run [135-136]; `ON_ERROR_STOP` + transacción BEGIN/COMMIT [145-151]; documentación explícita del porqué no usar TRUNCATE ciego y de tragedias previas (12 columnas vacías, duplicado 190.737) [VERIFICADO POR CÓDIGO — header 1-47].
- EJECUCIÓN: scp + ssh → docker cp → docker exec psql [96-101, 137-139]; CLI --tabla/--todas/--dry-run [171-195]; usa env con defaults para host/usuario/contenedor/pguser/pgdb [63-67].
- INFRA: destinos SSH `89.167.96.239` root (default; env CATALAXIA_HOST/USER) [63-64]; contenedor `catalaxia-db`; PG `catalaxia`; sin secretos hardcodeados de BD (vía env/psql en contenedor) [65-67].

CICLO →
- DEFINIR: header con estrategias upsert/reemplazo y su cuándo [VERIFICADO POR CÓDIGO — 17-28].
- IMPLEMENTAR: exportación→stage→DELETE+INSERT o INSERT ON CONFLICT→verify [104-168].
- VERIFICAR: conteo post-commit (final==local) [155-168]; DRY-RUN disponible [135-136, 175].
- CERTIFICAR: NO — la "verificación" concluye por conteo, no certifica contenido semántico [VERIFICADO POR CÓDIGO — 155-168 vs ausencia de otro control].

HOY → Sincroniza 7 tablas desde SQLite local hacia PostgreSQL de producción con dos estrategias (reemplazo transaccional o upsert), con verificación de conteo y dry-run. Sabidamente evita TRUNCATE ciego y documenta por qué. [VERIFICADO POR CÓDIGO]
OBJETIVO → En el harness, la sincronización a producción debe ser capa de EJECUCIÓN con gates (validación/certificación de la fuente ANTES del envío), transaccionalidad REAL del lado destino (lo tiene) y verificación por contenido/digest, no solo conteo; los secretos deben venir de un secreto manager, no de defaults en código. [VERIFICADO POR CÓDIGO — mejoras identificadas]
DEPENDENCIAS → local: data/screener.db (7 tablas); remote: scp/ssh a 89.167.96.239 root, contenedor catalaxia-db, psql -U catalaxia -d catalaxia; env CATALAXIA_HOST/USER/DB_CONTAINER/PG_USER/PG_DB; filesystem temporal /tmp/_sync_*.sql y CSV temp.

CONTRATO → INPUT: `--tabla NOMBRE | --todas | --dry-run` (si sin args, imprime ayuda, no toca nada [179-183]). OUTPUT: tablas de producción sincronizadas + mensajes de verificación. PRECONDICIONES: conexión SSH/docker al contenedor; tabla en PLAN; claves remotas. POSTCONDICIONES: % tablas del PLAN en producción == local; si el INSERT falla, el DELETE se deshace (transacción). INVARIANTES: I-008 IDEMPOTENCIA: PARCIAL — reemplazo vuelve a producir el mismo estado (idempotente en resultado); upsert ON CONFLICT DO NOTHING idempotente; pero NINGUNO garantiza determinismo de orden ni contenido. I-006 PROVENANCE: AUSENTE en la transferencia (no registra origen/fingerprint/run en destino).

RIESGOS →
1. DESCRUZAR PRODUCCIÓN CON DEFAULTS: host/usuario root por defecto en código (63-64), pudiendo apuntar a producción real aunque no se quiera (salvo --dry-run); aunque NO hay password hardcodeada, el default `root@89.167.96.239` es una superficie alta. [VERIFICADO POR CÓDIGO — 63-67]
2. VERIFICACIÓN SOLO POR CONTEO: el propio script documenta el caso en que 572==572 pero la data era incorrecta; el conteo final==local no valida contenido ni columnas vacías ni duplicados semánticos. [VERIFICADO POR CÓDIGO — header 8-15 + 155-168]
3. `DELETE FROM tabla; INSERT ...` sobre tablas con PK vacía/débil y reemplazo de tablas clave de publicación (silver_norm, validaciones, certificacion_nueva) sin gate de certificación previa de la fuente. [VERIFICADO POR CÓDIGO — PLAN 73-83, 141-144]
4. `shell=True` en subprocess para todas las operaciones remotas [86-88, 96-101, 137-139] con valores que los defaults permiten manipular vía env — riesgo de inyección si los env se contaminan (énfasis teórico; no vi caso real).
5. sin manejo de error explícito sobre fallo de scp/ssh: captura stdout+stderr pero nunca comprueba returncode de los saltos [96-101]; un fallo silencioso se reflejaría en el conteo, ok, pero no hay log estructurado de errores.

DECISIÓN → (FASE 1: NO ejecutar nada). KEEP con condiciones. Tiene transaccionalidad y dry-run (bien), pero requiere: (a) exigir gate de certificación de las tablas fuente antes del envío; (b) verificación por digest/contenido además de conteo; (c) quitar defaults a producción y usar secret manager; (d) chequear returncodes de la cadena scp/ssh.

EVIDENCIA → VERIFICADO POR CÓDIGO: sincronizar_a_produccion.py:60-61 (ROOT/DB); :63-67 (defaults host/user/cont/PG); :69 (NUL); :73-83 (PLAN con PK); :86-101 (sh/psql cadena docker); :104-127 (exportar, centinela/empty); :130-168 (sincronizar: dry 135, cuerpo 141-151, verify 155-168); :171-195 (main, sin args → ayuda/build 179-183). VERIFICADO POR EJECUCIÓN: NO DETERMINABLE (no tengo logs de corrida en snapshot). VERIFICADO POR CÓDIGO referencia histórica en header: tragedia 12 columnas/572==572, duplicado 190.737 [1-47]. NO DETERMINABLE: certificación previa de tablas fuente en producción.

ESTADO: PASS_WITH_WARNINGS (transaccional y con dry-run; pero default root@prod, verificación por conteo y sin gate de certificación posterior → corregir antes de uso en CI).