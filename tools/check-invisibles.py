#!/usr/bin/env python3
"""Report invisible or anomalous Unicode in the saga's text. No dependencies.

Why this exists: a text watermark, if one is ever present, is not visible and the author
would not catch it by reading. c2patool cannot help here at all. It reads C2PA manifests
embedded in media containers and answers `Unsupported file type` on markdown, so it has a
role at export (PDF, EPUB, cover art) and none in the manuscript.

This is the manuscript-side check. It finds zero-width characters, directional marks,
unusual spaces and other format-category codepoints that carry no visible meaning in this
corpus and would be invisible in an editor.

    python3 tools/check-invisibles.py canon/vignettes/a-scene.md
    python3 tools/check-invisibles.py            # whole corpus

Exit 1 if anything is found. A clean run is evidence of absence only for the classes below;
it says nothing about statistical token-level watermarking, which cannot be detected from
the text without the key and probably not with it.
"""

import pathlib
import sys
import unicodedata

NAMED = {
    0x200B: "ZERO WIDTH SPACE", 0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER", 0xFEFF: "BOM / ZERO WIDTH NO-BREAK SPACE",
    0x202F: "NARROW NO-BREAK SPACE", 0x00A0: "NO-BREAK SPACE",
    0x2009: "THIN SPACE", 0x2007: "FIGURE SPACE", 0x2008: "PUNCTUATION SPACE",
    0x2028: "LINE SEPARATOR", 0x2029: "PARAGRAPH SEPARATOR",
    0x200E: "LEFT-TO-RIGHT MARK", 0x200F: "RIGHT-TO-LEFT MARK",
    0x2060: "WORD JOINER", 0x180E: "MONGOLIAN VOWEL SEPARATOR",
    0x061C: "ARABIC LETTER MARK", 0x2061: "FUNCTION APPLICATION",
    0x2062: "INVISIBLE TIMES", 0x2063: "INVISIBLE SEPARATOR", 0x2064: "INVISIBLE PLUS",
}
ROOTS = ["canon", "deliverables", "generated", "spec"]


def suspect(ch):
    o = ord(ch)
    if o in NAMED:
        return NAMED[o]
    # Cf is the format category: unprintable, non-spacing, carries no visible meaning.
    if o > 127 and unicodedata.category(ch) == "Cf":
        return unicodedata.name(ch, f"U+{o:04X}")
    # Variation selectors: invisible, and a documented carrier for hidden payloads.
    if 0xFE00 <= o <= 0xFE0F or 0xE0100 <= o <= 0xE01EF:
        return "VARIATION SELECTOR"
    return None


def main(argv):
    repo = pathlib.Path(__file__).resolve().parent.parent
    if argv:
        files = [pathlib.Path(a) for a in argv]
    else:
        files = sorted(p for r in ROOTS for p in (repo / r).rglob("*.md"))

    found = 0
    for f in files:
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"{f}: unreadable ({e})", file=sys.stderr)
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for col, ch in enumerate(line, 1):
                what = suspect(ch)
                if what:
                    try:
                        rel = f.resolve().relative_to(repo)
                    except ValueError:
                        rel = f  # outside the repo; report the path as given
                    print(f"{rel}:{n}:{col} [invisible] {what}  (U+{ord(ch):04X})")
                    found += 1

    print(f"\ncheck-invisibles: {found} finding(s) across {len(files)} file(s).")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
