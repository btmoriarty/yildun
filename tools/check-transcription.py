#!/usr/bin/env python3
"""Catch the author's notes being written into the prose instead of built into it.

Author, 2026-08-30, twice in one session, then: "You have a tendency to literally transcribe my
words into sentences rather than use them as inspiration for story crafting."

The failure is specific. His notes arrive beside the text being edited, so the engine locates the
wrong sentence and swaps in a sentence that SAYS what he said. His phrasing leaks straight through.
Worse, his notes are often VERDICTS ("clearly flaunting her ass", "but that didn't matter") rather
than facts, and a verdict written down is the reader being told the conclusion instead of being
given what causes it.

Two independent detectors, because neither alone catches the set:

  NOTE-ECHO   Prose sentences that share content words with a quoted author note in the same
              file's frontmatter. IT SEES NOTHING THAT IS NOT WRITTEN THERE, so an author
              correction that arrives in conversation is invisible to it. 2026-09-02: two
              corrections were echoed back as sentences while this reported zero, for that reason.
              **Record author corrections verbatim in the frontmatter BEFORE rebuilding.** Once the
              note was present the checker caught the echo it had been blind to. Catches the direct lifts ("he didn't own any sheets" ->
              "He did not own sheets"; "all mouth no hands" -> "It was all mouth. She did not
              use her hands at all.")

  VERDICT     Evaluative vocabulary in narration. Catches the rewrites that share no words with
              the note but still assert its conclusion ("clearly flaunting" -> "there was no
              question at all about what she was showing him"). Skipped inside dialogue, because
              a character may say any of it.

Advisory by default so legacy files do not block a commit. --strict promotes everything to a failure.

  ONE VERDICT BLOCKS ON ITS OWN, ALWAYS: a shape-echo of >= PARROT_BLOCK_BEATS beats. That is the
  author's dictation walked through in his order, and it is the failure this whole file exists to stop.
  Everything else stays advisory. Calibrated 2026-09-04 against a deliberate parrot (fired at 12) and
  the author-approved derivations (topped out at 3-4).

  This detector was BLIND to it until 2026-09-04: notes_from capped quoted spans at 600 chars, so a
  long verbatim drop pasted into frontmatter matched nothing and the parrot check ran against an empty
  note list. The cap is gone. A clean run on a long-drop piece before that date proved nothing.
"""
import re
import sys

# A single author note walked through in order, this many beats or more, is dictation, not
# derivation, and it BLOCKS. Calibrated 2026-09-04: a deliberate parrot of a full drop fired at 12
# beats; author-approved derivations (over-for-good, dead-and-buried) topped out at 3-4, which is the
# unavoidable micro-order inside one of his sentences. 6 sits clear of both with margin.
PARROT_BLOCK_BEATS = 6

STOP = set("""a an and the of to in on at it its is was were be been being am are as by for from
her him his she he they them their there here that this those these with without into onto out up
down over under back off but or nor so if then than when while who whom which what where why how
not no did do does done had has have having i you we us our your my me not one two all any some
each every both few more most other same very can will just should now about after before
again against between during through above below only such too also got get gets getting go goes
didn't don't doesn't wasn't isn't weren't aren't wouldn't couldn't hadn't haven't hasn't won't can't
it's that's there's he's she's i'm i'd you're they're
went gone come comes came make makes made take takes took put puts kept keep like way thing things
time times said say says""".split())

VERDICT = [
    (r"\bno question\b", "no question"),
    (r"\b(?:made|makes|making) (?:it|that|this) (?:entirely |perfectly |quite |completely |very )?clear\b", "made it clear"),
    (r"\bit (?:did|does) ?n[o']t matter\b", "it did not matter"),
    (r"\bwas ?n[o']t (?:the )?point\b", "wasn't the point"),
    (r"\bwhich (?:is|was) (?:the )?(?:whole |entire |real )?point\b", "which is the point"),
    (r"\bthere (?:was|is) no (?:doubt|mistaking|hiding)\b", "there was no doubt"),
    (r"\bclearly\b", "clearly"),
    (r"\bobviously\b", "obviously"),
    (r"\bcertainly\b", "certainly"),
    (r"\bunmistakab\w+", "unmistakably"),
    (r"\bof course\b", "of course"),
    (r"\bneedless to say\b", "needless to say"),
]


def split_doc(text):
    """Return (frontmatter, body). Frontmatter is between the first two --- lines."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[4:end], text[end + 5:]
    return "", text


def notes_from(frontmatter):
    """Author notes are recorded in frontmatter as quoted spans. Collect them."""
    flat = " ".join(frontmatter.split())
    out = []
    # BOUNDARY-AWARE. A naive pair-them-in-sequence walk breaks completely on a single unpaired
    # quote: every pair after it is off by one, and the "notes" become spans running across
    # unrelated YAML keys. That is how a 44-word author note sat in a file's frontmatter on
    # 2026-08-30 and was never compared against anything. An opening quote must follow
    # whitespace or an opener; a closing quote must precede whitespace or punctuation.
    for m in re.finditer(r'(?:(?<=\s)|(?<=[:(\[])|^)"([^"]{12,})"(?=[\s,.;:)\]]|$)', flat):
        out.append(m.group(1))
    for m in re.finditer(r'[“]([^”]{12,})[”]', flat):
        out.append(m.group(1))
    # A SHORT note is an instruction and is the failure surface. A LONG quoted span is usually
    # the author's own transcribed capture, which the prose is SUPPOSED to render, so comparing
    # against the whole of it would flag the work for doing its job.
    #
    # BUT A LONG NOTE CAN STILL BE AN INSTRUCTION. 2026-08-30: a 44-word note explaining why she
    # worked a library desk was restated almost verbatim in the prose and this check missed it,
    # because the whole span was over the cap. So long spans are split into sentences and each
    # sentence is a candidate on its own. The dominance ratio is what keeps a legitimate rendering
    # of a captured sentence from firing.
    notes = []
    for n in out:
        if len(n.split()) <= 25:
            notes.append(n)
            continue
        for part in re.split(r"(?<=[.!?])\s+", n):
            if len(content_words(part)) >= 4 and len(part.split()) <= 25:
                notes.append(part.strip())
        # AND KEEP THE LONG SPAN ITSELF. A ratio cannot see a long note being restated across
        # three sentences: nine shared content words against a forty-word note is only 0.5
        # coverage and slips under the bar, which is exactly how the library-desk restatement
        # got past this check on 2026-08-30. Long spans get an ABSOLUTE test instead.
        notes.append(n)
    return notes


IRREGULAR = {"saw": "see", "seen": "see", "knew": "know", "known": "know", "felt": "feel",
             "held": "hold", "told": "tell", "left": "leave", "meant": "mean", "sat": "sit",
             "stood": "stand", "wore": "wear", "worn": "wear", "drove": "drive", "rode": "ride"}


def _stem(t):
    if t in IRREGULAR:
        return IRREGULAR[t]
    for suf in ("ings", "ing", "edly", "ed", "ies", "s", "es"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            base = t[: -len(suf)]
            return base + "y" if suf == "ies" else base
    return t


def content_words(s):
    toks = re.findall(r"[a-z']+", s.lower())
    return {_stem(t) for t in toks if len(t) > 2 and t not in STOP}


def sentences(body):
    """Yield (line_no, sentence). Skips headings, blockquotes and list machinery."""
    for i, line in enumerate(body.splitlines(), start=1):
        t = line.strip()
        if not t or t.startswith(("#", ">", "-", "*", "|", "`")):
            continue
        for part in re.split(r"(?<=[.!?])\s+", t):
            part = part.strip()
            if len(part) > 3:
                yield i, part


def paragraphs(body):
    """Group sentences by blank-line-separated paragraph, so a window never spans two."""
    out, cur, start = [], [], 1
    for n, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            if cur:
                out.append((start, cur))
                cur = []
            continue
        if not cur:
            start = n
        cur.append(line)
    if cur:
        out.append((start, cur))
    for start, block in out:
        sents = [(ln + start - 1, sn) for ln, sn in sentences("\n".join(block))]
        if sents:
            yield sents


def shape_echo(notes, body):
    """SHAPE DICTATION: the note's beats reproduced in the note's order.

    The NOTE-ECHO detector above reads word overlap inside a window. It cannot see the failure the
    author named on 2026-09-02: "you are taking my input as dictation." Four author sentences became
    eight prose sentences, in his order, one beat per sentence, with synonyms doing the disguising.
    Every word-overlap threshold passed, because no single span restated any single note closely
    enough. The dictation was in the SEQUENCE.

    So this asks a different question. Take a multi-sentence author note. Find where each of its
    sentences best matches the prose. If those matches are strictly in order, all present, and packed
    into a short stretch of prose, the prose is the note walked through end to end. That is dictation
    whatever the vocabulary.

    It deliberately does not fire on a single-sentence note, which has no order to reproduce, and it
    needs at least three beats, because two in order is a coincidence.
    """
    out = []
    sent = list(sentences(body))
    if len(sent) < 3:
        return out
    for note in notes:
        beats = [s for s in re.split(r"(?<=[.!?])\s+", note) if len(content_words(s)) >= 2]
        if len(beats) < 3:
            continue
        pos, hits = [], 0
        for beat in beats:
            bw = {_stem(w) for w in content_words(beat)}
            best, best_i = 0.0, None
            for i, (ln, s) in enumerate(sent):
                sw = {_stem(w) for w in content_words(s)}
                if not sw:
                    continue
                share = len(bw & sw) / max(len(bw), 1)
                if share > best:
                    best, best_i = share, i
            if best >= 0.34 and best_i is not None:
                pos.append(best_i); hits += 1
            else:
                pos.append(None)
        found = [i for i in pos if i is not None]
        if hits < 3 or hits < len(beats) - 1:
            continue
        if found != sorted(found):
            continue
        span = found[-1] - found[0] + 1
        if span > 2 * len(beats) + 2:
            continue
        out.append((sent[found[0]][0], "shape-echo",
                    f"{hits} beats of the author's note reproduced in his order across {span} "
                    f"sentence(s) (\"{' '.join(note.split())[:58]}...\"); the sequence is the "
                    f"dictation, not the wording", hits))
    return out


def check(path, offset):
    text = open(path, encoding="utf-8").read()
    fm, body = split_doc(text)
    # Under mode: nonfiction the anti-parrot verdict relaxes: accurate quotation is the point, so a
    # shape-echo is advisory rather than blocking (the unmarked-copy check moves to the accuracy gate).
    nonfiction = bool(re.search(r"(?mi)^mode:\s*nonfiction\b", fm or ""))
    notes = notes_from(fm)
    note_sets = [(n, content_words(n)) for n in notes]
    findings = []

    # NOTE-ECHO over sliding windows of up to three consecutive sentences. The failure very
    # often lands as two short sentences in a row ("It was all mouth." / "She did not use her
    # hands at all."), which a per-sentence test cuts in half and never sees.
    seen = set()
    for para in paragraphs(body):
        sents = [(ln, sn) for ln, sn in para
                 if not sn.lstrip().startswith(('"', "“"))]
        for i in range(len(sents)):
            for span in (1, 2, 3):
                if i + span > len(sents):
                    break
                line_no = sents[i][0]
                sw = set()
                for _, sn in sents[i:i + span]:
                    sw |= content_words(sn)
                if not sw:
                    continue
                for note, nw in note_sets:
                    if not nw or (line_no, note) in seen:
                        continue
                    shared = sw & nw
                    # TWO ratios, and both are needed.
                    # COVERAGE: how much of his note this span reproduces. Count alone never
                    # fires, because a two-word note is wholly echoed by two shared words.
                    # DOMINANCE: whether his words ARE the span or merely sit inside it.
                    # "He did not own sheets." is a restatement. "...a red paisley cover on it
                    # and nothing under it, because he did not own sheets" is the same fact
                    # doing work in a sentence, which is what was wanted.
                    coverage = len(shared) / len(nw)
                    dominance = len(shared) / len(sw)
                    long_note = len(note.split()) > 25
                    hit = (len(shared) >= 7 and dominance >= 0.35) if long_note else (
                        len(shared) >= 2 and coverage >= 0.6 and dominance >= 0.5)
                    if hit:
                        seen.add((line_no, note))
                        findings.append((line_no, "note-echo",
                                         f"restates {len(shared)}/{len(nw)} of the author's note "
                                         f"\"{note[:60]}{'...' if len(note) > 60 else ''}\" "
                                         f"({sorted(shared)}); build it, do not restate it"))

    for line_no, sent in sentences(body):
        if sent.lstrip().startswith(('"', "“")):
            continue  # a character may say any of this
        for pat, label in VERDICT:
            if re.search(pat, sent, re.IGNORECASE):
                findings.append((line_no, "verdict",
                                 f"narration asserts a verdict ('{label}'); cause it instead"))
                break

    # advisory findings so far carry no severity; give them one, then fold in shape-echo, whose
    # severity depends on how many beats were walked through in order.
    graded = [(ln, kind, msg, "warning") for (ln, kind, msg) in findings]
    for ln, kind, msg, hits in shape_echo(notes, body):
        level = "error" if (hits >= PARROT_BLOCK_BEATS and not nonfiction) else "warning"
        graded.append((ln, kind, msg, level))

    graded.sort(key=lambda f: (f[0], f[1]))
    blocking = 0
    for line_no, kind, msg, level in graded:
        if level == "error":
            blocking += 1
        print(f"{path}:{line_no + offset} [{level}] {kind}: {msg}")
    return len(graded), blocking


def main(argv):
    strict = "--strict" in argv
    files = [a for a in argv if not a.startswith("-")]
    if not files:
        print("check-transcription: no files given")
        return 0
    total = 0
    blocking = 0
    for f in files:
        try:
            # frontmatter lines are consumed by split_doc; body line numbers need the offset back
            head = open(f, encoding="utf-8").read()
            fm, _ = split_doc(head)
            offset = fm.count("\n") + 2 if fm else 0
            n, b = check(f, offset)
            total += n
            blocking += b
        except OSError as e:
            print(f"check-transcription: {e}", file=sys.stderr)
    tail = f" {blocking} BLOCKING (parrot)." if blocking else "."
    print(f"\ncheck-transcription: {total} finding(s) across {len(files)} file(s);{tail}")
    # A parrot verdict blocks on its own, always. Other findings block only under --strict.
    return 1 if (blocking or (strict and total)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
