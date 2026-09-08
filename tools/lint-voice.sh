#!/usr/bin/env bash
# Saga voice gate, mechanical layer. Wraps the vendored voicelint.py with the saga
# config so callers do not have to remember the --config path.
#
# Usage:
#   tools/lint-voice.sh                      # sweep the whole shareable tree (canon/**, deliverables/**)
#   tools/lint-voice.sh path/to/file.md ...  # lint specific files (what the nightly does on what it wrote)
#   tools/lint-voice.sh --strict ...         # promote warnings to failures
#
# Scope per the world's voice law: this binds SHAREABLE prose only (canon entries, vignettes,
# legends, deliverables). It does NOT lint generated/ or routine/ machinery, which use em
# dashes as house style. If no file args are given, it globs the shareable tree and skips
# the machinery automatically.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(dirname "$here")"
cfg="$here/voice_config.json"

# Pass through any flags (e.g. --strict, --json) but supply our config.
flags=()
files=()
for a in "$@"; do
  case "$a" in
    -*) flags+=("$a") ;;
    *)  files+=("$a") ;;
  esac
done

if [ "${#files[@]}" -eq 0 ]; then
  # Default: the shareable NARRATIVE tree. Use find (portable; macOS bash 3.2 has no globstar).
  # Exclude the numbered canon law/reference files (00-*.md .. 08-*.md): they DEFINE and quote the
  # very tells the linter matches, so they false-positive by design (Pherkad's "validator-internals"
  # exemption, which a regex cannot honor). Lint them by hand only if you edit their prose, not
  # their rule definitions.
  while IFS= read -r f; do files+=("$f"); done < <(
    find "$repo/canon" "$repo/deliverables" -name '*.md' -type f \
      ! -name '[0-9][0-9]-*.md' 2>/dev/null | sort
  )
fi

# ${arr[@]+...} guards against "unbound variable" when an array is empty under set -u.
# NOTE: this was `exec` until 2026-08-16. Changed to a plain call so a second, independent
# check can run after it. voicelint.py itself is untouched: pherkad stays the single source
# of truth for voice, and this only adds a step beside it.
# `set -e` IS ON AND THIS COMMAND IS EXPECTED TO FAIL. Without the guard the shell exits the moment
# voicelint reports an error, so check-invisibles, voice-metrics, check-transcription and structlint
# never run. Found 2026-09-02: a draft with one banned phrase was reported as one voicelint error and
# nothing else, and the six transcription findings in the same file were never printed. **The gate
# silently shrank to its first tool exactly when a draft was worst.** Same family as every other
# failure this project has logged: the run reported success at what it did reach.
# VENDOR DRIFT GUARD (the standing pherkad -> engine sync path). voicelint.py is VENDORED from pherkad,
# never forked. This confirms the local copy still matches its recorded sha256 before its results are
# trusted; a drift means someone edited voicelint here instead of in pherkad, and the fix is to
# re-vendor with tools/sync-voicelint.sh (which needs PHERKAD_VOICELINT). Advisory: it reports and does
# not block, because re-vendoring is a deliberate step, not this gate's job.
if [ -f "$here/sync-voicelint.sh" ]; then
  bash "$here/sync-voicelint.sh" --check >/dev/null 2>&1 || \
    echo "lint-voice: voicelint.py has DRIFTED from its pherkad vendor record; run tools/sync-voicelint.sh to re-vendor" >&2
fi

set +e
python3 "$here/voicelint.py" --config "$cfg" \
  ${flags[@]+"${flags[@]}"} ${files[@]+"${files[@]}"}
voice_rc=$?
set -e

# Invisible-character gate (author instruction, 2026-08-16: check the manuscript for
# watermarking as we build). c2patool cannot read markdown at all, so this is the
# manuscript-side check and c2patool's role is at export only.
set +e
python3 "$here/check-invisibles.py" ${files[@]+"${files[@]}"}
invis_rc=$?
set -e

# Prose metrics against the author's own corpus (author instruction, 2026-08-17: make the
# voice updates a feature rather than a reminder). Reports the long-sentence rate, derived
# number/adverb tics and recycled phrases. ADVISORY BY DEFAULT: it always prints, and only
# fails the run under --strict, because the existing corpus already carries findings and a
# hard gate here would block every commit on legacy prose.
if [ -f "$here/voice-metrics.py" ]; then
  python3 "$here/voice-metrics.py" ${files[@]+"${files[@]}"} || true
fi

# Transcription gate (author instruction, 2026-08-30: "You have a tendency to literally
# transcribe my words into sentences rather than use them as inspiration for story crafting."
# He asked for tools that act on simple instructions rather than for a promise to be careful).
# Flags prose that restates a short author note recorded in the file's frontmatter, and
# narration that asserts a verdict instead of causing it. ADVISORY BY DEFAULT, like the metrics.
# 2026-09-04: THE PARROT VERDICT BLOCKS. check-transcription's note-echo/verdict findings stay
# advisory (the corpus carries them, and proper nouns inflate them), but a shape-echo of >=6 beats
# walked through in the author's order is dictation, not derivation, and it exits non-zero on its own.
# The root cause it now catches: notes_from used to cap quoted spans at 600 chars, so a long verbatim
# drop was invisible and the parrot detector saw nothing on exactly the pieces most at risk. Cap
# removed the same day. This is the enforcement half of the "stop sounding like a parrot" fix; the
# seed-brief shuffle is the prevention half.
trans_rc=0
if [ -f "$here/check-transcription.py" ]; then
  set +e
  python3 "$here/check-transcription.py" ${flags[@]+"${flags[@]}"} ${files[@]+"${files[@]}"}
  trans_rc=$?
  set -e
fi

# STRUCTURAL GATE (author instruction, 2026-09-02: "The gate has to run every time you are
# producing text for my review, not just when I remind you").
#
# voicelint matches literal strings. The families that actually sink a draft have no string to
# match: the clipped two-beat parallel, a run of short sentences, a header that strikes a pose,
# and flagged density. Pherkad ships structlint for exactly those and it was never wired in here,
# so saga prose had never been checked for them once. Three drafts in a row passed this gate and
# were returned by the author as AI-speak, which is the gap in one sentence.
#
# Advisory like the metrics, because it over-fires by design and the corpus carries legacy prose.
# Advisory does not mean optional: the output is read before anything reaches the author.
# structlint lives in pherkad (the voice SSoT), whose path is world-specific. Read it from the
# world config (world.json "structlint", or $WORLD_STRUCTLINT); empty means skip the structural gate.
STRUCTLINT="$(python3 "$here/worldconfig.py" structlint 2>/dev/null)"
if [ -f "$STRUCTLINT" ]; then
  python3 "$STRUCTLINT" ${files[@]+"${files[@]}"} || true
else
  echo "lint-voice: structlint not found at $STRUCTLINT; structural families UNCHECKED" >&2
fi

# ROOTED GATE (requirement 8: everything traceable to a human origin, even one sentence). Nothing
# shareable ships whose ancestry does not resolve to a human root (an author drop, captured verbatim,
# an author-attributed provenance block, or the capture store). Only the memory story types
# (derivation / composite / deliverable) are required to be rooted; canon world-building, law and
# working files are skipped by the check's own type filter. Verified 2026-09-06: 0 orphans across the
# whole corpus, so this blocks only genuinely rootless new pieces. Blocks on its own, like the parrot.
rooted_rc=0
if [ -f "$here/provenance-map.py" ]; then
  set +e
  python3 "$here/provenance-map.py" --check ${files[@]+"${files[@]}"}
  rooted_rc=$?
  set -e
fi

# MASK GATE (requirement 4, the unmasked-rebuild guarantee). A shareable memory/adaptation piece may
# not use a mask whose real is unrecorded (the rebuild could not reverse it) -- that BLOCKS. A recorded
# real appearing in shareable prose is reported ADVISORY (a bare first name over-fires; precise leak
# gating belongs to the export boundary). Fiction pieces and personal-record drafts are exempt.
mask_rc=0
if [ -f "$here/mask-gate.py" ]; then
  set +e
  python3 "$here/mask-gate.py" --check ${files[@]+"${files[@]}"}
  mask_rc=$?
  set -e
fi

# FRAGMENTATION GATE (the publication invariant, 2026-09-06). The identifiable material is the author's
# alone and never shared; the only thing that leaves him is a radically-fragmented composite. This
# verifies a SHIPPABLE piece (experience: fiction + composite, or shippable: true) descends from >=2
# real sources, carries no surviving verbatim identifier, and no real name. Raw memory is not shippable
# and is not checked. Blocks on its own.
frag_rc=0
if [ -f "$here/fragmentation-gate.py" ]; then
  set +e
  python3 "$here/fragmentation-gate.py" --check ${files[@]+"${files[@]}"}
  frag_rc=$?
  set -e
fi

# NON-FICTION GATES (spec/NONFICTION-TRACK.md). These act ONLY on pieces marked `mode: nonfiction` and
# shippable; every fiction piece is skipped, so they are safe to run over the whole tree. Under
# non-fiction the fragmentation gate above skips (the real is kept on purpose) and these two replace it:
# ACCURACY requires claims to trace to a declared, cited source; CONSENT requires a status on record for
# each named living person. Both block, like fragmentation does for fiction.
accuracy_rc=0
if [ -f "$here/accuracy-gate.py" ]; then
  set +e
  python3 "$here/accuracy-gate.py" --check ${files[@]+"${files[@]}"}
  accuracy_rc=$?
  set -e
fi
consent_rc=0
if [ -f "$here/consent-gate.py" ]; then
  set +e
  python3 "$here/consent-gate.py" --check ${files[@]+"${files[@]}"}
  consent_rc=$?
  set -e
fi

# IDENTITY (spec section 16, requirement X): every built piece should carry an identity: line
# (author/engine/approved). ADVISORY: reports missing identity so new writes carry it; legacy
# pieces predate the convention and are not retrofitted.
if [ -f "$here/identity-gate.py" ]; then
  python3 "$here/identity-gate.py" --check ${files[@]+"${files[@]}"} || true
fi

if [ $voice_rc -ne 0 ]; then exit $voice_rc; fi
if [ $trans_rc -ne 0 ]; then exit $trans_rc; fi
if [ $rooted_rc -ne 0 ]; then exit $rooted_rc; fi
if [ $mask_rc -ne 0 ]; then exit $mask_rc; fi
if [ $frag_rc -ne 0 ]; then exit $frag_rc; fi
if [ $accuracy_rc -ne 0 ]; then exit $accuracy_rc; fi
if [ $consent_rc -ne 0 ]; then exit $consent_rc; fi
exit $invis_rc
