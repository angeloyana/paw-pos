# System Features

Each feature lists **acceptance criteria (AC)** the AI should satisfy and verify.

Shared table presentation applies across owner workspaces, POS, and dialogs:
readable row spacing, bold padded headers, alternating row backgrounds, and
distinct selection colors. Tables follow live theme changes while retaining
their data, selection, and low-stock warning tags. Existing table interactions
and column layouts are preserved.

## A. Authentication and users

**F-A1 Login screen**

- AC: Username + password; wrong credentials show an error; disabled users are rejected.
- AC: Login requires exact username capitalization after trimming surrounding
  whitespace, even with a case-insensitive database collation.
- AC: Passwords verified with bcrypt. Owner goes to the owner shell; cashier goes to the POS screen.

**F-A2 Logout**

- AC: Returns to the login screen and clears the in-memory current user. Switching user = logout then login.

**F-A3 User management (owner)**

- AC: Create cashier (username unique, full name, password), enable/disable, reset password.
- AC: New usernames retain capitalization and trim surrounding whitespace;
  usernames differing only by case are rejected using Python case folding.
- AC: Owner cannot disable their own account. No forgotten-password recovery. Signed-in password changes require the current password.

**F-A4 Account settings**

- AC: Active owners and cashiers can read/save only their own built-in theme
  preference. Missing or unsupported saved themes default to `cosmo`.
- AC: Change own password requires the correct current password and matching
  confirmation, preserves the session, and uses existing bcrypt validation.
- AC: Failed saves roll back; seed runs preserve preferences and passwords.
- AC: Owners have a Settings sidebar page; both roles can open the shared form
  in a modal from POS, preserving cart/customer/last receipt and keyboard focus.
- AC: Apply theme saves then updates all existing widgets, custom canvases, and
  charts immediately. Login restores the account theme; logout uses `cosmo`.
- AC: Inline feedback retains failed input; successful password changes clear
  secrets. Theme and password changes save independently.

## B. Catalog

**F-B1 Categories (owner)**

- AC: Add, rename, delete categories. Fields: name (unique), `is_food` flag (used by refund rules), optional description.
- AC: Cannot delete a category that has products (show a message).

**F-B2 Products (owner)**

- AC: Fields: name, category, unit price, unit type (`piece` or `kg`), stock quantity, low-stock threshold, supplier (text), image (optional), active flag.
- AC: Validation: name required, price >= 0, threshold >= 0, stock >= 0. Per-piece stock is an integer; per-kg stock allows 3 decimals.
- AC: Image chosen via file dialog is **copied** to `assets/products/` and the relative path stored. Missing image shows a paw placeholder.
- AC: Edit and deactivate (soft delete). Inactive products are hidden from the POS.
- AC: Initial stock entered at creation creates a `stock_received` movement (note "Initial stock").
- AC: Changing stock after creation is **not** possible in the product form. Use Inventory.

## C. Point of sale (cashier and owner)

**F-C1 Product grid**

- AC: Cards show thumbnail, name, price (with `/kg` for kg items), and stock. Category buttons plus a search box filter the grid.
- AC: Out-of-stock cards are shown but disabled. Search is case-insensitive "contains".

**F-C2 Cart**

- AC: Click a card to add. Per-piece: quantity 1 (adds to existing line). Per-kg: weight pop-up (kg, up to 3 decimals, > 0, <= available stock), shows computed price, then adds.
- AC: Edit a line's quantity/weight, remove a line (Delete key), void (see F-C4). Cart shows line totals and grand total.
- AC: Cannot add/edit beyond available stock.

**F-C3 Hold and resume**

- AC: Hold (F4) saves the cart as `held` and clears the screen. Resume (F8) lists held carts (time, item count, total, customer) and loads one.
- AC: Resuming removes the held record from the list (the cart becomes the active cart again; holding again saves a new/updated held record).

**F-C4 Void**

- AC: Void line or void all (F6). Reason required (dropdown of common reasons plus "Other" with text). Logged in `void_logs`. No owner approval.
- AC: Void History in POS opens a read-only list; cashiers see only voids they
  performed and owners see all actors, including disabled accounts. Owners also
  have a Void History sidebar page using the same form. Optional calendar From/To
  filters start blank, include whole days, and apply automatically when selected or cleared; Refresh reloads on demand.
- AC: Show saved item name, actor, timestamp, quantity (without an inferred unit),
  amount, and Line/Transaction scope, newest first by timestamp/ID. Selecting a
  row shows its full reason in a scrollable read-only area. Transaction voids
  remain individual item rows. No edit/delete/restore action is available.
- AC: Invalid ranges and read failures retain authorized results with inline
  feedback; session changes clear cached records. History preserves the POS
  cart/customer/last receipt, sales, stock, and audit records.

**F-C5 Customer (optional)**

- AC: Select an existing customer via search or quick-add (name + contact). Can be skipped.

**F-C6 Payment**

- AC: Pay (F5) opens the payment dialog with the total.
- AC: Cash: amount received >= total, change displayed live. GCash: reference number required (non-empty).
- AC: On confirm, in one transaction: create sale (`completed`), items, deduct stock, write `sale` movements, assign receipt number.
- AC: If any line lacks stock at this moment, abort with a clear message and change nothing.

**F-C7 Receipt**

- AC: Preview appears automatically after payment with **Print** and **Close**.
- AC: Contents: shop name (PawPOS), date and time, receipt number, cashier name, items (name, qty or kg, unit price, line total), total, payment method, amount received and change (cash), GCash reference (GCash), customer name if any.
- AC: Print generates an 80 mm-wide PDF (ReportLab) and opens it with the OS default viewer so the user prints via the system print dialog.
- AC: Receipts can be reprinted from sales lookup.

**F-C8 Refund request (cashier)**

- AC: Enter receipt number, load sale, select lines/quantities, flag opened/used, enter reason, submit as `pending`.
- AC: Enforce all rules from `BUSINESS_PROCESS.md` section 6 with clear error messages.

## D. Inventory (owner)

**F-D1 Stock overview**: product, category, stock, threshold, low-stock highlight.
**F-D2 Receive stock**: product, quantity > 0, supplier (prefilled from product, editable), calendar-selected delivery date (defaults to today), note. Creates `stock_received` movement.
**F-D3 Adjust stock**: product, signed quantity change (not zero), reason (damage, loss, correction, other), note required. Resulting stock must not go below 0. Creates `adjustment` movement.
**F-D4 Movement history**: table with date, product, type, change (+/-), stock after, reference (receipt number or refund id), user, note. Filter by product, type, and date range using calendar-only From/To pickers with individual Clear buttons (blank = unrestricted). Read-only; never editable or deletable.

## E. Refund approval (owner)

**F-E1 Pending list**: receipt number, requester, date, items, reason, amount.
**F-E2 Approve**: owner marks each line resellable yes/no, confirms. Status `approved`, stock restored for resellable lines with `refund` movements, reviewer and time stored.
**F-E3 Reject**: owner enters a note; status `rejected`; nothing else changes.
**F-E4 History tab**: all processed requests.

## F. Sales history (owner; lookup also available to cashier via refund dialog)

- AC: Table of completed sales: receipt number, date, cashier, customer, method, total, refunded amount. Filter by date range, receipt number, cashier, payment method.
- AC: Date filters use the shared calendar-only From/To pickers with individual Clear buttons; blank dates are unrestricted. Calendar cancellation preserves the value. Selecting or clearing dates automatically applies the inclusive range; Refresh reloads on demand.
- AC: Detail view with items; **Reprint receipt** button.

## G. Customers (owner)

- AC: Add, edit, search customers (name, contact). View a customer's purchase list.
- AC: Customers with sales cannot be deleted (no delete in v1; just edit).

## H. Dashboard (owner)

- AC: Cards: today's net sales, today's transactions, number of low-stock items, pending refunds count.
- AC: Chart 1: daily sales (bar, last 7 days, toggle 30). Chart 2: best sellers (horizontal bar, top 5; range today / 7 / 30 days). Low-stock table.
- AC: Charts use Matplotlib embedded via `FigureCanvasTkAgg`, themed to match the selected account theme.
- AC: Refresh button (and refresh when the dashboard is shown).

## I. Shared refund tracking

- AC: POS Refunds provides shared receipt/status filtering, decision/item/payment
  details, requester-only unread badge and notices, ten-second polling, manual
  retry, and callbacks cancelled at logout. Opening a decision acknowledges it.
- AC: Confirmed payout recording preserves the cart. Owner Status / payouts adds
  correction controls and visible audit history. Failed reads retain data; failed
  writes retain inputs; committed writes disable repeat actions before refresh.

- AC: Active cashiers and owners can query every shop refund by literal receipt
  text and pending/rejected/awaiting-payout/paid/legacy-assumed-paid status.
- AC: Approval/rejection creates a requester-only persistent notice atomically;
  acknowledgment is restricted to the recipient.
- AC: Record full approved payouts as cash or GCash with a required reference.
  Record actor/time and reject duplicate or nonapproved payouts atomically.
- AC: Owners alone can correct method/reference with a reason and preserved audit;
  payment stays complete and original actor/time remain intact.
- AC: Startup marks existing approvals assumed paid once, with no fabricated
  payment details or old notices. Reports and stock are unchanged by payouts.

## J. Automatic table filtering

- AC: Sales History, Movement History, and owner/POS Void History apply date and
  dropdown filters automatically. Customers, Stock Overview, Sales History receipt,
  and Refund Status receipt searches apply after a 300 ms typing pause. Refund
  Status changes apply automatically. Enter and Refresh reload immediately.
- AC: Refresh buttons remain available and use the label Refresh. Search retains
  focus; pending reloads are cancelled when the screen closes. Existing live
  filters, validation, permissions, and read-failure handling remain in effect.
