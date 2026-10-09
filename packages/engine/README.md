# yoko-engine (`yoko_engine`)

Construction graph, formulas, geometry, pieces, validation, pattern library.

Status: Phase 1 in progress. Done so far: the formula language (`yoko_engine.formula`).

```python
from yoko_engine.formula import parse

f = parse("size>22?4.75:size>16?4.5:size>10?4.25:4")  # a real variable from the basic set
print(f.names)                      # ('size',)  the dependency edges
print(f.evaluate({"size": 18.0}))   # 4.5
```

How it differs from Seamly2D's parser, and why: `docs/formula-differences.md`.
