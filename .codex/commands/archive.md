---
description: Archive a tracked change into the dated archive folder.
---

# Archive

Use this command to close and archive an existing tracked change.

## Preflight

1. Confirm the user provided a change id in `$ARGUMENTS`.
2. Verify the repository root contains [bin/archive](/Users/andrei/projects/my_pets/family-bot/bin/archive).
3. Verify `tasks/changes/$ARGUMENTS/` exists.
4. If `$ARGUMENTS` is empty, ask the user which change should be archived.

## Plan

Before executing:

- state that the command will archive the selected change
- mention the exact change id from `$ARGUMENTS`
- note that the folder will be moved into `tasks/archive/<date>/`

## Commands

Run the repository-local script:

```bash
./bin/archive "$ARGUMENTS"
```

Use the script instead of manually moving files unless it is broken.

## Verification

1. Confirm the script exited successfully.
2. Verify the source folder no longer exists under `tasks/changes/`.
3. Report the final archive destination.

## Summary

```text
## Result
- Action: archived a tracked change
- Status: success | partial | failed
- Details: change id and archive destination
```

## Next Steps

- Start a new proposal if follow-up work is needed.
- Reopen as a fresh change instead of editing archived records in place.
