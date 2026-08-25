"""Validacion de contenido CNV.

Hallazgo C2 que origina este modulo: **HTTP 200 no significa documento valido**.
Evidencia empirica recogida en C0/C2/C3-inspect:

  * `Empresa/{cuit}` inexistente -> HTTP **200** + shell generica de 40.720 bytes,
    sin el CUIT en el cuerpo y con 0 GUIDs.
  * `publicview/{guid}` inexistente -> HTTP 404 pero con HTML de 45 KB que **igual**
    define `presentationIdGlobal`; lo que falta es un `formTypeId` no vacio.
  * `GetPublicValetKey/{guid}` -> HTTP **200** + token valido incluso para un blob
    que no existe.
  * `DownloadBlob` con valet key invalida -> 400 con `text/html` (pagina de error
    disfrazada de descarga).

Cada regla tiene id estable y severidad:
  HARD -> INVALID (el artefacto no se acepta como evidencia)
  SOFT -> REVIEW  (se acepta y persiste, pero queda en cola humana; nunca se cierra solo)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VALID = "VALID"
REVIEW = "REVIEW"
INVALID = "INVALID"

HARD = "HARD"
SOFT = "SOFT"

# Shell generica observada: 40.720 bytes. Piso con margen para no depender del byte exacto.
GENERIC_PAGE_MAX_BYTES = 200_000
MIN_BYTES = {"EMPRESA_PAGE": 100_000, "VISOR": 5_000, "BLOB": 64, "VALET_KEY": 32}

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
RTF_MAGIC = b"{\\rt"

HTML_SNIFF = re.compile(rb"^\s*(<!doctype html|<html|<\?xml[^>]*\?>\s*<!doctype html)", re.I)
ERROR_MARKERS = (b"Request Error", b"Server Error", b"HTTP Error", b"Runtime Error",
                 b"An error occurred while processing your request")


@dataclass
class Rule:
    id: str
    severity: str
    passed: bool
    detail: str


@dataclass
class Validation:
    kind: str
    status: str = VALID
    rules: list[Rule] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def add(self, rule_id: str, severity: str, passed: bool, detail: str) -> None:
        self.rules.append(Rule(rule_id, severity, passed, detail))

    def finish(self) -> "Validation":
        if any(not r.passed and r.severity == HARD for r in self.rules):
            self.status = INVALID
        elif any(not r.passed and r.severity == SOFT for r in self.rules):
            self.status = REVIEW
        else:
            self.status = VALID
        return self

    @property
    def failed(self) -> list[str]:
        return [r.id for r in self.rules if not r.passed]

    @property
    def failed_hard(self) -> list[str]:
        return [r.id for r in self.rules if not r.passed and r.severity == HARD]

    def reason(self) -> str | None:
        bad = [f"{r.id}({r.severity}): {r.detail}" for r in self.rules if not r.passed]
        return "; ".join(bad) if bad else None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "status": self.status, "failed": self.failed,
                "facts": self.facts,
                "rules": [{"id": r.id, "severity": r.severity, "passed": r.passed,
                           "detail": r.detail} for r in self.rules]}


def normalize_cuit(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def cuit_variants(cuit: str) -> list[str]:
    """CNV escribe el CUIT sin guiones en la URL y CON guiones en el cuerpo."""
    plain = normalize_cuit(cuit) or ""
    out = [plain]
    if len(plain) == 11:
        out.append(f"{plain[:2]}-{plain[2:10]}-{plain[10:]}")
    return out


def _decode(content: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", "replace")


def _base_checks(v: Validation, res, kind: str) -> bool:
    """Reglas comunes de transporte. Devuelve False si no tiene sentido seguir."""
    v.add("V-HTTP-STATUS", HARD, res.http_status == 200,
          f"http_status={res.http_status}")
    body = res.content
    v.add("V-NONEMPTY", HARD, bool(body), f"bytes={len(body) if body else 0}")
    if not body:
        v.facts["bytes"] = 0
        return False
    v.facts["bytes"] = len(body)
    v.facts["content_type"] = res.content_type
    v.add("V-MIN-SIZE", HARD, len(body) >= MIN_BYTES.get(kind, 1),
          f"bytes={len(body)} piso={MIN_BYTES.get(kind, 1)}")
    return res.http_status == 200


def _html_shape(v: Validation, text: str, body: bytes) -> None:
    v.add("V-HTML-STRUCTURE", HARD, ("<html" in text.lower() and "</html>" in text.lower()),
          "etiquetas <html>...</html> presentes" if "</html>" in text.lower() else "HTML truncado o no-HTML")
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    v.facts["title"] = (re.sub(r"\s+", " ", title.group(1)).strip()[:120] if title else None)
    v.add("V-TITLE", SOFT, bool(title), f"title={v.facts['title']!r}")
    hit = next((m for m in ERROR_MARKERS if m in body), None)
    v.add("V-DISGUISED-ERROR", HARD, hit is None,
          "sin marcadores de pagina de error" if hit is None else f"marcador de error: {hit.decode()!r}")


def validate_empresa_page(res, cuit: str) -> Validation:
    """Pagina empresa. La trampa: CNV responde 200 con una shell generica identica
    para cualquier CUIT inexistente. Discriminador = CUIT en el cuerpo + GUIDs + tamano."""
    v = Validation(kind="EMPRESA_PAGE")
    if not _base_checks(v, res, "EMPRESA_PAGE"):
        return v.finish()
    body = res.content
    text = _decode(body)
    ctype = (res.content_type or "").lower()
    v.add("V-CONTENT-TYPE", HARD, "html" in ctype, f"content_type={res.content_type!r}")
    _html_shape(v, text, body)

    guids = set(re.findall(r"publicview/([0-9a-fA-F-]{36})", text))
    v.facts["guids"] = len(guids)
    variants = cuit_variants(cuit)
    cuit_hit = [c for c in variants if c and c in text]
    v.facts["cuit_forms_found"] = cuit_hit

    v.add("V-EXPECTED-ENTITY", HARD, bool(cuit_hit),
          f"CUIT {cuit} presente en el cuerpo (formas {cuit_hit})" if cuit_hit
          else f"CUIT {cuit} AUSENTE del cuerpo (probadas: {variants})")
    v.add("V-HAS-PRESENTATIONS", HARD, len(guids) > 0,
          f"guids publicview={len(guids)}")
    generic = (len(guids) == 0 and not cuit_hit and len(body) < GENERIC_PAGE_MAX_BYTES)
    v.add("V-GENERIC-PAGE", HARD, not generic,
          "shell generica CNV (0 guids, sin CUIT, tamano de shell)" if generic
          else "no coincide con la firma de shell generica")

    otros = {normalize_cuit(c) for c in re.findall(r"CUIT:\s*(\d{2}-\d{8}-\d)", text)}
    otros.discard(normalize_cuit(cuit))
    v.facts["otros_cuits_en_pagina"] = len(otros)
    return v.finish()


def validate_visor(res, guid: str, expected_cuit: str | None = None) -> Validation:
    """Visor AIF2. Trampa: el 404 del visor devuelve HTML que igual declara
    `presentationIdGlobal`; la senal real es un `formTypeId` con valor."""
    v = Validation(kind="VISOR")
    ok_transport = _base_checks(v, res, "VISOR")
    if not res.content:
        return v.finish()
    body = res.content
    text = _decode(body)
    ctype = (res.content_type or "").lower()
    v.add("V-CONTENT-TYPE", HARD, "html" in ctype, f"content_type={res.content_type!r}")
    if ok_transport:
        _html_shape(v, text, body)

    form_type_id = _js_var(text, "formTypeId")
    form_type_name = _js_var(text, "formTypeName")
    pres_id = _js_var(text, "presentationIdGlobal")
    v.facts.update({"form_type_id": form_type_id, "form_type_name": form_type_name,
                    "presentation_id": pres_id})
    v.add("V-DOCTYPE-DECLARED", HARD, bool(form_type_id),
          f"formTypeId={form_type_id!r} formTypeName={form_type_name!r}")
    v.add("V-PRESENTATION-ID", HARD, bool(pres_id),
          f"presentationIdGlobal={pres_id!r}")
    modelo = "<modeloDatos" in text or "claveinformativa" in text
    v.facts["modelo_datos"] = modelo
    v.add("V-STRUCTURE-MODELO", SOFT, modelo,
          "modeloDatos/claveinformativa presente" if modelo
          else "sin modeloDatos: visor sin datos estructurados (legacy o formulario informativo)")

    if expected_cuit:
        variants = [c for c in cuit_variants(expected_cuit) if c and c in text]
        v.facts["cuit_forms_found"] = variants
        # H-C2-04: los visores legacy no exponen ni societyName ni CUIT. Ausencia no
        # es prueba de error; presencia de OTRO CUIT si es motivo de revision.
        otros = {normalize_cuit(c) for c in re.findall(r"\b(\d{2}-\d{8}-\d)\b", text)}
        otros.discard(normalize_cuit(expected_cuit))
        v.facts["otros_cuits_en_visor"] = sorted(x for x in otros if x)[:5]
        v.add("V-ENTITY-CONSISTENCY", SOFT, not (otros and not variants),
              "sin CUIT ajeno dominante" if not (otros and not variants)
              else f"visor menciona CUIT(s) ajeno(s) {sorted(x for x in otros if x)[:3]} y no el esperado {expected_cuit}")
    return v.finish()


def validate_blob(res, nombre: str | None = None, tamano_declarado: str | None = None,
                  hash_cnv: str | None = None, sha256_b64: str | None = None) -> Validation:
    """Adjunto binario. Valida magic bytes reales contra la extension declarada y
    detecta paginas de error servidas donde deberia haber un documento."""
    v = Validation(kind="BLOB")
    v.facts["nombre"] = nombre
    if not _base_checks(v, res, "BLOB"):
        return v.finish()
    body = res.content
    ext = (nombre or "").lower().rsplit(".", 1)[-1] if nombre and "." in nombre else ""
    v.facts["ext"] = ext
    v.facts["magic"] = body[:8].hex()

    looks_html = bool(HTML_SNIFF.match(body[:200])) or body[:200].lstrip().lower().startswith(b"<html")
    ctype = (res.content_type or "").lower()
    v.add("V-DISGUISED-ERROR", HARD, not (looks_html and ext not in ("htm", "html")),
          "cuerpo binario" if not looks_html else f"HTML servido donde se esperaba .{ext or '?'}")
    v.add("V-CONTENT-TYPE", SOFT, ("octet-stream" in ctype or "pdf" in ctype or "application" in ctype),
          f"content_type={res.content_type!r}")

    if ext == "pdf":
        head_ok = body.startswith(PDF_MAGIC)
        v.add("V-PDF-MAGIC", HARD, head_ok,
              f"cabecera={body[:8]!r} esperada {PDF_MAGIC!r}")
        tail_ok = b"%%EOF" in body[-2048:]
        v.add("V-PDF-EOF", HARD, tail_ok,
              "trailer %%EOF presente" if tail_ok else "PDF sin %%EOF: truncado o corrupto")
    elif ext in ("doc", "xls", "ppt"):
        v.add("V-OLE-MAGIC", HARD, body.startswith(OLE_MAGIC) or body.startswith(RTF_MAGIC),
              f"cabecera={body[:8]!r} esperada OLE2/RTF")
    elif ext in ("docx", "xlsx", "pptx", "zip"):
        v.add("V-ZIP-MAGIC", HARD, body.startswith(ZIP_MAGIC),
              f"cabecera={body[:8]!r} esperada {ZIP_MAGIC!r}")
    elif ext in ("htm", "html"):
        v.add("V-HTML-MAGIC", SOFT, looks_html, f"cabecera={body[:32]!r}")
    else:
        v.add("V-EXT-DESCONOCIDA", SOFT, False,
              f"extension {ext!r} sin regla de magic bytes: se persiste sin verificar formato")

    declared = _parse_tamano(tamano_declarado)
    if declared is not None:
        v.facts["bytes_declarados"] = declared
        # CNV declara en MB con 2 decimales -> tolerancia +-10 KB o 5%.
        tol = max(10_240, declared * 0.05)
        v.add("V-DECLARED-SIZE", SOFT, abs(len(body) - declared) <= tol,
              f"bytes={len(body)} declarado~{declared} tol={int(tol)}")

    if hash_cnv and sha256_b64:
        match = hash_cnv == sha256_b64
        v.facts["hash_cnv_match"] = match
        # C0-CNV-006: el hash que CNV registro en el upload NO coincide con el SHA256
        # del archivo servido. Se registra, jamas se usa para idempotencia.
        v.add("V-HASH-CNV", SOFT, match,
              "hash CNV coincide" if match else
              f"hash CNV {hash_cnv[:16]}... != sha256(b64) {sha256_b64[:16]}... (C0-CNV-006)")
    return v.finish()


def validate_valet_key(res, key: str | None) -> Validation:
    v = Validation(kind="VALET_KEY")
    if not _base_checks(v, res, "VALET_KEY"):
        return v.finish()
    ctype = (res.content_type or "").lower()
    v.add("V-CONTENT-TYPE", HARD, "json" in ctype, f"content_type={res.content_type!r}")
    v.add("V-VALETKEY-PRESENT", HARD, bool(key), "valetKeyData presente" if key else "sin valetKeyData")
    # Documentado: 200 + token valido para un blob inexistente. El token NO prueba existencia.
    v.add("V-VALETKEY-NO-PRUEBA-EXISTENCIA", SOFT, True,
          "token obtenido; la existencia del blob se prueba recien en DownloadBlob")
    return v.finish()


def _js_var(text: str, name: str) -> str | None:
    m = re.search(rf"var\s+{re.escape(name)}\s*=\s*'([^']*)'", text) or \
        re.search(rf'var\s+{re.escape(name)}\s*=\s*"([^"]*)"', text)
    if not m:
        return None
    val = m.group(1).strip()
    return val or None


def _parse_tamano(tamano: str | None) -> int | None:
    if not tamano:
        return None
    m = re.match(r"\s*([\d.,]+)\s*(KB|MB|GB|B)\s*$", tamano, re.I)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    mult = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[m.group(2).upper()]
    return int(num * mult)
