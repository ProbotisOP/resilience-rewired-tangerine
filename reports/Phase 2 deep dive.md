# Phase 2 Deep Dive — Corrected Product and Evidence Specification

**Status:** Replaces the prior exploratory hypotheses and stale numerical claims.
**Project:** Resilience Rewired · Sheridan Datathon 2026 · CTRL + ALT + WIN

## Product direction

Resilience Rewired is a customer-controlled financial resilience simulator, not an underwriting or predictive-risk system. A judge can choose any of the 4,500 supplied account IDs and apply a challenge shock without leaving the active scenario.

The business value is a clear answer to:

1. What is the account's challenge-defined baseline?
2. How does a specified shock change buffer, monthly gap and Judge Match runway?
3. What monthly improvement is mathematically required to reach a user-selected survival duration?
4. How would a user-selected adjustment change the estimate?

The official result and optional adjustment model are displayed separately. No spending category is presumed discretionary.

## Data sources and coverage

All source files are expected in `tangerine/data`.

| File | Rows | Grain |
|---|---:|---|
| `accounts.csv` | 4,500 | Account |
| `clients.csv` | 5,369 | Client |
| `dispositions.csv` | 5,369 | Client-account role |
| `cards.csv` | 892 | Card linked to a disposition |
| `districts.csv` | 77 | District |
| `loans.csv` | 682 | Loan |
| `standing_orders.csv` | 6,471 | Undated payment instruction |
| `monthly_summary.csv` | 185,326 | Account-month |
| `transactions.csv` | 1,056,320 | Transaction |

Monthly and transaction records fall within 2020–2025. Account histories are not all the same length. `dispositions.type == 'authorized user'` describes account access and does not establish a personal relationship. Standing orders are an undated snapshot without a frequency field. Transaction rows do not provide reliable within-day ordering.

## Challenge-defined account metrics

For each account, sorted by month:

| Measure | Definition |
|---|---|
| I | Median `money_in` |
| F | Median of row-wise `household_bills + insurance + loan_payments` |
| S | Median `money_out` |
| B | Mean `avg_daily_balance` over the latest six chronological rows |
| H | Median `household_bills` |
| P | `monthly_payment` for status C or D; otherwise zero |

Portfolio medians are taken across 4,500 account-level values, not across all monthly rows.

| Measure | Current portfolio median |
|---|---:|
| I | $7,568.26 |
| S | $7,388.65 |
| F | $1,774.16 |
| H | $1,536.68 |
| B | $22,325.10 |
| Accounts with S > I | 1,181 / 4,500 |

`money_in` includes cash deposits, transfers, pensions and interest; it is not confirmed payroll. F is the requested challenge metric and may not represent every essential customer cost.

## Runway and optimizer

```text
buffer_left = B - one_off_costs
monthly_gap = spending_after_shock - income_after_shock
if buffer_left <= 0: runway = 0
elif monthly_gap <= 0: runway = 120+ (no shortfall)
else: runway = round(min(buffer_left / monthly_gap, 120), 1)
```

Portfolio threshold counts use the rounded one-decimal official runway before applying strict `<3`, `<6` and `<12` comparisons. This ensures the matrix, chart and account-level outputs use the same displayed formula.

For target duration `T > 0`, available buffer `B` and monthly gap `G`, the optimizer calculates:

```text
required_monthly_improvement = max(0, G - B / T)
```

An optional user-selected monthly adjustment changes the proposed gap and runway. It is not a spending recommendation or a claim that the amount can be saved.

## Supported evidence and limitations

- The income-decile chart is a deterministic 55% money-in simulation, not observed EI receipt or a forecast.
- The pre-loan analysis uses the latest six available monthly rows before loan start. It compares with the supplied default flag; status C/D outcomes may still be running.
- Authorized-user, statement-frequency, card, cash-deposit-share and leasing-order group differences are descriptive, unadjusted associations only.
- An external-destination loan-payment standing order is not confirmation of outstanding external debt.
- Penalty-fee causal or temporal claims are not made without verified sequencing.
- A 48–72-hour payday assertion is removed; no account-level date-sequence analysis supports it.
- Cash withdrawals are not classified as discretionary.
- Emergency targets require an explicit customer-confirmed essential cost when F is zero. Recent net cash flow is a six-row statistic, not a historical savings forecast.
- Snowflake is not connected to the application. SQL files are optional setup examples. Gemini, if configured, is limited to explanation and cannot modify calculations.

See [phase2_hidden_patterns_discovery.md](./phase2_hidden_patterns_discovery.md) for the item-by-item correction ledger and [README.md](../README.md) for setup, tests and the judging runbook.
