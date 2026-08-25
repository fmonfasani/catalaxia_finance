from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "data" / "raw" / "engine"
SEC_UA = "Federico Monfasani fmonfasani@gmail.com"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class Fetcher:
    def __init__(self, delay: float = 0.35, connect_timeout: float = 10.0,
                 read_timeout: float = 180.0, max_attempts: int = 3):
        self.delay = delay
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_attempts = max_attempts
        self.backoff = [2.0, 5.0, 10.0]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"})
        self._last_ts = 0.0
        self.request_starts: list[float] = []

    def _throttle(self) -> None:
        wait = self.delay - (time.monotonic() - self._last_ts)
        if wait > 0:
            time.sleep(wait)

    def fetch(self, url: str) -> dict:
        last_error: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._throttle()
            self._last_ts = time.monotonic()
            self.request_starts.append(self._last_ts)
            try:
                resp = self.session.get(url, timeout=(self.connect_timeout, self.read_timeout))
                if resp.status_code == 200:
                    return {"attempt": attempt, "http_status": 200,
                            "content_type": resp.headers.get("Content-Type"),
                            "content": resp.content, "error": None}
                last_error = f"HTTP {resp.status_code}"
                if resp.status_code not in (429, 500, 502, 503, 504):
                    return {"attempt": attempt, "http_status": resp.status_code,
                            "content_type": resp.headers.get("Content-Type"),
                            "content": None, "error": last_error}
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_attempts:
                time.sleep(self.backoff[min(attempt - 1, len(self.backoff) - 1)])
        return {"attempt": self.max_attempts, "http_status": None,
                "content_type": None, "content": None, "error": last_error}


def raw_existing_hash(rel_path: str) -> str | None:
    path = RAW_ROOT / rel_path
    if not path.exists():
        return None
    return sha256_bytes(path.read_bytes())


def write_raw_new(rel_path: str, content: bytes) -> str:
    path = RAW_ROOT / rel_path
    if path.exists():
        raise FileExistsError(f"RAW overwrite bloqueado: {rel_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(content)
    tmp.rename(path)
    return str(path)
