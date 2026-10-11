#!/usr/bin/env bash
# Regenerate what the pinned Seamly2D (the oracle) computes for each small case pattern:
#   fixtures/patterns/cases/<name>.sm2d  ->  fixtures/oracle/cases/<name>.seamly2d.json
# The case patterns are written by hand (or by a script) to cover one tool in many configurations.
#
#   scripts/oracle_cases.sh [path/to/seamly2d]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-${SEAMLY2D_BIN:-/home/user/seamly2d-build/src/app/seamly2d/bin/seamly2d}}"
BIN="$(realpath "$BIN")"
WORK="$(mktemp -d)"; HOME_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK" "$HOME_DIR"' EXIT
for pattern in "$ROOT"/fixtures/patterns/cases/*.sm2d; do
  name="$(basename "$pattern" .sm2d)"
  cp "$pattern" "$WORK/"   # Seamly2D writes a .lck file next to the pattern
  HOME="$HOME_DIR" QT_QPA_PLATFORM=offscreen YOKO_ORACLE_DUMP="$WORK/$name.json" \
    timeout 120 "$BIN" --test "$WORK/$name.sm2d" >/dev/null 2>&1
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); open(sys.argv[2],"w").write(json.dumps(d,indent=1))' \
    "$WORK/$name.json" "$ROOT/fixtures/oracle/cases/$name.seamly2d.json"
  echo "refreshed fixtures/oracle/cases/$name.seamly2d.json"
done
