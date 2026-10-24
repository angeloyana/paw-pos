# 002: Settings

**Status:** in progress

**Touches:** `docs/FEATURES.md`, `docs/BUSINESS_PROCESS.md`, `docs/DATABASE.md`, `docs/ARCHITECTURE.md`, `docs/UI_UX.md`, `README.md`, `CHANGELOG.md`.

## Summary

Owners and cashiers can choose any built-in ttkbootstrap theme and change their
own password while signed in. Preferences belong to the account.

## Requirements

- Owners get a Settings sidebar page; POS gets a modal Settings window sharing
  the same form. Preserve cart, customer, and last receipt; block POS shortcuts
  in the modal and restore focus when it closes.
- A read-only theme selector lists all built-in themes. Apply theme saves first,
  then applies immediately without rebuilding the workspace. Failed writes leave
  the existing theme active and show inline feedback.
- A new `user_settings` table has `user_id` as primary key/foreign key to users
  and a required theme string. Startup creates it automatically; no existing
  tables change and no manual ALTER SQL is required. Missing/unsupported themes
  use `cosmo`. Seed runs preserve preferences. Restore on login, reset on logout.
- Theme colors follow the selection, including canvases and dashboard charts.
- Separate Change password action requires masked current/new/confirmation
  fields, correct current password, and matching confirmation. Use existing
  bcrypt validation (nonblank, at most 72 UTF-8 bytes). Clear fields on success;
  remain signed in. Forgotten-password recovery remains out of scope.
- Services derive the target account from the session and recheck active status.
  Theme and password saves are independent. Existing owner resets remain.

## Tasks

1. Add preference model/services, password-change service, and service tests;
   update database/business/architecture docs and seed behavior documentation.
2. Add shared Settings UI, navigation, theme lifecycle and color updates, with
   GUI tests and current user documentation.
3. Run full tests, Ruff checks, and app smoke checks; verify acceptance and close
   the spec/index/changelog. Commit each tested logical change.

## Done when

- [x] Both roles can save independent themes, restored after login/restart.
- [x] Password validation, authorization, rollback, and replacement login work.
- [x] Settings navigation preserves POS state and modal keyboard/focus behavior.
- [x] All built-in themes work; custom colors and charts follow the theme.
- [x] Relevant tests and the full suite pass; the app runs.
- [ ] Living docs/changelog are current and all changes are committed.
- [ ] Remaining work is resolved and spec/index statuses are `done`.

## Remaining work

Tasks 1–2 implemented. Full suite: 444 tests and 26 subtests passed with real Tk
coverage on an isolated Xvfb/Matchbox display. Ruff checks pass. Actual app startup,
seeding, and event loop passed with disposable SQLite; light/dark Settings layouts
were inspected at 1280×720. Remaining: commit UI and close out documentation.
