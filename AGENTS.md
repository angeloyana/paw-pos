# AGENTS.md

Instructions for AI coding agents working in this repository (POS system).

## Commit rules

- Commit after every working change. A change is "working" when the code runs
  and the relevant tests pass.
- Keep commits small and focused: one logical change per commit.
- Never commit broken code, failing tests, or half-finished work.
- Never commit secrets: `.env` files, API keys, database credentials, or
  customer data. If you find one staged, unstage it and tell the user.
- Do not use `git commit --amend`, `git push --force`, or rewrite history
  unless the user asks.
- Work on a feature branch, not directly on `main`.

### Commit message format

```
type: short description in present tense
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `db`

Examples:

```
feat: add FEFO lot deduction on sale
fix: prevent negative qty_on_hand race condition
db: add inventory_lots table with expiry_date
test: cover void flow requiring manager PIN
```

Add a short body when the "why" is not obvious from the title.

## Documentation rules

- Update the docs in the same change that introduces a new feature, behavior
  change, endpoint, config option, environment variable, or database table.
  Do not leave docs for later.
- Update the README when setup steps, commands, or features change.
- Document schema changes (new tables, columns, indexes) and the reason for them.
- Update or remove docs that your change makes outdated.
- Add a short entry to `CHANGELOG.md` for user-visible changes.
- Add comments or docstrings only where the "why" is not obvious from the code.
- Commit docs together with the code they describe, or in a `docs:` commit
  right after it.

## Workflow

1. Make one change.
2. Run the tests (and the app, if the change affects runtime behavior).
3. Update any docs affected by the change.
4. If everything passes: `git add` the relevant files and commit.
5. Repeat.

Stage specific files rather than `git add -A` when unrelated files have changed.

## Before finishing a task

- Tests pass.
- No secrets or debug code in the diff.
- Docs and changelog are updated for any new or changed feature.
- Changes are committed with clear messages.
