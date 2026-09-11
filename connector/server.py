#!/usr/bin/env python3
"""Yildun desktop connector: the writing front-end for the Claude desktop app.

A writer works entirely in the Claude desktop app: they ask for help, react to suggestions in plain
words, and their document and their Accept/Modify/Reject log build together, with no terminal, no
copy-paste, and no separate log command. This MCP server is what makes that possible. It exposes the
existing Yildun tools (amr-log.py, lint-voice.sh) as tools the app can call, so every decision the
writer voices is captured in the same schema as the command-line `yildun amr`, and never reconstructed
from memory.

Design intent (see connector/PROJECT.md): capture the writer's decisions from the conversation and log
them silently. The logging is meant to encourage, not to nag. This server only provides the
capability; PROJECT.md is where the light-touch behaviour lives.

Configuration, all via environment (set in claude_desktop_config.json):
  YILDUN_HOME     the Yildun install (defaults to this file's grandparent)
  YILDUN_DRAFTS   where the writer's piece and log live (defaults to <home>/drafts); point this at a
                  git-backed student folder so the work is durable and retrievable
  YILDUN_AUTHOR   the writer's handle, stamped on every AMR entry (identity cannot be retrofitted)
  YILDUN_ENGINE   the model the suggestions come from (defaults to claude-desktop)

Run (as launched by the desktop app): uv run --with mcp python connector/server.py
"""
import json
import os
import subprocess
import sys

ROOT = os.environ.get("YILDUN_HOME") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
DRAFTS = os.environ.get("YILDUN_DRAFTS") or os.path.join(ROOT, "drafts")
AUTHOR = os.environ.get("YILDUN_AUTHOR", "").strip() or "unknown"
ENGINE = os.environ.get("YILDUN_ENGINE", "").strip() or "claude-desktop"
VERDICTS = {"accept", "modify", "reject"}

FICTION_TPL = ("---\ntype: composite\nexperience: fiction\nshippable: false\n---\n\n"
               "# Your title here\n\n")
NONFICTION_TPL = ("---\nmode: nonfiction\nshippable: false\nsources:\n"
                  "  - example-source: what this source is, in a few words\nconsent:\n  - none\n---\n\n"
                  "# Your title here\n\n")


# ---- core functions (no MCP dependency, so they are testable on their own) ----

def _piece_path(name):
    if not name:
        raise ValueError("a piece name is required")
    if os.path.isabs(name):
        return name
    if name.endswith(".md"):
        return os.path.join(DRAFTS, name)
    return os.path.join(DRAFTS, name + ".md")


def _log_path(name):
    p = _piece_path(name)
    stem = os.path.splitext(os.path.basename(p))[0]
    return os.path.join(os.path.dirname(p), stem + ".amr.jsonl")


def do_open(name, nonfiction=False):
    os.makedirs(DRAFTS, exist_ok=True)
    p = _piece_path(name)
    if os.path.exists(p):
        return {"ok": True, "piece": name, "path": p, "created": False, "message": "opened existing piece"}
    open(p, "w", encoding="utf-8").write(NONFICTION_TPL if nonfiction else FICTION_TPL)
    return {"ok": True, "piece": name, "path": p, "created": True,
            "message": "created a new " + ("non-fiction" if nonfiction else "fiction") + " piece"}


def do_read(name):
    p = _piece_path(name)
    if not os.path.exists(p):
        return {"ok": False, "error": f"no such piece: {name}. Open it first."}
    return {"ok": True, "piece": name, "path": p, "content": open(p, encoding="utf-8").read()}


def do_save(name, content):
    p = _piece_path(name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)
    return {"ok": True, "piece": name, "path": p, "bytes": len(content.encode("utf-8"))}


def do_append(name, text):
    p = _piece_path(name)
    if not os.path.exists(p):
        do_open(name)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(text if text.startswith("\n") else "\n" + text)
    return {"ok": True, "piece": name, "path": p}


def do_log(verdict, reason, piece, confidence=None, effort_s=None):
    v = (verdict or "").lower().strip()
    if v not in VERDICTS:
        return {"ok": False, "error": f"verdict must be accept, modify, or reject, not '{verdict}'"}
    p = _piece_path(piece)
    if not os.path.exists(p):
        return {"ok": False, "error": f"no such piece: {piece}. Open it first."}
    cmd = [sys.executable, os.path.join(TOOLS, "amr-log.py"), "--piece", p,
           "--verdict", v, "--note", reason or "", "--engine", ENGINE]
    if confidence is not None:
        cmd += ["--confidence", str(int(confidence))]
    if effort_s is not None:
        cmd += ["--effort", str(float(effort_s))]
    env = dict(os.environ, YILDUN_AUTHOR=AUTHOR, YILDUN_ENGINE=ENGINE)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout).strip()}
    return {"ok": True, "verdict": v, "logged": True, "who": AUTHOR, "detail": r.stdout.strip()}


def do_status(name):
    p = _piece_path(name)
    words = 0
    if os.path.exists(p):
        body = open(p, encoding="utf-8").read()
        if body.startswith("---"):
            parts = body.split("---", 2)
            body = parts[2] if len(parts) == 3 else body
        words = len(body.split())
    counts = {"accept": 0, "modify": 0, "reject": 0}
    last_reject = None
    lp = _log_path(name)
    if os.path.exists(lp):
        for line in open(lp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            v = e.get("verdict")
            if v in counts:
                counts[v] += 1
            if v == "reject" and e.get("note"):
                last_reject = e["note"]
    return {"ok": True, "piece": name, "words": words,
            "decisions": sum(counts.values()), **counts, "last_reject_reason": last_reject}


def do_check(name):
    p = _piece_path(name)
    if not os.path.exists(p):
        return {"ok": False, "error": f"no such piece: {name}"}
    lint = os.path.join(TOOLS, "lint-voice.sh")
    r = subprocess.run(["bash", lint, p], capture_output=True, text=True)
    return {"ok": r.returncode == 0, "passed": r.returncode == 0, "output": (r.stdout + r.stderr).strip()}


# ---- MCP wiring (imported lazily so the core functions above stay testable) ----

def build_server():
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("yildun")

    @mcp.tool()
    def open_piece(name: str, nonfiction: bool = False) -> dict:
        """Create or open the writer's document (a piece). Call this at the start of a session, or when
        the writer names a new piece. `nonfiction=true` for the non-fiction track."""
        return do_open(name, nonfiction)

    @mcp.tool()
    def read_piece(name: str) -> dict:
        """Return the current text of the writer's document, so you work from what is actually on disk."""
        return do_read(name)

    @mcp.tool()
    def save_piece(name: str, content: str) -> dict:
        """Overwrite the document with new content. Only call this after the writer has decided on the
        change and that decision has been logged with log_decision."""
        return do_save(name, content)

    @mcp.tool()
    def append_piece(name: str, text: str) -> dict:
        """Append text to the end of the document. Same rule as save_piece: the writer decided, and the
        decision is logged, first."""
        return do_append(name, text)

    @mcp.tool()
    def log_decision(verdict: str, reason: str, piece: str,
                     confidence: int = None, effort_s: float = None) -> dict:
        """Record ONE Accept/Modify/Reject decision the writer just made about a suggestion. This is the
        study's core datum. Call it whenever the writer reacts to something you proposed, in the moment,
        as part of the flow, not as a separate ceremony. `verdict` is accept, modify, or reject.
        `reason` is the writer's OWN words for why, verbatim where you have them (leave empty rather than
        invent one). Do this quietly; do not announce it or ask permission to log."""
        return do_log(verdict, reason, piece, confidence, effort_s)

    @mcp.tool()
    def writing_status(name: str) -> dict:
        """Return the writer's progress: word count and the running accept/modify/reject tally. Use it at
        a natural pause to reflect progress back lightly, never as a reminder to log."""
        return do_status(name)

    @mcp.tool()
    def check_piece(name: str) -> dict:
        """Run the voice gate on the document and return whether it passed. Call it when the writer asks,
        or at the end of a session."""
        return do_check(name)

    return mcp


if __name__ == "__main__":
    build_server().run()
