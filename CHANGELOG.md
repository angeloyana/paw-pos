# Changelog

## Unreleased

- Add login/logout and owner-only cashier creation, enable/disable, account
  listing, and password reset services. Disabled users cannot log in; owners
  cannot disable themselves. Password hashes are excluded from service results.

- Add the ten database tables and atomic first-run seed data: two demo accounts,
  eight categories, fourteen products, and initial stock history.

- Use Ruff for Python linting, import sorting, and formatting.

- Start Phase 0: project layout, local MySQL configuration, atomic database
  sessions, a startup connection check, Decimal formatting, bcrypt helpers,
  in-memory login state, and paw placeholder assets.
- Add automated foundation checks. Desktop screens and seed accounts remain
  scheduled for Phase 1.
