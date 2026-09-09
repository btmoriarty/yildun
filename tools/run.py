#!/usr/bin/env python3
"""run.py - the run loop: validate, log, and commit one unit of work, with identity on both.

P2 of the build plan (AUTHORING-TOOL-SPEC.md section 14). Generation is done by whatever agent you point
at the corpus; this closes the loop around it. Given the current uncommitted changes it:

  1. VALIDATE  runs the voice gate (lint-voice.sh) on the changed shareable files. If a gate blocks,
               nothing is logged or committed: a failing piece never enters the record.
  2. LOG       appends one line to the generation log in the house format, carrying author identity.
  3. COMMIT    stages the tree and commits, with the identity trailer and, for a Claude engine, a
               Co-Authored-By line. Never pushes.

Identity is carried on every write and every log line (section 16.2, 16.x), the one thing that cannot
be retrofitted: author from world.json `author` or $YILDUN_AUTHOR, engine from $YILDUN_ENGINE.

    run.py --note "fed the thin lane" --mode expand
    run.py --note "..." --mode deliverable --lanes 4,7 --gen after   # house extras, optional
    run.py --note "..." --dry-run        # show the log line and the commit, change nothing
    run.py --note "..." --no-commit      # validate and log, leave the commit to you
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import worldconfig as _wc

CFG = _wc.load()
ROOT = CFG["root"]


def git(*args, check=True):
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"run: git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def _parse_status(out):
    """Paths with a pending change, from `git status --porcelain=1 -z`. A rename or copy emits the new
    path in its record and the old path as the very next NUL-terminated field, so that trailing field
    is consumed rather than mistaken for a garbled second path."""
    fields = out.split("\0")
    files, i = [], 0
    while i < len(fields):
        e = fields[i]
        if len(e) >= 4:
            files.append(e[3:])          # e is "XY <path>"; for R/C, <path> is the NEW path
            if e[0] in ("R", "C"):
                i += 1                   # skip the following field: the old/source path
        i += 1
    return files


def changed_files():
    """Every path with a pending change (staged, unstaged, or untracked), repo-relative."""
    return _parse_status(git("status", "--porcelain=1", "-z"))


def under_trees(files, trees):
    return [f for f in files if any(f == t or f.startswith(t.rstrip("/") + "/") for t in trees)]


def main(argv):
    ap = argparse.ArgumentParser(description="The run loop: validate, log, commit one unit of work.")
    ap.add_argument("--note", required=True, help="what this run did, one line")
    ap.add_argument("--mode", default="run", help="work mode: expand / deliverable / check / infrastructure / ...")
    ap.add_argument("--posture", default="", help="oversight posture (house interaction mode), optional")
    ap.add_argument("--oversight", default="", help="oversight mode (sets review policy and posture); see tools/oversight-modes.json")
    ap.add_argument("--lanes", default="", help="house extra: lanes touched, e.g. 4,7")
    ap.add_argument("--gen", default="", help="house extra: generations touched")
    ap.add_argument("--strict", action="store_true", help="fail the run on gate warnings, not only errors")
    ap.add_argument("--no-commit", action="store_true", help="validate and log only; do not commit")
    ap.add_argument("--dry-run", action="store_true", help="show the log line and commit; change nothing")
    args = ap.parse_args(argv)

    # Oversight mode: the review posture, and the policy it implies. It sets gate strictness and
    # whether the run commits or holds the commit for the human, and it is recorded as the study's
    # independent variable.
    audit_flag = ""
    if args.oversight:
        mpath = os.path.join(HERE, "oversight-modes.json")
        modes = json.load(open(mpath, encoding="utf-8")).get("modes", {}) if os.path.exists(mpath) else {}
        pol = modes.get(args.oversight)
        if not pol:
            sys.exit(f"run: unknown oversight mode '{args.oversight}'. Known: {', '.join(sorted(modes)) or '(none configured)'}")
        if pol.get("strict"):
            args.strict = True
        if pol.get("commit") == "hold":
            args.no_commit = True
        if not args.posture:
            args.posture = args.oversight
        audit_flag = pol.get("flag", "")

    files = changed_files()
    if not files:
        sys.exit("run: nothing changed; make or generate something first.")
    shareable = under_trees(files, [os.path.relpath(t, ROOT) if os.path.isabs(t) else t
                                    for t in CFG["shareable_trees"]])

    # 1. VALIDATE the changed shareable prose. Non-shareable changes (tools, generated) are not gated.
    if shareable:
        lint = os.path.join(HERE, "lint-voice.sh")
        cmd = ["bash", lint] + (["--strict"] if args.strict else []) + \
              [os.path.join(ROOT, f) for f in shareable]
        print(f"run: validating {len(shareable)} shareable file(s)...")
        if subprocess.run(cmd).returncode != 0:
            sys.exit("\nrun: the gate blocked. Nothing logged or committed; fix and run again.")
    else:
        print("run: no shareable prose changed; skipping the voice gate.")

    # identity, carried on the log line and the commit
    author = CFG.get("author") or os.environ.get("YILDUN_AUTHOR", "").strip() or "unknown"
    engine = os.environ.get("YILDUN_ENGINE", "").strip() or "unknown"
    date = datetime.date.today().isoformat()

    # 2. LOG one line in the house format: date · mode [· posture · lanes · gen] · files · note · id
    parts = [f"- {date}", args.mode]
    if args.posture:
        parts.append(f"posture[{args.posture}]")
    if args.lanes:
        parts.append(f"lanes[{args.lanes}]")
    if args.gen:
        parts.append(f"gen[{args.gen}]")
    parts.append("files: " + ", ".join(files))
    parts.append(args.note)
    if audit_flag == "audit":
        parts.append("[audit-pending]")
    parts.append(f"id[author={author} engine={engine}]")
    line = " · ".join(parts)

    logrel = os.path.join(os.path.relpath(os.path.dirname(CFG["captures"]), ROOT), "LOG.md")
    logpath = os.path.join(ROOT, logrel)

    print("\nrun: log line ->")
    print("  " + line)
    if args.dry_run:
        print(f"\nrun (dry): would append to {logrel} and commit {len(files)} file(s). Nothing changed.")
        return 0

    os.makedirs(os.path.dirname(logpath), exist_ok=True)
    if not os.path.exists(logpath):
        open(logpath, "w", encoding="utf-8").write("# Generation Log\n\nOne line per run. Newest at the bottom.\n\n")
    with open(logpath, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    if args.no_commit:
        print(f"\nrun: logged to {logrel}. Commit left to you (--no-commit).")
        return 0

    # 3. COMMIT the tree, identity in the trailer, never push.
    git("add", "-A")
    msg = f"{args.mode}: {args.note}\n\nidentity: author={author} engine={engine} approved=pending\n"
    if "claude" in engine.lower():
        msg += "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n"
    r = subprocess.run(["git", "-C", ROOT, "commit", "-q", "-F", "-"], input=msg, text=True)
    if r.returncode != 0:
        sys.exit("run: logged, but the commit failed (a pre-commit hook may have blocked it).")
    head = git("rev-parse", "--short", "HEAD").strip()
    print(f"\nrun: committed {head}, {len(files)} file(s) logged and recorded. Not pushed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
