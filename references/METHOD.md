# The Method

Six mechanisms. Each exists because something failed without it. None of them is about any
particular world, which is why they transfer.

---

## 1. The drift registry, and the closure rule

A file of questions the world has deliberately not answered. Who somebody really was, which of
two endings happened, whether two figures are the same person, what a name even is.

**The rule: no run may close anything. Only the author, in writing, dated.** Opening a drift is
free. Closing one is not, and neither is resolving one by inference, which includes writing prose
that only works if it were resolved.

**Why.** An engine that can answer its own open questions will answer all of them, because at
every individual moment resolving looks like progress. What it is actually doing is spending the
world's depth for content. A held question compounds: every new entry that touches it without
settling it makes it heavier. A closed one is inert.

The registry is also the honest record of what the machine is not permitted to decide, which is
what makes an automated world safe to run unattended.

**Practice.** Every entry that touches a held question says in its own notes which drift it
touched and how it avoided resolving it. That way a later pass cannot resolve one by accident.

## 2. `Deepen-me`

Every entry ends with a short list of its own next questions. Some are seeds to be answered later.
Some are marked **never to be answered**, and those are the good ones.

**Why.** It makes the world self-replenishing: there is never a blank page, because every entry
tells you what it needs. And writing down what must *not* be answered, at the moment you are
closest to the material, is the only reliable way to protect it from a future pass that has less
context and more enthusiasm.

## 3. Rooted invention: capture, canon, and the trace

**The principle first: all of it has a basis in what the person provided.** The machine may expand
the universe of ideas interminably. What matters is that a trace back to an original human idea
exists, and is written down, and can still be followed years later by somebody who was not there.

This is not a limit on scale or on distance. A world can run to thousands of entries and travel
arbitrarily far from any given seed. The constraint is only that no branch grows from nothing but
other branches. Roots are the author's **captures** and the author's **laws**; everything else
descends from those via `derives_from`, one hop per entry, recursively resolvable. `baseline.py`
reports what fails to resolve.

**Why it earns its cost.** An engine left to feed on its own output produces steadily more of a
world and steadily less of a person's, and the drift is invisible from inside, because every
individual step is defensible. The trace is the only thing that keeps *whose idea was this,
originally* answerable, and answerable is what makes an unattended run safe to leave running.

The mechanics underneath it:

Two tiers, strictly separated.

- **Captures** are the author's raw material, recorded verbatim, upstream. Never published.
- **Canon** is the fiction. It shows masked figures only.

And in every canon file, a **provenance note**: what came from a capture, what the engine
generated, and which captures were combined.

**Why the separation.** It is what makes candour safe, and candour is what makes the fiction
specific.

**Why the provenance note.** Without it, an engine will merge two real people into one figure
while believing it is working from a single source, and it will not know it has done so. The
result may be good; the process is unreviewable, and a later pass reading a wrong note will build
on a source that does not exist. **An undeclared composite is the failure. The composite itself
is a legitimate technique.**

## 4. Rotation axes and a baseline

Pick a few axes the world should stay spread across: lanes or threads, eras, geography, entry
type. Then **measure the distribution with a script**, not by feel.

**Why.** Everyone believes they are writing broadly and nobody is. Attention follows the parts
that are already rich, so rich parts get richer and the rest silently starves.

**The finding that makes this worth automating:** rotation shares count *entries*. Deepening an
existing entry adds words and moves nothing. A thread fed only by deepens will read as starved on
every report while feeling well-tended from inside. Feed a starved axis with **new entries**.

`starter-kit/baseline.py` does this with no dependencies.

## 5. A linter as a build gate

A short list of banned constructions, checked mechanically, run **before** any commit and as its
own step.

**Why mechanical.** Voice rules that live only in a prompt decay across a long session. A checker
does not get tired at hour six.

**Why a separate step.** Chaining lint into the commit command means a failing lint still ships,
because the commit has already been typed. Run it, read it, then commit.

## 6. The influence dial

State a mix of influences as percentages and write to it: *28% Serling, 16% Carver, 32%
Stephenson, 14% Proust.*

- **A percentage is a share of contested decisions, not a share of text.** Every sentence poses
  choices: stop or continue, explain or withhold, name the feeling or leave it. The mix is the
  standing answer to who wins.
- **Interweaving works because influences own different channels** and operate simultaneously:
  one owns architecture and endings, another texture and length, another dialogue and the brake,
  another interiority and duration.
- **25% and up is ambient**, present in most paragraphs. **10 to 24% is punctual**: wholly present
  in one or two placements chosen for where only that influence can do the job. **Below 10% is a
  single gesture or nothing.**
- **Some channels are near-binary.** A piece either has the fable turn or it does not; a reality
  either destabilises or it does not. Round those to zero or to present and say which.
- **A mix is composable and not measurable.** Prose can be written to a specification and cannot
  be scored back to one. If asked what a finished piece "came out at", any number you give is
  invented. It is a composition instruction, never a metric.

---

## The one that is not a mechanism

**Contradiction is handled by register, not by parallel worlds.**

When two parts of the world disagree, do not invent a multiverse. Tag the weaker one: *bad
record*, *false memory*, *rumor*, *repaired lie*, *inner cinema*. The contradiction stays, and it
now means something about how the world remembers rather than about how many worlds there are.

This is worth the discipline it costs. A multiverse makes every contradiction free, and once
contradictions are free nothing in the world can be wrong, and once nothing can be wrong nothing
matters.
