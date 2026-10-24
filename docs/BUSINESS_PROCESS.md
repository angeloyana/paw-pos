# Business Process

## 1. Business context

- **Type:** Pet shop selling pet food (some sold loose by weight) and pet supplies (toys, accessories, etc.).
- **Size:** A single shop, one counter computer, one cashier at a time.
- **Payments:** Cash or GCash.
- **Tax/discounts:** None. Prices are final.

## 2. Roles

| Role        | Can do                                                                                                                                                                                                               |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cashier** | Log in/out, create sales, hold/resume transactions, void items or whole transactions (with reason), look up past sales by receipt number, submit/read refund requests and decisions, record full payouts, reprint receipts, add/select customers at checkout |
| **Owner**   | Everything the cashier can, plus: dashboard/reports, manage products, categories, inventory (receive stock, adjust stock, view movements), customers, sales history, approve/reject refunds, correct payout details with audit, manage cashier accounts |

Owner screens are only visible to the owner. The cashier sees only the POS screen.

## 3. Core sale flow

1. Customer picks products in the shop and brings them to the counter.
2. Cashier searches/clicks products and adds them to the cart.
   - **Per-piece item:** added with quantity 1 (editable).
   - **Per-kilo item:** a pop-up asks for the weight in kg (typed from the shop's scale). The computed price is shown before adding.
3. Cashier may edit quantities/weights or remove lines before payment.
4. Optional: attach a customer (search existing, or quick-add name + contact). Walk-ins can skip.
5. Cashier presses **Pay** and chooses the method:
   - **Cash:** enter amount received; the system shows change.
   - **GCash:** enter the reference number (stored as text, no verification).
6. System completes the sale: saves the sale, deducts stock, writes stock movements, generates the receipt number.
7. A **receipt preview** appears automatically with **Print** and **Close** buttons.
8. Customer leaves; the cart resets for the next customer.

## 4. Hold and resume

- The cashier can **Hold** the current cart (customer is still shopping). The cart is saved in the database with status `held`.
- Held transactions survive an app restart.
- **Resume** shows a list of held carts; picking one loads it back into the cart.
- Holding does **not** change stock. Stock is only deducted when the sale is completed.
- On completion, if stock is no longer enough for a line, block payment and tell the cashier which item.

## 5. Void (before payment)

- A **void** cancels a cart line or the entire transaction **before payment is completed**.
- The cashier can void **freely** (no owner approval) but **must enter a reason**.
- Every void is logged (who, what, qty, amount, reason, when).
- Voids never change stock (stock was never deducted).
- Voiding a held transaction removes the held sale/items and preserves each
  line, the actor, and the cancellation reason in `void_logs` atomically. The
  schema uses only `held` and `completed` sale statuses.

## 6. Refund (after payment)

A refund applies only to a **completed** sale.

**Flow**

1. Customer returns with the receipt. Cashier opens **Request Refund** and enters the **receipt number**.
2. Cashier selects the lines and quantities/weights to refund, marks if the item is **opened/used**, and enters a **reason**.
3. System validates the rules below and saves a **refund request** with status `pending`.
4. Later, the **owner** logs in separately, opens **Refunds**, and **approves or rejects** the request. There is **no on-the-spot approval** on the cashier screen.
5. On approval, the owner marks each refunded line **resellable: yes/no**.
   - Resellable = yes: stock is added back and a `refund` stock movement is recorded.
   - Resellable = no (damaged/opened): stock is not changed.
6. A cashier or owner returns the full approved amount manually, then records the payout method/reference, actor, and time (no payment integration).

**Rules (defaults, enforce in the service layer)**

- Refund must be requested **within 7 days** of the sale's completion.
- A **valid receipt number** is required.
- Items that are **opened/partially used** and belong to **food** are **not refundable**. A product is "food" when its category is flagged `is_food = true`.
- Total refunded quantity per sale line can never exceed the quantity sold (including earlier approved and pending requests).
- Refund amount per line = `unit_price` at time of sale x refunded quantity.

## 7. Inventory process

- **Receive stock:** the owner records a delivery (product, quantity, supplier note, date). Stock increases and a `stock_received` movement is logged.
- **Adjust stock:** the owner corrects stock for damage, loss, or counting mistakes (signed quantity, reason required). Logged as `adjustment`.
- **Sale:** stock decreases automatically; a `sale` movement is logged per line.
- **Refund (resellable):** stock increases; a `refund` movement is logged.
- **Low stock:** a product is "low" when `stock_quantity <= low_stock_threshold`.
  The owner dashboard alerts on active products in active categories, including
  zero stock. Inactive records remain available in Inventory. Cashiers do not
  receive low-stock alerts.
- **Out of stock:** products with stock 0 are shown in the POS grid but **disabled**.

## 8. Customers

- Fields: name, contact (phone/email as free text).
- Attaching a customer to a sale is **optional**.
- No loyalty points.

## 9. Reports (owner dashboard)

1. **Daily sales** (chart + total for today and number of transactions)
2. **Best-selling products** (chart, top 5 by quantity sold, selectable range: today / 7 days / 30 days)
3. **Low-stock list** (table)

Net sales count sales on their completion date and subtract approved refunds
on their review date. Pending/rejected requests do not reduce net sales.
Calendar ranges include today and zero-fill empty dates; refund-only days may
be negative. Best sellers rank gross quantities sold, without subtracting returns,
and label piece/kg units. Inactive products remain in historical sales rankings.

## 10. Accounts

- Owner creates cashier accounts, disables/enables them, and resets their passwords.
- Login is simulated: username + password checked against a bcrypt hash; the logged-in user is kept in memory. No tokens, no expiry, no auto-lock.
- Disabled users cannot log in.

### Refund payout records and decision notices

Active cashiers and owners can read all shop refund decisions, including other
shifts' requests. Only the requesting user receives a persistent decision notice.
Opening that decision acknowledges their notice, without acknowledging anyone
else's notices. Approval and rejection remain owner-only.

After handing over the full approved amount, a cashier or owner records Cash or
GCash (required reference, maximum 50 characters). No partial payouts or payment
integration are provided. Staff coordinate the physical handover manually; the
system prevents duplicate payment records, not simultaneous physical handovers.
Owners can correct method/reference with a required reason and preserved history;
this never reopens payment or changes the original actor/time. Existing approvals
at first tracking startup are assumed paid with payment details unknown, and
cannot be paid again or given invented details. Reports still deduct refunds on
the approval date, irrespective of payout status.
