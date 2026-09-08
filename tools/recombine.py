#!/usr/bin/env python3
"""recombine.py - turn parts of existing pieces into a seed for a NEW, independent story.

Capability 2 and 3 of the narrative compiler, in one stage: mix and match characteristics into a new
story, and blend real (de-identified) material with fiction. It works by the world's own ontology
(the world's masking law, "each character is many characters"): pull elements from SEVERAL different pieces, so the
result maps to no single real person. A composite of three real people is nobody real. That is
de-identification by construction, not by redaction.

WHAT IT DOES

  - Reads the facts of two or more source pieces (their captured verbatim, atomised) and, optionally,
    gestures from a gesture bank.
  - Selects a spread ACROSS the sources, round-robin, so no one source dominates and the seed cannot
    be resolved back to a single memory.
  - Emits a RECOMBINATION BRIEF: the chosen elements, each TAGGED WITH ITS REAL ROOT (nothing
    rootless, canon rule one), under a directive to build ONE new figure and ONE new situation that
    no single source owns, inventing the connective tissue.

WHAT IT REFUSES TO PRETEND

  - It does not decide the new story. Composition is generation; this hands the writer a rooted,
    de-identified seed and the instruction to make something new from it, then the writer writes and
    the gate checks. Same division as compose-brief.
  - It does not close a drift or resolve a held question (canon rule two).

    recombine.py A.md B.md C.md
    recombine.py A.md B.md --influence "30 Serling / 20 Carver" --pick 8 --gestures 3 --seed 5

World-agnostic and config-injected: sources, influence and the bank path all arrive by argument, so
the same stage runs against any world. Reuses seed-brief and check-transcription. This is the public
half; the private world stays private.
"""
import argparse
import hashlib
import importlib.util
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sb = _load("seed_brief", "seed-brief.py")
ct = _load("check_transcription", "check-transcription.py")
wc = _load("worldconfig", "worldconfig.py")


def facts_of(path):
    """Atomised, de-duplicated, meta-filtered facts from one piece, via the shared intake."""
    notes = sb.notes_of(path) or [open(path, encoding="utf-8").read()]
    facts, seen = [], set()
    for n in notes:
        if sb.is_meta(n):
            continue
        for f in sb.atoms(n):
            k = " ".join(f.lower().split())
            if len(ct.content_words(f)) >= 2 and k not in seen:
                seen.add(k)
                facts.append(f)
    return facts


def carrier_of(path):
    """A myth figure to transpose the real shapes ONTO: its name and a few defining traits.

    Returns (name, [trait facts], [locked lines]). The name comes from front matter; the traits are
    the first defining sentences of the body; locked lines are those the entry marks tier: locked, so
    the transposition preserves what canon has fixed.
    """
    text = open(path, encoding="utf-8").read()
    fm, body = ct.split_doc(text)
    m = re.search(r"(?m)^name:\s*(.+?)\s*$", fm)
    name = m.group(1).strip() if m else os.path.basename(path)
    traits, seen = [], set()
    for f in sb.atoms(body):
        k = " ".join(f.lower().split())
        if len(ct.content_words(f)) >= 3 and k not in seen:
            seen.add(k)
            traits.append(f)
        if len(traits) >= 6:
            break
    locked = re.findall(r'"([^"]{4,120})"[^\n]*tier:\s*locked', body)
    return name, traits, locked


def gestures_of(bank_path, rng, n):
    """Sample gestures from the bank's curated BODY list, one per '**N.**' line.

    The bank's front matter is discursive prose about rules and rejected items; the earlier miner
    read that and returned commentary fragments. The real gestures live in the body under '## '
    headings as numbered items, '**7.** Holds the back of his neck ...', and the author's struck
    numbers are already OMITTED from that list (4, 9, 17, 19 are simply absent). So mining the body
    items gives the live, pruned set. Any item still tagged STRUCK inline is skipped for safety.
    """
    if not bank_path or not os.path.exists(bank_path):
        return []
    _, body = ct.split_doc(open(bank_path, encoding="utf-8").read())
    items = []
    for m in re.finditer(r"(?m)^\*\*\d+\.\*\*\s*(.+?)\s*$", body):
        g = " ".join(m.group(1).split()).strip()
        if g and "STRUCK" not in g.upper() and len(ct.content_words(g)) >= 2:
            items.append(g)
    seen, uniq = set(), []
    for g in items:
        k = g.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(g)
    rng.shuffle(uniq)
    return uniq[:n]


def main(argv):
    ap = argparse.ArgumentParser(description="Recombine parts of pieces into a new-story seed.")
    ap.add_argument("sources", nargs="+", help="two or more piece files to draw from")
    ap.add_argument("--pick", type=int, default=8, help="how many facts to carry into the seed")
    ap.add_argument("--gestures", type=int, default=0, help="how many bank gestures to add")
    ap.add_argument("--bank", default="", help="gesture bank; default from world config")
    ap.add_argument("--influence", default="")
    ap.add_argument("--carrier", default="", help="a canon myth figure to transpose the shapes onto")
    ap.add_argument("--seed", type=int, default=None, help="vary the draw; default is content-derived")
    args = ap.parse_args(argv)

    if len(args.sources) < 2:
        sys.exit("recombine: give at least two source pieces; a composite needs more than one root.")

    pools = []
    for s in args.sources:
        if not os.path.exists(s):
            sys.exit(f"recombine: no such file: {s}")
        f = facts_of(s)
        if f:
            pools.append((os.path.basename(s), f))
    if len(pools) < 2:
        sys.exit("recombine: fewer than two sources yielded facts.")

    if args.seed is None:
        blob = "|".join(name + "".join(fs) for name, fs in pools)
        seed = int(hashlib.sha256(blob.encode()).hexdigest()[:8], 16)
    else:
        seed = args.seed
    rng = random.Random(seed)

    # Round-robin across sources so the draw spans them and no one memory owns the seed.
    shuffled = []
    for name, fs in pools:
        fs = fs[:]
        rng.shuffle(fs)
        shuffled.append((name, fs))
    picked = []
    i = 0
    while len(picked) < args.pick and any(fs for _, fs in shuffled):
        name, fs = shuffled[i % len(shuffled)]
        if fs:
            picked.append((name, fs.pop()))
        i += 1
    rng.shuffle(picked)

    bank = args.bank or wc.load()["gesture_bank"]
    gestures = gestures_of(bank, rng, args.gestures) if args.gestures else []

    carrier = carrier_of(args.carrier) if args.carrier else None
    if carrier:
        infl = args.influence.strip() or "the world's register and its influence set"
    else:
        infl = args.influence.strip() or "faithful: the world's register only, no writer styling"

    print("RECOMBINATION BRIEF" + ("  ·  MYTH TRANSPOSITION" if carrier else ""))
    print("sources   :", ", ".join(name for name, _ in pools))
    print("influence :", infl)
    if carrier:
        name, traits, locked = carrier
        print(f"carrier   : {name} (canon figure). Write a NEW legend of this figure.")
        print("identity  : TRANSPOSE. Carry the real shapes below into the carrier's world and register.")
        print("            The memory supplies the emotional architecture; the myth figure supplies who")
        print("            and where. The result is a legend, not a memory: nobody real survives the")
        print("            crossing. Keep the carrier's locked facts; invent everything between.")
    else:
        print("identity  : INVENT. Build one new figure and one new situation. No one here is any single")
        print("            real person; the mix of roots below is the de-identification. Do not reproduce")
        print("            any source's arc. Invent the connective tissue between the elements.")
    print()
    print("TWO RULES")
    print("  1. Nothing rootless. Every element below names the real piece it descends from; the new")
    print("     story inherits those roots. Invent freely BETWEEN them; add nothing that traces to")
    print("     no root at all.")
    print("  2. Close nothing. Do not resolve any held question a source or the carrier left open,")
    print("     and do not resolve a drift by writing prose that only works if it were resolved.")
    print()
    if carrier:
        name, traits, locked = carrier
        print(f"CARRIER — {name} (keep these fixed)\n")
        for tr in traits:
            print(f"  · {tr}")
        for lk in locked:
            print(f"  · LOCKED LINE: \"{lk}\"")
        print()
    print("ELEMENTS (drawn across sources; build ONE new thing from them)\n")
    for n, (src, fact) in enumerate(picked, 1):
        print(f"  {n:2}. {fact}")
        print(f"      root: {src}")
    if gestures:
        print("\nCANDIDATE GESTURES (from the bank's curated list, struck items already removed; "
              "use at most one, or none)\n")
        for g in gestures:
            print(f"  · {g}")
    print(f"\n{len(picked)} element(s) across {len(pools)} roots. The figure is a composite: nobody real.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
