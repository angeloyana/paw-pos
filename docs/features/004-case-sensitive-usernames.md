# 004: Case-sensitive usernames

**Status:** done

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
- [x] Relevant tests and the full test suite pass; the app runs.
- [x] Affected living docs and the changelog describe the completed behavior.
- [x] Remaining work is resolved and the spec and index statuses are `done`.

## Remaining work

None.

## Verification

- Regression tests first reproduced seven failures in the old implementation.
- Authentication, Users UI, and Login UI: 43 passed, including mixed-case account
  creation/login and real SQLite `NOCASE` username comparisons. Unicode case-fold
  duplicates remain rejected.
- Final full suite: 499 passed, 26 subtests passed, no failures or skips, on an
  isolated Xvfb/Openbox desktop with disposable SQLite (254.66 seconds).
- Initial WSLg runs had four dialog-focus failures also reproduced on starting
  commit `81eb592` and in a plain Tk window. Calendar, payment, settings, and
  nested-dialog checks pass with application code unchanged on isolated X11.
- Resize-test setup now clears X11's separate maximized attribute, following
  existing minimum-size tests. This allows the existing growth and proportional
  width assertions to exercise actual window resizing under a Linux window manager.
  All three affected resize cases pass; no assertions were removed or loosened.
- Actual app entry point, initialization/seeding, Tk event loop, wrong-case
  rejection, exact-case owner login, and shutdown passed with disposable SQLite.
  Shop data was not accessed.
- `python -m ruff check .`, `python -m ruff format --check .`, and
  `git diff --check` pass. A single Windows-encoded dash in the historical
  date-picker spec was corrected to UTF-8 to unblock repository-wide formatting.
- X11 test tools were downloaded/extracted under `/tmp`, with no system-wide
  installation or project dependency changes. Temporary displays and window
  managers shut down after each run.
- No schema changes, manual SQL, dependencies, or account renames were needed.
