# Yildun

A writing system for building your own world from your own material, with a person in charge of every
choice the AI would otherwise make alone. The tools surface, propose, check, and assemble. They do not compose the prose
or score its quality; you do. Yildun is world-agnostic: it reads an optional `world.json` and
otherwise falls back to convention, so it runs on any corpus, not one particular world.

## Two tracks

- **Fiction.** Build a story from your own real sources, fused so that no single real person survives.
- **Non-fiction.** Keep your own real people and facts, with a source for every claim and consent for
  every living person you name.

## Quick start

```
yildun new my-piece              # start a fiction piece (add --nonfiction for the other track)
yildun surface                   # show story material the corpus already holds
yildun amr accept "why"          # log an Accept / Modify / Reject decision as it happens
yildun check my-piece            # run every gate; says PASSED or stops at the first problem
```

Run the command with Yildun's full path, or put the folder on your `PATH`. Set `YILDUN_AUTHOR` so the
AMR log records who decided.

## The gates

`yildun check` runs a stack, and which gates apply depends on the track:

- **Voice** (`voicelint`, vendored from pherkad): reads like the world's voice, not marketing or a
  chatbot; no em dashes.
- **Parrot** (`check-transcription`): you transformed the source, you did not dictate it.
- **Rooted** (`provenance-map`): every piece traces to a human origin.
- **Mask / Fragmentation** (fiction): masked identities are on record, and a shippable composite draws
  on two or more real sources with no verbatim survival and no real name.
- **Accuracy / Consent** (non-fiction): claims cite declared sources, and each named living person has
  a consent status.

## Voice is not owned here

The voice rules live in [pherkad](https://github.com/btmoriarty/pherkad), the single source of truth.
`tools/voicelint.py` is vendored from it, never forked; `tools/sync-voicelint.sh` re-vendors it. Set
`PHERKAD_VOICELINT` to your pherkad checkout to re-sync, and `WORLD_STRUCTLINT` to pherkad's
`structlint.py` to add the structural gate. `tools/voice_config.json` ships neutral; customize it for
your world.

## The run loop

`tools/run.py` closes a unit of work: it validates the changed shareable files against the gate,
appends one line to the generation log with author identity, and commits, never pushing. Generation is
done by whatever agent you point at the corpus; this is the harness around it. A gate block stops the
run before anything is logged or committed.

```
python3 tools/run.py --note "what this run did" --mode expand
```

Pass `--oversight <mode>` (see `tools/oversight-modes.json`) to set the review posture: it raises or lowers gate strictness, commits or holds the commit for you, and records the mode as the study's oversight variable.

## Export

`tools/export.py` is the export gate: it verifies a shippable piece against the gate, strips invisible
watermark characters so no distributed file carries a hidden mark, renders the shareable prose to a PDF
with author, title, and date in the PDF metadata, and writes a provenance sidecar. Content Credentials
(C2PA) embed where the format and c2patool support it.

## Getting material on disk

`references/INTERROGATION.md` is the elicitation protocol: how to draw real material out of memory, one
side-door question at a time, before any fiction is written. `starter-kit/` scaffolds a new world.

## Layout a world uses

By convention, with `world.json` able to override any of it: `canon/` for world-building, `generated/`
for captures and derivations, `deliverables/` for assembled work. Nothing about one particular world
ships in this engine.
