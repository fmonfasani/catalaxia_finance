# Identidad — capa 2 (reglas mínimas para FX research)

Versión: identity-fx-v1.0.0. No crea entidades; sólo fija cómo citarlas.

- entity_key canónico: CUIT (CNV/BYMA) o CIK (SEC). Jamás ticker, razón social
  ni símbolo Yahoo como clave (cfr. IDENTITY_ARCHITECTURE_V1 §5).
- instrument_key: requerido para toda reconstrucción (par ADR o bono). Sin
  instrumento declarado la celda es NO_DECIDE (instrumental_spec §4).
- TIKR como vendor: se cita como `source=TIKR.com + benchmark_hash + hoja +
  período`; es objeto de estudio, nunca identidad ni oracle.
- Estado: VERIFICADO POR CÓDIGO que el repo ya modela ticker≠identidad
  (IDENTITY_ARCHITECTURE_V1 §1.1); este archivo sólo lo hace vinculante aquí.
