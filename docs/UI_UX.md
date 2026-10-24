# UI / UX Specification

## 1. Look and feel

- **Library:** ttkbootstrap, theme **`cosmo`** (blue primary). Make the theme name a constant in `config.py`.
- **Tone:** friendly pet-shop feel, but clean and professional. Straightforward labels, no clutter.
- **Brand:** system name **PawPOS**; paw-icon placeholder logo (`assets/logo.png`) in the login screen and top bar.
- **Palette (guide):** primary blue `#2F80ED`, light blue background `#EAF3FF`, white cards, dark text `#1F2D3D`, success green, warning amber, danger red for voids/low stock.
- **Typography:** system font (Segoe UI on Windows). Body 11 pt, headings 16-20 pt bold, totals 24 pt bold.
- **Currency:** `₱` with thousands separators and 2 decimals (e.g. `₱1,250.00`). Per-kg prices show `₱95.00/kg`. Kg quantities show up to 3 decimals (trim trailing zeros, e.g. `1.5 kg`).
- **Window:** start maximized (min size 1280x720). Input is keyboard + mouse only.

## 2. Login screen

Phase 1 implements this screen and separate owner/cashier placeholder workspaces.
The full owner shell and POS screen follow in later phases. Failed login clears
the password and shows an inline error; logout returns to an empty login form.

- Centered card: logo, "PawPOS", username, password (masked), **Login** button. Enter submits. Error message inline in red.
- Cashier goes to the POS screen; owner goes to the owner shell.

## 3. Cashier POS screen

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

- Scrollable grid of cards (4-5 per row). Card: 96x96 thumbnail (paw placeholder if none), name (max 2 lines), price (`/kg` suffix for kg items), stock text. Low stock text is amber; out of stock card is greyed and **disabled**, with "Out of stock" label.
- Category buttons (a horizontal row; "All" first) and a search box that filters live.
- Click a card: per-piece adds 1; per-kg opens the weight dialog.

**Cart (right, ~40% width)**

- Table: item name, qty or kg, unit price, line total. Select a line; buttons or keys to edit quantity and remove.
- Double-click or Enter on a line to edit quantity/weight.
- Customer row: shows "Walk-in" or the customer name; **Select** opens a picker with search and quick-add.
- Large total. Buttons: **Hold (F4)**, **Void (F6)**, **Pay (F5)** (Pay is the primary, large, blue button; disabled when the cart is empty).

**Top bar:** cashier name; **Held (F8)**; **Request Refund**; **Logout**. No low-stock notice for cashiers.

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

- Left **sidebar** with logo and buttons: **Dashboard, Products, Categories, Inventory, Customers, Sales History, Refunds, Users**, plus **POS** (opens the cashier screen to sell) and **Logout** at the bottom. Active item highlighted. A badge on Refunds shows the pending count.
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
