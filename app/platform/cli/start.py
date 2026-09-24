import subprocess
from pathlib import Path
from typing import Literal

import typer
from dotenv import get_key, load_dotenv

from app.platform.cli.keycloak import ensure_keycloak
from app.platform.cli.utils import ROOT_DIR, check

app = typer.Typer()


@app.command()
def run(
    mode: Literal["dev", "prod"] = typer.Option(
        "dev", "-m", "--mode", help="Run mode: dev (hot reload) or prod."
    ),
    args: list[str] = typer.Argument(default=None),
):
    """Start the uvicorn server. -m/--mode selects dev or prod (default: dev)."""
    check(error=True)

    extra = args or []

    load_dotenv(verbose=True)
    ensure_keycloak(mode)

    uvicorn_cmd = ["uv", "run", "uvicorn", "app.main:app"]
    if mode == "dev":
        uvicorn_cmd += ["--reload"]
    else:
        workers = get_key(Path(ROOT_DIR) / ".env", "HACKPLATE_WORKERS") or "4"
        uvicorn_cmd += ["--host", "0.0.0.0", "--port", "8000", "--workers", workers]
    subprocess.run([*uvicorn_cmd, *extra], check=True)


@app.command()
def up(
    mode: Literal["dev", "prod"] = typer.Option(
        "dev", "-m", "--mode", help="Compose profile: dev or prod."
    ),
    args: list[str] = typer.Argument(default=None),
):
    """Start the full stack via docker compose. -m/--mode selects the compose profile (default: dev)."""
    check(error=True)

    extra = args or []

    load_dotenv(verbose=True)
    ensure_keycloak(mode)

    command_prefix = ["docker", "compose", "--profile", mode]

    subprocess.run([*command_prefix, "up", "-d", *extra], check=True)
    subprocess.run([*command_prefix, "logs", "-f"], check=True)


@app.command()
def down(args: list[str] = typer.Argument(default=None)):
    """Stop active docker containers."""
    extra = args or []
    subprocess.run(
        ["docker", "compose", "--profile", "*", "down", *extra],
        check=True,
    )
    typer.echo("Keycloak runs separately — stop it with `hackplate keycloak down`.")
