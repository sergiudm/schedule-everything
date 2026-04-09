"""
Config layout helpers for versioned user schedule sets.

This module keeps the runtime path logic in one place. It supports migrating
the legacy flat layout into `user_config_n` directories, tracks the active
config set, and resolves the paths used by the rest of the application.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

CONFIG_SET_PREFIX = "user_config_"
ACTIVE_CONFIG_MARKER = ".active_config"
MANAGED_CONFIG_FILE_NAMES = (
    "ddl.json",
    "even_weeks.toml",
    "habits.toml",
    "habits_template.toml",
    "odd_weeks.toml",
    "profile.md",
    "settings.toml",
    "settings_template.toml",
    "week_schedule_template.toml",
)

_CONFIG_SET_PATTERN = re.compile(rf"^{CONFIG_SET_PREFIX}(\d+)$")


@dataclass(frozen=True)
class RuntimePaths:
    """Resolved filesystem paths for the currently active schedule set."""

    root_dir: Path
    active_id: int
    active_config_dir: Path
    settings_path: Path
    odd_path: Path
    even_path: Path
    ddl_path: Path
    habit_path: Path
    profile_path: Path
    tasks_path: Path
    task_log_path: Path
    record_path: Path
    procrastinate_path: Path


class DynamicPath(os.PathLike[str]):
    """Path-like wrapper that resolves against the current active config set."""

    def __init__(self, resolver: Callable[[], Path]):
        self._resolver = resolver

    def resolve_path(self) -> Path:
        return self._resolver()

    def __fspath__(self) -> str:
        return str(self.resolve_path())

    def __str__(self) -> str:
        return str(self.resolve_path())

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str(self)!r})"


def resolve_config_root_dir() -> Path:
    """Return the root config directory from the runtime environment."""
    raw_dir = os.getenv("REMINDER_CONFIG_DIR") or "config"
    return Path(raw_dir).expanduser().resolve()


def _parse_config_set_id(path: Path) -> int | None:
    match = _CONFIG_SET_PATTERN.fullmatch(path.name)
    if match is None:
        return None
    return int(match.group(1))


def _discover_config_dirs(root_dir: Path) -> dict[int, Path]:
    if not root_dir.exists():
        return {}

    discovered: dict[int, Path] = {}
    for child in root_dir.iterdir():
        if not child.is_dir():
            continue
        config_id = _parse_config_set_id(child)
        if config_id is None:
            continue
        discovered[config_id] = child
    return discovered


def list_config_ids(root_dir: Path | None = None) -> list[int]:
    """Return sorted config ids discovered under the root config directory."""
    actual_root = root_dir or resolve_config_root_dir()
    return sorted(_discover_config_dirs(actual_root))


def get_config_dir(root_dir: Path | None, config_id: int) -> Path:
    """Return the directory path for a specific config id."""
    actual_root = root_dir or resolve_config_root_dir()
    return actual_root / f"{CONFIG_SET_PREFIX}{config_id}"


def get_next_config_id(root_dir: Path | None = None) -> int:
    """Return the next unused config id under the root config directory."""
    ids = list_config_ids(root_dir)
    return max(ids, default=-1) + 1


def has_legacy_config_files(root_dir: Path | None = None) -> bool:
    """Return whether the root directory still contains the legacy flat files."""
    actual_root = root_dir or resolve_config_root_dir()
    return any((actual_root / file_name).exists() for file_name in MANAGED_CONFIG_FILE_NAMES)


def _read_active_config_marker(root_dir: Path) -> int | None:
    marker_path = root_dir / ACTIVE_CONFIG_MARKER
    if not marker_path.exists():
        return None

    try:
        raw_value = marker_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError:
        return None


def write_active_config_id(root_dir: Path | None, config_id: int) -> Path:
    """Persist the active config id marker under the root config directory."""
    actual_root = root_dir or resolve_config_root_dir()
    actual_root.mkdir(parents=True, exist_ok=True)

    marker_path = actual_root / ACTIVE_CONFIG_MARKER
    marker_path.write_text(f"{config_id}\n", encoding="utf-8")
    return marker_path


def migrate_legacy_config_layout(root_dir: Path | None = None) -> bool:
    """Move the legacy flat config files into `user_config_0` once."""
    actual_root = root_dir or resolve_config_root_dir()
    if not actual_root.exists():
        return False

    if list_config_ids(actual_root):
        return False

    legacy_files = [
        actual_root / file_name
        for file_name in MANAGED_CONFIG_FILE_NAMES
        if (actual_root / file_name).exists()
    ]
    if not legacy_files:
        return False

    target_dir = get_config_dir(actual_root, 0)
    target_dir.mkdir(parents=True, exist_ok=True)
    for source_path in legacy_files:
        shutil.move(str(source_path), str(target_dir / source_path.name))

    write_active_config_id(actual_root, 0)
    return True


def preview_active_config_dir(root_dir: Path | None = None) -> Path:
    """Return the active config directory without mutating on-disk layout."""
    actual_root = root_dir or resolve_config_root_dir()
    config_dirs = _discover_config_dirs(actual_root)
    if not config_dirs:
        return get_config_dir(actual_root, 0)

    active_id = _read_active_config_marker(actual_root)
    if active_id in config_dirs:
        return config_dirs[active_id]

    first_id = min(config_dirs)
    return config_dirs[first_id]


def resolve_active_config_id(root_dir: Path | None = None) -> int | None:
    """Return the active config id after applying the legacy migration if needed."""
    actual_root = root_dir or resolve_config_root_dir()
    migrate_legacy_config_layout(actual_root)

    config_dirs = _discover_config_dirs(actual_root)
    if not config_dirs:
        return None

    active_id = _read_active_config_marker(actual_root)
    if active_id in config_dirs:
        return active_id

    first_id = min(config_dirs)
    write_active_config_id(actual_root, first_id)
    return first_id


def resolve_active_config_dir(
    root_dir: Path | None = None,
    *,
    create: bool = False,
) -> Path:
    """Return the active config directory, defaulting to `user_config_0`."""
    actual_root = root_dir or resolve_config_root_dir()
    active_id = resolve_active_config_id(actual_root)
    if active_id is not None:
        return get_config_dir(actual_root, active_id)

    default_dir = get_config_dir(actual_root, 0)
    if create:
        default_dir.mkdir(parents=True, exist_ok=True)
        write_active_config_id(actual_root, 0)
    return default_dir


def clone_active_config_dir(
    root_dir: Path | None = None,
    *,
    source_dir: Path | None = None,
) -> tuple[int, Path]:
    """Clone the current active config set into the next `user_config_n` dir."""
    actual_root = root_dir or resolve_config_root_dir()
    actual_root.mkdir(parents=True, exist_ok=True)

    source = source_dir or resolve_active_config_dir(actual_root)
    next_id = get_next_config_id(actual_root)
    target_dir = get_config_dir(actual_root, next_id)
    target_dir.mkdir(parents=True, exist_ok=False)

    if source.exists():
        for child in source.iterdir():
            destination = target_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)

    return next_id, target_dir


def resolve_runtime_paths(root_dir: Path | None = None) -> RuntimePaths:
    """Resolve all runtime paths for the active config set and shared task data."""
    actual_root = root_dir or resolve_config_root_dir()
    active_id = resolve_active_config_id(actual_root)
    active_config_dir = resolve_active_config_dir(actual_root)
    if active_id is None:
        active_id = 0

    tasks_dir = actual_root / "tasks"
    return RuntimePaths(
        root_dir=actual_root,
        active_id=active_id,
        active_config_dir=active_config_dir,
        settings_path=active_config_dir / "settings.toml",
        odd_path=active_config_dir / "odd_weeks.toml",
        even_path=active_config_dir / "even_weeks.toml",
        ddl_path=active_config_dir / "ddl.json",
        habit_path=active_config_dir / "habits.toml",
        profile_path=active_config_dir / "profile.md",
        tasks_path=tasks_dir / "tasks.json",
        task_log_path=tasks_dir / "tasks.log",
        record_path=tasks_dir / "record.json",
        procrastinate_path=tasks_dir / "procrastinate.json",
    )


__all__ = [
    "ACTIVE_CONFIG_MARKER",
    "CONFIG_SET_PREFIX",
    "DynamicPath",
    "MANAGED_CONFIG_FILE_NAMES",
    "RuntimePaths",
    "clone_active_config_dir",
    "get_config_dir",
    "get_next_config_id",
    "has_legacy_config_files",
    "list_config_ids",
    "migrate_legacy_config_layout",
    "preview_active_config_dir",
    "resolve_active_config_dir",
    "resolve_active_config_id",
    "resolve_config_root_dir",
    "resolve_runtime_paths",
    "write_active_config_id",
]
