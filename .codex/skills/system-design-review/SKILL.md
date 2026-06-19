# Skill: System Design Review

Use this skill before coding when a task changes architecture, schema, scheduling, or integration patterns.

## Questions To Answer

1. What capability is changing, and why now?
2. Which layers are affected?
3. Does the data model need to change?
4. Does the scheduler or target-chat behavior change?
5. What are the failure and recovery paths?
6. What tests will prove the new design?

## Review Checklist

- Data model and migration impact are explicit.
- Repository interfaces still express the right domain behavior.
- External integrations remain isolated behind stable boundaries.
- Scheduled jobs remain idempotent or duplication-aware where possible.
- Configuration changes are backward compatible or clearly documented.

## Deliverable

Produce a compact design note with:

- objective;
- proposed approach;
- alternatives rejected;
- risks;
- verification plan.
