#!/usr/bin/env bash
# Run real Seamly2D headless on a pattern and write everything it computed (points, curves, variables)
# as JSON. Needs a build from docker/oracle/build-local.sh (or the CI oracle image).
#
#   scripts/oracle_dump.sh <pattern.sm2d> <out.json> [path/to/seamly2d]
set -euo pipefail
PATTERN="$(realpath "$1")"
OUT="$(realpath -m "$2")"
BIN="${3:-${SEAMLY2D_BIN:-$HOME/seamly2d-build/src/app/seamly2d/bin/seamly2d}}"
HOME_DIR="$(mktemp -d)"   # Seamly2D writes settings; keep them out of the real home
HOME="$HOME_DIR" YOKO_ORACLE_DUMP="$OUT" QT_QPA_PLATFORM=offscreen \
  timeout 300 "$BIN" --test "$PATTERN" >/dev/null 2>"$HOME_DIR/stderr.log" || {
    echo "seamly2d failed:"; tail -5 "$HOME_DIR/stderr.log"; exit 1; }
echo "wrote $OUT"
