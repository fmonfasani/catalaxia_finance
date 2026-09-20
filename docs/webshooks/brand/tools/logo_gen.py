# -*- coding: utf-8 -*-
"""Generador del kit de logos webshooks (reproducible).
Produce el wordmark y el mark en variantes y formatos: PNG (transparente),
JPEG (sobre fondo), ICO (favicon) y SVG (vectorial).

    python logo_gen.py           # -> ../logo/*.png|svg|jpg|ico
"""
import os, json
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.path.dirname(HERE)
OUT = os.path.join(BRAND, "logo")
os.makedirs(OUT, exist_ok=True)

theme = json.load(open(os.path.join(BRAND, "theme_webshooks.json"), encoding="utf-8"))
C = theme["colors"]
NAVY = C["navy"]; BLUE = C["blue"]; ORANGE = C["orange"]; WHITE = "#FFFFFF"

def hx(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def font(size, bold=True):
    for name in (("calibrib.ttf" if bold else "calibri.ttf"), "arialbd.ttf", "arial.ttf"):
        for base in ("C:/Windows/Fonts/", ""):
            p = base + name
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ---------------- WORDMARK ----------------
def wordmark(parts, size=170, pad=24):
    """parts = [(text, hexcolor), ...]. Devuelve imagen RGBA transparente."""
    f = font(size, bold=True)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    widths = [tmp.textlength(t, font=f) for t, _ in parts]
    asc, desc = f.getmetrics()
    W = int(sum(widths) + pad * 2)
    H = int(asc + desc + pad)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad; baseline = pad // 2 + asc
    for (t, col), w in zip(parts, widths):
        d.text((x, baseline), t, font=f, fill=hx(col), anchor="ls")
        x += w
    return img

WM = [("web", BLUE), ("shooks", NAVY), (".", ORANGE)]

def wm_mono(color):
    return wordmark([(t, color) for t, _ in WM])

# ---------------- MARK (isotipo) ----------------
def mark(square_fill=NAVY, w_color=WHITE, dot_color=ORANGE, S=512):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(S * 0.06); r = int(S * 0.20)
    d.rounded_rectangle([m, m, S - m, S - m], radius=r, fill=hx(square_fill))
    f = font(int(S * 0.62), bold=True)
    d.text((S * 0.47, S * 0.55), "w", font=f, fill=hx(w_color), anchor="mm")
    dr = int(S * 0.075)
    cx, cy = int(S * 0.72), int(S * 0.66)
    d.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=hx(dot_color))
    return img

# ---------------- LOCKUP horizontal ----------------
def lockup(wm_img, mark_img, gap=40, bg=None):
    mh = wm_img.height
    m = mark_img.resize((mh, mh), Image.LANCZOS)
    W = m.width + gap + wm_img.width
    H = mh
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0) if bg is None else hx(bg) + (255,))
    canvas.alpha_composite(m, (0, 0))
    canvas.alpha_composite(wm_img, (m.width + gap, (H - wm_img.height) // 2))
    return canvas

def on_bg(img, bg, padx=60, pady=48):
    W = img.width + padx * 2; H = img.height + pady * 2
    canvas = Image.new("RGBA", (W, H), hx(bg) + (255,))
    canvas.alpha_composite(img, (padx, pady))
    return canvas

def save_png(img, name):
    img.save(os.path.join(OUT, name)); print("png:", name)

def save_jpg(img, name, bg="#FFFFFF"):
    base = Image.new("RGB", img.size, hx(bg))
    base.paste(img, (0, 0), img)
    base.save(os.path.join(OUT, name), quality=92); print("jpg:", name)

# ---------------- SVG (vectorial) ----------------
def svg_wordmark(path, colors=None, size=170):
    cols = colors or [p[1] for p in WM]
    f = font(size); tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    widths = [tmp.textlength(t, font=f) for t, _ in WM]
    W = int(sum(widths) + 40); H = int(size * 1.3)
    tspans = "".join(f'<tspan fill="{c}">{t}</tspan>' for (t, _), c in zip(WM, cols))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f'<text x="20" y="{int(H*0.72)}" font-family="Calibri, Segoe UI, sans-serif" '
           f'font-weight="700" font-size="{size}">{tspans}</text></svg>')
    open(os.path.join(OUT, path), "w", encoding="utf-8").write(svg); print("svg:", path)

# ==================================================================== main
if __name__ == "__main__":
    wm_color = wordmark(WM)
    wm_white = wm_mono(WHITE)
    wm_navy  = wm_mono(NAVY)
    mk_color = mark()                                   # cuadrado navy (isotipo por defecto)
    mk_blue  = mark(square_fill=BLUE, w_color=WHITE, dot_color=ORANGE)  # para fondo oscuro

    # PNG transparentes
    save_png(wm_color, "webshooks-wordmark-color.png")
    save_png(wm_white, "webshooks-wordmark-white.png")
    save_png(wm_navy,  "webshooks-wordmark-navy.png")
    save_png(mk_color, "webshooks-mark-color.png")

    # Lockups
    save_png(lockup(wm_color, mk_color), "webshooks-logo-horizontal-color.png")
    save_png(on_bg(lockup(wm_white, mk_blue), NAVY), "webshooks-logo-horizontal-onnavy.png")

    # JPEG (sobre blanco)
    save_jpg(lockup(wm_color, mk_color), "webshooks-logo-horizontal-onwhite.jpg")

    # App icon (mark sobre navy, cuadrado)
    save_png(on_bg(mk_color, NAVY, 60, 60).resize((512, 512), Image.LANCZOS),
             "webshooks-appicon-512.png")

    # Favicon multi-size
    mk_color.save(os.path.join(OUT, "webshooks-favicon.ico"),
                  sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]); print("ico: webshooks-favicon.ico")

    # SVG vectoriales
    svg_wordmark("webshooks-wordmark-color.svg")
    svg_wordmark("webshooks-wordmark-white.svg", colors=[WHITE, WHITE, ORANGE])

    print("\nOK — logos en", OUT)
