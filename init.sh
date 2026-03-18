#!/usr/bin/env bash
set -euo pipefail

# ─── mv_hofki optional setup ───
# Adds optional modules and configures git remote.
# Renaming is handled automatically by .devcontainer/initialize.sh on first startup.
#
# Usage:
#   Interactive:  ./init.sh
#   Headless:     ./init.sh [OPTIONS]
#
# Options:
#   --jobs               Include job queue module (SSE progress streaming)
#   --no-jobs            Skip job queue module
#   --git local          Local git repo only
#   --git remote         Push to Azure DevOps remote
#   --devops-url URL     Azure DevOps collection URL (required with --git remote)
#   --devops-project P   Azure DevOps project name (required with --git remote)
#   --repo-name NAME     Repository name on remote (defaults to project name)
#   --help               Show this help

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[init]${NC} $*"; }
warn()  { echo -e "${YELLOW}[init]${NC} $*"; }
error() { echo -e "${RED}[init]${NC} $*" >&2; exit 1; }

# ── Parse arguments ───────────────────────────────────────────────────────

INCLUDE_JOBS=""
GIT_MODE=""
DEVOPS_URL=""
DEVOPS_PROJECT=""
REPO_NAME=""

show_help() {
  sed -n '/^# Usage:/,/^#   --help/p' "$0" | sed 's/^# \?//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobs)       INCLUDE_JOBS="y"; shift ;;
    --no-jobs)    INCLUDE_JOBS="n"; shift ;;
    --git)        GIT_MODE="$2"; shift 2 ;;
    --devops-url) DEVOPS_URL="$2"; shift 2 ;;
    --devops-project) DEVOPS_PROJECT="$2"; shift 2 ;;
    --repo-name)  REPO_NAME="$2"; shift 2 ;;
    --help|-h)    show_help ;;
    -*)           error "Unknown option: $1. Use --help for usage." ;;
    *)            error "Unexpected argument: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Derive project/package name from folder ───────────────────────────────

PROJECT_NAME="$(basename "$SCRIPT_DIR")"
PACKAGE_NAME="${PROJECT_NAME//-/_}"

# ── Check renaming was done ───────────────────────────────────────────────

if [[ -d "$SCRIPT_DIR/src/backend/app" ]]; then
  error "Project has not been renamed yet. Run the devcontainer first (initialize.sh handles renaming) or rename manually."
fi

info "Project: $PROJECT_NAME (package: $PACKAGE_NAME)"

# ── Prompt for missing values ─────────────────────────────────────────────

if [[ -z "$INCLUDE_JOBS" ]]; then
  read -rp "Include job queue module (SSE progress streaming)? (y/n) " INCLUDE_JOBS
fi

if [[ -z "$GIT_MODE" ]]; then
  echo ""
  info "Git setup:"
  echo "  local)  Initialize new repo, no remote"
  echo "  remote) Initialize and push to Azure DevOps"
  echo "  skip)   Don't touch git"
  read -rp "Choose (local/remote/skip): " GIT_MODE
fi

if [[ "$GIT_MODE" == "remote" ]]; then
  if [[ -z "$DEVOPS_URL" ]]; then
    read -rp "Azure DevOps collection URL (e.g., https://server/DefaultCollection): " DEVOPS_URL
  fi
  if [[ -z "$DEVOPS_PROJECT" ]]; then
    read -rp "Azure DevOps project name: " DEVOPS_PROJECT
  fi
  if [[ -z "$REPO_NAME" ]]; then
    read -rp "Repository name [${PROJECT_NAME}]: " REPO_NAME
  fi
  REPO_NAME="${REPO_NAME:-$PROJECT_NAME}"
  DEVOPS_URL="${DEVOPS_URL%/}"
fi

# ── Optional: job queue module ─────────────────────────────────────────────

if [[ "$INCLUDE_JOBS" =~ ^[yY]$ ]]; then
  if [[ -d "$SCRIPT_DIR/optional/job-queue" ]]; then
    info "Integrating job queue module..."

    cp "$SCRIPT_DIR/optional/job-queue/backend/jobs.py" \
       "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/"
    mkdir -p "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/api/routes"
    cp "$SCRIPT_DIR/optional/job-queue/backend/routes/jobs.py" \
       "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/api/routes/jobs.py"
    mkdir -p "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/services"
    cp "$SCRIPT_DIR/optional/job-queue/backend/services/example_worker.py" \
       "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/services/"

    for f in "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/jobs.py" \
             "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/api/routes/jobs.py" \
             "$SCRIPT_DIR/src/backend/$PACKAGE_NAME/services/example_worker.py"; do
      sed -i "s/from app\./from ${PACKAGE_NAME}./g" "$f"
      sed -i "s/import app\./import ${PACKAGE_NAME}./g" "$f"
    done

    mkdir -p "$SCRIPT_DIR/src/frontend/src/components"
    cp "$SCRIPT_DIR/optional/job-queue/frontend/components/JobProgress.vue" \
       "$SCRIPT_DIR/src/frontend/src/components/"
    mkdir -p "$SCRIPT_DIR/src/frontend/src/lib"
    cp "$SCRIPT_DIR/optional/job-queue/frontend/lib/sse.js" \
       "$SCRIPT_DIR/src/frontend/src/lib/"

    APP_PY="$SCRIPT_DIR/src/backend/$PACKAGE_NAME/api/app.py"
    sed -i "/^from.*routes\.health/a from ${PACKAGE_NAME}.api.routes.jobs import router as jobs_router" "$APP_PY"
    sed -i "/app.include_router(health_router)/a app.include_router(jobs_router, prefix=\"/api/v1\")" "$APP_PY"

    info "Job queue module integrated."
  else
    warn "optional/job-queue/ not found — already integrated or removed."
  fi
else
  info "Skipping job queue module."
fi

# ── Clean up optional dir ─────────────────────────────────────────────────

if [[ -d "$SCRIPT_DIR/optional" ]]; then
  info "Cleaning up optional modules..."
  rm -rf "$SCRIPT_DIR/optional"
fi

# ── Git setup ──────────────────────────────────────────────────────────────

if [[ "$GIT_MODE" == "remote" ]]; then
  info "Checking connectivity to Azure DevOps..."

  if ! curl -sf --connect-timeout 5 -o /dev/null "${DEVOPS_URL}/_apis/connectionData?api-version=7.0" 2>/dev/null; then
    http_code=$(curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" "${DEVOPS_URL}" 2>/dev/null || echo "000")
    if [[ "$http_code" == "000" ]]; then
      error "Cannot reach Azure DevOps server at '${DEVOPS_URL}'.
  Possible causes:
    - Server URL is wrong or has a typo
    - Server is down or unreachable from this network/container
    - DNS cannot resolve the hostname
  If running inside a devcontainer, check that the container has network access
  to your on-premise server."
    elif [[ "$http_code" == "401" || "$http_code" == "403" ]]; then
      error "Azure DevOps server is reachable but authentication failed (HTTP ${http_code}).
  Possible causes:
    - Git credentials are not configured in this environment
    - If running inside a devcontainer, credentials from the host may not be forwarded"
    else
      warn "Azure DevOps returned HTTP ${http_code} — proceeding, but push may fail."
    fi
  else
    info "Azure DevOps server is reachable."
  fi

  if ! curl -sf --connect-timeout 5 -u ":" --negotiate \
    "${DEVOPS_URL}/${DEVOPS_PROJECT}/_apis/projects/${DEVOPS_PROJECT}?api-version=7.0" \
    &>/dev/null 2>&1; then
    warn "Could not verify project '${DEVOPS_PROJECT}' — it may not exist or credentials may lack access."
  fi
fi

if [[ "$GIT_MODE" == "local" || "$GIT_MODE" == "remote" ]]; then
  rm -rf "$SCRIPT_DIR/.git"
  cd "$SCRIPT_DIR"
  git init
  git add .

  if [[ "$GIT_MODE" == "remote" ]]; then
    remote_url="${DEVOPS_URL}/${DEVOPS_PROJECT}/_git/${REPO_NAME}"

    info "Creating repository '${REPO_NAME}' in project '${DEVOPS_PROJECT}'..."
    curl -sf -u ":" --negotiate \
      -X POST "${DEVOPS_URL}/${DEVOPS_PROJECT}/_apis/git/repositories?api-version=7.0" \
      -H "Content-Type: application/json" \
      -d "{\"name\": \"${REPO_NAME}\"}" &>/dev/null && {
      info "Repository created on Azure DevOps."
    } || {
      if curl -sf -u ":" --negotiate \
        "${DEVOPS_URL}/${DEVOPS_PROJECT}/_apis/git/repositories/${REPO_NAME}?api-version=7.0" \
        &>/dev/null; then
        info "Repository '${REPO_NAME}' already exists — using it."
      else
        warn "Could not create repository via API. Attempting push anyway..."
      fi
    }

    git commit -m "Initial project '${PROJECT_NAME}' from mv_hofki"
    git branch -M main
    git remote add origin "$remote_url"
    if ! git push -u origin main 2>&1; then
      error "Push to '${remote_url}' failed.
  The project has been initialized locally. You can push manually later:
    git remote add origin ${remote_url}
    git push -u origin main"
    fi
    info "Pushed to $remote_url"
  else
    git commit -m "Initial project '${PROJECT_NAME}' from mv_hofki"
    git branch -M main
    info "Local git repo initialized."
  fi
fi

# ── Pre-commit ─────────────────────────────────────────────────────────────

if command -v pre-commit &>/dev/null; then
  pre-commit install
  info "Pre-commit hooks installed."
fi

# ── Devcontainer: reinstall and restart services ───────────────────────

if [[ "${DEVCONTAINER:-}" == "true" ]]; then
  info "Reinstalling and restarting services..."

  cd "$SCRIPT_DIR"
  pip install -e '.[dev]' --quiet

  cd "$SCRIPT_DIR/src/frontend"
  npm install --silent
  VITE_BASE_PATH="${VITE_BASE_PATH:-/}" npx vite build

  cd "$SCRIPT_DIR"
  tmux kill-session -t server 2>/dev/null || true
  tmux kill-session -t frontend 2>/dev/null || true
  tmux new-session -d -s server \
    "cd $SCRIPT_DIR && PYTHONPATH=src/backend uvicorn ${PACKAGE_NAME}.api.app:app --host 0.0.0.0 --port 8000 --reload"
  tmux new-session -d -s frontend \
    "cd $SCRIPT_DIR/src/frontend && VITE_BASE_PATH=\${VITE_BASE_PATH:-/} npx vite build --watch"

  info "Backend and frontend restarted."
fi

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Project '$PROJECT_NAME' setup complete!"
echo ""
echo "  Package:    src/backend/$PACKAGE_NAME/"
echo "  Frontend:   src/frontend/"
echo "  Tests:      tests/backend/, tests/frontend/, e2e/"
[[ "$INCLUDE_JOBS" =~ ^[yY]$ ]] && echo "  Job queue:  included"
[[ "$GIT_MODE" == "skip" ]] && echo "  Git:        unchanged"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
