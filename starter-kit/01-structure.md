---
type: law
name: Structure
tier: locked
---

# 01 · Structure

**Template.** Adjust the vocabulary to your world; keep the mechanics.

## Front-matter schema

Every entry file opens with this block. The axis fields are what `baseline.py` measures, so they
must be present and spelled consistently.

```yaml
---
type: figure | place | route | legend | object | vignette | law
name: Display Name
aka: [alternate, names]        # optional
tier: locked | firm | drift
lanes: [1, 4]                  # thread(s) this belongs to
generation: before | origin | middle | reckoning | after
region: <region-tag> | multi | n-a | held
first_seen: <slug>
derives_from: [capture:2026-08-13-harbour-room, the-salt-barn]   # REQUIRED. see below
tags: [drift, rumor, "bad record"]   # optional register tags
---
```

## `derives_from`, and why it is required

**Every entry must trace back to something a human supplied.** The field names this entry's
*immediate* parents, one hop, not the whole chain. Resolving it recursively must terminate in a
root, and there are only two kinds of root:

- **`capture:<id>`** — an author drop in `captures/CAPTURED.md`.
- **`law:<name>`** — a law, lexicon term, or standing directive the author wrote.

Anything else is an intermediate. An entry whose ancestry terminates only in machine output is an
**orphan** and is a defect regardless of quality; `check` reports them.

Multiple parents are normal and are how composites get declared. **Name every one.** An
undeclared composite cannot be reviewed, and a later pass reading a short list will build on a
source that does not exist.

Distance from the root is not limited and never counts against an entry. A capture about a rented
room may legitimately become a legend about a harbour on the other side of the world, five hops
out. The requirement is that the line home exists and is written down.

## Tiers

- **`locked`** — cannot change. Quote exactly. Reserved for the laws, a handful of lines of
  dialogue, and anything the world's identity rests on.
- **`firm`** — real and citable. Changing one requires a dated changelog line in the file, with an
  in-world reason.
- **`drift`** — deliberately unsettled. Points at the drift registry.

## Axis vocabulary

**Lanes** are the world's parallel threads. Six to eight is the useful range. Name them so that
"which lane is this" has an obvious answer, and so that a healthy world keeps all of them fed.

**Generations** are eras. Five is plenty. Use words, not dates, so the world can stay vague about
its own calendar.

**Regions** are geography tags. Add `n-a` for entries where place genuinely does not matter and
`held` for entries whose location is deliberately unresolved. Both are real answers, and neither
should be used to avoid a decision.

## Required sections

Every entry, without exception:

- **Body prose.**
- **`## Connections`** — a line of `[[links]]` to neighbours, plus any lexicon terms used. A link
  to something that does not exist yet is not an error. It is a seed.
- **`## Deepen-me`** — its own next questions. Mark the ones that must **never** be answered, and
  say so in the line itself.

Vignettes additionally require:

- **`## Provenance`** — what came from a capture, what the engine generated, which captures were
  combined, and which held questions the piece touched without resolving.

## Slugs and renames

The filename stem is the slug and is what `[[links]]` resolve against. **After any rename, grep
for both the old and the new form.** Fixing the references you remember writing and missing the
ones you do not is the standard regression.
