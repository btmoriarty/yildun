#!/usr/bin/env python3
"""compose-brief.py - turn a drop of free-association notes into a brief you WRITE FROM.

The narrative-compiler front end. The parrot is a function of the input: when the author's
sentences are in front of the writer, the writer walks them, in his order, with synonyms, and no
gate reliably catches the disguised version. So this destroys, in the input, everything that
enables the walk, while keeping every fact and naming the forbidden moves:

  - ATOMISE to single facts and SHUFFLE them (reused from seed-brief), so there is no sequence.
  - STRIP his sequence cues ("After ...", "Then", "In the mean time", "A few nights later", "By
    this time"), so the order cannot be reconstructed even from what is left.
  - FLAG his distinctive phrasings (reused from seed-brief), which narration may not use.
  - Optionally DENATURE each fact through a local model, replacing his wording entirely, so there
    is no phrasing left to copy. Off by default; needs ollama; falls back loudly.
  - Emit the COMPOSE DIRECTIVES: the influence mix and the identity policy, and the two governing
    rules, so the write is instructed rather than improvised.

The writer then composes FROM THE BRIEF, with the drop closed, and the draft is checked against
the raw drop by check-transcription (the dictation gate). Intake here, gate there, writing between.

WORLD-AGNOSTIC. Nothing saga-specific lives in this file. The influence set, the identity/masking
policy and the corpus all arrive by argument or from the world's own config, so the same engine
runs against any world a student points it at. This is the public half; the private world stays
private.

    compose-brief.py NOTES.md
    compose-brief.py NOTES.md --influence "28 Serling / 16 Carver / 32 Stephenson / 14 Proust"
    compose-brief.py NOTES.md --identity mask
    compose-brief.py NOTES.md --denature            # rewrite wording via local model (ollama)

NOTES may be a bible entry with quoted author spans in its front matter, or a plain text file of
raw notes. Either way only the author's material is read; process/placement notes are dropped.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Reuse the intake that already exists rather than fork it.
sb = _load("seed_brief", "seed-brief.py")
ct = _load("check_transcription", "check-transcription.py")

# Leading sequence cues. Stripped so a shuffled fact cannot be re-sorted by its own timestamp.
# This is the piece seed-brief lacks: it scrambles order but leaves "A few nights later" sitting on
# the fact, which hands the order straight back.
SEQ = re.compile(
    r"^(?:"
    r"and\s+|but\s+|then\s+|so\s+|"
    r"after(?:ward)?s?\b|before\b|next\b|soon\s+after\b|later\b|meanwhile\b|"
    r"in\s+the\s+mean\s?time\b|at\s+(?:one|some)\s+point\b|around\s+then\b|"
    r"a\s+few\s+(?:nights?|days?|weeks?|months?|years?)\s+(?:later|on|after)\b|"
    r"the\s+(?:first|second|third|last|next)\s+time\b|"
    r"by\s+(?:this|that)\s+time\b|"
    r"toward(?:s)?\s+the\s+(?:end|start|beginning)\s+of\s+\w+\b|"
    r"when\s+\w+\s+came\b|"
    r"that\s+(?:spring|summer|fall|autumn|winter|night|week|month|year|day|morning|evening)\b|"
    r"in\s+(?:early|late|mid)?\s*\w*\s*(?:19|20)\d\d\b"
    r")[\s,]*",
    re.I,
)


def destamp(fact):
    """Strip one or more leading sequence cues, and recapitalise."""
    prev = None
    f = fact
    while f != prev:
        prev = f
        f = SEQ.sub("", f, count=1).lstrip(" ,")
    return (f[:1].upper() + f[1:]) if f else fact


def notes_from_source(path):
    """A bible entry (quoted spans in front matter) or a plain notes file. Either way, author-only."""
    if not os.path.exists(path):
        sys.exit(f"compose-brief: no such file: {path}\n"
                 f"  Point it at a real notes file (absolute path). To make one from a drop:\n"
                 f"    printf '%s' \"<your notes>\" > /path/to/your/notes.txt")
    if os.path.isdir(path):
        sys.exit(f"compose-brief: {path} is a directory, not a notes file.")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        sys.exit(f"compose-brief: cannot read {path}: {e}")
    fm, _ = ct.split_doc(text)
    if fm.strip():
        notes = sb.notes_of(path)
        if notes:
            return notes
    # Plain notes file: the whole thing is one note.
    return [text]


def denature(fact):
    """Replace his wording with neutral wording, keeping who/what/where. Local model, optional.

    Returns a clean one-line English rewrite, or None. None means the caller marks the fact "his
    words, do not copy": a missing denature is a weaker brief, never a broken one, and never a
    silent pass-through of his phrasing. The guards below reject the ways a local model fails loudly
    (server down, refusal, non-English drift, preamble).

    THE RISK THE GUARDS DO NOT CATCH is quiet fact-drift: a local model will occasionally alter a
    detail while rephrasing ("the back of his car" came back as "her car" in testing). Denature
    trades phrasing-parrot for that risk, which is why it is opt-in and off by default, and why the
    deterministic brief (shuffle + sequence-strip + forbidden vocab) is the reliable path. Use
    denature when phrasing-parrot is the live danger and verify the facts survived.
    """
    prompt = (
        "Rewrite this single fact in plain, neutral words. Keep exactly who did what to whom and "
        "where. Change the phrasing completely: no distinctive words from the original. Respond in "
        "English only, one sentence, no preamble, no alternatives, no explanation. Reply with the "
        "rewritten fact only.\n\nFACT: " + fact
    )
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    if not host.startswith("http"):
        host = "http://" + host
    model = os.environ.get("COMPOSE_BRIEF_MODEL", "qwen2.5:14b")
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    try:
        # The HTTP API returns the whole answer as clean JSON: no streaming, no ANSI cursor codes,
        # none of the partial-word redraw that mangles `ollama run` piped through a pipe. stdlib only.
        req = urllib.request.Request(host + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read()).get("response", "")
    except (urllib.error.URLError, OSError, ValueError):
        return None
    # A reasoning model may still wrap its thinking; keep only the answer.
    out = re.sub(r"(?is)<think>.*?</think>", " ", out)
    out = re.split(r"(?i)\.\.\.\s*done thinking\.?", out)[-1]
    out = " ".join(out.split()).strip().strip('"')
    if not out:
        return None
    # A censored model refuses explicit facts, which are the ones most in need of denaturing. A
    # refusal is a failure: mark the fact unsafe rather than pass the refusal off as a rewrite.
    if re.search(r"(?i)\b(i'?m sorry|can'?t (help|assist|do that)|cannot (help|assist|comply)|"
                 r"as an ai|disallowed|against .* policy|i (can'?t|cannot|won'?t) (help|assist))", out):
        return None
    # Fail safe on model drift. A local model sometimes answers in another script, or adds preamble
    # and several alternative rewrites. None of that may enter the brief as if it were the fact, so
    # reject non-Latin output and anything much longer than the original (the tell of a preamble).
    if re.search(r"[^\x00-ɏ]", out):        # anything past Latin Extended-B is not a rewrite
        return None
    if len(out.split()) > 2 * len(fact.split()) + 8:
        return None
    return out


def build_facts(notes):
    facts, seen = [], set()
    for n in notes:
        if sb.is_meta(n):
            continue
        for f in sb.atoms(n):
            f = destamp(f)
            if len(ct.content_words(f)) < 2:
                continue
            k = " ".join(f.lower().split())
            if k not in seen:
                seen.add(k)
                facts.append(f)
    return facts


def main(argv):
    ap = argparse.ArgumentParser(description="Turn a drop of notes into a brief to write from.")
    ap.add_argument("source", help="a bible entry (.md) or a plain notes file")
    ap.add_argument("--influence", default="", help='e.g. "28 Serling / 16 Carver / 32 Stephenson"')
    ap.add_argument("--identity", choices=["keep", "mask"], default="keep")
    ap.add_argument("--denature", action="store_true", help="rewrite wording via local model")
    args = ap.parse_args(argv)

    notes = notes_from_source(args.source)
    facts = build_facts(notes)
    if not facts:
        print("compose-brief: no author facts found in", args.source)
        return 1

    seed = int(hashlib.sha256(" ".join(facts).encode()).hexdigest()[:8], 16)
    order = list(range(len(facts)))
    random.Random(seed).shuffle(order)

    denatured = None
    if args.denature:
        denatured = {}
        failed = 0
        for i in order:
            d = denature(facts[i])
            if d is None:
                failed += 1
            else:
                denatured[i] = d
        if failed:
            print(f"# denature: model unavailable or errored on {failed}/{len(facts)} "
                  f"facts; those are shown in his words and are UNSAFE to copy.\n", file=sys.stderr)

    infl = args.influence.strip() or "faithful: the world's register only, no writer styling"
    ident = ("identities preserved exactly: change no name, no role, and no account of who did "
             "what to whom" if args.identity == "keep"
             else "mask real identities per the world's masking map before writing; flag any name "
             "you are unsure of and do not guess")

    print("COMPOSE BRIEF —", os.path.basename(args.source))
    print("influence :", infl)
    print("identity  :", ident)
    print()
    print("TWO RULES THAT GOVERN THE WRITE")
    print("  1. Nothing rootless. Every sentence traces to a fact below. Infer downstream")
    print("     (two facts imply a third), never sideways (a relation that exists only in the")
    print("     sentence).")
    print("  2. Close nothing. Do not resolve a held question or answer what the notes leave open.")
    print()
    print("WRITE FROM THESE, NOT FROM HIS ACCOUNT. The order is scrambled and the sequence cues are")
    print("stripped on purpose. Reconstruct the shape yourself. Do not walk the list.")
    print()
    print("FACTS (orderless)\n")
    for n, i in enumerate(order, 1):
        line = denatured.get(i) if denatured else facts[i]
        if denatured and i not in denatured:
            print(f"  {n:2}. [his words, do not copy] {facts[i]}")
        else:
            print(f"  {n:2}. {line}")

    vocab = sorted({w for n in notes for w in sb.his_words(n)})
    if vocab:
        print("\nFORBIDDEN PHRASINGS. His distinctive words. A character may say them; narration may")
        print("not write them.\n")
        for i in range(0, len(vocab), 6):
            print("  " + "  ".join(vocab[i:i + 6]))

    print(f"\n{len(facts)} fact(s). Coverage is the test; order and wording are yours.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
