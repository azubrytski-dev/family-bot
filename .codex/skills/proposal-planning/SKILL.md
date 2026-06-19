# Skill: Proposal Planning

Use this skill when creating or refining a change proposal so the resulting `proposal.md` and `plan.md` are grounded in the actual repository instead of generic placeholders.

## Goal

Turn a user request into an apply-ready planning artifact with concrete scope, affected layers, implementation steps, and verification work.

## When To Use

- After `./bin/propose <change-name>` creates a scaffold.
- When a user asks for a more detailed plan.
- Before `/start` if the proposal still contains generic placeholders.

## Steps

1. Read the current proposal request and restate the smallest safe objective.
2. Inspect the relevant entrypoints and modules before drafting steps.
3. Identify which of these are affected:
   - startup wiring in `app/main.py`;
   - bot handlers or scheduler code in `app/bot/`;
   - business services in `app/core/services/`;
   - repository interfaces, PostgreSQL code, or migrations in `app/storage/`.
4. Fill `proposal.md` with:
   - a concrete objective;
   - in-scope and out-of-scope bullets;
   - design review notes for schema, scheduler, outbound messaging, and failure modes;
   - a verification plan tied to changed tests.
5. Replace the generic `plan.md` steps with numbered tasks that:
   - reference real files or layers;
   - separate design decisions from code edits;
   - include migration and configuration work if needed;
   - end with tests and review gates.
6. Keep the plan narrow. If the request sounds broad, state non-goals instead of silently expanding scope.

## Repository-Specific Reminders

- Preserve single-family-chat assumptions unless the change explicitly reopens them.
- Keep bot-facing copy in Russian.
- Treat migrations as append-only.
- Favor graceful degradation for scheduler or provider failures where feasible.
- Do not leave orphaned config flags or startup wiring after removing a feature area.

## Good Plan Characteristics

- Names the exact modules likely to change.
- Includes at least one explicit risk or open design decision.
- Makes it obvious which tests should be updated.
- Avoids vague steps like "implement the change" when more specific wording is possible.
