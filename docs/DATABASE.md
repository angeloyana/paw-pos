# Database Schema (MySQL via SQLAlchemy 2.x)

Conventions: table names plural snake_case; integer auto-increment `id` primary keys; money = `Numeric(10,2)`; quantities = `Numeric(10,3)`; timestamps = `DateTime` (local time). Engine: InnoDB, charset `utf8mb4`.

## users

All fifteen tables are registered by `pawpos.models` and created by `init_db()`.
Named checks reject negative product prices, stock, thresholds, sale/refund
amounts, and movement balances; sale/refund item quantities must be positive.
Enums are checked in SQLite tests as well as MySQL. The declared indexes cover
product names and stock-movement product/date lookups; usernames, category
names, and receipt numbers are unique. Category `is_active` implements the
project-wide soft-deletion rule. No migrations are used.

| Column        | Type                    | Notes            |
| ------------- | ----------------------- | ---------------- |
| id            | int PK                  |                  |
| username      | varchar(50)             | unique, not null |
| full_name     | varchar(100)            | not null         |
| password_hash | varchar(100)            | bcrypt           |
| role          | enum('owner','cashier') | not null         |
| is_active     | bool                    | default true     |
| created_at    | datetime                | default now      |

## user_settings

Account theme preferences, created automatically by `init_db()`. Existing tables
need no ALTER SQL. Missing settings use `cosmo`; rows are created on first save,
and repeat seed runs preserve all preferences.

| Column | Type | Notes |
| --- | --- | --- |
| user_id | int PK, FK users.id | One preference per account |
| theme | varchar(100) | Required built-in ttkbootstrap theme name |

## categories

| Column      | Type         | Notes                                                 |
| ----------- | ------------ | ----------------------------------------------------- |
| id          | int PK       |                                                       |
| name        | varchar(80)  | unique, not null                                      |
| description | varchar(255) | nullable                                              |
| is_food     | bool         | default false; used for the refund "opened food" rule |
| is_active   | bool         | default true; soft deletion preserves category history |

## products

| Column                  | Type               | Notes                           |
| ----------------------- | ------------------ | ------------------------------- |
| id                      | int PK             |                                 |
| name                    | varchar(120)       | not null, indexed               |
| category_id             | FK categories.id   | not null                        |
| unit_price              | Numeric(10,2)      | price per piece or per kg; >= 0 |
| unit_type               | enum('piece','kg') | not null                        |
| stock_quantity          | Numeric(10,3)      | default 0; >= 0                 |
| low_stock_threshold     | Numeric(10,3)      | default 0                       |
| supplier                | varchar(120)       | nullable, plain text            |
| image_path              | varchar(255)       | nullable, relative path         |
| is_active               | bool               | default true                    |
| created_at / updated_at | datetime           |                                 |

## customers

| Column     | Type         | Notes    |
| ---------- | ------------ | -------- |
| id         | int PK       |          |
| name       | varchar(120) | not null |
| contact    | varchar(120) | nullable |
| created_at | datetime     |          |

## sales

Holds completed sales and held carts. Resuming removes the held sale/items;
cancelling also removes them while retaining their item snapshots and reason in
`void_logs`. Neither operation changes stock. No `voided` status is stored.
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| receipt_number | varchar(30) | unique, nullable (null while held). Format `PAW-YYYYMMDD-0001`, sequence resets daily |
| status | enum('held','completed') | |
| cashier_id | FK users.id | not null |
| customer_id | FK customers.id | nullable |
| total | Numeric(10,2) | |
| payment_method | enum('cash','gcash') | nullable while held |
| amount_received | Numeric(10,2) | cash only |
| change_amount | Numeric(10,2) | cash only |
| gcash_reference | varchar(50) | gcash only |
| created_at | datetime | when first held/created |
| completed_at | datetime | nullable |

## sale_items

| Column       | Type               | Notes                             |
| ------------ | ------------------ | --------------------------------- |
| id           | int PK             |                                   |
| sale_id      | FK sales.id        | on delete cascade                 |
| product_id   | FK products.id     | not null                          |
| product_name | varchar(120)       | snapshot                          |
| unit_type    | enum('piece','kg') | snapshot                          |
| quantity     | Numeric(10,3)      | > 0                               |
| unit_price   | Numeric(10,2)      | snapshot                          |
| line_total   | Numeric(10,2)      | = round(quantity x unit_price, 2) |

## void_logs

| Column       | Type                       | Notes              |
| ------------ | -------------------------- | ------------------ |
| id           | int PK                     |                    |
| user_id      | FK users.id                | who voided         |
| product_id   | FK products.id             | nullable           |
| product_name | varchar(120)               | snapshot           |
| quantity     | Numeric(10,3)              |                    |
| amount       | Numeric(10,2)              | line amount voided |
| void_scope   | enum('line','transaction') |                    |
| reason       | varchar(255)               | required           |
| created_at   | datetime                   |                    |

## stock_movements

Append-only history. **Never update or delete rows.**
| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| product_id | FK products.id | indexed |
| movement_type | enum('stock_received','sale','refund','adjustment') | |
| quantity_change | Numeric(10,3) | signed (+ in, - out) |
| stock_after | Numeric(10,3) | stock after this movement |
| reference_type | varchar(20) | 'sale', 'refund', or null |
| reference_id | int | nullable |
| user_id | FK users.id | |
| note | varchar(255) | nullable (required for adjustments; holds supplier for received) |
| created_at | datetime | indexed |

## refund_requests

| Column       | Type                                  | Notes           |
| ------------ | ------------------------------------- | --------------- |
| id           | int PK                                |                 |
| sale_id      | FK sales.id                           | not null        |
| status       | enum('pending','approved','rejected') | default pending |
| reason       | varchar(255)                          | required        |
| requested_by | FK users.id                           |                 |
| requested_at | datetime                              |                 |
| reviewed_by  | FK users.id                           | nullable        |
| reviewed_at  | datetime                              | nullable        |
| review_note  | varchar(255)                          | nullable        |
| total_amount | Numeric(10,2)                         | sum of items    |

## refund_items

| Column            | Type                  | Notes                                |
| ----------------- | --------------------- | ------------------------------------ |
| id                | int PK                |                                      |
| refund_request_id | FK refund_requests.id | cascade                              |
| sale_item_id      | FK sale_items.id      |                                      |
| quantity          | Numeric(10,3)         | > 0, within remaining refundable qty |
| amount            | Numeric(10,2)         | unit_price x quantity                |
| is_opened         | bool                  | set by cashier                       |
| resellable        | bool                  | nullable; set by owner on approval   |

## Relationships

- Category 1-N Product; Product 1-N SaleItem and StockMovement
- User 1-N Sale (cashier), StockMovement, VoidLog, RefundRequest
- Customer 1-N Sale (optional)
- Sale 1-N SaleItem; Sale 1-N RefundRequest; RefundRequest 1-N RefundItem

## Derived values (compute in services, don't store)

- **Net sales** = sum of sale totals by completion date - sum of approved refund
  totals by review date. Refund-only days may be negative.
- **Remaining refundable qty of a sale item** = sale item qty - sum of refund item qty from `pending` + `approved` requests.
- **Low stock** = `stock_quantity <= low_stock_threshold`.

## Seed data (`db/seed.py`, only when `users` is empty)

**Users:** `owner` / `owner123` (role owner, "Shop Owner"); `cashier` / `cashier123` (role cashier, "Cashier One").

**Categories:** Dog Food (`is_food`), Cat Food (`is_food`), Fish and Bird Food (`is_food`), Treats (`is_food`), Toys, Accessories, Grooming, Health and Care.

**Sample products (about 14):**
| Name | Category | Type | Price | Stock | Threshold |
|------|----------|------|-------|-------|-----------|
| Dog Food Loose (Adult) | Dog Food | kg | 95.00 | 50.000 | 10 |
| Cat Food Loose (Tuna) | Cat Food | kg | 120.00 | 40.000 | 10 |
| Pedigree Adult 1.5kg Pack | Dog Food | piece | 285.00 | 20 | 5 |
| Whiskas Pouch 85g | Cat Food | piece | 28.00 | 60 | 15 |
| Fish Flakes 50g | Fish and Bird Food | piece | 45.00 | 25 | 5 |
| Bird Seed Mix | Fish and Bird Food | kg | 80.00 | 15.000 | 5 |
| Dog Biscuit Treats | Treats | piece | 65.00 | 30 | 8 |
| Rubber Chew Toy | Toys | piece | 150.00 | 12 | 3 |
| Cat Feather Wand | Toys | piece | 85.00 | 3 | 5 |
| Nylon Dog Collar (M) | Accessories | piece | 120.00 | 18 | 5 |
| Dog Leash 1.2m | Accessories | piece | 180.00 | 10 | 3 |
| Pet Shampoo 250ml | Grooming | piece | 210.00 | 14 | 4 |
| Flea and Tick Spray | Health and Care | piece | 260.00 | 0 | 3 |
| Stainless Food Bowl | Accessories | piece | 95.00 | 22 | 5 |

Each seeded product with stock > 0 gets an initial `stock_received` movement (note "Initial stock"). Leave a couple low or at zero on purpose so the dashboard and disabled cards can be demonstrated.

## Refund tracking (feature 001)

Four additional tables are created automatically; existing tables need no ALTER
SQL. `seed_database()` also performs an atomic one-time initialization before
login, even when users already exist. It inserts legacy assumed-paid records for
existing approved refunds and an initialization marker together. Later startups
never backfill new approvals. No notices are backfilled and no shop data is reset.

| Table | Columns and constraints |
| --- | --- |
| `refund_payouts` | Integer PK; unique required `refund_request_id` FK; required `legacy_assumed_paid` boolean; nullable method (cash/gcash), reference varchar(50), `paid_by` user FK, `paid_at` datetime. Check requires either a legacy record with all payment details NULL or a real payment with actor/time, cash with NULL reference, or GCash with nonblank reference. Amount derives from the approved request. |
| `refund_payout_corrections` | Integer PK; indexed payout FK; required old/new methods, nullable old/new references varchar(50), required reason varchar(255), correcting user FK, local correction time. Append-only history; original payout actor/time are retained. |
| `refund_decision_notices` | Integer PK; unique required refund FK; indexed recipient user FK; local creation time; nullable read time. Approval/rejection inserts the notice in its review transaction. |
| `refund_tracking_state` | Singleton integer PK constrained to 1; local initialization time. Commits with legacy records. |

Payout writes never change request approval status, stock, or report dates. A
unique payout per request prevents duplicate records, including competing saves.
Legacy records contain no fabricated payment method, reference, actor, or time.
