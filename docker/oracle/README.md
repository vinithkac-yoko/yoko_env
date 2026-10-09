# Seamly2D oracle

Real Seamly2D, built from the pinned tag, used as ground truth for the engine.

| File | Purpose |
| --- | --- |
| `yoko-oracle-dump.patch` | Adds `YOKO_ORACLE_DUMP=<file>`: after loading a pattern, writes every point, curve, arc and variable as JSON. Needed by every oracle build |
| `qt64-compat.patch` | Four Qt 6.5+ calls replaced for Ubuntu's Qt 6.4. **Local development only**; the CI build uses Qt 6.11.1 and does not need it |
| `build-local.sh` | Clone the pinned tag, apply the patches, build on Ubuntu 24.04 |

Run it: `scripts/oracle_dump.sh pattern.sm2d out.json`. Compare: `tests/test_oracle_basic_set.py`.

`tools/oracle/qt_vectors.cpp` produces `fixtures/oracle/qt_lines.jsonl.gz`, real Qt `QLineF` results
for 4000 random lines, which `tests/test_qt_vectors.py` checks bit for bit. Build it with
`g++ -std=c++17 -O2 -fPIC tools/oracle/qt_vectors.cpp $(pkg-config --cflags --libs Qt6Core)`.

Provenance: the committed JSON was produced by the local Qt 6.4.2 build. When the CI job exists it
regenerates these files with Qt 6.11.1 and fails if the engine disagrees.
