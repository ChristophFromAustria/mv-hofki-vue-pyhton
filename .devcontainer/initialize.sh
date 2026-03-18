#!/usr/bin/env bash
# Runs on the HOST before the container is built.
# Uses the folder name as the project name and renames all template references.
set -euo pipefail

PROJECT_NAME=$(basename "$PWD")

# ── Block if folder not renamed from template ─────────────────────────────

if [ "$PROJECT_NAME" = "fullstack-fastapi-vue" ]; then
  echo ""
  echo "ERROR: Rename the project folder before starting the devcontainer."
  echo "Clone with a custom name: git clone <template-url> my-project-name"
  echo "Or rename: mv fullstack-fastapi-vue my-project-name"
  echo ""
  exit 1
fi

# ── Skip if already renamed ───────────────────────────────────────────────

if [ ! -d "src/backend/app" ]; then
  echo "[init] Already renamed — skipping."
  exit 0
fi

# ── Validate project name ─────────────────────────────────────────────────

if ! echo "$PROJECT_NAME" | grep -qE '^[a-z][a-z0-9_-]*$'; then
  echo ""
  echo "ERROR: Folder name '$PROJECT_NAME' is not a valid project name."
  echo "Use only lowercase letters, numbers, hyphens, and underscores."
  echo "Rename the folder and try again."
  echo ""
  exit 1
fi

PACKAGE_NAME=$(echo "$PROJECT_NAME" | tr '-' '_')

echo "[init] Project name: $PROJECT_NAME"
echo "[init] Package name: $PACKAGE_NAME"

# ── Rename Python package ─────────────────────────────────────────────────

echo "[init] Renaming src/backend/app/ → src/backend/$PACKAGE_NAME/"
mv "src/backend/app" "src/backend/$PACKAGE_NAME"

# ── Find & replace across all files ───────────────────────────────────────

echo "[init] Replacing references across project files..."

find . \
  -type f \
  ! -path '*/.git/*' \
  ! -path '*/node_modules/*' \
  ! -path '*/__pycache__/*' \
  ! -path '*/dist/*' \
  \( -name '*.py' -o -name '*.toml' -o -name '*.json' -o -name '*.js' \
     -o -name '*.vue' -o -name '*.yaml' -o -name '*.yml' -o -name '*.md' \
     -o -name '*.sh' -o -name '*.html' -o -name '*.css' -o -name '*.env*' \
     -o -name 'Dockerfile' -o -name '.eslintrc.cjs' -o -name '.prettierrc' \) \
  | while IFS= read -r file; do

  # Replace Python imports (only in .py and .toml files)
  case "$file" in
    *.py|*.toml)
      sed -i "s/from app\./from ${PACKAGE_NAME}./g" "$file"
      sed -i "s/import app\./import ${PACKAGE_NAME}./g" "$file"
      sed -i "s/\"app\"/\"${PACKAGE_NAME}\"/g" "$file"
      sed -i "s/packages = \[\"app\"\]/packages = [\"${PACKAGE_NAME}\"]/g" "$file"
      ;;
  esac

  # Replace mv_hofki → project name
  sed -i "s/mv_hofki/${PROJECT_NAME}/g" "$file"
  sed -i "s/mv_hofki/${PROJECT_NAME}/g" "$file"

  # Replace app-frontend in package.json
  case "$file" in
    *package.json)
      sed -i "s/app-frontend/${PROJECT_NAME}-frontend/g" "$file"
      ;;
  esac

  # Replace uvicorn mv_hofki.api.app:app → <package>.api.app:app
  sed -i "s/app\.api\.app:app/${PACKAGE_NAME}.api.app:app/g" "$file"

  # Replace APP_NAME in env files
  case "$file" in
    *.env*)
      sed -i "s/APP_NAME=mv_hofki/APP_NAME=${PROJECT_NAME}/g" "$file"
      ;;
  esac
done

echo "[init] References updated."

# ── Create marker ─────────────────────────────────────────────────────────

echo "Renamed from mv_hofki to ${PROJECT_NAME} on $(date -Iseconds)" > .initialized

echo "[init] Done. Project '$PROJECT_NAME' is ready for container build."
