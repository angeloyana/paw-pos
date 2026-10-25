# 005: Read-only void history

**Status:** planned

**Touches:** docs/FEATURES.md, docs/BUSINESS_PROCESS.md, docs/ARCHITECTURE.md, docs/UI_UX.md, README.md, CHANGELOG.md

## Summary

Expose the existing void audit records in the application so cashiers can review
their own cancellations and owners can review all shop voids. Both roles receive
read-only history with optional inclusive date filters.

## Requirements

- Active cashiers can read only records whose `void_logs.user_id` matches their
  signed-in account. Active owners can read every account's records, including
  their own and records attributed to accounts that are now disabled.
- Enforce authorization in the service layer using the current authenticated
  account and recheck its active status and role in the database. Do not accept
  a caller-supplied account ID to determine cashier access. Reject reads without
  an active authorized session; apply the same restrictions to any detail lookup.
- Add a **Void History** button in POS for both roles, opening a shared modal,
  and a **Void History** sidebar page for owners. Reuse the history form and
  service so permissions and filtering are consistent across entry points.
- Show one row per existing `void_logs` record, newest first by `created_at`
  and then ID. Include date/time, actor name, saved product name, quantity,
  amount, scope (Line or Transaction), and the complete reason. Long reasons
  may be shown in a read-only selected-row detail area.
- Whole-cart and held-cart cancellations already generate one transaction-scope
  log per item. Display those item rows individually; do not infer transaction
  groups, receipt numbers, customers, or historical units that the log does not
  store. Use the saved quantity (up to three decimals) and peso amount (two
  decimals), without deriving a historical unit from the current product.
- Include existing records and new line, whole-cart, and held-cart voids. The
  actor is the person who performed the void, including when another account
  originally held the cart. Historical product names come from log snapshots.
- Provide optional **From** and **To** filters using the shared calendar-only
  date picker, each initially blank and with its own Clear button. Blank bounds
  are unrestricted; both chosen dates include the whole local calendar day,
  using the application's existing local timestamp convention.
- Load history on opening; **Filter / Refresh** applies the current range and
  reloads committed records. Reject From later than To with inline feedback
  and retain the previous results. Calendar cancellation preserves its value.
- Show an explicit empty state when no accessible records match. Read failures
  show a retry message and retain previously loaded authorized results; session
  loss must close or clear the view so another account cannot see stale data.
- Both roles have read-only access: no edit, delete, restore, or cancellation
  action in this history. Opening, selecting, filtering, and refreshing do not
  change audit records, stock, sales, or the current POS cart/customer/last receipt.
- Preserve existing modal focus/grab behavior, disable POS function keys while
  the modal is open, and restore focus on Escape/Close. Follow shared table and
  theme conventions; filters, scrollable rows, and full reasons must remain
  reachable at the application's 1280x720 minimum size.
- Reuse the existing schema and dependencies. No new tables, existing-table
  alterations, manual SQL, seed changes, or historical backfill are required.
  Actor filters, exports, totals, and transaction grouping are outside this spec.

## Tasks

1. Add the read-only history service with authenticated role scoping, optional
   inclusive date bounds, stable newest-first ordering, and immutable results.
   Test access denial, cross-cashier isolation, owner visibility, date boundaries,
   invalid ranges, historical snapshots, and line/transaction-scope records.
   Update the affected service and business-rule documentation and commit.
2. Add the shared history form, POS modal/button, and owner sidebar page. Test
   role-specific results, date selection/clearing/cancellation, refresh, empty
   states, failure recovery, full reason access, and unchanged POS state. Verify
   the running app's layout, themes, navigation, and modal keyboard behavior;
   update screen documentation and commit the working change.
3. Verify all acceptance checks with isolated test data, run the full test suite
   and required code checks, and smoke-test the app. Update README and changelog,
   sync final behavior into the listed living docs, and mark the spec and index
   done only after implementation and verification are complete.

## Done when

- [ ] Cashiers can view only their own voids; owners can view all shop voids,
      including disabled accounts' history, through every supported entry point.
- [ ] Unauthenticated, disabled, and unauthorized access is rejected by the service;
      any detail lookup cannot bypass cashier isolation.
- [ ] Existing and new line, whole-cart, and held-cart void records appear with
      correct actors, saved values, complete reasons, and stable ordering.
- [ ] Optional inclusive date bounds, clearing, calendar cancellation, same-day
      filtering, and invalid ranges are verified.
- [ ] Empty states, retryable read failures, and session changes preserve access
      restrictions without exposing another account's cached records.
- [ ] History is read-only for both roles and leaves audit records, stock, sales,
      and the POS cart/customer/last receipt unchanged.
- [ ] POS modal and owner navigation work at 1280x720 in light/dark themes with
      readable scrolling, full reasons, and correct keyboard focus/grab handling.
- [ ] Relevant tests, the full test suite, and required code checks pass; the app runs.
- [ ] Affected living docs, README, and changelog describe the completed behavior.
- [ ] Remaining work is resolved and the spec and index statuses are `done`.

## Remaining work

Draft only: implementation, tests, runtime verification, living-doc updates,
README, and the user-visible changelog entry remain pending. The proposed
entry points and initially unrestricted date range are design choices in this
draft. No application code or schema has changed.
