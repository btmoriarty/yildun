#!/usr/bin/env bash
# Package the Yildun desktop connector as an MCP bundle (.mcpb).
#
# The build is REPRODUCIBLE: entries are sorted and every timestamp is fixed, so the same source
# always produces byte-identical output. That matters because an organization's desktop-extension
# allowlist permits a specific artifact; a writer must install the same bytes the admin allowlisted,
# not a rebuild that happens to differ. Verify with: shasum -a 256 yildun.mcpb
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="$HERE/yildun.mcpb"
python3 - "$HERE" "$ROOT" "$OUT" <<'PY'
import os, sys, zipfile
here, root, out = sys.argv[1:4]
FIXED = (2026, 1, 1, 0, 0, 0)          # every entry, same stamp
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDE_EXT = {".VENDOR", ".pyc"}
files = [("manifest.json", os.path.join(here, "bundle", "manifest.json")),
         ("server.py",     os.path.join(here, "server.py")),
         ("PROJECT.md",    os.path.join(here, "PROJECT.md"))]
tools = os.path.join(root, "tools")
for dirpath, dirnames, filenames in os.walk(tools):
    dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
    for fn in sorted(filenames):
        if fn == ".DS_Store" or os.path.splitext(fn)[1] in EXCLUDE_EXT:
            continue
        full = os.path.join(dirpath, fn)
        files.append((os.path.join("tools", os.path.relpath(full, tools)), full))
files.sort(key=lambda p: p[0])
if os.path.exists(out):
    os.remove(out)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for arc, full in files:
        zi = zipfile.ZipInfo(arc, date_time=FIXED)
        zi.external_attr = 0o644 << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        with open(full, "rb") as fh:
            z.writestr(zi, fh.read())
print(f"Built {out} ({len(files)} files)")
PY
