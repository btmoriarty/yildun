#!/usr/bin/env python3
"""consent-gate.py - the inverse of masking: a real person kept on the page needs consent on record.

The non-fiction track (spec/NONFICTION-TRACK.md). Fiction removes the person by construction, so
consent is moot and the mask/fragmentation gates handle the removal. Non-fiction keeps the real, named
person on purpose, so consent becomes the work. Like the mask map, this is declaration-based: it cannot
read every real name out of prose, and a tool that guessed at who is real would over-fire or leak. It
forces the author to enumerate the real living people named and record a status for each, the same
conscious call the mask gate forces for fiction.

Acts only on pieces that are `mode: nonfiction` AND shippable (`shippable: true`); everything else,
fiction included, is skipped.

Declared in front matter, one of:

    consent:
      - Jane Roe: consented
      - A. Public-Official: public-figure
      - the coroner: public-interest
      - Old Man Hensley: deceased

or, when no real living person is named:

    consent:
      - none

The gate BLOCKS a shippable non-fiction piece with no `consent:` block, or any entry whose status is
missing or not one of: consented, public-figure, public-interest, deceased. The literal `- none` is the
author's on-record assertion that no real living person is named; the gate accepts it the way the mask
gate trusts a resolved mced entry, because verifying it is the author's job, not a regex's.
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

VALID = {"consented", "public-figure", "public-interest", "deceased"}


def is_shippable(fm):
    return bool(re.search(r"(?mi)^shippable:\s*true\b", fm or ""))


def consent_block(fm):
    m = re.search(r"(?ms)^consent:\s*\n((?:[ \t]+-.*\n?)+)", fm or "")
    return m.group(1) if m else None


def check_one(path):
    fm, _ = pm.ct.split_doc(open(path, encoding="utf-8").read())
    if pm.mode_of(fm) != "nonfiction" or not is_shippable(fm):
        return None
    block = consent_block(fm)
    problems = []
    if block is None:
        problems.append("no `consent:` block; non-fiction keeps real people, so record a status for "
                        "each named living person, or `- none` if no real living person is named")
        return problems
    items = re.findall(r"(?m)^\s*-\s*(.+?)\s*$", block)
    if items == ["none"]:
        return problems  # on-record assertion: no real living person named
    for it in items:
        if it.strip().lower() == "none":
            problems.append("`- none` cannot be mixed with named people; use one or the other")
            continue
        m = re.match(r"^(.*\S)\s*:\s*([\w-]+)$", it)
        if not m:
            problems.append(f"consent entry '{it}' has no status; use `name: <status>`")
            continue
        name, status = m.group(1), m.group(2).lower()
        if status not in VALID:
            problems.append(f"consent for '{name}' is '{status}', not one of "
                            f"{', '.join(sorted(VALID))}")
    return problems


def main(argv):
    ap = argparse.ArgumentParser(description="Non-fiction consent gate: a named real person needs consent on record.")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv)
    checked = violations = 0
    for f in args.files:
        if not os.path.exists(f):
            continue
        problems = check_one(f)
        if problems is None:
            continue
        checked += 1
        rel = os.path.relpath(os.path.abspath(f), pm.CFG["root"])
        for p in problems:
            violations += 1
            print(f"  BLOCK    {rel}: {p}")
        if not problems:
            print(f"  ok       {rel}")
    print(f"\nconsent-gate: {checked} non-fiction shippable piece(s), {violations} violation(s).")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
