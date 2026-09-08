#!/usr/bin/env bash
# sync-voicelint.sh - re-vendor pherkad's voicelint, or verify this copy has not drifted.
#
# the saga does not own voice rules. Pherkad does. This script is the only sanctioned way for
# tools/voicelint.py to change, and --check is what makes an unsanctioned change visible.
#
#   sync-voicelint.sh            copy from pherkad and rewrite the VENDOR record
#   sync-voicelint.sh --check    exit 1 if the vendored copy differs from its recorded sha256
set -uo pipefail
# The voice SSoT is pherkad. Public users set PHERKAD_VOICELINT to their checkout's voicelint.py.
SRC="${PHERKAD_VOICELINT:-}"
HERE=$(cd "$(dirname "$0")/.." && pwd)
DST="$HERE/tools/voicelint.py"
REC="$HERE/tools/voicelint.VENDOR"

if [ "${1:-}" = "--check" ]; then
    want=$(grep '^sha256' "$REC" 2>/dev/null | awk '{print $2}')
    have=$(shasum -a 256 "$DST" 2>/dev/null | awk '{print $1}')
    if [ -z "$want" ] || [ -z "$have" ]; then echo "sync-voicelint: cannot verify"; exit 2; fi
    if [ "$want" = "$have" ]; then echo "sync-voicelint: vendored copy matches its record"; exit 0; fi
    echo "sync-voicelint: DRIFTED. tools/voicelint.py was edited here instead of in pherkad."
    echo "  recorded $want"
    echo "  actual   $have"
    exit 1
fi

[ -f "$SRC" ] || { echo "sync-voicelint: set PHERKAD_VOICELINT to your pherkad checkout skills/pherkad/tools/voicelint.py (pherkad is public at github.com/btmoriarty/pherkad)"; exit 2; }
cp "$SRC" "$DST"
sha=$(shasum -a 256 "$DST" | awk '{print $1}')
commit=$(git -C "$(dirname "$SRC")" log -1 --format='%h  (%ad)' --date=short -- "$SRC" 2>/dev/null)
printf 'tools/voicelint.py is VENDORED, NOT FORKED. Do not edit it here.\n\nsource   %s\ncommit   %s\nvendored %s\nsha256   %s\n' \
    "$SRC" "${commit:-unknown}" "$(date +%Y-%m-%d)" "$sha" > "$REC.new"
sed -n '/^Pherkad is the single source/,$p' "$REC" >> "$REC.new" 2>/dev/null
printf '\n' >> "$REC.new"; mv "$REC.new" "$REC"
echo "sync-voicelint: vendored $(wc -l < "$DST" | tr -d ' ') lines, sha256 $sha"
