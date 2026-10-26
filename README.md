# PawPOS

PawPOS is a desktop **point of sale system for a pet shop**, built as a school
project. It manages sales, inventory, customers, receipts, and refunds for one
shop using one computer. Prices use Philippine pesos (₱).

The application runs locally with **Python, Tkinter/ttkbootstrap, SQLAlchemy,
and MySQL**. After installing the dependencies, daily operation works offline.
GCash payments and refund payouts are recorded manually; the app does not connect
to a payment provider.

## Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running and seeding](#running-and-seeding)
- [Building](#building)
- [Using PawPOS](#using-pawpos)
- [Testing and code checks](#testing-and-code-checks)
- [Files and assets](#files-and-assets)
- [Troubleshooting](#troubleshooting)
- [Project documentation](#project-documentation)

## Features

- **Owner and cashier accounts** with password authentication and account themes.
- **Checkout** for products sold by piece or kilogram, optional customers, cash
  and manual GCash payments, and PDF receipts.
- **Held carts and voids**, with saved transactions and logged cancellation reasons.
- **Catalog and inventory management**, including product images, stock receipts,
  adjustments, movement history, and low-stock indicators for the owner.
- **Refund requests and owner decisions**, plus shared status tracking, decision
  notices, and recorded payouts.
- **Owner dashboard and sales history** with charts, filters, and receipt reprints.
  Dashboard Top 5 Products ranks by net revenue, deducting approved refunds on
  their approval date, with Today / 7 days / 30 days ranges.

This version is designed for a single terminal. It does not include executable
packaging, multi-terminal support, barcode scanning, digital scales, discounts,
VAT calculation, or integrated payment processing.

## Prerequisites

Install the following before setting up the project:

| Requirement | Purpose |
| --- | --- |
| Python **3.11 or 3.12** | Run the application and development commands |
| Tkinter | Display the desktop interface |
| Local **MySQL 8** server | Store application data |
| PDF viewer | Open generated receipts and print them |

A graphical desktop session is required to run the app. Check Tkinter with
`python -m tkinter`; a small demonstration window should open. On systems where
Python is named `python3`, use `python3` to create the virtual environment.
Linux distributions may require a separate Tkinter package matching your Python
version, such as `python3-tk` on Ubuntu/Debian.

## Installation

### 1. Get the project

Clone this repository or download and extract it from GitHub. Open a terminal
in the `paw-pos` project directory, where `main.py` and `requirements.txt` live.
Run the commands below from that directory.

### 2. Create a virtual environment and install dependencies

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell prevents activation, you can use the environment directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Complete the database and configuration steps before starting the app.
Use that same interpreter path for the testing commands if you skip activation.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Activate the environment again whenever you open a new terminal.
Use `deactivate` when you are finished.

### 3. Create the MySQL database and user

Start your local MySQL server. Open a MySQL client as an administrator, for example:

```bash
mysql -u root -p
```

Run the following SQL once, replacing the example password with your own:

```sql
CREATE DATABASE pawpos CHARACTER SET utf8mb4;
CREATE USER 'pawpos'@'localhost' IDENTIFIED BY 'replace_with_your_local_password';
GRANT ALL PRIVILEGES ON pawpos.* TO 'pawpos'@'localhost';
```

If you already have a database and user, use their credentials instead.
The app creates tables inside the configured database, but does not create the
database itself. Its user needs permission to create tables and read/write data.

### 4. Configure the connection

Copy the example environment file:

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
cp .env.example .env
```

Edit `.env` to match the database and password from the previous step.
Do not overwrite an existing `.env` containing your working settings.

## Configuration

The project-root `.env` contains the database connection settings:

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=pawpos
DB_PASSWORD=replace_with_your_local_password
DB_NAME=pawpos
```

| Variable | Description | Default when unset |
| --- | --- | --- |
| `DB_HOST` | MySQL server hostname | `localhost` |
| `DB_PORT` | MySQL server port | `3306` |
| `DB_USER` | Database username | `pawpos` |
| `DB_PASSWORD` | Database password | Empty string |
| `DB_NAME` | Existing database name | `pawpos` |

Existing environment variables take precedence over `.env`. The app finds `.env`
in the project directory even when launched from another working directory.
Connections use `utf8mb4` and a five-second connection timeout.

Keep `.env` private; it is ignored by Git.

## Running and seeding

With MySQL running and your virtual environment active, start the application:

```bash
python main.py
```

Startup checks the connection, creates missing tables, initializes refund
tracking, and seeds demo data **only when the `users` table is empty**. There is
no separate seed command to run.

An empty installation receives two accounts, eight categories, fourteen products,
and initial stock movement records for products with positive stock. Some
products deliberately start low or out of stock for demonstrations.

| Role | Username | Initial password |
| --- | --- | --- |
| Owner | `owner` | `owner123` |
| Cashier | `cashier` | `cashier123` |

Usernames are case sensitive: enter `owner`, not `Owner` or `OWNER`. Surrounding
username whitespace is ignored. New cashier usernames preserve their capitalization,
but names differing only by case cannot be used for separate accounts. Existing
usernames are unchanged; accounts stored in lowercase require lowercase login.

Change these demo passwords through **Settings** before using real shop data.
The owner starts on Dashboard; the cashier starts in POS. Owners can also open
POS from the sidebar.

Later launches preserve existing accounts, passwords, inventory, and account
preferences. If any user already exists, startup skips the entire demo seed;
it does not restore missing demo accounts or reset stock.

Table creation does not migrate columns in existing tables. Follow the relevant
feature documentation if a future update requires manual SQL. Startup also
classifies refunds approved before payout tracking as assumed paid once, without
inventing payment details or paying them again.

## Building

PawPOS runs directly from Python source. There is no separate build command,
installer, or supported executable packaging step. Install `requirements.txt`,
configure MySQL, and run `python main.py` as described above.

## Using PawPOS

### Checkout and receipts

1. Search or choose a category from the dropdown (All by default), then click a product to add it.
   Kilogram products prompt for weight, with up to three decimal places;
   piece quantities must be whole numbers. Out-of-stock products are disabled.
2. Double-click a cart row or press **Enter** to edit its quantity. Use **Delete**
   to remove a selected row. Optionally select or create a customer.
3. Select **Pay (F5)**. For cash, enter the amount received and check the change.
   For GCash, enter the reference number after handling payment manually.
4. Confirm payment. The app saves the sale and deducts stock together, clears
   the cart, and opens the receipt preview. Payment errors leave the cart available
   for correction.
5. Select **Print** to generate an 80 mm PDF in `receipts/` and open your default
   PDF viewer. Print from that viewer. **Last receipt** reopens the latest receipt
   in the current POS session; owners can also reprint from **Sales History**.

Adding products to a cart does not deduct stock. Stock is checked again when
payment is confirmed. Reprinting a receipt does not charge the customer again.

### Hold, resume, and void

- **Hold (F4)** saves the cart and customer, then clears the active cart.
- **Held (F8)** lists shared held transactions, including after logout or restart.
  Hold or empty your active cart before resuming another transaction.
- **Void (F6)** records a cancellation of a selected line or the whole cart.
  Choose a reason and confirm. Use **Cancel held (void)** to cancel a saved cart.
- Holds and voids do not change stock. **Delete/Remove** is an ordinary cart edit;
  use **Void** when a cancellation needs a reason in the audit history.
- **Void History**, immediately right of Held in the header, shows your own voids when
  signed in as a cashier; owners see all shop voids. Choose optional From/To
  dates with Calendar; filtering applies automatically. Blank dates are unrestricted
  and both selected days are included. Select an item row to read its full reason.
  History is read-only; whole-cart cancellations appear as one row per item.

### Owner management

Use the owner sidebar to access these workspaces:

| Workspace | What to do |
| --- | --- |
| Dashboard | Review net sales, transaction counts, best sellers, low stock, and pending refunds; use Refresh after changes |
| Categories / Products | Add and edit the catalog, set prices and units, attach images, and deactivate records |
| Inventory | Receive deliveries, adjust stock with a reason and note, and inspect movement history |
| Customers | Add/edit customers, search contacts, and view their purchase history |
| Sales History | Filter completed sales, inspect payment details, and reprint receipts |
| Void History | Review all actors' voided item records and reasons with optional date filters; read-only |
| Users | Create cashier accounts, enable/disable cashiers, and reset passwords |
| Refunds | Review requests and manage payout status |
| Settings | Change your own password and theme |

Inventory delivery dates and the From/To filters in Inventory, Sales History, and Void History
use a **Calendar** button instead of typed dates. Each optional filter has a
**Clear** button; blank dates include all dates. Selecting or clearing a date
applies filters automatically; **Refresh** reloads on demand. Closing the calendar
or pressing Escape keeps the previous date.

Table filters apply automatically when dates or dropdowns change. Customer,
inventory, sales receipt, and refund receipt searches apply after a short typing
pause; Enter or **Refresh** reloads immediately.

Enter initial stock when creating a product. For later stock changes, use
**Inventory**. Receiving stock and adjustments record their movement history
together with the stock change. Adjustments cannot make stock negative.

### Refunds and payouts

1. In POS, select **Request Refund**, load a receipt, choose items and returned
   quantities, indicate opened/used items, and enter a reason. Submit within
   seven elapsed days of the sale; opened food cannot be refunded.
2. The owner opens **Refunds** to review pending requests. On approval, mark
   resellable lines to return their quantities to stock. Rejection requires a note.
3. Cashiers open **Refunds** to inspect shared statuses and owner decisions.
   Requesters receive persistent decision notices, refreshed every ten seconds;
   **View decisions** opens them, and **Refresh notices** retries a read.
4. After manually returning the full approved amount, use **Record payout**.
   Choose Cash or GCash, supply a GCash reference when applicable, and confirm
   that the money has already been returned.

Coordinate with staff before handing over money. The app prevents duplicate
payout records, but cannot prevent duplicate physical handovers. Partial payouts
and automatic payment reversals are not supported. Owners can correct recorded
payment details through **Status / payouts**, with a required reason and audit
history. Refunds marked assumed paid before tracking cannot be paid again.

### Account settings

Open **Settings** from the owner sidebar or from POS for either role.
Choose a theme and select **Apply theme** to save it to your account immediately.
Opening settings from POS preserves the cart, customer, and last receipt.

To change your password, enter the current password, the new password, and its
confirmation. Passwords must be nonblank and at most 72 UTF-8 bytes. If a cashier
forgets their password, the owner can reset it through **Users**. Log out to switch
accounts; hold a draft cart first if you need to keep it.

### Keyboard shortcuts

| Key | Action |
| --- | --- |
| **F2** | Focus product search in POS |
| **F4** | Hold the active cart |
| **F5** | Open payment |
| **F6** | Open the void dialog |
| **F8** | List held transactions |
| **Enter** | Edit the selected cart row when the cart has focus |
| **Delete** | Remove the selected cart row when the cart has focus |
| **Escape** | Close a dialog |

## Testing and code checks

Run commands from the project root with your virtual environment active.

**Full test suite**

```bash
python -m pytest
```

Tests use disposable SQLite databases and do not require a MySQL server or real
shop credentials. GUI tests use real Tk widgets and skip when no display is
available. A passing run with skips does not verify those GUI scenarios.

**GUI demo flow**

```bash
python -m pytest tests/test_demo_flow.py -q
```

This test exercises checkout, hold/resume across an app restart, voids, receipts,
refunds, inventory, reports, and accounts with a disposable file-backed database.
PDFs are generated, while external viewer launches are mocked. A display is
required; physical printer output remains a manual check.

**Headless Linux with Xvfb installed**

```bash
xvfb-run -a python -m pytest
xvfb-run -a python -m pytest tests/test_demo_flow.py -q
```

**Lint and formatting checks**

```bash
python -m ruff check .
python -m ruff format --check .
```

To apply formatting deliberately, run `python -m ruff format .`.
Foundation checks are also available through `python -m unittest discover -v`;
use pytest for the complete suite.

## Files and assets

| Path | Purpose |
| --- | --- |
| `.env` | Private local database settings; ignored by Git |
| `pawpos.log` | UTF-8 startup and diagnostic log; ignored by Git |
| `receipts/` | Generated receipt PDFs; ignored by Git |
| `assets/products/` | Product images copied into the project when saved |
| `assets/fonts/` | Bundled receipt font and its license |
| `assets/logo.png`, `assets/placeholder_product.png` | Bundled paw graphics |

To regenerate the bundled paw graphics, run:

```bash
python scripts/generate_assets.py
```

This replaces the logo and placeholder images. It is optional for normal setup.
Receipt PDFs use the bundled DejaVu Sans Mono font to display the peso sign.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Cannot connect to the database | Start MySQL; confirm the database exists, `.env` values are correct, and the configured user has access. Check for environment variables overriding `.env`. |
| Cannot initialize the database | Check the database user's table privileges and whether the existing schema needs a documented update. |
| Tkinter cannot be imported | Install Tk support for your Python version and retry `python -m tkinter`. |
| App cannot open / no display | Launch it in a graphical desktop session. For headless Linux tests, use Xvfb. |
| Receipt PDF does not open | Install/configure a default PDF viewer. On Linux, ensure `xdg-open` is available. Open the generated PDF from `receipts/` manually if needed. |
| Demo login does not work | Existing users prevent reseeding; an account may have a changed password or be disabled. Ask the owner to reset a cashier account. |

Startup diagnostics appear in the terminal and `pawpos.log`. If the log cannot
be written, console logging still works. Connection failures exit with status 1
and show a desktop error dialog when a display is available.

## Project documentation

- [Documentation guide](docs/README.md): entry point to the technical documentation.
- [Features](docs/FEATURES.md): current capabilities and acceptance criteria.
- [Business processes](docs/BUSINESS_PROCESS.md): shop workflows and rules.
- [Architecture](docs/ARCHITECTURE.md), [database](docs/DATABASE.md),
  [UI/UX](docs/UI_UX.md), and [technology stack](docs/TECH_STACK.md): technical references.
- [Contributor instructions](AGENTS.md) and [feature index](docs/features/INDEX.md):
  development workflow and feature tracking.
- [Changelog](CHANGELOG.md): project changes.
