# Changelog

## Unreleased

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
