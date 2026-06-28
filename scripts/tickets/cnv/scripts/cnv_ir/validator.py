"""
validator.py

Validación de páginas HTML descargadas desde la CNV.
"""

from dataclasses import dataclass
import re


# Si alguna vez la CNV cambia el tamaño promedio,
# solamente modificar este valor.
MIN_HTML_SIZE = 10_000


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    reason: str = ""
    presentation_id: str | None = None


def extract_presentation_id(html: str) -> str | None:
    """
    Extrae presentationIdGlobal del HTML.
    """

    m = re.search(
        r"presentationIdGlobal\s*=\s*['\"](\d+)['\"]",
        html,
        re.I,
    )

    if m:
        return m.group(1)

    return None


def contains_captcha(html: str) -> bool:
    html = html.lower()

    keywords = (
        "captcha",
        "recaptcha",
        "cloudflare",
        "cf-browser-verification",
        "verify you are human",
    )

    return any(k in html for k in keywords)


def contains_maintenance(html: str) -> bool:
    html = html.lower()

    keywords = (
        "maintenance",
        "mantenimiento",
        "temporarily unavailable",
        "service unavailable",
        "503",
    )

    return any(k in html for k in keywords)


def contains_error_page(html: str) -> bool:
    html = html.lower()

    keywords = (
        "404",
        "not found",
        "ha ocurrido un error",
        "ocurrió un error",
        "error interno",
        "internal server error",
    )

    return any(k in html for k in keywords)


def validate_html(html: str) -> ValidationResult:
    """
    Valida un HTML descargado.
    """

    if not html:
        return ValidationResult(False, "empty_response")

    if len(html) < MIN_HTML_SIZE:
        return ValidationResult(False, "html_too_small")

    if contains_captcha(html):
        return ValidationResult(False, "captcha")

    if contains_maintenance(html):
        return ValidationResult(False, "maintenance")

    if contains_error_page(html):
        return ValidationResult(False, "error_page")

    presentation_id = extract_presentation_id(html)

    if presentation_id is None:
        return ValidationResult(False, "presentation_id_not_found")

    return ValidationResult(
        ok=True,
        presentation_id=presentation_id,
    )