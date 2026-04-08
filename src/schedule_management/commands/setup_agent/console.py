"""
Shared Rich console for the setup-agent package.

Keeping a single console instance avoids drift in output behavior across the
setup workflow modules.
"""

from rich.console import Console

CONSOLE = Console()
