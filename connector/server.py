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

Run (as launched by the desktop app, or as a desktop extension): python3 connector/server.py. No packages.
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



CHECKIN_TPL = """**Week of:** {week_of}
**Words so far:** {words}
**AMR this week:** accept {a} / modify {m} / reject {r}

**What I did.** {what}

**Where I had to step in.** {stepin}

**Using the tools.** {tools}

**Overrides.** {overrides}

**Blockers and questions.** {blockers}

**Rough time.** {time}
"""

CHECKIN_PROMPTS = {
    "what": "What did you do this week? Two or three sentences on where the document moved.",
    "stepin": "Where did you have to step in? The one or two decisions that mattered most.",
    "tools": "How was using the tools? What worked, what confused you, where you lost time.",
    "overrides": "Any gate you overrode at check, and why. If none, say none.",
    "blockers": "Blockers and questions. What you need from your mentor to keep moving.",
    "time": "Roughly how many hours this week, and where they went.",
}


def _week_counts(name, days=7):
    """Accept/modify/reject counts from entries stamped within the last `days` days."""
    import datetime as _dt
    counts = {"accept": 0, "modify": 0, "reject": 0}
    lp = _log_path(name)
    if not os.path.exists(lp):
        return counts
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    for line in open(lp, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            ts = _dt.datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))
        except Exception:
            continue
        if ts >= cutoff and e.get("verdict") in counts:
            counts[e["verdict"]] += 1
    return counts


def do_checkin_start(name, week_of):
    """Hand the partner what it needs to walk the writer through the weekly check-in."""
    st = do_status(name)
    wk = _week_counts(name)
    return {"ok": True, "week_of": week_of, "words": st.get("words", 0), "this_week": wk,
            "prompts": CHECKIN_PROMPTS,
            "note": "Ask the prompts in plain conversation, one or two at a time. Then call checkin_save "
                    "with the writer's answers; the counts above fill the header."}


def do_checkin_save(name, week_of, what, stepin, tools, overrides, blockers, time):
    st = do_status(name)
    wk = _week_counts(name)
    text = CHECKIN_TPL.format(week_of=week_of, words=st.get("words", 0), a=wk["accept"], m=wk["modify"],
                              r=wk["reject"], what=what, stepin=stepin, tools=tools,
                              overrides=overrides, blockers=blockers, time=time)
    d = os.path.join(DRAFTS, "checkins")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{week_of}.md")
    open(path, "w", encoding="utf-8").write(text)
    return {"ok": True, "path": path, "saved": True}


def do_sync(message=""):
    """Commit and push the writer's folder, so the term survives a lost laptop. The folder must be a
    clone of the study repo (git finds the root from a subfolder)."""
    r = subprocess.run(["git", "-C", DRAFTS, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "error": "the work folder is not inside a git repository; it should be a "
                                      "clone of the study repo (see README)."}
    root = r.stdout.strip()
    subprocess.run(["git", "-C", root, "add", "-A"], capture_output=True, text=True)
    c = subprocess.run(["git", "-C", root, "commit", "-q", "-m", message or "writing session"],
                       capture_output=True, text=True)
    committed = c.returncode == 0
    nothing = ("nothing to commit" in (c.stdout + c.stderr))
    p = subprocess.run(["git", "-C", root, "push", "-q"], capture_output=True, text=True)
    return {"ok": p.returncode == 0, "committed": committed, "nothing_new": nothing,
            "pushed": p.returncode == 0, "detail": (c.stderr + p.stderr).strip()[:300]}


# ---- MCP over stdio, standard library only ----
#
# The Model Context Protocol's stdio transport is newline-delimited JSON-RPC 2.0. A server for tools
# needs four methods: initialize, tools/list, tools/call, and ping, plus silence on notifications.
# Implementing that here, with no third-party package, is what lets this connector ship as a desktop
# extension that runs on any machine with python3, and what lets the install drop uv entirely.

SERVER_NAME = "yildun"
SERVER_VERSION = "0.2.4"
PROTOCOLS = {"2025-06-18", "2025-03-26", "2024-11-05"}

def _s(desc): return {"type": "string", "description": desc}

TOOL_TABLE = [
    {"name": "open_piece",
     "description": "Create or open the writer's document (a piece). Call this at the start of a session, or when "
                    "the writer names a new piece. nonfiction=true for the non-fiction track.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name"), "nonfiction": {"type": "boolean", "default": False}},
                     "required": ["name"]},
     "handler": lambda a: do_open(a["name"], bool(a.get("nonfiction", False)))},
    {"name": "read_piece",
     "description": "Return the current text of the writer's document, so you work from what is actually on disk.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name")}, "required": ["name"]},
     "handler": lambda a: do_read(a["name"])},
    {"name": "save_piece",
     "description": "Overwrite the document with new content. Only call this after the writer has decided on the "
                    "change and that decision has been logged with log_decision.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name"), "content": _s("full document text")},
                     "required": ["name", "content"]},
     "handler": lambda a: do_save(a["name"], a["content"])},
    {"name": "append_piece",
     "description": "Append text to the end of the document. Same rule as save_piece: the writer decided, and the "
                    "decision is logged, first.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name"), "text": _s("text to append")},
                     "required": ["name", "text"]},
     "handler": lambda a: do_append(a["name"], a["text"])},
    {"name": "log_decision",
     "description": "Record ONE Accept/Modify/Reject decision the writer just made about a suggestion. This is the "
                    "study's core datum. Call it whenever the writer reacts to something you proposed, in the "
                    "moment, as part of the flow, not as a separate ceremony. verdict is accept, modify, or reject. "
                    "reason must contain ONLY words the writer typed in this conversation, quoted or lightly "
                    "trimmed. Never the document's text, never a paraphrase of the passage, never your own account "
                    "of why the change was good. Test it: if what you are about to send as reason appears in the "
                    "document, or would read as prose inside it, it is not a reason, so send \"\" instead. A bare "
                    "yes or no carries no reason; send \"\" and move on. An empty reason is wanted data, an invented "
                    "one is a falsified record. Call this once per reaction, immediately, never in a batch at the end "
                    "of a passage, because the timestamp is the only evidence of when the decision happened. Set "
                    "effort_s and confidence only if the writer states them; never estimate. Do this quietly; do not "
                    "announce it or ask permission to log.",
     "inputSchema": {"type": "object",
                     "properties": {"verdict": {"type": "string", "enum": ["accept", "modify", "reject"]},
                                    "reason": _s("the writer's own words, or empty"), "piece": _s("piece name"),
                                    "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
                                    "effort_s": {"type": "number"}},
                     "required": ["verdict", "reason", "piece"]},
     "handler": lambda a: do_log(a["verdict"], a.get("reason", ""), a["piece"], a.get("confidence"), a.get("effort_s"))},
    {"name": "writing_status",
     "description": "Return the writer's progress: word count and the running accept/modify/reject tally. Use it at "
                    "a natural pause to reflect progress back lightly, never as a reminder to log.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name")}, "required": ["name"]},
     "handler": lambda a: do_status(a["name"])},
    {"name": "check_piece",
     "description": "Run the voice gate on the document and return whether it passed. Call it when the writer asks, "
                    "or at the end of a session.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name")}, "required": ["name"]},
     "handler": lambda a: do_check(a["name"])},
    {"name": "checkin_start",
     "description": "Begin the weekly check-in. Returns the writer's word count, this week's accept/modify/reject "
                    "tally, and the six prompts to ask in plain conversation, one or two at a time. week_of is the "
                    "Monday's date as YYYY-MM-DD. Do this once a week, or when the writer asks.",
     "inputSchema": {"type": "object", "properties": {"name": _s("piece name"), "week_of": _s("YYYY-MM-DD")},
                     "required": ["name", "week_of"]},
     "handler": lambda a: do_checkin_start(a["name"], a["week_of"])},
    {"name": "checkin_save",
     "description": "Save the weekly check-in from the writer's own answers, into checkins/<week_of>.md in their "
                    "folder. Use their words; do not embellish. Call sync_work afterwards.",
     "inputSchema": {"type": "object",
                     "properties": {k: _s(k) for k in ("name", "week_of", "what", "stepin", "tools", "overrides", "blockers", "time")},
                     "required": ["name", "week_of", "what", "stepin", "tools", "overrides", "blockers", "time"]},
     "handler": lambda a: do_checkin_save(a["name"], a["week_of"], a["what"], a["stepin"], a["tools"],
                                          a["overrides"], a["blockers"], a["time"])},
    {"name": "sync_work",
     "description": "Commit and push the writer's folder so nothing is lost. Call it at the end of every session "
                    "and after saving a check-in. Quiet on success; report the error if the push fails.",
     "inputSchema": {"type": "object", "properties": {"message": _s("commit message, optional")}},
     "handler": lambda a: do_sync(a.get("message", ""))},
]
_BY_NAME = {t["name"]: t for t in TOOL_TABLE}


def _public(t):
    return {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}


def _result(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(msg):
    """Return a response dict, or None for notifications."""
    method = msg.get("method")
    id_ = msg.get("id")
    params = msg.get("params") or {}
    if id_ is None:                       # a notification: never answer
        return None
    if method == "initialize":
        want = params.get("protocolVersion", "2024-11-05")
        return _result(id_, {"protocolVersion": want if want in PROTOCOLS else "2024-11-05",
                             "capabilities": {"tools": {"listChanged": False}},
                             "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}})
    if method == "ping":
        return _result(id_, {})
    if method == "tools/list":
        return _result(id_, {"tools": [_public(t) for t in TOOL_TABLE]})
    if method == "tools/call":
        name = params.get("name"); args = params.get("arguments") or {}
        t = _BY_NAME.get(name)
        if not t:
            return _error(id_, -32602, f"unknown tool: {name}")
        try:
            out = t["handler"](args)
            return _result(id_, {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                                 "isError": not bool(out.get("ok", True))})
        except Exception as e:  # noqa: BLE001
            return _result(id_, {"content": [{"type": "text", "text": json.dumps({"ok": False, "error": str(e)})}],
                                 "isError": True})
    return _error(id_, -32601, f"method not found: {method}")


def serve_stdio():
    """One JSON-RPC message per line on stdin, one per line on stdout. Nothing else ever goes to stdout."""
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out.write(json.dumps(_error(None, -32700, "parse error")) + "\n"); out.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n"); out.flush()


if __name__ == "__main__":
    serve_stdio()
