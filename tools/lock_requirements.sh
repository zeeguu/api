#!/bin/bash
# Compile requirements.txt into requirements.lock for the server's platform.
# Extra arguments go to uv: --upgrade-package <name>, or --upgrade.
# Without them, packages already in the lock keep their versions.
set -e
cd "$(dirname "$0")/.."
uv pip compile requirements.txt \
    --python-version 3.12 \
    --python-platform x86_64-manylinux_2_28 \
    --no-header --annotation-style line \
    -o requirements.lock "$@"
