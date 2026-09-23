# Yildun desktop connector

The writing front-end for the Claude desktop app. A writer works entirely in the app: they ask for
help, react to suggestions in plain words, and their document and Accept/Modify/Reject log build
together, with no terminal, no copy-paste, and no separate log command. This connector exposes the
Yildun tools to the app; `PROJECT.md` is the behaviour that rides on top of it.

## What it provides

An MCP server (`server.py`) with ten tools the app can call: `open_piece`, `read_piece`,
`save_piece`, `append_piece`, `log_decision`, `writing_status`, `check_piece`, plus `checkin_start`
and `checkin_save` for the weekly check-in, and `sync_work`, which commits and pushes the writer's
folder so nothing is lost. The logging tool wraps
the existing `tools/amr-log.py`, so entries land in the same schema as the command-line `yildun amr`,
and `check_piece` runs the same `tools/lint-voice.sh` gate. Nothing here forks the format.

## Install (one time, on the writer's machine)

**Prerequisite, and it is the one that actually bites: the writer's machine needs a python3 the desktop
app can find.** The manifest calls the interpreter as bare `python3`, and the app resolves that against a
path list it builds itself rather than against a login shell, so nothing in `.zshrc` or `.bash_profile`
reaches it. The app logs which one it picked, and this is the line to read:

```
Using MCP server command: /opt/homebrew/bin/python3 with path: { ... }
```

A machine with no reachable python3 installs the bundle perfectly and then reports **"Unable to connect
to extension server"** on every enable. Disabling, enabling and restarting the app do not clear it,
because none of them change the environment. On macOS this is a bare machine with no Xcode command line
tools, where `/usr/bin/python3` exists as a stub that does not run; on Windows `python3` usually resolves
to nothing at all. **Send the writer to python.org for the installer rather than to a terminal**, because
it needs no command line and it lands in `/usr/local/bin`, which is on the list the app searches.


The connector ships as an MCP bundle, `yildun.mcpb`, built by `build-bundle.sh` from `server.py`,
`PROJECT.md`, and the `tools/` gates. It runs on python3 alone, no packages and no `uv`.

**In a lab workspace, the writer installs it from the app's own extension list, not from a file.** Once an
organization turns on the desktop extension allowlist, members can no longer install an MCPB by dragging or
double-clicking one, and an attempt returns "Contact your organization owner". The owner uploads the bundle
once (Organization settings, Connectors, Desktop tab, Add custom extension), then adds it to the team from
the entry's kebab menu, and it appears in the members' list for a one-click install. The writer fills in the
two fields the bundle asks for: author name, and the work folder inside their clone of the study repo.

To ship a new version, keep the manifest `name` unchanged, increment its `version`, and use "Upload new
version" on the existing entry. Changing the name creates a second extension instead of replacing the first.

**Outside a workspace**, double-click `yildun.mcpb` on a machine with the Claude desktop app and fill in the
same two fields. Check the file first:

```
shasum -a 256 yildun.mcpb
```

```
656be36e8cb3fa37fa3fe9a39d2d4048de563505dbd523b568bc599636d9c0f5
```

The build is reproducible, so `build-bundle.sh` on the same source reproduces that hash exactly.

Then create a Project, paste `PROJECT.md` as the Project instructions, and write inside that Project.

### Developer install, without the bundle

Add the server to `claude_desktop_config.json` directly (adjust the absolute paths):

```json
{
  "mcpServers": {
    "yildun": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/yildun/connector/server.py"],
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

## Where the work lands, and how to retrieve it

`YILDUN_DRAFTS` is the writer's folder, and it must sit inside a clone of the study's git repo (for
example `<clone>/students/<name>`). Their document (`<piece>.md`), log (`<piece>.amr.jsonl`), and
weekly check-ins (`checkins/`) are written there, and `sync_work` commits and pushes the whole clone,
so the work is recoverable and the mentor pulls it from the remote. Never a tmp dir. At setup, clone
the study repo on the writer's machine, set `git config user.name` and `user.email` there so the
commits carry their name, and make sure a push works once by hand before the first session. The log is JSON Lines, one flat object per decision, so it converts to CSV
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

The tool logic in `server.py` is plain functions (`do_open`, `do_log`, `do_status`, `do_check`, ...),
and the MCP transport is a small standard-library JSON-RPC loop with no dependency, so both can be
exercised directly with `YILDUN_DRAFTS`, `YILDUN_AUTHOR`, and
`YILDUN_ENGINE` set, before wiring the server into the app.

## When a writer says it will not connect

Read the log before changing anything. On macOS:

```
sed -n '1,3p' "$HOME/Library/Logs/Claude/mcp-server-Yildun writing partner.log"
```

Line 3 names the interpreter the app resolved. If it names a path, the interpreter was found and the
fault is further in; if the file does not exist or the line is missing, the server was never started and
the prerequisite above is the cause.

To see what is installed and how it got there:

```
ls "$HOME/Library/Application Support/Claude/Claude Extensions"
```

A `local.mcpb.` prefix means the bundle was installed from a file rather than from the workspace list.
In an allowlisted workspace that should not be possible, so a writer who has one either installed it
before the allowlist was turned on or is not in the workspace at all. **That distinction matters more
than the error does**, because it decides whether the problem is their machine or their membership.
