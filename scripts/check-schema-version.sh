#!/usr/bin/env bash
# Pre-commit guard: refuse a commit that touches src/vera/schema.py
# without bumping the SCHEMA_VERSION constant.
#
# Reasoning is in CONTRIBUTING.md "Schema contract" — the schema is
# the wire format shared by firmware, bridge, trainer, and inference,
# so any silent drift breaks deployments. The script is opt-in (not
# wired into a hook by default); install with:
#
#   ln -s ../../scripts/check-schema-version.sh .git/hooks/pre-commit
#
# Or call it manually with `bash scripts/check-schema-version.sh`.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if ! git diff --cached --name-only | grep -q '^src/vera/schema\.py$'; then
  exit 0  # schema.py not in this commit — nothing to check
fi

# Look for a SCHEMA_VERSION change in the staged diff.
if git diff --cached -- src/vera/schema.py | grep -qE '^[+-]\s*SCHEMA_VERSION\s*[:=]'; then
  exit 0  # SCHEMA_VERSION is part of the staged change
fi

cat >&2 <<'EOF'
ERROR: src/vera/schema.py is staged but SCHEMA_VERSION was not bumped.

The wire schema is shared by firmware, bridge, trainer, and inference.
Any column rename, reorder, or addition is a breaking change. Either
bump SCHEMA_VERSION in this same commit, or unstage the schema.py
change.

To bypass this check (e.g. for a comment-only edit), use:
   git commit --no-verify

EOF
exit 1
