"""
Attachment helpers for setup-agent build turns.

The build flow accepts either text files or images and normalizes them into a
single attachment model.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from schedule_management.commands.setup_agent.models import SourceAttachment

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".py",
    ".ini",
    ".log",
}

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}


def _resolve_source_path_input(raw_input: str) -> Path:
    """Resolve user-provided source path, including common download locations."""
    raw = raw_input.strip()
    candidate = Path(raw).expanduser()
    if candidate.exists():
        return candidate

    has_separators = any(separator in raw for separator in ("/", "\\"))
    if candidate.is_absolute() or has_separators:
        return candidate

    file_name = candidate.name
    common_roots: list[Path] = [
        Path.cwd(),
        Path.home(),
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Pictures",
    ]

    seen: set[Path] = set()
    for root in common_roots:
        try:
            resolved_root = root.expanduser().resolve()
        except OSError:
            continue
        if resolved_root in seen:
            continue
        seen.add(resolved_root)

        probe = resolved_root / file_name
        if probe.exists():
            return probe

    return candidate


def _detect_image_mime_from_bytes(raw: bytes) -> str | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a"):
        return "image/gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith(b"BM"):
        return "image/bmp"
    if raw.startswith(b"II*\x00") or raw.startswith(b"MM\x00*"):
        return "image/tiff"
    if b"ftypheic" in raw[:64] or b"ftypheif" in raw[:64]:
        return "image/heic"
    return None


def _normalize_image_mime(path: Path, raw: bytes, guessed: str | None) -> str:
    if guessed and guessed.startswith("image/"):
        return guessed

    by_header = _detect_image_mime_from_bytes(raw)
    if by_header:
        return by_header

    suffix = path.suffix.lower()
    suffix_to_mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }
    return suffix_to_mime.get(suffix, "application/octet-stream")


def _load_source_attachment(path: Path) -> tuple[SourceAttachment | None, str | None]:
    if not path.exists():
        return None, f"Path does not exist: {path}"
    if path.is_dir():
        return None, f"Expected a file path, but got directory: {path}"

    suffix = path.suffix.lower()
    raw = path.read_bytes()
    mime_type, _ = mimetypes.guess_type(path.name)
    mime = _normalize_image_mime(path, raw, mime_type)

    if suffix in IMAGE_EXTENSIONS or mime.startswith("image/"):
        encoded = base64.b64encode(raw).decode("ascii")
        return SourceAttachment(path=path, mime_type=mime, image_base64=encoded), None

    if suffix in TEXT_EXTENSIONS or mime.startswith("text/"):
        content = raw.decode("utf-8", errors="replace")
        if len(content) > 15000:
            content = content[:15000] + "\n... [truncated]"
        return SourceAttachment(
            path=path,
            mime_type="text/plain",
            text_content=content,
        ), None

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return (
            None,
            "Unsupported file type for setup agent. Use a text file or image file.",
        )

    if len(content) > 15000:
        content = content[:15000] + "\n... [truncated]"

    return SourceAttachment(
        path=path,
        mime_type="text/plain",
        text_content=content,
    ), None
