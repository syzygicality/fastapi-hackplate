import shutil
from pathlib import Path
from typing import Literal

import typer

from app.platform.cli.utils import ROOT_DIR

app = typer.Typer()

BEHAVIOR_DIR = "modes/behavior"
SETTINGS_DIR = "modes/settings"

# CLAUDE.mode.md sits in BEHAVIOR_DIR alongside the mode files it re-exports, and
# Claude Code resolves a relative @import against the importing file's own directory —
# not the project root. So the import written here must be a bare sibling filename;
# a root-style "@modes/behavior/CLAUDE.safe.md" would resolve to
# modes/behavior/modes/behavior/CLAUDE.safe.md and silently load nothing.
MODE_IMPORT_PREFIX = "@CLAUDE."


def _mode_file() -> Path:
    return Path(ROOT_DIR) / BEHAVIOR_DIR / "CLAUDE.mode.md"


def write_mode_files(mode: Literal["safe", "fast", "review"]) -> None:
    """Write modes/behavior/CLAUDE.mode.md and copy the matching settings file into
    .claude/settings.json. Shared by `hackplate setmode` and `hackplate init` — neither
    modes/behavior/ nor .claude/ is guaranteed to exist on a fresh clone, since the
    gitignored entries (CLAUDE.mode.md, settings.json) are files, not their directories.
    """
    mode_path = _mode_file()
    mode_path.parent.mkdir(parents=True, exist_ok=True)
    mode_path.write_text(f"{MODE_IMPORT_PREFIX}{mode}.md\n")

    claude_dir = Path(ROOT_DIR) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(
        Path(ROOT_DIR) / SETTINGS_DIR / f"settings.{mode}.json",
        claude_dir / "settings.json",
    )


@app.command()
def getmode():
    """Show the current Claude Code operating mode."""
    mode_path = _mode_file()
    if not mode_path.exists():
        typer.echo("mode: (not set)")
        return
    content = mode_path.read_text().strip()
    mode = content.removeprefix(MODE_IMPORT_PREFIX).removesuffix(".md")
    typer.echo(f"mode: {mode}")


@app.command()
def setmode(mode: Literal["safe", "fast", "review"]):
    """Switch the Claude Code operating mode. Writes to the gitignored
    modes/behavior/CLAUDE.mode.md."""
    write_mode_files(mode)
    typer.echo(
        f"Claude mode set to '{mode}'. Restart your session for {mode} mode to take effect"
    )
