#!/usr/bin/env python3
"""screenplay.py - the screenplay rung: lay a finished prose piece out in Fountain screenplay format.

The last rung of the deliverable ladder (AUTHORING-TOOL-SPEC.md section 14, P5), and a FORMAT track, not
a writing one. A screenplay is written, not converted: turning narration into scenes, beats, and spoken
lines is composition, and composition is the author's (requirement 8). So this does only what a format
adapter may honestly do. It reads the shareable prose, sets the section titles as scene headings, lays
the prose down as action, and lifts a line that is nothing but a quotation into a dialogue block. It
invents nothing, and it says plainly that the result is a layout to rewrite, not a screenplay.

Output is Fountain (plain text, the open screenplay markup), which any screenwriting app imports.

    screenplay.py deliverables/the-route.md
    screenplay.py deliverables/the-route.md --out exports/the-route.fountain
"""
import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_iu = __import__("importlib").import_module("importlib.util")
_s = _iu.spec_from_file_location("pm", os.path.join(HERE, "provenance-map.py"))
pm = _iu.module_from_spec(_s); _s.loader.exec_module(pm)
CFG = pm.CFG
ROOT = CFG["root"]
APPARATUS = re.compile(r"\n(?:#+\s*(?:Notes|Connections|Provenance|Deepen-me|Register|Canonical lines|"
                       r"Seeded|Machine))", re.I)


def is_pure_quote(block):
    """A block that is one quoted line and nothing else, safe to lay out as dialogue."""
    b = block.strip()
    if "\n" in b or len(b.split()) > 25:
        return None
    m = re.fullmatch(r'[“"](.+?)[”"][.,]?', b)
    return m.group(1).strip() if m else None


def main(argv):
    ap = argparse.ArgumentParser(description="Lay a prose piece out in Fountain screenplay format (a format pass, not a rewrite).")
    ap.add_argument("piece")
    ap.add_argument("--out", default="")
    ap.add_argument("--title", default="")
    args = ap.parse_args(argv)

    piece = args.piece if os.path.isabs(args.piece) else os.path.join(ROOT, args.piece)
    if not os.path.exists(piece):
        sys.exit(f"screenplay: no such piece: {piece}")
    fm, body = pm.ct.split_doc(open(piece, encoding="utf-8").read())
    stem = os.path.splitext(os.path.basename(piece))[0]
    nm = re.search(r"(?m)^name:\s*(.+)$", fm)
    title = args.title or (nm.group(1).strip() if nm else stem)
    author = CFG.get("author") or os.environ.get("YILDUN_AUTHOR", "").strip() or "unknown"
    date = datetime.date.today().isoformat()

    prose = APPARATUS.split(body, maxsplit=1)[0]
    prose = re.sub(r"^\s*#\s+.*\n", "", prose, count=1)  # drop the top H1; the title page carries it

    out_lines = [
        f"Title: {title}", "Credit: laid out from prose by Yildun", f"Author: {author}",
        f"Draft date: {date}", f"Source: {os.path.relpath(piece, ROOT)}",
        "Notes: FORMAT PASS ONLY. Scene headings are the section titles, the prose is set as action, and",
        "    only quote-only lines became dialogue. A screenplay is written, not converted; rewrite this.",
        "", "",
    ]
    scenes = 0
    for block in re.split(r"\n\s*\n", prose):
        b = block.strip()
        if not b:
            continue
        h = re.match(r"#{1,6}\s+(.+)", b)
        if h:
            out_lines += [f".{h.group(1).strip().upper()}", ""]
            scenes += 1
            continue
        q = is_pure_quote(b)
        if q:
            out_lines += ["SPEAKER", q, ""]
        else:
            out_lines += [b, ""]

    if scenes == 0:  # a single unsectioned piece: give it one scene from the title
        out_lines.insert(9, f".{title.upper()}")
        out_lines.insert(10, "")

    out = args.out or os.path.join(ROOT, "exports", stem + ".fountain")
    out = out if os.path.isabs(out) else os.path.join(ROOT, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(out_lines).rstrip() + "\n")
    print(f"screenplay: wrote {os.path.relpath(out, ROOT)} (Fountain), {scenes} scene heading(s).")
    print("  FORMAT PASS ONLY: scene headings from section titles, prose as action, quote-only lines as")
    print("  dialogue under a SPEAKER cue. A screenplay is written, not converted; this is a layout to rework.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
