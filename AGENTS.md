# AGENTS.md

This file describes **how to work**. What the system is, what it does, and the technical rules live in `docs/`.

## Start of every session

You have no memory of earlier sessions. Read in this order:

1. `docs/README.md`
2. `docs/features/INDEX.md` (status of all features)
3. The spec for the current task in `docs/features/`
4. Only the living docs that the spec's `Touches` line lists (for example `DATABASE.md`, `UI_UX.md`)

If there is no spec for the task, stop and ask the user to provide one (or offer to draft it) before writing code.

## Source of truth

- The docs describe the current system. If code and docs disagree, do not guess: report the conflict and ask which is correct.
- Do not invent requirements. If something is unclear, ask.
- Follow the rules and conventions written in `docs/` (architecture, tech stack, coding standards). Do not restate or override them here.

## Workflow for each new feature

1. **Branch:** create a feature branch (for example `feature/discounts`). Never work directly on `main`.
2. **Spec:** confirm `docs/features/NNN-name.md` exists and follows `docs/features/TEMPLATE.md`. Set its status to `in progress` in `docs/features/INDEX.md`.
3. **Plan:** read the spec's Tasks list. Say briefly which tasks you will do and in what order.
4. **Build, one task at a time.** For each task, run the loop below.
5. **Verify:** go through the spec's "Done when" checklist and tick each item honestly. Run the full test suite and the app.
6. **Sync docs:** merge the feature's final behavior into the living docs (see Documentation rules).
7. **Close out:** set the spec status to `done` in `INDEX.md` and add an entry to `CHANGELOG.md`.
8. **Report:** summarize what changed, files touched, docs updated, how you tested, and any assumptions or open questions.

Features are tracked in their own specs, not as phases in `IMPLEMENTATION_PLAN.md`. That file is the frozen record of the initial build; do not add to it.

If a feature is too large for one session, stop at a clean commit, record what remains in the spec, and keep its status `in progress`. If it is too large overall, split it into separate specs (for example `001a`, `001b`).

### Task loop

1. Make one change.
2. Run the tests (and the app, if the change affects runtime behavior).
3. Update any docs affected by the change.
4. If everything passes: `git add` the relevant files and commit.
5. Repeat.

## Workflow for a bug fix or small change

1. Reproduce or understand the problem; find the relevant doc section.
2. Fix it with the smallest change that works. Do not refactor unrelated code.
3. Add a test that fails before the fix and passes after, when the logic is testable.
4. Run the task loop (tests, docs, commit). Add a `CHANGELOG.md` line.
5. Report as in step 8 above.

## Database changes

1. Check whether the change adds a new table (created automatically) or alters an existing table (not applied automatically).
2. For altered tables, write the exact SQL needed in the spec and in your report, and tell the user to run it. Never reset, drop, or truncate data unless explicitly asked.
3. Update `docs/DATABASE.md` and the seed script in the same change, and document the reason for the change.

## Commit rules

- Commit after every working change. A change is "working" when the code runs and the relevant tests pass.
- Keep commits small and focused: one logical change per commit.
- Never commit broken code, failing tests, or half-finished work.
- Never commit secrets: `.env` files, API keys, database credentials, or customer data. If you find one staged, unstage it and tell the user.
- Do not use `git commit --amend`, `git push --force`, or rewrite history unless the user asks.
- Stage specific files rather than `git add -A` when unrelated files have changed.

### Commit message format

```
type: short description in present tense
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `db`

Examples:

```
feat: add discount line to receipt
fix: prevent negative stock when two sales complete in a row
db: add discounts table
test: cover refund request past the 7-day window
docs: add discounts to FEATURES and DATABASE
```

Add a short body when the "why" is not obvious from the title.

## Documentation rules

- Update the docs in the same change that introduces a new feature, behavior change, config option, environment variable, or database table. Do not leave docs for later.
- Update the README when setup steps, commands, or features change.
- Update or remove docs that your change makes outdated. Living docs always describe the current system, not its history.
- Add a short entry to `CHANGELOG.md` for user-visible changes.
- Add comments or docstrings only where the "why" is not obvious from the code.
- Commit docs together with the code they describe, or in a `docs:` commit right after it.

Which doc to update:

| Change                      | Update                                                         |
| --------------------------- | -------------------------------------------------------------- |
| Feature added or changed    | `docs/FEATURES.md`, the feature spec, `docs/features/INDEX.md` |
| Business rule               | `docs/BUSINESS_PROCESS.md`                                     |
| Tables or columns           | `docs/DATABASE.md`, seed script                         |
| Screens, dialogs, shortcuts | `docs/UI_UX.md`                                                |
| Structure or flow           | `docs/ARCHITECTURE.md`                                         |
| Libraries                   | `docs/TECH_STACK.md`, `requirements.txt`                       |
| Any user-visible change     | `CHANGELOG.md`                                                 |

## Working rules

- One feature or fix at a time.
- Prefer editing existing files over creating parallel versions.
- Do not change unrelated files or formatting.
- Do not add dependencies unless the task needs them.
- Never weaken or delete tests to make them pass.

## Before finishing a task

- The spec's "Done when" checklist is fully ticked.
- Tests pass and the app runs.
- No secrets or debug code in the diff.
- Docs, `docs/features/INDEX.md`, and `CHANGELOG.md` are updated.
- Changes are committed with clear messages.
- Your report lists changes, tests run, and open questions.
