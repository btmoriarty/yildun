#!/usr/bin/env python3
"""surface-material.py - help the author find material: latent stories in what exists, or new material.

Two modes, per the author's ask (2026-09-06):

  --discover (default): stories already IMPLIED by the corpus but not yet built. It mines signals other
    tools do not: unresolved [[links]] (entries the world keeps pointing at but has never built), open
    Deepen-me seeds (each piece's own next-questions, minus the ones marked never-to-answer, which are
    protected drift), and the dropped-but-unbuilt PENDING roster. Points to recommend.py (carrier
    clusters) and beat-manifest.py (unbuilt captured beats) for the angles they already cover.

  --elicit: generative prompts for NEW material, using worldbuild's interrogation protocol (present
    tense, the periphery, procedure over summary, the gap). Generative, never investigative: it asks
    for material the corpus does NOT have, and it themes a few prompts by the thinnest threads so the
    new material lands where the world is sparest. Read references/INTERROGATION.md for the full ritual.

It surfaces and asks; it does not write, build, or resolve a drift (canon rule two). The author decides
what becomes a story.

    surface-material.py                 latent stories in the corpus
    surface-material.py --elicit        prompts for new material
    surface-material.py --n 12          how many items per section
"""
import argparse
import glob
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_iu = __import__("importlib").import_module("importlib.util")
_s = _iu.spec_from_file_location("pm", os.path.join(HERE, "provenance-map.py"))
pm = _iu.module_from_spec(_s); _s.loader.exec_module(pm)
_sr = _iu.spec_from_file_location("rc", os.path.join(HERE, "recommend.py"))
rc = _iu.module_from_spec(_sr); _sr.loader.exec_module(rc)
CFG = pm.CFG

PROTECT = re.compile(r"never|do not answer|don't answer|keep .*drift|not to be answered|unanswer", re.I)
LAWFILE = re.compile(r"^\d\d-.*\.md$")  # numbered canon law/reference (00-*.md .. 09-*.md)
CODE = re.compile(r"`[^`]*`|```.*?```", re.S)  # inline + fenced code spans
NAME = re.compile(r"^[A-Z][A-Za-z.'-]+(?: [A-Z][A-Za-z.'-]+){0,2}$")  # a clean 1-3 token name


def all_md(include_law=False):
    """Canon entries + derivations. By default the numbered canon law/reference files are excluded:
    they DEFINE the [[link]]/Deepen-me conventions and quote them as syntax examples, so scanning
    them yields the tool's own vocabulary as false latents (the same reason lint-voice.sh excludes
    them). Pass include_law=True to still count them as RESOLVABLE targets: a cross-reference to
    [[07-masks]] resolves to a real file and is not a latent story."""
    out = set(glob.glob(os.path.join(CFG["corpus_dir"], "*.md")))
    out |= set(glob.glob(os.path.join(CFG["canon_dir"], "**", "*.md"), recursive=True))
    return sorted(out if include_law else (f for f in out if not LAWFILE.match(os.path.basename(f))))


REGISTRY_DEG = 24  # a file linking to this many entries is an index/register (the object register is
# the lone case today at 48; the richest actual story sits at 17), not a story. It is dropped from the
# connective graph in both roles: as a source it would tie every entry it lists into a false cluster,
# and as a target ("pieces that reference the object register") it is a structural reference, not a
# latent story. Set well above the story range (median 6, p90 12) so growth does not catch a real entry.


def stem(f):
    return os.path.splitext(os.path.basename(f))[0].lower()


def _links_in(f):
    txt = CODE.sub("", open(f, encoding="utf-8").read())  # a [[link]] inside code is documentation
    return {m.group(1).strip().lower().replace(" ", "-") for m in
            re.finditer(r"\[\[([^]|]+)(?:\|[^]]*)?\]\]", txt)}


def registry_stems(files):
    return {stem(f) for f in files if len(_links_in(f)) >= REGISTRY_DEG}


def link_graph(files):
    """entity -> set of piece-stems that link to it (self-links and index/register files dropped)."""
    reg = registry_stems(files)
    ent = {}
    for f in files:
        base = stem(f)
        if base in reg:
            continue
        for tgt in _links_in(f):
            if tgt and tgt != base and tgt not in reg:
                ent.setdefault(tgt, set()).add(base)
    return ent


def unresolved_links(files):
    stems = {stem(f) for f in all_md(include_law=True)}
    return sorted(((t, len(ps)) for t, ps in link_graph(files).items() if t not in stems),
                  key=lambda x: (-x[1], x[0]))


def implied_stories(files, lo=2, hi=8):
    """An entity that ties LO..HI built pieces together is a latent story: the corpus keeps returning
    to it, but the story running BETWEEN those specific pieces through it has never been written. The
    mega-hubs (the world's spine, tying dozens of pieces) are excluded by the HI ceiling: they are the
    world itself, not a discoverable new story."""
    stems = {stem(f) for f in all_md(include_law=True)}
    hubs = [(t, sorted(ps), t in stems) for t, ps in link_graph(files).items() if lo <= len(ps) <= hi]
    hubs.sort(key=lambda x: (-len(x[1]), x[0]))
    omitted = sum(1 for t, ps in link_graph(files).items() if len(ps) > hi)
    return hubs, omitted


def deepen_seeds(files):
    seeds = []
    for f in files:
        txt = open(f, encoding="utf-8").read()
        m = re.search(r"(?ims)^#*\s*Deepen-me\b(.*?)(?=\n#{1,6}\s|\Z)", txt)
        if not m:
            continue
        for line in re.findall(r"(?m)^\s*[-*]\s+(.+)$", m.group(1)):
            line = line.strip()
            if line and not PROTECT.search(line):
                seeds.append((os.path.basename(f), line))
    return seeds


def main(argv):
    ap = argparse.ArgumentParser(description="Surface material: latent stories, or prompts for new material.")
    ap.add_argument("--discover", action="store_true", help="latent stories in the corpus (the default)")
    ap.add_argument("--elicit", action="store_true", help="generative prompts for new material")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--hub-ceiling", type=int, default=8,
                    help="an entity tying more than this many pieces is world-spine, not a latent story")
    args = ap.parse_args(argv)
    files = all_md()

    if not args.elicit:
        print("MATERIAL, DISCOVERED (latent in the corpus; you decide what becomes a story)\n")

        hubs, omitted = implied_stories(files, hi=args.hub_ceiling)
        print(f"IMPLIED STORIES ({len(hubs)} entities that tie 2+ built pieces together; the story "
              f"running BETWEEN them, through the shared thing, is untold):")
        for tgt, pieces, built in hubs[:args.n]:
            tag = "" if built else "  [no entry of its own -- the world circles it but never wrote it]"
            print(f"  [[{tgt}]] ties {len(pieces)}:{tag}")
            print(f"      {', '.join(pieces)}")
        if omitted:
            print(f"  ({omitted} mega-hub(s) over {args.hub_ceiling} pieces omitted: those are the "
                  f"world's spine, not a single latent story.)")

        links = unresolved_links(files)
        print(f"\nUNRESOLVED [[links]] ({len(links)} entities the world points at but has never built "
              f"at all -- missing nodes, not connective stories):")
        for tgt, n in links[:args.n]:
            print(f"  {n:>3}x  [[{tgt}]]")
        seeds = deepen_seeds(files)
        rng = __import__("random").Random(len(seeds))
        rng.shuffle(seeds)
        print(f"\nOPEN DEEPEN-ME SEEDS ({len(seeds)} buildable; a sample):")
        for src, line in seeds[:args.n]:
            print(f"  [{src}] {line[:96]}")
        roster = rc.pending_roster()
        if roster:
            print(f"\nDROPPED BUT NOT BUILT (PENDING, {len(roster)}):")
            for it in roster[:args.n]:
                print(f"  {it[:90]}")
        print("\nSee also: recommend.py (carrier/novella clusters), beat-manifest.py (unbuilt captured "
              "beats), recombine.py (fuse any two into a new de-identified story),")
        print("and spec/THE-MACHINES.md -- the recurring mechanisms (M1-M8) a built story can be RE-RUN "
              "in a place that is not yours, which is a third kind of new story from old material.")
        return 0

    # elicit: prompts for NEW material, themed by the thinnest threads
    clusters = {}
    for p, fm in rc.memory_pieces():
        for c in rc.carriers(fm):
            if NAME.match(c):  # a clean name reads in a prompt; a descriptive carrier phrase does not
                clusters.setdefault(c.lower(), {"name": c, "n": 0})["n"] += 1
    thin = sorted(clusters.values(), key=lambda c: c["n"])[:4]
    seeds = deepen_seeds(files)
    __import__("random").Random(len(seeds)).shuffle(seeds)

    protocol = os.path.join(os.path.dirname(HERE), "references", "INTERROGATION.md")
    print("PROMPTS FOR NEW MATERIAL (generative, one at a time; the full ritual is in\n"
          f"{protocol})\n")
    print("These ask for what the corpus does NOT have. Answer whichever pulls; a gap is the room the")
    print("story gets built in, not evidence to recover.\n")
    print("PRESENT TENSE (zero retrieval, gets you talking in specifics):")
    print("  - What is on the shelf you can see from where you are sitting right now?")
    print("  - What is the weather doing, and what will you eat tonight?")
    print("\nPERIPHERY (not the protagonist, the edges of a scene you have already given):")
    for t in thin[:2]:
        print(f"  - In the {t['name']} material: who was in the room that you have never described?")
    print("  - Whose face do you remember from a place already in the world, that no piece names?")
    print("\nPROCEDURE (how a thing was actually done, step by step, not summarised):")
    print("  - Walk one ordinary task from that time end to end: the hands, the order, what went wrong.")
    print("\nTHE GAP (name what you still do not know, and leave it unresolved):")
    for src, line in seeds[:2]:
        print(f"  - A piece asks: \"{line[:80]}\" ({src}). What is the smallest true thing you can add?")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
