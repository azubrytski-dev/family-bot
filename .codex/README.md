# Codex Setup

This folder contains project-specific Codex workflow assets:

- `commands/`: lightweight local command wrappers for proposal/start/archive flow.
- `prompts/`: console-facing aliases for the same tracked-change workflow.
- `skills/`: reusable task patterns for design, review, testing, and apply readiness.
- `workflows/`: step-by-step operating guides for common delivery flows.

Start with [`AGENTS.md`](/Users/andrei/projects/my_pets/family-bot/AGENTS.md) for repository-wide expectations.

## Recommended Usage

- Use the local commands in [`.codex/commands/README.md`](/Users/andrei/projects/my_pets/family-bot/.codex/commands/README.md) for proposal lifecycle tracking.
- Use the `proposal-planning` skill right after `/propose` when the scaffold needs concrete project-based steps.
- Use the `apply-workflow` skill for normal implementation tasks.
- When a milestone is finished and verified, use the `commit-workflow` skill and create a focused checkpoint commit.
- Treat `/start` as a continue-working command by default, not only a status flip.
- Use the `system-design-review` skill before migrations, new integrations, or scheduler changes.
- Use the `performance-review` skill when touching queries, polling, or scheduled aggregation jobs.
- Use the `code-review-gate` skill before merge or deployment.

## Project Priorities

1. Keep the bot reliable for one target family chat.
2. Preserve clean boundaries between core logic, storage, bot, and integrations.
3. Prefer fast tests and incremental change over broad rewrites.
4. Protect scheduled behavior and outbound-message discipline.
