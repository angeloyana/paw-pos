# UI / UX Specification

## 1. Look and feel

- **Library:** ttkbootstrap, default theme **`cosmo`** (blue primary), configured in `config.py`. Signed-in users can choose any built-in theme in Settings.
- **Tone:** friendly pet-shop feel, but clean and professional. Straightforward labels, no clutter.
- **Brand:** system name **PawPOS**; paw-icon placeholder logo (`assets/logo.png`) in the login screen and top bar.
- **Palette (default-theme guide):** primary blue `#2F80ED`, light blue background `#EAF3FF`, white cards, dark text `#1F2D3D`, success green, warning amber, danger red for voids/low stock.
- **Typography:** system font (Segoe UI on Windows). Body 11 pt, headings 16-20 pt bold, totals 24 pt bold.
- **Currency:** `₱` with thousands separators and 2 decimals (e.g. `₱1,250.00`). Per-kg prices show `₱95.00/kg`. Kg quantities show up to 3 decimals (trim trailing zeros, e.g. `1.5 kg`).
- **Window:** start maximized (min size 1280x720). Input is keyboard + mouse only.

All workspace and dialog tables use the same appearance: body text in the system
font at least 11 pt, bold padded headers at the system font size (at least 10 pt),
rows at least 32 pixels tall at standard display
scaling (growing with display scaling and font metrics), and subtle alternating
row backgrounds. Headers, stripes, and selection highlights follow the active
theme immediately. Low-stock warning text remains visible on striped rows;
selection uses the theme's selection foreground and background for readability.
Reloading, inserting, deleting, or moving rows keeps the stripes alternating.
Cells and headers have horizontal padding to separate adjacent values and keep
text away from table borders. Column minimum widths fit their headers and loaded
values using the current font metrics; reloading rows or changing themes updates
these widths. Narrow windows use horizontal scrolling instead of squeezing text
into neighboring columns. Numeric alignment and keyboard/mouse actions are preserved.
The Products table shares extra width across all columns, keeping Name wider for
product names without assigning it all the available space. Columns remain
manually resizable and retain their text-based minimum widths.

## 2. Login screen

The login screen is implemented. Owners enter the owner shell; cashiers enter
the POS screen. Failed login clears the password and shows an
inline error; logout returns to an empty login form.

- Centered card: logo, "PawPOS", username, password (masked), **Login** button. Enter submits. Error message inline in red.
- Cashier goes to the POS screen; owner goes to the owner shell.

## 3. Cashier POS screen

Phase 4 implements browsing, cart editing, and customer selection. Category
buttons wrap into rows to fit the owner workspace. Product thumbnails are cached
for the screen lifetime, with a paw fallback for missing or corrupt files. Stock
appears as plain text without low-stock alerts on the cashier screen. Click any
part of an available card to add it; out-of-stock cards cannot add items.
The weight dialog previews the merged line total when that product is already
in the cart. Invalid input disables OK and keeps the dialog open. Cart editing
uses the same dialog, with whole-number validation for piece items.

F2 focuses search; Enter/double-click edits the selected cart row, and Delete
removes it while the cart table has focus. F4 holds, F5 opens payment, F6 opens
void confirmation, and F8 lists held transactions. Payment is disabled
when the cart is empty. POS function keys are inactive in dialogs, on other
owner pages, and after logout. Owners retain their in-memory cart and customer
when switching sidebar pages. Logout discards that in-memory transaction.

Phase 5 connects the payment dialog: choose Cash or GCash, enter a sufficient
amount or reference, and confirm. Live validation disables confirmation until
the tender is valid; Cash displays change and offers Exact/100/500/1000 buttons.
Cancellation and failed payment preserve the cart/customer. A successful commit
clears both, refreshes product stock, and opens a read-only receipt preview.
Print writes the PDF and opens the OS viewer; errors remain in the preview.
The header's Last receipt button reopens the last completed sale during this
POS session, including after a failed preview. It never resubmits payment.

Phase 6 connects Hold/F4, Held/F8, and Void/F6. Holding clears the cart/customer
after saving. The held list shows time, line count, total, customer, and original
cashier. Resume is disabled while an active cart has items, with an explanation;
cancelling a held transaction is still available. Refresh reloads the list, and
an empty list explains that there are no held transactions. Resume restores the
saved snapshots/customer and removes that held record. Payment handles any
subsequent stock shortage.

Void defaults to the selected line, or the whole transaction when no line is
selected. Its confirmation dialog requires a common reason or nonblank Other
text (maximum 255 characters). No owner PIN is required. Cancel held opens a
nested transaction-void dialog and then refreshes the list. Successful writes
update the cart; failures retain the dialog/input and show an inline error.
Nested modals restore the parent's keyboard focus/grab, Enter confirms, and
Escape closes the dialog. Whole-cart voids clear the selected customer too.

Single screen, two main columns plus a top bar.

```
+---------------------------------------------------------------------+
| [logo] PawPOS        Cashier: Name          [Held F8] [Refund] [Logout]|
+--------------------------------------+------------------------------+
| [Search F2 ______________]           |  CART                        |
| [All][Dog Food][Cat Food][Toys]...   |  Item        Qty   Price     |
|                                      |  ----------------------------|
|  +------+ +------+ +------+ +------+ |  ...cart lines...            |
|  | img  | | img  | | img  | | img  | |                              |
|  | name | | name | | name | | name | |  Customer: [None] [Select]   |
|  | ₱ /kg| | ₱    | | ₱    | | ₱    | |  ----------------------------|
|  |Stock | |Stock | |Stock | |Stock | |  TOTAL          ₱0.00        |
|  +------+ +------+ +------+ +------+ |  [Hold F4] [Void F6] [PAY F5]|
+--------------------------------------+------------------------------+
```

**Product grid (left, ~60% width)**

- Scrollable grid of cards (columns adapt to available width). Card: 96x96 thumbnail (paw placeholder if none), wrapped name, price (`/kg` suffix for kg items), stock text. Out-of-stock cards are **disabled**, with an "Out of stock" label. Low-stock alerts belong to the owner dashboard.
- Category buttons (a horizontal row; "All" first) and a search box that filters live.
- Click a card: per-piece adds 1; per-kg opens the weight dialog.

**Cart (right, ~40% width)**

- Table: item name, qty or kg, unit price, line total. Select a line; buttons or keys to edit quantity and remove.
- Double-click or Enter on a line to edit quantity/weight.
- Customer row: shows "Walk-in" or the customer name; **Select** opens a picker with search and quick-add.
- Large total. Buttons: **Hold (F4)**, **Void (F6)**, **Pay (F5)** (Pay is the primary large button; disabled when the cart is empty).

**Top bar:** cashier name; **Held (F8)**; **Request Refund**; **Refunds** with unread decision count; **Settings**; **Logout**. No low-stock notice for cashiers.

## 4. Dialogs

| Dialog              | Content                                                                                                                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Weight**          | Product name, price per kg, entry for kg (focus on open), live computed price, available stock; OK/Cancel. Enter confirms, Esc cancels. Rejects <= 0, > stock, and more than 3 decimals       |
| **Payment**         | Total; method toggle (Cash / GCash). Cash: amount received entry + live change; quick amount buttons (exact, 100, 500, 1000). GCash: reference number entry. **Confirm** disabled until valid |
| **Receipt preview** | Opens automatically after payment. Monospace receipt text; **Print** and **Close** buttons                                                                                                    |
| **Void**            | Choose "line" or "all"; reason dropdown (Wrong item, Customer changed mind, Wrong weight, Price issue, Other) + text if Other; reason required                                                |
| **Held list**       | Table: time, items, total, customer; **Resume** and **Cancel held (void)**                                                                                                                    |
| **Customer picker** | Search box, list, "Add new" with name + contact                                                                                                                                               |
| **Refund request**  | Receipt number entry, **Load**, shows items with checkboxes and qty/kg entry, "Opened/used" checkbox per line, reason field, **Submit request**. Shows rule errors inline                     |

## 5. Owner shell

The sidebar implements Products, Categories, Inventory, Customers, Sales History,
Refunds, Users, Settings, and POS. The Dashboard now shows report cards, charts, and active
low-stock products. All owner sidebar workspaces are enabled. Select a catalog
table row to edit it. Forms show errors inline and
retain input on validation failure. The Active checkbox permits reactivation;
deactivation buttons ask for confirmation. Product stock is editable only during
creation. Missing image files display the paw placeholder.
Catalog forms have a vertical scrollbar so the final controls remain accessible
at the minimum window size and with larger system fonts.

- Left **sidebar** with logo and buttons: **Dashboard, Products, Categories, Inventory, Customers, Sales History, Refunds, Users, Settings**, plus **POS** (opens the cashier screen to sell) and **Logout** at the bottom. Active item highlighted. A badge on Refunds shows the pending count.
- Content area on the right swaps frames.

### Screens

| Screen            | Layout                                                                                                                                                                                                                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Dashboard**     | Top row of 4 stat cards (Today's sales, Transactions, Low-stock items, Pending refunds). Middle row: Daily sales bar chart (7/30 toggle) and Best sellers chart (range selector). Bottom: Low-stock table (product, stock, threshold) |
| **Products**      | Table (thumbnail optional, name, category, type, price, stock, threshold, active) with search and category filter; **Add / Edit / Deactivate**. Form: all product fields + image picker with preview                                  |
| **Categories**    | Simple table + add/edit/delete form with `is_food` checkbox                                                                                                                                                                           |
| **Inventory**     | Tabs: **Stock Overview**, **Receive Stock**, **Adjust Stock**, **Movement History** (filters: product, type, dates)                                                                                                                   |
| **Customers**     | Table with search; add/edit form; selected customer's purchases below                                                                                                                                                                 |
| **Sales History** | Filters (dates, receipt no., cashier, method); table; detail panel; **Reprint**                                                                                                                                                       |
| **Refunds**       | Tabs: **Pending** and **History**. Select a request, view items; **Approve** (resellable checkboxes per line) or **Reject** (note)                                                                                                    |
| **Users**         | Table with role/status; **Add cashier**, **Enable/Disable**, **Reset password**                                                                                                                                                       |

## 6. Keyboard shortcuts

| Key    | Action                                  |
| ------ | --------------------------------------- |
| F2     | Focus product search                    |
| F4     | Hold transaction                        |
| F5     | Pay                                     |
| F6     | Void                                    |
| F8     | Resume held transaction                 |
| Delete | Remove selected cart line               |
| Enter  | Confirm in dialogs / edit selected line |
| Esc    | Close dialog / cancel                   |

Shortcuts are active only on the POS screen (except Enter/Esc in dialogs). Show hints on the buttons.

## 7. UX rules

- Confirmation before destructive actions (void all, disable user, reject).
- Success and error feedback via non-blocking toast or status bar where possible; blocking dialogs for errors that need action.
- Focus management: after adding an item, focus returns to the search box. Dialog opens with focus in the first input.
- Empty states: friendly text ("Cart is empty. Click a product to start.").
- Table columns right-align numbers; sortable headers where cheap.
- Never freeze the UI on long work (PDF generation and charts are fast; no threading needed).

### Inventory (Phase 7)

The four tabs are available to the owner. Stock Overview includes inactive
products and highlights balances at or below the threshold. Receive Stock
prefills the selected product's supplier and accepts a delivery date, quantity,
and note. Adjust Stock uses a signed quantity, a common reason, and a required
note. Validation errors retain input. Successful writes clear quantity/note
inputs before refreshing, preventing accidental resubmission after a read error.
Movement History refreshes when opened and exposes only filtering and scrolling;
there are no edit/delete actions. Date filters are inclusive and optional.
History shows explicit positive signs, receipt/refund references, and an empty
state when no rows match. Both tables have vertical and horizontal scrollbars.

### Refunds (Phase 8)

Request Refund opens a scrollable modal with receipt lookup, remaining
quantities, per-item selection/quantity/opened flags, reason, and original-price
total. Editing the receipt number invalidates the loaded sale and disables
submission/reprinting until Load succeeds. Errors retain entered inputs;
successful submission closes the dialog and reports pending owner approval on
the POS. The current cart/customer stays intact. Reprint opens the existing
receipt preview, without creating a refund or sale. Escape cancels the modal.

The owner sidebar shows `Refunds (N)` and refreshes after requests, reviews, and
navigation. The Refunds screen has Pending and History tabs with scrollable
tables and item details. Each pending line defaults to Resellable No; Yes
restores that line's stock on approval. Approve asks for confirmation and reminds
the owner to return money manually. Reject requires a note and confirmation.
Processed details show status, reviewer/time, note, and resellable choices;
review controls are disabled. After a saved review, controls are disabled before
refresh, preventing resubmission if the read fails. Empty pending lists explain
where processed reviews appear.

### Customers (Phase 9)

The owner can search names/contacts, add customers, and select a row to edit.
Contact is optional; customer deletion is not available. Selecting a customer
loads only their completed purchases below the form, with receipt, date, payment,
total, and approved refunded amount. Empty states explain unmatched searches and
customers without purchases. Validation/write errors preserve input. Saved input
is cleared before refreshing so a refresh failure cannot duplicate a new record.

### Sales History (Phase 9)

The owner can filter completed sales by inclusive dates (blank = any date),
literal receipt text, account, and Cash/GCash. Account choices include inactive
users and owners because both can have historical sales. The table shows gross
sale totals and approved-only refunded amounts. Select a row to see original
item quantities/prices, customer/cashier, cash tender/change or GCash reference.
Detail text is read-only. Reprint receipt generates the existing 80 mm PDF and
opens the default viewer, without changing sales or stock. Viewer errors retain
the selected sale and the generated PDF path for manual opening. Details/forms
scroll at the minimum window size; the sales table scrolls in both directions.
Sales History columns share spare table width as the window expands, while
preserving text-based minimum widths and horizontal scrolling in narrow windows.

### Users (Phase 9)

Add cashier clears the form for username, full name, and masked new password.
Selecting an account makes its identity fields read-only and clears the password
input. Cashiers can be disabled with confirmation or re-enabled. Owner accounts
have no enabled/disabled action; services also protect the current owner from
self-disable. Reset password applies to the selected account, including the
owner's own demo password. Validation and write failures retain form input.
Successful actions clear password and account input before refreshing; read
failures report that the save succeeded. No password/hash appears in the table.
The form scrolls so every control is reachable at the minimum window size.

### Dashboard (Phase 10)

Owner login and the Dashboard sidebar entry show four summary cards, two theme-colored
Matplotlib charts, and a read-only low-stock table. Daily net sales offers 7/30
calendar days, fills empty dates, and renders negative days in red. Currency
axis labels show pesos and centavos. Best sellers offers Today/7/30 days and
labels the top five gross quantities with piece/kg units. Product names wrap,
and exact quantity labels use Decimal-derived text.

The low-stock list includes active products/categories at or below threshold,
including zero stock, and scrolls in both directions. Cards/list share the same
rule. Empty charts and low-stock lists explain that there is no matching
activity. All reports refresh on screen creation, selector changes, or Refresh.
Read failures retain the previous display and show a retry message. Chart figures
belong to their frames, reuse their canvases for range changes, and cancel queued
Tk draws on destruction. The dashboard fits the 1280×720 minimum window and does
not alter the draft POS cart/customer during navigation.

### Final polish (Phase 11)

POS search, Hold, Pay, Void, Held, edit/remove, and cart rows have hover help
showing their keyboard actions. Tooltip windows and scheduled hovers close on
navigation or logout. Customer selection explains empty saved lists/searches
and offers Add or Walk-in. Database startup errors show a native owned dialog
before the themed login; headless startup retains console diagnostics. UTF-8
diagnostics also go to the ignored project-root `pawpos.log`.

### Shared refund status and payout tracking

POS Refunds opens a shared modal list with receipt search and filters for All,
Pending, Rejected, Approved awaiting payout, Paid, Assumed paid before tracking,
and Unread decisions. Refresh runs on opening and by button/Enter; failed reads
retain the previous list and show inline retry feedback. Select a request to
load its current decision, item amounts, requester/reviewer/times, review note,
payment details, and correction history. Opening a decision acknowledges only
the signed-in requester's notice. Empty filters explain that no requests match.

A nonblocking POS notice names the latest unread decision. The Refunds button
shows the unread count, View decisions opens the unread filter, and Refresh
notices retries failures. Notices refresh every ten seconds and when the modal
closes; scheduled callbacks are cancelled when the POS is destroyed on logout.
Unread notices survive sessions and only go to the original requester.

Approved unpaid requests enable Record payout. A nested dialog shows the receipt
and full amount, Cash/GCash selection, and required GCash reference. Confirmation
explicitly states the money was already returned and reminds staff to coordinate
physical handovers. Failed saves retain input; successful saves disable repeat
actions before refreshing. Stale status is rechecked before opening payment.

Owners can open Status / payouts from their existing Refunds workspace, including
from a selected request. Processed approval details show payment status. Real paid
requests enable owner-only Correct payout details, with required correction reason
and retained before/after audit. Assumed-paid legacy requests show unknown payment
details and have no payment/correction actions. Details scroll and Escape closes
the shared modal while restoring the parent's focus/grab.

### Settings

Owners open Settings from the sidebar; owners and cashiers can also use the POS
Settings button to open a modal window. Both share the same form: Appearance
with a read-only list of all built-in theme names, Apply theme, Reload saved
theme, and Change password with masked Current password, New password, Confirm
new password, and a separate Change password button.

Apply theme saves the account preference first, then changes appearance immediately
without recreating the workspace. Failed saves keep the existing theme and retain
input with inline feedback. Custom canvases and dashboard charts follow theme
colors. Dark themes use filled sidebar buttons to keep navigation readable.
Login restores the saved theme (missing/unsupported values use `cosmo`);
logout restores `cosmo`. A failed theme read opens the default workspace with a
message directing the user to Settings to retry.

Password changes require the correct current password, matching confirmation,
and the existing nonblank/72 UTF-8 byte validation. Failure retains inputs;
success clears password fields and keeps the user signed in. Navigating away or
closing the modal discards password input. Forgotten-password recovery still
requires contacting the owner for a reset.

Settings preserves the POS cart, selected customer, and last receipt. POS function
keys are inactive in the modal; Escape/Close dismisses it and restores focus.
Controls fit the minimum window size. Theme and password saves are independent.
