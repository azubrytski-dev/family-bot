# Skill: Code Review Gate

Use this skill after implementation and before merge/apply.

## Primary Focus

Find bugs, regressions, boundary leaks, and missing tests before discussing style.

## Review Order

1. Correctness
2. Security and secret handling
3. Boundary adherence
4. Test coverage and regression risk
5. Readability and maintainability

## Repository-Specific Checks

- No accidental user-visible sends outside intended bot flows.
- Single-chat filtering is preserved where relevant.
- Storage changes match migration state.
- Async code does not block or swallow important failures.
- Russian end-user formatting remains coherent.

## Expected Output

Report:

- findings ordered by severity;
- open questions or assumptions;
- brief apply recommendation.
