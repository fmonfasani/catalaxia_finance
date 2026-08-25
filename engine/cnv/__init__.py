"""Adaptador CNV (Comision Nacional de Valores, Argentina) para el engine Catalaxia.

Generalizable a cualquier empresa por CUIT. CEPU es el caso piloto, no una excepcion:
ninguna regla de este paquete depende de una empresa concreta.

Cadena: Discovery -> Fetch -> RAW -> Integrity -> Manifest -> Provenance -> Validation.
"""

CNV_ADAPTER_VERSION = "cnv-fetch-v1"
