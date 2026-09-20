# -*- coding: utf-8 -*-
"""Genera el deck de demostración de resultados de Catalaxia (cliente),
con la paleta y tipografía de la marca webshooks.

    python demo_catalaxia.py
    -> docs/proyecto/Catalaxia_Demostracion_Resultados.pptx

Requiere: python-pptx.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---- Paleta webshooks ----
NAVY = RGBColor(0x1A, 0x27, 0x44)
BLUE = RGBColor(0x3B, 0x82, 0xF6)
ORANGE = RGBColor(0xF5, 0x82, 0x1F)
GREEN = RGBColor(0x43, 0xA0, 0x47)
BODY = RGBColor(0x3A, 0x44, 0x58)
GRAY = RGBColor(0x6B, 0x75, 0x89)
BLUEBG = RGBColor(0xDC, 0xEA, 0xFF)
GREENBG = RGBColor(0xE7, 0xF7, 0xEC)
ZEBRA = RGBColor(0xF4, 0xF8, 0xFE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xD6, 0xE2, 0xF2)
FONT = "Calibri"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, os.pardir, "proyecto", "Catalaxia_Demostracion_Resultados.pptx")

SW, SH = Inches(13.333), Inches(7.5)


def _fill(shp, color):
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()


def _txt(shp, runs, size=14, color=BODY, align=PP_ALIGN.LEFT, bold=False):
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    lines = runs.split("\n")
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold


def box(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE, line=False, radius=None):
    shp = slide.shapes.add_shape(shape, x, y, w, h)
    _fill(shp, color)
    if line:
        shp.line.color.rgb = LINE
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    if radius:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    shp.shadow.inherit = False
    return shp


def clean_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def header(slide, title, kicker=None):
    box(slide, 0, 0, SW, Inches(0.16), ORANGE)
    box(slide, Inches(0.55), Inches(0.42), Inches(4.2), Inches(0.6), NAVY)
    t = box(slide, Inches(0.55), Inches(0.42), Inches(9.9), Inches(0.6), NAVY)
    _txt(t, title.upper(), size=18, color=WHITE, bold=True)
    if kicker:
        k = box(slide, Inches(0.55), Inches(1.14), Inches(12), Inches(0.38), WHITE)
        _txt(k, kicker, size=11, color=GRAY)


def bullets(slide, items, x=Inches(0.7), y=Inches(1.7), w=Inches(11.9), h=Inches(4.6), size=14):
    tb = box(slide, x, y, w, h, WHITE)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        if isinstance(it, tuple):
            txt = it[0]
            color = it[1] if len(it) >= 2 else BODY
            color = color if color is not None else BODY
            bold = it[2] if len(it) == 3 else False
            bold = bold or False
        else:
            txt, color, bold = it, BODY, False
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = ("• " if not txt.startswith(("\u25cf", "•")) else "") + txt
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold
        p.space_after = Pt(8)
    return tb


def stat_card(slide, x, y, w, h, big, label, note=None, color=NAVY, bg=WHITE):
    c = box(slide, x, y, w, h, bg, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line=True, radius=0.06)
    tf = c.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    r0 = p0.add_run(); r0.text = big
    r0.font.name = FONT; r0.font.size = Pt(24); r0.font.bold = True; r0.font.color.rgb = color
    r0.font.color.rgb = color
    p1 = tf.add_paragraph(); r1 = p1.add_run(); r1.text = label
    r1.font.name = FONT; r1.font.size = Pt(11); r1.font.color.rgb = GRAY
    if note:
        p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = note
        r2.font.name = FONT; r2.font.size = Pt(10); r2.font.color.rgb = GRAY
    return c


def table(slide, x, y, w, rows, cols, data, col_widths=None, header_fill=NAVY, size=11):
    shp = slide.shapes.add_table(rows, cols, x, y, w, Inches(0.4 * rows + 0.15)).table
    if col_widths:
        for i, cw in enumerate(col_widths):
            shp.columns[i].width = cw
    for ri in range(rows):
        for ci in range(cols):
            cell = shp.cell(ri, ci)
            cell.text = ""
            cell.margin_left = Inches(0.05)
            cell.margin_right = Inches(0.05)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            r = p.add_run()
            r.text = str(data[ri][ci])
            r.font.name = FONT
            r.font.size = Pt(size if ri > 0 else size + 1)
            if ri == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = header_fill
                r.font.color.rgb = WHITE; r.font.bold = True
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if ri % 2 else ZEBRA
                r.font.color.rgb = BODY
    return shp


def badge(slide, x, y, w, text, color=GREEN, bg=GREENBG):
    b = box(slide, x, y, w, Inches(0.34), bg, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    _txt(b, text, size=10, color=color, align=PP_ALIGN.CENTER, bold=True)


def footer(slide, n):
    f = box(slide, Inches(0.55), Inches(7.08), Inches(12.2), Inches(0.32), WHITE)
    tf = f.text_frame
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = "webshooks.com"
    r.font.name = FONT; r.font.size = Pt(8.5); r.font.color.rgb = GRAY
    r2 = p.add_run(); r2.text = "\t\t\t\t\t\t\t\t\t\t %d" % n
    r2.font.name = FONT; r2.font.size = Pt(8.5); r2.font.color.rgb = GRAY
    ln = box(slide, Inches(0.55), Inches(7.02), Inches(12.2), Pt(0.75), LINE)


def wordmark(slide, x, y, size=16):
    tb = box(slide, x, y, Inches(3.6), Inches(0.5), WHITE)
    tf = tb.text_frame
    p = tf.paragraphs[0]
    for txt, col in [("web", BLUE), ("shooks", NAVY), (".", ORANGE)]:
        r = p.add_run(); r.text = txt
        r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = col


# ---------------------------------------------------------------- build
prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH

# ---------- 1 · Portada ----------
s = clean_slide(prs)
box(s, 0, 0, SW, SH, NAVY)
wordmark(s, Inches(0.55), Inches(0.5), 20)
box(s, Inches(0.55), Inches(2.15), Inches(4.6), Inches(2.3), NAVY)
t = box(s, Inches(0.55), Inches(2.15), Inches(12.2), Inches(1.1), NAVY)
_txt(t, "Catalaxia", size=54, color=WHITE, bold=True)
t = box(s, Inches(0.55), Inches(3.3), Inches(11), Inches(0.6), NAVY)
_txt(t, "Demostración de resultados", size=26, color=RGBColor(0xAE, 0xCB, 0xFF))
box(s, Inches(0.55), Inches(4.15), Inches(2.2), Pt(3.5), ORANGE)
t = box(s, Inches(0.55), Inches(4.5), Inches(11), Inches(1.2), NAVY)
_txt(t, "Plataforma de datos financieros trazables · SEC EDGAR · CNV · Market · TIKR\n"
        "Un sistema funcionando, medido y verificable — con resultados.", size=14,
     color=RGBColor(0xB9, 0xC6, 0xDC))
f = box(s, Inches(0.55), Inches(6.7), Inches(11), Inches(0.4), NAVY)
_txt(f, "webshooks. · Septiembre 2026 · Documento presentado a Catalaxia — interno/confidencial",
     size=11, color=GRAY)

# ---------- 2 · Resumen ejecutivo ----------
s = clean_slide(prs)
header(s, "Resumen ejecutivo", "Qué demostramos con datos medidos, no con promesas")
stat_card(s, Inches(0.55), Inches(1.75), Inches(3.9), Inches(1.9), "3 / 3", "pipelines golden run", "YPF · KO · METR — PASS_WITH_WARNINGS", color=GREEN, bg=GREENBG)
stat_card(s, Inches(4.65), Inches(1.75), Inches(3.9), Inches(1.9), "0", "errores de Catalaxia", "en homologación TIKR (152 métricas)", color=NAVY)
stat_card(s, Inches(8.75), Inches(1.75), Inches(3.9), Inches(1.9), "51 / 152", "métricas coinciden con TIKR", "33,6% exactas o derivadas · gate PASS", color=BLUE, bg=BLUEBG)
bullets(s, [
    ("El sistema corre E2E sobre las tres fuentes: SEC (YPF, KO) y CNV (METR), con reporte de golden run para cada una.", None, False),
    ("La calidad se mide contra un proveedor externo pago (TIKR): cero errores propios; las diferencias se explican una por una.", None, False),
    ("Cada número tiene una historia trazable: RAW → parsing → normalización → hecho económico → ratio → certificación.", None, False),
    ("Operación protegida: producción aislada (5432 vs 5433), 241 corridas auditadas, 34 migraciones, 378 tests en verde.", None, False),
], y=Inches(3.95))
footer(s, 2)

# ---------- 3 · Qué es Catalaxia ----------
s = clean_slide(prs)
header(s, "Qué es Catalaxia", "Propósito y diseño")
bullets(s, [
    ("Propósito: transformar evidencia financiera de múltiples fuentes en información económica de calidad, trazable y lista para decisiones.", None, False),
    ("Fuentes: SEC / EDGAR (XBRL), CNV (estados contables HTML) y Market (precios, acciones corporativas, FX).", None, False),
    ("Modelo: RAW → PARSED → NORMALIZED → Economic Facts → Financial Model → Ratios → Certificación.", None, False),
    ("Principios rectores: trazabilidad completa, reproducibilidad, separación de dato reportado/derivado, calidad antes que cantidad, transparencia y auditabilidad.", None, False),
    ("Gobernanza transversal: provenance, quality gates, certificación (PASS / PARTIAL / BLOCKED), logs y auditoría.", None, False),
], size=15)
badge(s, Inches(0.7), Inches(5.7), Inches(3.4), "ESTADO: OPERATIVO (parcial)", GREEN)
badge(s, Inches(4.3), Inches(5.7), Inches(5.2), "4 CAPÍTULOS SIGUEN EN WORKTREE (D-1)", ORANGE)
footer(s, 3)

# ---------- 4 · Los tres pilotos ----------
s = clean_slide(prs)
header(s, "Los tres pilotos", "Un piloto por fuente / régimen contable")
data = [
    ["Piloto", "Fuente", "Régimen", "Estado de la corrida"],
    ["YPF (CIK 0000904851)", "SEC / EDGAR", "IFRS + srt", "PASS_WITH_WARNINGS"],
    ["KO (CIK 0000021344)", "SEC / EDGAR", "US-GAAP puro", "PASS_WITH_WARNINGS"],
    ["METR (CUIT 30657863676)", "CNV", "EEFF HTML", "PASS_WITH_WARNINGS"],
]
tbl = table(s, Inches(0.55), Inches(1.8), Inches(12.2), 4, 4, data,
            col_widths=[Inches(3.6), Inches(2.6), Inches(2.8), Inches(3.2)], size=12)
bullets(s, [
    ("YPF: aprendizaje completo del camino SEC (7 gates).", None, False),
    ("KO: generaliza SEC a US-GAAP — falta corrida de certificación formal (implica C-3).", None, False),
    ("METR: generaliza la FUENTE (CNV); el tramo canónico del adaptador vive en el worktree (D-1).", None, False),
], y=Inches(4.1), size=13)
footer(s, 4)

# ---------- 5 · Golden runs ----------
s = clean_slide(prs)
header(s, "Golden runs", "Corridas de referencia verificadas")
data = [
    ["Caso de referencia", "Fuente", "Resultado", "Validador"],
    ["YPF", "SEC · IFRS", "PASS_WITH_WARNINGS", "golden run completo"],
    ["KO", "SEC · US-GAAP", "PASS_WITH_WARNINGS", "pendiente certificar (C-3)"],
    ["METR", "CNV", "PASS_WITH_WARNINGS", "golden run + demo"],
]
table(s, Inches(0.55), Inches(1.8), Inches(12.2), 4, 4, data,
      col_widths=[Inches(2.4), Inches(2.9), Inches(3.6), Inches(3.3)], size=12)
bullets(s, [
    ("Definición: corrida completa del pipeline (fuente → publicación) con resultado verificado y auditable.", None, False),
    ("Cada golden run deja un reporte: conteos, gates, provenance y advertencias (GOLDEN_RUNS.md).", None, False),
    ("Uso operativo: la regla de operación es comparar toda corrida nueva contra su golden run.", None, False),
], y=Inches(4.1), size=13)
footer(s, 5)

# ---------- 6 · Homologación TIKR ----------
s = clean_slide(prs)
header(s, "Homologación TIKR · METR FY2025", "Nuestros datos vs. un proveedor externo pago (152 métricas)")
data = [
    ["Resultado", "Cantidad", "% del universo"],
    ["Coinciden exactas o por derivación (MATCH_EXACT / DERIVED / ROUNDING)", "51", "33,6%"],
    ["Explicadas por definición o perimetría (DEFINITION / INPUT DIFFERENCE)", "28", "18,4%"],
    ["Sin insumo en Catalaxia (CATALAXIA_MISSING_INPUT)", "66", "43,4%"],
    ["Errores propios de formato/proceso (CATALAXIA_ERROR)", "0", "0%"],
]
table(s, Inches(0.55), Inches(1.8), Inches(12.2), 5, 3, data,
      col_widths=[Inches(7.9), Inches(2.0), Inches(2.3)], size=11)
bullets(s, [
    ("Gate del proceso de homologación: PASS_WITH_WARNINGS.", GREEN, True),
    ("Validación del perímetro: el INDIVIDUAL de METR = segmento \u201cMetroGAS Distribution\u201d.", None, False),
    ("Ejemplos: NetIncome −1.827 exacto; Total Debt difiere (cuenta + provisión, factor IAS 29 1.3155); Operating Income reclasifica 7.728.", None, False),
    ("Qué significa: falta insumo, no calidad. Las 66 métricas sin insumo son inputs no cargados aún — mejora por datos, no por corrección.", None, False),
], y=Inches(4.15), size=12)
footer(s, 6)

# ---------- 7 · Trazabilidad de un número ----------
s = clean_slide(prs)
header(s, "Trazabilidad de un número", "Cada número tiene una historia — y podemos explicarla")
steps = ["RAW", "PARSED", "NORMALIZED", "ECON. FACTS", "FIN. MODEL", "RATIOS", "CERTIFY"]
x = Inches(0.55)
w = Inches(1.55)
gap = Inches(0.24)
for i, st in enumerate(steps):
    color = NAVY if i == len(steps) - 1 else BLUE
    b = box(s, x, Inches(2.0), w, Inches(0.85), color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    _txt(b, st, size=12 if len(st) <= 8 else 10, color=WHITE, align=PP_ALIGN.CENTER, bold=True)
    if i < len(steps) - 1:
        ar = box(s, x + w, Inches(2.28), gap, Inches(0.3), WHITE)
        _txt(ar, "→", size=16, color=ORANGE, align=PP_ALIGN.CENTER, bold=True)
    x = x + w + gap
bullets(s, [
    ("P/E de KO (ejemplo): Price (Market) ÷ EPS — EPS = Net Income (XBRL, 10-K/SEC) ÷ Shares.", None, False),
    ("El rastro queda en provenance: origen, transformación, reglas aplicadas, hash por etapa.", None, False),
    ("Certificación: estado PASS con evidencia; la corrida puede reproducirse y compararse contra el golden run.", None, False),
], y=Inches(3.4), size=14)
footer(s, 7)

# ---------- 8 · Salud del sistema ----------
s = clean_slide(prs)
header(s, "Salud del sistema", "Datos de operación y pruebas, tomados del estado real")
stat_card(s, Inches(0.55), Inches(1.75), Inches(3.9), Inches(1.8), "34", "migraciones aplicadas", "00→033 en repo · 034–036 en worktree D-1", color=NAVY)
stat_card(s, Inches(4.65), Inches(1.75), Inches(3.9), Inches(1.8), "378", "tests en verde", "3 fallas pre-existentes (F-038) · 1 skip", color=BLUE, bg=BLUEBG)
stat_card(s, Inches(8.75), Inches(1.75), Inches(3.9), Inches(1.8), "241", "corridas auditadas", "OK 61 · ABORTED 132 · BLOCKED 48", color=GREEN, bg=GREENBG)
stat_card(s, Inches(0.55), Inches(3.8), Inches(3.9), Inches(1.8), "4,8M", "precios de mercado", "584 instrumentos · 8.322 filas de calidad", color=NAVY)
stat_card(s, Inches(4.65), Inches(3.8), Inches(3.9), Inches(1.8), "51.917", "acciones corporativas", "601 filas de fetch auditadas", color=BLUE, bg=BLUEBG)
stat_card(s, Inches(8.75), Inches(3.8), Inches(3.9), Inches(1.8), "5432", "producción aislada", "guard EXT-010: bloquea escritura sin permiso", color=GREEN, bg=GREENBG)
footer(s, 8)

# ---------- 9 · Lo que falta y plan ----------
s = clean_slide(prs)
header(s, "Próximos pasos", "Transparentes y priorizados — para llegar a cobertura completa")
data = [
    ["Prioridad", "Trabajo", "Qué desbloquea"],
    ["P0", "Idempotencia de S00/S02 + is_custom", "Corridas estables sin dobles conteos"],
    ["P1", "Tramo canónico de CNV (adaptador)", "METR completo y certificable (D-1)"],
    ["P1", "Homologación TIKR → cobertura de inputs", "Subir coincidencia 33,6% → 80%+"],
    ["P2", "Certificación formal de KO (C-3) y Market E2E", "Completar los tres pilotos"],
]
table(s, Inches(0.55), Inches(1.75), Inches(12.2), 5, 3, data,
      col_widths=[Inches(1.6), Inches(6.9), Inches(3.7)], size=11)
bullets(s, [
    ("Decisiones abiertas a validar con el cliente: D-1 (repo vs worktree), D-2, D-3, D-4.", None, False),
    ("El manual operativo v2.0 documenta todo: 21 partes, 40 figuras, plantillas de diagramas.", None, False),
], y=Inches(4.1), size=12)
footer(s, 9)

# ---------- 10 · Cierre ----------
s = clean_slide(prs)
box(s, 0, 0, SW, SH, NAVY)
wordmark(s, Inches(0.55), Inches(0.5), 20)
t = box(s, Inches(0.55), Inches(2.0), Inches(12.2), Inches(1.0), NAVY)
_txt(t, "El sistema funciona", size=40, color=WHITE, bold=True)
box(s, Inches(0.55), Inches(3.0), Inches(2.2), Pt(3.5), ORANGE)
bullets(s, [
    ("Tres pilotos E2E sobre las dos fuentes reales (SEC y CNV), con golden runs y reportes.", WHITE),
    ("Calidad contrastada contra TIKR con cero errores propios.", WHITE),
    ("Trazabilidad de cada número desde el documento original hasta el ratio publicado.", WHITE),
], x=Inches(0.55), y=Inches(3.3), w=Inches(12), h=Inches(2.0), size=16)
t = box(s, Inches(0.55), Inches(5.6), Inches(12), Inches(0.8), NAVY)
_txt(t, "Siguiente paso propuesto: aprobar prioridades P0/P1 y habilitar el tramo canónico de CNV.",
     size=14, color=RGBColor(0xAE, 0xCB, 0xFF))
f = box(s, Inches(0.55), Inches(6.8), Inches(11), Inches(0.4), NAVY)
_txt(f, "webshooks. · Septiembre 2026 · Para Catalaxia — interno/confidencial", size=11, color=GRAY)

prs.save(OUT)
print("OK ->", OUT, f"({os.path.getsize(OUT)//1024} KB)", "·", len(prs.slides.__iter__.__self__._sldIdLst), "slides")