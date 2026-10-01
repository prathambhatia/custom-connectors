#!/usr/bin/env bash
# Installs the custom-connectors skills into ~/.claude/skills (no plugin system needed).
set -euo pipefail
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl -fsSL https://github.com/prathambhatia/custom-connectors/archive/refs/heads/main.tar.gz | tar -xz -C "$tmp"
src="$tmp/custom-connectors-main/plugins/custom-connectors/skills"
mkdir -p "$HOME/.claude/skills"
for d in "$src"/*/; do
  name=$(basename "$d")
  if [ -e "$HOME/.claude/skills/$name" ]; then echo "skipped $name (already exists, remove it to reinstall)"; continue; fi
  cp -R "$d" "$HOME/.claude/skills/$name" && echo "installed $name"
done
command -v jq >/dev/null || echo "note: jq is missing, run: brew install jq"
echo "Done. Start a new Claude Code session, then disable the Slack, Fathom, ClickUp, Vercel, AWS and chrome-devtools MCPs with /mcp."
