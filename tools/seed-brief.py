#!/usr/bin/env python3
"""seed-brief.py - turn an author note into a brief you cannot mimeograph.

Author, 2026-09-02: "we need to build something robust that uses my input as inspiration, not as a
mimeograph."

WHY THE DETECTORS ARE NOT ENOUGH. check-transcription now catches two failures: a span that restates
a note's words, and a sequence that walks a note's beats in order. Both fire AFTER the prose exists.
By then the draft has already been written next to the note, in the note's order, in the note's
vocabulary, and what follows is repair rather than authorship.

THE CONTAMINATION IS THE NOTE'S ORDER AND THE NOTE'S WORDS. So this removes both before drafting,
and hands back something that cannot be walked through.

  1. ATOMISE. The note is split into single facts. A fact is one thing that happened, one state, or
     one thing somebody said.
  2. SHUFFLE, deterministically, seeded from the note's own hash so the same note always produces the
     same brief and two people get the same one. The author's sequence is destroyed on purpose. If a
     chronology matters it has to be rebuilt from the facts, which is the work.
  3. FLAG HIS VOCABULARY. Words that are distinctive to him ("retort", "stewing", "wiped out") are
     listed separately as NOT FOR NARRATION. They may be spoken by a character or quoted in
     frontmatter. Reused in narration they are the tell, and they are how a rebuild stays a rewording.
  4. LEAVE THE DOWNSTREAM SLOTS EMPTY. Each fact gets a blank line for what it implies that he did not
     say. That is the half the corpus calls inspiration: grow consequences from his facts, never
     invention beside them.

THEN COVERAGE, NOT FIDELITY. `--cover` checks the finished prose contains every fact, and says which
are missing. It deliberately does not check that they appear in order, because appearing in order is
the failure this tool exists to prevent.

Usage:
  seed-brief.py FILE.md              brief from the file's recorded author corrections
  seed-brief.py --note "text"        brief from a note pasted directly
  seed-brief.py --cover FILE.md      which recorded facts are missing from the prose
"""
import hashlib
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_ct = __import__("importlib").import_module("importlib.util")
_spec = _ct.spec_from_file_location("ct", os.path.join(HERE, "check-transcription.py"))
ct = _ct.module_from_spec(_spec); _spec.loader.exec_module(ct)
import worldconfig as _wc

# Words common enough that reusing them is not a tell. Everything rarer that the author used is
# flagged, because his unusual word is exactly the one a rewording reaches for.
COMMON = set("""about after again all also and any are back because been before being both but came
come could did does down each even every first from get going good got had has have her here him
his how into just know like little long made make many more most much must never new now off one
only other our out over own said same see she should since some still such take than that the their
them then there these they thing think this those time too took two under until upon very was way
we well went were what when where which while who will with would you your car night day house room
door bed hand hands eye eyes water street month later last time back""".split())


def atoms(note):
    """One fact per line. Splits on sentence ends and on coordinating joins that carry a new fact."""
    out = []
    for s in re.split(r"(?<=[.!?])\s+", note.strip()):
        s = " ".join(s.split())
        if not s:
            continue
        parts = re.split(r",\s+(?:and|but|though|so)\s+|\s+;\s+", s)
        for p in parts:
            p = p.strip(" .,;")
            if len(ct.content_words(p)) >= 2:
                out.append(p)
    return out


def corpus_freq():
    """How often each word appears across existing derivation prose.

    THE HAND-WRITTEN COMMON LIST WAS THE WRONG INSTRUMENT and first use proved it: brown, green,
    chair, family, money and star were all flagged as the author's distinctive vocabulary, which
    would have banned the colour of the trousers. Rarity is measurable instead of guessable, so it is
    measured against the prose this project already has.
    """
    import glob
    freq = {}
    for f in glob.glob(os.path.join(_wc.load()["corpus_dir"], "*.md")):
        try:
            body = ct.split_doc(open(f, encoding="utf-8").read())[1]
        except OSError:
            continue
        for w in re.findall(r"[A-Za-z']{4,}", body):
            lw = w.lower()
            freq[lw] = freq.get(lw, 0) + 1
    return freq


def his_words(note):
    """Distinctive words he used, minus proper nouns.

    A name has to be writable: the prose cannot avoid a character's name and should not try. A word
    is treated as a proper noun when it appears capitalised somewhere other than after a full stop,
    which is crude and errs toward letting a word through rather than banning a name.
    """
    proper = set()
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z']{2,})\b", note):
        proper.add(m.group(1).lower())
    seen = set()
    for w in re.findall(r"[A-Za-z']{4,}", note):
        lw = w.lower().rstrip("'s")
        if lw in COMMON or lw in ct.STOP or lw in proper:
            continue
        if lw.rstrip("s") in proper or (lw + "s") in proper:
            continue
        # Rare in the corpus means distinctive. A word the prose already uses freely is not his tell.
        if FREQ.get(lw, 0) > 3:
            continue
        seen.add(lw)
    return sorted(seen)


# A note about the DRAFT is not a fact about the WORLD. A correction of a previous build ("no, not
# the blue car, the grey one") and a note about the process ("you are taking my input as dictation")
# are neither of them material for the page, and counting them makes a finished piece look half-written.
# A note ABOUT the draft or its placement is not a fact about the WORLD, and both leak into a brief
# and a coverage count as though they were material. Two families:
#   corrections/process: "wrong", "no, not the blue car, the grey one", "you are parroting again"
#   labels/placement:    "that detail was with the earlier group", "I forgot X which belonged in the last group"
# Widened after a placement note ("I forgot X... belonged in the last group") came through as a fact,
# because the old pattern only covered the first family and only ran in cover().
META = re.compile(
    r"^(wrong|nope|no,|not \w+'s|er,|again,|i forgot)\b|"
    r"\b(you are|you're|didn't acknowledge|doesn't need|transcrib|dictation|"
    r"ai.?ism|voice pass|reprint|print the|show me)\b|"
    r"\b(belong(s|ed)?|placed?|goes)\s+(in|with|to|before|after)\s+the\s+"
    r"(last|next|first|this|same)?\s*(group|run|phase|entry|piece|batch|story)\b|"
    r"\bwill be called\b|\bthis (room|beat|entry|piece) (is|was|belongs)\b|"
    # Disambiguation asides. "Not Sarah from his apartment in New Haven, but Sarah whom he knew from
    # Yale" is the author telling the engine WHICH person, not a fact for the page. Transcribed once
    # into prose as "not the Sarah from the New Haven apartment but the other one", which no one would
    # write. It is bookkeeping and belongs in front matter. Added 2026-09-05.
    r"\bnot\s+(?:the\s+)?\w+\s+(?:from|of)\s+.+?\bbut\s+(?:the\s+)?\w+\b|"
    r"\bnot\s+the\s+\w+\s+.*?\bbut\s+the\s+other\s+one\b",
    re.I)


def is_meta(note):
    return bool(META.search(note.strip()))


FREQ = corpus_freq()


def notes_of(path):
    text = open(path, encoding="utf-8").read()
    fm, _ = ct.split_doc(text)
    notes = ct.notes_from(fm)
    # check-transcription's notes_from caps a quoted span at 600 chars, so a long verbatim drop
    # (a whole beat pasted into author_supply) is skipped entirely and brief() gets nothing. That is
    # exactly when the engine falls back to drafting from the running account in the author's order,
    # which is the parrot. Recover the long quotes here, without the cap, so long drops atomise like
    # short ones. Fixed 2026-09-03 after repeated parroting on long captures.
    flat = " ".join(fm.split())
    for m in re.finditer(r'"([^"]{600,})"', flat):
        notes.append(m.group(1))
    for m in re.finditer(r'[\u201c]([^\u201d]{600,})[\u201d]', flat):
        notes.append(m.group(1))
    return notes


def brief(notes):
    # DEDUPE. notes_from returns both a long span and its constituent sentences, by design, so a
    # multi-sentence note arrives twice and atomises twice. First real use produced 37 facts from
    # about twenty. Order-preserving dedupe on the normalised text.
    facts, seen = [], set()
    for n in notes:
        if is_meta(n):
            continue
        for f in atoms(n):
            k = " ".join(f.lower().split())
            if k not in seen:
                seen.add(k); facts.append(f)
    if not facts:
        print("seed-brief: no author facts found."); return 1
    seed = int(hashlib.sha256(" ".join(facts).encode()).hexdigest()[:8], 16)
    order = list(range(len(facts)))
    random.Random(seed).shuffle(order)
    print("FACTS, in an order that is not his. Rebuild the sequence yourself.\n")
    for n, i in enumerate(order, 1):
        print(f"  {n:2}. {facts[i]}")
        print(f"      downstream: ")
    vocab = sorted({w for n in notes for w in his_words(n)})
    if vocab:
        print("\nHIS WORDS. Not for narration. A character may say them; you may not write them.\n")
        for i in range(0, len(vocab), 6):
            print("  " + "  ".join(vocab[i:i + 6]))
    print(f"\n{len(facts)} fact(s). Coverage is the test, order is not.")
    return 0


def cover(path):
    text = open(path, encoding="utf-8").read()
    fm, body = ct.split_doc(text)
    facts = []
    for n in ct.notes_from(fm):
        if is_meta(n):
            continue
        facts.extend(atoms(n))
    facts = list(dict.fromkeys(facts))
    body_stems = {ct._stem(w) for w in ct.content_words(body)}
    clear, verify = [], []
    for f in facts:
        fw = {ct._stem(w) for w in ct.content_words(f)}
        if not fw:
            continue
        (clear if len(fw & body_stems) / len(fw) >= 0.34 else verify).append(f)
    # THIS ASKS, IT DOES NOT DECIDE, and the reason is the whole point of the tool. Coverage is
    # measured by shared words, and a fact rebuilt properly shares few. A low score is therefore
    # ambiguous between "absent" and "built well", and a checker that called it absent would be
    # punishing the behaviour this tool exists to produce. So it prints a list to read.
    print(f"{len(clear)} of {len(facts)} fact(s) are present in words the author used.")
    if verify:
        print(f"\n{len(verify)} to VERIFY BY EYE. Each is either absent, or built well enough that "
              f"its words are gone. Only reading tells you which.\n")
        for v in verify:
            print(f"  ?  {v}")
    return 0


def main(argv):
    if not argv:
        print(__doc__); return 2
    if argv[0] == "--cover":
        return cover(argv[1])
    if argv[0] == "--note":
        return brief([argv[1]])
    return brief(notes_of(argv[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
