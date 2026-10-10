#!/usr/bin/env bash
# Open every pattern under fixtures/external/seamly2d/original with the pinned Seamly2D (the oracle),
# save it again (which upgrades it to the pinned format) and dump everything it computed.
#
#   scripts/oracle_upgrade.sh [path/to/seamly2d]
#
# Output, mirroring the original tree:
#   fixtures/external/seamly2d/upgraded/<path>.sm2d        the pattern as the pinned Seamly2D saves it
#   fixtures/external/seamly2d/oracle/<path>.seamly2d.json what Seamly2D computed (points, curves, variables)
#   fixtures/external/seamly2d/oracle/<path>.failed        written instead when Seamly2D could not open it
#   fixtures/external/seamly2d/converted/<path>            the measurement files it upgraded on the way
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${1:-${SEAMLY2D_BIN:-$HOME/seamly2d-build/src/app/seamly2d/bin/seamly2d}}"
SRC="$ROOT/fixtures/external/seamly2d/original"
UP="$ROOT/fixtures/external/seamly2d/upgraded"
OR="$ROOT/fixtures/external/seamly2d/oracle"
CV="$ROOT/fixtures/external/seamly2d/converted"
PIN_VERSION="2026.10.5.154"
BIN="$(realpath "$BIN")" || { echo "no Seamly2D binary at $BIN" >&2; exit 2; }   # the script changes directory
rm -rf "$UP" "$OR" "$CV"; mkdir -p "$UP" "$OR" "$CV"
# Seamly2D writes a .lck lock file next to every pattern it opens: work on a copy
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cp -r "$SRC/." "$WORK/"
SRC="$WORK"
cd "$SRC"
# alltools_pattern.sm2d has a background image whose path is on its author's Windows disk. Seamly2D
# stops on a modal dialog when it cannot find an image, so point it at the logo next to the file.
# (Only this working copy changes; the committed original is untouched, and the saved copy gets the
# original path back below.)
ORIG_IMG='D:/Github/Seamly2D/src/libs/vmisc/share/resources/icon/logos/seamly_logo_192.png'
perl -pi -e "s{\Q$ORIG_IMG\E}{$WORK/all_tools_pattern/seamly_logo_192.png}" all_tools_pattern/alltools_pattern.sm2d
find . -name '*.sm2d' | sort | while read -r f; do
  rel="${f#./}"; mkdir -p "$UP/$(dirname "$rel")" "$OR/$(dirname "$rel")"
  home="$(mktemp -d)"; conv="$(mktemp -d)"
  if HOME="$home" QT_QPA_PLATFORM=offscreen YOKO_ORACLE_DUMP="$OR/$rel.seamly2d.json" \
       YOKO_ORACLE_CONVERTED_DIR="$conv" \
       YOKO_ORACLE_SAVE="$UP/$rel" timeout 40 "$BIN" --test "$SRC/$rel" >/dev/null 2>"$home/err" \
     && [ -s "$UP/$rel" ] && [ -s "$OR/$rel.seamly2d.json" ]; then
    # a build made without scripts/version.sh reports 0.6.0.1; release builds report their tag
    sed -i "s/Seamly2D v0\.6\.0\.1 /Seamly2D v$PIN_VERSION /" "$UP/$rel"
    sed -i "s#$WORK/all_tools_pattern/seamly_logo_192.png#$ORIG_IMG#" "$UP/$rel"
    echo "ok      $rel"
  else
    rm -f "$UP/$rel" "$OR/$rel.seamly2d.json"
    # the temporary directory's name and some Qt-version-specific warnings change: keep the notes stable
    grep -v -E "propagateSizeHints|pdftops|Checked locale|QStandardPaths" "$home/err" | tail -3 | sed "s#$WORK#<work>#g" > "$OR/$rel.failed"
    echo "FAILED  $rel"; sed 's/^/          /' "$OR/$rel.failed"
  fi
  # keep the measurement files Seamly2D's converter upgraded (not the pattern's own temporary copy)
  for m in "$conv"/*.smis "$conv"/*.smms; do
    [ -f "$m" ] || continue
    mkdir -p "$CV/$(dirname "$rel")" && cp "$m" "$CV/$(dirname "$rel")/"
    # QDomDocument::save orders attributes by Qt version: keep the copy in canonical form
    python3 "$ROOT/scripts/canon_xml.py" "$CV/$(dirname "$rel")/$(basename "$m")"
  done
  rm -rf "$home" "$conv"
done
