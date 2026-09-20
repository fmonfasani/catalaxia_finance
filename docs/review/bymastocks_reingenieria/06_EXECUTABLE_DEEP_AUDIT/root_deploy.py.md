# deploy.py — FICHA DEEP AUDIT

> FORMATE OBLIGATORIO. Cada afirmación lleva clase de evidencia:
> VERIFICADO POR CÓDIGO · VERIFICADO POR TEST · VERIFICADO POR EJECUCIÓN · NO DETERMINABLE.

CAPA →
PRIMARIA: PLANO INFRAESTRUCTURA / 18_INFRA (despliegue a servidor). [VERIFICADO POR CÓDIGO — deploy.py:23-241, despliega vía scp/ssh/docker; census SCRR005]. NO es capa de datos.
SECUNDARIAS: NADA de negocio — pero EJECUTA migración de datos en el servidor (rompe la pureza de capa; ver RIESGOS). [VERIFICADO POR CÓDIGO — deploy.py:124-141 llama load_screener_ratios.py que escribe DB].

PLANOS →
- DATOS: copia artefactos (load_screener_ratios.py, api/main.py, dashboards) a /opt/catalaxia y /var/www; NO copia self.screener.db en copy_files (aunque verify_files lo lista) [VERIFICADO POR CÓDIGO — deploy.py:76-93 vs 99-104].
- CONTROL: lista de verificación de existencia local (verify_files) [72-93]; validación de endpoints tras deploy [154-183]; acumulación de errores y resumen [185-204]; `StrictHostKeyChecking=no` en scp/ssh [111, 128, 147] (inseguro pero deliberado).
- EJECUCIÓN: secuencia paso a paso con cortocircuito si una fase falla [206-235]; perl `subprocess.run(shell=True, timeout=30)` [47-70].
- INFRA: servidor `89.167.96.239`, usuario `root`, ruta `/opt/catalaxia`, api `http://api.catalaxia.webshooks.com` [26-29]; docker-compose restart catalaxia-api [147].

CICLO →
- DEFINIR: header "Deploy Screener v2 – copia archivos + ejecuta migración + valida" [VERIFICADO POR CÓDIGO — deploy.py:1-8].
- IMPLEMENTAR: cronología copy→migration→restart→validate [206-235].
- VERIFICAR: validación de endpoints por HTTP 200 [154-183]; sin verificación de checksum/integridad de lo copiado [NO DETERMINABLE — no hay hash en el flujo].
- CERTIFICAR: NO — el resumen es auto-declarado, no una certificación [185-204].

HOY → Despliega manualmente/automatizado: verifica archivos, copia por SCP, ejecuta MIGRACIÓN de datos por SSH (load_screener_ratios.py), reinicia la API Docker y valida endpoints. [VERIFICADO POR CÓDIGO]
OBJETIVO → En el harness, el despliegue debe ser PLANO INFRA puro (copia de binarios/artefactos versionados) y la migración de datos debe vivir en un ejecutable de capa DATOS con gates, checkpoints y reversible; deploy.py no debería ejecutar lógica de escritura de datos ni inventar el estado de la aplicación. [VERIFICADO POR CÓDIGO — el propio script mezcla ambas].

DEPENDENCIAS → red:scp/ssh al servidor 89.167.96.239 (root); archivos locales: scripts\tickets\screener\load_screener_ratios.py, api\main.py, dashboard_estatico.html, dashboard_dinamico_v2.html, data\screener.db; subprocess/urllib; remote: docker-compose, python3.

CONTRATO → INPUT: none (corre entero). OUTPUT: copia en servidor + migración ejecutada + API reiniciada + endpoints validados; exit 0/1. PRECONDICIONES: claves SSH a root@host; archivos presentes; API levantada. POSTCONDICIONES: artefactos en el destino; screener ratios migrados (572); API reiniciada. INVARIANTES: I-007 DETERMINISMO PARCIAL (secuencia fija pero orden de as_completed no); I-008 IDEMPOTENCIA: NO probada (no registra versión desplegada ni permite rollback); I-006 PROVENANCE: no aplica formalmente.

RIESGOS →
1. CREDENCIAL/INSEGURIDAD: usuario `root` hardcodeado (deploy.py:27) y host/IP hardcodeado (:26) con `StrictHostKeyChecking=no`; corre migración de datos como root en el servidor remoto sin secretos de gestión ni confirmación. [VERIFICADO POR CÓDIGO — deploy.py:26-29, 111, 128, 147]
2. VIOLACIÓN DE SEPARACIÓN: deployment que además EJECUTA migración/escritura de datos (load_screener_ratios.py) — mezcla PLANO INFRA con capa DATOS; rompe la responsabilidad simple del despliegue. [VERIFICADO POR CÓDIGO — deploy.py:124-141]
3. FALSO ÉXITO: restart_api() SIEMPRE devuelve True sin chequear el resultado real del ssh (deploy.py:151-152 "API reiniciada" incondicional). El deploy puede reportar éxito con API caída. [VERIFICADO POR CÓDIGO]
4. copy_files considera éxito si `output is not None OR "100%" in output` — un scp que no subió nada o devolvió error en stderr puede pasar como OK. [VERIFICADO POR CÓDIGO — deploy.py:114-120]
5. Sin verificación de integridad (checksum) de lo copiado, sin rollback, sin inmutabilidad RAW del lado remoto (la migración toca producción). [NO DETERMINABLE — ausencia de hash/flujo de rollback en el código]

DECISIÓN → (FASE 1: NO ejecutar nada). REVIEW / CORRECTIVO urgente. Planificar: (a) NO hardcodear credenciales/host (externalizar a env/SSH config y revocar el uso de `root` para ejecutar datos); (b) separar el despliegue de binarios del job de migración de datos; (c) hacer restart_api honesto (chequear realmente) y validación por checksum; (d) soporte de rollback.

EVIDENCIA → VERIFICADO POR CÓDIGO: deploy.py:26-29 (host/root/ruta/api); :47-70 (subprocess shell=True timeout 30); :72-93 (verify_files, incluye data\screener.db listado 81); :95-122 (copy_files SCP, éxito laxo 116-120); :124-141 (run_migration vía SSH, criterio string "MIGRACION COMPLETADA" 133); :143-152 (restart_api, SIEMPRE True 151-152); :154-183 (validate_endpoints HTTP 200); :185-204 (summary auto-declarado); :206-235 (run cortocircuito). VERIFICADO POR EJECUCIÓN: NO DETERMINABLE. NO DETERMINABLE: estado real del servidor tras cada deploy, checksum, rollback.

ESTADO: DECISION_REQUIRED (secretos hardcodeados root@IP + falso éxito en restart; no apto para producción sin corrección).
