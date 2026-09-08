#!/usr/bin/env python3
"""fragmentation-gate.py - nothing leaves the author unless it is radically fragmented.

The author's publication invariant (2026-09-06): the identifiable material (raw memory, the mask-map,
the unmasked-rebuild key) is HIS ALONE and is never shared, including with research partners. The only
artifact that goes beyond him is a composite that has been radically fragmented, so that no single real
person survives it. De-identification is by construction (a composite of several people is nobody), not
by name-swap. This gate verifies the fragmentation before a piece is shippable, rather than trusting it.

A SHIPPABLE piece (experience: fiction with type composite, or `shippable: true`) must:

  1. SOURCE MULTIPLICITY. Descend from at least two distinct real sources, so it is not one person's
     story with the serial numbers filed off. Fewer than two -> BLOCK. Two is the floor; three or more
     is the intent, and two is flagged as thin.
  2. NO VERBATIM SURVIVAL. No long contiguous span (>= 8 words) from any source's captured verbatim may
     appear intact in the shipped prose. A surviving quoted line is a distinctive identifier a subject
     recognizes even inside an invented figure -> BLOCK.
  3. NO REAL NAME. No recorded real (from the mask-map) may appear in the prose -> BLOCK.

Raw-memory pieces are never shippable and are not checked here; they stay with the author.

    fragmentation-gate.py                 report shippable pieces and their status
    fragmentation-gate.py --check FILE... gate; exit 1 on any violation
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_iu = __import__("importlib").import_module("importlib.util")
_spm = _iu.spec_from_file_location("pm", os.path.join(HERE, "provenance-map.py"))
pm = _iu.module_from_spec(_spm); _spm.loader.exec_module(pm)
_smg = _iu.spec_from_file_location("mg", os.path.join(HERE, "mask-gate.py"))
mg = _iu.module_from_spec(_smg); _smg.loader.exec_module(mg)
CFG = pm.CFG

NGRAM = 8
APPARATUS = mg.APPARATUS


def is_shippable(fm):
    if re.search(r"(?mi)^shippable:\s*false\b", fm or ""):
        return False  # an explicit draft: not ready, so the shipping gate does not run yet
    if re.search(r"(?mi)^shippable:\s*true\b", fm or ""):
        return True
    return pm.tier_of(fm) == "fiction" and pm.type_of(fm) == "composite"


def verbatim_text(fm):
    """All *_verbatim block-scalar values in a piece's front matter (its captured source drops)."""
    out = []
    for m in re.finditer(r"(?mis)^\w*verbatim\w*:\s*(?:>-|\|)?\s*\n((?:[ \t]+\S.*\n?)+)", fm or ""):
        out.append(m.group(1))
    return " ".join(out)


def ngrams(text, n=NGRAM):
    words = re.findall(r"[a-z0-9']+", text.lower())
    return set(tuple(words[i:i + n]) for i in range(len(words) - n + 1)) if len(words) >= n else set()


def source_pieces(path, fm):
    """Distinct real source pieces this composite draws on (resolved from its lineage)."""
    srcs = []
    for ref in pm.lineage_lines(fm):
        for k in pm.resolve(ref, CFG["root"]):
            ak = os.path.abspath(k)
            if ak != pm.CAPTURES and ak != os.path.abspath(path) and ak not in srcs:
                srcs.append(ak)
    return srcs


def check_one(path, reals):
    text = open(path, encoding="utf-8").read()
    fm, body = pm.ct.split_doc(text)
    if not is_shippable(fm):
        return None  # not a shippable artifact; stays with the author
    if pm.mode_of(fm) == "nonfiction":
        return None  # non-fiction keeps the real on purpose; the accuracy and consent gates cover it
    prose = APPARATUS.split(body, maxsplit=1)[0]
    problems = []

    srcs = source_pieces(path, fm)
    if len(srcs) < 2:
        problems.append(f"single-source ({len(srcs)}): not radically fragmented; a composite needs >=2 "
                        f"real sources so no one person survives it")

    # verbatim survival: any 8-gram from a source's captured drop appearing intact in the prose
    prose_ng = ngrams(prose)
    survived = []
    for s in srcs:
        sfm, _ = pm.ct.split_doc(open(s, encoding="utf-8").read())
        common = prose_ng & ngrams(verbatim_text(sfm))
        if common:
            survived.append((os.path.basename(s), next(iter(common))))
    for name, gram in survived:
        problems.append(f"verbatim survived from {name}: \"...{' '.join(gram)}...\" — a distinctive "
                        f"identifier carried intact")

    for r in reals:
        if r and r != "?" and re.search(rf"\b{re.escape(r)}\b", prose):
            problems.append(f"real name '{r}' present in shippable prose")

    thin = len(srcs) == 2 and not problems
    return problems, thin, len(srcs)


def main(argv):
    ap = argparse.ArgumentParser(description="Verify radical fragmentation before a piece may ship.")
    ap.add_argument("pieces", nargs="*")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    reals = [r["real"] for r in mg.load_map()]
    targets = args.pieces or sorted(glob.glob(os.path.join(CFG["corpus_dir"], "*.md")))

    violations, checked = 0, 0
    for p in targets:
        if not os.path.exists(p):
            continue
        res = check_one(p, reals)
        if res is None:
            continue
        checked += 1
        problems, thin, nsrc = res
        rel = os.path.relpath(os.path.abspath(p), CFG["root"])
        if problems:
            for pr in problems:
                print(f"  BLOCK  {rel}: {pr}")
            violations += len(problems)
        else:
            note = "  (thin: only 2 sources; 3+ is the intent)" if thin else ""
            print(f"  ship-ok  {rel}  [{nsrc} sources]{note}")
    print(f"\nfragmentation-gate: {checked} shippable piece(s), {violations} violation(s).")
    return 1 if (violations and args.check) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
