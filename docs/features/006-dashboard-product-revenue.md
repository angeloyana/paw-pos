# 006: Dashboard Top 5 Products by Net Revenue

**Status:** in progress

**Touches:** `docs/FEATURES.md`, `docs/BUSINESS_PROCESS.md`, `docs/UI_UX.md`, `docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`

## Summary

Rank the owner dashboard's Top 5 Products by net revenue instead of quantity.
Deduct approved refunds on their approval date, matching daily net sales.

## Requirements

- Net revenue is recorded completed-sale line totals minus approved refund-item
  amounts. Sales use completion dates; refunds use approval dates, including
  refunds for older sales. Pending/rejected refunds and payout dates have no effect.
- Preserve Today / 7 days / 30 days, defaulting to 7 days.
- Rank descending before limiting to five; retain product/unit grouping, current
  names, inactive history, and stable name/ID/unit ties.
- Include products with sales or approved refunds in the range, including zero
  and negative results. Do not clamp negative revenue.
- Title: **Top 5 products by net revenue**. Bar widths use revenue; axis and exact
  value labels use pesos/centavos. Negative bars and labels remain readable.
- Retain existing BestSeller fields and add Decimal-valued net_revenue.
- No database changes or dependencies.

## Tasks

1. Create a feature branch and register this spec as in progress.
2. Aggregate sales and refunds separately in best_sellers, combine, rank and limit;
   add service regression coverage and update related docs.
3. Update the dashboard/chart, add UI coverage and update related docs/changelog.
4. Verify acceptance checks, full tests, Ruff checks and the app; close out and commit.

## Done when

- [ ] Lower-quantity, higher-revenue products rank first.
- [ ] Partial/multiple approved refunds deduct once; pending/rejected refunds do not.
- [ ] Old sales refunded today reduce today's product revenue.
- [ ] Boundaries, ranges, limit, ties, inactive history and owner authorization pass.
- [ ] Fractional-kg sales use recorded money and retain Decimal precision.
- [ ] Empty, zero, negative and refund-only results render with currency labels.
- [ ] Refresh, ranges, theme redraws and canvas reuse pass.
- [ ] Full tests, Ruff checks and app verification pass; docs and commits are complete.

## Remaining work

Implement and verify the tasks above.
