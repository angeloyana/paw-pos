# 004: Case-sensitive usernames

**Status:** in progress

**Touches:** `docs/FEATURES.md`, `docs/BUSINESS_PROCESS.md`, `docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`.

## Summary

Owners and cashiers must enter the stored capitalization of their username to
sign in. New cashier accounts preserve capitalization, while names differing
only by case remain unavailable for separate accounts.

## Requirements

- Trim surrounding username whitespace on creation and login, preserving case.
- Require exact username equality in Python before accepting credentials,
  including when the database uses case-insensitive comparisons. Mismatches use
  the generic credentials error and clear any previous login state.
- Reject new usernames whose Python `casefold()` matches an existing username.
- Preserve existing usernames and password behavior. Existing lowercase accounts
  require lowercase login. No schema changes or manual SQL are required.

## Tasks

1. Update authentication and account creation with regression tests; sync the
   authentication and account documentation in the same change.
2. Run relevant tests, the full suite, Ruff checks, and an app smoke check;
   complete acceptance checks, close the spec/index, and commit tested changes.
3. Verify baseline focus-restoration failures on an isolated X11 test desktop
   and rerun the full suite before closing acceptance. Clear X11 maximization
   in resize-test setup, as existing minimum-size tests already do.

## Done when

- [x] Exact-case login succeeds and case mismatches clear previous login state.
- [x] Mixed-case account creation preserves case and rejects case-only duplicates.
- [x] Lowercase accounts and surrounding-whitespace trimming still work.
- [x] Case-insensitive database comparisons cannot bypass exact-case login.
- [ ] Relevant tests and the full test suite pass; the app runs.
- [x] Affected living docs and the changelog describe the completed behavior.
- [ ] Remaining work is resolved and the spec and index statuses are `done`.

## Remaining work

No username implementation work remains. Full-suite acceptance and final status
remain open because four unrelated GUI focus tests fail on this desktop, also
reproduced on starting commit `81eb592`. Resolve or verify those baseline focus
failures separately before closing the full-suite checklist and spec/index.

## Verification

- Regression tests first reproduced seven failures in the old implementation.
- Authentication, Users UI, and Login UI: 43 passed, including mixed-case account
  creation/login and real SQLite `NOCASE` username comparisons. Unicode case-fold
  duplicates remain rejected.
- Full suite: 495 passed, 26 subtests passed, four failed, no skips. All four
  failures reproduced on a clean copy of starting commit `81eb592`:
  `test_calendar_selection_and_cancellation[escape-2024-02-29]`,
  `test_calendar_selection_and_cancellation[close-2024-02-29]`,
  `test_modal_takes_keyboard_focus_and_restores_owner_focus`, and
  `test_cashier_modal_entry_focus_escape_and_pos_state`. Each failure concerns
  keyboard focus restoration after a dialog closes; `focus_get()` returns `None`.
- Actual app entry point, initialization/seeding, Tk event loop, wrong-case
  rejection, exact-case owner login, and shutdown passed with disposable SQLite.
  Shop data was not accessed.
- `python -m ruff check .`, Python formatting checks for `pawpos`, `tests`,
  `main.py`, and `scripts`, and `git diff --check` pass. Repository-wide
  `ruff format --check .` encounters pre-existing invalid UTF-8 in
  `docs/features/003-date-picker.md`; that unrelated document is unchanged.
- No schema changes, manual SQL, dependencies, or account renames were needed.
