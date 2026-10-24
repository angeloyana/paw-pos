# 001: Cashier refund status and payouts

**Status:** in progress

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

- [ ] Shared visibility, requester-only notices, payout validation, duplicate
      prevention, correction audit, and legacy initialization are verified.
- [ ] Reports and stock remain unchanged by payout operations.
- [ ] Relevant tests and the full test suite pass; the app runs.
- [ ] Affected living docs and changelog describe the completed behavior.
- [ ] Remaining work is resolved and the spec and index statuses are done.

## Remaining work

Implement tasks 1–3.
