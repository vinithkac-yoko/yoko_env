# 0011. Evaluation kernel: Seamly2D's pixel scale, and object identity

Status: accepted

**Kernel scale.** The evaluator computes geometry in Seamly2D's native scale (96-dpi pixels) using its exact conversion arithmetic (`ToPixel`, `FromPixel`, `src/libs/vmisc/def.cpp`), then exposes mm. The spec says "mm internally"; this keeps that true at every API boundary but not inside the kernel, on purpose.

Why: Seamly2D truncates line angles to 5 decimals (`VLineAngle::SetValue`: `qFloor(angle * 100000) / 100000`). A value like 270.00000000000006 and 269.99999999999994 land on different sides of that truncation, so rounding noise of 1e-14 can change an angle by 1e-5 degrees, which moves a point 10 cm away by about 0.002 mm. Doing the same arithmetic in the same order, with the same libm functions, reproduces Seamly2D's noise instead of adding our own. The oracle (Phase 2) checks it.

**Identity.** An object's stable internal id is Seamly2D's numeric id; references go by id, so renaming a label never breaks a reference. We do not add random UUIDs: they would make state hashes non-deterministic. Labels (`A1`) are human-readable names; geometric variables (`Line_A_B`) are built from labels, as in Seamly2D.

**Evaluation order** follows `VPattern::Parse`: measurements, then variables in file order, then draft blocks' objects in file order. An object can only use objects defined earlier.

**Errors do not abort.** A bad object becomes an `Issue` (stable `code`, object id, field, hint) and evaluation continues, so a model sees every problem at once.

**Bit-exactness depends on the platform's maths library (found by the CI oracle, 2026-10-10).** The same Qt calls on different systems can differ in the last bit. Qt 6.11.1 on the GitHub runner (Ubuntu 22.04, glibc 2.35) gave a `setAngle` result one ulp away from Qt 6.4.2 on glibc 2.39 in 1 of 4000 random cases, and a flip result one ulp away in 1 of 2000. We cannot yet say whether the cause is Qt's code or glibc's `sin` and `cos`. Consequences:
- The engine still matches the Seamly2D built in CI with Qt 6.11.1 exactly on every pattern we have (the basic set and 23 real patterns), so the checks against Seamly2D's own output stay exact.
- The committed real-Qt vectors are checked exactly in unit tests (same machine type that produced them) and within 2 ulp against Qt 6.11.1 in the oracle job.
- Seamly2D on Windows and macOS uses other maths libraries again, so results there can differ from ours by about 1e-13 px. The one place this can grow is the 5-decimal truncation of `AngleLine_` variables: a value on the edge can flip by 1e-5 degrees, which moves a point 10 cm away by about 0.002 mm. That is well inside the 0.01 mm tolerance of the Phase 2 checkpoint, but "bit for bit" is a statement about Linux, not about every platform.
