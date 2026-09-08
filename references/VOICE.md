# Voice

How a world gets a register of its own, and how that register is enforced rather than merely hoped for.

Required reading before any prose mode (`new-scene`, and any deepen that writes body text).

---

## 1. The world's voice is not the author's voice

These are two different objects and confusing them ruins both.

- **The author's own voice** is how they write when they are being themselves: correspondence, a
  proposal, a post. If they have a personal voice profile, it governs anything they will **send or
  publish as themselves**, and it does not govern the fiction.
- **The world's voice** is a constructed register. It is a mask, deliberately not the author, built
  to serve the world's subject.

Running the author's personal voice over the fiction flattens the fiction toward the author, which is
the opposite of what the mask is for. Running the world's voice over their correspondence makes them
sound like a novel.

**Keep them in separate files with separate enforcement, and say in each which is which.** The
overlap is real but partial: the anti-AI tells in section 4 apply to both, because those are not
style, they are failure.

## 2. Establishing the register, when the world has none yet

A new world has no voice file. Do not ask the author to write one, and do not draft one from nothing
and ask for approval. Both fail the same way as a bulk memory request: they demand a specification
for something nobody can specify in the abstract.

**Derive it from material that already exists**, in this order:

1. **Their captures.** The interrogation has already produced pages of their own phrasing. Their
   sentence length, their idiom, what they refuse to dramatise. Read it as a style sample.
2. **One test paragraph.** Write a short passage of the world, deliberately, in a register you can
   defend. Show it and ask only what is wrong with it. **Reacting to a draft is easy where
   specifying a voice is impossible**, which is the same recognition-over-recall move the
   interrogation uses.
3. **Their corrections become the file.** Every time they strike something, write down the rule
   behind the strike, not just the instance. A ban with a stated reason survives; a list of
   forbidden words does not.

Start the file with three or four rules and let it grow to twenty. A voice law written up front,
before any prose exists, is a guess dressed as law.

## 3. What a voice file must contain

| Section | What it holds |
|---|---|
| **Register** | The concrete identity of the prose in a sentence or two. Not adjectives. What it does. |
| **Hard prohibitions** | Things never written, each with the reason. |
| **Tells** | Patterns that are not individually wrong and are fatal at density. |
| **The judgment layer** | What no checker can catch. Section 5. |
| **Scope** | Which files the law binds, and which it does not. |
| **Exemptions** | Claimed explicitly, in writing, with the ruling that granted them. |

**Scope is the section everyone forgets and it causes the most trouble.** State plainly whether the
law covers only canon prose, or also notes, commit messages, and what the engine says in chat. An
unstated scope gets read as *everything*, and then a rule meant for fiction starts mangling a commit
message.

## 4. The anti-AI tells: ship these into any world

These are not stylistic preferences. They are the specific ways machine prose announces itself, and
they should be banned in a new world by default, subject to the author striking any of them.

- **Announcing candour instead of exercising it.** *The honest answer, to be clear, I want to be <!-- voicecheck:allow -->
  direct, let me be upfront.* Nearly always deletable, and the sentence after it is the candid one.
  <!-- voicecheck:allow -->
- **Antithesis at density.** *Not X, but Y.* One is a legitimate move. Two in adjacent sentences is
  the single loudest tell in machine prose, and a paragraph built entirely of them cannot be saved.
- **The summarising last sentence** that restates the paragraph in more abstract words. Cut it. The
  paragraph already did the work.
- **Naming the feeling.** *She felt a profound sense of loss.* <!-- voicecheck:allow --> Fatal in fiction. Put the feeling in
  the furniture or leave it out.
- **Filler and intensifiers.** *Really, very, quite, simply, just, genuinely, honestly, truly,
  actually, incredibly.* <!-- voicecheck:allow --> Almost never survive deletion.
- **Rule-of-three cadence** used as rhythm rather than because there are three things.
- **Dead structural metaphor.** *Load-bearing, cornerstone, linchpin, backbone* used figuratively. <!-- voicecheck:allow -->
  Name the function instead. Reaching for a different metaphor of structural support is the same
  failure with extra steps.
- **Hedge stacks.** *It may perhaps be somewhat.* <!-- voicecheck:allow --> Pick one hedge or none.
- **Elegant variation.** Calling the same object three different things to avoid repeating a noun.
  Repeat the noun.

Add a punctuation policy while you are here, and hold it. Which dash the world uses, whether it uses
one at all, and what replaces it. This is arbitrary and it does not matter which way it goes; what
matters is that it is decided once rather than drifting per scene.

## 5. The judgment layer, which no checker can see

A linter catches strings. These need a reader, and they are the ones that actually make prose sound
machine-made:

- **Cadence sameness.** Every sentence the same length. Vary it or the prose hums.
- **Explaining the joke.** The line after the good line, telling you it was good.
- **Symmetry that reality would not have.** Four examples where three exist, a list that balances.
- **Every scene resolving.** Real events trail off. A world where every scene lands is a world of
  episodes rather than a world.
- **Unearned lyricism** at paragraph ends, where the prose reaches for beauty because it has run out
  of material.
- **Correct-sounding invented precision.** A weight, a distance, a statute, a season length,
  generated because the sentence wanted a number. This is the failure that poisons everything near
  it, because once the author catches one, every other fact is suspect.

## 6. The output gate

**Decide, in writing, whether the engine may show the author prose it is not confident is in voice.**

The strict setting is that it may not: while the voice is still being trained, the engine prefers
capture, structure and analysis over finished prose, and writes scenes only when the author is
present to reject them. The loose setting is that it drafts freely and the author culls.

Either is defensible. What is not defensible is leaving it unstated, because the engine will then
default to producing prose, and a headless run will fill the world with unrejected text that is
tonally wrong and now has to be unpicked from entries that reference it.

**If the gate is strict, say what an unattended run does instead**, or it will simply stop being run.

## 7. Mechanical enforcement

A voice law nobody can check is a voice law nobody follows. Ship a checker with the world, however
crude. `starter-kit/voicecheck.py` here is a starting point: it reads `voice-bans.txt`, reports file,
line and column, skips fenced code, and exempts any line marked `voicecheck:allow` so that a rules
file can quote what it forbids.

Three rules about it, all learned the hard way:

1. **The checker is a floor, not a ceiling.** Passing means no banned string is present. It says
   nothing about section 5, and a clean run is not a voice review.
2. **Lint and commit as separate steps.** Chaining them ships broken files.
3. **When the checker catches the engine, say so plainly in the run output.** A tool that only ever
   reports on the author's prose looks like a tool for policing the author. Its most valuable catches
   are the engine's own.

## 8. Influences do not touch the register

Whatever writers the world dials in (see `INFLUENCES.md`), they are rendered **through** the world's
register, never as pastiche. A mix allocates influence over decisions. It does not change the
identity of the prose, and **no combination of weights licenses a narrator made of dead novelists.**

If a passage reads as an imitation of one of the named influences, the mix is not being applied. It
is being performed, and it should be rewritten in the register with the influence expressed as
choices rather than as costume.
