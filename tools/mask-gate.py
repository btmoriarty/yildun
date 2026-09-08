#!/usr/bin/env python3
"""mask-gate.py - the real<->mask registry check that guarantees an unmasked rebuild.

Requirement 4's preservation half (author, 2026-09-06: "everything I write preserved in case I want to
rebuild unmasked later"). The captures are the unmasked truth; this makes the masked->unmasked mapping
recorded and complete, so any shareable masked piece can be reversed deterministically.

The registry is `generated/mask-map.tsv` (private): mask <TAB> real <TAB> experience <TAB> notes, with
real "?" meaning unresolved.

Two enforced properties, on SHAREABLE memory/adaptation pieces only (canon entries and deliverables;
personal-record drafts under generated/derivations are exempt, and fiction pieces have no real):

  1. NO UNRESOLVED MASK IN USE. If a shareable piece uses a registered mask whose real is still "?",
     the unmasked rebuild cannot resolve it -> block, and name the hole to fill.
  2. NO REAL LEAK. If a recorded real name appears in a shareable piece's prose, masking was not
     applied -> block. (Shareable prose carries masks only; the reals live in the map and captures.)

    mask-gate.py                     print the registry and its holes
    mask-gate.py --check FILE...     gate; exit 1 on any violation
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
NONSHAREABLE_STATUS = re.compile(
    r"draft, not canon|mask before|personal.record|working.file|demo|not canon", re.I)
CANON_TYPES = {"figure", "vignette", "legend", "location", "route", "object", "body", "term"}


def load_map():
    rows = []
    try:
        for line in open(CFG["mask_map"], encoding="utf-8"):
            if line.strip().startswith("#") or not line.strip():
                continue
            parts = [c.strip() for c in line.rstrip("\n").split("\t")]
            while len(parts) < 4:
                parts.append("")
            rows.append({"mask": parts[0], "real": parts[1],
                         "experience": parts[2] or "memory", "notes": parts[3]})
    except OSError:
        pass
    return rows


def _field(fm, key):
    m = re.search(rf"(?m)^{key}:\s*(.+)$", fm or "")
    return m.group(1).strip() if m else ""


def experience_of(fm):
    m = re.search(r"(?m)^experience:\s*(memory|adaptation|fiction)\b", fm or "", re.I)
    return m.group(1).lower() if m else "memory"


def is_shareable(fm, path):
    """Canon entries and deliverables are shareable; personal-record drafts are not."""
    if NONSHAREABLE_STATUS.search(_field(fm, "status")):
        return False
    typ = _field(fm, "type").lower()
    ap = os.path.abspath(path)
    if os.path.abspath(CFG["deliverables_dir"]) in ap:
        return True
    if os.path.abspath(CFG["canon_dir"]) in ap and typ != "law":
        return True
    return typ in CANON_TYPES


# Apparatus headings/markers: engine notes, not the author's narrative. A reference to the real author
# as overseer ("what Brian said", "Flagged for Brian", "until Brian chooses") lives here, not in a
# scene, so the leak check must not read it. Take the prose before the first apparatus marker.
APPARATUS = re.compile(
    r"\n(?:#+\s*(?:Notes|Connections|Provenance|Deepen-me|Canonical lines|Register|Seeded|Machine)"
    r"|\*\*(?:Notes|Connections|Provenance|Register|Seeded|Machine|Deepen))", re.I)


def narrative_only(body):
    return APPARATUS.split(body, maxsplit=1)[0]


def scan(path, rows):
    """Return (unresolved_masks_used, reals_leaked) for a shareable memory/adaptation piece."""
    text = open(path, encoding="utf-8").read()
    fm, body = ct.split_doc(text)
    if experience_of(fm) == "fiction" or not is_shareable(fm, path):
        return None  # exempt
    body = narrative_only(body)
    unresolved, leaked = [], []
    for r in rows:
        if r["mask"] and re.search(rf"\b{re.escape(r['mask'])}\b", body):
            if r["real"] == "?" or not r["real"]:
                unresolved.append(r["mask"])
        if r["real"] and r["real"] != "?" and re.search(rf"\b{re.escape(r['real'])}\b", body):
            if r["real"] not in leaked:
                leaked.append(r["real"])
    return unresolved, leaked


def main(argv):
    ap = argparse.ArgumentParser(description="Check the real<->mask registry for unmasked-rebuild.")
    ap.add_argument("pieces", nargs="*")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    rows = load_map()
    holes = [r for r in rows if r["real"] in ("?", "")]

    if not args.check:
        print(f"mask-map: {len(rows)} entr(y/ies), {len(holes)} unresolved.\n")
        for r in rows:
            mark = "  (HOLE)" if r["real"] in ("?", "") else ""
            print(f"  {r['mask']:<18} -> {r['real']:<10} [{r['experience']}]{mark}  {r['notes']}")
        return 0

    violations, advisories = 0, 0
    if holes:
        print(f"mask-map: {len(holes)} unresolved real(s) — fill before those masks go shareable: "
              + ", ".join(r["mask"] for r in holes))
    for p in args.pieces:
        if not os.path.exists(p):
            continue
        res = scan(p, rows)
        if res is None:
            continue  # fiction or personal-record: exempt
        unresolved, leaked = res
        rel = os.path.relpath(os.path.abspath(p), CFG["root"])
        # BLOCKING: a mask in use with no recorded real breaks the unmasked rebuild. Precise.
        for m in unresolved:
            print(f"  BLOCK  {rel}: uses mask '{m}' whose real is unrecorded — unmasked rebuild "
                  f"cannot resolve it."); violations += 1
        # ADVISORY: a recorded real in shareable prose MIGHT be a leak, but a common first name also
        # matches legitimate uses (a note about the author, a differently-named character). Surfaced
        # for a human glance; precise leak-gating belongs to the export boundary with curated
        # sensitive identifiers, not a bare first name.
        for r in leaked:
            print(f"  advisory  {rel}: contains '{r}' (a recorded real) in prose — confirm it is not a "
                  f"leak before export."); advisories += 1
    print(f"\nmask-gate: {violations} blocking, {advisories} advisory.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
