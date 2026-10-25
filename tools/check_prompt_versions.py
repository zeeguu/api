#!/usr/bin/env python
"""
Fail when a prompt's text changes but its version name does not.

Every stored LLM output points at an AIGenerator row naming the model and the
prompt version that wrote it, and stale outputs are found by querying that
version. A prompt edited in place keeps its old name, so the stamp then names
two different texts, and a query for the old version returns rows written by
the new one. That is how ~900 audio lessons could only be found by a regex over
their scripts (May 2026).

This keeps a hash of the text of every versioned prompt in
zeeguu/core/llm_services/prompts/prompt_versions.lock.json:

    python -m tools.check_prompt_versions            # check (CI runs this)
    python -m tools.check_prompt_versions --update   # record new versions

--update only adds versions it has not seen and drops removed ones. It refuses
to change the hash of an existing version: that is exactly the edit the check
is there to catch. Give the prompt a new version instead.

Which prompts are covered:
  - audio lesson prompt files named ...-vN.txt (the version is the file name)
  - prompt modules in llm_services/prompts with a PROMPT_VERSION constant
  - each entry of EXAMPLE_GENERATION_PROMPTS, keyed by its version

Only string literals are hashed, not the code around them: comments,
formatting and Python version do not change a hash, but a prompt assembled by
code from unversioned pieces is not covered. Unversioned prompts (the article
simplification ones, the older unversioned lesson files) are not covered
either; they have no name to bump.

Standard library only, so CI can run it without installing the app.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LESSON_PROMPTS = os.path.join(ROOT, "zeeguu", "core", "audio_lessons", "prompts")
LLM_PROMPTS = os.path.join(ROOT, "zeeguu", "core", "llm_services", "prompts")
LOCK = os.path.join(LLM_PROMPTS, "prompt_versions.lock.json")

VERSIONED_FILE = re.compile(r"-v\d+\.txt$")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strings(node, skip=()):
    """The string literals under node, in source order, except the nodes in skip."""
    found = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n not in skip:
            found.append((n.lineno, n.col_offset, n.value))
    return [s for _, _, s in sorted(found)]


def _module_level(tree, name):
    """The value node assigned to a module-level name, or None."""
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return stmt.value
    return None


def lesson_prompt_files():
    for name in sorted(os.listdir(LESSON_PROMPTS)):
        if VERSIONED_FILE.search(name):
            with open(os.path.join(LESSON_PROMPTS, name), encoding="utf-8") as f:
                yield f"audio_lessons/prompts/{name}", _sha(f.read())


def prompt_modules():
    for name in sorted(os.listdir(LLM_PROMPTS)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(LLM_PROMPTS, name), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        module = name[:-3]

        if module == "example_generation":
            prompts = _module_level(tree, "EXAMPLE_GENERATION_PROMPTS")
            for key, value in zip(prompts.keys, prompts.values):
                yield f"{module}:{key.value}", _sha("\n\x00\n".join(_strings(value)))
            continue

        version = _module_level(tree, "PROMPT_VERSION")
        if not isinstance(version, ast.Constant):
            continue
        # The module docstring explains the prompt to developers; editing it
        # changes nothing the model sees.
        skip = {version}
        if ast.get_docstring(tree) is not None:
            skip.add(tree.body[0].value)
        yield f"{module}:{version.value}", _sha("\n\x00\n".join(_strings(tree, skip)))


def current():
    return dict(list(lesson_prompt_files()) + list(prompt_modules()))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--update", action="store_true", help="record new prompt versions")
    args = parser.parse_args()

    now = current()
    try:
        with open(LOCK, encoding="utf-8") as f:
            locked = json.load(f)
    except FileNotFoundError:
        locked = {}

    changed = sorted(k for k in now if k in locked and locked[k] != now[k])
    new = sorted(k for k in now if k not in locked)

    for k in changed:
        print(f"CHANGED IN PLACE: {k}\n  its text changed but its version did not. "
              f"Save the change as a new version and point the code at it.")

    if args.update:
        if changed:
            print("\nNot updating: the lock never changes the hash of an existing version.")
            return 1
        with open(LOCK, "w", encoding="utf-8") as f:
            json.dump(now, f, indent=2, sort_keys=True)
            f.write("\n")
        for k in new:
            print(f"recorded {k}")
        for k in sorted(set(locked) - set(now)):
            print(f"dropped {k}")
        return 0

    for k in new:
        print(f"NEW: {k}\n  run: python -m tools.check_prompt_versions --update")

    if changed or new:
        return 1
    print(f"{len(now)} prompt versions unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
