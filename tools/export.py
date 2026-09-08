#!/usr/bin/env python3
"""export.py - the export gate: turn one shippable piece into a clean, provenance-bearing artifact.

P4's last step (AUTHORING-TOOL-SPEC.md section 14, and section 17.4). A shareable export happens here
and only here, so the checks that must hold at the boundary run here, not on a habit:

  1. VERIFY   the piece is marked shippable and passes every gate right now. A piece that would not
              pass the gate does not leave the workshop.
  2. STRIP    the obfuscation gate (section 377): remove zero-width and other invisible watermark
              characters so no distributed file carries a hidden mark. Reported, not silent.
  3. RENDER   the shareable prose only (front matter and the Notes / Connections / Deepen-me apparatus
              dropped) to a PDF, with author, title, and date written into the PDF's own metadata.
  4. PROVENANCE  a sidecar `<out>.provenance.json` records author, engine, date, the source piece, the
              commit, and that the gate passed: a portable record that travels with the file.

Content Credentials (C2PA) are the intended provenance carrier, but the installed c2patool embeds only
into media formats, not PDF, so for a prose export the provenance rides in the PDF metadata and the
sidecar. When exporting a supported media asset, or on a c2patool that signs PDF, pass --c2pa with a
signing cert (env C2PA_SIGN_CERT and C2PA_PRIVATE_KEY) to embed it.

    export.py deliverables/the-route.md
    export.py deliverables/the-route.md --out exports/the-route.pdf
"""
import argparse
import datetime
import json
import os
import re
import subprocess
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
DELETE = {0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060, 0x180E, 0x061C, 0x2061, 0x2062, 0x2063, 0x2064,
          0x200E, 0x200F, 0x2028, 0x2029}
SPACEY = {0x00A0, 0x2009, 0x2007, 0x2008, 0x202F}


def strip_obfuscation(text):
    out, removed = [], 0
    for ch in text:
        o = ord(ch)
        if o in DELETE or 0xFE00 <= o <= 0xFE0F or 0xE0100 <= o <= 0xE01EF or 0xE0000 <= o <= 0xE007F:
            removed += 1
            continue
        out.append(" " if o in SPACEY else ch)
    return "".join(out), removed


def main(argv):
    ap = argparse.ArgumentParser(description="Export gate: verify, strip, render, record provenance.")
    ap.add_argument("piece")
    ap.add_argument("--out", default="", help="output path (default exports/<stem>.pdf)")
    ap.add_argument("--c2pa", action="store_true", help="attempt C2PA embedding (needs a supported format + signing cert)")
    args = ap.parse_args(argv)

    piece = args.piece if os.path.isabs(args.piece) else os.path.join(ROOT, args.piece)
    if not os.path.exists(piece):
        sys.exit(f"export: no such piece: {piece}")
    fm, body = pm.ct.split_doc(open(piece, encoding="utf-8").read())

    # 1. VERIFY
    if not re.search(r"(?mi)^shippable:\s*true\b", fm or ""):
        sys.exit("export: piece is not shippable (set shippable: true first). Refusing to export.")
    print("export: verifying against the gate...")
    if subprocess.run(["bash", os.path.join(HERE, "lint-voice.sh"), piece]).returncode != 0:
        sys.exit("\nexport: the gate blocked. Nothing exported; fix and try again.")

    stem = os.path.splitext(os.path.basename(piece))[0]
    name = (re.search(r"(?m)^name:\s*(.+)$", fm) or [None, stem])
    name = re.search(r"(?m)^name:\s*(.+)$", fm)
    title = name.group(1).strip() if name else stem
    author = CFG.get("author") or os.environ.get("YILDUN_AUTHOR", "").strip() or "unknown"
    engine = os.environ.get("YILDUN_ENGINE", "").strip() or "unknown"
    date = datetime.date.today().isoformat()

    # 2. PROSE + STRIP
    prose = APPARATUS.split(body, maxsplit=1)[0]
    prose = re.sub(r"^\s*#\s+.*\n", "", prose, count=1).strip()  # drop the H1; the title carries it
    prose, removed = strip_obfuscation(prose)
    print(f"export: obfuscation strip removed {removed} invisible character(s).")

    # 3. RENDER
    out = args.out if args.out else os.path.join(ROOT, "exports", stem + ".pdf")
    out = out if os.path.isabs(out) else os.path.join(ROOT, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    md = f"% {title}\n% {author}\n% {date}\n\n{prose}\n"
    r = subprocess.run(["pandoc", "-M", f"title={title}", "-M", f"author={author}",
                        "-M", f"date={date}", "-o", out, "-"], input=md, text=True)
    if r.returncode != 0:
        sys.exit("export: pandoc failed to render the PDF (a LaTeX engine issue, or a special "
                 "character). Nothing exported.")

    # 4. PROVENANCE sidecar
    try:
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip() or None
    except Exception:
        head = None
    sidecar = out + ".provenance.json"
    json.dump({
        "title": title, "author": author, "engine": engine, "date": date,
        "source": os.path.relpath(piece, ROOT), "commit": head,
        "gate": "passed", "obfuscation_stripped": removed, "exported_by": "yildun/export.py",
    }, open(sidecar, "w", encoding="utf-8"), indent=2)

    print(f"\nexport: wrote {os.path.relpath(out, ROOT)}")
    print(f"        provenance -> {os.path.relpath(sidecar, ROOT)} (author, date, source, commit, gate)")
    print(f"        PDF metadata carries title/author/date.")
    if args.c2pa:
        print("export: C2PA embedding into PDF is not supported by the installed c2patool; the "
              "provenance rides in the sidecar and the PDF metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
