"""Tests de humo para engine/cnv/*. No requieren red ni base de datos.

Cubren dos bugs reales encontrados y corregidos en la sesion de ejecucion C2->C3
(2026-08-25):
  1. RawStore.canonical_sha256: EMPRESA_PAGE/VISOR embeben contenido aleatorio
     por request (cache-busting de assets, token anti-forgery) que antes rompia
     la idempotencia. Este hash debe ignorar SOLO esos 2 patrones confirmados.
  2. discovery.classify: separacion CONTROLADA/VINCULADA que C2 exigio antes de
     un fetch masivo (H-C2-02).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.cnv.discovery import (  # noqa: E402
    CLASE_EEFF_CONTROLADA,
    CLASE_EEFF_PROPIO,
    CLASE_EEFF_RELAC_OTRA,
    CLASE_EEFF_VINCULADA,
    CLASE_OTRO,
    classify,
)
from engine.cnv.rawstore import canonical_sha256, sha256_bytes  # noqa: E402


# --------------------------------------------------------------------------
# canonical_sha256 (idempotencia)
# --------------------------------------------------------------------------
EMPRESA_A = (
    b'<link href="/assets/css/style.css?v=0dd70260-e8a9-47f8-b32c-4874db8145d6" '
    b'rel="stylesheet"><body>contenido real sin cambios</body>'
)
EMPRESA_B = (
    b'<link href="/assets/css/style.css?v=7653a2b6-13d9-46d2-9329-e3d6565a6649" '
    b'rel="stylesheet"><body>contenido real sin cambios</body>'
)
VISOR_A = (
    b'<input type="hidden" id="RequestVerificationToken" '
    b'name="RequestVerificationToken" value="tokenAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">'
    b'<body>presentacion 123</body>'
)
VISOR_B = (
    b'<input type="hidden" id="RequestVerificationToken" '
    b'name="RequestVerificationToken" value="tokenBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB">'
    b'<body>presentacion 123</body>'
)


class TestCanonicalHash:
    def test_empresa_page_ignora_cachebust_de_assets(self):
        assert sha256_bytes(EMPRESA_A) != sha256_bytes(EMPRESA_B)
        assert canonical_sha256(EMPRESA_A, "EMPRESA_PAGE") == canonical_sha256(EMPRESA_B, "EMPRESA_PAGE")

    def test_visor_ignora_token_antiforgery(self):
        assert sha256_bytes(VISOR_A) != sha256_bytes(VISOR_B)
        assert canonical_sha256(VISOR_A, "VISOR") == canonical_sha256(VISOR_B, "VISOR")

    def test_cambio_real_de_contenido_si_se_detecta(self):
        distinto = EMPRESA_A.replace(b"contenido real sin cambios", b"contenido DISTINTO")
        assert canonical_sha256(EMPRESA_A, "EMPRESA_PAGE") != canonical_sha256(distinto, "EMPRESA_PAGE")

    def test_blob_no_se_canonicaliza(self):
        # BLOB/VALET_KEY no tienen los patrones de ruido conocidos: su canonico
        # debe ser identico al sha256 crudo (ninguna sustitucion aplica).
        contenido = b"%PDF-1.4 contenido binario de un adjunto"
        assert canonical_sha256(contenido, "BLOB") == sha256_bytes(contenido)


# --------------------------------------------------------------------------
# discovery.classify (separacion CONTROLADA / VINCULADA, hallazgo H-C2-02)
# --------------------------------------------------------------------------
class TestClassifyRelacion:
    def test_controlada_se_distingue_de_vinculada(self):
        controlada, _ = classify(
            "RELAC.: CONTROLADA - CUIT: 30711900582 - CENTRAL VUELTA DE OBLIGADO S.A. - "
            "FECH. CIERRE BAL.: 31-12-2025", None)
        vinculada, _ = classify(
            "RELAC.: VINCULADA - CUIT: 33657865279 - DISTRIBUIDORA DE GAS DEL CENTRO S.A. - "
            "FECH. CIERRE BAL.: 31-12-2025", None)
        assert controlada == CLASE_EEFF_CONTROLADA
        assert vinculada == CLASE_EEFF_VINCULADA
        assert controlada != vinculada

    def test_relac_sin_tipo_reconocido_cae_en_otra(self):
        clase, ambito = classify("RELAC.: SOCIEDAD DEL GRUPO - CUIT: 30000000001 - X", None)
        assert clase == CLASE_EEFF_RELAC_OTRA
        assert ambito == "RELACIONADA"

    def test_eeff_propio_moderno(self):
        clase, ambito = classify(
            "NORMA CONTABLE: NIIF - TIPO BALANCE: INDIVIDUAL - PERIODICIDAD: 3 - "
            "FECHA CIERRE: 2026-06-30 - ESTADOS CONTABLES - NIIF", None)
        assert clase == CLASE_EEFF_PROPIO
        assert ambito == "PROPIO"

    def test_texto_no_financiero_cae_en_otro(self):
        clase, ambito = classify("AVISO DE PAGO OBLIGACIONES NEGOCIABLES", None)
        assert clase == CLASE_OTRO
        assert ambito == "NO_FINANCIERO"
