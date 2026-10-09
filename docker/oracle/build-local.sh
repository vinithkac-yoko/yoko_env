#!/usr/bin/env bash
# Build the pinned Seamly2D with the yoko oracle dump hook, for local development on Ubuntu 24.04.
#
# This uses Ubuntu's Qt 6.4, which is older than the Qt 6.11 Seamly2D builds with, so four files need
# small compatibility patches (docker/oracle/qt64-compat.patch). Those patches are for local use only:
# the GitHub Actions oracle job builds with Qt 6.11.1 and applies only yoko-oracle-dump.patch.
#
#   docker/oracle/build-local.sh [source_dir] [build_dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-$HOME/seamly2d-src}"
BUILD="${2:-$HOME/seamly2d-build}"
PIN="v2026.10.5.154"

if [ ! -d "$SRC/.git" ]; then
  git clone https://github.com/FashionFreedom/seamly2d "$SRC"
fi
git -C "$SRC" fetch --depth 1 origin tag "$PIN"
git -C "$SRC" checkout -q "$PIN"
git -C "$SRC" apply --check "$HERE/yoko-oracle-dump.patch" && git -C "$SRC" apply "$HERE/yoko-oracle-dump.patch"
git -C "$SRC" apply --check "$HERE/qt64-compat.patch" && git -C "$SRC" apply "$HERE/qt64-compat.patch"

apt-get install -y build-essential qt6-base-dev qt6-base-dev-tools qt6-svg-dev qt6-tools-dev \
  qt6-tools-dev-tools qt6-multimedia-dev qt6-5compat-dev libxerces-c-dev libgl1-mesa-dev \
  libxkbcommon-dev xvfb

mkdir -p "$BUILD"
cd "$BUILD"
qmake6 "$SRC/Seamly2D.pro" CONFIG+=release CONFIG-=debug
# SeamlyMe (the measurement editor) needs Qt 6.5+ and is not needed; -k builds everything else.
make -k -j"$(nproc)" || true
test -x "$BUILD/src/app/seamly2d/bin/seamly2d" && echo "built: $BUILD/src/app/seamly2d/bin/seamly2d"
