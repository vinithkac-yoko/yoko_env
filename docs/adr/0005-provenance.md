# 0005. Provenance sidecar

Status: accepted (Addendum 1 §6)

Every object created or edited through the environment records: plan step id, recipe op id, author (model, human, teacher, import), episode id, on-plan flag, and for edits the old and new formula or inputs.

Stored in a sidecar next to the Seamly2D file (`<style>.yoko.json`) together with the plan, the parent pattern's hash and the new objects' landmarks. The Seamly2D file stays lossless.

Visible to the policy: step ids and landmarks. **Privileged, never shown to the policy:** the on-plan flag and the teacher's labels.
