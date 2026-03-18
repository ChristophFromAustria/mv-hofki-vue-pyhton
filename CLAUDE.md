# CLAUDE.md

This file provides guidance to Claude Code when working with this project.

## First-Time Setup

Project renaming is handled automatically by `.devcontainer/initialize.sh` when the
devcontainer first starts — the folder name becomes the project name. No manual renaming needed.

If `optional/` still exists, `init.sh` can be run for additional setup. Ask the user:
   - **Include job queue module?** (yes/no) — SSE progress streaming for background tasks
   - **Git setup** — `local`, `remote` (Azure DevOps), or `skip`
   - If remote: **DevOps collection URL**, **DevOps project name**, **repository name**

Run init.sh with ALL parameters as flags (the script must run non-interactively):
```bash
# Example: local git, no job queue
./init.sh --no-jobs --git local

# Example: with job queue + Azure DevOps remote
./init.sh --jobs --git remote \
  --devops-url https://server/DefaultCollection \
  --devops-project MyTeamProject \
  --repo-name my-project

# Example: just add job queue, don't touch git
./init.sh --jobs --git skip
```

IMPORTANT: Always pass ALL options as flags. Do NOT run init.sh without flags — it will
prompt interactively which does not work in this environment. Collect all answers from
the user first, then run the script once with all flags.

If neither job queue nor git remote setup is needed, init.sh can be skipped entirely.

## Project Overview

**mv_hofki** — Full-stack web application template using FastAPI (backend) and Vue 3 (frontend).

## Commands

```bash
# Backend server: auto-started in tmux session "server"
server-logs                    # View last 500 lines of server output
server-attach                  # Attach to server tmux session (Ctrl+B, D to detach)
server-restart                 # Restart uvicorn

# Frontend watcher: auto-started in tmux session "frontend"
frontend-logs                  # View last 500 lines of frontend watcher output
frontend-attach                # Attach to frontend tmux session
frontend-restart               # Restart vite build --watch

# Tests
python -m pytest tests/backend/ -v                        # Backend tests
cd src/frontend && npx vitest run                         # Frontend tests
cd e2e && npx playwright test                             # E2E tests

# Lint
pre-commit run --all-files     # Run all linters
```

## Architecture

- **Backend:** FastAPI at `src/backend/app/` — routes, services, models, core config
- **Frontend:** Vue 3 at `src/frontend/` — pages, components, lib, Vue Router
- **Dev workflow:** uvicorn `--reload` serves `frontend/dist/`. `vite build --watch` auto-rebuilds the frontend. Backend changes auto-restart the server. Frontend changes auto-rebuild — refresh the browser manually.
- Both processes are auto-started in the devcontainer via tmux.
- **Path-based routing:** Set `BASE_PATH` and `VITE_BASE_PATH` in `.env` for sub-path deployment (e.g., `/newWebApp`). Default is `/`.

## Authentication & Authorization

No built-in authentication. Access is secured externally via Cloudflare Tunnel.

## Infrastructure

- **Database:** SQLite at `data/mv_hofki.db`, managed via SQLAlchemy 2.0 async (aiosqlite) + Alembic
- **Migrations:** `PYTHONPATH=src/backend alembic upgrade head`
- **Seed data:** Instrument types (20) and currencies (4) are seeded on app startup if tables are empty

## API Conventions

- All routes under `/api/v1/`
- Health check: `GET /health`
<!-- Fill in: error response format, pagination, etc. -->

## Dev Workflow Note for Claude

When making frontend changes, the `vite build --watch` process in the `frontend` tmux session will automatically rebuild `src/frontend/dist/`. The backend serves this directory as static files. There is no need to restart the server for frontend changes — just ensure the frontend tmux session is running (`frontend-logs` to check).

When making backend changes, uvicorn `--reload` will automatically restart. Check `server-logs` if something seems wrong.

Always run `pre-commit run --all-files` before committing to ensure code quality.
