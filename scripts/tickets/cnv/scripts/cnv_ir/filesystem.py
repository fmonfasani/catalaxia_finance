"""
filesystem.py

Utilidades para organizar y almacenar los EEFF descargados.

Estructura:

eeff/
    ALUA/
        3523703.html
    LEDE/
        1948821.html
"""

from pathlib import Path
from typing import Union


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EEFF_DIR = PROJECT_ROOT / "eeff"


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Crea un directorio si no existe.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_ticker_directory(ticker: str) -> Path:
    """
    Devuelve la carpeta correspondiente al ticker.
    """
    ticker = ticker.strip().upper()

    folder = EEFF_DIR / ticker

    ensure_directory(folder)

    return folder


def build_html_path(
    ticker: str,
    presentation_id: Union[int, str]
) -> Path:
    """
    Devuelve la ruta final del HTML.

    Ejemplo:

    eeff/ALUA/3523703.html
    """

    folder = get_ticker_directory(ticker)

    filename = f"{presentation_id}.html"

    return folder / filename


def exists(
    ticker: str,
    presentation_id: Union[int, str]
) -> bool:
    """
    Indica si el HTML ya existe.
    """
    return build_html_path(
        ticker,
        presentation_id
    ).exists()


def save_html(
    ticker: str,
    presentation_id: Union[int, str],
    html: str,
    encoding: str = "utf-8"
) -> Path:
    """
    Guarda el HTML y devuelve la ruta.
    """

    path = build_html_path(
        ticker,
        presentation_id
    )

    path.write_text(
        html,
        encoding=encoding
    )

    return path


def html_size(
    ticker: str,
    presentation_id: Union[int, str]
) -> int:
    """
    Devuelve el tamaño del HTML en bytes.
    """

    path = build_html_path(
        ticker,
        presentation_id
    )

    if not path.exists():
        return 0

    return path.stat().st_size


def iter_html_files():
    """
    Itera todos los HTML descargados.

    Yields
    ------
    Path
    """

    if not EEFF_DIR.exists():
        return

    yield from EEFF_DIR.rglob("*.html")


def count_downloaded_html() -> int:
    """
    Cuenta los HTML descargados.
    """

    return sum(1 for _ in iter_html_files())


def total_downloaded_bytes() -> int:
    """
    Tamaño total del repositorio.
    """

    return sum(
        p.stat().st_size
        for p in iter_html_files()
    )


if __name__ == "__main__":

    print("Repositorio:", EEFF_DIR)

    print(
        "HTML descargados:",
        count_downloaded_html()
    )

    print(
        "Tamaño:",
        total_downloaded_bytes(),
        "bytes"
    )