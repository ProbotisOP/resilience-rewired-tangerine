# overdraft_risk: 6-month overdraft-risk model
Estimates the chance that an account has at least one **overdraft event** in the 6 months after a chosen month.
An overdraft event is any of:
- `monthly_summary.csv`: `days_below_zero` > 0 in a month, or
- `monthly_summary.csv`: `min_balance` < 0 in a month, or
- `transactions.csv`: a row whose `purpose` is `penalty interest (negative balance)`.
 
The result is a percentage rounded to 2 decimals, for example `30.35%`. It is a statistical association from past
behaviour, not a credit decision, and it says nothing about the size or cause of a shortfall.
 
## Folder layout
 
```
overdraft_risk/
  __init__.py                  exports get_overdraft_risk, OverdraftRisk, format_probability
  service.py                   scoring service (numpy + pandas; no scikit-learn needed)
  ui.py                        Streamlit page "Overdraft risk"
  model/
    overdraft_risk_6m.json     saved model: features, scaling constants, weights, intercept
  training/
    __init__.py
    features.py                point-in-time feature builder used for training and tests
    train.py                   refits the model and rewrites model/overdraft_risk_6m.json
    evaluate.py                train / validation / test evaluation (AUC, AP, Brier, calibration)
  tests/
    __init__.py
    test_overdraft_risk.py     10 tests
```
 
## Using it
 
```python
from overdraft_risk import get_overdraft_risk
r = get_overdraft_risk(20111)               # as of the account's latest month
r.display                                   # '13.51%'
r.probability_pct                           # 13.51
r.as_of_month, r.horizon_months             # '2025-12', 6
r.features                                  # the 12 predictor values used
get_overdraft_risk(20111, as_of="2024-06")  # any month with at least 6 monthly rows of history
get_overdraft_risk(1)                       # None (unknown account_id)
```
 
With data to December 2025, the default result covers January to June 2026. Accounts whose last row is earlier
get a result for the 6 months after their own last month.
 
## The 12 predictors
 
All use data up to and including the as-of month. "6m" means the last 6 monthly rows.
 
| Predictor | Definition | Source columns | CSV |
|---|---|---|---|
| `log_buffer6` | ln(1 + mean `avg_daily_balance`, 6m), floored at 0 | `avg_daily_balance` | `monthly_summary.csv` |
| `buffer_months` | that buffer ÷ mean monthly `money_out` (cap 60) | `avg_daily_balance`, `money_out` | `monthly_summary.csv` |
| `min_bal_to_out` | lowest `min_balance` (6m) ÷ mean monthly `money_out` (clipped to -5..60) | `min_balance`, `money_out` | `monthly_summary.csv` |
| `log_mean_in` | ln(1 + mean `money_in`, 6m) | `money_in` | `monthly_summary.csv` |
| `cash_wd_share` | sum `cash_withdrawals_genuine` ÷ sum `money_out` (6m) | `cash_withdrawals_genuine`, `money_out` | `monthly_summary.csv` |
| `outflow_months_share` | fraction of the 6 months with `money_out` > `money_in` | `money_in`, `money_out` | `monthly_summary.csv` |
| `spend_trend` | ln(1 + mean `money_out`, last 3m) − ln(1 + mean `money_out`, previous 3m) | `money_out` | `monthly_summary.csv` |
| `loanpay_to_in` | sum `loan_payments` ÷ sum `money_in` (6m) | `loan_payments`, `money_in` | `monthly_summary.csv` |
| `so_to_in` | total standing-order `amount` ÷ mean monthly `money_in` (cap 5) | `amount` | `standing_orders.csv` (+ `money_in`) |
| `penalty_hist` | 1 if any penalty-interest charge up to the as-of month | `purpose` | `transactions.csv` |
| `neg_months_win` | months in the last 6 with `days_below_zero` > 0 or `min_balance` < 0 | `days_below_zero`, `min_balance` | `monthly_summary.csv` |
| `joint` | 1 if two different `client_id` share the `account_id` | `client_id`, `account_id` | `dispositions.csv` |
 
Missing values are replaced by the training median. `standing_orders.csv` and `dispositions.csv` are undated
snapshots, so `so_to_in` and `joint` always show the end-of-data state.
 
## How the model was built
 
- **Model:** ridge-regularised logistic regression (C = 1.0): standardise each predictor, take a weighted sum,
  pass it through `1 / (1 + e^-x)` to get a probability.
- **Rows:** one per account per cutoff month (June and December). Predictors use data up to the cutoff; the label is 1 if an
  overdraft event occurs in the 6 months after it. An account needs at least 6 monthly rows before the cutoff and
  6 observed months after it.
- **Evaluation split:**
 
  | Set | Cutoffs | Labels cover |
  |---|---|---|
  | Train | 2020-12 to 2023-06 | Jan 2021 – Dec 2023 |
  | Validation (choose C) | 2023-12, 2024-06 | Jan – Dec 2024 |
  | Test | 2024-12, 2025-06 | Jan – Dec 2025 |
 
- **Saved model:** refit on cutoffs 2020-12 to 2024-06 (labels to Dec 2024; 15,803 rows, 340 events). No 2025 data
  is in the weights.
- **Test accuracy (2025 labels, 8,541 rows, 234 events):** AUC 0.958 (95% CI 0.947–0.968), average precision 0.606,
  Brier 0.0159 versus 0.0267 for a constant, log loss 0.0655. Mean predicted 2.73% against 2.74% observed.
  Flagging the top 10% of rows captures 84.6% of events (precision 23.2%).
 
## Limits
 
- Overdrafts are rare (about 2.7% of rows in the test period), so the weights rest on few events.
- The label is a proxy for financial stress: it does not measure how large a shortfall would be.
- Predictions beyond the data assume future behaviour resembles 2021–2025.
- Coefficients are associations, not causes, and some hold only after controlling for the others (for example, higher
  `log_mean_in` raises risk once the buffer is held fixed).
- The same account can appear at several cutoffs. Holding out 30% of accounts entirely gave AUC 0.949.
 
## Setup
 
Inference and the Streamlit page need no new packages (pandas, numpy and streamlit are already in `requirements.txt`).
Training and evaluation also need `scikit-learn`.
 
```
pip install scikit-learn
python -m overdraft_risk.training.train       # rewrites overdraft_risk/model/overdraft_risk_6m.json
python -m overdraft_risk.training.evaluate    # prints the train / validation / test results
python -m pytest overdraft_risk/tests         # run the tests
```
 
## Adding the page to `app.py`
 
Add three lines (the import, a `PAGE_OPTIONS` entry at the end, and a slug), plus the routing branch:
 
```python
from overdraft_risk.ui import render_overdraft_risk            # with the other src.ui imports
PAGE_OPTIONS = [..., "⚠️ Overdraft risk"]                      # append at the end of the list
PAGE_SLUGS[PAGE_OPTIONS[7]] = "overdraft-risk"                 # or add PAGE_OPTIONS[7]: "overdraft-risk" to the dict
    elif page == "⚠️ Overdraft risk":                          # in main(), after the last elif
        render_overdraft_risk(repo)
```
 
`app_py_changes.patch` in the bundle contains the exact change (`git apply app_py_changes.patch`).
