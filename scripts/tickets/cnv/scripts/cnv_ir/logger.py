"""
logger.py

Registro de todas las descargas realizadas por el downloader.

Genera:

logs/download_log.csv

Thread-safe.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "download_log.csv"


FIELDNAMES = [
    "timestamp",
    "ticker",
    "guid",
    "presentationId",
    "status",
    "http_status",
    "bytes",
    "seconds",
    "file",
    "error",
]


class DownloadLogger:
    """
    Logger thread-safe para registrar las descargas.
    """

    def __init__(self, log_file: Path = LOG_FILE):
        self.log_file = Path(log_file)
        self._lock = Lock()

        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.log_file.exists():
            with self.log_file.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=FIELDNAMES,
                )
                writer.writeheader()

    def log(
        self,
        *,
        ticker: str,
        guid: str,
        presentation_id: Optional[str],
        status: str,
        http_status: Optional[int] = None,
        bytes_downloaded: int = 0,
        seconds: float = 0.0,
        file: str = "",
        error: str = "",
    ) -> None:
        """
        Agrega una fila al CSV.
        """

        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "ticker": ticker,
            "guid": guid,
            "presentationId": presentation_id or "",
            "status": status,
            "http_status": http_status if http_status is not None else "",
            "bytes": bytes_downloaded,
            "seconds": round(seconds, 3),
            "file": file,
            "error": error,
        }

        with self._lock:
            with self.log_file.open(
                "a",
                newline="",
                encoding="utf-8",
            ) as f:

                writer = csv.DictWriter(
                    f,
                    fieldnames=FIELDNAMES,
                )

                writer.writerow(row)


LOGGER = DownloadLogger()


def log_download(
    *,
    ticker: str,
    guid: str,
    presentation_id: Optional[str],
    status: str,
    http_status: Optional[int] = None,
    bytes_downloaded: int = 0,
    seconds: float = 0.0,
    file: str = "",
    error: str = "",
):
    """
    Wrapper para no instanciar el logger en otros módulos.
    """

    LOGGER.log(
        ticker=ticker,
        guid=guid,
        presentation_id=presentation_id,
        status=status,
        http_status=http_status,
        bytes_downloaded=bytes_downloaded,
        seconds=seconds,
        file=file,
        error=error,
    )


if __name__ == "__main__":

    log_download(
        ticker="TEST",
        guid="1234",
        presentation_id="999999",
        status="SUCCESS",
        http_status=200,
        bytes_downloaded=2458123,
        seconds=0.84,
        file="eeff/TEST/999999.html",
    )

    print(LOG_FILE)