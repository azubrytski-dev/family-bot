---
description: Mark a tracked change as in progress and scaffold implementation and review notes.
---

# Start

Use this command to begin work on an existing tracked change and continue directly into implementation unless the user explicitly asks for start-updating only.

## Preflight

1. Confirm the user provided a change id in `$ARGUMENTS`.
2. Verify the repository root contains [bin/start](/Users/andrei/projects/my_pets/family-bot/bin/start).
3. Verify `tasks/changes/$ARGUMENTS/` exists.
4. If `$ARGUMENTS` is empty, ask the user which change should be started.

## Plan

Before executing:

- state that the command will mark the change as in progress
- mention the exact change id from `$ARGUMENTS`
- note that the script will add implementation and review files if they do not exist

After scaffolding:

- read the change `proposal.md`, `plan.md`, `implementation.md`, and `review.md`
- treat the tracked change artifacts as the active implementation brief
- continue with the smallest safe implementation work instead of stopping at scaffolding
- use the local `apply-workflow` skill for normal code changes
- only stop after either:
  - a meaningful implementation step is completed, verified, and summarized; or
  - a real blocker is found that cannot be resolved safely without the user

## Commands

Run the repository-local script:

```bash
./bin/start "$ARGUMENTS"
```

Do not recreate the workflow files by hand unless the script is unavailable.

## Verification

1. Confirm the script exited successfully.
2. Verify `status.md` now shows `in_progress`.
3. Verify `implementation.md` and `review.md` exist for the selected change.
4. Verify implementation work has either started or the blocker has been documented clearly.

## Summary

```text
## Result
- Action: started a tracked change
- Status: success | partial | failed
- Details: change id, updated status, and created support files
```

## Next Steps

- Continue implementation immediately in the smallest safe scope.
- Fill in review findings before the apply step.
