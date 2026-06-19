---
description: Mark a tracked change as in progress and scaffold implementation and review notes.
---

# Start

Console alias for the tracked-change start workflow.

Use the same behavior and verification rules as [`.codex/commands/start.md`](/Users/andrei/projects/my_pets/family-bot/.codex/commands/start.md):

- require a change id in `$ARGUMENTS`
- run `./bin/start "$ARGUMENTS"`
- verify `status.md`, `implementation.md`, and `review.md`
- continue into implementation by default after scaffolding

Example:

```text
/commands:start simplify-to-ai-and-db-scheduler
```
