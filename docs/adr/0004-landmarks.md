# 0004. Landmarks: standard names in a sidecar

Status: accepted; the vocabulary and mapping are **proposed** until the pattern makers verify them (Addendum 1 §5)

- Plans, recipes, tools and observations refer to pattern-making names (`bodice_front.SNP`, `sleeve.cap_top`), not labels like `A12`.
- One sidecar per base pattern, `fixtures/patterns/base/<name>.landmarks.yaml`. The `.sm2d` stays untouched. Versioned and hashed.
- Naming: `<piece>.<landmark>` with common abbreviations and a glossary.
- Process: (1) I propose the vocabulary and a best-guess mapping with a confidence per row; (2) pattern makers verify and correct; never guess silently; (3) commit the verified file; (4) a studio tagging screen comes later.
- Rules: derived styles inherit landmarks; each recipe names the landmarks it creates; tools accept a landmark anywhere they accept a label; validation fails if a landmark does not resolve.
- Scheduled for Phase 3. Nothing is guessed before then.
