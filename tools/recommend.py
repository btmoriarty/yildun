#!/usr/bin/env python3
"""recommend.py - advisory: what is novella-ready, and what is waiting to be built.

Requirement 7 (tools that recommend stories, novellas, novels). ADVISORY BY CONSTRUCTION: it proposes,
the author disposes (the oversight principle). It reads the built memory pieces and clusters them by
carrier (the recurring figure a run is about), flags clusters large enough to assemble into a longer
work, and surfaces the material that has been dropped but not yet built (the PENDING roster).

It recommends nothing about canon world-building and it never assembles anything; it points, and the
author chooses. The deliverable ladder (separate) is what actually assembles a chosen cluster.

    recommend.py                 the recommendations
    recommend.py --min 3         cluster-size threshold for a novella candidate (default 4)
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_iu = __import__("importlib").import_module("importlib.util")
_spec = _iu.spec_from_file_location("pm", os.path.join(HERE, "provenance-map.py"))
pm = _iu.module_from_spec(_spec); _spec.loader.exec_module(pm)
CFG = pm.CFG

# The protagonist masks are in nearly every memory piece, so clustering on them says nothing. Cluster
# on the OTHER carrier, the figure a run is actually about.
PROTAGONIST = {"he", "she", "they", "the man", "the woman", "the protagonist"} | {
    n.lower() for n in (CFG.get("protagonist") or [])}
ROLE_WORDS = re.compile(r"\((?:man|woman|background|existing|new figure|closing|entering|canon)[^)]*\)", re.I)


def carriers(fm):
    m = re.search(r"(?m)^carrier:\s*(.+)$", fm)
    if not m:
        return []
    raw = ROLE_WORDS.sub("", m.group(1))
    raw = re.sub(r"\b(existing|unnamed|new figure|both|order-\d+ figures?|and)\b", ",", raw, flags=re.I)
    names = []
    for part in re.split(r"[,;/.]| and ", raw):
        n = part.strip().strip(".").strip()
        # keep proper-name-ish tokens
        if n and n[0].isupper() and n.lower() not in PROTAGONIST and 2 <= len(n) <= 30:
            names.append(n)
    return names


def memory_pieces():
    out = []
    for p in sorted(glob.glob(os.path.join(CFG["corpus_dir"], "*.md"))):
        if os.path.basename(p).endswith("BANK.md") or os.path.basename(p) == "PENDING.md":
            continue
        fm = pm.read_fm(p)
        if fm is None or pm.type_of(fm) not in ("derivation", "composite"):
            continue
        if pm.tier_of(fm) == "fiction":
            continue
        out.append((p, fm))
    return out


def pending_roster():
    """Dropped-but-unbuilt material recorded in the PENDING file."""
    path = os.path.join(CFG["corpus_dir"], "PENDING.md")
    if not os.path.exists(path):
        return []
    items = []
    for line in open(path, encoding="utf-8"):
        # A roster entry is a bold LABEL followed by an em/en/spaced-hyphen dash, either after the
        # bold (**Nadia** -- awaiting) or inside it (**Dana -- a whole arc**). A bolded sentence
        # fragment with no such dash (**The kitchen.**, **She invited him over.**) is an annotation
        # of a captured drop, not a roster name, and is skipped -- that was the prose-fragment noise.
        m = re.match(r"^\s*[-*]\s+\*\*([^*]+?)\*\*\s*[—–-]\s", line)          # **Name** -- ...
        if not m:
            m = re.match(r"^\s*[-*]\s+\*\*([^*]+?)\s+[—–-]\s[^*]*\*\*", line)  # **Name -- ...**
        if m:
            label = re.split(r"\s+[—–-]\s", m.group(1))[0].strip().rstrip(".:,")
            items.append(label)
    return items


def main(argv):
    ap = argparse.ArgumentParser(description="Advisory recommendations for stories/novellas/novels.")
    ap.add_argument("--min", type=int, default=4, help="cluster size to call a novella candidate")
    args = ap.parse_args(argv)

    clusters = {}
    for p, fm in memory_pieces():
        for c in carriers(fm):
            clusters.setdefault(c.lower(), {"name": c, "pieces": []})["pieces"].append(os.path.basename(p))
    ranked = sorted(clusters.values(), key=lambda c: -len(c["pieces"]))

    print("RECOMMENDATIONS (advisory — proposals; the author disposes)\n")
    def scale(n):
        if n >= 20:
            return "NOVEL / book-scale spine"
        if n >= 8:
            return "novella-scale"
        return "short story-cycle"

    print("ASSEMBLY CANDIDATES (memory runs by carrier):\n")
    any_cand = False
    for c in ranked:
        n = len(c["pieces"])
        if n >= args.min:
            any_cand = True
            print(f"  {c['name']} — {n} pieces, {scale(n)}:")
            for b in sorted(c["pieces"])[:12]:
                print(f"      {b}")
            if n > 12:
                print(f"      ... and {n - 12} more")
    if not any_cand:
        print(f"  (no carrier has >= {args.min} pieces yet; largest is "
              f"{ranked[0]['name']} at {len(ranked[0]['pieces'])})" if ranked else "  (no clusters)")

    smaller = [c for c in ranked if 1 < len(c["pieces"]) < args.min]
    if smaller:
        print("\nGROWING (a run forming, not yet novella-scale):")
        for c in smaller[:8]:
            print(f"  {c['name']} — {len(c['pieces'])}")

    roster = pending_roster()
    if roster:
        print("\nDROPPED BUT NOT BUILT (from PENDING — build these to extend a run):")
        for it in roster[:12]:
            print(f"  {it[:96]}")

    print("\nNEXT MOVES (advisory):")
    if any_cand:
        top = next(c for c in ranked if len(c["pieces"]) >= args.min)
        n = len(top["pieces"])
        if n >= 20:
            print(f"  - The {top['name']} run ({n} pieces) is book-scale: it is the spine of a NOVEL, and")
            print(f"    wants sub-threading into novella-length movements before assembly, not one pass.")
        else:
            print(f"  - The {top['name']} run ({n} pieces) is the strongest {scale(n)} candidate; the")
            print(f"    deliverable ladder could sequence it in emotional order.")
    if roster:
        print(f"  - {len(roster)} dropped thread(s) await building; each extends or opens a run.")
    print("  - recombine.py can spin any two pieces into a new de-identified story or a myth transposition.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
