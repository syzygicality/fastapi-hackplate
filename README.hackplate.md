# Hackplate

A FastAPI metaframework for 24–48 hour hackathons. Clone it, run one command, and have a working API with auth, a database, and a dev CLI, configured by swapping plates, not rewriting code.

## How it works

Hackplate separates two concerns:

- **Framework internals** live in `app/platform/` and are not meant to be edited.
- **Your code** lives in `app/` alongside the framework — routes, schemas, models, feature slices.

Backend integrations are called **plates**. Active plates are selected via environment variables; switching plates is a one-liner that requires no changes to your route handlers.

```
HACKPLATE_DB=sqlite    # sqlite | postgres | supabase | mongo
HACKPLATE_AUTH=local   # local | auth0 | keycloak
```

## Quickstart

```bash
git clone <repo> my-project && cd my-project
pip install uv && uv sync
hackplate init
hackplate run
```

`hackplate init` installs dependencies, creates `.env` from the template, prompts for your initial plate selections, generates a secret key, and installs pre-commit hooks. Fill in any remaining `.env` values (database URLs, OAuth credentials) before running.

## Plates

### Database

| Plate | Driver | Notes |
|---|---|---|
| `sqlite` | aiosqlite | Zero config, default |
| `postgres` | asyncpg | Provide `POSTGRES_URL` or individual fields |
| `supabase` | asyncpg | Same as postgres, SSL required by default |
| `mongo` | Beanie ODM | Motor async driver |

SQLite, Postgres, and Supabase use SQLModel/SQLAlchemy for schema management. MongoDB uses Beanie document models. Switching between SQL and Mongo requires updating the user model base class (see [User Model](#user-model)).

### Auth

| Plate | Description |
|---|---|
| `local` | JWT-based, no external dependencies |
| `auth0` | Auth0 OAuth, requires Auth0 tenant credentials |
| `keycloak` | Keycloak SSO, requires Docker or an external instance |

Auth plates automatically register login/logout/token routes and provide a `get_current_user` dependency available through `app/dependencies.py`.

#### Keycloak

Keycloak runs as its own Docker Compose project, separate from the app stack:

```bash
sudo sh -c 'echo "127.0.0.1 keycloak" >> /etc/hosts'   # one time
hackplate keycloak up                                  # starts Keycloak, waits until healthy
```

`KEYCLOAK_URL` (default `http://keycloak:8080`) is the single URL used by the browser, the app and the CLI, which is why the name needs to resolve on the host as well — inside the api container it is provided automatically.

`hackplate run` and `hackplate up` start Keycloak if it isn't already running and sync its realm config before the app boots, so `hackplate keycloak up` is only needed on its own. Stop it with `hackplate keycloak down`.

## Project structure

```
app/
├── main.py              ← register routers here
├── lifespan.py          ← pre/post startup hooks (user-editable)
├── dependencies.py      ← get_db and get_current_user wrappers (user-editable)
└── platform/            ← framework internals — do not modify
    ├── cli.py
    ├── config.py
    ├── hackplate_types.py
    ├── websocket.py
    ├── lifespan.py
    ├── toml_settings.py
    └── plates/
        ├── auth_plates/
        │   ├── local/
        │   ├── auth0/
        │   └── keycloak/
        └── db_plates/
            ├── sqlite/
            ├── postgres/
            └── mongo/
```

Add your own code as vertical slices under `app/`. Register routers in `app/main.py` inside `register_routes()`.

## Adding a feature

```bash
hackplate startfeature <name>
hackplate startfeature <name> --with-tools   # also scaffold MCP tools
```

Creates `app/<name>/` with `routes.py`, `schemas.py`, `crud.py`, `models.py`, and `__init__.py`, and registers the model in `migrations/register_models.py`.

With `--with-tools` (`-t`) it also creates `tools.py` and registers it in `migrations/register_tools.py`, which is imported at startup when `mcp_server_enabled = true`. Define MCP tools there with `@mcp.tool()`.

```bash
hackplate dropfeature <name>   # removes the directory and its registry imports
```

## User model

The active user model is set in `pyproject.toml`:

```toml
[tool.hackplate]
auth_user_model = "app.platform.user.models.User"
```

- SQL plates: model must inherit from `AbstractUser` (SQLModel)
- Mongo plate: model must inherit from `AbstractUserDocument` (Beanie Document)

The default `User` lives at `app/platform/user/models.py`. To extend it, create your own model class in `app/`, update `auth_user_model`, and register it in `migrations/register_models.py`.

## Configuration

Two sources, two purposes:

- **`.env`** — deployment-varying values: plate selection, database URLs, OAuth credentials, secret keys.
- **`pyproject.toml` `[tool.hackplate]`** — structural project decisions: active user model, Alembic toggle.

Never put deployment-varying values in `pyproject.toml` or structural decisions in `.env`.

## CLI reference

| Command | Description |
|---|---|
| `hackplate run` | Start uvicorn (`-m dev`\|`prod`, default `dev`; `prod` runs `HACKPLATE_WORKERS` workers, no reload) |
| `hackplate up` | Start full stack via Docker Compose (`-m dev`\|`prod` selects the compose profile) |
| `hackplate init` | First-time repo setup (runs once) |
| `hackplate getplates` | Show active auth and db plates |
| `hackplate setplate auth <plate>` | Switch auth plate |
| `hackplate setplate db <plate>` | Switch db plate |
| `hackplate setmode safe\|fast` | Switch Claude Code operating mode |
| `hackplate getmode` | Show the current Claude Code operating mode |
| `hackplate startfeature <name>` | Scaffold a vertical slice under `app/` (`-t`\|`--with-tools` also adds `tools.py`) |
| `hackplate dropfeature <name>` | Remove a feature directory |
| `hackplate regenkey` | Regenerate `SECRET_KEY` in `.env` |
| `hackplate precommit` | Install and run pre-commit on all files |
| `hackplate clean` | Remove cache and build artifacts |
| `hackplate keycloak up` | Start the standalone Keycloak stack and wait until healthy |
| `hackplate keycloak down` | Stop the standalone Keycloak stack |
| `hackplate keycloak sync` | Sync Keycloak realm config to `settings.json` |
| `hackplate down` | Stop Docker containers |

Run `hackplate --help` for the full reference.

## Migrations

Schema is managed automatically by default (`alembic = false` in `pyproject.toml` — SQLModel creates tables on startup). To switch to Alembic:

```toml
[tool.hackplate.db]
alembic = true
```

```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

## WebSockets

`app/platform/websocket.py` exports `WSConnectionManager` for broadcasting to all connected clients, and `get_db_from_ws` for injecting a database session into WebSocket handlers.

## Stack

- **FastAPI** + **Uvicorn** — async web framework and server
- **SQLModel** / **SQLAlchemy** (async) — ORM and schema management for SQL plates
- **Beanie** — async ODM for MongoDB
- **fastapi-users** — user management primitives
- **Pydantic v2** + **pydantic-settings** — validation and config
- **Alembic** — optional SQL migrations
- **Typer** — CLI framework
- **uv** — dependency and virtual environment management
- **pytest** + **pytest-asyncio** — testing

## For AI agents

Read `CLAUDE.md` (reasoning-friendly, supports `@import`) and `AGENTS.md` (imperative, cross-tool standard) before making changes. The `.claude/settings.json` pre-configures allowed commands and post-edit hooks.

`CLAUDE.md` is yours to edit — it holds nothing but imports: `modes/CLAUDE.hackplate.md` (the framework docs above) and the gitignored `modes/behavior/CLAUDE.mode.md`, which re-exports one of `modes/behavior/CLAUDE.{safe,fast,review}.md`. Switch modes with `hackplate setmode safe|fast|review`; that also copies the matching `modes/settings/settings.<mode>.json` to `.claude/settings.json`. `hackplate init` writes both, defaulting to `safe`.

The single extension pattern: add routes in `app/main.py` via `register_routes()`, inject dependencies from `app/dependencies.py`, and scaffold new slices with `hackplate startfeature`. Don't modify `app/platform/` unless extending a plate interface.
