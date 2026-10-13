# 0014. The tool layer

Status: accepted

- **One YAML file per tool is the source of truth** for what a model sees (description, parameters, examples) and, for a primitive, what a call builds. The loader refuses a primitive whose description does not say both when to use it and when not to. Descriptions are v1 and meant to be edited; a bundle digest changes with any word.
- **Edit and delete tools are derived, not written.** `edit_<tool>` has the tool's parameters, all optional, plus `target`; `delete_<tool>` has only `target`. Both check that the target was made with that tool, so the model learns the right pairing. Only tools that build one element from single-attribute parameters have them (not operations, dart points or spline paths, which are changed by deleting and redoing).
- **Names, never ids, in calls.** A point by label, a curve or arc by its name, a line by `#<id>`, anything by a landmark name. Resolution happens in the runtime so the engine sees ids only. Unknown names get "did you mean" hints.
- **One result shape for every call**, success or failure, so a policy and a data record parse one thing.
- **Adapters never change meaning.** The canonical call is `(name, args)`; Anthropic, OpenAI and the text DSL carry it and parse it back; the DSL uses JSON values so any argument survives.
- **Plan amounts are typed** (`value`, `unit`) and each becomes a pattern variable `#s<step>_<param>` in the pattern's unit. A formula is written in the pattern's unit; only plain numbers are converted. Plans with choices (parallel or hinged) need two recipes, because parameters are numbers.
- **Seamly2D remains the check.** The tools write a pattern that the pinned Seamly2D opens and computes identically (`tool_calls` case, in CI), so a tool cannot drift from what Seamly2D understands.
- **Procedures are questions until a pattern maker answers.** The drafts in `docs/manipulations/` carry structure and tool calls, and mark each drafting rule `(?)`.
