# CNV_MULTIEMPRESA_GATE

Objeto: mecanismo Identity V1 → CNV, evaluado para homologación con múltiples
emisores (CEPU, YPF, TGSU2 fetcheados; GGAL, BMA, control negativo
correctamente bloqueados). Fecha: 2026-09-01. DB: `catalaxia-engine-dev`
(5433), `prod=False` confirmado en cada corrida — sin ambigüedad dev/prod.

```
CNV_VALIDATION_GATE = PASS_WITH_WARNINGS
```

## Clasificación de hallazgos (según el criterio de calidad del mandato)

### Defectos reales (no bloqueantes, no maquillados)

1. **`fetch_raw.cnv_download_log` sin FK/CHECK de coherencia entity_key↔cuit**
   (adversario #7). Un INSERT con `entity_key` y `cuit` de dos empresas
   distintas se aplica sin excepción. Mitigado solo por disciplina de
   aplicación (el fetcher siempre deriva ambos del mismo `resolver_en_identity_v1()`),
   no por el esquema.
2. **`fetch_raw.*` permite UPDATE sin ninguna barrera** (adversario #8). Un
   hash ya persistido puede falsificarse; solo una auditoría posterior lo
   detecta comparando contra el archivo físico.

### Limitaciones de evidencia (no defectos de identidad ni de atribución)

3. **RAW histórico no reproducible físicamente** para la mayoría de las
   presentaciones de CEPU/YPF/TGSU2 previas a esta sesión (0 mismatch en lo
   que sobrevive; el resto simplemente no está en disco). Es una limitación
   de lo que se puede volver a verificar hoy, no una falla de identidad: la
   provenance en la base sigue completa y coherente para esas filas.

### Datos faltantes (no convertidos en defecto)

4. **No existen 5-10 emisores adicionales con CUIT VERIFIED** — se buscó
   explícitamente en las 525 entidades de `identity_v1` y el resultado real
   es que solo hay 3 (CEPU, YPF, TGSU2). Esto es un hecho del estado actual
   de Identity V1, no un defecto del mecanismo CNV ni de esta validación. Se
   documenta como tal, no se fuerza una muestra más grande inventando
   elegibilidad que no existe.
5. **YPF sin corrida `--rerun` propia en esta sesión** (se priorizó TGSU2 para
   Fase G, ya que repetirlo en YPF no habría aportado una propiedad distinta
   de la ya demostrada en TGSU2 y CEPU). No es un defecto: es una decisión de
   alcance para no multiplicar tráfico contra CNV sin necesidad.

### Casos correctamente bloqueados (NO son failures)

6. GGAL (`CUIT_NO_VERIFICADO`), BMA (`SIN_CUIT`), CUIT `20111111112`
   (`NO_ESTA_EN_IDENTITY_V1`) — los 3 bloqueados por el propio pipeline,
   antes de tocar red, con 0 escrituras. El contrato exige bloquearlos; que
   lo hagan es un PASS de esa garantía, no una ausencia de resultado.

### Warnings no bloqueantes

7. El motivo `AMBIGUO` de `resolver_en_identity_v1()` es estructuralmente
   inalcanzable con el CLI actual (exige exactamente uno de `--cuit`/`--cik`,
   y el índice único de `identity_v1` ya impide que dos entidades compartan
   un identificador autoritativo vigente). No es un problema — es defensa en
   profundidad para un estado que hoy no puede ocurrir por otras vías.
8. `checkpoint=None` en la corrida 3 de TGSU2 (donde `C-C3-006` dio FAIL) es
   el comportamiento correcto: no se certifica una idempotencia que no se
   cumplió esa vez. La corrida en sí (discovery, fetch, integridad,
   provenance, scope) siguió siendo válida.

## Resumen de lo demostrado

- **Identity → CNV generaliza**: 2 empresas nuevas (YPF, TGSU2) fetcheadas
  con el mismo código, mismo gate, CUIT resuelto en vivo desde `identity_v1`
  — 0 cambios de código requeridos.
- **El mecanismo de bloqueo generaliza**: 3 casos no elegibles (2 reales —
  GGAL, BMA — más 1 de control) bloqueados con el mensaje correcto, antes de
  cualquier escritura, sin fallback legacy y sin inventar identidad.
- **La idempotencia detecta tanto la ausencia como la presencia de cambios
  reales** — demostrado en TGSU2 con 2 corridas consecutivas de resultado
  distinto y correcto cada una.
- **La auditoría independiente no depende de confiar en el fetcher**: separó
  correctamente "0 mezcla/0 duplicados" (PASS real) de "el RAW histórico ya
  no está en disco" (limitación real, no ocultada).

## Qué queda pendiente para homologación

1. Decisión de producto sobre F-007/F-008 (ya abiertos, no tocados acá).
2. Decisión de producto sobre los 2 hallazgos nuevos (#7, #8 de esta sesión):
   ¿se refuerza `fetch_raw` con las mismas garantías que `identity_v1`, o se
   acepta el riesgo por ser un schema de solo-CNV con un único escritor
   conocido? No es una decisión que corresponda cerrar en esta validación.
3. Si se quiere ampliar el universo de emisores CNV con identidad demostrada,
   el trabajo previo es sobre **Identity V1** (ratificar más puentes
   CIK↔LEI↔CUIT vía GLEIF/AFIP/IGJ), no sobre CNV — CNV ya demostró que
   consume correctamente cualquier CUIT que Identity V1 entregue como
   VERIFIED.
4. Política de retención de RAW explícita antes de escalar el volumen
   (F-008), para que la próxima auditoría no encuentre el mismo patrón de
   archivos faltantes a mayor escala.

## Evidencia

- `CNV_MULTIEMPRESA_VALIDATION_REPORT.md` (narrativa completa, Fases A-F)
- `CNV_MULTIEMPRESA_VALIDATION_MATRIX.csv` (por emisor: CIK/LEI/CUIT/assertion/bridge/runs/hashes/provenance)
- `CNV_MULTIEMPRESA_ADVERSARIAL.json` (10 ataques con garantía/esperado/real/barrera)
- `CNV_MULTIEMPRESA_AUDIT.json` (auditoría independiente, 4 CUIT)
- Logs crudos: `scratchpad/c3_runs/run{7,8,9,10}_*.log`
