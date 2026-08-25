from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path = REPO_ROOT / ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: str
    db_name: str
    db_user: str
    db_password: str
    mode: str
    allow_prod: bool

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def is_prod(self) -> bool:
        return self.db_port == "5432"

    def describe(self) -> str:
        return f"{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name} mode={self.mode} prod={self.is_prod}"


def load_settings() -> Settings:
    env = {**load_env(), **os.environ}
    settings = Settings(
        db_host=env.get("ENGINE_DB_HOST", "127.0.0.1"),
        db_port=env.get("ENGINE_DB_PORT", "5433"),
        db_name=env.get("ENGINE_DB_NAME", "catalaxia"),
        db_user=env.get("ENGINE_DB_USER", "catalaxia"),
        db_password=env.get("ENGINE_DB_PASSWORD", env.get("POSTGRES_PASSWORD", "")),
        mode=env.get("ENGINE_MODE", "FAST").upper(),
        allow_prod=env.get("ENGINE_ALLOW_PROD", "0") == "1",
    )
    if settings.mode not in {"FAST", "FULL", "AUDIT"}:
        raise ValueError(f"ENGINE_MODE invalido: {settings.mode}")
    if settings.is_prod and not settings.allow_prod:
        raise RuntimeError(
            "EXT-010: el engine apunta al puerto de produccion (5432). "
            "Usar ENGINE_DB_PORT=5433 (dev) o ENGINE_ALLOW_PROD=1 explicito para modo AUDIT."
        )
    return settings
