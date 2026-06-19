---
description: Archive a tracked change into the dated archive folder.
---

# Archive

Console alias for the tracked-change archive workflow.

Use the same behavior and verification rules as [`.codex/commands/archive.md`](/Users/andrei/projects/my_pets/family-bot/.codex/commands/archive.md):

- require a change id in `$ARGUMENTS`
- run `./bin/archive "$ARGUMENTS"`
- verify the change moved into `tasks/archive/<date>/`

Example:

```text
/commands:archive simplify-to-ai-and-db-scheduler
```
