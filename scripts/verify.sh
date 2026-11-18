#!/bin/bash
# Build the site the way the deploy does, check every internal link, and confirm that
# drafts stay out of the published output. Run from the repository root.
set -euo pipefail

BASE_URL="https://hamseabd.github.io/"
PYTHON="${PYTHON:-python3.12}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

hugo --minify --quiet --destination "$OUT/site"
"$PYTHON" scripts/check_links.py "$OUT/site" "$BASE_URL"

hugo --minify --quiet --buildDrafts --destination "$OUT/drafts"
"$PYTHON" scripts/check_links.py "$OUT/drafts" "$BASE_URL"

drafts=$(hugo list drafts | tail -n +2 | cut -d, -f1)
for source in $drafts; do
  slug="$(basename "$source" .md)"
  if grep -rlF "/$slug/" "$OUT/site" >/dev/null; then
    echo "draft leaked into the published build: $slug" >&2
    exit 1
  fi
done
echo "published build has no draft: $(echo "$drafts" | wc -w | tr -d ' ') draft(s) held back"
