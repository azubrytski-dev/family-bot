---
description: Create a new tracked change proposal and scaffold its planning files.
---

# Propose

Console alias for the tracked-change proposal workflow.

Use the same behavior and verification rules as [`.codex/commands/propose.md`](/Users/andrei/projects/my_pets/family-bot/.codex/commands/propose.md):

- require a proposal name in `$ARGUMENTS`
- run `./bin/propose "$ARGUMENTS"`
- verify `proposal.md`, `plan.md`, and `status.md`
- enrich the scaffold with repository-specific planning for substantial changes

Example:

```text
/commands:propose simplify-to-ai-and-db-scheduler
```
