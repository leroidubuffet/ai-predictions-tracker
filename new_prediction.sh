#!/usr/bin/env bash
# Usage: ./new_prediction.sh "Source Name"
# Creates a new prediction file, opens it in $EDITOR, validates it, and commits.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PREDICTIONS_DIR="$REPO_ROOT/predictions"
TEMPLATE="$REPO_ROOT/template.yaml"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

# ── Argument ────────────────────────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"Source Name\""
  echo "Example: $0 \"Sam Altman\""
  exit 1
fi

SOURCE_NAME="$1"

# ── Slugify ──────────────────────────────────────────────────────────────────
# Lowercase, replace spaces and non-alphanumeric with hyphens, collapse runs

slug() {
  echo "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9]/-/g' \
    | sed 's/-\{2,\}/-/g' \
    | sed 's/^-//;s/-$//'
}

TODAY="$(date +%Y-%m-%d)"
SLUG="$(slug "$SOURCE_NAME")"
FILENAME="${TODAY}-${SLUG}.yaml"
DEST="$PREDICTIONS_DIR/$FILENAME"

# ── Guard against overwrite ──────────────────────────────────────────────────

if [[ -f "$DEST" ]]; then
  echo "ERROR: $FILENAME already exists. Choose a different source name or rename manually."
  exit 1
fi

# ── Copy template and pre-fill date ─────────────────────────────────────────

cp "$TEMPLATE" "$DEST"
# Replace the placeholder date with today
if [[ "$(uname)" == "Darwin" ]]; then
  sed -i '' "s/prediction_date: YYYY-MM-DD/prediction_date: $TODAY/" "$DEST"
else
  sed -i "s/prediction_date: YYYY-MM-DD/prediction_date: $TODAY/" "$DEST"
fi

echo "Created $FILENAME"
echo "Opening in ${EDITOR:-vi}..."

# ── Open editor ──────────────────────────────────────────────────────────────

${EDITOR:-vi} "$DEST"

# ── Validate ─────────────────────────────────────────────────────────────────

echo ""
echo "Validating..."

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "ERROR: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  rm "$DEST"
  exit 1
fi

if ! "$VENV_PYTHON" "$REPO_ROOT/scripts/validate.py" "$DEST"; then
  echo ""
  echo "Validation failed. Fix the errors above and re-run, or edit the file manually:"
  echo "  $DEST"
  echo ""
  echo "To discard: rm $DEST"
  exit 1
fi

# ── Commit ───────────────────────────────────────────────────────────────────

echo ""
echo "Validation passed. Staging and committing..."

git -C "$REPO_ROOT" add "$DEST"
git -C "$REPO_ROOT" commit -m "Add prediction: $SOURCE_NAME ($TODAY)"

echo ""
echo "Done. Prediction committed: $FILENAME"
