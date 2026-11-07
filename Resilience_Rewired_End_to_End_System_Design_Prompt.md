# Resilience Rewired — Current System Specification

**Sheridan Datathon 2026 · Tangerine track · CTRL + ALT + WIN**

This specification supersedes the earlier exploratory build prompt and its unsupported discovery claims. The current judging runbook and setup instructions are in [README.md](./README.md); the corrected evidence ledger is in [reports/phase2_hidden_patterns_discovery.md](./reports/phase2_hidden_patterns_discovery.md).

## Product and business proposition

Build a bank-embedded financial-wellness decision-support tool for customer/advisor conversations. The user selects an account, applies a transparent shock, and sees the official runway plus the monthly improvement required to reach a selected survival duration. The candidate business value is more concrete stress-planning; reduced defaults, revenue lift and causal customer effects are not demonstrated.

The app must not become an automated underwriting/rejection system. Customers control the essential-cost and adjustment assumptions. No spending category is presumed discretionary.

## Required capabilities

1. Select any of the 4,500 supplied account IDs and calculate I/F/S/B/H/P.
2. Select an official or custom income, bill or one-off shock.
3. Keep the Judge Match Runway visibly separate from optional selected-adjustment scenarios.
4. Project monthly cash flow for `scenario.duration_months`.
5. Show current monthly shock gap, available buffer, target survival duration, required monthly improvement, the selected adjustment, proposed gap and runway.
6. Make emergency-fund assumptions visible. Use recent six-row median net cash flow as a labelled statistic; do not call it forecast savings.
7. When F is zero, require an entered essential-cost estimate rather than inventing one.
8. Describe lender/lease changes as options to investigate, not guaranteed programs.
9. Keep the advisor grounded in verified service outputs and explain when the data cannot answer.

## Source data and relationships

Expected files are `accounts.csv`, `cards.csv`, `clients.csv`, `dispositions.csv`, `districts.csv`, `loans.csv`, `monthly_summary.csv`, `standing_orders.csv` and `transactions.csv` under `tangerine/data`.

Use `account_id` to connect account-level records. `dispositions.csv` links clients and accounts; use the owner disposition for the primary profile. An authorized user is an account-access role, not proof of a spouse, partner, household member or co-borrower. Aggregate one-to-many tables before joining.

Data caveats:

- Recorded money-in includes cash deposits, transfers, pensions and interest; it is not confirmed employment income.
- Standing orders are an undated snapshot without frequency or start date. Do not treat amounts as monthly commitments or add them to observed outflows.
- The transaction ledger and monthly summary represent the same underlying activity; do not sum them together.
- Same-day transaction row ordering is not reliable. Do not infer intraday or 48–72-hour sequences.
- Cash withdrawals are not necessarily discretionary.
- Loan status C/D may still be running; the `defaulted` flag does not make all other loans completed successful outcomes.

## Deterministic definitions

Sort each account's monthly rows by month:

| Metric | Definition |
|---|---|
| I | Median `money_in` |
| F | Median of row-wise `household_bills + insurance + loan_payments` |
| S | Median `money_out` |
| B | Mean `avg_daily_balance` over the latest six chronological rows |
| H | Median `household_bills` |
| P | `monthly_payment` if loan status is C or D; otherwise zero |

```text
buffer_left = B - one_off_costs
monthly_gap = spending_after_shock - income_after_shock
if buffer_left <= 0: runway = 0
elif monthly_gap <= 0: runway = 120+ (no shortfall)
else: runway = round(min(buffer_left / monthly_gap, 120), 1)
```

Portfolio metrics are medians across account-level metrics. Threshold counts compare the one-decimal official result using strict `<3`, `<6` and `<12` boundaries. A 6.0-month result is not below six months.

For target duration `T > 0`, buffer `B` and monthly gap `G`:

```text
required_monthly_improvement = max(0, G - B / T)
```

An adjustment is a user-entered simulation, not a recommendation or a verified saving.

## Evidence standards

- Income-decile runway is a simulated 55% money-in scenario, not an observed layoff or forecast.
- Pre-loan analysis reports the supplied default flag by the latest six available pre-start monthly rows. It is an association; no causal claim is allowed.
- Authorized-user, statement, card, cash-deposit and leasing-group differences are descriptive and unadjusted.
- External-destination loan-payment standing orders are instructions, not proof of external debt.
- Remove unsupported causal and timing claims, including penalty-fee causation, payday evaporation and cash-withdrawal discretion.
- Every discovery used in a presentation needs sample size, denominator, observation window and limitations.

## Architecture and validation

- `src/services/baseline_metrics.py` is the shared source for account and portfolio calculations.
- `src/services/shock_engine.py` applies the challenge formula and separate selected-adjustment calculation.
- `src/services/recovery_planner.py` builds the reserve goal and deterministic gap optimizer.
- `src/services/discovery_engine.py` calculates portfolio tables dynamically from local data.
- `src/data/local_repository.py` loads the nine-file local dataset and resolves account context.
- Streamlit pages are in `src/ui`; the app is launched with `streamlit run app.py`.

Required checks:

```powershell
python -m compileall -q app.py config src tests
python -m pytest
python src/discovery/run_discoveries.py
```

The application currently queries local CSV files only. Snowflake scripts are optional setup examples; no Snowflake adapter or Cortex Semantic View is connected. Gemini is an optional language layer and cannot modify calculations.
