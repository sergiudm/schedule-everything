"""Tests for versioned config layout helpers."""

from pathlib import Path

from schedule_management.config_layout import (
    ACTIVE_CONFIG_MARKER,
    clone_active_config_dir,
    migrate_legacy_config_layout,
    resolve_runtime_paths,
    write_active_config_id,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_migrate_legacy_config_layout_moves_files_into_user_config_0(tmp_path):
    config_root = tmp_path / "config"
    config_root.mkdir(parents=True)

    _write(config_root / "settings.toml", "[settings]\n")
    _write(config_root / "odd_weeks.toml", "[monday]\n")
    _write(config_root / "even_weeks.toml", "[monday]\n")
    _write(config_root / "habits.toml", '[habits]\n1 = "Read"\n')
    _write(config_root / "profile.md", "# Profile\n")
    _write(config_root / "ddl.json", "{}\n")
    _write(config_root / "tasks" / "tasks.json", "[]\n")

    migrated = migrate_legacy_config_layout(config_root)

    assert migrated is True
    assert not (config_root / "settings.toml").exists()
    assert (config_root / "user_config_0" / "settings.toml").exists()
    assert (config_root / "user_config_0" / "profile.md").exists()
    assert (config_root / "tasks" / "tasks.json").exists()
    assert (config_root / ACTIVE_CONFIG_MARKER).read_text(encoding="utf-8").strip() == "0"

    paths = resolve_runtime_paths(config_root)
    assert paths.active_config_dir == config_root / "user_config_0"
    assert paths.settings_path == config_root / "user_config_0" / "settings.toml"
    assert paths.tasks_path == config_root / "tasks" / "tasks.json"


def test_clone_active_config_dir_copies_current_config_set(tmp_path):
    config_root = tmp_path / "config"
    source_dir = config_root / "user_config_0"
    _write(source_dir / "settings.toml", "[settings]\n")
    _write(source_dir / "profile.md", "# Draft\n")
    _write(source_dir / "ddl.json", "{}\n")
    write_active_config_id(config_root, 0)

    new_config_id, new_config_dir = clone_active_config_dir(
        config_root,
        source_dir=source_dir,
    )

    assert new_config_id == 1
    assert new_config_dir == config_root / "user_config_1"
    assert (new_config_dir / "settings.toml").read_text(encoding="utf-8") == "[settings]\n"
    assert (new_config_dir / "profile.md").read_text(encoding="utf-8") == "# Draft\n"
    assert (new_config_dir / "ddl.json").read_text(encoding="utf-8") == "{}\n"
