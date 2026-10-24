# Changelog

## Unreleased

- Let cashiers browse shared refund decisions, receive requester-only unread
  alerts, and record confirmed cash/GCash payouts. Add owner payout correction
  controls and audit details, retry feedback, and notification cleanup at logout.

- Add shared refund tracking services, requester-only persistent decision notices,
  full cash/GCash payout records, owner correction audit, and one-time legacy
  assumed-paid initialization. Keep approval-date reports and stock unchanged.

- Initialize the documentation guide, feature index, and reusable spec template.
  Preserve the completed initial build as history and align contributor reading
  guidance with `AGENTS.md`, retaining the existing `DATABASE.md` schema document.

- Complete Phase 11 and the full implementation plan. Verify all ten demo steps
  on disposable SQLite and local MySQL, preserving shop data through rollback.
  Final checks pass: 397 tests, 26 subtests, Ruff, and dependency consistency.
  Refresh README setup/workflows and distinguish verified PDFs/viewer handoffs
  from the manual physical-printer check.

- Automate the ten-step demo through real Tk screens and a reopened disposable
  database, covering hold/resume, void, GCash/PDF, refund approval, inventory,
  dashboard/history/customer purchases, and disabled-account login.

- Add hover help for POS function keys and cart editing/removal, with clean
  tooltip cancellation on navigation/logout. Explain empty customer searches
  and walk-in checkout. Use current ttkbootstrap widget imports with support
  for earlier 1.x releases.

- Write UTF-8 diagnostics to project-root `pawpos.log` alongside console output.
  Show friendly database connection/initialization error dialogs before login,
  with console-only fallback when a display or log file is unavailable.

- Replace the owner dashboard placeholder with net-sales/transaction/low-stock/
  pending-refund cards, blue Matplotlib daily-sales and best-seller charts with
  range selectors, and an active low-stock table. Refresh on navigation or by
  button, show empty states and negative net days, retain visible data on read
  failures, and clean up chart callbacks on logout/navigation.

- Add owner report services for daily net sales, today's summary, gross-quantity
  best sellers, active low-stock products, and pending refunds. Zero-fill date
  ranges and deduct refunds on their approval date without duplicating sales.

- Enable owner Users management: create cashiers, confirm disabling, re-enable,
  and reset passwords, including the owner's demo password. Keep owner status
  protected and password inputs masked; clear saved account inputs before
  refreshing to avoid duplicate creation after a read failure.

- Enable owner Sales History with date/receipt/account/payment filters, original
  item and tender details, approved refund totals, and receipt PDF reprinting.

- Enable owner Customers management with add/edit, name/contact search, and
  completed purchase lists. Preserve customer history and form input on errors.

- Add owner-only customer editing and completed-sales history services, with
  date/receipt/cashier/payment/customer filters, original item/payment snapshots,
  and approved-only refund totals. Customer edits preserve purchase links.

- Connect POS refund requests to receipt lookup/reprinting, per-item quantities,
  opened/used flags, reasons, and original-price totals. Add owner Pending and
  History tabs with per-line resellable choices, confirmed approval/rejection,
  rejection notes, reviewer details, and a live pending-count sidebar badge.
  Validation and database failures preserve inputs; successful reviews disable
  repeat actions before refreshing.

- Add receipt-based refund request and owner review services, enforcing the
  seven-day window, opened-food restrictions, and remaining quantities including
  pending requests. Approval restores only resellable stock with linked movement
  history; rejection releases quantities without changing inventory.

- Enable the owner Inventory workspace with Stock Overview, Receive Stock,
  Adjust Stock, and read-only Movement History tabs. Include low-stock
  highlighting, supplier prefill, delivery dates, signed corrections, history
  filters, validation feedback, and protection against resubmitting a saved
  stock change after a refresh failure.

- Connect F4/F6/F8 to hold, void, and held-transaction dialogs. Restore held
  quantities, prices, and customers after restart; prevent active-cart
  replacement; require reasons and confirmation for voids/held cancellations.
  Restore focus and modal grabs after nested dialogs, and let Escape close the
  held list even when its table has focus.

- Add persistent held-cart services with customer and item snapshots, atomic
  resume/cancellation, and reasoned line/transaction void logs. Holds and voids
  leave stock unchanged; failed writes preserve the active cart and held rows.

- Connect Pay/F5 to live Cash/GCash validation, cash quick amounts and change,
  atomic completion, stock refresh, cart reset, and automatic receipt preview.
  Add Print and Last receipt actions; receipt failures keep the committed sale
  recoverable without repeating payment. Correct modal ownership so dialogs
  belong to their calling screen.

- Add completed-sale receipt data, wrapped receipt text, and atomic 80 mm PDF
  generation with an embedded peso-capable font. PDF printing opens the system
  default viewer; failed viewer launches leave the PDF available for manual use.

- Add atomic sale completion with product locks, stock revalidation, item price
  snapshots, linked stock movements, cash change, GCash reference validation,
  and daily `PAW-YYYYMMDD-NNNN` receipt numbering.

- Replace the cashier placeholder with the POS screen and enable owner POS
  navigation. Add product cards, search/category filtering, cached thumbnails,
  weight pricing previews, cart editing/removal, and customer selection/quick
  creation. Scope keyboard shortcuts to the POS and preserve owner draft carts
  across sidebar navigation. Payment, hold, void, and refund actions still show
  messages for their planned phases.

- Add signed-in customer lookup by name/contact and quick creation with optional
  contact, ready for the Phase 4 checkout picker.

- Add the pure Python cart with merged piece/kg lines, quantity editing and
  removal, current-stock checks, immutable line snapshots, and Decimal half-up
  pricing. Invalid operations preserve the active cart. The selling UI follows
  in Phase 4.

- Add the owner sidebar and category/product forms with validation feedback,
  image previews, search and category filters, reactivation, and confirmed
  deactivation. Existing product stock is read-only in the form.

- Add category and product services with owner access checks, validation, search,
  category filtering, soft deletion, and atomic initial stock history. Product
  image copies are removed if saving fails.

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

- Add owner inventory services for receiving deliveries, signed stock corrections,
  stock overview, and filtered read-only movement history. Stock changes and
  audit rows commit together; invalid quantities or failed writes change neither.
