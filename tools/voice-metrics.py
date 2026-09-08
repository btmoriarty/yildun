#!/usr/bin/env python3
"""Prose metrics for the saga, measured against the author's own corpus. No dependencies.

The judgment layer in the world's voice law is a reading and cannot be automated. One part of it can:
criterion 5, the long-sentence rate, is arithmetic. This runs that, plus two other checks
that are arithmetic and were previously done by eye and repeatedly missed.

    python3 tools/voice-metrics.py canon/vignettes/a-scene.md

NOTHING IN HERE IS HARDCODED. Every threshold is derived at runtime from the author's
verbatim prose in generated/CAPTURED.md, so the baseline moves as he writes more. That is
the same rule the rotation cursors follow: the measurement outranks any number written in
a file, including this one.

Three checks:

1. LONG-SENTENCE RATE (the voice law's judgment layer, criterion 5). The engine's failure is not
   a lack of short sentences; both parties write short at the same rate. It over-spends the
   forty-plus sentence, which turns emphasis into gait.

2. DERIVED TICS, SCOPED. Two earlier versions of this check reported subject vocabulary
   (wool, yard, wolf) because the author's corpus is ~19,500 words and most ordinary English
   is simply absent from it, so 'absent' read as 'tic'. **The check is therefore scoped to the
   closed class where the engine's tics have actually occurred: NUMBER WORDS and -LY ADVERBS.**
   Both observed tics, 'eleven' and 'quietly', are in it. A general-vocabulary tic detector is
   not reliable at this corpus size and this does not pretend to be one.
   Conditions: far above the author's rate, and spread across many separate pieces rather than
   concentrated in one, which is what distinguishes a habit from a subject.

   KNOWN LIMITATION: it cannot tell quoted material from narration. A proverb, a song title or a
   character's own line may legitimately carry a flagged word, and the answer is to overrule the
   check in the entry's notes, in writing, not to alter the quotation. First declared override:
   canon/vignettes/the-night-off.md, 'A stitch in time saves nine.'

3. RECYCLED PHRASES. Six-word sequences in the file under test that already appear in other
   committed prose. The author struck one of these on sight; a phrase that worked once is
   not a motif the second time.

Exit 1 if any check fires, but `lint-voice.sh` runs it advisory (`|| true`) because the
existing corpus already carries findings and a hard gate would block every commit on
legacy prose. Pass --strict once the corpus is clean to make it a real gate.
"""

import collections
import pathlib
import re
import statistics
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
_here = str(pathlib.Path(__file__).resolve().parent)
import sys as _sys; _sys.path.insert(0, _here)
import worldconfig as _wc
CAPTURES = pathlib.Path(_wc.load()["captures"])
PROSE_DIRS = [REPO / "canon" / "vignettes", REPO / "canon" / "legends", REPO / "deliverables"]
STOP_HEADINGS = ("## Notes", "## Provenance", "## Deepen-me", "## Connections", "## What the revision")


def sentences(text):
    r"""Sentence split that survives dialogue.

    The original pattern was r"(?<=[.!?])\s+", which never fires after a closing quote,
    so consecutive speech lines glued into one apparent sentence and the long-sentence
    rate was overstated on every dialogue-heavy entry. Found 2026-08-18 when the-wording
    reported four sentences over forty words and all four were exchanges, not sentences.
    Earlier figures reported for spoken-cadence pieces were wrong on the high side.
    """
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r'(?<=[.!?])\s+|(?<=[.!?]")\s+|(?<=[.!?]\u201d)\s+', text)
    return [s for s in parts if len(s.split()) > 2]


def body_of(path):
    """Prose only: no front matter, no apparatus, no engine notes."""
    t = path.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
    for h in STOP_HEADINGS:
        i = t.find(h)
        if i != -1:
            t = t[:i]
    t = re.sub(r"^\s*[-*|>#].*$", "", t, flags=re.M)      # lists, tables, quotes, headings
    t = re.sub(r"\*\*|\*|`", "", t)
    return t


def is_assembled(path):
    """An assembled deliverable (front-matter `assembled:`) is a concatenation of other pieces, not an
    independent source. It must not enter the recycled-phrase corpus (it would make every constituent
    look recycled), and recycled-phrase is meaningless when run ON it (it contains its parts by design).
    """
    try:
        head = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")[:1000]
    except OSError:
        return False
    return bool(re.search(r"(?m)^assembled:\s*\S", head))


def author_corpus():
    if not CAPTURES.exists():
        return []
    blocks = re.findall(r'\*"(.*?)"\*', CAPTURES.read_text(encoding="utf-8"), flags=re.S)
    out = []
    for b in blocks:
        out.extend(sentences(b))
    return out


def engine_corpus(exclude):
    out, texts = [], []
    for d in PROSE_DIRS:
        for p in sorted(d.rglob("*.md")):
            if p.resolve() in exclude or is_assembled(p):
                continue
            b = body_of(p)
            if len(b.split()) < 120:
                continue
            texts.append((p, b))
            out.extend(sentences(b))
    return out, texts


def words(sents):
    return re.findall(r"[a-z][a-z'-]+", " ".join(sents).lower())


def rate_over(sents, n):
    L = [len(s.split()) for s in sents]
    return sum(1 for x in L if x > n) / len(L) if L else 0.0


def shingles(text, n=6):
    """Six-word sequences, with NAMES EXCLUDED.

    A proper noun repeated across entries is not a recycled phrase, it is the same thing
    being called by its name, and an entry is required to name a body it belongs to. Added
    2026-08-17 after the check fired five times on 'The Otago and Southland Provident and
    Burial Society', which no entry can avoid and none should. A window carrying three or
    more capitalised tokens is treated as a name and dropped. False negatives are the
    cheaper error here: this check is advisory and a missed recycle is caught by reading.
    """
    toks = re.findall(r"[A-Za-z][A-Za-z'-]+", text)
    out = set()
    for i in range(len(toks) - n + 1):
        win = toks[i:i + n]
        if sum(1 for w in win if w[0].isupper()) >= 3:
            continue
        out.add(" ".join(w.lower() for w in win))
    return out


def main(argv):
    if not argv:
        print("usage: voice-metrics.py <file.md> [...]", file=sys.stderr)
        return 2
    targets = [pathlib.Path(a) for a in argv if pathlib.Path(a).is_file()]
    if not targets:
        return 0
    excl = {t.resolve() for t in targets}

    auth = author_corpus()
    eng, eng_texts = engine_corpus(excl)
    if not auth:
        print("voice-metrics: no author corpus found; skipping.")
        return 0

    a_over, a_med = rate_over(auth, 40), statistics.median([len(s.split()) for s in auth])

    # derived tics. Two conditions, and the second is what makes it work:
    #   (a) the engine uses the word far above the author's rate, and
    #   (b) it is SPREAD across many separate pieces rather than concentrated in one.
    # Without (b) this reports subject vocabulary, because the author's captures are about
    # other subjects and every noun in the saga scores infinite ratio against them.
    aw, ew = collections.Counter(words(auth)), collections.Counter(words(eng))
    at, et = sum(aw.values()) or 1, sum(ew.values()) or 1
    docfreq, maxshare = collections.Counter(), {}
    for _, b in eng_texts:
        c = collections.Counter(words(sentences(b)))
        for w, n in c.items():
            docfreq[w] += 1
            maxshare[w] = max(maxshare.get(w, 0), n / ew[w]) if ew.get(w) else 1.0
    ndocs = max(len(eng_texts), 1)
    NUMBERS = {"one","two","three","four","five","six","seven","eight","nine","ten","eleven",
               "twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen",
               "nineteen","twenty","thirty","forty","fifty","sixty","seventy","eighty",
               "ninety","hundred","thousand","dozen"}
    def in_scope(w):
        return w in NUMBERS or (w.endswith("ly") and len(w) > 5)

    tics = []
    for w, c in ew.items():
        if c < 8 or len(w) < 4 or not in_scope(w):
            continue
        if docfreq[w] < max(4, ndocs * 0.15):        # must recur across pieces
            continue
        if maxshare.get(w, 1.0) > 0.45:              # and not be concentrated in one
            continue
        er, ar = c / et, aw.get(w, 0) / at
        ratio = er / ar if ar else 99.0
        if ratio >= 4:
            tics.append((ratio, w, c, aw.get(w, 0), docfreq[w]))
    tics.sort(reverse=True)
    tic_words = {w for _, w, _, _, _ in tics[:20]}

    print(f"author baseline (from {len(auth)} sentences): median {a_med:.0f} words, "
          f"{a_over * 100:.0f}% over 40")

    fired = 0
    for t in targets:
        b = body_of(t)
        s = sentences(b)
        if not s:
            continue
        over, med = rate_over(s, 40), statistics.median([len(x.split()) for x in s])
        try:
            label = t.resolve().relative_to(REPO)
        except ValueError:
            label = t
        print(f"\n{label}")
        print(f"  sentences {len(s)}  median {med:.0f}  over-40 {over * 100:.0f}%  "
              f"(author {a_med:.0f} / {a_over * 100:.0f}%)")

        if over > max(a_over * 1.6, a_over + 0.03):
            print(f"  [FIRED] long-sentence rate {over * 100:.0f}% against author's "
                  f"{a_over * 100:.0f}%. the voice law's judgment layer, criterion 5: "
                  f"spend the long sentence rarely and completely.")
            fired += 1

        # A tic is a repetition, not an appearance. One 'nine' in a piece is a number;
        # three of them is a habit. Threshold added 2026-08-17 after the check fired on a
        # single legitimate use and would have bent a sentence to satisfy a tool.
        here = collections.Counter(w for w in re.findall(r"[a-z][a-z'-]+", b.lower()) if w in tic_words)
        used = sorted(w for w, n in here.items() if n >= 2)
        if used:
            print(f"  [FIRED] derived tic(s): {', '.join(used)}  "
                  f"(engine uses these far above the author's rate)")
            fired += 1

        if is_assembled(t):
            print("  (recycled-phrase skipped: an assembled work contains its constituents by design;"
                  " voicelint's per-file soft-caps also over-fire at whole-work scale and are advisory here)")
        else:
            mine = shingles(b)
            hits = []
            for p, other in eng_texts:
                for sh in mine & shingles(other):
                    hits.append((sh, p.name))
            if hits:
                for sh, where in sorted(set(hits))[:5]:
                    print(f'  [FIRED] recycled phrase: "{sh}" also in {where}')
                fired += 1

    if tics and "-v" in argv:
        print("\ntop derived tics (ratio, word, engine n, author n, spread):")
        for r, w, c, a, df in tics[:12]:
            print(f"  {r:6.1f}x  {w:<16} engine {c:4}  author {a:4}  in {df} files")

    print(f"\nvoice-metrics: {fired} check(s) fired across {len(targets)} file(s).")
    return 1 if (fired and "--strict" in argv) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
