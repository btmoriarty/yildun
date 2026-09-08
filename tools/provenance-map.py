#!/usr/bin/env python3
"""provenance-map.py - render a piece's lineage back to its human root(s), and gate on it.

Requirement 1 (the idea-to-output map) and requirement 8 (everything traceable to a human origin).
Given any piece, walk its lineage keys (derives_from / recombined_from / crossed_from) to the human
roots -- author drops, captured verbatim, an author-attributed provenance block, the CAPTURED.md
capture store -- print the chain, label each node with its experiential tier, and report ROOTED
yes/no. A branch that reaches no human origin is an ORPHAN.

The experiential tier is the front-matter key `experience:` (not `tier:`, the settledness axis).
Absent means memory. Here it only labels the map.

    provenance-map.py PIECE.md              render the lineage tree; exit 1 if orphan
    provenance-map.py --check FILE...        quiet gate over many files; exit 1 if any orphan
    provenance-map.py --require T1,T2 ...     types the gate requires rooting for (default from below)
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import worldconfig as _wc
_iu = __import__("importlib").import_module("importlib.util")
_spec = _iu.spec_from_file_location("ct", os.path.join(HERE, "check-transcription.py"))
ct = _iu.module_from_spec(_spec); _spec.loader.exec_module(ct)

CFG = _wc.load()
CAPTURES = os.path.abspath(CFG["captures"])

# Types the gate REQUIRES a human root for: the personal-memory story pieces. Canon world-building
# (figure/location/route/...) roots differently (in the world's laws and cross-links), which this
# tool does not yet fully model, so it is not gated here. Widen once law-rooting is handled.
DEFAULT_REQUIRE = {"derivation", "composite", "deliverable"}

FILE_RE = re.compile(r"([\w./-]+\.md)")
# A human-origin marker: an author drop or supply, captured verbatim, an "Author, <date>:" attribution,
# or a reference to the capture store.
ROOT_MARKER = re.compile(r"author\s*(?:drop|supply|,|:)|verbatim|CAPTURED\.md|\bcaptured?\b", re.I)
TIER_RE = re.compile(r"(?m)^experience:\s*(memory|adaptation|fiction)\b", re.I)
LINEAGE_KEYS = ("derives_from", "recombined_from", "crossed_from")


def read_fm(path):
    try:
        return ct.split_doc(open(path, encoding="utf-8").read())[0]
    except OSError:
        return None


def type_of(fm):
    m = re.search(r"(?m)^type:\s*([\w-]+)", fm or "")
    return m.group(1).lower() if m else ""


def tier_of(fm):
    m = TIER_RE.search(fm or "")
    return m.group(1).lower() if m else "memory"


MODE_RE = re.compile(r"(?m)^mode:\s*(fiction|nonfiction)\b", re.I)


def mode_of(fm):
    """The shipping/treatment axis, separate from experience: fiction hides the real, nonfiction keeps
    it. Absent means fiction, so every existing piece keeps its current behavior."""
    m = MODE_RE.search(fm or "")
    return m.group(1).lower() if m else "fiction"


def has_own_verbatim(fm):
    return bool(re.search(r"(?mi)^\s*\w*verbatim\w*\s*:", fm or ""))


def block_text(fm, key):
    """The text value of a `key: >-` (or plain) front-matter block, for scanning."""
    m = re.search(rf"(?ms)^{key}:\s*(?:>-|\|)?\s*\n((?:[ \t]+\S.*\n?)+)", fm or "")
    return m.group(1) if m else ""


def provenance_is_rooted(fm):
    return bool(ROOT_MARKER.search(block_text(fm, "provenance")))


def lineage_lines(fm):
    """Entries under the lineage keys, in either YAML form: a block list

        derives_from:
          - author drop ...
          - generated/derivations/x.md

    or an inline scalar

        derives_from: the ride to grand central (CAPTURED, 2026-07-24)
    """
    keys = "|".join(LINEAGE_KEYS)
    out, collecting = [], False
    for line in (fm or "").splitlines():
        m_block = re.match(rf"^({keys}):\s*$", line)
        m_inline = re.match(rf"^({keys}):\s+(.+)$", line)
        if m_block:
            collecting = True
            continue
        if m_inline:
            val = m_inline.group(2).strip().strip('"')
            if val not in (">-", "|"):          # a real inline value, not a block indicator
                out.append(val)
            collecting = val in (">-", "|")
            continue
        if collecting:
            m = re.match(r"^\s+-\s+(.*)$", line)
            if m:
                out.append(m.group(1).strip().strip('"'))
            elif line.strip() == "":
                continue
            else:
                collecting = False
    return out


def resolve(ref, root):
    corpus = CFG["corpus_dir"]
    paths = []
    for cand in FILE_RE.findall(ref):
        for p in (cand if os.path.isabs(cand) else os.path.join(root, cand),
                  os.path.join(corpus, cand),
                  os.path.join(corpus, os.path.basename(cand))):
            if os.path.exists(p):
                if p not in paths:
                    paths.append(p)
                break
    return paths


def walk(path, root, depth, maxdepth, seen, indent="", quiet=False):
    """Print the subtree (unless quiet); return True if this branch reaches a human root."""
    fm = read_fm(path)
    def out(s):
        if not quiet:
            print(s)
    out(f"{indent}{os.path.relpath(path, root)}  [{tier_of(fm)}]")
    if fm is None:
        out(f"{indent}   (unreadable)")
        return False
    ci = indent + "   "
    rooted = False
    if tier_of(fm) == "fiction":
        # Requirement 8 asks for a HUMAN origin. For fiction that origin is the authorship itself:
        # the author invented it, which the world's own law counts as a root (riff-as-root,
        # references/INTERROGATION.md 4c: "an invented fragment supplied by the author is a capture
        # ... properly rooted"). Memory/adaptation still demand a capture-root below; only a declared
        # fiction is rooted by construction, and the tier is the author's declaration to make.
        out(f"{ci}◆ author-invented fiction (experience: fiction) — HUMAN ROOT (authorship)")
        rooted = True
    if has_own_verbatim(fm):
        out(f"{ci}◆ own captured drop (verbatim in front matter) — HUMAN ROOT")
        rooted = True
    if provenance_is_rooted(fm):
        out(f"{ci}◆ provenance names an author drop / capture — HUMAN ROOT")
        rooted = True
    if path in seen or depth >= maxdepth:
        if depth >= maxdepth:
            out(f"{ci}(max depth)")
        return rooted
    seen = seen | {path}
    for ref in lineage_lines(fm):
        children = resolve(ref, root)
        if children:
            for child in children:
                if os.path.abspath(child) == CAPTURES:
                    out(f"{ci}◆ {os.path.relpath(child, root)} (capture store) — HUMAN ROOT")
                    rooted = True
                else:
                    rooted = walk(child, root, depth + 1, maxdepth, seen, ci, quiet) or rooted
        elif ROOT_MARKER.search(ref):
            out(f"{ci}◆ {ref[:88]} — HUMAN ROOT")
            rooted = True
        else:
            out(f"{ci}✗ {ref[:88]} — UNRESOLVED (no file, no human-root marker)")
    return rooted


def main(argv):
    ap = argparse.ArgumentParser(description="Map a piece's lineage to its human root(s); gate on it.")
    ap.add_argument("pieces", nargs="+")
    ap.add_argument("--depth", type=int, default=12)
    ap.add_argument("--check", action="store_true", help="quiet gate over many files; exit 1 if any orphan")
    ap.add_argument("--require", default="", help="comma-separated types the gate requires rooting for")
    args = ap.parse_args(argv)
    root = CFG["root"]
    require = set(t.strip() for t in args.require.split(",") if t.strip()) or DEFAULT_REQUIRE

    if args.check:
        orphans = 0
        for p in args.pieces:
            if not os.path.exists(p):
                print(f"  ? missing   {p}"); continue
            t = type_of(read_fm(p))
            if t not in require:
                print(f"  · skip      {os.path.relpath(os.path.abspath(p), root)} (type={t or 'none'})")
                continue
            ok = walk(os.path.abspath(p), root, 0, args.depth, set(), quiet=True)
            print(f"  {'ok       ' if ok else 'ORPHAN   '} {os.path.relpath(os.path.abspath(p), root)}")
            orphans += 0 if ok else 1
        print(f"\nrooted-gate: {orphans} orphan(s) across {len(args.pieces)} file(s).")
        return 1 if orphans else 0

    p = args.pieces[0]
    if not os.path.exists(p):
        sys.exit(f"provenance-map: no such file: {p}")
    print(f"PROVENANCE MAP — {os.path.relpath(os.path.abspath(p), root)}\n")
    rooted = walk(os.path.abspath(p), root, 0, args.depth, set())
    print()
    if rooted:
        print("ROOTED: yes — every branch shown reaches a human origin.")
        return 0
    print("ROOTED: NO — no human origin found. This is an ORPHAN; the rooted gate will block it.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
