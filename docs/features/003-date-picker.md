# 003: Shared calendar date picker

**Status:** done

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
5. Resolve the existing modal keyboard-focus blocker with a minimal focus fix;
   verify payment and nested-dialog keyboard interactions before the full suite.

## Done when

- [x] Selection, cancellation, clearing, read-only input, and leap day are tested.
- [x] Delivery and filter selections reach their existing service calls.
- [x] Existing validation tests and the full suite pass; the app runs.
- [x] Layout at 1280x720 and light/dark calendars are verified with running-widget checks.
- [x] Living docs/changelog are updated; spec and index are done.

## Remaining work

None.

## Verification

- Full suite: `python -m pytest -q -x
  --basetemp=.pytest_cache/date-picker-full-final` — 489 passed and 26 subtests
  passed. Run on the Windows desktop with isolated test databases.
- Payment/POS/nested-modal regression checks: 31 passed. Settings/payment checks:
  15 passed. Date-picker, Inventory, Sales History and service checks: 62 passed.
- `python -m ruff check .` and `git diff --check` pass.
- The app launched against an isolated, seeded in-memory database without
  accessing shop data. Live Tk checks verified widget bounds at 1280x720, popup
  visibility and screen bounds, and cosmo/darkly themes. Desktop capture access
  to the Python app was denied, so screenshot inspection was unavailable.
- The original full-suite blocker reproduced before this feature. Activating
  each modal toplevel before assigning input focus resolved its Windows keyboard
  failure. The added regression verifies input focus, Escape cancellation, owner
  focus restoration, and grab release. Settings' existing assertions wait for
  native input focus within their existing four-second watchdog.
