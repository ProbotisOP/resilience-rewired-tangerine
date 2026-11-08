# Resilience Rewired

**CTRL + ALT + WIN · Sheridan Datathon 2026 · Tangerine track**

Resilience Rewired is a financial-resilience copilot for a bank, built natively on Snowflake. It answers one question for
every customer: **if money in drops tomorrow, how many months can they last, and what would it take to get back to
safety?** It combines the challenge's deterministic runway formula with Snowflake ML, Cortex AI and an interactive
Streamlit in Snowflake app.

It is decision support for customer conversations, not underwriting, financial advice or a prediction of an individual
customer's future.

## What it does

| Section | Page | What it shows |
|---|---|---|
| The story | **Portfolio snapshot** | Portfolio KPIs, the money-in vs buffer map, a money-in × bills stress heatmap and runway by income decile. |
| | **Hidden patterns** | Ten findings in two acts: what the data shows (01–06) and what the ML found (07–10), each with the metric a bank would track and a Monday-morning action. |
| Customer | **Customer case** | One account's 360 view: baseline, balance history, ML stress tier, anomalies and the story behind them. |
| | **Live twist solver** | Pick a shock from example cards (each shows that account's runway), fine-tune it and play the buffer month by month. |
| | **Recovery plan & brief** | Target survival period, the monthly improvement needed and an advisor-ready brief. |
| AI assistant | **Ask TANG** | Cortex Agent over the semantic view and documentation search: plain-English questions, answered from the data. |
| Proof | **Evidence & model** | Discovery evidence, stress model results, calibration and parity checks. |
| | **How we calculate** | Formulas, definitions and limitations. |
| Models | **Overdraft risk (6 months)** | Chance of at least one overdraft event in the next 6 months for an account ([details](overdraft_risk/README.md)). |

## Architecture

```
tangerine/data/*.csv  ──PUT/COPY──►  RAW  ──►  CURATED (dims, facts, 9 DQ checks)
                                               │
                    ┌──────────────────────────┼─────────────────────────────┐
                    ▼                          ▼                             ▼
            MART (baseline, runways,     FEATURES (point-in-time     ML (XGBoost stress model,
            FN_ACCOUNT_SHOCK, 360)       account-month features)     ANOMALY_DETECTION, FORECAST
                    │                                                 backtest, TOP_INSIGHTS)
                    └──────────────► MART.ACCOUNT_RESILIENCE_360 ◄────────────┘
                                               │
              SEMANTIC (semantic view, Cortex Agent "TANG")  ·  OPS (Cortex Search over docs, audit)
                                               │
                              APP: Streamlit in Snowflake (container runtime)
```

Everything lives in database `RESILIENCE_REWIRED_DB`, runs on warehouse `RR_WH` and is read by role `RR_APP_ROLE`.

| Layer | Snowflake features used |
|---|---|
| Ingest | Internal stage, file format, `COPY INTO` with `METADATA$FILENAME`, load audit table |
| Model | Curated star schema, data-quality results table, SQL UDFs (`FN_SIMULATE_SHOCK`, `FN_ACCOUNT_SHOCK`) |
| ML | Snowpark Python stored procedure training XGBoost, Model Registry (`STRESS_XGB`), `SNOWFLAKE.ML.ANOMALY_DETECTION`, `SNOWFLAKE.ML.FORECAST`, `SNOWFLAKE.ML.TOP_INSIGHTS` |
| AI | Semantic view, Cortex Search service, Cortex Agent, `AI_COMPLETE` |
| App | Streamlit in Snowflake on the container runtime, ECharts visuals, Snowflake session (no stored credentials) |

## Key results

**Challenge baseline** (account-level medians over 4,500 accounts):

| Metric | Result |
|---|---:|
| Median money in (I) | \$7,568.26 |
| Median spending (S) | \$7,388.65 |
| Median fixed costs (F) | \$1,774.16 |
| Median household bills (H) | \$1,536.68 |
| Median buffer (B) | \$22,325.10 |
| Accounts where median S > median I | 1,181 / 4,500 |

**Stress model** (3-month stress label, test year 2025, 39,628 account-months, 708 positives):

| Model | PR-AUC | ROC-AUC | Brier | Recall at top 5% |
|---|---:|---:|---:|---:|
| Majority class | 0.018 | 0.500 | 0.0176 | 5.2% |
| Rule-based heuristic | 0.349 | 0.827 | 0.0133 | 68.5% |
| Logistic regression (calibrated) | 0.601 | 0.963 | 0.0102 | 76.6% |
| **XGBoost (calibrated)** | **0.642** | **0.977** | **0.0096** | **83.6%** |

**Overdraft risk model** (6-month horizon, 2025 test labels): AUC 0.958, average precision 0.606.

**Highlights from Hidden patterns**

- **Penalty interest before the loan:** 26 of 29 defaulted loans had penalty interest *before* the loan started.
- **The wealth illusion:** 175 top-decile earners who spend 90–100% of money in still show 6+ months of runway today;
  the 55% money-in shock shows how quickly that disappears.
- **Forecast honesty:** the `FORECAST` backtest did not beat a "balance stays flat" baseline, so the app shows no
  balance projections. `ML.ACCOUNT_BALANCE_FORECAST` is empty on purpose.

Full write-ups are in [`reports/phase2_hidden_patterns_discovery.md`](reports/phase2_hidden_patterns_discovery.md) and
[`reports/SNOWFLAKE_HACKATHON_DELIVERABLE.md`](reports/SNOWFLAKE_HACKATHON_DELIVERABLE.md).

## Calculation conventions

For each account: median money in (I), median fixed costs (F), median spending (S), median household bills (H), and the
mean of the latest six `avg_daily_balance` rows (B). P is the loan payment only for loans with status C or D. Money in
is recorded deposits, not verified employment income.

```text
buffer_left = B - one_off_costs
monthly_gap = spending_after_shock - income_after_shock
if buffer_left <= 0: runway = 0
elif monthly_gap <= 0: runway = 120+ (no shortfall)
else: runway = round(min(buffer_left / monthly_gap, 120), 1)
```

Threshold counts compare the one-decimal runway to strict thresholds (`<3`, `<6`, `<12`). The same formula is
implemented in Python (`src/services/shock_engine.py`) and in SQL (`MART.FN_ACCOUNT_SHOCK`); the parity tests check
that both give identical results for all 4,500 accounts.

## Deploy to Snowflake

Full instructions are in [`DEPLOY.md`](DEPLOY.md). In short:

```bash
pip install "snowflake-connector-python[pandas]>=3.12"
python scripts/setup_snowflake.py --connection default   # steps 00–12: load CSVs, build marts, train ML, Cortex
snow streamlit deploy --replace --connection default     # deploy the app
```

Requirements: a role that can create a warehouse, database and role; Cortex AI and ML functions in your region; the
`SYSTEM_COMPUTE_POOL_CPU` compute pool; the Snowflake CLI.

## Run locally

Use Python 3.11 or newer:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

With a working connection in `~/.snowflake/connections.toml` the app reads Snowflake. Without one it falls back to
the nine CSVs in `tangerine/data/`; the stress model, TANG and other ML outputs are then unavailable.

## Tests

```bash
python -m pytest                       # baseline, shock engine, planner, data quality, charts, Snowflake parity
python -m pytest overdraft_risk/tests  # overdraft risk model
python src/discovery/run_discoveries.py
```

## Limitations

- The 55% money-in scenario is a simulation on recorded deposits, not observed job loss or confirmed EI eligibility.
- Pre-loan buffer, penalty interest and loan outcomes are associations, not causal evidence; running loans may not
  have final outcomes.
- An authorized-user disposition does not prove a spouse, partner or co-borrower.
- Standing orders are an undated snapshot; external loan-payment orders are instructions, not confirmed external debt.
- Cash withdrawals are not classified as discretionary spending.
- ML steps (stress model retraining, anomaly detection, forecast) can shift slightly when the setup is rerun.

## Repository map

| Path | Contents |
|---|---|
| `app.py` | Streamlit entry point and grouped sidebar navigation |
| `src/ui/` | Pages (`overview`, `hidden_patterns`, `customer_explorer`, `shock_simulator`, `recovery_planner`, `ai_advisor`, `discoveries`, `methodology`) and the ECharts wrapper `charts.py` |
| `src/services/` | Baseline metrics, shock engine, recovery planner, hidden-pattern queries, case narratives |
| `src/data/` | `snowflake_repository.py` (live) and `local_repository.py` (CSV fallback) |
| `overdraft_risk/` | 6-month overdraft model: service, page, saved weights, training and tests |
| `setup/` | Ordered `00`–`12` SQL build of the whole Snowflake backend |
| `scripts/setup_snowflake.py` | Runs `setup/` in order, uploads the CSVs, can resume with `--from` |
| `sql/` | Original step scripts the setup was assembled from (reference) |
| `tangerine/data/` | The nine challenge CSVs |
| `Dashboards/` | Standalone HTML exploration dashboards |
| `reports/` | Data audit, hidden-pattern discovery, hackathon deliverable and demo script |
| `tests/` | pytest suite, including Snowflake parity tests |
| `snowflake.yml`, `pyproject.toml` | Streamlit in Snowflake deploy config and app dependencies |
