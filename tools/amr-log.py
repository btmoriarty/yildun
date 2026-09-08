#!/usr/bin/env python3
"""amr-log.py - append one Accept/Modify/Reject decision to a piece's durable AMR log.

The study's core datum (writing_partner_replication.md, writing_recurrence.md): every AI suggestion a
writer takes, changes, or refuses, marked AS IT HAPPENS, timestamped, one entry per suggestion, no
sampling and no gaps. This writes the entry so it is captured in the moment rather than reconstructed
from memory, and so every student's log has the SAME shape and can be pooled.

The log lives next to the piece as `<piece>.amr.jsonl` (JSON Lines, one decision per line): durable,
append-only, version-controllable, and trivial to export to CSV. It is never written to a tmp dir.

Fields (the shared review-record shape, plus the oversight extension):
  ts        ISO-8601 UTC, stamped here so it is honest about when the decision happened
  who       reviewer identity (env YILDUN_AUTHOR), because identity per entry cannot be retrofitted
  engine    the AI agent/model the suggestion came from (env YILDUN_ENGINE or --engine)
  piece     the document stem
  verdict   accept | modify | reject
  note      what the suggestion was and why you did what you did (free text)
  effort_s  seconds on the decision, if given (--effort); else null, and analysis derives it from ts
  confidence 1-5 if given (--confidence); else null

Usage (normally invoked via `yildun amr`, not directly):
  amr-log.py --piece /path/to/piece.md --verdict modify --note "tightened the intro; kept the claim"
"""
import argparse
import datetime
import json
import os
import sys

VERDICTS = {"accept", "modify", "reject"}


def main(argv):
    ap = argparse.ArgumentParser(description="Append one AMR decision to a piece's durable log.")
    ap.add_argument("--piece", required=True, help="path to the .md piece")
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--effort", type=float, default=None, help="seconds on this decision")
    ap.add_argument("--confidence", type=int, default=None, help="1-5")
    ap.add_argument("--engine", default=os.environ.get("YILDUN_ENGINE", "unknown"))
    args = ap.parse_args(argv)

    verdict = args.verdict.lower()
    if verdict not in VERDICTS:
        sys.exit(f"amr-log: verdict must be one of {', '.join(sorted(VERDICTS))}, not '{args.verdict}'")
    piece = os.path.abspath(args.piece)
    if not os.path.exists(piece):
        sys.exit(f"amr-log: no such piece: {piece}")

    stem = os.path.splitext(os.path.basename(piece))[0]
    log = os.path.join(os.path.dirname(piece), stem + ".amr.jsonl")
    who = os.environ.get("YILDUN_AUTHOR", "").strip() or "unknown"
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "who": who,
        "engine": args.engine,
        "piece": stem,
        "verdict": verdict,
        "note": args.note,
        "effort_s": args.effort,
        "confidence": args.confidence,
    }
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    n = sum(1 for _ in open(log, encoding="utf-8"))
    print(f"Logged {verdict} to {log} (entry {n})")
    if who == "unknown":
        print("  note: set YILDUN_AUTHOR to your name so the log records who decided.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
