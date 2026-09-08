#!/usr/bin/env python3
"""worldconfig.py - resolve a world's layout for the engine tools.

The narrative engine assumes a conventional layout: pieces in generated/derivations, captures in
generated/CAPTURED.md, canon in canon/, shareable prose in canon/ and deliverables/, the world's
voice config in tools/voice_config.json, a gesture bank under generated/derivations. A world may
override any of these in a world.json at its root. Relative values resolve against the world root;
absolute values are used as given; structlint is always absolute-or-empty and never root-joined.

This is what makes the engine world-agnostic. Nothing saga-specific is compiled into a tool: vendor
tools/ into any world, drop a world.json beside it (or accept the defaults), and the same tools run
against that world. It is also what keeps a private world private: a student running the engine can
only ever reach the world their own config points at.

Resolution of the config file: $WORLD_CONFIG, then world.json at the world root (the parent of the
tools dir), then none (pure defaults).

As a CLI: `worldconfig.py <key>` prints one resolved value (used by lint-voice.sh from bash).
"""
import json
import os
import sys

DEFAULTS = {
    "corpus_dir": "generated/derivations",
    "captures": "generated/CAPTURED.md",
    "canon_dir": "canon",
    "deliverables_dir": "deliverables",
    "voice_config": "tools/voice_config.json",
    "gesture_bank": "generated/GESTURE-BANK.md",
    "mask_map": "generated/mask-map.tsv",
    "author": "",  # world author id; passed through raw, not a path
    "protagonist": [],  # the world's protagonist name(s), matched case-insensitively; kept out of recommendations
    "shareable_trees": ["canon", "deliverables"],
    "structlint": "",  # absolute path to pherkad's structlint.py, or "" to skip that gate
}


def _engine_root():
    # tools/ live under the world root; the root is the parent of this file's directory.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_path(root):
    p = os.environ.get("WORLD_CONFIG")
    if p and os.path.exists(p):
        return p
    cand = os.path.join(root, "world.json")
    return cand if os.path.exists(cand) else None


def load():
    root = _engine_root()
    data = {}
    cfgp = _config_path(root)
    if cfgp:
        try:
            data = json.load(open(cfgp, encoding="utf-8"))
            root = os.path.dirname(os.path.abspath(cfgp))
        except (OSError, ValueError):
            data = {}

    def resolve(key):
        v = data.get(key, DEFAULTS[key])
        if key == "structlint":
            return v or os.environ.get("WORLD_STRUCTLINT", "")
        if key == "author":
            return v
        if key == "protagonist":
            return v
        if isinstance(v, list):
            return [x if os.path.isabs(x) else os.path.join(root, x) for x in v]
        return v if os.path.isabs(v) else os.path.join(root, v)

    cfg = {k: resolve(k) for k in DEFAULTS}
    cfg["root"] = root
    return cfg


if __name__ == "__main__":
    cfg = load()
    if len(sys.argv) > 1:
        val = cfg.get(sys.argv[1], "")
        print(" ".join(val) if isinstance(val, list) else val)
    else:
        print(json.dumps(cfg, indent=2))
