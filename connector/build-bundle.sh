#!/usr/bin/env bash
# Package the Yildun desktop connector as an MCP bundle (.mcpb) an org admin can add to the
# desktop-extension allowlist, or a writer can double-click to install. Standard library only, so
# the bundle needs nothing but python3 on the writer's machine.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/yildun/tools"
cp "$HERE/bundle/manifest.json" "$STAGE/yildun/manifest.json"
cp "$HERE/server.py" "$STAGE/yildun/server.py"
cp "$HERE/PROJECT.md" "$STAGE/yildun/PROJECT.md"
# the gates the connector shells out to, minus caches and the vendored copy of voicelint
rsync -a --exclude '__pycache__' --exclude '*.VENDOR' --exclude '.pytest_cache' "$ROOT/tools/" "$STAGE/yildun/tools/"
OUT="$HERE/yildun.mcpb"
rm -f "$OUT"
( cd "$STAGE/yildun" && zip -qr "$OUT" . -x '*.DS_Store' )
echo "Built $OUT"
unzip -l "$OUT" | tail -1
