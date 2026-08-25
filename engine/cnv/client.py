"""Cliente HTTP CNV: timeout, retry, backoff exponencial, rate limiting por host.

No decide nada sobre el contenido: devuelve bytes crudos + metadata de transporte.
La validacion de contenido vive en engine/cnv/validate.py (leccion C2: HTTP 200 no
significa documento valido).
"""
from __future__ import annotations

import hashlib
import random
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

CNV_WWW = "https://www.cnv.gov.ar"
AIF2 = "https://aif2.cnv.gov.ar"
BLOB = "https://blob.cnv.gov.ar"

URL_EMPRESA = CNV_WWW + "/SitioWeb/Empresas/Empresa/{cuit}"
URL_VISOR = AIF2 + "/presentations/publicview/{guid}"
URL_VALETKEY = AIF2 + "/api/ValetKeyProvider/GetPublicValetKey/{guid}?operation=DownloadBlob"
URL_BLOB = BLOB + "/BlobWebService.svc/DownloadBlob/{guid}"

USER_AGENT = "Catalaxia-Research/1.0 (+fmonfasani@gmail.com)"

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS = {400, 401, 403, 404, 410}

# La pagina empresa de un emisor grande pesa ~2.3 MB y CNV tarda 30-40 s en servirla.
# Los visores responden en 1-3 s. Por eso el read timeout es por host.
DEFAULT_TIMEOUTS = {
    "www.cnv.gov.ar": (10.0, 240.0),
    "aif2.cnv.gov.ar": (10.0, 120.0),
    "blob.cnv.gov.ar": (10.0, 600.0),
}
DEFAULT_DELAYS = {
    "www.cnv.gov.ar": 2.0,
    "aif2.cnv.gov.ar": 0.8,
    "blob.cnv.gov.ar": 1.0,
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass
class FetchResult:
    """Resultado de transporte. content=None significa que no hubo cuerpo utilizable."""

    url: str
    method: str = "GET"
    http_status: int | None = None
    content_type: str | None = None
    content: bytes | None = None
    bytes: int = 0
    elapsed_ms: int = 0
    attempts: int = 0
    error: str | None = None
    retry_after: float | None = None
    history: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.http_status == 200 and self.content is not None

    def transport_state(self) -> str:
        if self.http_status == 404:
            return "NOT_FOUND"
        if self.http_status in (401, 403, 429):
            return "BLOCKED"
        if self.ok:
            return "OK"
        return "FAILED"


class RateLimiter:
    """Espaciado minimo entre requests, por host. Thread-safe por si se paraleliza luego."""

    def __init__(self, delays: dict[str, float], default: float = 1.0):
        self.delays = dict(delays)
        self.default = default
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self.starts: list[tuple[str, float]] = []

    def delay_for(self, host: str) -> float:
        return self.delays.get(host, self.default)

    def acquire(self, host: str) -> None:
        with self._lock:
            delay = self.delay_for(host)
            wait = delay - (time.monotonic() - self._last.get(host, -1e9))
            if wait > 0:
                time.sleep(wait)
            now = time.monotonic()
            self._last[host] = now
            self.starts.append((host, now))

    def min_interval(self, host: str) -> float | None:
        ts = sorted(t for h, t in self.starts if h == host)
        if len(ts) < 2:
            return None
        return round(min(b - a for a, b in zip(ts, ts[1:])), 3)


class CnvClient:
    def __init__(self, rate: RateLimiter | None = None, max_attempts: int = 4,
                 backoff_base: float = 1.5, backoff_cap: float = 30.0,
                 timeouts: dict[str, tuple[float, float]] | None = None,
                 session: requests.Session | None = None, jitter: bool = True,
                 sleeper=time.sleep):
        self.rate = rate or RateLimiter(DEFAULT_DELAYS)
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.timeouts = dict(timeouts or DEFAULT_TIMEOUTS)
        self.jitter = jitter
        self._sleep = sleeper
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "es-AR,es;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })
        self.stats = {"requests": 0, "retries": 0, "rate_limited": 0}

    # -- transporte -----------------------------------------------------------
    def _timeout(self, host: str) -> tuple[float, float]:
        return self.timeouts.get(host, (10.0, 180.0))

    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, self.backoff_cap)
        wait = min(self.backoff_base * (2 ** (attempt - 1)), self.backoff_cap)
        if self.jitter:
            wait *= 0.5 + random.random()
        return round(wait, 3)

    def request(self, url: str, method: str = "GET", **kwargs) -> FetchResult:
        host = urlparse(url).netloc
        res = FetchResult(url=url, method=method)
        started = time.monotonic()
        for attempt in range(1, self.max_attempts + 1):
            res.attempts = attempt
            self.rate.acquire(host)
            self.stats["requests"] += 1
            try:
                resp = self.session.request(method, url, timeout=self._timeout(host), **kwargs)
            except requests.RequestException as exc:
                res.error = f"{type(exc).__name__}: {exc}"
                res.history.append({"attempt": attempt, "error": res.error})
                if attempt < self.max_attempts:
                    self.stats["retries"] += 1
                    self._sleep(self._backoff(attempt, None))
                    continue
                break

            status = resp.status_code
            ctype = resp.headers.get("Content-Type")
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            res.history.append({"attempt": attempt, "http_status": status, "content_type": ctype})
            if status == 200:
                res.http_status, res.content_type = 200, ctype
                res.content, res.bytes = resp.content, len(resp.content)
                res.error = None
                break
            res.http_status, res.content_type, res.retry_after = status, ctype, retry_after
            res.error = f"HTTP {status}"
            if status == 429:
                self.stats["rate_limited"] += 1
            if status in NON_RETRYABLE_STATUS or status not in RETRYABLE_STATUS:
                res.content = None
                break
            if attempt < self.max_attempts:
                self.stats["retries"] += 1
                self._sleep(self._backoff(attempt, retry_after))
                continue
            res.content = None
        res.elapsed_ms = int((time.monotonic() - started) * 1000)
        return res

    # -- endpoints CNV --------------------------------------------------------
    def fetch_empresa(self, cuit: str) -> FetchResult:
        return self.request(URL_EMPRESA.format(cuit=cuit))

    def fetch_visor(self, guid: str) -> FetchResult:
        return self.request(URL_VISOR.format(guid=guid))

    def fetch_valet_key(self, blob_guid: str) -> tuple[str | None, FetchResult]:
        """PASO 1 del flujo de adjuntos. OJO: CNV devuelve 200 + token valido incluso
        para un blob inexistente; la falla recien aparece en el POST del blob."""
        res = self.request(URL_VALETKEY.format(guid=blob_guid))
        if not res.ok:
            return None, res
        payload = res.content.decode("utf-8", "replace")
        key = re.search(r'"valetKeyData"\s*:\s*"([^"]+)"', payload)
        return (key.group(1) if key else None), res

    def fetch_blob(self, blob_guid: str, valet_key: str, csrf_token: str | None = None) -> FetchResult:
        headers = {"X-CSRF-TOKEN": csrf_token} if csrf_token else {}
        return self.request(URL_BLOB.format(guid=blob_guid), method="POST",
                            data={"ValetKey": valet_key}, headers=headers)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
