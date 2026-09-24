import json
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

import httpx
import typer
from dotenv import get_key, set_key

from app.platform.cli.utils import ROOT_DIR

SENSITIVE_KEYS = {"secret", "registrationAccessToken"}

KEYCLOAK_COMPOSE_FILE = (
    "app/platform/plates/auth_plates/keycloak/docker-compose.keycloak.yml"
)
KEYCLOAK_PROJECT = "hackplate-keycloak"

app = typer.Typer(help="Manage the local Keycloak stack.")


def keycloak_compose(mode: Literal["dev", "prod"] | None = None) -> list[str]:
    """Base `docker compose` command for the standalone Keycloak project.

    Keycloak lives in its own compose project, so the project name and directory
    are pinned explicitly: the project dir keeps relative paths (`.env`, the realm
    settings mount) resolving from the repo root, and the project name keeps this
    stack from colliding with the app stack in `docker-compose.yml`.
    """
    command = [
        "docker",
        "compose",
        "-f",
        KEYCLOAK_COMPOSE_FILE,
        "--project-directory",
        ROOT_DIR,
        "-p",
        KEYCLOAK_PROJECT,
    ]
    if mode:
        command += ["--profile", mode]
    return command


def keycloak_service(mode: Literal["dev", "prod"]) -> str:
    return "keycloak" if mode == "dev" else "keycloak-prod"


def uses_local_keycloak() -> bool:
    """True when the active auth plate is Keycloak and it is the local stack."""
    env_path = Path(ROOT_DIR) / ".env"
    auth_plate = get_key(env_path, "HACKPLATE_AUTH")
    use_local = (get_key(env_path, "KEYCLOAK_USE_LOCAL") or "").strip().lower()
    return auth_plate == "keycloak" and use_local in {"true", "1", "yes", "on"}


def allow_keycloak_http(url: str, username: str, password: str, service: str):
    kcadm = [
        *keycloak_compose(),
        "exec",
        service,
        "/opt/keycloak/bin/kcadm.sh",
    ]
    subprocess.run(
        [
            *kcadm,
            "config",
            "credentials",
            "--server",
            url,
            "--realm",
            "master",
            "--user",
            username,
            "--password",
            password,
        ],
        check=True,
    )
    subprocess.run(
        [*kcadm, "update", "realms/master", "-s", "sslRequired=none"],
        check=True,
    )


def wait_for_keycloak(url: str | None = None, retries: int = 30, delay: float = 1.0):
    """Poll Keycloak over HTTP until it answers, from wherever the CLI is running."""
    from app.platform.plates.auth_plates.keycloak.env_settings import KeycloakSettings

    kc_url = url or KeycloakSettings().url
    typer.echo(f"Waiting for Keycloak at {kc_url} ...")
    for _ in range(retries):
        try:
            httpx.get(f"{kc_url}/realms/master", timeout=2)
            return
        except Exception:
            time.sleep(delay)
    typer.echo(
        f"Keycloak did not become reachable at {kc_url} in time.\n"
        "If the container is running, check that the host in KEYCLOAK_URL resolves "
        "on this machine. For the default http://keycloak:8080, add it to /etc/hosts:\n"
        "    sudo sh -c 'echo \"127.0.0.1 keycloak\" >> /etc/hosts'",
        err=True,
    )
    raise typer.Exit(code=1)


def start_keycloak(mode: Literal["dev", "prod"], extra: list[str] | None = None):
    """Bring the Keycloak stack up and block until the container reports healthy."""
    typer.echo("Starting Keycloak...")
    subprocess.run(
        [*keycloak_compose(mode), "up", "-d", "--wait", *(extra or [])],
        check=True,
    )
    wait_for_keycloak()
    typer.echo("Keycloak is ready.")


def ensure_keycloak(mode: Literal["dev", "prod"]):
    """Start Keycloak and sync its realm config, when the local stack is in use."""
    if not uses_local_keycloak():
        return
    start_keycloak(mode)
    subprocess.run(["hackplate", "keycloak", "sync", "--mode", mode], check=True)


@app.command("up")
def keycloak_up(
    mode: Literal["dev", "prod"] = typer.Option(
        "dev", "-m", "--mode", help="Compose profile: dev or prod."
    ),
    args: list[str] = typer.Argument(default=None),
):
    """Start the standalone Keycloak stack and wait for it to become healthy."""
    env_path = Path(ROOT_DIR) / ".env"
    if get_key(env_path, "HACKPLATE_AUTH") != "keycloak":
        typer.echo(
            "warning: the active auth plate is not 'keycloak' — starting Keycloak "
            "anyway, but the app will not use it. Switch with "
            "`hackplate setplate auth keycloak`.",
            err=True,
        )
    elif not uses_local_keycloak():
        typer.echo(
            "warning: KEYCLOAK_USE_LOCAL is not true — the app is pointed at an "
            "external Keycloak. Starting the local stack anyway.",
            err=True,
        )

    start_keycloak(mode, args or [])


@app.command("down")
def keycloak_down(args: list[str] = typer.Argument(default=None)):
    """Stop the standalone Keycloak stack."""
    subprocess.run(
        [*keycloak_compose(), "--profile", "*", "down", *(args or [])],
        check=True,
    )


@app.command("sync")
def sync(
    mode: Literal["dev", "prod"] = typer.Option(
        "dev",
        "-m",
        "--mode",
        help="Which running mode's Keycloak container to sync from.",
    ),
    url: str | None = typer.Option(None, "-u", "--url"),
    realm: str | None = typer.Option(None, "-r", "--realm"),
    username: str | None = typer.Option(None, "--username"),
    password: str | None = typer.Option(None, "-p", "--password"),
):
    """Sync Keycloak realm config to app/platform/plates/auth_plates/keycloak/settings.json."""
    from keycloak import KeycloakAdmin
    from keycloak.exceptions import KeycloakError

    from app.platform.plates.auth_plates.keycloak.env_settings import KeycloakSettings

    settings = KeycloakSettings()

    kc_url = url or settings.url
    kc_realm = realm or settings.realm
    kc_username = username or settings.admin_username
    kc_password = password or settings.admin_password
    kc_use_local = settings.use_local

    keycloak_admin = KeycloakAdmin(
        server_url=kc_url,
        username=kc_username,
        password=kc_password,
        realm_name=kc_realm,
        user_realm_name="master",
    )

    if kc_use_local:
        allow_keycloak_http(kc_url, kc_username, kc_password, keycloak_service(mode))

    try:
        exported: dict[str, Any] = keycloak_admin.export_realm(
            export_clients=True, export_groups_and_role=True
        )

        clients: list[dict[str, Any]] = exported.get("clients", [])
        hackplate_client = next(
            (c for c in clients if c["clientId"] == settings.client_id), None
        )
        if not hackplate_client:
            typer.echo(
                f"Could not find client '{settings.client_id}' in realm.", err=True
            )
            raise typer.Exit(code=1)

        client_secret = keycloak_admin.get_client_secrets(hackplate_client["id"]).get(
            "value"
        )
    except KeycloakError as e:
        typer.echo(f"Could not sync Keycloak at {kc_url}: {e}", err=True)
        raise typer.Exit(code=1)
    finally:
        if kc_use_local and mode == "dev":
            # Keep admin portal open during development. We assume that master realm will be protected by HTTPS when deployed to production.
            keycloak_admin.connection.realm_name = "master"
            keycloak_admin.update_realm("master", {"sslRequired": "EXTERNAL"})

    if client_secret:
        set_key(
            Path(ROOT_DIR) / ".env",
            "KEYCLOAK_CLIENT_SECRET",
            client_secret,
            quote_mode="never",
        )
        typer.echo("Client secret written to .env")

    exported["clients"] = [
        {k: v for k, v in c.items() if k not in SENSITIVE_KEYS} for c in clients
    ]

    merged = exported

    out_path = Path(ROOT_DIR) / "app/platform/plates/auth_plates/keycloak/settings.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2) + "\n")

    typer.echo("Keycloak synced!")
