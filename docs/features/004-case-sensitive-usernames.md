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

## Done when

- [ ] Exact-case login succeeds and case mismatches clear previous login state.
- [ ] Mixed-case account creation preserves case and rejects case-only duplicates.
- [ ] Lowercase accounts and surrounding-whitespace trimming still work.
- [ ] Case-insensitive database comparisons cannot bypass exact-case login.
- [ ] Relevant tests and the full test suite pass; the app runs.
- [ ] Affected living docs and the changelog describe the completed behavior.
- [ ] Remaining work is resolved and the spec and index statuses are `done`.

## Remaining work

Implementation and verification.
