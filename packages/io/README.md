# yoko-io (`yoko_io`)

Seamly2D import and export, SVG and PNG render.

Status: Phase 1 reads format 0.6.8 patterns and multisize measurement tables. Lossless writing,
newer formats and rendering come in Phase 2.

```python
from yoko_engine.evaluator import evaluate
from yoko_io.seamly import read_measurements, read_pattern

pattern = read_pattern("fixtures/patterns/base/Aldrich-Womens-6th-Ed-Basic-Blocks.sm2d")
table = read_measurements("fixtures/measurements/Aldrich-Womens-MultiSize-06-14.smms")
result = evaluate(pattern, table.values())
print(result.point_mm("A1"))
```
