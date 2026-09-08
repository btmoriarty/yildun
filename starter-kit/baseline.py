#!/usr/bin/env python3
"""Measure a story bible: axis distribution, lineage, and structural gaps.

No dependencies. Run from anywhere:

    python3 baseline.py /absolute/path/to/bible-root

Reports:
  * distribution across the rotation axes (rotation is measured, not felt)
  * ORPHANS: entries whose derives_from chain does not reach a human root
  * broken [[links]] and entries missing required sections

The orphan check enforces the root rule: every entry must trace, through however
many hops, to something a human supplied. Roots are `capture:<id>` and `law:<name>`.
Distance from a root is never a problem. Rootlessness is.
"""

import os
import re
import sys
from collections import Counter, defaultdict

# --- configure for your world -------------------------------------------------
AXES = ["lanes", "generation", "region", "type"]
REQUIRED_SECTIONS = ["## Connections", "## Deepen-me"]
SECTIONS_BY_TYPE = {"vignette": ["## Provenance"]}
SCAN_DIRS = ["canon"]          # directories under the root holding entries
ROOT_PREFIXES = ("capture:", "law:")
# ------------------------------------------------------------------------------

FM = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
LINK = re.compile(r"\[\[([^\]|#]+)")


def parse_front_matter(text):
    m = FM.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        line = line.split(" #")[0].rstrip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip("\"'") for v in val[1:-1].split(",")]
            out[key] = [v for v in items if v]
        else:
            out[key] = val.strip("\"'")
    return out


def load(root):
    entries = {}
    for scan in SCAN_DIRS:
        base = os.path.join(root, scan)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fn in sorted(filenames):
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                slug = fn[:-3]
                entries[slug] = {
                    "path": os.path.relpath(path, root),
                    "fm": parse_front_matter(text),
                    "text": text,
                }
    return entries


def resolve_root(slug, entries, seen=None):
    """True if slug's derives_from chain reaches a human root."""
    seen = seen or set()
    if slug in seen:
        return False                      # cycle: not a root
    seen = seen | {slug}
    entry = entries.get(slug, {})
    if entry.get("fm", {}).get("type") == "law":
        return True                       # the author wrote it; it IS a root
    parents = entry.get("fm", {}).get("derives_from") or []
    if isinstance(parents, str):
        parents = [parents]
    if not parents:
        return False
    for p in parents:
        if p.startswith(ROOT_PREFIXES):
            return True
        if p in entries and resolve_root(p, entries, seen):
            return True
    return False


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")

    if not os.path.isdir(root):
        sys.exit(f"error: no such directory: {root}")

    entries = load(root)

    if not entries:
        # An empty bible is a normal state, not a failure. It is where every
        # world starts and where it should stay until the interrogation has run.
        missing = [d for d in SCAN_DIRS if not os.path.isdir(os.path.join(root, d))]
        print(f"BIBLE  {root}\nENTRIES  0\n")
        print("  Nothing to measure yet, which is the correct state for a new world.")
        if missing:
            print(f"  Not created yet: {', '.join(missing + [''])[:-2]}/")
        print("\n  Next: run the `seed` mode and follow references/INTERROGATION.md.")
        print("  Capture first. Do not generate entries until a cross-section of real")
        print("  material exists, or the world will transpose the same few memories")
        print("  forever.\n")
        print("=" * 62)
        print("HEADLINE  entries=0  orphans=0  dangling=0")
        print("=" * 62)
        return

    print(f"BIBLE  {root}\nENTRIES  {len(entries)}\n")

    print("--- ROTATION AXES " + "-" * 44)
    for axis in AXES:
        counts = Counter()
        missing = 0
        for e in entries.values():
            val = e["fm"].get(axis)
            if val is None:
                missing += 1
            elif isinstance(val, list):
                counts.update(str(v) for v in val)
            else:
                counts[str(val)] = counts[str(val)] + 1
        total = sum(counts.values()) or 1
        print(f"\n  {axis}  (missing on {missing})")
        for key, n in counts.most_common():
            bar = "#" * max(1, round(40 * n / total))
            print(f"    {key:<20} {n:>4}  {100*n/total:5.1f}%  {bar}")

    print("\n--- LINEAGE " + "-" * 50)
    orphans = [s for s in entries if not resolve_root(s, entries)]
    no_field = [s for s in orphans if not entries[s]["fm"].get("derives_from")]
    unrooted = [s for s in orphans if s not in no_field]
    print(f"  rooted   {len(entries) - len(orphans)}")
    print(f"  ORPHANS  {len(orphans)}   (no derives_from: {len(no_field)}, "
          f"chain never reaches a root: {len(unrooted)})")
    for s in orphans[:25]:
        print(f"    ! {entries[s]['path']}")
    if len(orphans) > 25:
        print(f"    ... and {len(orphans) - 25} more")

    print("\n--- STRUCTURE " + "-" * 48)
    gaps = defaultdict(list)
    for slug, e in entries.items():
        if e["fm"].get("type") == "law":
            continue
        needed = REQUIRED_SECTIONS + SECTIONS_BY_TYPE.get(e["fm"].get("type"), [])
        for sec in needed:
            if sec not in e["text"]:
                gaps[sec].append(e["path"])
    for sec, paths in sorted(gaps.items()):
        print(f"  missing {sec:<16} {len(paths)}")
        for p in paths[:5]:
            print(f"    - {p}")

    broken = Counter()
    for e in entries.values():
        for target in LINK.findall(e["text"]):
            t = target.strip()
            if t and t not in entries:
                broken[t] += 1
    print(f"\n  dangling [[links]]  {len(broken)} distinct "
          f"({sum(broken.values())} references)")
    for t, n in broken.most_common(10):
        print(f"    - {t} ({n})")
    print("\n  A dangling link is a seed, not an error. A rising count is fine; "
          "a stalled one\n  means nothing is being promoted.")

    print("\n" + "=" * 62)
    print(f"HEADLINE  entries={len(entries)}  orphans={len(orphans)}  "
          f"dangling={len(broken)}")
    print("=" * 62)


if __name__ == "__main__":
    main()
