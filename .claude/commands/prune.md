---
description: Tree-shake Hackplate down to the plates and features actually in use, removing everything else
---

# Prune Hackplate

Tree-shake this project from a general-purpose Hackplate template into a solidified,
single-configuration application. Remove every unused plate, feature toggle, and piece
of swappable infrastructure, leaving only what this project actually runs on.

**This command always runs in two phases. Never skip the approval gate, even in `fast`
mode, even if the user seems in a hurry.** Phase 1 only reads the repo and produces a
plan. Nothing is deleted, edited, or moved until the user explicitly approves that plan
in a follow-up message.

## Phase 1 — Plan (read-only)

### Step 1 — Determine the locked-in configuration

Run `hackplate getplates` and `hackplate getmode`, and read `pyproject.toml
[tool.hackplate]` plus `.env`, to determine:

- `HACKPLATE_DB` (sqlite / postgres / supabase / mongo)
- `HACKPLATE_AUTH` (local / auth0 / keycloak)

### Step 2 — Build the removal plan

Work through the categories below. For each, decide keep/remove and note *why* not just
*what*:

1. **Database plates** (`app/hackplate/plates/db_plates/`) — everything except the
   selected one. Also flags: `database_plates`/`database_plate_list` in
   `app/hackplate/config.py`, the `settings_map` entry in `run_checks()`
   (`app/hackplate/cli/utils.py`), the matching `pyproject.toml` dependency
   (`beanie` / `asyncpg`), and confirms the kept plate's `config.py` still passes
   `class_=AsyncSession` explicitly.

   **If Mongo is locked in, remove Alembic too.** Beanie manages the schema, so Alembic
   serves no purpose. Remove:
   - `alembic.ini` at the repo root
   - the Alembic-only files in `migrations/`: `env.py`, `script.py.mako`, `README`, and
     `versions/` if it exists
   - the `alembic` dependency in `pyproject.toml` (then `uv lock`)
   - the `[tool.hackplate.db] alembic` key and its comment in `pyproject.toml`
   - the `alembic` field on `DatabaseSettings` in `app/hackplate/toml_settings.py`.
     Keep the class itself, because `MongoPlate.__init__` takes it as an argument.
   - Alembic docs: the "Migrations" section and `alembic` commands in
     `modes/CLAUDE.hackplate.md`, plus the Alembic mentions in `README.hackplate.md`

   **Keep the `migrations/` directory and every file there that is used outside
   Alembic.** Before planning to delete any file there, grep for its importers and
   leave it in place if anything other than `migrations/env.py` uses it. Currently that
   means keeping these three:
   - `register_models.py`: `MongoPlate` imports it to register Beanie documents, and
     `startfeature`/`dropfeature` edit it.
   - `register_auth_model.py`: `register_models.py` imports it.
   - `register_tools.py`: `app/hackplate/lifespan.py` imports it, and the feature
     commands edit it.

   Don't rename or move `migrations/`; `feature.py` and `lifespan.py` hardcode that
   path.
2. **Auth plates** (`app/hackplate/plates/auth_plates/`) — same pattern. If Keycloak is
   being removed, this includes `app/hackplate/cli/keycloak.py`, the `ensure_keycloak()`
   calls in `app/hackplate/cli/start.py`, the `docker-compose.keycloak.yml` +
   `settings.json`, and the `KEYCLOAK_*` block plus `keycloak:host-gateway` entries.
3. **CLI commands** (`app/hackplate/cli/`) — once the configuration is locked in, any
   command that exists to switch, scaffold for, or manage a removed plate is dead
   weight. Read every module registered in `cli/cli.py` and decide per command:
   - **`plate.py`** (`getplates`, `setplate`) — remove the module and its `add_typer`
     line in `cli/cli.py`. There is only one valid value per plate type now, so there is
     nothing to switch or inspect.
   - **`keycloak.py`** — if Keycloak is removed, delete the module, its
     `add_typer(keycloak.app, name="keycloak")` line, the `ensure_keycloak` import and
     calls in `start.py`, and the "Keycloak runs separately" echo in `down()`. If
     Keycloak is kept, keep the module intact.
   - **`utils.py` `init`** — drop the `_prompt_plate` prompts and the
     `database_plate_list`/`auth_plate_list` import; write the locked-in
     `HACKPLATE_AUTH`/`HACKPLATE_DB` values directly (or drop those keys entirely if the
     config surface step removes them). Remove `_warn_if_docker_missing` unless Keycloak
     is kept. Remove `SECRET_KEY` generation only if nothing outside the removed plates
     reads it — check `app/hackplate/user/managers.py`, which reads `LocalAuthSettings`
     directly.
   - **`utils.py` `regenkey`** — same rule as `SECRET_KEY` above: keep it while
     anything still reads `SECRET_KEY`.
   - **`utils.py` `run_checks()`** — besides trimming `settings_map` (category 1/2),
     remove the lazy imports of removed plates' settings classes; they'd raise
     `ImportError` once the plate directories are gone.
   - **`feature.py`** — `_models_stub()` picks `SQL_MODELS_STUB` or `MONGO_MODELS_STUB`
     based on `HACKPLATE_DB`. Keep only the kept plate's stub constant and have
     `startfeature` write it directly, removing `_models_stub()` and its `.env` read. If
     MCP is removed, drop `--with-tools`, `TOOLS_STUB`, and the `"tools"` entry in
     `REGISTRIES`.
   - **Keep**: `run`, `up`, `down`, `check`, `clean`, `precommit`, `startfeature`,
     `dropfeature`, `getmode`/`setmode` — these don't depend on which plate is active.
     Don't touch `mode.py`; operating modes are a Claude Code concern, not framework
     surface.

   Also update the command table in `modes/CLAUDE.hackplate.md` and any CLI reference in
   `README.hackplate.md` to match the surviving command set.

### Step 3 — Present the plan and stop

Output a clear, itemized list: files to delete, files to edit (with what changes),
dependencies to drop. Group by category (db plates / auth plates / CLI / infra / MCP /
config surface). End with something like:

> This plan deletes N files and edits M files. Nothing has been touched yet — reply
> with "approved" (or tell me what to adjust) before I make any changes.

**Then stop. Do not call Edit, Write, Bash(rm...), or any other mutating tool in this
turn.** If the user's original message already contains something equivalent to
approval for the full plan, still show the plan first and wait for a separate
confirming reply — the plan is the first time the actual file list exists, so approval
of "the general idea" earlier in the conversation doesn't cover it.

## Phase 2 — Execute (only after explicit approval)

Only enter this phase once the user has replied approving the plan (either as-is or
with adjustments you've incorporated and re-confirmed if the adjustments were
substantial).

- Execute exactly the approved plan — same category order as Step 2 (db → auth →
  CLI → infra → MCP → config surface)
- If reality has drifted since Phase 1 (files already gone, unexpected content), stop
  and flag the discrepancy rather than improvising past it
- After execution, run verification:
  - `hackplate check`
  - `hackplate --help` — confirm it loads and lists only the commands kept in the plan
  - `hackplate run` (confirm clean boot, then stop it)
  - `uv run pytest`, if a test suite exists
  - grep for leftover references to removed plate names, env var prefixes, and
    dependency imports (including `alembic`, if it was removed) across the repo, including `README.hackplate.md` and
    `modes/CLAUDE.hackplate.md`
- Summarize what was actually removed/edited, and separately call out anything you
  noticed but left alone (e.g. Keycloak's network-reachability assumptions, if kept)
