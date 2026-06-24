---
name: commit-workflow
description: Use when the user asks to commit local changes, wants commit-message help, or wants commit history checked before committing. Review recent git history first, prefer short one-line tagged messages like `(feat): ...`, `(fix): ...`, `(spec): ...`, or `(chore): ...`, verify scope with `git status`, and commit only the intended files.
---

# Skill: Commit Workflow

Use this skill when the user asks to create a commit, improve a commit message, or align commit style with recent repository history.

## Goal

Create intentional commits with a clean scope and a short repository-consistent message.

## Steps

1. Inspect recent history first with `git log --oneline -8`.
2. Check the current scope with `git status --short` and `git diff --stat`.
3. Infer the smallest accurate commit type:
   - `(feat):` for user-facing or capability additions
   - `(fix):` for bug fixes and correctness changes
   - `(spec):` for proposal, planning, or tracked-change docs
   - `(chore):` for maintenance, tooling, or non-product cleanup
4. Use a one-line commit message in the form `(type): short summary`.
5. Stage only the files that belong to the requested checkpoint.
6. Commit without amending unless the user explicitly asks for it.
7. Report the created commit hash and confirm whether the worktree is clean.

## Repository-Specific Rules

- Check recent history before choosing the final message wording.
- Prefer one-line tagged commit messages over unprefixed summaries.
- Do not include unrelated tracked-change files unless they belong to the same checkpoint.
- If tests were run, mention that in the final summary after committing.
- If `.git` writes require approval, request escalation only for the git staging/commit step.

## Expected Output

Report:

- the chosen commit message;
- the created commit hash;
- whether the worktree is clean;
- any intentionally uncommitted follow-up work.
