# -*- coding: utf-8 -*-
"""Componentes visuales webshooks (branded): timeline, pipeline y diagrama de flujo.
Se alimentan con datos simples y producen PNG (300dpi) + SVG para insertar en
documentos Word/PPT/PDF/HTML. Usan la paleta de theme_webshooks.json.

Uso como librería:
    from components import timeline, pipeline, flow
    timeline([{"label":"2026","sub":"kickoff"}, ...], "Título", "Subtítulo", "mi-timeline")

Demo:
    python components.py        # genera ejemplos en components/examples/
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Circle
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.dirname(HERE)
theme = json.load(open(os.path.join(BRAND, "theme_webshooks.json"), encoding="utf-8"))
C = theme["colors"]
NAVY, BLUE, ORANGE, GREEN = C["navy"], C["blue"], C["orange"], C["green"]
PURPLE = "#A64D79"; BODY, GRAY, GRID = C["body"], C["gray"], C["border"]
LB, PANEL = C["tint_blue"], C["surface"]
PALETTE = [BLUE, GREEN, ORANGE, PURPLE, C["blue_dark"]]

for fam in ("Calibri", "Segoe UI", "DejaVu Sans"):
    try:
        font_manager.findfont(fam, fallback_to_default=False); plt.rcParams["font.family"] = fam; break
    except Exception:
        continue
plt.rcParams.update({"savefig.dpi": 300, "figure.dpi": 120})

OUT = os.path.join(HERE, "examples")


def _title_block(fig, title, subtitle, accent):
    if not title:
        return
    fig.text(0.045, 0.90, title, fontsize=15.5, color=NAVY, fontweight="bold")
    fig.add_artist(plt.Line2D([0.048, 0.13], [0.855, 0.855], color=accent, lw=2.6,
                              solid_capstyle="round", transform=fig.transFigure))
    if subtitle:
        fig.text(0.045, 0.815, subtitle, fontsize=10.5, color=GRAY)


def _save(fig, name, out=None):
    out = out or OUT
    os.makedirs(out, exist_ok=True)
    fig.savefig(os.path.join(out, name + ".png"), facecolor="white", bbox_inches=None)
    fig.savefig(os.path.join(out, name + ".svg"), facecolor="white", bbox_inches=None)
    plt.close(fig)
    print("componente:", name)


# ============================================================ TIMELINE
def timeline(events, title="", subtitle="", name="timeline", out=None):
    """events: lista de {'label':..., 'sub':..., 'color':opcional}."""
    fig = plt.figure(figsize=(9.4, 4.4), facecolor="white")
    ax = fig.add_axes([0.03, 0.14, 0.94, 0.58]); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(-1.25, 1.25)
    ax.plot([0.3, 9.7], [0, 0], color=GRID, lw=2.6, solid_capstyle="round", zorder=1)
    xs = np.linspace(0.7, 9.3, len(events))
    for i, (ev, x) in enumerate(zip(events, xs)):
        col = ev.get("color", PALETTE[i % len(PALETTE)])
        side = 1 if i % 2 == 0 else -1
        ax.plot([x, x], [0, 0.5 * side], color=col, lw=1.8, zorder=2)
        ax.scatter([x], [0], s=70, color=col, edgecolors="white", linewidths=1.8, zorder=4)
        txt = f"{ev.get('label','')}\n{ev.get('sub','')}".strip()
        ax.text(x, 0.6 * side, txt, ha="center", va="bottom" if side > 0 else "top",
                color=NAVY, fontsize=8.4, fontweight="bold", linespacing=1.35)
    _title_block(fig, title, subtitle, BLUE)
    _save(fig, name, out)


# ============================================================ PIPELINE
def pipeline(stages, title="", subtitle="", name="pipeline", out=None):
    """stages: lista de {'title':..., 'desc':..., 'color':opcional}."""
    n = len(stages)
    fig = plt.figure(figsize=(2.5 * n + 0.5, 4.2), facecolor="white")
    ax = fig.add_axes([0.02, 0.05, 0.96, 0.66]); ax.axis("off")
    ax.set_xlim(0, n); ax.set_ylim(0, 3)
    w = 0.82; gap = (1 - w)
    for i, st in enumerate(stages):
        col = st.get("color", PALETTE[i % len(PALETTE)])
        x = i + gap / 2
        box = FancyBboxPatch((x, 0.2), w, 2.4, boxstyle="round,pad=0.02,rounding_size=0.06",
                             fc=PANEL, ec=GRID, lw=1.0); ax.add_patch(box)
        head = FancyBboxPatch((x, 2.0), w, 0.6, boxstyle="round,pad=0.02,rounding_size=0.06",
                              fc=col, ec="none"); ax.add_patch(head)
        ax.add_patch(plt.Rectangle((x, 2.0), w, 0.32, color=col))
        ax.text(x + w / 2, 2.28, st.get("title", ""), ha="center", va="center",
                color="white", fontsize=10.5, fontweight="bold")
        ax.text(x + w / 2, 1.15, st.get("desc", ""), ha="center", va="center",
                color=BODY, fontsize=8.8, wrap=True)
        if i < n - 1:
            ax.annotate("", xy=(i + 1 + gap / 2 - 0.02, 1.4), xytext=(x + w + 0.02, 1.4),
                        arrowprops=dict(arrowstyle="-|>", color=GRAY, lw=2))
    _title_block(fig, title, subtitle, BLUE)
    _save(fig, name, out)


# ============================================================ FLOW (vertical)
def flow(steps, title="", subtitle="", name="flow", out=None):
    """steps: lista de {'text':..., 'type': 'start'|'process'|'decision'|'end'}."""
    n = len(steps)
    fig = plt.figure(figsize=(6.4, 1.35 * n + 1.0), facecolor="white")
    ax = fig.add_axes([0.05, 0.04, 0.9, 0.80]); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, n * 1.35 + 0.4)
    cx = 5.0
    y = n * 1.35 - 0.35
    kind_col = {"start": GREEN, "process": BLUE, "decision": ORANGE, "end": NAVY}
    centers = []
    for i, s in enumerate(steps):
        kind = s.get("type", "process"); col = kind_col.get(kind, BLUE)
        if kind == "decision":
            d = Polygon([(cx, y + 0.55), (cx + 2.0, y), (cx, y - 0.55), (cx - 2.0, y)],
                        closed=True, fc=PANEL, ec=col, lw=2.0); ax.add_patch(d)
            ax.text(cx, y, s.get("text", ""), ha="center", va="center", color=NAVY,
                    fontsize=9, fontweight="bold")
        else:
            style = "round,pad=0.02,rounding_size=0.5" if kind in ("start", "end") else "round,pad=0.02,rounding_size=0.14"
            box = FancyBboxPatch((cx - 2.2, y - 0.42), 4.4, 0.84, boxstyle=style,
                                 fc=(col if kind in ("start", "end") else PANEL),
                                 ec=col, lw=2.0); ax.add_patch(box)
            ax.text(cx, y, s.get("text", ""), ha="center", va="center",
                    color=("white" if kind in ("start", "end") else NAVY),
                    fontsize=9.5, fontweight="bold")
        centers.append(y)
        y -= 1.35
    for i in range(n - 1):
        ax.annotate("", xy=(cx, centers[i + 1] + 0.45), xytext=(cx, centers[i] - 0.45),
                    arrowprops=dict(arrowstyle="-|>", color=GRAY, lw=2))
    _title_block(fig, title, subtitle, BLUE)
    _save(fig, name, out)


# ============================================================ DEMO
if __name__ == "__main__":
    timeline([
        {"label": "Fase 0", "sub": "data lista"},
        {"label": "Sem 1", "sub": "infra + API"},
        {"label": "Sem 2", "sub": "front real"},
        {"label": "Sem 3", "sub": "funcionalidad"},
        {"label": "Sem 4", "sub": "QA + entrega"},
    ], "Cronograma del proyecto", "Mié 15/07 → Vie 14/08", "ejemplo-timeline")

    pipeline([
        {"title": "1 · Extracción", "desc": "SEC · CNV · IAMC · Comafi · JPM → raw cache"},
        {"title": "2 · Ratios", "desc": "~16 ratios fundamentales"},
        {"title": "3 · Ensamble AR", "desc": "doble precio + CEDEAR/ADR"},
        {"title": "4 · Modelo 2 niveles", "desc": "empresa + 733 instrumentos"},
        {"title": "5 · Export", "desc": "CSV + JSON + SQL con source_url"},
    ], "Arquitectura del pipeline", "Cada bloque se re-ejecuta solo", "ejemplo-pipeline")

    flow([
        {"text": "Aprobación", "type": "start"},
        {"text": "Primer pago", "type": "process"},
        {"text": "Kickoff + accesos", "type": "process"},
        {"text": "¿VPS lista?", "type": "decision"},
        {"text": "Desarrollo (4 semanas)", "type": "process"},
        {"text": "QA + entrega", "type": "end"},
    ], "Flujo de arranque", "", "ejemplo-flow")

    print("\nOK — ejemplos en", OUT)
