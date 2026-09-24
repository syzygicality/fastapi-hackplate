import shutil
from pathlib import Path

import typer
from dotenv import get_key

from app.platform.cli.utils import ROOT_DIR

app = typer.Typer()

BASE_FILES = ["routes.py", "schemas.py", "crud.py", "models.py", "__init__.py"]

SQL_MODELS_STUB = "from sqlmodel import SQLModel, Field  # noqa: F401\n"

MONGO_MODELS_STUB = "from app.platform.plates.db_plates.mongo.registry import register_document  # noqa: F401\n"

TOOLS_STUB = """from app.platform.mcp import get_mcp

mcp = get_mcp()

# Register MCP tools on the shared server:
#
# @mcp.tool()
# async def example() -> str:
#     return "hello"
"""

REGISTRIES = {
    "models": "register_models.py",
    "tools": "register_tools.py",
}


def _models_stub() -> str:
    """Pick the models.py stub matching the active db plate (defaults to sqlite)."""
    db = get_key(Path(ROOT_DIR) / ".env", "HACKPLATE_DB") or "sqlite"
    return MONGO_MODELS_STUB if db == "mongo" else SQL_MODELS_STUB


def _registry_path(kind: str) -> Path:
    return Path(ROOT_DIR) / "migrations" / REGISTRIES[kind]


def _import_line(feature_name: str, kind: str) -> str:
    return f"import app.{feature_name}.{kind}  # noqa: F401\n"


def _register(feature_name: str, kind: str) -> None:
    """Append the feature's import to the matching registry, unless already present."""
    registry = _registry_path(kind)
    current = registry.read_text() if registry.exists() else ""
    line = _import_line(feature_name, kind)
    if line in current:
        return
    if current and not current.endswith("\n"):
        current += "\n"
    registry.write_text(current + line)


def _unregister(feature_name: str, kind: str) -> None:
    """Remove the feature's import from the matching registry."""
    registry = _registry_path(kind)
    if not registry.exists():
        return
    registry.write_text(
        registry.read_text().replace(_import_line(feature_name, kind), "")
    )


@app.command()
def startfeature(
    feature_name: str,
    with_tools: bool = typer.Option(
        False,
        "-t",
        "--with-tools",
        help="Also scaffold tools.py and register it in migrations/register_tools.py",
    ),
):
    """Autogenerate feature files and directory."""
    feature_dir = Path(ROOT_DIR) / "app" / feature_name
    try:
        feature_dir.mkdir(exist_ok=False)
    except FileExistsError:
        raise typer.BadParameter(
            f"feature directory /app/{feature_name} already exists."
        )

    for filename in BASE_FILES:
        (feature_dir / filename).touch()
    (feature_dir / "models.py").write_text(_models_stub())
    _register(feature_name, "models")

    if with_tools:
        (feature_dir / "tools.py").write_text(TOOLS_STUB)
        _register(feature_name, "tools")

    typer.echo(f"Started feature '{feature_name}'.")

    if with_tools:
        from app.platform.toml_settings import GeneralSettings

        if not GeneralSettings().mcp_server_enabled:
            typer.echo(
                "note: tools.py is only imported when mcp_server_enabled = true "
                "in [tool.hackplate] (pyproject.toml)."
            )


@app.command()
def dropfeature(feature_name: str):
    """Remove a feature directory and its registry imports."""
    feature_dir = Path(ROOT_DIR) / "app" / feature_name
    if not feature_dir.exists():
        typer.echo(f"Feature directory /app/{feature_name} does not exist.", err=True)
        raise typer.Exit(code=1)
    typer.confirm(
        f"Drop feature '{feature_name}'? This will delete /app/{feature_name} "
        "and its model/tool imports.",
        abort=True,
    )

    for kind in REGISTRIES:
        _unregister(feature_name, kind)
    shutil.rmtree(feature_dir)
    typer.echo(f"Dropped feature '{feature_name}'.")
