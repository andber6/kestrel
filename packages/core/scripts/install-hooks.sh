#!/bin/sh
# Install git pre-commit hook for auto-formatting and linting.
# Run this once after cloning: ./scripts/install-hooks.sh

HOOK_PATH="$(git rev-parse --show-toplevel)/.git/hooks/pre-commit"

cat > "$HOOK_PATH" << 'EOF'
#!/bin/sh
cd packages/core || exit 0

uv run ruff format src/ tests/ 2>/dev/null
uv run ruff check --fix src/ tests/ 2>/dev/null

git diff --name-only | xargs -r git add

uv run ruff check src/ tests/
EOF

chmod +x "$HOOK_PATH"
echo "Pre-commit hook installed."
