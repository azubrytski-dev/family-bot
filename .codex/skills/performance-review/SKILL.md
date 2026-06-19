# Skill: Performance Review

Use this skill when touching scheduled jobs, repositories, polling loops, aggregation code, or external API usage.

## Focus Areas

- DB query count and indexing assumptions
- repeated external API calls
- large payload parsing or serialization
- blocking calls inside async flows
- unnecessary work inside scheduled tasks

## Questions

1. Did this change add more queries or larger scans?
2. Will scheduled jobs re-fetch or recompute too much?
3. Can retries or fallbacks amplify traffic under failure?
4. Is the hottest code path still simple and bounded?

## Deliverable

Summarize:

- potential regressions;
- required mitigations;
- whether benchmarking or integration validation is needed.
