"""Discovery CNV: pagina empresa -> inventario de presentaciones; visor -> metadata + adjuntos.

Reglas duras heredadas de C0/C1/C2:

* La identidad NUNCA se resuelve por similitud de nombre: solo por CUIT.
* `CONTROLADA` y `VINCULADA` son relaciones DISTINTAS y se preservan como tales.
* Una fila legacy `BALANCE SUBSIDIARIA` no declara relacion ni CUIT: su relacion es
  UNKNOWN. Asumirla CONTROLADA seria inventar identidad.
* Las controladas no tienen perfil propio en CNV (C2-CNV-002): su unica fuente es el
  titulo `RELAC.:` publicado bajo el perfil de la controlante.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

PARSER_VERSION = "cnv-discovery-v1"

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
         "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}

RE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
RE_HEADER = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.S | re.I)
RE_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
RE_GUID = re.compile(r"publicview/([0-9a-fA-F-]{36})")
RE_TAG = re.compile(r"<[^>]+>")

# Clases del inventario C3. Sustituyen a EEFF_CONTROLADA de C0, que mezclaba
# 78 filas con relacion declarada y 57 filas legacy sin relacion ni CUIT.
CLASE_EEFF_PROPIO = "EEFF_PROPIO"
CLASE_EEFF_CONTROLADA = "EEFF_RELACIONADA_CONTROLADA"
CLASE_EEFF_VINCULADA = "EEFF_RELACIONADA_VINCULADA"
CLASE_EEFF_RELAC_OTRA = "EEFF_RELACIONADA_OTRA"
CLASE_EEFF_LEGACY_PROPIO = "EEFF_LEGACY_PROPIO"
CLASE_EEFF_SUBSIDIARIA_LEGACY = "EEFF_SUBSIDIARIA_LEGACY"
CLASE_ACTA = "ACTA_EECC"
CLASE_ON = "INFORME_TRIMESTRAL_ON"
CLASE_HR = "HECHO_RELEVANTE"
CLASE_OTRO = "OTRO"

CLASES_FINANCIERAS = {CLASE_EEFF_PROPIO, CLASE_EEFF_CONTROLADA, CLASE_EEFF_VINCULADA,
                      CLASE_EEFF_RELAC_OTRA, CLASE_EEFF_LEGACY_PROPIO,
                      CLASE_EEFF_SUBSIDIARIA_LEGACY}
CLASES_PROPIAS = {CLASE_EEFF_PROPIO, CLASE_EEFF_LEGACY_PROPIO}


@dataclass
class Presentation:
    guid: str
    presentation_id: str | None = None
    fecha_publicacion: str | None = None
    hora: str | None = None
    seccion: str | None = None
    secciones: list[str] = field(default_factory=list)
    titulo: str = ""
    url: str = ""
    clase: str = CLASE_OTRO
    ambito: str = "NO_FINANCIERO"          # PROPIO | RELACIONADA | NO_FINANCIERO
    relacion: str | None = None            # CONTROLADA | VINCULADA | None
    relacion_origen: str = "AUSENTE"       # DECLARADA | AUSENTE
    cuit_relacionado: str | None = None
    nombre_relacionado: str | None = None
    sigla_legacy: str | None = None
    norma_contable: str | None = None
    tipo_balance: str | None = None
    periodicidad_raw: str | None = None
    periodicidad_norm: str | None = None
    periodicidad_origen: str = "AUSENTE"
    fecha_cierre: str | None = None
    anio_cierre: int | None = None
    ocurrencias: int = 1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["secciones"] = "|".join(self.secciones)
        return d


def normalize_cuit(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 11 else (digits or None)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", RE_TAG.sub(" ", fragment)).strip()


def _parse_fecha_es(value: str | None) -> str | None:
    """'22 abr. 2026' -> '2026-04-22'."""
    if not value:
        return None
    m = re.match(r"(\d{1,2})\s+([a-zA-Zñ]{3,4})\.?\s+(\d{4})", value.strip())
    if not m:
        return None
    mes = MESES.get(m.group(2)[:3].lower())
    if not mes:
        return None
    return f"{int(m.group(3)):04d}-{mes:02d}-{int(m.group(1)):02d}"


def _parse_fecha_dmy(value: str | None) -> str | None:
    """'31-12-2025' -> '2025-12-31'. Tambien acepta ya-ISO."""
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", value)
    if not m:
        return None
    return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"


# CNV mezcla periodicidad textual ('TRIMESTRAL') y codigo numerico ('1', '3').
# El codigo NO es una cantidad de meses: la evidencia del perfil CEPU es que el
# codigo 1 aparece SIEMPRE con cierre en diciembre (8/8) y el codigo 3 SIEMPRE con
# cierre en marzo/junio/septiembre (26/26). De ahi el mapeo. Un codigo no observado
# no se adivina: se marca para revision.
PERIODICIDAD_TEXTO = {"ANUAL", "SEMESTRAL", "TRIMESTRAL", "MENSUAL"}
PERIODICIDAD_CODIGO = {"1": "ANUAL", "3": "TRIMESTRAL"}


def normalize_periodicidad(value: str | None) -> tuple[str | None, str]:
    """Devuelve (periodicidad_normalizada, origen)."""
    if not value:
        return None, "AUSENTE"
    v = value.strip().upper()
    if v in PERIODICIDAD_TEXTO:
        return v, "TEXTO"
    if v in PERIODICIDAD_CODIGO:
        return PERIODICIDAD_CODIGO[v], "CODIGO_CNV"
    if v.isdigit():
        return None, f"CODIGO_SIN_MAPEO:{v}"
    return v, "TEXTO_LIBRE"


def _field(titulo: str, label: str) -> str | None:
    """Extrae 'LABEL: valor' de un titulo cuyos campos se separan con ' - '.

    El separador exige espacios alrededor del guion, para que valores con guiones
    internos ('2026-06-30', '30-71190058-2') no se corten por la mitad.
    """
    m = re.search(rf"{re.escape(label)}\s*:\s*(.*?)(?=\s+-\s|\s*$)", titulo, re.I)
    if not m:
        return None
    val = m.group(1).strip().strip(".").strip()
    return val or None


def classify(titulo: str, seccion: str | None) -> tuple[str, str]:
    """Devuelve (clase, ambito). Solo mira el texto declarado por CNV."""
    t = titulo.upper()
    sec = (seccion or "").upper()
    if "RELAC.:" in t:
        if re.search(r"RELAC\.:\s*CONTROLADA", t):
            return CLASE_EEFF_CONTROLADA, "RELACIONADA"
        if re.search(r"RELAC\.:\s*VINCULADA", t):
            return CLASE_EEFF_VINCULADA, "RELACIONADA"
        return CLASE_EEFF_RELAC_OTRA, "RELACIONADA"
    if t.startswith("NORMA CONTABLE:"):
        return CLASE_EEFF_PROPIO, "PROPIO"
    if t.startswith("BALANCE SUBSIDIARIA"):
        return CLASE_EEFF_SUBSIDIARIA_LEGACY, "RELACIONADA"
    if re.match(r"BALANCE\s+(CONSOLIDADO|INDIVIDUAL|TRIMESTRAL|ANUAL)", t):
        return CLASE_EEFF_LEGACY_PROPIO, "PROPIO"
    if "INFORME TRIMESTRAL ON" in t or "INFORME TRIMESTRAL ON" in sec:
        return CLASE_ON, "NO_FINANCIERO"
    if "ACTA" in t and ("EECC" in t or "ESTADOS CONTABLES" in t or "BALANCE" in t):
        return CLASE_ACTA, "NO_FINANCIERO"
    if "HECHO RELEVANTE" in t or "HECHOS RELEVANTES" in sec:
        return CLASE_HR, "NO_FINANCIERO"
    return CLASE_OTRO, "NO_FINANCIERO"


def parse_presentation_row(tr_html: str, seccion: str | None) -> Presentation | None:
    guid_m = RE_GUID.search(tr_html)
    if not guid_m:
        return None
    guid = guid_m.group(1).lower()
    celdas = [_text(c) for c in RE_TD.findall(tr_html)]
    celdas = [c for c in celdas if c and c not in ("add_circle_outline",)]
    fecha = next((f for f in (_parse_fecha_es(c) for c in celdas[:2]) if f), None)
    hora = next((c for c in celdas[:3] if re.fullmatch(r"\d{1,2}:\d{2}", c)), None)
    pres_id = next((c for c in celdas if re.fullmatch(r"\d{4,10}", c)), None)
    # El titulo es la celda mas larga que no sea fecha, hora ni id numerico.
    candidatas = [c for c in celdas
                  if not re.fullmatch(r"\d{1,2}:\d{2}", c)
                  and not re.fullmatch(r"\d{1,10}", c)
                  and _parse_fecha_es(c) is None]
    titulo = max(candidatas, key=len, default="")

    clase, ambito = classify(titulo, seccion)
    p = Presentation(guid=guid, presentation_id=pres_id, fecha_publicacion=fecha, hora=hora,
                     seccion=seccion, secciones=[seccion] if seccion else [],
                     titulo=titulo, clase=clase, ambito=ambito,
                     url=f"https://aif2.cnv.gov.ar/presentations/publicview/{guid}")

    if clase in (CLASE_EEFF_CONTROLADA, CLASE_EEFF_VINCULADA, CLASE_EEFF_RELAC_OTRA):
        rel = _field(titulo, "RELAC.")
        p.relacion = rel.upper() if rel else None
        p.relacion_origen = "DECLARADA" if rel else "AUSENTE"
        p.cuit_relacionado = normalize_cuit(_field(titulo, "CUIT"))
        p.nombre_relacionado = _nombre_relacionado(titulo)
        p.fecha_cierre = _parse_fecha_dmy(_field(titulo, "FECH. CIERRE BAL."))
        p.norma_contable = _field(titulo, "NORMA CONT.")
        p.periodicidad_raw = _field(titulo, "PERIODO BAL.")
        p.periodicidad_norm, p.periodicidad_origen = normalize_periodicidad(p.periodicidad_raw)
        p.tipo_balance = _upper(_field(titulo, "TIPO BAL."))
    elif clase == CLASE_EEFF_PROPIO:
        p.norma_contable = _field(titulo, "NORMA CONTABLE")
        p.tipo_balance = _upper(_field(titulo, "TIPO BALANCE"))
        p.periodicidad_raw = _field(titulo, "PERIODICIDAD")
        p.periodicidad_norm, p.periodicidad_origen = normalize_periodicidad(p.periodicidad_raw)
        p.fecha_cierre = _parse_fecha_dmy(_field(titulo, "FECHA CIERRE"))
    elif clase in (CLASE_EEFF_SUBSIDIARIA_LEGACY, CLASE_EEFF_LEGACY_PROPIO):
        # 'BALANCE SUBSIDIARIA - 12-2017 - CPR - ESTADOS CONTABLES - BALANCE SUBSIDIARIA'
        mm = re.search(r"-\s*(\d{2})-(\d{4})\s*-", titulo)
        if mm:
            p.fecha_cierre = f"{mm.group(2)}-{mm.group(1)}-00"  # dia desconocido: vive en el documento
        if clase == CLASE_EEFF_SUBSIDIARIA_LEGACY:
            p.sigla_legacy = _sigla_legacy(titulo)
            p.relacion = None            # NUNCA asumir CONTROLADA: CNV no la declara aqui
            p.relacion_origen = "AUSENTE"
        else:
            p.tipo_balance = "CONSOLIDADO" if "CONSOLIDADO" in titulo.upper() else \
                             ("INDIVIDUAL" if "INDIVIDUAL" in titulo.upper() else None)
    if p.fecha_cierre and re.match(r"^\d{4}", p.fecha_cierre):
        p.anio_cierre = int(p.fecha_cierre[:4])
    return p


def _upper(value: str | None) -> str | None:
    return value.upper() if value else None


def _nombre_relacionado(titulo: str) -> str | None:
    m = re.search(r"CUIT:\s*[\d-]+\s*-\s*(.+?)\s*-\s*FECH\.\s*CIERRE", titulo, re.I)
    return m.group(1).strip() if m else None


def _sigla_legacy(titulo: str) -> str | None:
    partes = [p.strip() for p in titulo.split(" - ")]
    for parte in partes[1:]:
        if re.fullmatch(r"[A-Z]{2,10}", parte):
            return parte
        m = re.fullmatch(r"ESTADOS (?:CONTABLES|FINANCIEROS)\s+([A-Z]{2,12})", parte.upper())
        if m:
            return m.group(1)
    return None


def parse_empresa_page(html: str) -> tuple[list[Presentation], dict]:
    """Recorre el documento en orden para asociar cada fila a su encabezado de seccion."""
    eventos: list[tuple[int, str, str]] = []
    for m in RE_HEADER.finditer(html):
        eventos.append((m.start(), "H", _text(m.group(1))))
    for m in RE_ROW.finditer(html):
        eventos.append((m.start(), "TR", m.group(1)))
    eventos.sort(key=lambda e: e[0])

    seccion: str | None = None
    por_guid: dict[str, Presentation] = {}
    filas = 0
    for _, tipo, payload in eventos:
        if tipo == "H":
            if payload:
                seccion = payload
            continue
        p = parse_presentation_row(payload, seccion)
        if p is None:
            continue
        filas += 1
        prev = por_guid.get(p.guid)
        if prev is None:
            por_guid[p.guid] = p
        else:
            # Duplicado benigno: la misma presentacion aparece en 'Ultima Informacion
            # Recibida' y en su seccion tematica. Se conservan ambas ubicaciones.
            prev.ocurrencias += 1
            if p.seccion and p.seccion not in prev.secciones:
                prev.secciones.append(p.seccion)
            if prev.clase == CLASE_OTRO and p.clase != CLASE_OTRO:
                por_guid[p.guid] = p
                p.ocurrencias = prev.ocurrencias
                p.secciones = prev.secciones
    resumen = {"filas_con_guid": filas, "guids_unicos": len(por_guid),
               "duplicados_por_seccion": filas - len(por_guid)}
    return list(por_guid.values()), resumen


# ---------------------------------------------------------------- visor ------
@dataclass
class Attachment:
    blob_guid: str
    nombre: str
    tamano: str | None = None
    hash_cnv: str | None = None
    propiedad: str | None = None


@dataclass
class ViewerMeta:
    guid: str
    form_type_id: str | None = None
    form_type_name: str | None = None
    presentation_id: str | None = None
    society_name: str | None = None
    presentation_date: str | None = None
    csrf_token: str | None = None
    unidad_medida: str | None = None
    fecha_cierre: str | None = None
    tipo_balance: str | None = None
    moneda: str | None = None
    inline_codes: int = 0
    attachments: list[Attachment] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["attachments"] = [asdict(a) for a in self.attachments]
        return d


RE_UPLOADER = re.compile(r'uploader="[^"]*"\s*>\s*(\[\s*\{.*?\}\s*\])\s*</propiedad>', re.S)
RE_PROP_ID = re.compile(r'<propiedad\s+id="([^"]+)"[^>]*uploader="[^"]*"\s*>\s*\[', re.S)


def _js_var(text: str, name: str) -> str | None:
    m = re.search(rf"var\s+{re.escape(name)}\s*=\s*'([^']*)'", text) or \
        re.search(rf'var\s+{re.escape(name)}\s*=\s*"([^"]*)"', text)
    if not m:
        return None
    return m.group(1).strip() or None


def parse_viewer(html: str, guid: str) -> ViewerMeta:
    meta = ViewerMeta(guid=guid.lower())
    meta.form_type_id = _js_var(html, "formTypeId")
    meta.form_type_name = _js_var(html, "formTypeName")
    meta.presentation_id = _js_var(html, "presentationIdGlobal")
    meta.society_name = _js_var(html, "societyName")
    meta.presentation_date = _js_var(html, "presentationDate")
    tok = re.search(r'id="RequestVerificationToken"[^>]*value="([^"]+)"', html)
    meta.csrf_token = tok.group(1) if tok else None
    meta.inline_codes = len(re.findall(r"claveinformativa", html))
    for label, attr in (("unidad_medida", "UnidadMedida"), ("fecha_cierre", "FechaCierre"),
                        ("tipo_balance", "TipoBalance"), ("moneda", "Moneda")):
        m = re.search(rf'claveinformativa="{attr}"[^>]*>([^<]{{1,80}})</propiedad>', html)
        if m:
            setattr(meta, label, m.group(1).strip() or None)
    if meta.fecha_cierre:
        meta.fecha_cierre = _parse_fecha_dmy(meta.fecha_cierre) or meta.fecha_cierre

    prop_ids = RE_PROP_ID.findall(html)
    for i, block in enumerate(RE_UPLOADER.findall(html)):
        try:
            items = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in items:
            blob_guid = (item.get("guid") or "").strip().lower()
            nombre = (item.get("nombreArchivo") or "").strip()
            if not blob_guid or not nombre:
                continue
            meta.attachments.append(Attachment(
                blob_guid=blob_guid, nombre=nombre, tamano=item.get("tamano"),
                hash_cnv=item.get("hash"), propiedad=prop_ids[i] if i < len(prop_ids) else None))
    return meta
