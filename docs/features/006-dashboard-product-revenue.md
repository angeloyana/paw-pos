# 006: Dashboard Top 5 Products by Net Revenue

**Status:** done

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

- [x] Lower-quantity, higher-revenue products rank first.
- [x] Partial/multiple approved refunds deduct once; pending/rejected refunds do not.
- [x] Old sales refunded today reduce today's product revenue.
- [x] Boundaries, ranges, limit, ties, inactive history and owner authorization pass.
- [x] Fractional-kg sales use recorded money and retain Decimal precision.
- [x] Empty, zero, negative and refund-only results render with currency labels.
- [x] Refresh, ranges, theme redraws and canvas reuse pass.
- [x] Full tests, Ruff checks and app verification pass; docs and commits are complete.

## Remaining work

None.

## Verification

- Focused report/dashboard tests: 35 passed.
- Full pytest suite: 543 passed and 26 subtests passed. Used a fresh permitted
  `--basetemp` directory because sandbox default temp-directory creation failed.
- `python -m ruff check .` and `python -m ruff format --check .`: passed.
- App smoke against disposable seeded SQLite: owner login, 1280x720 dashboard,
  positive/zero/negative currency bars, dark theme and desktop event loop passed.
  Rendered chart visually checked for readable labels.
- Report query compiles for MySQL; no live shop data was changed.
