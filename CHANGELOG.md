# Changelog

## Unreleased

- Launch the themed desktop login after database initialization and first-run
  seeding. Route owners and cashiers to placeholder workspaces, with logout and
  login state cleared when the window closes. Report startup failures clearly.
- Add real Tk login/logout tests, runnable headlessly with Xvfb.

- Add login/logout and owner-only cashier creation, enable/disable, account
  listing, and password reset services. Disabled users cannot log in; owners
  cannot disable themselves. Password hashes are excluded from service results.

- Add the ten database tables and atomic first-run seed data: two demo accounts,
  eight categories, fourteen products, and initial stock history.

- Use Ruff for Python linting, import sorting, and formatting.

- Start Phase 0: project layout, local MySQL configuration, atomic database
  sessions, a startup connection check, Decimal formatting, bcrypt helpers,
  in-memory login state, and paw placeholder assets.
- Add automated foundation checks.
