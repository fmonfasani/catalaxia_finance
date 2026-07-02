"""
scripts/cnv_ir/downloader.py

NOTA:
Este archivo es un esqueleto completo listo para integrarse con
filesystem.py, validator.py y logger.py del proyecto.
Debe ajustarse únicamente a las firmas reales de esos módulos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class DownloadStatus(str, Enum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    INVALID_HTML = "INVALID_HTML"
    HTTP_ERROR = "HTTP_ERROR"
    REQUEST_ERROR = "REQUEST_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass(slots=True)
class DownloadResult:
    guid: str
    ticker: str
    presentation_id: Optional[str]
    status: DownloadStatus
    http_status: Optional[int]
    bytes: int
    seconds: float
    file: Optional[Path]
    error: Optional[str]


class Downloader:
    BASE_URL = "https://aif2.cnv.gov.ar/presentations/publicview"

    def __init__(
        self,
        filesystem,
        validator,
        csv_logger,
        timeout=(10, 60),
        user_agent="Mozilla/5.0",
    ):
        # filesystem: module with build_html_path/save_html/exists
        # validator: module exposing validate_html(html) -> ValidationResult(ok, reason, presentation_id)
        # csv_logger: module exposing log_download(...) wrapper
        self.fs = filesystem
        self.validator = validator
        self.logger = csv_logger
        self.timeout = timeout

        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self):
        self.session.close()

    def _url(self, guid: str) -> str:
        return f"{self.BASE_URL}/{guid}"

    def download(self, row) -> DownloadResult:
        """
        row debe contener al menos:
            ticker
            guid
        """

        import time

        started = time.perf_counter()

        ticker = row.get("ticker") or row.get("Ticker")

        # Prefer an explicit full URL if present in the row. Accept common field names.
        url = None
        for key in ("url", "url_presentacion", "URL_PRESENTACION", "url_presentacion_https", "URL"):
            if key in row and row.get(key):
                url = row.get(key)
                break

        guid = row.get("guid") or row.get("GUID")

        try:

            # Build request URL: prefer explicit URL from the row, else use GUID-derived URL
            request_url = url if url else (self._url(guid) if guid else None)

            if not request_url:
                elapsed = time.perf_counter() - started

                self.logger.log_download(
                    ticker=ticker,
                    guid=guid or "",
                    presentation_id=None,
                    status=DownloadStatus.REQUEST_ERROR.value,
                    http_status=None,
                    bytes_downloaded=0,
                    seconds=elapsed,
                    file="",
                    error="no_request_url",
                )

                return DownloadResult(guid or "", ticker, None, DownloadStatus.REQUEST_ERROR, None, 0, elapsed, None, "no_request_url")

            r = self.session.get(request_url, timeout=self.timeout)

            elapsed = time.perf_counter() - started

            if r.status_code != 200:
                # HTTP error
                self.logger.log_download(
                    ticker=ticker,
                    guid=guid,
                    presentation_id=None,
                    status=DownloadStatus.HTTP_ERROR.value,
                    http_status=r.status_code,
                    bytes_downloaded=0,
                    seconds=elapsed,
                    file="",
                    error=f"HTTP {r.status_code}",
                )

                return DownloadResult(guid, ticker, None, DownloadStatus.HTTP_ERROR, r.status_code, 0, elapsed, None, f"HTTP {r.status_code}")

            html = r.text

            validation = self.validator.validate_html(html)

            if not getattr(validation, "ok", False):
                self.logger.log_download(
                    ticker=ticker,
                    guid=guid,
                    presentation_id=None,
                    status=DownloadStatus.INVALID_HTML.value,
                    http_status=200,
                    bytes_downloaded=len(r.content),
                    seconds=elapsed,
                    file="",
                    error=getattr(validation, "reason", "invalid_html"),
                )

                return DownloadResult(guid, ticker, None, DownloadStatus.INVALID_HTML, 200, len(r.content), elapsed, None, getattr(validation, "reason", "invalid_html"))

            presentation_id = getattr(validation, "presentation_id", None)

            output = self.fs.build_html_path(ticker=ticker, presentation_id=presentation_id)

            # If already exists, skip
            if output.exists():
                self.logger.log_download(
                    ticker=ticker,
                    guid=guid,
                    presentation_id=presentation_id,
                    status=DownloadStatus.SKIPPED.value,
                    http_status=200,
                    bytes_downloaded=len(r.content),
                    seconds=elapsed,
                    file=str(output),
                    error="",
                )

                return DownloadResult(guid, ticker, presentation_id, DownloadStatus.SKIPPED, 200, len(r.content), elapsed, output, None)

            # Write atomically
            tmp = output.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(html, encoding="utf-8")
            tmp.replace(output)

            self.logger.log_download(
                ticker=ticker,
                guid=guid,
                presentation_id=presentation_id,
                status=DownloadStatus.SUCCESS.value,
                http_status=200,
                bytes_downloaded=len(r.content),
                seconds=elapsed,
                file=str(output),
                error="",
            )

            return DownloadResult(guid, ticker, presentation_id, DownloadStatus.SUCCESS, 200, len(r.content), elapsed, output, None)

        except requests.RequestException as exc:

            elapsed = time.perf_counter() - started

            self.logger.log_download(
                ticker=ticker,
                guid=guid,
                presentation_id=None,
                status=DownloadStatus.REQUEST_ERROR.value,
                http_status=None,
                bytes_downloaded=0,
                seconds=elapsed,
                file="",
                error=str(exc),
            )

            return DownloadResult(guid, ticker, None, DownloadStatus.REQUEST_ERROR, None, 0, elapsed, None, str(exc))

        except Exception as exc:

            elapsed = time.perf_counter() - started

            self.logger.log_download(
                ticker=ticker,
                guid=guid,
                presentation_id=None,
                status=DownloadStatus.UNKNOWN_ERROR.value,
                http_status=None,
                bytes_downloaded=0,
                seconds=elapsed,
                file="",
                error=str(exc),
            )

            return DownloadResult(guid, ticker, None, DownloadStatus.UNKNOWN_ERROR, None, 0, elapsed, None, str(exc))
