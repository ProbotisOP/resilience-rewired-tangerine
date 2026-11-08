# Hidden Patterns: story dashboards

Guided, animated dashboards for `reports/phase2_hidden_patterns_discovery.md`.
Each one moves the chart one step at a time and explains what just changed.

## Open
Double-click `index.html`. It works offline because D3 is bundled in `lib/` and there is no server or build step.

| File | Story | Discoveries |
|---|---|---|
| `1_who_defaults.html` | 682 loans as dots, regrouped by household, card, cash share, statement habit, then warning-sign count | #1 #2 #4 #5 |
| `2_phantom_wealth.html` | Income deciles under the EI shock → runway, plus an interactive "race to zero" | #3 |
| `3_trap_doors.html` | Penalty spiral + timeline, leasing paradox, loan payments with no loan on record | #6 #7 #8 |
| `4_money_flow.html` | Day-of-month money flow, spending breakdown, adaptive-runway what-if | #9 #10 |
| `5_default_forecaster.html` | Random-forest default model: held-out accuracy, feature importance, cash-share what-if curves, and a borrower picker with a live slider | model |

Controls: **Next / Back**, the ← → keys, **Space** to autoplay, and hover for tooltips. Every chart has a table view.
`#3` at the end of a URL opens that step. `?still` turns animation off (useful for screenshots).

## Rebuild the data
```
python Dashboards/prep/build_data.py            # defaults to ../Tangerine next to the repo
python Dashboards/prep/build_data.py path/to/csvs
```
This writes `data/data.js`. Every number shown comes from that file.

## Rebuild the forecaster model (page 5)
```
pip install scikit-learn
python Dashboards/prep/build_model.py            # same default data path as above
```
This writes `data/model.js` (~380 KB) and prints the held-out metrics. It takes about a minute.
- **Features:** 17 per loan, all computed from months **before** the loan started. Post-loan overdrafts and penalties would leak the outcome.
- **Model:** 300 trees with class weights to balance the rare defaults.
- **Scores:** accuracy, the confusion matrix and permutation importance all come from 5-fold cross-validation.
- **What-if curves:** these come from a forest refit on all loans. Cash share is varied on a grid that is fine near 0% and above 95%, because that's where real borrowers sit and where the forest splits.

## Where numbers differ from the report
These are listed on the index page. In short:
- **#3:** buffer-based figures differ slightly.
- **#5:** the quartile table did not reproduce, though the direction holds and the real gradient is steeper.
- **#7:** "competitor bank" can't be proven from the bank codes.
- **#8 / #9:** the local `transactions.csv` stops on 2025-03-31, so counts are lower. Cash withdrawals are flat across the month.
