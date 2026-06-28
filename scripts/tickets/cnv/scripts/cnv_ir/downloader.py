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

        ticker = row["ticker"]
        guid = row["guid"]

        try:

            r = self.session.get(
                self._url(guid),
                timeout=self.timeout,
            )

            elapsed = time.perf_counter() - started

            if r.status_code != 200:
                result = DownloadResult(
                    guid,
                    ticker,
                    None,
                    DownloadStatus.HTTP_ERROR,
                    r.status_code,
                    0,
                    elapsed,
                    None,
                    f"HTTP {r.status_code}",
                )

                self.logger.log(result)
                return result

            html = r.text

            validation = self.validator.validate(html)

            if not validation.valid:
                result = DownloadResult(
                    guid,
                    ticker,
                    None,
                    DownloadStatus.INVALID_HTML,
                    200,
                    len(r.content),
                    elapsed,
                    None,
                    validation.reason,
                )

                self.logger.log(result)
                return result

            presentation_id = validation.presentation_id

            output = self.fs.build_html_path(
                ticker=ticker,
                presentation_id=presentation_id,
            )

            if output.exists():

                result = DownloadResult(
                    guid,
                    ticker,
                    presentation_id,
                    DownloadStatus.SKIPPED,
                    200,
                    len(r.content),
                    elapsed,
                    output,
                    None,
                )

                self.logger.log(result)
                return result

            tmp = output.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)

            tmp.write_text(html, encoding="utf-8")
            tmp.replace(output)

            result = DownloadResult(
                guid,
                ticker,
                presentation_id,
                DownloadStatus.SUCCESS,
                200,
                len(r.content),
                elapsed,
                output,
                None,
            )

            self.logger.log(result)

            return result

        except requests.RequestException as exc:

            elapsed = time.perf_counter() - started

            result = DownloadResult(
                guid,
                ticker,
                None,
                DownloadStatus.REQUEST_ERROR,
                None,
                0,
                elapsed,
                None,
                str(exc),
            )

            self.logger.log(result)
            return result

        except Exception as exc:

            elapsed = time.perf_counter() - started

            result = DownloadResult(
                guid,
                ticker,
                None,
                DownloadStatus.UNKNOWN_ERROR,
                None,
                0,
                elapsed,
                None,
                str(exc),
            )

            self.logger.log(result)
            return result
