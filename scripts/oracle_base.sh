#!/usr/bin/env bash
# Regenerate everything the pinned Seamly2D (the oracle) says about the basic pattern set:
#   fixtures/oracle/base_set.seamly2d.json                 what it computed (points, curves, variables)
#   fixtures/oracle/base_set.upgraded.sm2d                 the pattern as it saves it (format 0.7.5)
#   fixtures/oracle/base_set.measurements.converted.smms   the measurement table as its converter upgrades it
#
#   scripts/oracle_base.sh [path/to/seamly2d]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-${SEAMLY2D_BIN:-/home/user/seamly2d-build/src/app/seamly2d/bin/seamly2d}}"
PIN_VERSION="2026.10.5.154"
BIN="$(realpath "$BIN")"
WORK="$(mktemp -d)"; HOME_DIR="$(mktemp -d)"; CONV="$(mktemp -d)"
trap 'rm -rf "$WORK" "$HOME_DIR" "$CONV"' EXIT
cp "$ROOT"/fixtures/patterns/base/*.sm2d "$ROOT"/fixtures/measurements/*.smms "$WORK/"   # Seamly2D writes a .lck file
HOME="$HOME_DIR" QT_QPA_PLATFORM=offscreen \
  YOKO_ORACLE_DUMP="$WORK/dump.json" \
  YOKO_ORACLE_SAVE="$ROOT/fixtures/oracle/base_set.upgraded.sm2d" \
  YOKO_ORACLE_CONVERTED_DIR="$CONV" \
  timeout 120 "$BIN" --test "$WORK/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d" >/dev/null 2>&1
# keep the hand-written _provenance note that sits in the committed file
python3 - "$WORK/dump.json" "$ROOT/fixtures/oracle/base_set.seamly2d.json" <<'PY'
import json, sys
fresh, committed = sys.argv[1], sys.argv[2]
data = json.load(open(fresh))
try:
    data = {"_provenance": json.load(open(committed))["_provenance"], **data}
except (OSError, KeyError):
    pass
open(committed, "w").write(json.dumps(data, indent=1))
PY
sed -i "s/Seamly2D v0\.6\.0\.1 /Seamly2D v$PIN_VERSION /" "$ROOT/fixtures/oracle/base_set.upgraded.sm2d"
cp "$CONV/Aldrich-Womens-MultiSize-06-14.smms" "$ROOT/fixtures/oracle/base_set.measurements.converted.smms"
# QDomDocument::save orders attributes by Qt version: keep the copy in canonical form
python3 "$ROOT/scripts/canon_xml.py" "$ROOT/fixtures/oracle/base_set.measurements.converted.smms"
echo "refreshed fixtures/oracle/base_set.*"
