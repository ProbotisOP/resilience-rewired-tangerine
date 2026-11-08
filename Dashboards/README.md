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

Controls: **Next / Back**, the ← → keys, **Space** to autoplay, and hover for tooltips. Every chart has a table view.
`#3` at the end of a URL opens that step. `?still` turns animation off (useful for screenshots).

## Rebuild the data
```
python Dashboards/prep/build_data.py            # defaults to ../Tangerine next to the repo
python Dashboards/prep/build_data.py path/to/csvs
```
This writes `data/data.js`. Every number shown comes from that file.

## Where numbers differ from the report
These are listed on the index page. In short:
- **#3:** buffer-based figures differ slightly.
- **#5:** the quartile table did not reproduce, though the direction holds and the real gradient is steeper.
- **#7:** "competitor bank" can't be proven from the bank codes.
- **#8 / #9:** the local `transactions.csv` stops on 2025-03-31, so counts are lower. Cash withdrawals are flat across the month.
