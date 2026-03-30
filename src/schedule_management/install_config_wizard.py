"""Install-time wizard for validating and completing user configuration."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


InputFunc = Callable[[str], str]

REQUIRED_CONFIG_FILES = OrderedDict(
    [
        ("settings.toml", "settings_template.toml"),
        ("odd_weeks.toml", "week_schedule_template.toml"),
        ("even_weeks.toml", "week_schedule_template.toml"),
        ("habits.toml", "habits_template.toml"),
    ]
)


@dataclass(frozen=True)
class SettingEntry:
    section: str
    key: str
    value: Any


def _load_toml_file(path: Path) -> dict[str, Any]:
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def _ask_yes_no(
    prompt: str,
    *,
    default: bool,
    auto_yes: bool,
    input_func: InputFunc,
) -> bool:
    if auto_yes:
        print(f"{prompt} [auto-yes]")
        return True

    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = input_func(f"{prompt} {suffix}: ").strip().lower()
        except EOFError:
            print("Input stream closed; using default answer.")
            return default

        if answer == "":
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer with 'y' or 'n'.")


def _format_toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    raise ValueError(f"Unsupported config value type: {type(value).__name__}")


def _parse_user_value(raw_value: str, default_value: Any) -> Any:
    if isinstance(default_value, bool):
        lowered = raw_value.strip().lower()
        if lowered in {"true", "t", "yes", "y", "1"}:
            return True
        if lowered in {"false", "f", "no", "n", "0"}:
            return False
        raise ValueError("expected true/false")

    if isinstance(default_value, int) and not isinstance(default_value, bool):
        try:
            return int(raw_value.strip())
        except ValueError as exc:
            raise ValueError("expected an integer") from exc

    if isinstance(default_value, float):
        try:
            return float(raw_value.strip())
        except ValueError as exc:
            raise ValueError("expected a number") from exc

    if isinstance(default_value, list):
        stripped = raw_value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = tomllib.loads(f"value = {stripped}").get("value")
            except tomllib.TOMLDecodeError as exc:
                raise ValueError("expected a valid TOML list") from exc
            if not isinstance(parsed, list):
                raise ValueError("expected a list")
            return parsed

        if stripped == "":
            return []

        items = [part.strip() for part in stripped.split(",") if part.strip()]
        if not items:
            return []

        if default_value and all(isinstance(item, int) for item in default_value):
            try:
                return [int(item) for item in items]
            except ValueError as exc:
                raise ValueError("expected comma-separated integers") from exc

        return items

    return raw_value


def _collect_missing_settings(
    current_data: dict[str, Any], template_data: dict[str, Any]
) -> list[SettingEntry]:
    missing: list[SettingEntry] = []

    for section, template_section_data in template_data.items():
        if not isinstance(template_section_data, dict):
            continue

        current_section_data = current_data.get(section, {})
        if not isinstance(current_section_data, dict):
            current_section_data = {}

        for key, default_value in template_section_data.items():
            if key not in current_section_data:
                missing.append(
                    SettingEntry(section=section, key=key, value=default_value)
                )

    return missing


def _find_section_bounds(lines: list[str]) -> dict[str, tuple[int, int]]:
    bounds: dict[str, tuple[int, int]] = {}
    headers: list[tuple[str, int]] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and "=" not in stripped:
            section_name = stripped[1:-1].strip()
            if section_name:
                headers.append((section_name, idx))

    for idx, (section_name, start_idx) in enumerate(headers):
        end_idx = headers[idx + 1][1] if idx + 1 < len(headers) else len(lines)
        bounds[section_name] = (start_idx, end_idx)

    return bounds


def _write_missing_settings(settings_path: Path, updates: list[SettingEntry]) -> None:
    if not settings_path.exists():
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("", encoding="utf-8")

    lines = settings_path.read_text(encoding="utf-8").splitlines()

    grouped_updates: OrderedDict[str, list[SettingEntry]] = OrderedDict()
    for entry in updates:
        grouped_updates.setdefault(entry.section, []).append(entry)

    for section, section_updates in grouped_updates.items():
        insertion_lines = [
            f"{entry.key} = {_format_toml_value(entry.value)}"
            for entry in section_updates
        ]
        section_bounds = _find_section_bounds(lines)

        if section in section_bounds:
            _, end_idx = section_bounds[section]
            lines[end_idx:end_idx] = insertion_lines
            continue

        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section}]")
        lines.extend(insertion_lines)

    content = "\n".join(lines).rstrip()
    if content:
        content += "\n"
    settings_path.write_text(content, encoding="utf-8")


def _ensure_required_files(
    config_dir: Path,
    template_dir: Path,
    *,
    auto_yes: bool,
    input_func: InputFunc,
) -> bool:
    for config_name, template_name in REQUIRED_CONFIG_FILES.items():
        config_path = config_dir / config_name
        if config_path.exists():
            continue

        template_path = template_dir / template_name
        if not template_path.exists():
            print(f"Missing required template: {template_path}")
            return False

        should_create = _ask_yes_no(
            f"{config_name} is missing. Create it from {template_name}?",
            default=True,
            auto_yes=auto_yes,
            input_func=input_func,
        )
        if not should_create:
            print(f"Cannot continue without {config_name}.")
            return False

        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_path, config_path)
        print(f"Created {config_path}")

    return True


def _load_current_settings(
    settings_path: Path,
    settings_template_path: Path,
    *,
    auto_yes: bool,
    input_func: InputFunc,
) -> dict[str, Any] | None:
    if not settings_path.exists():
        return {}

    try:
        return _load_toml_file(settings_path)
    except tomllib.TOMLDecodeError as exc:
        print(f"Invalid TOML in {settings_path}: {exc}")
        if not settings_template_path.exists():
            print(
                "settings_template.toml is unavailable; cannot auto-repair settings.toml"
            )
            return None

        should_replace = _ask_yes_no(
            "Replace settings.toml with settings_template.toml and continue?",
            default=False,
            auto_yes=auto_yes,
            input_func=input_func,
        )
        if not should_replace:
            return None

        shutil.copyfile(settings_template_path, settings_path)
        return _load_toml_file(settings_path)


def run_wizard(
    config_dir: Path,
    template_dir: Path,
    *,
    auto_yes: bool = False,
    input_func: InputFunc = input,
) -> bool:
    config_dir.mkdir(parents=True, exist_ok=True)

    if not _ensure_required_files(
        config_dir, template_dir, auto_yes=auto_yes, input_func=input_func
    ):
        return False

    settings_template_path = template_dir / "settings_template.toml"
    if not settings_template_path.exists():
        print("settings_template.toml not found; skipping missing-key checks.")
        return True

    try:
        template_settings = _load_toml_file(settings_template_path)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"Failed to load settings template: {exc}")
        return False

    settings_path = config_dir / "settings.toml"
    current_settings = _load_current_settings(
        settings_path,
        settings_template_path,
        auto_yes=auto_yes,
        input_func=input_func,
    )
    if current_settings is None:
        return False

    missing_entries = _collect_missing_settings(current_settings, template_settings)
    if not missing_entries:
        print("Configuration check complete. No missing keys found.")
        return True

    print(f"Found {len(missing_entries)} missing configuration value(s).")

    resolved_entries: list[SettingEntry] = []
    for entry in missing_entries:
        default_display = _format_toml_value(entry.value)

        if auto_yes:
            print(
                f"Missing [{entry.section}].{entry.key}; using default {default_display}"
            )
            resolved_entries.append(entry)
            continue

        while True:
            response = input_func(
                f"Enter value for [{entry.section}].{entry.key} "
                f"(press Enter for {default_display}): "
            ).strip()

            if response == "":
                resolved_entries.append(entry)
                break

            try:
                parsed_value = _parse_user_value(response, entry.value)
            except ValueError as exc:
                print(f"Invalid value: {exc}")
                continue

            resolved_entries.append(
                SettingEntry(section=entry.section, key=entry.key, value=parsed_value)
            )
            break

    _write_missing_settings(settings_path, resolved_entries)
    print(f"Updated {settings_path} with {len(resolved_entries)} missing value(s).")
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and complete required reminder configuration files."
    )
    parser.add_argument(
        "--config-dir",
        required=True,
        help="Target configuration directory (e.g. ~/.schedule_management/config)",
    )
    parser.add_argument(
        "--template-dir",
        help="Directory containing settings_template.toml and other templates.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Use template defaults without interactive prompts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    config_dir = Path(args.config_dir).expanduser()
    template_dir = (
        Path(args.template_dir).expanduser() if args.template_dir else config_dir
    )

    if not args.yes and not sys.stdin.isatty():
        print(
            "Interactive prompts require a TTY. Re-run with --yes to accept defaults."
        )
        return 1

    success = run_wizard(config_dir, template_dir, auto_yes=args.yes)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
