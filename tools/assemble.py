#!/usr/bin/env python3
"""assemble.py - the deliverable ladder: sequence pieces into a longer work.

Requirement 3 (short stories, novellas, novels). Takes an ORDERED set of built pieces and assembles
their prose into one deliverable, under a title, with section breaks, carrying provenance so the
assembled work is rooted through its constituents (requirement 8) and traces back to them (req 1).

Ordering is the author's: emotional order, not chronology, is his call (the standing principle), so
this assembles the order it is GIVEN. With --carrier it pulls a cluster in a default order (by the
`hex:` field, else filename) as a STARTING arrangement to be reordered, never as the final sequence.

It assembles prose only; a screenplay adapter is a separate format track (deferred). The output is a
personal-record draft (status: draft, not canon): assembling does not mask, so the deliverable stays
exempt from the shareable gates until the author masks it.

    assemble.py --title "A Thread" --out deliverables/a-thread.md \
                generated/derivations/piece-one.md generated/derivations/piece-two.md
    assemble.py --title "..." --out ... --carrier NAME
"""
import argparse
import datetime
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_iu = __import__("importlib").import_module("importlib.util")
_spec = _iu.spec_from_file_location("pm", os.path.join(HERE, "provenance-map.py"))
pm = _iu.module_from_spec(_spec); _spec.loader.exec_module(pm)
_specr = _iu.spec_from_file_location("rc", os.path.join(HERE, "recommend.py"))
rc = _iu.module_from_spec(_specr); _specr.loader.exec_module(rc)
CFG = pm.CFG

APPARATUS = re.compile(
    r"\n(?:#+\s*(?:Notes|Connections|Provenance|Deepen-me|Canonical lines|Register|Seeded|Machine)"
    r"|\*\*(?:Notes|Connections|Provenance|Register|Seeded|Machine|Deepen))", re.I)


def piece_body(fm_body):
    """The narrative prose: drop the leading '# Title' heading and any trailing apparatus."""
    body = APPARATUS.split(fm_body, maxsplit=1)[0]
    body = re.sub(r"^\s*#\s+.*\n", "", body, count=1)  # drop the piece's own H1
    return body.strip()


def name_of(fm, path):
    m = re.search(r"(?m)^name:\s*(.+)$", fm)
    return m.group(1).strip() if m else os.path.basename(path)


def hex_of(fm):
    m = re.search(r'(?m)^hex:\s*"?(0x[0-9a-fA-F]+)"?', fm)
    return int(m.group(1), 16) if m else 1 << 30


def carrier_cluster(name):
    out = []
    for p, fm in rc.memory_pieces():
        if name.lower() in [c.lower() for c in rc.carriers(fm)]:
            out.append((hex_of(fm), p))
    return [p for _, p in sorted(out)]


def main(argv):
    ap = argparse.ArgumentParser(description="Assemble ordered pieces into one deliverable.")
    ap.add_argument("pieces", nargs="*")
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", required=True, help="output path (under deliverables/)")
    ap.add_argument("--carrier", default="", help="pull this carrier's cluster (default order) instead")
    ap.add_argument("--headings", action="store_true", help="keep each piece's title as a section heading")
    ap.add_argument("--date", default="", help="assembly date (YYYY-MM-DD); default today")
    args = ap.parse_args(argv)

    paths = [os.path.abspath(p) for p in args.pieces]
    if args.carrier:
        paths = carrier_cluster(args.carrier)
        print(f"# carrier '{args.carrier}': {len(paths)} pieces in default (hex) order — REORDER for "
              f"emotional sequence before this is final.", file=sys.stderr)
    if len(paths) < 1:
        sys.exit("assemble: give pieces (ordered) or --carrier NAME.")
    for p in paths:
        if not os.path.exists(p):
            sys.exit(f"assemble: no such piece: {p}")

    date = args.date or datetime.date.today().isoformat()
    tiers, sections, constituents = set(), [], []
    for p in paths:
        text = open(p, encoding="utf-8").read()
        fm, body = pm.ct.split_doc(text)
        tiers.add(pm.tier_of(fm))
        constituents.append(os.path.relpath(p, CFG["root"]))
        prose = piece_body(body)
        if args.headings:
            sections.append(f"## {name_of(fm, p)}\n\n{prose}")
        else:
            sections.append(prose)

    experience = tiers.pop() if len(tiers) == 1 else "mixed"
    slug_rel = os.path.relpath(os.path.abspath(args.out), CFG["root"])
    fm_lines = [
        "---",
        "type: deliverable",
        f"name: {args.title}",
        "status: draft, not canon",
        f"experience: {experience}",
        "shippable: true",
        f"assembled: {date}",
        "provenance: >-",
        f"  Assembled {date} by tools/assemble.py from {len(paths)} pieces, in the order given (the",
        "  author's emotional order). Personal-record until masked; inherits its constituents' roots.",
        "derives_from:",
    ]
    fm_lines += [f"  - {c}" for c in constituents]
    fm_lines += ["carrier: inherited from constituents.", "---", "", f"# {args.title}", ""]
    doc = "\n".join(fm_lines) + ("\n\n---\n\n".join(sections)) + "\n"

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(doc)
    words = len(re.findall(r"\S+", "\n".join(sections)))
    print(f"assembled {slug_rel}: {len(paths)} pieces, ~{words} words, experience={experience}")
    print("  rooted through its constituents (derives_from); personal-record until masked.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
