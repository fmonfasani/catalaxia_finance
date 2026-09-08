# 18 — F7 Certification C11 (autoridad formal)

C11 responde "¿evidencia suficiente y válida para certificar este run?" con CERTIFICADA/NEGADA + motivo + hash + provenance. C11 no valida datos primarios, no reemplaza C10, no publica, no toca RAW/facts/identity/market. Solo DEV. Evidencia `[CÓDIGO]`/`[TEST]`/`[EJECUCIÓN]`/`[NO DETERMINABLE]`.

## Auditoría C11 (PASO 1)

Consume: `engine.runs` + `stage_runs` (gates/reports) + `checkpoints` (contexto). Produce: 1 fila `engine.certifications` por run + boletín JSON (artefacto, no primario). Condiciones CERTIFICADA (todo PASS terminal) / CON_OBSERVACIONES (WARNINGs) / NEGADA (en-curso, abortada, sin stages, insuficiente, BLOCK, inconsistencia BLOCKED-sin-BLOCK). `cert_hash` = sha256(canónico(rule, run_id, pipeline_version, run_status, etapas_declaradas_ordenadas, stages[{id,state,gate,report}])) — sin reloj/azar (INV3); checkpoints vía report.content; `certification_id` = `c11-{run_id}` determinista. Determinismo: misma evidencia ⇒ mismo hash (probado puro + round-trip). Idempotencia: ON CONFLICT DO NOTHING + re-lectura (INV6; sin UPDATE/DELETE). Provenance: evidence JSON por etapa + motivo + generado_por/at. Sin-C10 imposible: NEGADA con motivo explícito. Histórico inmutable: re-evaluar devuelve la fila intacta (hash+timestamp estables). Veredictos: CUBIERTO todo; GAP: ninguno (PASO 6: sin implementación).

## Contrato C11 (PASO 2) y matriz C10≠C11 (PASO 3)

INPUT (run + stage_runs + checkpoints) · OUTPUT (acta CERTIFICADA/NEGADA) · AUTHORITY (c11 exclusivo; 40_certificar = atestación de dominio, no autoridad) · PRECONDITIONS (C10 existe y no-BLOCK a nivel stage_runs) · CERTIFICATION RULES (todo PASS→CERTIFICADA; WARNINGs→CON_OBSERVACIONES) · DENIAL RULES (6 NEGADAs listadas) · EVIDENCE/HASH/IMMUTABILITY/IDEMPOTENCE/PROVENANCE (arriba). Política WARN explícita: C10-WARN de alcance (CNV) NO bloquea C11 (C11 solo exige su evidencia; run YPF CERTIFICADA con WARN vigente — probado, no asumido); WARNINGs de stage SÍ constan (CON_OBSERVACIONES). C10 ausente ⇒ NEGADA.
Matriz: stage gate→C10 valida · invariants→C10 valida · sufficiency→C11 decide · attestation→C11 produce · publication→C12 consume. C11 verifica presencia/integridad, no revalida las 9 invariantes (sin segundo C10).

## Determinismo, inmutabilidad, C11→C12 (PASO 4/5/9/11)

Hash puro verificado ×2 + round-trip contra filas (I + stored==recomputed). Re-certificar CERTIFICADA (KO) y NEGADA (cb2a) deja hash+timestamp intactos; cero filas duplicadas por run (N). C11→C12 en vivo: últimas publicaciones staging referencian `c11-9a5d42…`/`c11-0d9a29…` = CERTIFICADA (join verificado); publisher exige CERTIFIED (F2/F3). Reglas/versiones: `cert_rule`=DEFAULT_RULE = pipeline del run (Q).

## Tests A–T (20/20) + ejecución DEV (PASO 7/8)

A (YPFCERTIFICADA vía K) · B (WARN compatible) · C (BLOCK→NEGADA) · D (ausente→NEGADA pura) · E (5/5 PASS) · F (incompleto) · G (insuficiente) · H (hash sensible) · I (determinista) · J (re-evalúa idéntico) · K (run YPF nuevo CERTIFICADA) · L/M (historiales intactos) · N (cero duplicados) · O (acta completa) · P (stages == DISTINCT stage_runs) · Q (regla/versión) · R/S/T (canales C10/datos/C12 ausentes en c11 + conteos iguales). DEV: YPF+KO CERTIFICADA, BLOCK NEGADA, WARN documentado. Regresión c11+f6+f2: 52/0.

## No-touch (PASO 10/12) y matrices (§13)

Producción/RAW/parsed/facts/Market/CNV 0 escrituras · C10 solo lectura (evaluador intacto) · C12 solo lectura (joins) · legacy intacto · +filas DEV explícitas (1 CERTIFICADA YPF + 1 NEGADA demo F6). Matrices: 1 C10→C11 (PASS→puede, BLOCK→no, WARN→puede con alcance, ausente→no) · 2 authority (c11 exclusivo) · 3 rules/denial (6+2) · 4 hash-inputs (6 campos, sin reloj) · 5 immutability (conflict→relectura) · 6 idempotence (mismos 3 casos) · 7 C11→C12 (publisher exige + join verificado) · 8 no-touch (verificaciones).
