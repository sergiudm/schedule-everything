"""
Build the desktop JSON bridge as a Tauri sidecar binary.

Tauri external binaries are referenced without a target suffix in
tauri.conf.json, while the actual built file includes the host target triple.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "src" / "schedule_management" / "gui" / "bridge.py"
SOURCE_ROOT = ROOT / "src"
BINARIES_DIR = ROOT / "src-tauri" / "binaries"
BUILD_DIR = ROOT / "build" / "gui-sidecar"
BINARY_BASENAME = "schedule-gui-bridge"
EXCLUDED_MODULES = ("matplotlib", "numpy", "PIL")


def _host_triple() -> str:
    try:
        result = subprocess.run(
            ["rustc", "-Vv"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _fallback_host_triple()

    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    return _fallback_host_triple()


def _fallback_host_triple() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
    if system == "darwin":
        return f"{arch}-apple-darwin"
    if system == "linux":
        return f"{arch}-unknown-linux-gnu"
    if system == "windows":
        return f"{arch}-pc-windows-msvc"
    raise RuntimeError(f"unsupported sidecar host platform: {system}/{machine}")


def _remove_previous_binaries() -> None:
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    for path in BINARIES_DIR.glob(f"{BINARY_BASENAME}-*"):
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def main() -> int:
    if not ENTRYPOINT.exists():
        raise FileNotFoundError(f"bridge entrypoint not found: {ENTRYPOINT}")

    target_triple = _host_triple()
    binary_name = f"{BINARY_BASENAME}-{target_triple}"
    _remove_previous_binaries()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        binary_name,
        "--distpath",
        str(BINARIES_DIR),
        "--workpath",
        str(BUILD_DIR / "work"),
        "--specpath",
        str(BUILD_DIR),
        "--paths",
        str(SOURCE_ROOT),
    ]
    for module in EXCLUDED_MODULES:
        command.extend(["--exclude-module", module])
    command.append(str(ENTRYPOINT))
    subprocess.run(command, cwd=ROOT, check=True)

    suffix = ".exe" if os.name == "nt" else ""
    built_binary = BINARIES_DIR / f"{binary_name}{suffix}"
    if not built_binary.exists():
        raise FileNotFoundError(f"sidecar build did not produce {built_binary}")
    built_binary.chmod(0o755)
    print(f"Built GUI bridge sidecar: {built_binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
