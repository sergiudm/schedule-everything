"""
Profile draft persistence for the setup agent.

The setup workflow treats `profile.md` as durable context that can be refined
over multiple turns before schedule files are generated.
"""

from __future__ import annotations

from pathlib import Path

PROFILE_FILE_NAME = "profile.md"


def _resolve_profile_path(config_dir: Path) -> Path:
    return config_dir / PROFILE_FILE_NAME


def _load_profile_markdown(config_dir: Path) -> str | None:
    profile_path = _resolve_profile_path(config_dir)
    if not profile_path.exists():
        return None

    try:
        content = profile_path.read_text(encoding="utf-8")
    except OSError:
        return None

    cleaned = content.strip()
    return cleaned or None


def _write_profile_markdown(config_dir: Path, content: str) -> Path:
    cleaned = content.strip()
    if not cleaned:
        raise ValueError("profile markdown cannot be empty")

    config_dir.mkdir(parents=True, exist_ok=True)
    profile_path = _resolve_profile_path(config_dir)
    profile_path.write_text(cleaned + "\n", encoding="utf-8")
    return profile_path
