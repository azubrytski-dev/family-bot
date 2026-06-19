# Apply Loop Workflow

Use this workflow for nearly every production-facing change.

## 1. Frame the Change

Write down:

- objective;
- budget and scope;
- affected layers;
- non-goals;
- rollout or fallback concerns.

If the task changes schema, scheduling, data flow, or integrations, run a system design review first.

## 2. Review Before Coding

Answer these quickly:

- Does this belong in `core`, `storage`, `integrations`, or `bot`?
- Will it change migrations, scheduled jobs, or outbound Telegram behavior?
- What are the likely failure modes?
- Which unit tests should prove correctness?

## 3. Implement Locally

Make the smallest coherent change that satisfies the task.

Expected local habits:

- preserve layer boundaries;
- keep user-facing copy in Russian;
- use English for code and comments;
- avoid coupling business logic directly to PostgreSQL or provider-specific clients.

## 4. Unit Test First-Class Logic

Minimum expectation:

- add or update focused unit tests for changed logic;
- keep tests deterministic and fast;
- avoid live network or live database access.

Preferred command:

```bash
uv run pytest
```

## 5. Run the Review Gates

### Code Review Gate

- Is the code easy to reason about?
- Are names and boundaries clear?
- Is async behavior safe?
- Are config and secrets handled correctly?

### Performance Gate

- Did we add extra queries, polling work, or repeated parsing?
- Could a scheduled job become too expensive?
- Are any network retries or fallbacks likely to stampede?

### Calamity Gate

- What happens if PostgreSQL is slow or unavailable?
- What happens if Gemini or OpenAI fails?
- Could a scheduler run duplicate user-visible sends?
- Is the bot still safe for a single target chat?

## 6. Apply Decision

A change is ready to apply when:

- scope is met without silent creep;
- tests pass for the changed behavior;
- review findings are addressed or explicitly accepted;
- risks and follow-ups are documented.
