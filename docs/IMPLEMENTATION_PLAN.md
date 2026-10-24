# Implementation Plan

**Read first:** `README.md`, then the other docs. Build **phase by phase, in order**. After each phase: run the app and tests and verify the "Done when" list before continuing. Do not build out-of-scope features.

## Phase 0: Project setup

**Implementation status:** foundation code and automated checks are implemented.
The connection checker reports success/failure clearly. Phase 1 extends startup
with tables, seeding, and the desktop login.

**Tasks**

- Create the structure from `ARCHITECTURE.md`; add `requirements.txt`, `.env.example`, `.gitignore` (`.env`, `.venv`, `receipts/`, `__pycache__`, `pawpos.log`).
- `config.py` (loads `.env`, constants: `SHOP_NAME="PawPOS"`, `REFUND_WINDOW_DAYS=7`, `THEME="cosmo"`).
- `core/errors.py`, `core/money.py` (`D()`, `round_money()`, `format_peso()`, `format_qty()`), `core/security.py`, `core/session.py`.
- `db/base.py`: engine, `session_scope()`, `Base`, `init_db()`.
- Placeholder assets: `logo.png`, `placeholder_product.png` (generate simple paw images with Pillow).

**Done when:** `python -c "from pawpos.db.base import init_db"` works; a DB connection check function reports success/failure clearly.

## Phase 1: Models, seed, auth

**Implementation status:** models, atomic seeding, authentication, owner-only
account services, startup wiring, and the desktop login are implemented. SQLite
tests check schema, seeding, account rules, and real Tk login/logout behavior
under Xvfb. MySQL DDL compiles successfully. During Phase 5, normal startup,
table initialization, both demo-account logins, catalog/POS reads, and logout
were also verified against local MySQL with desktop access.

**Tasks**

- Implement all models from `DATABASE.md` and import them in `models/__init__.py`.
- `db/seed.py` with seed users, categories, products, and initial stock movements.
- `auth_service.login(username, password)`; `user_service` (create cashier, enable/disable, reset password, list).
- `main.py`: init DB, seed, launch app.
- `ui/app.py` with ttkbootstrap root, screen switching, `ui/login_screen.py`.

**Done when:** tables are created in MySQL; seed data present; login works for both users; wrong password and disabled user fail; owner/cashier land on placeholder screens.

## Phase 2: Catalog services and owner shell

**Implementation status:** catalog services, the owner shell, and category/product
screens are implemented. Service tests cover validation, access, filters, stock
history, and image rollback. Real Tk tests cover catalog forms, image preview,
and deactivation. Live MySQL startup and catalog/POS reads were verified during
Phase 5. No database schema changes were needed in this phase.

**Tasks**

- `category_service`, `product_service` (CRUD, search, category filter, soft delete, image copy to `assets/products/`, initial-stock movement).
- `ui/owner/shell.py` (sidebar + content frames), `categories.py`, `products.py` (table, form, image picker with preview).

**Done when:** owner can add/edit/deactivate products and categories with validation; images saved and previewed; deleting a category with products is blocked.

## Phase 3: Cart logic (pure Python)

**Implementation status:** implemented with `Cart` and immutable `CartLine`
snapshots. Piece and kg additions merge by product; all adds and edits validate
precision, positive quantity, supplied current stock, and database numeric limits
before changing the cart. Tests cover rounding, totals, merging, editing,
removal, invalid inputs, and failed-operation preservation. This phase needs no
schema or UI changes. Live MySQL startup was subsequently verified in Phase 5.
Verification: 68 cart/pricing tests pass; the full suite passes with 157 tests
and 26 subtests (12 GUI tests skipped without a display). Ruff lint and format
checks pass. Initial sandboxed startup could not reach MySQL; Phase 5 verified
normal startup and both role workspaces with local desktop/database access.

**Tasks**

- `services/cart.py`: `Cart` with `add_piece`, `add_weight`, `set_quantity`, `remove_line`, `clear`, `total`, `lines`. Merge duplicate per-piece lines; per-kg lines each stay separate or merge by product (choose merge by product for simplicity).
- Enforce quantity rules (integer for piece, 3 decimals for kg, > 0) and available-stock checks (pass stock into the add call).
- Write `tests/test_cart.py` and `tests/test_weight_pricing.py` now.

**Done when:** tests pass for totals, rounding (`1.375 kg x ₱95.00 = ₱130.63`), merge, edit, remove, and invalid input.

## Phase 4: POS screen (selling UI)

**Implementation status:** implemented for cashier login and the owner's POS
sidebar entry. Product cards, live search/category filters, cached thumbnails,
weight entry with live pricing, cart editing/removal, and customer lookup/quick
creation are connected to services. Function keys are scoped to the visible POS;
payment was connected in Phase 5 and hold/void/resume in Phase 6.
Owners retain the cart and customer across page changes. No schema changes.
Live MySQL startup and catalog/POS reads were verified during Phase 5.
Verification: the full suite passes with 188 tests and 26 subtests, including
real Tk login, catalog, POS, modal dialog, keyboard scope, and minimum-window
layout checks on the local display. Ruff lint/format checks pass.

**Tasks**

- `widgets/product_card.py`, `pos_screen.py` (grid, category buttons, search, cart table, totals, top bar), thumbnail loader with cache.
- `dialogs/weight.py`, cart editing, Delete key, shortcuts F2/F5/F6/F4/F8, customer picker (`customer_service` + `dialogs/customer_picker.py`).
- Out-of-stock cards disabled.

**Done when:** a cashier can fill a cart with piece and kg items, edit/remove lines, and see correct totals; disabled cards cannot be clicked; shortcuts work.

## Phase 5: Complete sale, receipt, printing

**Implementation status:** atomic sale completion, validated Cash/GCash payment,
receipt preview, 80 mm PDFs, and the default-viewer handoff are implemented.
Successful payment clears the cart/customer and refreshes stock. Failure before
commit preserves the cart. A Last receipt action recovers/reopens a committed
sale's preview without repeating payment. PDFs embed a bundled, licensed font
with the peso sign. No schema changes.

Verification: 229 tests and 26 subtests pass, including real Tk Cash/GCash
checkout, receipt preview, actual PDF generation, cart/customer reset, stock
updates, cancellation, rollback, and receipt recovery. Ruff lint/format checks
pass. Normal startup and both role workspaces were verified against local
MySQL; the initial connection failures were due to sandbox restrictions.
Sale transaction tests use disposable SQLite data. Platform viewer handoffs are
tested with mocked launchers; live MySQL checkout and physical printing remain
manual acceptance checks.

**Tasks**

- `sale_service.complete_sale(...)` as in `ARCHITECTURE.md` 4.1 (atomic, locked, stock deduction, movements, receipt number generator `PAW-YYYYMMDD-NNNN`).
- `dialogs/payment.py` (cash with change, GCash reference).
- `receipt_service.build_receipt`, `make_pdf` (80 mm), `print_receipt` (open default viewer), `dialogs/receipt_preview.py`.
- Reset cart after a successful sale.
- Tests: `tests/test_sale_service.py` (stock deduction, movement rows, insufficient stock rollback, cash change, GCash reference required, receipt number sequence).

**Done when:** a full sale works end to end; stock decreases; movement rows exist; preview shows after payment; PDF opens; tests pass.

## Phase 6: Hold, resume, void

**Implementation status:** persistent holds, shared held lists, snapshot/customer
restoration, and reasoned line/transaction/held voids are implemented. F4/F6/F8
and their buttons call the new flows. Active carts are protected from resume
replacement; failed writes preserve the cart/held record. Nested confirmation
dialogs restore parent focus/grab. Cancellation deletes held sale/items and
retains audit rows in the existing `void_logs` table. No schema changes.

Verification: 258 tests and 26 subtests pass, including real Tk hold/resume
across app recreation, resumed-cart void/payment, reason validation, active-cart
protection, nested modal keyboard/grab behavior, and rollback preservation.
A file-backed SQLite test reopens the database through a new engine to verify
hold persistence. Ruff lint/format checks pass. Normal startup and held-list
reads pass for both roles against local MySQL. MySQL hold/resume, held
cancellation, and line/all voids also pass inside an outer transaction that is
rolled back; verification leaves no test sale/void rows and no stock changes.

**Tasks**

- `sale_service.hold_cart`, `list_held`, `resume_held` (removes the held row), `cancel_held`; `void_line`, `void_all` writing `void_logs`.
- `dialogs/held_list.py`, `dialogs/void.py` (reason required).

**Done when:** held carts survive an app restart; resume restores the cart; voids require a reason and appear in `void_logs`; stock unchanged by hold/void.

## Phase 7: Inventory

**Implementation status:** owner-only inventory services and the four-tab
Inventory screen are implemented. Receiving and signed adjustments atomically
save stock and movement rows, with precision/range checks and required adjustment
notes. Overview includes inactive products and low-stock highlights. History
is read-only with product/type/inclusive-date filters and receipt/refund
references. Delivery supplier/date/note use existing movement fields; no schema
changes are required.

Verification: service tests cover access checks, precision, negative/overflow
balances, dates, references, filters, and commit rollback. Real Tk tests cover
receiving, adjustments, validation preservation, filters, empty states, refresh
failure recovery, navigation, and minimum-window layout. Normal startup, both
role logins/logout, and owner inventory tabs pass against local MySQL. MySQL
receive/adjust/history checks pass inside an outer transaction that is rolled
back, leaving stock and movement counts unchanged. The full suite passes with
286 tests and 26 subtests, including all real Tk tests. Ruff lint/format checks
pass.

**Tasks**

- `inventory_service`: `receive_stock`, `adjust_stock` (no negative result), `list_movements(filters)`, `stock_overview`.
- `ui/owner/inventory.py` with the four tabs.

**Done when:** receiving and adjusting stock update products and write movement rows; the history table shows sale/refund/received/adjustment entries with correct signs and `stock_after`; rows are read-only.

## Phase 8: Refunds

**Implementation status:** refund rules/services, cashier receipt lookup and
request entry, owner Pending/History review tabs, receipt reprinting, and the
pending sidebar badge are implemented. Requests preserve the active POS cart;
owner approval adds stock only for resellable lines. Rejection requires a note
and releases reserved quantities. Failed writes preserve inputs and pending
state; committed review actions are disabled before a fallible refresh. Existing
refund tables support this phase without schema changes.

Verification: 33 service tests cover the exact seven-day boundary, completed
receipts, opened food, quantity/precision rules, pending/approved reservations,
rejection release, original-price rounding, access checks, review decisions,
stock overflow, and transaction rollback. Eight real Tk tests cover request to
review/inventory history, badges, validation, reprinting, modal cancellation,
failed writes, refresh failures, and minimum-window layout. Normal startup and
both role logins/logout pass against local MySQL. MySQL refund requests, mixed
approval, rejection, remaining quantities, and movement rows are verified inside
an outer transaction that is rolled back; shop stock and sale/refund/movement
counts are unchanged. The full suite passes with 327 tests and 26 subtests,
including all real Tk tests; Ruff lint and format checks pass.

**Tasks**

- `refund_service`: `create_request`, `list_pending`, `list_history`, `approve`, `reject`, `remaining_refundable(sale_item_id)`.
- Rules: 7-day window, valid completed receipt, no opened food, quantity within remaining refundable.
- `dialogs/refund_request.py` (cashier) and `ui/owner/refunds.py` (owner tabs, approve with resellable flags, reject with note).
- Tests: `tests/test_refund_rules.py`.

**Done when:** refund rules are enforced; approval restores stock only for resellable lines and writes `refund` movements; pending badge count shows in the sidebar; tests pass.

## Phase 9: Customers, sales history, users

**Implementation status:** all three owner screens are implemented. Customers
supports add/edit/search and completed purchase lists while retaining sale links.
Sales History filters completed sales by dates/receipt/account/payment, shows
original item/tender details and approved refund totals, and opens receipt PDFs.
Users supports cashier creation, enable/disable, and password resets. Owner
self-disable is blocked. Saved customer/account input is cleared before refresh;
validation and write failures retain entered values. No schema changes.

Verification: 16 new service tests cover filtered history, inclusive date bounds,
approved refund aggregation, immutable sale details, customer edits/rollback,
and owner access. Sixteen new real Tk tests cover all three screens, login after
account changes, owner protection, original receipts and PDF viewer handoff,
form preservation/refresh failures, and minimum-window layout. MySQL startup,
both demo logins/logout, customer purchases/edits, filtered sales/refund totals,
and cashier creation/status/password flows pass. All live verification records
and stock changes are rolled back; existing shop data/credentials are preserved.
The full suite passes with 359 tests and 26 subtests, including all real Tk
tests. Ruff lint/format checks pass.

**Tasks**

- `ui/owner/customers.py` (CRUD, search, purchases), `sales_history.py` (filters, detail, reprint), `users.py` (add cashier, enable/disable, reset password).

**Done when:** all three screens work; reprint opens the PDF; owner cannot disable themselves.

## Phase 10: Dashboard and reports

**Implementation status:** owner report services and 24 report tests are
implemented. Dashboard cards, charts, and the low-stock table follow in this
phase. No schema changes are needed.

**Tasks**

- `report_service`: `today_summary`, `daily_sales(days)`, `best_sellers(days, limit)`, `low_stock()`, `pending_refund_count()`. Net sales subtract approved refunds.
- `widgets/chart_frame.py` (Matplotlib in Tk) and `ui/owner/dashboard.py` (cards, two charts, low-stock table, refresh).

**Done when:** numbers match manually computed totals from seed and test sales; charts render in the blue theme; ranges can be toggled.

## Phase 11: Polish and final checks

**Tasks**

- Consistent theme and spacing, tooltips for shortcuts, empty states, error messages.
- Logging to `pawpos.log`; friendly DB-connection error dialog.
- Project `README.md` with setup steps and default accounts.
- Run through the **demo script** below and fix issues.

**Done when:** the demo script passes without errors and all tests pass.

## Required unit tests (summary)

| Test file                | Covers                                                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `test_cart.py`           | add/merge/edit/remove, totals, stock cap, invalid qty                                                                           |
| `test_weight_pricing.py` | kg x price rounding (`ROUND_HALF_UP`), 3-decimal limit, zero/negative rejected                                                  |
| `test_sale_service.py`   | stock deduction, movement rows, atomic rollback on insufficient stock, cash change, GCash reference required, receipt numbering |
| `test_refund_rules.py`   | 7-day window, receipt required, opened food blocked, over-refund blocked, resellable vs non-resellable stock effect             |

`tests/conftest.py` provides an in-memory SQLite engine, session override, and fixtures for users, categories, and products.

## Demo script (acceptance test)

1. Log in as **cashier**. Add a dog food loose item (1.5 kg), a toy, and a cat food pouch x2. Edit one quantity, remove one line. Attach a customer.
2. Hold the cart, restart the app, log in, resume it.
3. Void one line with a reason.
4. Pay with **GCash** (enter a reference). Confirm the receipt preview, print the PDF.
5. Confirm an out-of-stock product is disabled.
6. Request a refund for the sale using its receipt number; try an opened food item (should be blocked).
7. Log out, log in as **owner**. Approve the refund and mark one item resellable. Check **Inventory > Movement History**.
8. Receive stock for a low item; confirm it leaves the dashboard low-stock list.
9. View the **Dashboard** charts and **Sales History**; reprint the receipt.
10. Add a new cashier, disable them, and confirm they cannot log in.

## Definition of done (whole project)

- All features in `FEATURES.md` implemented; nothing out of scope added.
- Every stock change has a movement row; no float used for money.
- `python main.py` runs from a fresh clone following the README; `pytest` passes.
