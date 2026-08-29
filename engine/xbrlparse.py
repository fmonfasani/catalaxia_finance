"""Parser XBRL propio (D-004) — nucleo generico de la etapa S03 PARSE.

Alcance: preservar y estructurar. Este modulo NO normaliza conceptos hacia
Revenue/EBITDA/etc, no elige "el mejor tag" y no deduplica hechos: solo los
marca. Toda decision que descarta informacion queda registrada como error o
warning con codigo; nunca hay perdida silenciosa.

Cero conocimiento de empresas concretas: no hay CIK, ticker ni nombre alguno
en este archivo (regla YPF del programa).
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from lxml import etree

PARSER_VERSION = "xbrlparse-v3"

# --------------------------------------------------------------------------
# Namespaces
# --------------------------------------------------------------------------
XBRLI_NS = "http://www.xbrl.org/2003/instance"
XBRLDI_NS = "http://xbrl.org/2006/xbrldi"          # explicitMember / typedMember
XBRLDT_NS = "http://xbrl.org/2005/xbrldt"          # atributos de hipercubo en definition
XLINK_NS = "http://www.w3.org/1999/xlink"
LINK_NS = "http://www.xbrl.org/2003/linkbase"
SCHEMA_NS = "http://www.w3.org/2001/XMLSchema"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XHTML_NS = "http://www.w3.org/1999/xhtml"

# Inline XBRL tuvo dos namespaces publicados; ambos existen en filings reales.
IXBRL_NAMESPACES = (
    "http://www.xbrl.org/2013/inlineXBRL",
    "http://www.xbrl.org/2008/inlineXBRL",
)
# Namespaces historicos de xbrldi vistos en generadores viejos.
XBRLDI_NAMESPACES = (XBRLDI_NS, "http://xbrl.org/2005/xbrldi")

IX_FACT_LOCALS = ("nonfraction", "nonnumeric", "fraction")

# --------------------------------------------------------------------------
# Clasificacion de linkbases
# --------------------------------------------------------------------------
EXTENDED_LINK_TO_LINKBASE = {
    "labelLink": "LABEL",
    "presentationLink": "PRESENTATION",
    "calculationLink": "CALCULATION",
    "definitionLink": "DEFINITION",
    "referenceLink": "REFERENCE",
    "footnoteLink": "FOOTNOTE",
}
ARC_ROLE_TO_LINKBASE = {
    "http://www.xbrl.org/2003/arcrole/concept-label": "LABEL",
    "http://www.xbrl.org/2003/arcrole/element-label": "LABEL",
    "http://www.xbrl.org/2003/arcrole/concept-reference": "REFERENCE",
    "http://www.xbrl.org/2003/arcrole/element-reference": "REFERENCE",
    "http://www.xbrl.org/2003/arcrole/summation-item": "CALCULATION",
    "http://www.xbrl.org/2003/arcrole/percentage-item": "CALCULATION",
    "http://www.xbrl.org/2003/arcrole/weighted-summation-item": "CALCULATION",
    "http://www.xbrl.org/2003/arcrole/parent-child": "PRESENTATION",
    "http://www.xbrl.org/2003/arcrole/fact-footnote": "FOOTNOTE",
    "http://xbrl.org/int/dim/arcrole/hypercube-dimension": "DEFINITION",
    "http://xbrl.org/int/dim/arcrole/dimension-domain": "DEFINITION",
    "http://xbrl.org/int/dim/arcrole/dimension-default": "DEFINITION",
    "http://xbrl.org/int/dim/arcrole/domain-member": "DEFINITION",
    "http://xbrl.org/int/dim/arcrole/all": "DEFINITION",
    "http://xbrl.org/int/dim/arcrole/notAll": "DEFINITION",
    # variantes historicas sin el segmento /arcrole/
    "http://xbrl.org/int/dim/hypercube-dimension": "DEFINITION",
    "http://xbrl.org/int/dim/dimension-domain": "DEFINITION",
    "http://xbrl.org/int/dim/dimension-default": "DEFINITION",
    "http://xbrl.org/int/dim/domain-member": "DEFINITION",
}
SUFFIX_TO_LINKBASE = (
    ("_pre.xml", "PRESENTATION"),
    ("_cal.xml", "CALCULATION"),
    ("_defr.xml", "DEFINITION"),
    ("_def.xml", "DEFINITION"),
    ("_lab.xml", "LABEL"),
    ("_ref.xml", "REFERENCE"),
)
VALID_LINKBASES = ("LABEL", "PRESENTATION", "CALCULATION", "DEFINITION",
                   "REFERENCE", "FOOTNOTE")

# Orden explicito: un `set` daria resultados no deterministas entre corridas.
STANDARD_TAXONOMIES = (
    "ifrs-full", "ifrs-smes", "us-gaap", "srt", "dei", "iso4217", "xbrli",
    "country", "currency", "exch", "naics", "sic", "stpr", "invest", "utr",
    "num", "nonnum", "ecd", "cyd", "rr", "cef", "ffd", "vip",
)


# --------------------------------------------------------------------------
# Utilidades de nombres
# --------------------------------------------------------------------------
def localname(qname: str) -> str:
    return qname.rsplit("}", 1)[-1] if "}" in qname else qname.split(":")[-1]


def namespace_of(qname: str) -> str:
    return qname[1:].split("}", 1)[0] if qname.startswith("{") else ""


def split_prefix(tag_with_prefix: str) -> tuple[str, str]:
    if ":" in tag_with_prefix:
        pfx, _, local = tag_with_prefix.partition(":")
        return pfx, local
    return "", tag_with_prefix


def _taxonomy_of(prefix: str, ns_uri: str) -> str:
    """Deriva la familia de taxonomia. Determinista: recorre una tupla ordenada."""
    if ns_uri:
        for std in STANDARD_TAXONOMIES:
            if f"/{std}/" in ns_uri or ns_uri.endswith(f"/{std}") or f"/{std}-" in ns_uri:
                return std
    for std in STANDARD_TAXONOMIES:
        if prefix == std:
            return std
    if ns_uri:
        for std in STANDARD_TAXONOMIES:
            if std in ns_uri:
                return std
    if prefix:
        return prefix
    host = (urlparse(ns_uri).hostname or "") if ns_uri else ""
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return parts[-2]
    if parts:
        return parts[0]
    return ns_uri.rsplit("/", 1)[-1] if ns_uri else "unknown"


def is_standard_taxonomy(taxonomy: str | None) -> bool:
    return (taxonomy or "") in STANDARD_TAXONOMIES


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fact_key(qname: str, context_id: str | None, unit_ref: str | None,
             value_text: str | None) -> str:
    """Clave de identidad de un hecho. NO se usa para deduplicar (prohibido en
    S03), solo para poder contar y auditar repeticiones."""
    payload = "|".join([qname, context_id or "", unit_ref or "", value_text or ""])
    return hashlib.sha1(payload.encode("utf-8", "replace")).hexdigest()


# --------------------------------------------------------------------------
# Modelo de salida
# --------------------------------------------------------------------------
@dataclass
class ParsedContext:
    context_id: str
    scheme: str | None = None
    identifier: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    instant_date: str | None = None
    period_kind: str | None = None
    dimensions: list[dict] = field(default_factory=list)        # explicitas
    typed_dimensions: list[dict] = field(default_factory=list)  # tipadas
    non_dimensional: list[dict] = field(default_factory=list)   # segment/scenario no-XDT
    has_segment: bool = False
    has_scenario: bool = False

    @property
    def dim_count(self) -> int:
        return len(self.dimensions) + len(self.typed_dimensions)

    @property
    def all_dimensions(self) -> list[dict]:
        return self.dimensions + self.typed_dimensions


@dataclass
class ParsedUnit:
    unit_ref: str
    unit_type: str
    measures: list[str]
    numerator: list[str]
    denominator: list[str]


@dataclass
class ParsedFact:
    tag: str
    qname: str
    namespace: str
    taxonomy: str
    value_text: str | None          # valor final (texto), post-transformacion
    value_raw_text: str | None      # valor tal como vino en el documento
    value_numeric: Decimal | None
    is_numeric: bool
    is_nil: bool
    unit_ref: str | None
    decimals: str | None
    precision: str | None
    context_id: str | None
    period_kind: str | None
    frame: str | None = None
    element_id: str | None = None
    scale: str | None = None
    sign: str | None = None
    ix_format: str | None = None
    numeric_transform: str | None = None
    transform_status: str | None = None
    is_hidden: bool = False
    is_escaped: bool = False
    ix_target: str | None = None
    continuation_steps: int = 0
    doc_kind: str = "XBRL_INSTANCE"

    @property
    def key(self) -> str:
        return fact_key(self.qname, self.context_id, self.unit_ref, self.value_text)


@dataclass
class ParsedFootnote:
    footnote_id: str
    role: str | None
    lang: str | None
    text: str | None
    fact_ids: list[str] = field(default_factory=list)


@dataclass
class ParsedRelation:
    linkbase: str
    role: str | None
    from_qname: str | None
    to_qname: str | None
    arc_role: str | None
    weight: float | None = None
    order_num: float | None = None
    label_type: str | None = None
    lang: str | None = None
    label_text: str | None = None
    preferred_sign: str | None = None
    dimension_qname: str | None = None
    member_qname: str | None = None
    from_href: str | None = None
    to_href: str | None = None
    use: str | None = None
    priority: float | None = None
    target_role: str | None = None
    closed: str | None = None
    context_element: str | None = None


@dataclass
class ParsedConcept:
    namespace: str | None
    tag: str
    qname: str
    label: str | None
    documentation: str | None
    xsd_type: str | None
    period_type: str | None
    balance: str | None
    abstract: bool | None
    taxonomy: str
    source_schema: str
    element_id: str | None = None
    substitution_group: str | None = None
    nillable: bool | None = None
    is_dimension: bool = False
    is_hypercube: bool = False
    is_custom: bool = False


@dataclass
class InstanceParseResult:
    facts: list[ParsedFact] = field(default_factory=list)
    contexts: dict[str, ParsedContext] = field(default_factory=dict)
    units: dict[str, ParsedUnit] = field(default_factory=dict)
    footnotes: list[ParsedFootnote] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    doc_kind: str = "XBRL_INSTANCE"

    def add_error(self, code: str, message, severity: str = "ERROR",
                  source_file: str | None = None) -> None:
        self.errors.append({"severity": severity, "code": code,
                            "message": str(message)[:900], "source_file": source_file})

    @property
    def fatal(self) -> bool:
        return any(e["severity"] == "ERROR" for e in self.errors)


# --------------------------------------------------------------------------
# Sniffing de documentos (clasificacion por contenido, no por nombre)
# --------------------------------------------------------------------------
@dataclass
class DocumentInfo:
    kind: str  # XBRL_INSTANCE|INLINE_XBRL|XSD_SCHEMA|LINKBASE|OTHER_XML|NON_XML|UNPARSEABLE
    root_tag: str | None = None
    linkbase_types: list[str] = field(default_factory=list)
    detail: str = ""
    ix_namespace: str | None = None


_XML_HEAD_RE = re.compile(rb"<\s*[A-Za-z_?!]")
# Magias binarias: sin esto un JPEG con un `<` casual se reporta UNPARSEABLE y
# parece un fallo de parseo cuando solo es una imagen.
_BINARY_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"%PDF", b"PK\x03\x04",
                 b"\x1f\x8b", b"BM", b"II*\x00", b"MM\x00*")


def _first_element(data: bytes) -> tuple[str | None, dict, dict]:
    """Devuelve (tag, nsmap, attrib) del elemento raiz sin parsear todo el doc."""
    try:
        ctx = etree.iterparse(BytesIO(data), events=("start",), huge_tree=True,
                              recover=True, resolve_entities=False)
        for _event, el in ctx:
            return (el.tag if isinstance(el.tag, str) else None,
                    dict(el.nsmap or {}), dict(el.attrib))
    except Exception:
        return None, {}, {}
    return None, {}, {}


def sniff_document(name: str, data: bytes) -> DocumentInfo:
    """Clasifica un payload por su contenido real.

    Distingue instance XML / Inline XBRL / XSD / linkbase (label, calculation,
    definition, presentation, reference, footnote) sin confiar en el nombre.
    """
    low = (name or "").lower().rsplit("/", 1)[-1]
    if not data:
        return DocumentInfo(kind="NON_XML", detail="archivo vacio")
    if data.startswith(_BINARY_MAGIC):
        return DocumentInfo(kind="BINARY", detail=f"contenido binario ({low})")
    if b"\x00" in data[:2048]:
        return DocumentInfo(kind="BINARY", detail=f"bytes nulos en cabecera ({low})")
    if not _XML_HEAD_RE.search(data[:4096]):
        return DocumentInfo(kind="NON_XML", detail=f"sin marcado XML en cabecera ({low})")

    tag, nsmap, _attrib = _first_element(data)
    if tag is None:
        return DocumentInfo(kind="UNPARSEABLE", detail=f"raiz ilegible ({low})")
    ns, local = namespace_of(tag), localname(tag)

    if ns == XBRLI_NS and local == "xbrl":
        return DocumentInfo(kind="XBRL_INSTANCE", root_tag=tag, detail="raiz xbrli:xbrl")
    if ns == SCHEMA_NS and local == "schema":
        # EDGAR moderno puede embeber las linkbases dentro de xs:appinfo en vez
        # de publicarlas como *_pre/_cal/_def/_lab.xml sueltos (visto FY2025).
        embedded = _linkbase_types(data)
        return DocumentInfo(kind="XSD_SCHEMA", root_tag=tag, linkbase_types=embedded,
                            detail="raiz xs:schema" +
                                   (f" con linkbases embebidas ({'+'.join(embedded)})"
                                    if embedded else ""))
    if ns == LINK_NS and local == "linkbase":
        types = _linkbase_types(data)
        return DocumentInfo(kind="LINKBASE", root_tag=tag, linkbase_types=types,
                            detail=f"raiz link:linkbase ({'+'.join(types) or 'sin extended links'})")
    if local.lower() in ("html", "xhtml") or ns == XHTML_NS:
        ix_ns = next((u for u in nsmap.values() if u in IXBRL_NAMESPACES), None)
        if ix_ns is None:
            for cand in IXBRL_NAMESPACES:
                if cand.encode() in data[:16384]:
                    ix_ns = cand
                    break
        if ix_ns:
            return DocumentInfo(kind="INLINE_XBRL", root_tag=tag, ix_namespace=ix_ns,
                                detail=f"XHTML con namespace inline {ix_ns}")
        return DocumentInfo(kind="NON_XML", root_tag=tag,
                            detail="HTML sin namespace inline XBRL")
    return DocumentInfo(kind="OTHER_XML", root_tag=tag, detail=f"raiz {tag}")


def _linkbase_types(data: bytes) -> list[str]:
    found: list[str] = []
    for elname, kind in EXTENDED_LINK_TO_LINKBASE.items():
        if f"<link:{elname}".encode() in data or f"<{elname}".encode() in data:
            if kind not in found:
                found.append(kind)
    return found


# --------------------------------------------------------------------------
# Seleccion de fuentes de hechos dentro de un filing
# --------------------------------------------------------------------------
FACT_SOURCE_PRECEDENCE = ("XBRL_INSTANCE", "INLINE_XBRL")


def select_fact_sources(docs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Aplica la politica de seleccion de fuente de hechos de un filing.

    `docs`: lista de dicts con al menos {name, kind, sha256, container}.
    Precedencia documentada:
      1. instancia XBRL (`xbrli:xbrl`), venga suelta o dentro del zip;
      2. si no hay ninguna, documento Inline XBRL;
      3. si no hay ninguna de las dos, el filing no tiene fuente de hechos.
    Copias con identico sha256 se marcan DUPLICATE_SHA (se conserva la suelta,
    que tiene ruta estable). Nada se descarta en silencio: cada documento no
    elegido sale con su motivo.
    """
    selected: list[dict] = []
    rejected: list[dict] = []
    chosen_kind: str | None = None
    for kind in FACT_SOURCE_PRECEDENCE:
        if any(d["kind"] == kind for d in docs):
            chosen_kind = kind
            break

    seen_sha: dict[str, dict] = {}

    def _order(d: dict) -> tuple:
        # LOOSE antes que ZIP: la ruta del archivo suelto es la provenance estable.
        return (0 if d.get("container") == "LOOSE" else 1, d.get("name") or "")

    for doc in sorted(docs, key=_order):
        kind = doc["kind"]
        if kind not in FACT_SOURCE_PRECEDENCE:
            rejected.append({**doc, "role": "NOT_A_FACT_SOURCE",
                             "selection_reason": f"kind={kind}"})
            continue
        if kind != chosen_kind:
            rejected.append({**doc, "role": "NOT_SELECTED",
                             "selection_reason": f"precedencia: el filing tiene {chosen_kind}"})
            continue
        prev = seen_sha.get(doc["sha256"])
        if prev is not None:
            rejected.append({**doc, "role": "DUPLICATE_SHA",
                             "selection_reason": f"mismo sha256 que {prev['name']}"})
            continue
        seen_sha[doc["sha256"]] = doc
        selected.append({**doc, "role": "FACT_SOURCE",
                         "selection_reason": f"fuente elegida por precedencia {chosen_kind}"})
    return selected, rejected


# --------------------------------------------------------------------------
# Contextos y unidades (compartidos instance / inline)
# --------------------------------------------------------------------------
def _dim_entry(child: etree._Element, container: str) -> dict | None:
    tag = child.tag
    if not isinstance(tag, str):
        return None
    ns, local = namespace_of(tag), localname(tag)
    dim = child.get("dimension") or ""
    if ns in XBRLDI_NAMESPACES and local == "explicitMember":
        return {"dimension": dim, "member": (child.text or "").strip(),
                "typed": False, "container": container}
    if ns in XBRLDI_NAMESPACES and local == "typedMember":
        inner = "".join(etree.tostring(c, encoding="unicode") for c in child).strip()
        return {"dimension": dim, "content": inner[:4000], "typed": True,
                "container": container}
    if dim:
        # Elemento con atributo `dimension` fuera de xbrldi: se preserva marcado
        # como tipado y con el namespace real, para no perderlo ni afirmar que
        # es explicito.
        inner = etree.tostring(child, encoding="unicode").strip()
        return {"dimension": dim, "content": inner[:4000], "typed": True,
                "container": container, "nonstandard_namespace": ns}
    return None


def _read_dims(ctx: ParsedContext, container: etree._Element, container_name: str) -> None:
    for child in container:
        entry = _dim_entry(child, container_name)
        if entry is None:
            if isinstance(child.tag, str):
                ctx.non_dimensional.append({
                    "container": container_name, "element": child.tag,
                    "xml": etree.tostring(child, encoding="unicode").strip()[:2000]})
            continue
        if entry["typed"]:
            ctx.typed_dimensions.append(entry)
        else:
            ctx.dimensions.append(entry)


def parse_context(el: etree._Element, nsmap: dict | None = None) -> ParsedContext:
    ctx = ParsedContext(context_id=el.get("id") or "")
    entity = el.find(f"{{{XBRLI_NS}}}entity")
    if entity is not None:
        ident = entity.find(f"{{{XBRLI_NS}}}identifier")
        if ident is not None:
            ctx.scheme = ident.get("scheme")
            ctx.identifier = (ident.text or "").strip()
        segment = entity.find(f"{{{XBRLI_NS}}}segment")
        if segment is not None:
            ctx.has_segment = True
            _read_dims(ctx, segment, "segment")
    scenario = el.find(f"{{{XBRLI_NS}}}scenario")
    if scenario is not None:
        ctx.has_scenario = True
        _read_dims(ctx, scenario, "scenario")

    period = el.find(f"{{{XBRLI_NS}}}period")
    if period is not None:
        inst = period.find(f"{{{XBRLI_NS}}}instant")
        beg = period.find(f"{{{XBRLI_NS}}}startDate")
        end = period.find(f"{{{XBRLI_NS}}}endDate")
        forever = period.find(f"{{{XBRLI_NS}}}forever")
        if inst is not None:
            ctx.instant_date = (inst.text or "").strip()
            ctx.period_kind = "INSTANT"
        elif beg is not None and end is not None:
            ctx.start_date = (beg.text or "").strip()
            ctx.end_date = (end.text or "").strip()
            ctx.period_kind = "DURATION"
        elif forever is not None:
            ctx.period_kind = "FOREVER"
    return ctx


def parse_unit(el: etree._Element) -> ParsedUnit:
    ref = el.get("id") or ""
    div = el.find(f"{{{XBRLI_NS}}}divide")
    if div is not None:
        # F-026: los elementos se llaman unitNumerator / unitDenominator en la
        # especificacion XBRL 2.1, no numerator / denominator. Con los nombres
        # equivocados findall no encontraba nada y las 32 unidades DIVIDED
        # quedaban con numerator=[] y denominator=[], perdiendo la unidad de
        # 436 hechos (precios por accion y por barril). El dato SI estaba en el
        # RAW: verificado en 28/28 unidades resolubles.
        num = [m.text.strip() for m
               in div.findall(f"{{{XBRLI_NS}}}unitNumerator/{{{XBRLI_NS}}}measure") if m.text]
        den = [m.text.strip() for m
               in div.findall(f"{{{XBRLI_NS}}}unitDenominator/{{{XBRLI_NS}}}measure") if m.text]
        return ParsedUnit(ref, "DIVIDED", [], num, den)
    measures = [m.text.strip() for m in el.findall(f"{{{XBRLI_NS}}}measure") if m.text]
    return ParsedUnit(ref, "SIMPLE", measures, [], [])


def _resolve_prefix(ns_uri: str, el: etree._Element) -> str:
    if not ns_uri:
        return ""
    for k, v in (el.nsmap or {}).items():
        if v == ns_uri and k:
            return k
    return ""


# --------------------------------------------------------------------------
# Transformaciones numericas (registro ixt / heuristica declarada)
# --------------------------------------------------------------------------
_DOT_DECIMAL = ("numdotdecimal", "numdotdecimalin", "numspacedot", "numwithdot")
_COMMA_DECIMAL = ("numcommadecimal", "numdotcomma", "numspacecomma", "numcomma")
_ZERO = ("zerodash", "fixedzero", "numdash", "nodash")
_EMPTY = ("nocontent", "fixedempty")
_WORDS = ("numwordsen", "numwordsenin")

# ixt-sec:numwordsen — cardinal en palabras. La SEC lo usa sobre todo para
# "no"/"none" (= 0) en notas; se cubre el rango util sin inventar semantica.
_WORD_UNITS = {
    "no": 0, "none": 0, "nil": 0, "zero": 0, "a": 1, "an": 1, "one": 1, "two": 2,
    "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_WORD_SCALES = {"hundred": 100, "thousand": 1000, "million": 10 ** 6,
                "billion": 10 ** 9, "trillion": 10 ** 12}


def _words_to_number(text: str) -> Decimal | None:
    tokens = [t for t in re.split(r"[\s\-]+", text.lower().strip()) if t and t != "and"]
    if not tokens:
        return None
    total = current = 0
    seen = False
    for tok in tokens:
        if tok in _WORD_UNITS:
            current += _WORD_UNITS[tok]
            seen = True
        elif tok in _WORD_SCALES:
            scale = _WORD_SCALES[tok]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            seen = True
        else:
            return None
    return Decimal(total + current) if seen else None


def _norm_format(fmt: str | None) -> str:
    if not fmt:
        return ""
    local = fmt.split(":", 1)[-1].lower()
    return local.replace("-", "").replace("_", "")


def transform_numeric(text_val: str | None, fmt: str | None) -> tuple[Decimal | None, str, str]:
    """Convierte el texto presentado a Decimal.

    Devuelve (valor, regla_aplicada, estado). Estados: APPLIED (formato ixt
    conocido), HEURISTIC (sin formato declarado), UNKNOWN_FORMAT (formato
    declarado pero no soportado), EMPTY. Nunca lanza: un valor irreconocible
    vuelve como None con su estado, para que la capa superior lo registre en
    vez de perderlo.
    """
    if text_val is None:
        return None, "none", "EMPTY"
    raw = text_val.replace("\xa0", " ").replace(" ", " ").strip()
    norm = _norm_format(fmt)

    if norm in _ZERO:
        return Decimal(0), norm, "APPLIED"
    if norm in _EMPTY:
        return None, norm, "APPLIED"
    if not raw:
        return None, norm or "none", "EMPTY"

    negative = False
    body = raw
    if body.startswith("(") and body.endswith(")"):
        negative, body = True, body[1:-1]
    if norm and "paren" in norm:
        negative = True

    if norm in _WORDS:
        val = _words_to_number(body)
        if val is None:
            return None, norm, "UNKNOWN_FORMAT"
        return (-val if negative else val), norm, "APPLIED"

    if norm in _DOT_DECIMAL:
        cleaned = re.sub(r"[^\d.\-]", "", body.replace(",", ""))
        rule, status = norm, "APPLIED"
    elif norm in _COMMA_DECIMAL:
        cleaned = re.sub(r"[^\d.\-]", "",
                         body.replace(".", "").replace(" ", "").replace(",", "."))
        rule, status = norm, "APPLIED"
    elif norm:
        cleaned, rule, status = _heuristic_number(body), f"{norm}->heuristica", "UNKNOWN_FORMAT"
    else:
        cleaned, rule, status = _heuristic_number(body), "heuristica", "HEURISTIC"

    if not cleaned or cleaned in ("-", ".", "-."):
        return None, rule, status
    try:
        val = Decimal(cleaned)
    except InvalidOperation:
        return None, rule, status
    return (-val if negative else val), rule, status


def _heuristic_number(body: str) -> str:
    """Sin formato declarado: el ultimo separador manda. Que fue heuristica
    queda declarado en `transform_status`, nunca oculto."""
    stripped = re.sub(r"[^\d.,\-]", "", body)
    last_dot, last_comma = stripped.rfind("."), stripped.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        if last_comma > last_dot:
            stripped = stripped.replace(".", "").replace(",", ".")
        else:
            stripped = stripped.replace(",", "")
    elif last_comma >= 0:
        tail = stripped[last_comma + 1:]
        stripped = stripped.replace(",", "") if len(tail) == 3 else stripped.replace(",", ".")
    return re.sub(r"[^\d.\-]", "", stripped)


def _apply_scale_sign(val: Decimal | None, scale: str | None,
                      sign: str | None) -> Decimal | None:
    if val is None:
        return None
    if scale not in (None, ""):
        try:
            val = val.scaleb(int(scale))
        except (ValueError, InvalidOperation, TypeError):
            return None
    if sign == "-":
        val = -val
    return val


def _plain_number(text: str | None) -> Decimal | None:
    """Valor de una instancia XBRL clasica: la sintaxis lexica ya es canonica."""
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


# --------------------------------------------------------------------------
# Instancia XBRL clasica
# --------------------------------------------------------------------------
def _instance_parser() -> etree.XMLParser:
    return etree.XMLParser(huge_tree=True, resolve_entities=False,
                           collect_ids=False, recover=False)


def iter_instance_facts(root: etree._Element) -> Iterator[etree._Element]:
    skip_prefixes = (f"{{{XBRLI_NS}}}", f"{{{LINK_NS}}}", f"{{{SCHEMA_NS}}}",
                     f"{{{XBRLDI_NS}}}")
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag.startswith(skip_prefixes):
            continue
        if el.get("contextRef") is None:
            continue
        yield el


def parse_instance_bytes(data: bytes, source_name: str = "") -> InstanceParseResult:
    result = InstanceParseResult(doc_kind="XBRL_INSTANCE")
    try:
        root = etree.fromstring(data, parser=_instance_parser())
    except etree.XMLSyntaxError as exc:
        result.add_error("XML_SYNTAX", exc, source_file=source_name)
        return result
    except ValueError as exc:  # p.ej. declaracion de encoding recibida como str
        result.add_error("XML_INPUT", exc, source_file=source_name)
        return result

    if localname(root.tag) != "xbrl" or namespace_of(root.tag) != XBRLI_NS:
        result.add_error("NOT_AN_INSTANCE", f"raiz {root.tag} no es xbrli:xbrl",
                         source_file=source_name)
        return result

    for el in root.iter(f"{{{XBRLI_NS}}}context"):
        try:
            ctx = parse_context(el)
            if ctx.context_id in result.contexts:
                result.add_error("CONTEXT_DUPLICATE_ID", f"id repetido {ctx.context_id}",
                                 severity="WARNING", source_file=source_name)
            result.contexts[ctx.context_id] = ctx
        except Exception as exc:
            result.add_error("CONTEXT_PARSE", exc, source_file=source_name)
    for el in root.iter(f"{{{XBRLI_NS}}}unit"):
        try:
            u = parse_unit(el)
            result.units[u.unit_ref] = u
        except Exception as exc:
            result.add_error("UNIT_PARSE", exc, source_file=source_name)

    tuples = sum(1 for el in root.iter()
                 if isinstance(el.tag, str) and el.tag == f"{{{XBRLI_NS}}}tuple")
    for el in iter_instance_facts(root):
        qn = etree.QName(el)
        ns = qn.namespace or ""
        prefix = _resolve_prefix(ns, el)
        local = qn.localname
        text_val = el.text
        is_nil = (el.get(f"{{{XSI_NS}}}nil") or "").lower() in ("true", "1")
        unit_ref = el.get("unitRef")
        # Regla XBRL: un item es numerico si y solo si declara unitRef.
        numeric = None if is_nil or unit_ref is None else _plain_number(text_val)
        ctxref = el.get("contextRef")
        ctx = result.contexts.get(ctxref) if ctxref else None
        if ctxref and ctx is None:
            result.add_error("CONTEXT_REF_DANGLING",
                             f"{local} apunta a contextRef inexistente {ctxref}",
                             severity="WARNING", source_file=source_name)
        if unit_ref and unit_ref not in result.units:
            result.add_error("UNIT_REF_DANGLING",
                             f"{local} apunta a unitRef inexistente {unit_ref}",
                             severity="WARNING", source_file=source_name)
        if unit_ref is not None and not is_nil and numeric is None:
            result.add_error("NUMERIC_UNPARSEABLE",
                             f"{local} con unitRef={unit_ref} y valor no numerico: "
                             f"{(text_val or '')[:80]!r}",
                             severity="WARNING", source_file=source_name)
        result.facts.append(ParsedFact(
            tag=local,
            qname=f"{ns}#{local}" if ns else local,
            namespace=ns,
            taxonomy=_taxonomy_of(prefix, ns),
            value_text=None if text_val is None else text_val.strip(),
            value_raw_text=text_val,
            value_numeric=numeric,
            is_numeric=unit_ref is not None and not is_nil,
            is_nil=is_nil,
            unit_ref=unit_ref,
            decimals=el.get("decimals"),
            precision=el.get("precision"),
            context_id=ctxref or None,
            period_kind=(ctx.period_kind if ctx else None),
            element_id=el.get("id"),
            transform_status="DIRECT" if unit_ref else "NOT_NUMERIC",
            doc_kind="XBRL_INSTANCE"))

    _read_footnote_links(root, result)

    if tuples:
        result.add_error("TUPLES_PRESENT", f"{tuples} xbrli:tuple no expandidos",
                         severity="WARNING", source_file=source_name)
    result.stats = _stats(result, extra={"tuples": tuples})
    return result


def _read_footnote_links(root: etree._Element, result: InstanceParseResult) -> None:
    for flink in root.iter(f"{{{LINK_NS}}}footnoteLink"):
        locs: dict[str, str] = {}
        for loc in flink.iter(f"{{{LINK_NS}}}loc"):
            href = loc.get(f"{{{XLINK_NS}}}href") or ""
            locs[loc.get(f"{{{XLINK_NS}}}label") or ""] = href.split("#", 1)[-1]
        notes: dict[str, ParsedFootnote] = {}
        for fn in flink.iter(f"{{{LINK_NS}}}footnote"):
            label = fn.get(f"{{{XLINK_NS}}}label") or ""
            notes[label] = ParsedFootnote(
                footnote_id=fn.get("id") or label,
                role=fn.get(f"{{{XLINK_NS}}}role"),
                lang=fn.get(f"{{{XML_NS}}}lang"),
                text="".join(fn.itertext()).strip()[:4000])
        for arc in flink.iter(f"{{{LINK_NS}}}footnoteArc"):
            src = locs.get(arc.get(f"{{{XLINK_NS}}}from") or "")
            note = notes.get(arc.get(f"{{{XLINK_NS}}}to") or "")
            if note is not None and src:
                note.fact_ids.append(src)
        result.footnotes.extend(notes.values())


def _stats(result: InstanceParseResult, extra: dict | None = None) -> dict:
    empty_ctx = ParsedContext("")
    dim = sum(1 for f in result.facts
              if f.context_id and (result.contexts.get(f.context_id) or empty_ctx).dim_count)
    keys: dict[str, int] = {}
    for f in result.facts:
        keys[f.key] = keys.get(f.key, 0) + 1
    stats = {
        "facts": len(result.facts),
        "contexts": len(result.contexts),
        "units": len(result.units),
        "footnotes": len(result.footnotes),
        "facts_dimensional": dim,
        "facts_numeric": sum(1 for f in result.facts if f.is_numeric),
        "facts_with_value": sum(1 for f in result.facts if f.value_numeric is not None),
        "facts_nil": sum(1 for f in result.facts if f.is_nil),
        "facts_hidden": sum(1 for f in result.facts if f.is_hidden),
        "duplicate_fact_keys": sum(n - 1 for n in keys.values() if n > 1),
        "errors": sum(1 for e in result.errors if e["severity"] == "ERROR"),
        "warnings": sum(1 for e in result.errors if e["severity"] == "WARNING"),
    }
    stats.update(extra or {})
    return stats


# --------------------------------------------------------------------------
# Inline XBRL (iXBRL)
# --------------------------------------------------------------------------
def _inline_parser() -> etree.XMLParser:
    return etree.XMLParser(huge_tree=True, resolve_entities=False,
                           collect_ids=False, recover=True)


def _ix_localname(el: etree._Element, ix_ns: str) -> str | None:
    tag = el.tag
    if not isinstance(tag, str) or not tag.startswith(f"{{{ix_ns}}}"):
        return None
    return localname(tag).lower()


def _collect_text(node: etree._Element, ix_ns: str, out: list[str]) -> None:
    if node.text:
        out.append(node.text)
    for child in node:
        if isinstance(child.tag, str) and child.tag != f"{{{ix_ns}}}exclude":
            _collect_text(child, ix_ns, out)
        if child.tail:
            out.append(child.tail)


def _ix_text(el: etree._Element, ix_ns: str,
             continuations: dict[str, etree._Element]) -> tuple[str, int]:
    """Texto de un hecho inline: concatena descendientes, salta `ix:exclude` y
    sigue la cadena `continuedAt` -> `ix:continuation` (con guarda de ciclos)."""
    chunks: list[str] = []
    steps = 0
    visited: set[int] = set()
    node: etree._Element | None = el
    while node is not None:
        if id(node) in visited:
            break
        visited.add(id(node))
        _collect_text(node, ix_ns, chunks)
        cont_id = node.get("continuedAt")
        node = continuations.get(cont_id) if cont_id else None
        if node is not None:
            steps += 1
    return "".join(chunks).strip(), steps


def parse_inline_bytes(data: bytes, source_name: str = "") -> InstanceParseResult:
    """Extrae hechos de un documento Inline XBRL (XHTML).

    Contextos y unidades viven en ix:header/ix:resources con sintaxis xbrli
    estandar; los hechos son ix:nonFraction / ix:nonNumeric / ix:fraction y
    pueden estar dentro de ix:hidden.
    """
    result = InstanceParseResult(doc_kind="INLINE_XBRL")
    parser = _inline_parser()
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        result.add_error("IXML_SYNTAX", exc, source_file=source_name)
        return result
    except ValueError as exc:
        result.add_error("IXML_INPUT", exc, source_file=source_name)
        return result
    if root is None:
        result.add_error("IXML_EMPTY", "documento inline sin raiz", source_file=source_name)
        return result
    defects = list(parser.error_log or [])
    if defects:
        result.add_error("IXML_RECOVERED",
                         f"lxml recupero {len(defects)} defectos de marcado; primeros: "
                         f"{[str(d) for d in defects[:3]]}",
                         severity="WARNING", source_file=source_name)

    ix_ns = next((u for u in (root.nsmap or {}).values() if u in IXBRL_NAMESPACES), None)
    if ix_ns is None:
        for cand in IXBRL_NAMESPACES:
            if root.find(f".//{{{cand}}}header") is not None:
                ix_ns = cand
                break
    if ix_ns is None:
        result.add_error("IX_NAMESPACE_MISSING", "documento sin namespace inline XBRL",
                         source_file=source_name)
        return result

    for el in root.iter(f"{{{XBRLI_NS}}}context"):
        ctx = parse_context(el)
        result.contexts[ctx.context_id] = ctx
    for el in root.iter(f"{{{XBRLI_NS}}}unit"):
        u = parse_unit(el)
        result.units[u.unit_ref] = u
    if not result.contexts:
        result.add_error("IX_RESOURCES_EMPTY", "ix:resources sin contextos xbrli",
                         severity="WARNING", source_file=source_name)

    continuations: dict[str, etree._Element] = {}
    for el in root.iter(f"{{{ix_ns}}}continuation"):
        cid = el.get("id")
        if cid:
            continuations[cid] = el
    hidden_ids: set[int] = set()
    for hid in root.iter(f"{{{ix_ns}}}hidden"):
        for el in hid.iter():
            hidden_ids.add(id(el))

    tuples = sum(1 for _ in root.iter(f"{{{ix_ns}}}tuple"))
    if tuples:
        result.add_error("IX_TUPLES_PRESENT", f"{tuples} ix:tuple no expandidos",
                         severity="WARNING", source_file=source_name)

    for el in root.iter():
        local = _ix_localname(el, ix_ns)
        if local not in IX_FACT_LOCALS:
            continue
        result.facts.append(_inline_fact(el, ix_ns, local, continuations,
                                         hidden_ids, result, source_name))

    _read_ix_footnotes(root, ix_ns, result)

    result.stats = _stats(result, extra={"continuations": len(continuations),
                                         "tuples": tuples, "ix_namespace": ix_ns})
    return result


def _inline_fact(el: etree._Element, ix_ns: str, local: str,
                 continuations: dict[str, etree._Element], hidden_ids: set[int],
                 result: InstanceParseResult, source_name: str) -> ParsedFact:
    name_attr = el.get("name") or ""
    pfx, _, lname = name_attr.partition(":")
    ns_uri = (el.nsmap or {}).get(pfx, "") if pfx else ""
    if pfx and not ns_uri:
        result.add_error("IX_PREFIX_UNRESOLVED",
                         f"prefijo {pfx!r} sin declaracion de namespace en {name_attr}",
                         severity="WARNING", source_file=source_name)
    ctxref = el.get("contextRef")
    ctx = result.contexts.get(ctxref) if ctxref else None
    if ctxref and ctx is None:
        result.add_error("CONTEXT_REF_DANGLING",
                         f"{name_attr} apunta a contextRef inexistente {ctxref}",
                         severity="WARNING", source_file=source_name)
    unit_ref = el.get("unitRef")
    if unit_ref and unit_ref not in result.units:
        result.add_error("UNIT_REF_DANGLING",
                         f"{name_attr} apunta a unitRef inexistente {unit_ref}",
                         severity="WARNING", source_file=source_name)
    is_nil = (el.get(f"{{{XSI_NS}}}nil") or "").lower() in ("true", "1")
    fmt = el.get("format")
    scale, sign = el.get("scale"), el.get("sign")
    raw_text, steps = _ix_text(el, ix_ns, continuations)

    numeric: Decimal | None = None
    if local == "nonfraction":
        if is_nil:
            rule, status = "nil", "APPLIED"
        else:
            numeric, rule, status = transform_numeric(raw_text, fmt)
            numeric = _apply_scale_sign(numeric, scale, sign)
            if numeric is None:
                result.add_error("IX_NUMERIC_UNPARSEABLE",
                                 f"{name_attr} format={fmt} valor={raw_text[:60]!r} "
                                 f"-> sin valor numerico ({status})",
                                 severity="WARNING", source_file=source_name)
        is_num = True
    elif local == "fraction":
        numeric, rule, status = _inline_fraction(el, ix_ns, continuations, result,
                                                 name_attr, source_name)
        numeric = _apply_scale_sign(numeric, scale, sign)
        is_num = True
    else:
        rule, status = "none", "NOT_NUMERIC"
        is_num = False

    return ParsedFact(
        tag=lname or name_attr,
        qname=f"{ns_uri}#{lname}" if ns_uri else name_attr,
        namespace=ns_uri,
        taxonomy=_taxonomy_of(pfx, ns_uri),
        value_text=raw_text or None,
        value_raw_text=raw_text or None,
        value_numeric=None if is_nil else numeric,
        is_numeric=is_num and not is_nil,
        is_nil=is_nil,
        unit_ref=unit_ref,
        decimals=el.get("decimals"),
        precision=el.get("precision"),
        context_id=ctxref,
        period_kind=(ctx.period_kind if ctx else None),
        element_id=el.get("id"),
        scale=scale,
        sign=sign,
        ix_format=fmt,
        numeric_transform=rule,
        transform_status=status,
        is_hidden=id(el) in hidden_ids,
        is_escaped=(el.get("escape") or "").lower() in ("true", "1"),
        ix_target=el.get("target"),
        continuation_steps=steps,
        doc_kind="INLINE_XBRL")


def _inline_fraction(el: etree._Element, ix_ns: str,
                     continuations: dict[str, etree._Element],
                     result: InstanceParseResult, name_attr: str,
                     source_name: str) -> tuple[Decimal | None, str, str]:
    num_el = el.find(f"{{{ix_ns}}}numerator")
    den_el = el.find(f"{{{ix_ns}}}denominator")
    if num_el is None or den_el is None:
        result.add_error("IX_FRACTION_INCOMPLETA", f"{name_attr} sin numerator/denominator",
                         severity="WARNING", source_file=source_name)
        return None, "fraction", "EMPTY"
    n_txt, _ = _ix_text(num_el, ix_ns, continuations)
    d_txt, _ = _ix_text(den_el, ix_ns, continuations)
    n_val, _r1, s1 = transform_numeric(n_txt, num_el.get("format"))
    d_val, _r2, s2 = transform_numeric(d_txt, den_el.get("format"))
    n_val = _apply_scale_sign(n_val, num_el.get("scale"), num_el.get("sign"))
    d_val = _apply_scale_sign(d_val, den_el.get("scale"), den_el.get("sign"))
    if n_val is None or d_val is None or d_val == 0:
        result.add_error("IX_FRACTION_NO_EVALUABLE",
                         f"{name_attr} numerador={n_txt[:30]!r} denominador={d_txt[:30]!r}",
                         severity="WARNING", source_file=source_name)
        return None, "fraction", "EMPTY"
    return n_val / d_val, "fraction", ("APPLIED" if s1 == s2 == "APPLIED" else "HEURISTIC")


def _read_ix_footnotes(root: etree._Element, ix_ns: str,
                       result: InstanceParseResult) -> None:
    notes: dict[str, ParsedFootnote] = {}
    for fn in root.iter(f"{{{ix_ns}}}footnote"):
        fid = fn.get("id") or ""
        notes[fid] = ParsedFootnote(
            footnote_id=fid,
            role=fn.get(f"{{{XLINK_NS}}}role") or fn.get("footnoteRole"),
            lang=fn.get(f"{{{XML_NS}}}lang"),
            text="".join(fn.itertext()).strip()[:4000])
    for rel in root.iter(f"{{{ix_ns}}}relationship"):
        for to_ref in (rel.get("toRefs") or "").split():
            note = notes.get(to_ref)
            if note is not None:
                note.fact_ids.extend((rel.get("fromRefs") or "").split())
    result.footnotes.extend(notes.values())


# --------------------------------------------------------------------------
# Linkbases
# --------------------------------------------------------------------------
def _linkbase_of(parent: etree._Element | None, arc_role: str, source_hint: str) -> str:
    """Prioridad: nombre del extended link > arcrole > sufijo de archivo."""
    if parent is not None and isinstance(parent.tag, str):
        kind = EXTENDED_LINK_TO_LINKBASE.get(localname(parent.tag))
        if kind:
            return kind
    kind = ARC_ROLE_TO_LINKBASE.get(arc_role)
    if kind:
        return kind
    low = (source_hint or "").lower()
    for suffix, name in SUFFIX_TO_LINKBASE:
        if low.endswith(suffix):
            return name
    return "DEFINITION"


def parse_linkbase_bytes(data: bytes, source_hint: str = "") -> list[ParsedRelation]:
    """Relaciones de linkbase, resolviendo labels DENTRO de cada extended link.

    El alcance de `xlink:label` es el extended link, no el archivo: resolver
    globalmente multiplica las relaciones por cruce entre roles distintos
    (medido: 26x en la definition linkbase de un 20-F real).
    Sirve tambien para XSD con linkbases embebidas en `xs:appinfo`.
    """
    rels: list[ParsedRelation] = []
    try:
        root = etree.fromstring(data, parser=_instance_parser())
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"linkbase XML invalido ({source_hint}): {exc}") from exc

    for link in root.iter():
        if link.get(f"{{{XLINK_NS}}}type") != "extended":
            continue
        rels.extend(_relations_of_extended_link(link, source_hint))
    return rels


def _relations_of_extended_link(link: etree._Element,
                                source_hint: str) -> list[ParsedRelation]:
    # xlink:label NO es unico dentro del link: un mismo label puede tener varios
    # locators o varios resources (label terse/verbose). Se indexa a lista y el
    # arco se abanica sobre los que existan realmente en ESTE link.
    loc_targets: dict[str, list[tuple[str, str]]] = {}
    resources: dict[str, list[dict]] = {}
    arcs: list[etree._Element] = []
    for child in link.iter():
        xtype = child.get(f"{{{XLINK_NS}}}type")
        if xtype == "locator":
            href = child.get(f"{{{XLINK_NS}}}href") or ""
            label = child.get(f"{{{XLINK_NS}}}label") or ""
            loc_targets.setdefault(label, []).append(
                (href.split("#", 1)[1] if "#" in href else "", href))
        elif xtype == "resource":
            resources.setdefault(child.get(f"{{{XLINK_NS}}}label") or "", []).append({
                "role": child.get(f"{{{XLINK_NS}}}role") or "",
                "lang": child.get(f"{{{XML_NS}}}lang"),
                "text": "".join(child.itertext()).strip(),
                "value": (child.get("value") or "").strip() or None,
                "id": child.get("id")})
        elif xtype == "arc":
            arcs.append(child)

    link_role = link.get(f"{{{XLINK_NS}}}role")
    out: list[ParsedRelation] = []
    for arc in arcs:
        arc_role = arc.get(f"{{{XLINK_NS}}}arcrole") or ""
        lb = _linkbase_of(arc.getparent(), arc_role, source_hint)
        from_l = arc.get(f"{{{XLINK_NS}}}from") or ""
        to_l = arc.get(f"{{{XLINK_NS}}}to") or ""
        base = dict(
            linkbase=lb, role=link_role, arc_role=arc_role or None,
            weight=_as_float(arc.get("weight")), order_num=_as_float(arc.get("order")),
            preferred_sign=arc.get("preferredLabel"),
            dimension_qname=arc.get(f"{{{XBRLDT_NS}}}dimension") or arc.get("dimension"),
            use=arc.get("use"), priority=_as_float(arc.get("priority")),
            target_role=arc.get(f"{{{XBRLDT_NS}}}targetRole"),
            closed=arc.get(f"{{{XBRLDT_NS}}}closed"),
            context_element=arc.get(f"{{{XBRLDT_NS}}}contextElement"))
        froms = loc_targets.get(from_l) or [(from_l, "")]
        tos_locs = loc_targets.get(to_l)
        tos_res = resources.get(to_l)
        for frm_frag, frm_href in froms:
            if tos_res and lb in ("LABEL", "REFERENCE", "FOOTNOTE"):
                for res in tos_res:
                    out.append(ParsedRelation(
                        from_qname=frm_frag, to_qname=res.get("id") or to_l,
                        from_href=frm_href or None, to_href=None,
                        label_type=(res["role"] or "").rsplit("/", 1)[-1] or None,
                        lang=res["lang"],
                        label_text=(res["value"] or res["text"]) or None,
                        member_qname=res["value"], **base))
            elif tos_locs:
                for to_frag, to_href in tos_locs:
                    out.append(ParsedRelation(
                        from_qname=frm_frag, to_qname=to_frag,
                        from_href=frm_href or None, to_href=to_href or None,
                        member_qname=to_frag if "domain" in arc_role else None, **base))
            else:
                out.append(ParsedRelation(from_qname=frm_frag, to_qname=to_l or None,
                                          from_href=frm_href or None, **base))
    return out


def _as_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Schemas (XSD)
# --------------------------------------------------------------------------
def parse_schema_bytes(data: bytes, source_name: str) -> list[ParsedConcept]:
    concepts: list[ParsedConcept] = []
    try:
        root = etree.fromstring(data, parser=_instance_parser())
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"schema XML invalido ({source_name}): {exc}") from exc
    target_ns = root.get("targetNamespace") or ""
    taxonomy = _taxonomy_of(_prefix_for_target(root, target_ns), target_ns)
    for elem in root.iter(f"{{{SCHEMA_NS}}}element"):
        name = elem.get("name")
        if not name:
            continue
        label = documentation = None
        for ann in elem.iter(f"{{{SCHEMA_NS}}}documentation"):
            text = "".join(ann.itertext()).strip()
            if text and documentation is None:
                documentation = text
        for lab in elem.iter(f"{{{LINK_NS}}}label"):
            text = "".join(lab.itertext()).strip()
            if text and label is None:
                label = text
        sub_group = elem.get("substitutionGroup") or ""
        sub_local = sub_group.split(":", 1)[-1]
        concepts.append(ParsedConcept(
            namespace=target_ns or None, tag=name, qname=f"{target_ns}#{name}",
            label=label, documentation=documentation,
            xsd_type=elem.get("type"),
            period_type=elem.attrib.get(f"{{{XBRLI_NS}}}periodType"),
            balance=elem.attrib.get(f"{{{XBRLI_NS}}}balance"),
            abstract=(elem.get("abstract") or "false").lower() in ("true", "1"),
            taxonomy=taxonomy, source_schema=source_name,
            element_id=elem.get("id"),
            substitution_group=sub_group or None,
            nillable=(elem.get("nillable") or "false").lower() in ("true", "1"),
            is_dimension=sub_local == "dimensionItem",
            is_hypercube=sub_local == "hypercubeItem",
            is_custom=not is_standard_taxonomy(taxonomy)))
    return concepts


def _prefix_for_target(root: etree._Element, target_ns: str) -> str:
    for k, v in (root.nsmap or {}).items():
        if v == target_ns and k:
            return k
    return ""


# --------------------------------------------------------------------------
# CompanyFacts (contraste, no fuente)
# --------------------------------------------------------------------------
def companyfacts_index(cf_json: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for tax, concepts in (cf_json.get("facts") or {}).items():
        for tag, payload in concepts.items():
            units = payload.get("units") or {}
            obs = 0
            end_periods: set[str] = set()
            unit_kinds: set[str] = set()
            for ukind, rows in units.items():
                unit_kinds.add(ukind)
                obs += len(rows)
                for r in rows:
                    if r.get("end"):
                        end_periods.add(str(r["end"]))
            out[f"{tax}#{tag}"] = {
                "taxonomy": tax, "tag": tag, "obs": obs,
                "unit_kinds": sorted(unit_kinds),
                "first_period": min(end_periods) if end_periods else None,
                "last_period": max(end_periods) if end_periods else None,
                "label": payload.get("label"), "description": payload.get("description")}
    return out


# --------------------------------------------------------------------------
# Helpers de serializacion / zip
# --------------------------------------------------------------------------
def dimensions_json(ctx: ParsedContext) -> str:
    return json.dumps(ctx.dimensions, ensure_ascii=False)


def typed_dimensions_json(ctx: ParsedContext) -> str | None:
    if not ctx.typed_dimensions:
        return None
    return json.dumps(ctx.typed_dimensions, ensure_ascii=False)


def iter_zip_members(zip_path: Path) -> Iterator[tuple[str, bytes]]:
    with zipfile.ZipFile(zip_path) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            yield info.filename, zf.read(info)


def zip_instance_candidates(members_or_path) -> list[str]:
    """Miembros de un zip que SON instancias XBRL, verificado por contenido.

    Acepta una ruta a zip (clasificacion real) o una lista de nombres
    (compatibilidad: en ese caso solo puede filtrar por nombre).
    """
    if isinstance(members_or_path, (str, Path)):
        path = Path(members_or_path)
        out: list[str] = []
        with zipfile.ZipFile(path) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                if info.is_dir() or not info.filename.lower().endswith((".xml", ".xbrl")):
                    continue
                if sniff_document(info.filename, zf.read(info)).kind == "XBRL_INSTANCE":
                    out.append(info.filename)
        return out
    return _candidates_by_name(list(members_or_path))


def _candidates_by_name(members: list[str]) -> list[str]:
    out: list[str] = []
    for m in sorted(members):
        base = m.lower().rsplit("/", 1)[-1]
        if not base.endswith((".xml", ".xbrl")):
            continue
        if any(base.endswith(sfx) for sfx, _ in SUFFIX_TO_LINKBASE):
            continue
        if base.startswith(("filingsummary", "metalinks", "report")) or base == "manifest.xml":
            continue
        out.append(m)
    return out
