"""
04_reverse_engineering_cnv.py

Ingeniería inversa del HTML de una empresa de la CNV.

Analiza:

- URLs
- GUID
- Scripts JS
- AJAX
- Fetch
- XMLHttpRequest
- Controllers MVC
- Endpoints
- Servicios .svc .asmx .ashx
- Variables JavaScript
- JSON embebidos

Entrada:

cnv/
    datos/
        ledesma.html

Salida:

debug/
    reverse_engineering.txt
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

DATOS = ROOT / "datos"
DEBUG = ROOT / "debug"

HTML = DATOS / "ledesma.html"

OUT = DEBUG / "reverse_engineering.txt"

DEBUG.mkdir(exist_ok=True)

html = HTML.read_text(
    encoding="utf8",
    errors="ignore",
)


def titulo(t):

    print("\n")
    print("=" * 90)
    print(t)
    print("=" * 90)

    with open(
        OUT,
        "a",
        encoding="utf8",
    ) as f:

        f.write("\n")
        f.write("=" * 90)
        f.write("\n")
        f.write(t)
        f.write("\n")
        f.write("=" * 90)
        f.write("\n")


def guardar(lineas):

    with open(
        OUT,
        "a",
        encoding="utf8",
    ) as f:

        for l in sorted(set(lineas)):

            print(l)

            f.write(l + "\n")


OUT.write_text("", encoding="utf8")

print("=" * 90)
print("CNV REVERSE ENGINEERING")
print("=" * 90)

# ===========================================================
titulo("GUID")

guardar(
    re.findall(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        html,
        re.I,
    )
)

# ===========================================================
titulo("URLS")

guardar(
    re.findall(
        r"https?://[^\"]+",
        html,
        re.I,
    )
)

# ===========================================================
titulo("MVC ROUTES")

guardar(
    re.findall(
        r"/[A-Za-z0-9]+/[A-Za-z0-9_\-]+",
        html,
    )
)

# ===========================================================
titulo("AJAX")

guardar(
    re.findall(
        r"\$\.ajax\((.*?)\)",
        html,
        re.S,
    )
)

# ===========================================================
titulo("FETCH")

guardar(
    re.findall(
        r"fetch\((.*?)\)",
        html,
        re.S,
    )
)

# ===========================================================
titulo("XMLHttpRequest")

guardar(
    re.findall(
        r"XMLHttpRequest",
        html,
    )
)

# ===========================================================
titulo("SERVICIOS")

guardar(
    re.findall(
        r"[A-Za-z0-9/_\-.]+\.(?:svc|asmx|ashx)",
        html,
        re.I,
    )
)

# ===========================================================
titulo("JSON")

guardar(
    re.findall(
        r"[A-Za-z0-9/_\-.]+\.json",
        html,
        re.I,
    )
)

# ===========================================================
titulo("JAVASCRIPT")

guardar(
    re.findall(
        r"<script[^>]*src=\"([^\"]+)\"",
        html,
        re.I,
    )
)

# ===========================================================
titulo("CSS")

guardar(
    re.findall(
        r"<link[^>]*href=\"([^\"]+)\"",
        html,
        re.I,
    )
)

# ===========================================================
titulo("FORM ACTION")

guardar(
    re.findall(
        r'action="([^"]+)"',
        html,
        re.I,
    )
)

# ===========================================================
titulo("HREF")

guardar(
    re.findall(
        r'href="([^"]+)"',
        html,
        re.I,
    )
)

# ===========================================================
titulo("SRC")

guardar(
    re.findall(
        r'src="([^"]+)"',
        html,
        re.I,
    )
)

# ===========================================================
titulo("WINDOW")

guardar(
    re.findall(
        r"window\.[A-Za-z0-9_\.]+",
        html,
    )
)

# ===========================================================
titulo("VARIABLES JS")

guardar(
    re.findall(
        r"var\s+([A-Za-z0-9_]+)",
        html,
    )
)

# ===========================================================
titulo("HOST")

guardar(
    re.findall(
        r"host\s*=.*?;",
        html,
        re.S,
    )
)

# ===========================================================
titulo("PRESENTATION")

guardar(
    re.findall(
        r"presentation[A-Za-z0-9_]*",
        html,
    )
)

# ===========================================================
titulo("PUBLICVIEW")

guardar(
    re.findall(
        r"publicview",
        html,
        re.I,
    )
)

# ===========================================================
titulo("AIF2")

guardar(
    re.findall(
        r"aif2",
        html,
        re.I,
    )
)

# ===========================================================
titulo("CONTROLLERS")

controllers = sorted(set(

    re.findall(
        r"/([A-Za-z]+)/[A-Za-z0-9_\-]+",
        html,
    )

))

guardar(controllers)

# ===========================================================
titulo("FUNCIONES")

guardar(

    re.findall(

        r"function\s+[A-Za-z0-9_]+",

        html,

    )

)

print("\n")
print("=" * 90)
print("FINALIZADO")
print("=" * 90)

print(OUT)