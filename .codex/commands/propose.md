---
description: Create a new tracked change proposal and scaffold its planning files.
---

# Propose

Use this command to create a new change proposal through the local Bash workflow.

## Preflight

1. Confirm the user provided a proposal name in `$ARGUMENTS`.
2. Verify the repository root contains [bin/propose](/Users/andrei/projects/my_pets/family-bot/bin/propose).
3. Verify `tasks/` exists so the change can be scaffolded in the expected place.
4. If `$ARGUMENTS` is empty, ask the user for the change name before running anything.

## Plan

Before executing:

- state that the command will run the local proposal scaffold script
- mention the exact change name derived from `$ARGUMENTS`
- note that the script will create a new folder under `tasks/changes/`

After scaffolding:

- inspect the relevant code paths for the requested change before stopping
- use the local `proposal-planning` skill and `planner` agent brief if the request affects more than a trivial single-file edit
- replace generic placeholders in `proposal.md` and `plan.md` with repository-specific scope, risks, and numbered steps
- keep the resulting plan narrow, concrete, and tied to real files or layers

## Commands

Run the repository-local script:

```bash
./bin/propose "$ARGUMENTS"
```

Do not reimplement the scaffolding manually unless the script is missing or broken.

## Verification

1. Confirm the script exited successfully.
2. Report the created change id and folder path.
3. Verify that `proposal.md`, `plan.md`, and `status.md` were created.
4. Verify that `plan.md` no longer contains only the default generic steps when the request is substantial.

## Summary

```text
## Result
- Action: created a new change proposal
- Status: success | partial | failed
- Details: change id, folder path, and scaffolded files
```

## Next Steps

- Run `/start <change-id>` when implementation begins.
- Open the proposal and fill in objective, scope, and verification details.
