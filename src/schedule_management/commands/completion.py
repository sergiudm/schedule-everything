"""
Completion command for shell auto-complete support.

This module emits shell completion scripts for the argparse-based CLI.
It keeps completion-specific imports lazy so normal CLI startup stays lean.
"""

from __future__ import annotations

SUPPORTED_COMPLETION_SHELLS = ("bash", "zsh", "tcsh")


def completion_command(args) -> int:
    """
    Handle the `completion` command and print a shell completion script.

    Args:
        args: Namespace with `shell` and `parser_factory` attributes.

    Returns:
        0 on success, 1 on error.
    """
    parser_factory = getattr(args, "parser_factory", None)

    if parser_factory is None:
        print("❌ Completion parser factory is not available.")
        return 1

    try:
        import shtab
    except ImportError:
        print("❌ Shell completion support requires the 'shtab' package.")
        print("   Reinstall or update the project dependencies to enable it.")
        return 1

    try:
        parser = parser_factory()
        print(shtab.complete(parser, shell=args.shell))
        return 0
    except Exception as exc:
        print(f"❌ Error generating completion script: {exc}")
        return 1
