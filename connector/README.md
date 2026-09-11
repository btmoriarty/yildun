# Yildun desktop connector

The writing front-end for the Claude desktop app. A writer works entirely in the app: they ask for
help, react to suggestions in plain words, and their document and Accept/Modify/Reject log build
together, with no terminal, no copy-paste, and no separate log command. This connector exposes the
Yildun tools to the app; `PROJECT.md` is the behaviour that rides on top of it.

## What it provides

An MCP server (`server.py`) with seven tools the app can call: `open_piece`, `read_piece`,
`save_piece`, `append_piece`, `log_decision`, `writing_status`, `check_piece`. The logging tool wraps
the existing `tools/amr-log.py`, so entries land in the same schema as the command-line `yildun amr`,
and `check_piece` runs the same `tools/lint-voice.sh` gate. Nothing here forks the format.

## Install (one time, on the writer's machine)

1. Make sure `uv` is installed (the server runs under `uv run --with 'mcp<2'`, so nothing needs a
   global pip install). The `mcp<2` pin is deliberate: the SDK's 2.x line renamed the API this server
   uses (FastMCP became MCPServer), so the connector is built and pinned against v1 for reproducibility.

2. Open the desktop app's config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

3. Add the server (adjust the absolute paths):

   ```json
   {
     "mcpServers": {
       "yildun": {
         "command": "/ABSOLUTE/PATH/TO/uv",
         "args": ["run", "--with", "mcp<2", "python",
                  "/ABSOLUTE/PATH/TO/yildun/connector/server.py"],
         "env": {
           "YILDUN_HOME": "/ABSOLUTE/PATH/TO/yildun",
           "YILDUN_DRAFTS": "/ABSOLUTE/PATH/TO/the-writers-folder",
           "YILDUN_AUTHOR": "the-writer-handle",
           "YILDUN_ENGINE": "claude-desktop"
         }
       }
     }
   }
   ```

4. Restart the desktop app. The `yildun` tools should appear as an available connector.

5. Create a Project, and paste `PROJECT.md` as the Project instructions. The writer works inside that
   Project from then on.

## Where the work lands, and how to retrieve it

`YILDUN_DRAFTS` is the writer's folder. Their document (`<piece>.md`) and log (`<piece>.amr.jsonl`)
are written there, durable and append-only, never in a tmp dir. Point `YILDUN_DRAFTS` at a
git-backed folder (a checkout of the writer's own repo, or a synced folder), so the work is recoverable
and the mentor can pull it. The log is JSON Lines, one flat object per decision, so it converts to CSV
trivially when it is time to pool the data.

## Identity

`YILDUN_AUTHOR` is stamped on every AMR entry and cannot be added later, so set it before the writer's
first session. `YILDUN_ENGINE` records which model the suggestions came from.

## The reliability tradeoff, stated plainly

Logging runs through the conversation rather than a hard Accept/Reject button, so it depends on the
partner (guided by `PROJECT.md`) capturing each decision. That is a softer guarantee than a UI control.
Two things backstop it: the desktop transcript is saved, so the verdict-level log can be audited against
the conversation, and `writing_status` makes the running tally visible so a drift between decisions made
and decisions logged is easy to spot. The softness is the price of keeping the writer in the app they
already use, and the study wanted the logger to encourage rather than enforce.

## Testing the core without the app

The tool logic in `server.py` is plain functions (`do_open`, `do_log`, `do_status`, `do_check`, ...)
that do not import MCP, so they can be exercised directly with `YILDUN_DRAFTS`, `YILDUN_AUTHOR`, and
`YILDUN_ENGINE` set, before wiring the server into the app.
