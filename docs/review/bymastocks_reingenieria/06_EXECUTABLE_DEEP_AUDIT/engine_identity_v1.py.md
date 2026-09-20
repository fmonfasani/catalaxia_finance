# engine/identity_v1.py — FICHA DEEP AUDIT

> FORMATE OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: 02_IDENTIDAD. [VERIFICADO POR CÓDIGO — dominio de identidad puro: entidades, identifiers, assertions, bridges, instruments; docstring identity_v1.py:1-14 "escribe únicamente en el schema identity_v1"]. Resuelve identidad PUENTE CIK↔CUIT↔LEI, nunca por nombre/ticker (principio 1 filosofía).
SECUNDARIAS: 09_PROVENANCE [VERIFICADO POR CÓDIGO — cada assertion lleva source_id/source_record/quote/resolved_by/facts]; 11_CERTIFICACION [VERIFICADO POR CÓDIGO — estados VERIFIED/REVIEW_REQUIRED/CONFLICT que alimentan el gatillo de certificación posterior].

PLANOS →
- DATOS: lee/escribe SOLO schema `identity_v1` (entity, identifier, assertion, review, conflict, instrument, instrument_symbol, source, v_entity_resolution). [VERIFICADO POR CÓDIGO — identity_v1.py:202-217, 225-235, 304-313, 321-395, 544-556, 747-783, 907-926; corroborado io_tables.csv]. No toca dim_entity ni el pipeline legacy.
- CONTROL: inmutabilidad de assertions vía `supersede_assertion` con valid_to (nunca DELETE) [VERIFICADO POR CÓDIGO — identity_v1.py:887-899]; prohibición de procesos firmando decisiones humanas (F-016) con prefijo `proc:` [VERIFICADO POR CÓDIGO — identity_v1.py:48-54, 60-65]; fuente no autoritativa rechazada (UnusableSource) [VERIFICADO POR CÓDIGO — identity_v1.py:40-42, 195-217]; idempotencia explícita por fuente (F-023/F-034) [VERIFICADO POR CÓDIGO — identity_v1.py:513-535, 579-591].
- EJECUCIÓN: es una LIBRERÍA importada por drivers/tests (no tiene `if __name__ == "__main__"`; flags.csv flag=0) [VERIFICADO POR CÓDIGO / flags.csv]. Recibe `conn` del caller — no abre transacción propia ni gestiona run_scope (eso vive en engine.db).
- INFRA: sqlalchemy vía `conn` inyectado [VERIFICADO POR CÓDIGO — identity_v1.py:25 `from sqlalchemy import text`; flags.csv dbref:SQLite por heurística]. Escribe en PostgreSQL catalaxia.identity_v1.

CICLO →
- DEFINIR: contrato con evidencia obligatoria (Evidence NO es opcional), autoridad POR id_type, puente CIK↔LEI G5 solo ratificable por persona [VERIFICADO POR CÓDIGO — identity_v1.py:159-171, 195-217, 567-609, 791-884].
- IMPLEMENTAR: respeta capa 02 (identidad), sin mezclar parsing/fetching/market [VERIFICADO POR CÓDIGO — identity_v1.py:1-14; imports.csv sin requests/yfinance].
- VERIFICAR: batería de tests adversarios (test_identity_v1.py 13 tests; test_f032_no_duplicacion; test_f035_entidad_muerta; test_backfill_cik_adversarial; test_f041_reafirmacion) con TRUNCATE en transacción revertida [VERIFICADO POR CÓDIGO — tests en repo; imports.csv]. VERIFICADO POR EJECUCIÓN si corrieron: NO DETERMINABLE (no tengo evidencia de corrida en este snapshot).
- CERTIFICAR: el estado VERIFIED/REVIEW de las assertions es insumo, no certificación final [NO DETERMINABLE — nada en el módulo cierra certificación].

HOY → Librería de dominio de identidad con evidencia: resuelve entidades por identificador autoritativo, rechaza duplicación/conflicto en vez de decidir en silencio, exige persona para ratificar bridges, mantiene assertions inmutables con supercesión encadenada. [VERIFICADO POR CÓDIGO]
OBJETIVO → Ser el ÚNICO punto de resolución de identidad bajo la arquitectura canónica, consumido por S01 y por la capa CNV (vía c3_identity_link), mientras la v0 `engine/identity.py` (schema `identity`) convive sin fusionar como heredado a migrar. [VERIFICADO POR CÓDIGO — census CORE017/CORE018, coexistencia declarada]

DEPENDENCIAS → DB:identity_v1.source; DB:identity_v1.entity; DB:identity_v1.identifier; DB:identity_v1.assertion; DB:identity_v1.review; DB:identity_v1.conflict; DB:identity_v1.instrument; DB:identity_v1.instrument_symbol; DB:identity_v1.v_entity_resolution; sqlalchemy; conn inyectado por el caller.

CONTRATO → INPUT: `conn` a schema identity_v1 + entity_key/id_type/id_namespace/id_value + method + Evidence (source_id, source_record, quote, resolved_by, facts). OUTPUT: Result con status VERIFIED|CANDIDATE|REVIEW_REQUIRED|REJECTED + assertion/identifier/review/conflict ids. PRECONDICIONES: entidad existe (require_entity [identity_v1.py:416, 294-301]); fuente registrada con autoridad válida (source_authority [identity_v1.py:195-217]); Evidence completa; persona si método humano. POSTCONDICIONES: assertion insertada/encadenada; nunca dos entidades comparten un identificador autoritativo activo (barrera de dominio + índice ux_identifier_autoritativo_unico [VERIFICADO POR TEST — test_identity_v1 teste 12]). INVARIANTES: I-006 PROVENANCE (toda escritura lleva source+registro+cita+resolved_by) [VERIFICADO POR CÓDIGO]; I-007 DETERMINISMO (norm_cik/cuit/lei y clasificación deterministas; new_entity_key ULID no derivado del identificador para no romper FKs [identity_v1.py:75-89]); I-008 IDEMPOTENCIA (re-proponer misma fuente no duplica [identity_v1.py:513-535, 579-591]).

RIESGOS →
1. Convivencia de DOS implementaciones del mismo dominio (v0 `identity` y v1 `identity_v1`) sin fusión formal; un consumidor que use v0 puede emitir identidad no-conforme con las garantías de v1. [VERIFICADO POR CÓDIGO — census CORE017 vs CORE018]
2. El módulo confía en el `conn` inyectado: si el caller abre una transacción sin commit o en la DB equivocada, no hay guarda local de esquema (los INSERT son a tabla `identity_v1.*` fija, pero sin validación de conexión al schema correcto). [VERIFICADO POR CÓDIGO — identity_v1.py no gestiona engine/commit]
3. `NUNCA_AUTORITATIVOS={"TICKER","YF_SYMBOL","LEGACY_ENTITY_ID"}` fijo en el módulo: si un nuevo tipo de identificador legítimo debe excluirse, hay que tocarlo en código y no es configurable. [VERIFICADO POR CÓDIGO — identity_v1.py:146]
4. new_entity_key usa `secrets.token_bytes` (no determinista entre corridas) — esto es deliberado (opacidad D-I-B) pero rompería una re-ejecución bit-a-bit; la idempotencia se garantiza buscando por identificador, no por clave. [VERIFICADO POR CÓDIGO — identity_v1.py:82-89 vs 238-257]
5. Dependencia de datos de la vista v_entity_resolution (resolution_report) sin contrato de capa verificado [NO DETERMINABLE — solo SELECT identity_v1.py:907-912, no vi definición de la vista].

DECISIÓN → (FASE 1: NO ejecutar nada). KEEP. Es el módulo mejor gobernado de los 5. Planificar: (a) hoja de ruta de retiro/migración de identity v0; (b) verificación de corrida de la batería de tests; (c) contrato de la vista v_entity_resolution.

EVIDENCIA → VERIFICADO POR CÓDIGO: identity_v1.py:1-14 (capa, independencia); :48-65, 146 (dominio, F-016, NUNCA_AUTORITATIVOS); :75-89 (ULID D-I-B); :99-146 (normalizadores+checksum); :159-171 (Evidence/facts F-036); :195-217 (autoridad por id_type); :293-313 (require_entity/entity_of); :402-559 (assert_identifier: conflictos 450-512, idempotencia 513-535, escritura 537-559); :567-621 (assert_bridge G5); :632-729 (GLEIF→CUIT con puente); :737-783 (instrument/symbol); :791-884 (resolve_review/ratificar_bridge); :887-899 (supersede_assertion); :907-926 (lectura). VERIFICADO POR TEST (existencia en repo): test_identity_v1.py, test_f032_no_duplicacion.py, test_f035_entidad_muerta.py, test_backfill_cik_adversarial.py, test_f041_reafirmacion.py (imports.csv). VERIFICADO POR EJECUCIÓN: NO DETERMINABLE (tests referenciados, corrida no registrada en snapshot). NO DETERMINABLE: certificación formal final del contenido en la base.

ESTADO: PASS_WITH_WARNINGS (código sólido y bien testeado-en-repo; warn por coexistencia v0/v1 y falta de evidencia de corrida/certificación).
