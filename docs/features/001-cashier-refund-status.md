# 001: Cashier refund status and payouts

**Status:** done

**Touches:** docs/FEATURES.md, docs/BUSINESS_PROCESS.md, docs/ARCHITECTURE.md, docs/DATABASE.md, docs/UI_UX.md, README.md, CHANGELOG.md

## Summary

Give cashiers shared refund visibility, persistent requester-only decision alerts,
and full cash/GCash payout recording while retaining owner-only review.

## Requirements

- All active cashiers and owners can search refund requests by receipt and status,
  view decisions, and record a full payout after money has been returned.
- Only requesting users receive decision notices. Unread notices persist across
  sessions; opening a decision acknowledges it. Poll every ten seconds without
  blocking notices, cancel polling on logout/destruction, and allow retry.
- GCash payouts require a reference. Store actor and time, prevent duplicate payout
  records atomically, and require confirmation. Staff coordinate physical payment;
  no reservations, partial payouts, reversals, or provider integration.
- Owners may correct payout method/reference with a required reason and retained
  audit history. Corrections never reopen payment.
- Existing approved requests become assumed paid once, without fabricated payment
  details. New approvals await payout. No historical decision notice backfill.
- Preserve approval-date reporting, stock behavior, and owner review permissions.
- Add new tables only, created automatically; no existing-table ALTER SQL needed.
  Initialize legacy payment records and a durable marker atomically before access.

## Tasks

1. Add payout, correction, notice, and initialization storage, services, tests, and
   documentation; initialize existing approvals once before workspace access.
2. Add shared POS refund list, requester alerts, payout recording, owner correction
   UI, runtime checks, tests, and matching documentation.
3. Verify acceptance checks and full suite, smoke-test the app, update docs and
   changelog, and close out the spec and index in focused commits.

## Done when

- [x] Shared visibility, requester-only notices, payout validation, duplicate
      prevention, correction audit, and legacy initialization are verified.
- [x] Reports and stock remain unchanged by payout operations.
- [x] Relevant tests and the full test suite pass; the app runs.
- [x] Affected living docs and changelog describe the completed behavior.
- [x] Remaining work is resolved and the spec and index statuses are done.

## Remaining work

None.

## Verification

- Full suite: 423 tests and 26 subtests pass, including all real Tk GUI tests;
  no skipped tests. Headless checks used a temporary Xvfb display with top-level
  keyboard focus support; no display tooling was added as an app dependency.
- Focused coverage includes durable notices/read state and payouts after database
  reopen, simultaneous payout attempts, failed commit rollback, interrupted legacy
  initialization/retry, automatic polling, owner corrections/audit, and unchanged
  report aggregates and stock.
- Ruff lint and format checks pass; dependency compatibility check passes.
- The real app entrypoint opens/closes successfully on disposable SQLite; a
  cashier request → owner approval → cashier decision view was rendered and
  inspected at the dialog's minimum size. GUI tests cover confirmed cash/GCash
  payout and owner correction. The configured shop database was not modified.
- MySQL table DDL compiles in schema tests. Four new tables are auto-created;
  existing tables require no ALTER SQL and no manual migration command.
