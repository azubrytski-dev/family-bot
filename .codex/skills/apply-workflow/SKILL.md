# Skill: Apply Workflow

Use this skill for standard feature work, fixes, and refactors.

## Goal

Drive a task from local understanding to apply-ready verification without skipping design or tests.

## Steps

1. Restate the concrete objective and define the smallest useful scope.
2. Identify the impacted layer: `bot`, `core`, `storage`, or `integrations`.
3. Flag whether the task affects schema, scheduling, outbound messages, or third-party providers.
4. Implement the change with minimal surface area.
5. Add or update deterministic unit tests.
6. Run the review gates:
   - code review;
   - performance review;
   - calamity review.
7. Summarize:
   - what changed;
   - what was verified;
   - what remains risky or deferred.

## Repository-Specific Rules

- Preserve single-chat assumptions unless a task explicitly changes them.
- Keep bot output in Russian.
- Prefer scheduler-driven behavior for recurring outbound messages.
- Treat migrations as append-only history.
- Avoid direct business-logic dependence on provider-specific clients or SQL details.

## Verification Commands

```bash
uv run pytest
```

Use narrower test selection only when the task is intentionally local and you explain the tradeoff.
