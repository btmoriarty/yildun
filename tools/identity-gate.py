#!/usr/bin/env python3
"""identity-gate.py - author identity on every built piece (spec section 16, requirement X).

"The one thing that cannot be retrofitted." Git stamps commit-level authorship (author + co-author);
this adds per-PIECE identity: who authored the content and who approved it, which is what the RQ1 claim
(the idea is human, the support is AI) and content attribution both need at the grain of the work.

Convention: a built piece (derivation / composite / deliverable) carries a front-matter line

    identity: author=BTM engine=claude-opus-4-8 approved=2026-09-06

`approved=pending` is allowed (drafted, not yet approved). ADVISORY: it reports built pieces missing
identity so every NEW write carries it from now on; it does not block, because legacy pieces predate the
convention and are not retrofitted (retrofitting authorship would be inventing a record).

    identity-gate.py --check FILE...
"""
import argparse, os, re, sys
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import worldconfig as _wc
_iu=__import__("importlib").import_module("importlib.util")
_s=_iu.spec_from_file_location("ct",os.path.join(HERE,"check-transcription.py"))
ct=_iu.module_from_spec(_s); _s.loader.exec_module(ct)
CFG=_wc.load()
BUILT={"derivation","composite","deliverable"}

def main(argv):
    ap=argparse.ArgumentParser(); ap.add_argument("pieces",nargs="*"); ap.add_argument("--check",action="store_true")
    a=ap.parse_args(argv); missing=0; checked=0
    for p in a.pieces:
        if not os.path.exists(p): continue
        fm=ct.split_doc(open(p,encoding="utf-8").read())[0]
        typ=(re.search(r"(?m)^type:\s*([\w-]+)",fm) or [None,""])[1] if re.search(r"(?m)^type:\s*([\w-]+)",fm) else ""
        typ=(re.search(r"(?m)^type:\s*([\w-]+)",fm).group(1).lower() if re.search(r"(?m)^type:\s*([\w-]+)",fm) else "")
        if typ not in BUILT: continue
        checked+=1
        if not re.search(r"(?m)^identity:\s*author=",fm):
            print(f"  advisory  {os.path.relpath(os.path.abspath(p),CFG['root'])}: no identity: line "
                  f"(add: identity: author={CFG.get('author','?')} engine=<model> approved=<date|pending>)")
            missing+=1
    print(f"\nidentity-gate: {checked} built piece(s), {missing} without identity (advisory).")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1:]))
