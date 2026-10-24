# PawPOS: Project Documentation

PawPOS is a single-shop **point of sale system for a pet shop** that sells pet food and pet supplies. It is a **school project**: one desktop computer, fully offline, Python + Tkinter + SQLAlchemy + MySQL.

> **These documents are written to be consumed by an AI coding agent.** Read them in the order below, then build following `IMPLEMENTATION_PLAN.md` one phase at a time.

## Implementation status and setup

**Phase 8 is implemented.** Startup checks the
database connection, creates all ten tables, seeds an empty installation, and
opens the blue-themed desktop login. Owners can manage categories and products
from the sidebar, including images, search, initial stock, and deactivation.
Cashiers enter the POS screen; owners can open it from the sidebar. Both
workspaces support logout.
Local MySQL startup, catalog/POS reads, both demo-account logins, and logout have
been verified. Inventory receiving, adjustments, and history were verified on
local MySQL inside an outer transaction that was rolled back without changing
shop stock or history. Automated checkout/rollback tests use disposable SQLite
data; live MySQL checkout and physical printing remain manual acceptance checks.
Hold/resume, held cancellation, and line/transaction voids were also verified
against local MySQL inside a transaction that was fully rolled back.

The POS supports live search, category filters, cached product thumbnails,
piece/kg cart entry, quantity editing, removal, and optional customer selection
or quick creation. Click a product to add it; kg items prompt for weight and show
the computed line price. Double-click a cart row or press Enter to edit it;
Delete removes the selected row. F2 focuses search. Out-of-stock cards are
disabled. Owner navigation preserves the cart and selected customer until
logout. Adding to a cart does not deduct stock. **Request Refund** looks up a completed
receipt and submits selected items for owner review; it also offers receipt
preview/reprinting.

**Hold (F4)** saves the cart and customer to the database, then clears the POS.
**Held (F8)** lists saved transactions after logout or restart. Resume restores
the original quantities/prices and customer and removes the held record. Hold
or empty the active cart before resuming another; you can still cancel a held
transaction while a cart is active. Holds are shared by the shop's active
cashiers and owner. Stock is checked again at payment.

**Void (F6)** logs a selected line or the whole transaction. Choose a common
reason or **Other** and explain it, then confirm. **Cancel held (void)** uses the
same reason dialog. Whole-transaction voids clear the cart/customer; cancelled
holds retain their item/reason audit in `void_logs`. Holds and voids leave stock
unchanged. Delete/Remove remains a cart edit; use Void for a logged cancellation.

Press **Pay (F5)** to choose **Cash** or **GCash**. Cash shows change as you type;
the quick buttons enter the exact total, 100, 500, or 1000 pesos. GCash requires
a reference number. Confirm payment saves the sale and its stock movements
together, then clears the cart/customer and opens a receipt preview. Stock or
payment errors keep the cart for correction. **Print** saves an 80 mm PDF under
`receipts/` and opens the default PDF viewer, where you can print it. **Last
receipt** reopens the most recent receipt in the current POS session, including
after a preview/printing failure; reopening it does not charge the sale again.
Install/configure a PDF viewer locally for the Print handoff.

1. Install Python **3.11 or 3.12** and a local **MySQL 8** server.
2. Create the database with `CREATE DATABASE pawpos CHARACTER SET utf8mb4;`
   and create a local database user with privileges on it.
3. Create and activate a virtual environment:

   ```sh
   python -m venv .venv
   source .venv/bin/activate
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and fill in your local database credentials.
   Keep `.env` private; it is ignored by Git.
5. Run `python main.py` in a desktop session. Tables and demo data are created on
   first run. Sign in as `owner` / `owner123` or `cashier` / `cashier123`. Existing
   users, passwords, and inventory are preserved on later starts. These are
   school-project demo passwords; change them before using real shop data.
   Connection failures report what to check and exit with status 1.
6. Run `python -m pytest`. Tests use in-memory SQLite and need no MySQL server or
   real credentials. GUI tests use real Tk widgets and skip when no display is
   available. On Linux with Xvfb installed, use `xvfb-run -a python -m pytest` to
   include them in a headless session. Foundation checks also support
   `python -m unittest discover -v`.

Use Ruff to lint and format Python code:

```sh
python -m ruff check .
python -m ruff format --check .
# Apply formatting:
python -m ruff format .
```

`ruff.toml` targets Python 3.11, uses an 88-character line length, and enables
Ruff's standard error checks plus import sorting.

Configuration is loaded from the project-root `.env`, regardless of the current
working directory. Existing environment variables take precedence. Supported
settings are `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` as shown
in `.env.example`; connections use `utf8mb4` and a five-second connect timeout.
The configured database must already exist.

In the owner workspace, select **Categories** or **Products**. Select a table row
to edit it; use **Add category** or **New** to create another record. Product
images are copied to `assets/products/` when saved. **Show inactive** includes
deactivated records, which can be reactivated with the **Active** checkbox.
Categories with products cannot be deactivated. Initial stock is entered only
when creating a product; use **Inventory** to change existing stock. Sidebar
entries for later phases are disabled.

Owners can also open **Customers** to add/edit names and optional contacts,
search either field, and view the selected customer's completed purchases.
Customer records and purchase links are retained; there is no delete action.

Inventory has four owner-only tabs:

- **Stock Overview** lists products, categories, stock, and thresholds, with low
  stock highlighted. Inactive products are included. Search and Refresh update
  the list.
- **Receive Stock** records a positive quantity, supplier (prefilled from the
  product), delivery date, and optional note. The supplier applies to this
  delivery; it does not change the product default.
- **Adjust Stock** accepts a signed nonzero change, a reason, and a required
  note. Stock cannot fall below zero. Piece quantities must be whole numbers;
  kg quantities allow three decimals.
- **Movement History** shows read-only received, adjustment, sale, and refund
  entries, with signed changes, stock after, references, actor, and notes. Filter
  by product, type, and inclusive dates (`YYYY-MM-DD`; blank means any date).

Receiving and adjustments save stock and movement history in one transaction.
Delivery supplier/note text shares a 255-character history field. Past delivery
dates are recorded at midnight; future dates are rejected. Stock after means
the balance when posted, including for backdated deliveries. Returning to the
POS refreshes its stock while preserving any draft cart.

Use **Request Refund** on the POS to load a receipt, select items, enter returned
quantities, flag opened/used items, and give a reason. Requests must be submitted
within seven elapsed days of sale completion. Opened food is blocked. Pending
and approved requests count against the remaining refundable quantity; rejected
requests release that quantity. Requests leave stock unchanged and preserve any
active cart/customer. The displayed amounts use the original sale prices.

Owners open **Refunds** from the sidebar; its badge shows the pending count.
Select a **Pending** request and set each line's **Resellable** choice (default
No), then confirm **Approve**. Only resellable lines return to stock, with linked
refund movements. **Reject** requires a note and confirmation, and leaves stock
unchanged. **History** shows processed requests, item decisions, reviewer, and
review note. A timely request can be reviewed after its seven-day request
window. The refund money is handed back manually; there is no payment reversal
integration. POS users submit requests only; approval stays in the owner
workspace.

Local MySQL refund lookup/request, opened-food rejection, mixed resellable
approval, rejection, and movement history were verified inside a transaction
that was fully rolled back, leaving sales, refunds, movements, and shop stock
unchanged.

To regenerate the bundled paw placeholders, run
`python scripts/generate_assets.py`. Product image copies will live in
`assets/products/`; generated receipts and logs are ignored by Git.
Receipt PDFs use the bundled DejaVu Sans Mono font and its license in
`assets/fonts/` so the peso sign prints without requiring a system font install.

## Reading order

| #   | File                     | Purpose                                            |
| --- | ------------------------ | -------------------------------------------------- |
| 1   | `README.md`              | Overview, scope, global rules for the AI           |
| 2   | `BUSINESS_PROCESS.md`    | How the shop works, roles, and business rules      |
| 3   | `FEATURES.md`            | Feature list per role with acceptance criteria     |
| 4   | `ARCHITECTURE.md`        | Layers, project structure, key flows, transactions |
| 5   | `DATABASE.md`            | Tables, columns, constraints, seed data            |
| 6   | `UI_UX.md`               | Screens, layouts, shortcuts, theme                 |
| 7   | `TECH_STACK.md`          | Libraries, versions, configuration                 |
| 8   | `IMPLEMENTATION_PLAN.md` | Phased build order with tasks and "done" checks    |

## Scope summary

**In scope**

- Two roles: **Owner** (full access) and **Cashier** (sales, void, refund requests)
- Sell per-piece items and per-kilo items (weight typed manually by the cashier)
- Payments: **Cash** and **GCash** (manual; only a reference number is stored)
- Held transactions saved in the database
- Voids (before payment, free, reason logged) and Refunds (after payment, owner approval required)
- Inventory with a **stock movement history** table
- Product thumbnails, categories, customers (optional at checkout)
- Dashboard with charts (daily sales, best sellers) and a low-stock list
- Receipt preview and a receipt-sized PDF opened in the system print flow
- Simulated login with bcrypt-hashed passwords

**Out of scope (do NOT build)**
Expiry/batch tracking, FEFO, barcode/SKU, discounts (senior/PWD/promo), VAT, loyalty points, real GCash API, digital scale integration, backup, CSV export, password reset flow for self-service, auto-lock, multi-terminal/concurrency handling, migrations (Alembic), packaging (PyInstaller), cashier low-stock alerts.

## Global rules for the AI agent

1. **Follow the layers**: UI never talks to the database directly; UI calls services, services use models/session. (See `ARCHITECTURE.md`.)
2. **Money uses `decimal.Decimal`**, never `float`. Database columns are `Numeric`. Display with the peso sign: `₱1,234.50`.
3. **Quantities**: per-piece items are whole numbers; per-kilo items allow up to **3 decimals** (kg).
4. **Every stock change creates a `stock_movements` row** in the same DB transaction as the change. Stock is never edited without a movement record.
5. **Sales, refunds, and stock changes must be atomic**: one transaction, rollback on any error.
6. **Never hard-delete** products, users, categories with history. Use `is_active`.
7. **Scope discipline**: do not add features listed as out of scope. If something is ambiguous, pick the simplest option consistent with these docs and note it in a code comment.
8. **Keep code simple and readable.** This is a school project: clear names, short functions, docstrings on services.
9. **Write unit tests** for the core logic listed in `IMPLEMENTATION_PLAN.md` (Phase 9). Tests use an in-memory SQLite database.
10. After each phase, run the app (`python main.py`) and the tests, and confirm the phase's "Done when" checklist.

## Quick facts

| Item                  | Value                                  |
| --------------------- | -------------------------------------- |
| System name           | PawPOS                                 |
| Currency              | Philippine peso (₱)                    |
| Run command           | `python main.py`                       |
| Default owner login   | `owner` / `owner123` (seed; change it) |
| Default cashier login | `cashier` / `cashier123` (seed)        |
| Theme                 | ttkbootstrap, blue (`cosmo`)           |
