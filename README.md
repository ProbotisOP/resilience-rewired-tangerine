# Resilience Rewired

**CTRL + ALT + WIN · Sheridan Datathon 2026 · Tangerine track**

Resilience Rewired is a deterministic financial-resilience decision-support app. It calculates account-level baselines from the supplied banking records, applies transparent financial shocks, and lets a user test monthly adjustments against a selected survival period. It is not underwriting, financial advice, or a prediction of an individual customer's future.

## Business idea

Position Resilience Rewired as a **bank-embedded financial-wellness tool** for customer conversations: when a customer or advisor selects a disruption, the product shows the challenge-defined liquidity gap, available buffer and the monthly improvement required for a chosen survival period. Customers control the assumptions and can compare a proposed adjustment without the product deciding which spending is discretionary.

The near-term value proposition to validate with a bank is clearer, more explainable stress-planning conversations—not a promised reduction in defaults or a credit decision. A bank-licensed digital/advisor module is a candidate delivery model, not validated revenue evidence.

The interface supports live portfolio-level what-ifs, selectable account-history windows,
and month-by-month scenario playback. Results update from deterministic calculations as the
user changes assumptions; the playful narration is presentation only and does not change the
financial logic.

## Setup and data

Use Python 3.11 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The app expects all nine source files in `tangerine\data`:

`accounts.csv`, `cards.csv`, `clients.csv`, `dispositions.csv`, `districts.csv`, `loans.csv`, `monthly_summary.csv`, `standing_orders.csv`, and `transactions.csv`.

The configured data directory is checked at startup. If required files are missing, the app reports the missing filenames rather than silently using partial data. `transactions.csv` is read only by transaction-level analysis; the live account experience uses monthly summaries and relational tables.

## Verified calculation conventions

For each account, the app uses median money-in (I), median row-wise fixed costs (F), median spending (S), median household bills (H), and the mean of the latest six chronological `avg_daily_balance` rows (B). P is the supplied loan payment only for a loan with status C or D. Money-in is not verified employment income.

Portfolio medians are medians across the 4,500 calculated account-level metrics:

| Metric | Current result |
|---|---:|
| Median I | $7,568.26 |
| Median S | $7,388.65 |
| Median F | $1,774.16 |
| Median H | $1,536.68 |
| Median B | $22,325.10 |
| Accounts where median S > median I | 1,181 / 4,500 |

These are account-level medians, not medians over all monthly rows. The shared implementation is in `src/services/baseline_metrics.py`; portfolio, discovery and account-level views use its outputs.

The Judge Match Runway uses:

```text
buffer_left = B - one_off_costs
monthly_gap = spending_after_shock - income_after_shock
if buffer_left <= 0: runway = 0
elif monthly_gap <= 0: runway = 120+ (no shortfall)
else: runway = round(min(buffer_left / monthly_gap, 120), 1)
```

Portfolio threshold counts compare the **one-decimal official runway** to strict thresholds (`<3`, `<6`, `<12`). This avoids mixing unrounded ratio counts with displayed Judge Match values. The portfolio matrix and income-decile chart are calculated from the current CSV data at runtime.

## Discoveries and limitations

- **Money-in-group runway is a simulated result:** the 55% scenario applies to recorded money-in, not verified employment income or confirmed EI eligibility.
- **Pre-loan buffer and recorded loan outcomes are an association** in a subset with six available pre-start monthly rows. It is not causal evidence; running loans may not have completed outcomes.
- **Authorized-user account association** does not establish a spouse, partner, household or co-borrower.
- Statement frequency, card records, cash-deposit share and leasing-labelled standing orders are descriptive attributes. They do not prove causes, income quality, contracts or monthly obligations.
- External-destination loan-payment standing orders are payment instructions, not proof of confirmed outstanding external debt.
- Penalty fees are not claimed to cause or precede default without verified sequencing. No 48–72-hour payday assertion is used. Cash withdrawals are not classified as discretionary.
- Account histories vary in length. The latest six monthly rows define B and recent net cash flow; standing orders are an undated snapshot.

## Data and calculation validation

Run the complete tests, compile the Python files and reproduce current discoveries:

```powershell
python -m compileall -q app.py config src tests
python -m pytest
python src/discovery/run_discoveries.py
```

The raw-CSV discovery tests independently calculate account metrics, scenario thresholds, income deciles and pre-loan cohorts. The account-ID integrity test confirms that all 4,500 supplied IDs have monthly history and are represented in the shared account-metric output.

## Integrations

- **Local CSV repository is the live data source. Snowflake is not connected by the application.** Files in `sql` are optional Snowflake setup examples and must be run/configured separately; they do not represent a live repository adapter or a Cortex Semantic View.
- **Gemini is optional.** Without `GEMINI_API_KEY`, deterministic explanations are shown. When configured, Gemini receives aggregate verified metrics for language assistance only; Python calculations remain authoritative. Gemini cannot answer questions unsupported by the loaded metrics.

## Five-minute judging runbook

| Time | Demo |
|---|---|
| **0:00–0:45** | Open **Portfolio snapshot**. Explain the product: a transparent account what-if plus a resilience-gap calculation. Expand “Where these portfolio numbers come from” and explain that money-in is not verified payroll. |
| **0:45–1:30** | Open **What the data shows** → **Income what-if**. Tell the simple story: the same simulated 55% money-in change produces different runways across groups because buffers and spending also differ. State the group size; clarify this is a simulation, not observed job-loss evidence. |
| **1:30–3:30** | Open **Try a what-if**. Select any account from the supplied ID list without leaving the scenario. Choose “Income takes a dip,” adjust assumptions, and play the live month-by-month buffer timeline. Point out that the playful narration does not change the deterministic calculation. |
| **3:30–4:30** | Change the optional adjustment and compare the current vs. adjusted buffer paths. Open **Build a resilience plan** to show the target duration, required monthly improvement and calculation receipt. Make clear any contribution or expense estimate is user-selected. |
| **4:30–5:00** | Open the pre-loan discovery. State the eligible sample, six available pre-start rows and supplied outcome limitations. Explain that this may motivate a customer-controlled conversation, not causal inference or automated credit decisions. Snowflake is optional setup; Gemini cannot alter calculations. |

## Repository map

- `src/services/baseline_metrics.py` — shared account and portfolio calculations.
- `src/services/shock_engine.py` — deterministic Judge Match formula and optional selected-adjustment scenario.
- `src/services/recovery_planner.py` — recent net-cash-flow goal, gap optimizer and options to investigate.
- `src/services/discovery_engine.py` — dynamic portfolio, decile and pre-loan outputs.
- `src/data/local_repository.py` — local CSV loading and account lookups.
- `src/ui/` — Streamlit pages.
- `sql/` — optional Snowflake setup scripts, not used by the app.
