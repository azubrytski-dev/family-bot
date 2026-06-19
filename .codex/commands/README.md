# Local Commands

These commands provide a lightweight OpenSpec-style workflow without installing OpenSpec.

## Commands

Slash-command definitions live alongside the Bash scripts, so the workflow can be used either by invoking the scripts directly or by using `/propose`, `/start`, and `/archive` inside Codex when workspace commands are supported.

If your Codex console looks for prompt files instead, use the mirrored aliases in [`.codex/prompts/README.md`](/Users/andrei/projects/my_pets/family-bot/.codex/prompts/README.md). They expose the same workflow as `/commands:propose`, `/commands:start`, and `/commands:archive`.

### `./bin/propose <change-name>`

Creates a new change folder under `tasks/changes/<change-id>/` with:

- `proposal.md`
- `plan.md`
- `status.md`

Use this when a task needs scope, review framing, and a verification plan before implementation.

For non-trivial changes, follow the scaffold immediately by enriching `proposal.md` and `plan.md` with the `proposal-planning` skill so they reflect the actual codebase.

### `./bin/start <change-id>`

Marks an existing proposal as in progress and creates:

- `implementation.md`
- `review.md`

Use this when implementation begins and you want a dedicated place for working notes and review-gate output. In Codex command mode, `/start` should also continue into the implementation work unless you explicitly ask it to only scaffold the files.

### `./bin/archive <change-id>`

Moves a completed or abandoned change into `tasks/archive/<YYYY-MM-DD>/<change-id>/`.

Use this when the work is done, superseded, or intentionally closed.

## Suggested Flow

```bash
./bin/propose scheduler-outbound-only
./bin/start scheduler-outbound-only
./bin/archive scheduler-outbound-only
```

## Notes

- Change IDs are derived from the proposal name and normalized to lowercase kebab-case.
- These commands do not create branches or commit changes.
- They are safe to use alongside the Codex skills in `.codex/skills/`.
- Slash command definitions are:
  - [propose.md](/Users/andrei/projects/my_pets/family-bot/.codex/commands/propose.md)
  - [start.md](/Users/andrei/projects/my_pets/family-bot/.codex/commands/start.md)
  - [archive.md](/Users/andrei/projects/my_pets/family-bot/.codex/commands/archive.md)
