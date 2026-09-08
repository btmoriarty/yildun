#!/usr/bin/env python3
"""coverage.py - the coverage engine: one read-only picture of where the world is thin, fat, stale,
orphaned, or turning into a monoculture.

P1 of the build plan (AUTHORING-TOOL-SPEC.md section 14). It reports; it never writes. It complements
the others rather than repeating them: `gap-report` asks the author for material only a human can
supply, `recommend` proposes assemblies, `surface-material` finds latent stories. This is the flat
census, the distribution across every axis plus the four health checks, so a starved lane or a
forming monoculture is visible at a glance before any of the others run.

Read-only. Every finding is an observation, not an instruction. What to build, and whether an
imbalance is a problem, stays the author's call.

What it shows:
  DISTRIBUTION  per axis (lanes, generation, region, cadence, tier, type, ...), each value's count and
                share, with STARVED (well below the axis mean) and OVER-FED (well above) flagged.
  STALE         entries untouched longest, by last commit date (mtime if not a git repo).
  ORPHANED      entries nothing links to: no incoming [[link]] from any other entry.
  MONOCULTURE   a tag or motif carried by a large share of entries, the shape starting to repeat.

    coverage.py                 the whole census
    coverage.py --axis lanes    one axis in full
    coverage.py --stale 20      how many stale entries to list
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import worldconfig as _wc

CFG = _wc.load()
ROOT = CFG["root"]
DEFAULT_AXES = ["lanes", "generation", "region", "cadence", "tier", "type"]
LAWFILE = re.compile(r"^\d\d-.*\.md$")
CODE = re.compile(r"`[^`]*`|```.*?```", re.S)


def axes():
    """The axes to census: world.json "axes" if it sets them, else the engine defaults."""
    wj = os.path.join(ROOT, "world.json")
    if os.path.exists(wj):
        try:
            ax = json.load(open(wj, encoding="utf-8")).get("axes")
            if isinstance(ax, list) and ax:
                return ax
        except (OSError, ValueError):
            pass
    return DEFAULT_AXES


def entries():
    """World entries: canon plus derivations, minus the numbered law/reference files."""
    out = set(glob.glob(os.path.join(CFG["canon_dir"], "**", "*.md"), recursive=True))
    out |= set(glob.glob(os.path.join(CFG["corpus_dir"], "*.md")))
    return sorted(f for f in out if not LAWFILE.match(os.path.basename(f)))


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def axis_values(fm, key):
    m = re.search(rf"(?m)^{key}:\s*(.+)$", fm)
    if not m:
        return []
    raw = re.sub(r"\s+#.*$", "", m.group(1)).strip()  # drop any inline YAML comment
    if raw.startswith("["):
        return [v.strip().strip('"').lower() for v in raw.strip("[]").split(",") if v.strip()]
    return [raw.strip().strip('"').lower()]


def last_dates():
    """stem -> last commit date (YYYY-MM-DD) in one git pass; empty if not a git repo."""
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "--format=C%as", "--name-only"],
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    dates, cur = {}, ""
    for ln in out.splitlines():
        if ln.startswith("C"):
            cur = ln[1:]
        elif ln.strip() and cur:
            dates.setdefault(ln.strip(), cur)  # first seen == most recent
    return dates


def link_incoming(files):
    stems = {os.path.splitext(os.path.basename(f))[0].lower() for f in files}
    incoming = Counter()
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0].lower()
        txt = CODE.sub("", open(f, encoding="utf-8").read())
        for m in re.finditer(r"\[\[([^]|]+)(?:\|[^]]*)?\]\]", txt):
            t = m.group(1).strip().lower().replace(" ", "-")
            if t in stems and t != base:
                incoming[t] += 1
    return incoming


def bar(n, top):
    return "#" * int(round(18 * n / top)) if top else ""


def main(argv):
    ap = argparse.ArgumentParser(description="Coverage engine: distribution and health, read-only.")
    ap.add_argument("--axis", default="", help="show only this axis")
    ap.add_argument("--stale", type=int, default=12, help="how many stale entries to list")
    args = ap.parse_args(argv)

    files = entries()
    if not files:
        sys.exit("coverage: no entries found under canon/ or the corpus dir.")
    fms = {f: frontmatter(open(f, encoding="utf-8").read()) for f in files}

    print(f"COVERAGE, {len(files)} entries (read-only; observations, not instructions)\n")

    show_axes = [args.axis] if args.axis else axes()
    for key in show_axes:
        tally = Counter()
        for f in files:
            for v in axis_values(fms[f], key):
                tally[v] += 1
        if not tally:
            continue
        mean = sum(tally.values()) / len(tally)
        top = max(tally.values())
        print(f"AXIS {key}  ({len(tally)} values, mean {mean:.1f} per value)")
        for v, n in sorted(tally.items(), key=lambda x: -x[1]):
            flag = "  STARVED" if n <= max(1, mean * 0.4) else ("  OVER-FED" if n >= mean * 2 else "")
            print(f"  {v:<18} {n:>3} {bar(n, top)}{flag}")
        print()

    if args.axis:
        return 0

    # STALE
    dates = last_dates()
    src = "last commit" if dates else "file mtime"
    def when(f):
        return dates.get(os.path.relpath(f, ROOT)) or \
            __import__("datetime").date.fromtimestamp(os.path.getmtime(f)).isoformat()
    stale = sorted(files, key=when)[:args.stale]
    print(f"STALE, oldest {len(stale)} by {src}:")
    for f in stale:
        print(f"  {when(f)}  {os.path.relpath(f, ROOT)}")

    # ORPHANED (no incoming links)
    incoming = link_incoming(files)
    orphans = [f for f in files
               if incoming[os.path.splitext(os.path.basename(f))[0].lower()] == 0]
    print(f"\nORPHANED, {len(orphans)} entries nothing links to:")
    for f in sorted(orphans)[:20]:
        print(f"  {os.path.relpath(f, ROOT)}")
    if len(orphans) > 20:
        print(f"  ... and {len(orphans) - 20} more")

    # MONOCULTURE (tag share)
    tags = Counter()
    for f in files:
        for v in axis_values(fms[f], "tags"):
            tags[v] += 1
    hot = [(t, n) for t, n in tags.items() if n >= max(3, len(files) * 0.25)]
    print("\nMONOCULTURE (a tag on a quarter or more of entries; a shape starting to repeat):")
    if hot:
        for t, n in sorted(hot, key=lambda x: -x[1]):
            print(f"  {t}: {n} of {len(files)} ({100*n//len(files)}%)")
    else:
        print("  none by tag share. Motif monocultures are a human read; see repetition-report.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
