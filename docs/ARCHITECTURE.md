# System Architecture

## 1. Overview

A **single desktop application** (one process) on **one computer**, running offline. It connects to a **locally installed MySQL** server on `localhost`. There is no web server, API, or network dependency.

```
+-----------------------------------------------------+
|                    Tkinter UI (ttkbootstrap)        |
|  login | POS screen | owner shell + screens         |
+--------------------------+--------------------------+
                           | calls
+--------------------------v--------------------------+
|                    Services layer                   |
|  auth, catalog, cart, sales, refunds, inventory,    |
|  customers, reports, receipts                       |
|  (business rules, transactions, validation)         |
+--------------------------+--------------------------+
                           | uses
+--------------------------v--------------------------+
|        Models (SQLAlchemy ORM) + db session         |
+--------------------------+--------------------------+
                           |
                     MySQL (localhost)
```

**Layer rules**

- `ui/` imports from `services/` only (plus `core/` helpers). It never imports `models/` to run queries and never touches the session.
- `services/` own all business rules and DB transactions. Each public service function opens a session via a context manager, commits on success, and rolls back on error.
- `models/` contain only table definitions and relationships (no business logic).
- Services raise custom exceptions (`ValidationError`, `BusinessRuleError`, `NotFoundError`, `AuthError`) from `core/errors.py`. UI catches them and shows a message box. Unexpected errors are logged and shown generically.
- Services return plain data (dataclasses/DTOs or detached ORM objects with loaded attributes) so UI code never needs an open session.

## 2. Project structure

```
pawpos/
├── main.py                    # entry point: init DB, seed, start app
├── requirements.txt
├── .env.example               # DB connection settings
├── README.md
├── assets/
│   ├── logo.png               # paw placeholder logo
│   ├── placeholder_product.png
│   └── products/              # copied product images
├── receipts/                  # generated PDFs (git-ignored)
├── pawpos/
│   ├── __init__.py
│   ├── config.py              # loads .env, constants (shop name, 7-day refund window)
│   ├── core/
│   │   ├── errors.py          # custom exceptions
│   │   ├── money.py           # Decimal helpers, format_peso()
│   │   ├── security.py        # bcrypt hash/verify
│   │   └── session.py         # CurrentUser (in-memory)
│   ├── db/
│   │   ├── base.py            # engine, SessionLocal, Base, session_scope()
│   │   └── seed.py            # default users, categories, sample products
│   ├── models/
│   │   ├── __init__.py        # imports all models
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── customer.py
│   │   ├── sale.py            # Sale, SaleItem, VoidLog
│   │   ├── refund.py          # RefundRequest, RefundItem
│   │   └── stock_movement.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── category_service.py
│   │   ├── product_service.py
│   │   ├── customer_service.py
│   │   ├── cart.py            # in-memory Cart class (pure logic)
│   │   ├── sale_service.py    # hold/resume/void/complete
│   │   ├── refund_service.py
│   │   ├── inventory_service.py
│   │   ├── report_service.py
│   │   └── receipt_service.py # build receipt data + PDF
│   └── ui/
│       ├── app.py             # root window, screen switching, theme
│       ├── widgets/           # product_card.py, money_entry.py, chart_frame.py, dialogs.py
│       ├── login_screen.py
│       ├── pos_screen.py
│       ├── dialogs/           # weight, payment, receipt_preview, void, customer_picker, held_list, refund_request
│       └── owner/
│           ├── shell.py       # sidebar + content area
│           ├── dashboard.py
│           ├── products.py
│           ├── categories.py
│           ├── inventory.py
│           ├── customers.py
│           ├── sales_history.py
│           ├── refunds.py
│           └── users.py
└── tests/
    ├── conftest.py            # in-memory SQLite engine + fixtures
    ├── test_cart.py
    ├── test_weight_pricing.py
    ├── test_sale_service.py
    └── test_refund_rules.py
```

## 3. Key design decisions

`POSScreen` calls catalog/customer services and owns its `Cart`; widgets and
dialogs never query models. Adds and edits fetch current active product data
independently of the visible search/category filter. The owner shell keeps one
POS frame alive while showing other pages so a draft cart/customer survives
navigation. Logout destroys it. Root function-key bindings check visibility and
dialog focus and are removed when the screen is destroyed. Refund requests
open a receipt-based modal and preserve the active cart/customer. Owner review
is available separately through the Refunds sidebar entry.
F5 now opens `PaymentDialog`, which owns the service call and returns a committed
`CompletedSale` only on success. The POS then clears the cart/customer before
loading any receipt or refreshing catalog data. Receipt failures cannot leave
the paid cart available for a second payment. The Last receipt button retains
the completed sale ID within the POS session for preview retries. Modal windows
use an explicit `master` so Tk parents them to the calling screen.
`WeightDialog` also edits whole-piece quantities; its live preview uses the
cart's original unit-price snapshot when merging an existing weight line.
`ThumbnailCache` belongs to the POS frame and keeps Tk images alive, falling
back to the bundled paw for unreadable images.

Customer checkout services expose `list_customers(search="")` and
`create_customer(name, contact="")` to active signed-in users, returning frozen
`CustomerDetails` values. Searches match literal text in names or contacts;
duplicate names are allowed. No schema changes are required.

`services/cart.py` is pure Python and does not open a session or require login.
`Cart.add_piece(product_id, product_name, unit_price, quantity=1,
stock_quantity=...)` and `add_weight(product_id, product_name, unit_price,
quantity, stock_quantity=...)` accept Decimal, text, or integer numeric inputs;
`stock_quantity` is keyword-only. `set_quantity(product_id, quantity,
stock_quantity=...)` replaces the quantity using current supplied stock.
`remove_line(product_id)` and `clear()` remove items. `lines` is an immutable
tuple of frozen `CartLine` snapshots in first-added order; `total` is a Decimal.
Missing lines raise `NotFoundError`, invalid inputs raise `ValidationError`,
and insufficient stock or a conflicting unit type raises `BusinessRuleError`.

Both unit types merge by product ID, retaining the first name and unit price
until the line is removed. Each merged line is rounded half-up to centavos;
the cart total sums those rounded amounts. Zero quantities are rejected; remove
the line explicitly instead. Input quantities and amounts respect the existing
database column limits, including the sale total limit. Failed operations leave
the cart unchanged. The cart neither reserves nor changes stock; the caller
supplies current stock on every add/edit, and sale completion must recheck it.

Catalog services return frozen category/product data objects. Active catalog
reads require a signed-in active user; writes and inactive listings require an
active owner. Category deletion means deactivation and is blocked by any product
reference, including an inactive product. Initial product stock and its movement
commit together. Product edits reject stock input; changing units is allowed only
before stock or transaction history exists, to avoid reinterpreting quantities.
Image files are verified and copied under UUID names; a failed save removes its
new copy. Replacing a product image retains the old file. Searches treat `%` and
`_` literally. Money accepts at most two decimal places and quantities use the
documented piece/kg precision, within their database column limits.

Authentication returns a frozen `CurrentUser` containing only public identity
fields. A failed login clears previous login state. User-management operations
recheck that the signed-in account is active and has the owner role in the DB;
they return frozen `UserDetails` without password hashes. Usernames are trimmed
and case-folded on creation and login. Account status changes apply to cashiers;
owners can reset their own seeded password as well as cashier passwords.

| Topic           | Decision                                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| App style       | One Tkinter app; screens are frames swapped in a single root window                                                                               |
| Schema creation | `Base.metadata.create_all()` on startup; no migrations                                                                                            |
| Seeding         | `seed.py` initializes refund tracking on startup; demo users/catalog are added only if no users exist                                                                                                  |
| Cart            | In-memory `Cart` object (pure Python, unit-testable). Persisted to DB only when held                                                              |
| Held carts      | Stored as `sales` rows with `status='held'` plus `sale_items`                                                                                     |
| Sale completion | One DB transaction, row-level lock on products (`with_for_update()`), then deduct stock                                                           |
| Concurrency     | Not handled beyond the transaction above (one cashier at a time)                                                                                  |
| Session/auth    | Simulated: `core/session.py` holds the current user; no tokens, no timeouts                                                                       |
| Receipts        | ReportLab PDF, 80 mm wide, saved in `receipts/`, opened with the OS default app (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux) |
| Images          | Copied to `assets/products/<uuid><ext>`; DB stores the relative path; Pillow generates thumbnails (e.g. 96x96) cached in memory                   |
| Money           | `Decimal`, quantized to 2 places with `ROUND_HALF_UP`; line total = qty x price                                                                   |
| Time            | Store naive local time (`datetime.now`). Single computer, so no timezone handling                                                                 |

## 4. Key flows

### 4.1 Complete a sale

1. UI calls `sale_service.complete_sale(cart, payment, customer_id=...)`.
2. Validate: cart not empty; payment method valid; cash received >= total; GCash reference present.
3. Begin transaction. Load each product `FOR UPDATE`. Verify `stock >= qty` and product active, else raise `BusinessRuleError`.
4. Create `Sale(status='completed')`, `SaleItem` rows (snapshot name, unit type, unit price), generate receipt number.
5. For each item: `product.stock -= qty`; insert `StockMovement(type='sale', change=-qty, stock_after, reference sale id)`.
6. Commit. Return frozen `CompletedSale(id, receipt_number, total)`. UI clears
   the cart and builds the receipt preview only after successful completion.

`Payment(method, amount_received=None, gcash_reference="")` is validated by the
pure `validate_payment(total, payment)` helper and again during completion.
Cash must cover the total; GCash requires a trimmed reference of at most 50
characters. Unused tender fields are stored as NULL. The active authenticated
account supplies cashier identity; callers cannot attribute sales to another
account. Optional customers must exist. Inactive products/categories and changed
units block completion. Original cart name/price snapshots are preserved.
Receipt numbering restarts each local day and stops at 9999. The unique receipt
constraint and transaction protect writes; multiple-terminal sequencing remains
out of scope. The service leaves the in-memory cart untouched on success or
failure, letting the UI clear it after the commit. No schema changes are needed.

### 4.2 Hold / resume

- Hold: save cart as `Sale(status='held')` + items (receipt number NULL). Clear UI cart.
- Resume: load held sale items into a new `Cart`, delete the held sale row and its items (cart is now active again).

`hold_cart(cart, customer_id=None)` returns a frozen `HeldSummary`, leaving the
caller to clear its cart after commit. `list_held()` lists all shop holds, oldest
first, with time, line count, total, customer, and original cashier. Any active
cashier or owner can resume or cancel a hold. `resume_held(id)` returns a
`ResumedCart(cart, customer)` built before deleting the held sale/items in one
transaction. Original product names/prices and quantities are retained; no live
stock cap is applied while restoring, since holds do not reserve stock. Payment
rechecks current availability. Invalid or already-consumed IDs leave data intact.

### 4.3 Void

- Line void: remove from the in-memory cart and insert a `VoidLog` (product name, qty, amount, reason, user).
- Void all: log every line, clear the cart. If the cart came from a resumed held sale, nothing else to delete (already removed on resume).
- Voiding from the held list (cancel a held cart): delete the held sale, log voids for its lines.

`void_line(cart, product_id, reason)` and `void_all(cart, reason)` validate the
reason (trimmed, required, at most 255 characters), commit the audit rows, then
mutate the in-memory cart. `cancel_held(id, reason)` logs one transaction-scope
row per held line and deletes the held sale/items in the same transaction. Each
log records the current actor and original name, quantity, and rounded amount.
No stock or stock movements change. The existing schema has no `voided` sale
status; cancellation history is retained in `void_logs`. No schema changes.

### 4.4 Refund

1. `refund_service.create_request(receipt_number, items, reason)` derives the
   requester from the active login, validates the rules (see `BUSINESS_PROCESS.md`
   section 6), and inserts pending request/items.
2. Owner-only `approve(request_id, resellable_map)` atomically sets status,
   reviewer/time, restores resellable stock with movements, and creates the
   requester's decision notice.
3. Owner-only `reject(request_id, note)` records rejection/reviewer/time/note and
   the requester's decision notice atomically, without stock changes.
4. Shared tracking reads expose the decision; `record_payout` separately records
   full money returned without changing approval-date reports or stock.

### 4.5 Receipt printing

`receipt_service.build_receipt(sale_id)` returns a data object used by both the on-screen preview (monospace text widget) and `receipt_service.make_pdf(receipt)`, which writes the PDF. `print_receipt()` opens it with the OS default app for the user to print.

Receipt reads require an active account and a completed sale. Frozen receipt
objects use saved sale-item names, prices, quantities, and totals, so later
catalog edits do not alter them. `receipt_text(receipt)` wraps content to 38
characters for both preview and PDF. PDFs are 80 mm wide, with height computed
from wrapped lines, and use the bundled DejaVu Sans Mono font for the peso sign.
The font and its redistribution license live in `assets/fonts/`.
`make_pdf(receipt, output_dir=None)` writes a temporary file and replaces
`receipts/<receipt_number>.pdf` only after generation succeeds.
`print_receipt(receipt, output_dir=None)` opens that PDF using `os.startfile`,
`open`, or `xdg-open`. It never sends a job directly to a printer. Actual viewer
and printer availability depends on the local desktop configuration.

## 5. Error handling and logging

- Python `logging` to `pawpos.log` (rotating file) and console.
- User-facing errors via ttkbootstrap message dialogs. No stack traces shown.
- DB connection failure at startup shows a clear dialog ("Cannot connect to MySQL. Check .env") and exits.

## 6. Configuration (`.env`)

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=pawpos
DB_PASSWORD=your_password
DB_NAME=pawpos
```

The database (`pawpos`) must exist before first run; `main.py` may attempt `CREATE DATABASE IF NOT EXISTS` if the user has rights.

### Inventory services (Phase 7)

`inventory_service` restricts every read/write to an active owner. `stock_overview`
returns product snapshots including inactive products. `receive_stock` and
`adjust_stock` lock the product, validate unit precision and numeric limits, and
commit the balance and movement together. Receipt quantities are positive;
adjustments are signed, nonzero, and require a common reason plus a note.
Supplier text is delivery-specific and stored with the note (255 characters
combined); it does not change the product's default supplier. Optional delivery
dates use the existing movement timestamp, with past dates recorded at midnight.
`stock_after` always means the balance when the operation was posted, including
when a delivery is backdated. Future delivery dates are rejected.

`list_movements` returns immutable rows for all four movement types, with optional
product/type and inclusive calendar-date bounds. Sale references resolve to
receipt numbers; refund references show the refund ID. No history mutation API
is exposed. This phase uses existing tables without schema changes.

### Refund services (Phase 8)

`refund_service.lookup_receipt` exposes completed sale snapshots, food flags, and
remaining refundable quantities to active signed-in users. Requests use
`RefundLineInput(sale_item_id, quantity, is_opened)`; the service derives the
requester from the login, validates the receipt and every line, and inserts the
request/items together. The request window is inclusive through exactly seven
elapsed days after completion. Pending and approved quantities reserve the sold
quantity; rejected requests release it. Opened food is blocked using the
product's current category food flag (the existing sale schema has no food-flag
snapshot). Prices and units use sale-item snapshots, with half-up centavo rounding.

Only owners can list pending/history, count pending requests, or review them.
`approve(request_id, resellable_map)` requires a boolean for every refund-item ID.
The request and affected products are locked; approval, reviewer/time, resellable
flags, stock changes, and linked `refund` movements commit atomically. Inactive
products can still receive returns. A timely pending request remains reviewable
after the request window expires. `reject(request_id, note)` requires a note,
records reviewer/time, and leaves inventory unchanged. Already reviewed requests
cannot be reviewed again. The existing refund tables need no schema changes.

### Customer management and sales history (Phase 9)

`customer_service.update_customer` requires an active owner and edits name/contact
without deleting the customer or changing sale associations. Checkout lookup and
quick creation remain available to active cashiers and owners. Customer deletion
is not exposed in v1.

`sales_history_service.list_sales` is owner-only and returns immutable summaries
for completed sales, ordered newest first. Filters support inclusive calendar
dates, literal receipt-number text, cashier ID, payment method, and customer ID
(the latter supplies a customer's purchase list). Refund totals aggregate only
approved requests before joining to sales, so multiple refund requests do not
duplicate sale rows. `get_sale` returns original sale-item prices/names/quantities
and tender details. Customer/cashier names reflect their current records. Existing
receipt services supply preview/PDF reprinting. No schema changes are required.

### Dashboard reports (Phase 10)

`report_service` restricts all reports to an active owner and returns immutable
Decimal-valued snapshots. `today_summary` returns today's net sales, completed
transaction count, low-stock count, and pending refunds. `daily_sales(7|30)`
returns every local calendar date, oldest first, with zero-filled empty days.
Gross sales use `completed_at`; approved refunds use `reviewed_at`, including
refunds of sales from earlier days. Refund-only days can have negative net sales.
Sales/refund aggregates run separately to avoid multiplying totals across joins.

`best_sellers(1|7|30, limit=5)` ranks gross quantities from completed sales and
labels units. Refund quantities do not reduce this gross-sales ranking. Products
are grouped by ID/unit with current names, including inactive historical products;
ties use name/ID/unit for a stable order. `low_stock` includes active products in
active categories when stock is at or below threshold, including zero. Inactive
entries remain available in Inventory but do not generate dashboard restocking
alerts. The card and list share that rule. `pending_refund_count` supplies the
report/sidebar count; the existing refund service API delegates to it. No schema
changes are required.

### Shared refund tracking (feature 001)

`refund_tracking_service` exposes active-user `list_refunds(receipt, status)`,
`get_refund(id)`, `record_payout(id, method, reference="")`, `unread_notices()`, and
`acknowledge_decision(id)`. Filters distinguish pending/rejected, awaiting payout,
paid, and legacy assumed paid. Receipt searches treat wildcard characters
literally. Detached frozen DTOs carry request, payout, and correction details.
Owner-only `correct_payout(id, method, reference, reason)` appends before/after
audit while preserving the original payment actor/time. Existing owner-only
pending/history APIs and review permissions remain intact.

Review and requester notice commit together. Acknowledgment affects only the
current user's notice. Recording payment locks the approved request and relies
on a unique payout FK for duplicate protection, translating duplicate writes
after rollback. Payouts/corrections do not touch inventory or report aggregates.
Startup seed initialization records existing approvals as assumed paid once,
atomically with a durable marker, before any workspace is opened.

`RefundStatusDialog` is shared by the cashier POS and owner Refunds workspace.
It queries current detached details before payment, acknowledges the viewer's
personal notice on opening details, and opens a nested `PayoutDialog`. Payment
writes disable repeat actions before list refresh. The existing cart is untouched.
The POS owns a ten-second Tk `after` timer for notices, a separate status label,
unread badge, and explicit retry control; destruction cancels the timer. No
blocking notification dialogs or new runtime dependencies are introduced.
