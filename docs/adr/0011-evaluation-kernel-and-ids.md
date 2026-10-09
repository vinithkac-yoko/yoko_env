# 0011. Evaluation kernel: Seamly2D's pixel scale, and object identity

Status: accepted

**Kernel scale.** The evaluator computes geometry in Seamly2D's native scale (96-dpi pixels) using its exact conversion arithmetic (`ToPixel`, `FromPixel`, `src/libs/vmisc/def.cpp`), then exposes mm. The spec says "mm internally"; this keeps that true at every API boundary but not inside the kernel, on purpose.

Why: Seamly2D truncates line angles to 5 decimals (`VLineAngle::SetValue`: `qFloor(angle * 100000) / 100000`). A value like 270.00000000000006 and 269.99999999999994 land on different sides of that truncation, so rounding noise of 1e-14 can change an angle by 1e-5 degrees, which moves a point 10 cm away by about 0.002 mm. Doing the same arithmetic in the same order, with the same libm functions, reproduces Seamly2D's noise instead of adding our own. The oracle (Phase 2) checks it.

**Identity.** An object's stable internal id is Seamly2D's numeric id; references go by id, so renaming a label never breaks a reference. We do not add random UUIDs: they would make state hashes non-deterministic. Labels (`A1`) are human-readable names; geometric variables (`Line_A_B`) are built from labels, as in Seamly2D.

**Evaluation order** follows `VPattern::Parse`: measurements, then variables in file order, then draft blocks' objects in file order. An object can only use objects defined earlier.

**Errors do not abort.** A bad object becomes an `Issue` (stable `code`, object id, field, hint) and evaluation continues, so a model sees every problem at once.
