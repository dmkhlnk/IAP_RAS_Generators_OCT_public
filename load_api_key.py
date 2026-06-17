#!/usr/bin/env python3
"""
Load Gemini API key from environment variables or a local .env file.

Never commit .env — use env.example as a template.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PLACEHOLDER_VALUES = frozenset({
    "",
    "your_gemini_api_key_here",
    "your_api_key_here",
    "your_key_here",
})

_ENV_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _is_valid_key(value: str | None) -> bool:
    return bool(value) and value not in _PLACEHOLDER_VALUES


def load_dotenv(env_path: Path | None = None) -> None:
    """Populate GEMINI_API_KEY / GOOGLE_API_KEY from .env if not already set."""
    env_path = env_path or (_project_root() / ".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = _strip_quotes(value.split("#", 1)[0])

        if key not in _ENV_KEY_NAMES or not _is_valid_key(value):
            continue

        if not os.getenv("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = value
        if not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = value


def get_api_key() -> str | None:
    """Return configured API key, or None if missing."""
    load_dotenv()
    for name in _ENV_KEY_NAMES:
        value = os.getenv(name)
        if _is_valid_key(value):
            return value
    return None


def require_api_key() -> str:
    """Return API key or raise ValueError with setup instructions."""
    key = get_api_key()
    if key:
        return key
    raise ValueError(
        "Gemini API key not found. Copy env.example to .env and set GEMINI_API_KEY, "
        "or export GEMINI_API_KEY in your shell."
    )


def _mask_key(key: str) -> str:
    if len(key) <= 10:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def main() -> int:
    key = get_api_key()
    if key:
        print(f"API key configured ({_mask_key(key)})")
        return 0
    print("API key NOT configured.")
    print("  cp env.example .env")
    print("  # edit .env and set GEMINI_API_KEY=your_key")
    return 1


if __name__ == "__main__":
    sys.exit(main())
