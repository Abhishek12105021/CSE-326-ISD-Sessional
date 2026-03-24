import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from the backend .env file."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Keep real environment variables higher priority than the file.
        os.environ.setdefault(key, value)


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in {ENV_FILE.name} or in your shell environment."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_jwt_secret: str
    frontend_url: str = "http://localhost:3000"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    _load_env_file(ENV_FILE)

    return Settings(
        supabase_url=_get_env("SUPABASE_URL"),
        supabase_anon_key=_get_env("SUPABASE_ANON_KEY"),
        supabase_service_key=_get_env("SUPABASE_SERVICE_KEY"),
        supabase_jwt_secret=_get_env("SUPABASE_JWT_SECRET"),
        frontend_url=_get_env("FRONTEND_URL", "http://localhost:3000"),
    )
