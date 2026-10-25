# 003: Shared calendar date picker

**Status:** in progress

**Touches:** `docs/UI_UX.md`, `docs/FEATURES.md`, `README.md`, `CHANGELOG.md`

## Summary

Owners choose dates from a reusable calendar instead of typing into five text
fields: Inventory delivery date, Movement History From/To, and Sales History From/To.

## Requirements

- Read-only ISO date display with a keyboard-accessible calendar button.
- Delivery date starts at today with no Clear button. Each optional filter starts
  blank and has its own Clear button.
- Open at the selected date, or today when blank. Selection updates the value;
  Escape or closing the calendar preserves it. Restore focus after closing.
- Reuse ttkbootstrap without new dependencies. Preserve service interfaces,
  explicit filtering, inclusive dates, and validation. No database changes.

## Tasks

1. Build the shared widget and cancellation-aware calendar adapter.
2. Replace all five fields; test widget behavior and screen integration.
3. Run relevant/full tests and the app; verify minimum-size and themed layouts.
4. Update living docs/changelog, complete acceptance checks, and commit.

## Done when

- [x] Selection, cancellation, clearing, read-only input, and leap day are tested.
- [x] Delivery and filter selections reach their existing service calls.
- [ ] Existing validation tests and the full suite pass; the app runs.
- [x] Layout at 1280x720 and light/dark calendars are verified with running-widget checks.
- [ ] Living docs/changelog are updated; spec and index are done.

## Remaining work

Full-suite verification and final status closeout remain blocked by an existing
payment-modal keyboard test failure. The initial full run reported payment test
failures and then stalled in another modal test; it was interrupted. Running
`tests/test_payment_ui.py -x` separately reproduces the failure: generated Return
does not submit payment, then receipt lookup raises StopIteration. The identical
failure reproduces from a clean archive of pre-implementation commit `b9a6f57`,
both without this widget and without the owner-screen changes. Existing payment
code/tests have been left unchanged. Keep this spec and index in progress until
the repository-wide test gate passes.

Verification completed:

- `python -m pytest tests/test_date_picker.py tests/test_inventory_ui.py
  tests/test_sales_history_ui.py tests/test_inventory_service.py
  tests/test_sales_history_service.py -q --basetemp=.pytest_cache/date-picker-final`
  — 62 passed, including all nine widget tests, service integration, existing
  malformed-date/reversed-range validation, and minimum-size/light/dark checks.
- `python -m ruff check .` and `git diff --check` pass.
- The app launched against an isolated, seeded in-memory database without
  accessing shop data. Desktop capture access to the Python app was denied, so
  screenshot-based visual inspection was unavailable; live Tk bounds, popup
  visibility, and active themes were checked instead.
