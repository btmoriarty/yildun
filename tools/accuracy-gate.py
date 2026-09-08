#!/usr/bin/env python3
"""accuracy-gate.py - the non-fiction form of rooting: claims must trace to a checkable source.

The non-fiction track (spec/NONFICTION-TRACK.md). In fiction, the fragmentation gate is the blocking
check and it proves no real person survives. Non-fiction ships the real on purpose, so fragmentation is
off and this takes its place. It cannot judge whether a claim is TRUE, which is the author's and an
editor's work, and a tool that scored truth would be the classifier the whole system refuses. What it
can enforce is the apparatus: that a shippable non-fiction piece declares checkable sources and that its
inline citations resolve to them. Rooting asks whether a line traces to a human; this asks whether it
traces to something a second person could verify.

Acts only on pieces that are `mode: nonfiction` AND shippable (`shippable: true`). Everything else,
including every fiction piece, is skipped, so it is safe to run over the whole tree.

A source is declared in front matter:

    sources:
      - county-logs: cig-machine service records, 2019-2021
      - interview-2026-03-11: recorded, consented

A claim cites one inline with `[src:<id>]`. The gate BLOCKS when a shippable non-fiction piece declares
no source, carries no citation at all (nothing traces), or cites an id it never declared (a dangling
citation). A declared source that is never cited is advisory, not blocking.

    accuracy-gate.py --check FILE ...
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_iu = __import__("importlib").import_module("importlib.util")
_s = _iu.spec_from_file_location("pm", os.path.join(HERE, "provenance-map.py"))
pm = _iu.module_from_spec(_s); _s.loader.exec_module(pm)

APPARATUS = re.compile(r"\n(?:#+\s*(?:Notes|Connections|Provenance|Deepen-me|Register|Sources))", re.I)
CITE = re.compile(r"\[src:([\w.:-]+)\]")


def is_shippable(fm):
    return bool(re.search(r"(?mi)^shippable:\s*true\b", fm or ""))


def declared_sources(fm):
    """Ids declared under a `sources:` block: list items of the form `- <id>: <description>`."""
    m = re.search(r"(?ms)^sources:\s*\n((?:[ \t]+-.*\n?)+)", fm or "")
    if not m:
        return []
    return [mm.group(1) for mm in re.finditer(r"(?m)^\s*-\s*([\w.:-]+)\s*:", m.group(1))]


def check_one(path):
    fm, body = pm.ct.split_doc(open(path, encoding="utf-8").read())
    if pm.mode_of(fm) != "nonfiction" or not is_shippable(fm):
        return None  # fiction, or a non-shippable draft; not this gate's business
    prose = APPARATUS.split(body, maxsplit=1)[0]
    declared = declared_sources(fm)
    cited = set(CITE.findall(prose))
    problems = []
    if not declared:
        problems.append("no sources declared; non-fiction ships claims, so declare at least one "
                         "checkable source under `sources:`")
    if not cited:
        problems.append("no inline citation ([src:<id>]) anywhere; nothing in the prose traces to a "
                         "source")
    dangling = sorted(cited - set(declared))
    for d in dangling:
        problems.append(f"citation [src:{d}] resolves to no declared source")
    dead = sorted(set(declared) - cited)  # advisory
    return problems, dead


def main(argv):
    ap = argparse.ArgumentParser(description="Non-fiction accuracy gate: claims must trace to a declared source.")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv)
    checked = violations = 0
    for f in args.files:
        if not os.path.exists(f):
            continue
        r = check_one(f)
        if r is None:
            continue
        checked += 1
        problems, dead = r
        rel = os.path.relpath(os.path.abspath(f), pm.CFG["root"])
        for p in problems:
            violations += 1
            print(f"  BLOCK    {rel}: {p}")
        for d in dead:
            print(f"  advisory {rel}: declared source '{d}' is never cited")
        if not problems:
            print(f"  ok       {rel}")
    print(f"\naccuracy-gate: {checked} non-fiction shippable piece(s), {violations} violation(s).")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
